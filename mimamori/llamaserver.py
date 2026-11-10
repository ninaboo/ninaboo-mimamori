"""Runs llama.cpp's own `llama-server.exe` for translation.

Using the official llama.cpp builds (instead of the llama-cpp-python library)
means brand-new models like PLaMo 3 Translate work as soon as llama.cpp
supports them, and GPU use doesn't need a special rebuild of Mimamori.
The runtime is downloaded into engines/llama-<flavour>/ inside the app folder.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

from . import paths
from .download import download

RELEASES_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20"
ASSET_PATTERNS = {
    "cpu": re.compile(r"^llama-.*-bin-win-cpu-x64\.zip$", re.I),
    "vulkan": re.compile(r"^llama-.*-bin-win-vulkan-x64\.zip$", re.I),
}
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
EXE_NAME = "llama-server.exe" if sys.platform == "win32" else "llama-server"

StatusFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]


class LlamaError(RuntimeError):
    pass


def runtime_dir(flavour: str) -> Path:
    return paths.ENGINES / f"llama-{flavour}"


def find_exe(flavour: str) -> Optional[Path]:
    d = runtime_dir(flavour)
    if not d.exists():
        return None
    hits = sorted(d.rglob(EXE_NAME), key=lambda p: len(p.parts))
    return hits[0] if hits else None


def pick_asset(releases: list[dict], flavour: str) -> Optional[tuple[str, dict]]:
    """Newest release (stable or nightly) that has a Windows build of this flavour."""
    pat = ASSET_PATTERNS[flavour]
    for rel in releases:
        for a in rel.get("assets", []):
            if pat.match(a["name"]):
                return rel.get("tag_name", "?"), a
    return None


def install(flavour: str, status: StatusFn, progress: Optional[ProgressFn] = None,
            cancel: Optional[threading.Event] = None, manual_url: str = "") -> Path:
    paths.ensure_dirs()
    if manual_url:
        name = manual_url.rsplit("/", 1)[-1].split("?")[0] or "llama.zip"
        tag, asset = "manual", {"name": name, "browser_download_url": manual_url, "size": None}
    else:
        status("Looking up the latest llama.cpp build…")
        r = requests.get(RELEASES_API, timeout=20, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        found = pick_asset(r.json(), flavour)
        if not found:
            raise LlamaError(f"Couldn't find a Windows {flavour} build of llama.cpp. Paste a direct "
                             f"link to a llama-…-bin-win-{flavour}-x64.zip in config.json "
                             f"(llm_runtime_url) and try again.")
        tag, asset = found
    status(f"Downloading llama.cpp {tag} ({flavour})…")
    zpath = download(asset["browser_download_url"], paths.DOWNLOADS / asset["name"],
                     progress=progress, cancel=cancel, expected_size=asset.get("size"))
    dest = runtime_dir(flavour)
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    status("Unpacking llama.cpp…")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    zpath.unlink(missing_ok=True)
    (dest / "VERSION.txt").write_text(tag, encoding="utf-8")
    exe = find_exe(flavour)
    if not exe:
        raise LlamaError("Unpacked llama.cpp but couldn't find llama-server.exe in it.")
    status(f"llama.cpp {tag} ready.")
    return exe


class LlamaServer:
    def __init__(self, port: int = 10112) -> None:
        self.port = port
        self.proc: Optional[subprocess.Popen] = None
        self.model: Optional[str] = None
        self.gpu_layers: int = 0
        self._log = None
        self.http = requests.Session()
        self.http.trust_env = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def log_path(self) -> Path:
        return paths.LOGS / "llama-server.log"

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def healthy(self) -> bool:
        try:
            return self.http.get(f"{self.url}/health", timeout=2).status_code == 200
        except requests.RequestException:
            return False

    def _last_log_line(self) -> str:
        try:
            lines = [ln for ln in self.log_path.read_text("utf-8", "replace").splitlines() if ln.strip()]
            return lines[-1][:240] if lines else ""
        except OSError:
            return ""

    def start(self, exe: Path, model: str, gpu_layers: int = 0, threads: int = 0,
              ctx: int = 4096, status: Optional[StatusFn] = None, timeout: float = 300) -> None:
        if self.running() and self.model == model and self.gpu_layers == gpu_layers:
            return
        self.stop()
        args = [str(exe), "-m", model, "--host", "127.0.0.1", "--port", str(self.port),
                "-c", str(ctx), "-ngl", str(999 if gpu_layers < 0 else gpu_layers), "--jinja"]
        if threads:
            args += ["-t", str(threads)]
        self._log = open(self.log_path, "wb")
        self.proc = subprocess.Popen(args, cwd=str(exe.parent), stdout=self._log,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     creationflags=NO_WINDOW)
        self.model, self.gpu_layers = model, gpu_layers
        if status:
            status("Loading translation model…")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                last = self._last_log_line()
                self.stop()
                raise LlamaError(f"llama.cpp couldn't load the model. Last log line: {last}")
            if self.healthy():
                return
            time.sleep(0.5)
        self.stop()
        raise LlamaError("Timed out waiting for the translation model to load.")

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.model = None
        if self._log:
            self._log.close()
            self._log = None

    def complete(self, prompt: str, max_tokens: int, stop: list[str], temperature: float = 0.0) -> str:
        r = self.http.post(f"{self.url}/v1/completions", timeout=300, json={
            "prompt": prompt, "max_tokens": max_tokens, "stop": stop,
            "temperature": temperature, "cache_prompt": True,
        })
        r.raise_for_status()
        return r.json()["choices"][0]["text"]

    def chat(self, messages: list[dict], max_tokens: int, temperature: float = 0.0) -> str:
        r = self.http.post(f"{self.url}/v1/chat/completions", timeout=300, json={
            "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
        })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
