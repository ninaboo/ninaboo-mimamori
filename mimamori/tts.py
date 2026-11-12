"""AivisSpeech Engine: download, run hidden in the background, synthesize."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from . import paths, winjob
from .download import download

RELEASES_API = "https://api.github.com/repos/Aivis-Project/AivisSpeech-Engine/releases/latest"
SEVEN_ZIP_URL = "https://www.7-zip.org/a/7zr.exe"   # tiny standalone .7z extractor
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW

StatusFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]

_ARCHIVE_RE = re.compile(r"\.(zip|7z)(\.\d{3})?$", re.I)


class EngineError(RuntimeError):
    pass


def _local_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


# --------------------------------------------------------------------------- install
def choose_assets(assets: list[dict], gpu: bool) -> list[dict]:
    """Pick the Windows x64 archive (all parts, in order) from a GitHub release."""
    def n(a):
        return a["name"].lower()

    archives = [
        a for a in assets
        if "windows" in n(a) and any(x in n(a) for x in ("x64", "amd64", "x86_64"))
        and _ARCHIVE_RE.search(a["name"])
    ]
    if not archives:
        return []
    flavoured = [a for a in archives if any(k in n(a) for k in ("cpu", "gpu", "directml", "cuda"))]
    if flavoured:
        want = ("gpu", "directml") if gpu else ("cpu",)
        pick = [a for a in archives if any(k in n(a) for k in want)]
        archives = pick or archives
    # group split volumes (foo.7z.001, foo.7z.002 ...) by base name
    groups: dict[str, list[dict]] = {}
    for a in archives:
        base = re.sub(r"\.\d{3}$", "", a["name"])
        groups.setdefault(base, []).append(a)
    first = sorted(groups)[0]
    return sorted(groups[first], key=lambda a: a["name"])


def find_run_exe(folder: Path) -> Optional[Path]:
    name = "run.exe" if sys.platform == "win32" else "run"
    hits = sorted(folder.rglob(name), key=lambda p: len(p.parts))
    return hits[0] if hits else None


def install_engine(
    gpu: bool,
    status: StatusFn,
    progress: ProgressFn,
    cancel: threading.Event,
    manual_url: str = "",
) -> Path:
    """Download + extract AivisSpeech Engine into engines/aivisspeech. Returns run.exe path."""
    paths.ensure_dirs()
    if manual_url:
        parts = [{"name": manual_url.rsplit("/", 1)[-1].split("?")[0],
                  "browser_download_url": manual_url, "size": None}]
    else:
        status("Looking up the latest AivisSpeech Engine release…")
        r = requests.get(RELEASES_API, timeout=20, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        rel = r.json()
        parts = choose_assets(rel.get("assets", []), gpu)
        if not parts:
            names = ", ".join(a["name"] for a in rel.get("assets", []))
            raise EngineError("Couldn't find a Windows x64 build in the latest release. "
                              f"Assets: {names}. Paste a direct URL in Settings instead.")
        status(f"Release {rel.get('tag_name', '?')}: {', '.join(p['name'] for p in parts)}")

    total = sum(p.get("size") or 0 for p in parts)
    done_before = 0
    files: list[Path] = []
    for p in parts:
        dest = paths.DOWNLOADS / p["name"]
        status(f"Downloading {p['name']}…")
        download(
            p["browser_download_url"], dest,
            progress=lambda d, t, base=done_before: progress(base + d, total or t),
            cancel=cancel, expected_size=p.get("size"),
        )
        done_before += dest.stat().st_size
        files.append(dest)

    # wipe any previous install, then extract
    if paths.AIVIS_DIR.exists():
        shutil.rmtree(paths.AIVIS_DIR, ignore_errors=True)
    paths.AIVIS_DIR.mkdir(parents=True, exist_ok=True)

    first = files[0]
    status("Extracting… (this can take a minute)")
    progress(0, 0)
    if first.name.lower().endswith(".zip"):
        with zipfile.ZipFile(first) as z:
            z.extractall(paths.AIVIS_DIR)
    else:
        seven = paths.TOOLS_DIR / "7zr.exe"
        if not seven.exists():
            status("Downloading 7-Zip extractor…")
            download(SEVEN_ZIP_URL, seven, cancel=cancel)
        # 7zr picks up .002, .003 … automatically when given .001
        res = subprocess.run(
            [str(seven), "x", str(first), f"-o{paths.AIVIS_DIR}", "-y"],
            capture_output=True, text=True, creationflags=NO_WINDOW,
        )
        if res.returncode != 0:
            raise EngineError(f"Extraction failed: {res.stderr or res.stdout}")

    exe = find_run_exe(paths.AIVIS_DIR)
    if not exe:
        raise EngineError("Extracted the engine but couldn't find run.exe inside it.")
    for f in files:                      # free the disk space
        f.unlink(missing_ok=True)
    status("AivisSpeech Engine installed.")
    return exe


# --------------------------------------------------------------------------- run + synth
class Engine:
    def __init__(self, url_fn: Callable[[], str]) -> None:
        self._url_fn = url_fn
        self.proc: Optional[subprocess.Popen] = None
        self._log_handle = None
        self.http = _local_session()

    @property
    def url(self) -> str:
        return self._url_fn()

    @property
    def log_path(self) -> Path:
        return paths.LOGS / "aivisspeech.log"

    def is_up(self) -> bool:
        try:
            return self.http.get(f"{self.url}/version", timeout=2).ok
        except requests.RequestException:
            return False

    def owns_process(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _last_log_line(self) -> str:
        try:
            with open(self.log_path, "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 4096))
                lines = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if ln.strip()]
                return re.sub(r"\x1b\[[0-9;]*m", "", lines[-1])[:200] if lines else ""
        except OSError:
            return ""

    def start(self, exe: str, port: int, gpu: bool, status: StatusFn,
              cancel: Optional[threading.Event] = None, timeout: float = 30 * 60) -> None:
        if self.is_up():
            status("AivisSpeech Engine is running.")
            return
        if not exe or not Path(exe).exists():
            raise EngineError("AivisSpeech Engine isn't installed yet.")
        args = [exe, "--host", "127.0.0.1", "--port", str(port)]
        if gpu:
            args.append("--use_gpu")
        self._log_handle = open(self.log_path, "wb")
        self.proc = subprocess.Popen(
            args, cwd=str(Path(exe).parent), stdout=self._log_handle,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
        winjob.attach(self.proc)   # ends with Mimamori, even after a crash
        status("Starting AivisSpeech Engine… (first start downloads ~900 MB of voice data)")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if cancel is not None and cancel.is_set():
                self.stop()
                raise EngineError("Cancelled.")
            if self.proc.poll() is not None:
                raise EngineError(f"Engine exited (code {self.proc.returncode}). "
                                  f"Last log line: {self._last_log_line()}")
            if self.is_up():
                status("AivisSpeech Engine is running.")
                return
            line = self._last_log_line()
            status(f"Engine starting… {line}" if line else "Engine starting…")
            time.sleep(1.5)
        raise EngineError("Timed out waiting for the engine to start.")

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    # -- voice model management (AivisSpeech /aivm_models API) ------------------
    def _check(self, r: requests.Response) -> None:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except ValueError:
                detail = r.text[:200]
            raise EngineError(f"AivisSpeech said: {detail or r.status_code}")

    def models(self) -> list[VoiceModel]:
        r = self.http.get(f"{self.url}/aivm_models", timeout=30)
        self._check(r)
        data = r.json()
        out = [_model_from_info(uuid, info) for uuid, info in data.items()]
        return sorted(out, key=lambda m: m.name.lower())

    def install_from_url(self, url: str) -> None:
        r = self.http.post(f"{self.url}/aivm_models/install", data={"url": url}, timeout=1800)
        self._check(r)

    def install_from_file(self, path: str) -> None:
        with open(path, "rb") as fh:
            r = self.http.post(f"{self.url}/aivm_models/install",
                               files={"file": (Path(path).name, fh, "application/octet-stream")},
                               timeout=1800)
        self._check(r)

    def update_model(self, uuid: str) -> None:
        self._check(self.http.post(f"{self.url}/aivm_models/{uuid}/update", timeout=1800))

    def uninstall_model(self, uuid: str) -> None:
        self._check(self.http.delete(f"{self.url}/aivm_models/{uuid}/uninstall", timeout=120))

    def speakers(self) -> list[tuple[str, int]]:
        r = self.http.get(f"{self.url}/speakers", timeout=10)
        r.raise_for_status()
        out = []
        for sp in r.json():
            for st in sp.get("styles", []):
                out.append((f"{sp['name']} – {st['name']}", int(st["id"])))
        return out

    def synth(self, text: str, speaker: int, speed: float = 1.0, volume: float = 1.0) -> bytes:
        q = self.http.post(f"{self.url}/audio_query",
                           params={"text": text, "speaker": speaker}, timeout=60)
        q.raise_for_status()
        query = q.json()
        query["speedScale"] = speed
        query["volumeScale"] = volume
        r = self.http.post(f"{self.url}/synthesis", params={"speaker": speaker},
                           data=json.dumps(query), headers={"Content-Type": "application/json"},
                           timeout=120)
        r.raise_for_status()
        return r.content


# --------------------------------------------------------------------------- voice models
HUB_PAGE = "https://hub.aivis-project.com/"
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def model_source_url(text: str) -> str:
    """Turn what the user pasted into a download link the engine can install from.

    Accepts an AivisHub page link, a bare model ID, or a direct .aivmx link.
    """
    text = text.strip()
    if text.lower().split("?")[0].endswith(".aivmx"):
        return text
    m = _UUID_RE.search(text)
    if m:
        return f"https://api.aivis-project.com/v1/aivm-models/{m.group(0).lower()}/download?model_type=AIVMX"
    if text.startswith(("http://", "https://")):
        return text
    raise ValueError("Paste an AivisHub link, a model ID, or a link to an .aivmx file.")


@dataclass
class VoiceModel:
    uuid: str
    name: str
    version: str
    latest_version: str
    creators: str
    size_mb: float
    styles: int
    loaded: bool
    update_available: bool
    default: bool
    private: bool


def _model_from_info(uuid: str, info: dict) -> VoiceModel:
    man = info.get("manifest") or {}
    speakers = man.get("speakers") or info.get("speakers") or []
    styles = sum(len(sp.get("styles") or []) for sp in speakers) or len(speakers)
    return VoiceModel(
        uuid=uuid,
        name=man.get("name") or uuid,
        version=str(man.get("version") or ""),
        latest_version=str(info.get("latest_version") or ""),
        creators=", ".join(man.get("creators") or []),
        size_mb=(info.get("file_size") or 0) / 1e6,
        styles=styles,
        loaded=bool(info.get("is_loaded")),
        update_available=bool(info.get("is_update_available")),
        default=bool(info.get("is_default_model")),
        private=bool(info.get("is_private_model")),
    )


def play_wav(data: bytes) -> None:
    """Blocking preview playback (Windows only; silently skipped elsewhere)."""
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(data, winsound.SND_MEMORY)
