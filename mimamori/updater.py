"""Checks GitHub for a newer Mimamori and updates the app in place.

Updating replaces only Mimamori.exe and _internal\\. Settings, the voice
engine, models and logs in the app folder are left alone.

A running exe can't overwrite itself, so the swap is done by a small
PowerShell script: Mimamori starts it, quits, and the script waits for
Mimamori to exit, swaps the files, and starts the new version.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from . import __version__, paths
from .download import download

REPO = "ninaboo/ninaboo-mimamori"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_RE = re.compile(r"^Mimamori-.*-windows\.zip$", re.I)
EXE = "Mimamori.exe"

NO_WINDOW = 0x08000000           # CREATE_NO_WINDOW
DETACHED = 0x00000008            # DETACHED_PROCESS


def parse_version(v: str) -> tuple[int, ...]:
    """'v0.2.10' -> (0, 2, 10). Anything after the numbers is ignored."""
    nums = re.findall(r"\d+", v.split("-")[0])
    return tuple(int(n) for n in nums) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def can_self_update() -> bool:
    """Only the built exe on Windows can swap itself; running from source can't."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


@dataclass
class Release:
    version: str          # e.g. "v0.2.1"
    page_url: str
    notes: str
    asset_url: Optional[str]
    asset_name: Optional[str]
    asset_size: Optional[int]


def check_latest(timeout: float = 10) -> Release:
    r = requests.get(LATEST_API, timeout=timeout,
                     headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    data = r.json()
    asset = next((a for a in data.get("assets", []) if ASSET_RE.match(a["name"])), None)
    return Release(
        version=data.get("tag_name", ""),
        page_url=data.get("html_url", RELEASES_PAGE),
        notes=data.get("body") or "",
        asset_url=asset["browser_download_url"] if asset else None,
        asset_name=asset["name"] if asset else None,
        asset_size=asset["size"] if asset else None,
    )


def stage_dir() -> Path:
    return paths.TEMP / "update"


def download_and_stage(rel: Release, progress: Optional[Callable[[int, int], None]] = None,
                       cancel: Optional[threading.Event] = None) -> Path:
    """Download the release zip and unpack it. Returns the folder holding the new exe."""
    if not rel.asset_url:
        raise RuntimeError("That release has no Windows download attached.")
    zpath = download(rel.asset_url, paths.DOWNLOADS / rel.asset_name,
                     progress=progress, cancel=cancel, expected_size=rel.asset_size)
    dest = stage_dir()
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    zpath.unlink(missing_ok=True)
    new_root = find_new_root(dest)
    if new_root is None:
        raise RuntimeError("The download didn't contain Mimamori.exe and _internal.")
    return new_root


def find_new_root(folder: Path) -> Optional[Path]:
    for exe in sorted(folder.rglob(EXE), key=lambda p: len(p.parts)):
        if (exe.parent / "_internal").is_dir():
            return exe.parent
    return None


def _ps_quote(p: Path | str) -> str:
    return "'" + str(p).replace("'", "''") + "'"


def write_swap_script(new_root: Path, app_root: Path, pid: int) -> Path:
    """PowerShell script that waits for Mimamori to exit, swaps files, restarts it."""
    script = stage_dir() / "apply_update.ps1"
    log = paths.LOGS / "update.log"
    body = f"""$ErrorActionPreference = 'Stop'
Start-Transcript -Path {_ps_quote(log)} -Force | Out-Null
try {{
    $new = {_ps_quote(new_root)}
    $app = {_ps_quote(app_root)}
    Write-Output "Waiting for Mimamori (pid {pid}) to close..."
    Wait-Process -Id {pid} -Timeout 60 -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800

    # retry a few times in case Windows still has the files open
    for ($i = 1; $i -le 10; $i++) {{
        try {{
            if (Test-Path "$app\\_internal") {{ Remove-Item "$app\\_internal" -Recurse -Force }}
            Move-Item "$new\\_internal" "$app\\_internal"
            Copy-Item "$new\\{EXE}" "$app\\{EXE}" -Force
            break
        }} catch {{
            Write-Output "Attempt $i failed: $_"
            if ($i -eq 10) {{ throw }}
            Start-Sleep -Seconds 1
        }}
    }}
    Write-Output "Files replaced. Starting the new version."
    Remove-Item {_ps_quote(stage_dir())} -Recurse -Force -ErrorAction SilentlyContinue
}} catch {{
    Write-Output "Update failed: $_"
}} finally {{
    Start-Process -FilePath "$app\\{EXE}" -WorkingDirectory $app
    Stop-Transcript | Out-Null
}}
"""
    # UTF-8 with BOM so Windows PowerShell 5 reads non-English folder names correctly
    script.write_text(body, encoding="utf-8-sig")
    return script


def launch_swap(script: Path) -> None:
    """Start the swap script detached; the caller must quit straight afterwards."""
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-File", str(script)],
        cwd=str(script.parent), creationflags=NO_WINDOW | DETACHED,
        close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def prepare_restart(new_root: Path) -> Path:
    return write_swap_script(new_root, paths.ROOT, os.getpid())
