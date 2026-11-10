"""Resumable HTTP downloads with progress + cancel."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import requests

ProgressFn = Callable[[int, int], None]   # (downloaded_bytes, total_bytes or 0)

CHUNK = 1024 * 512
HEADERS = {"User-Agent": "Mimamori/0.2"}


class Cancelled(Exception):
    pass


def download(
    url: str,
    dest: Path,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[threading.Event] = None,
    expected_size: Optional[int] = None,
) -> Path:
    """Download url -> dest. Resumes from dest.part if it exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (expected_size is None or dest.stat().st_size == expected_size):
        if progress:
            size = dest.stat().st_size
            progress(size, size)
        return dest

    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = dict(HEADERS)
    if have:
        headers["Range"] = f"bytes={have}-"

    with requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True) as r:
        if have and r.status_code == 200:      # server ignored Range -> start over
            have = 0
        elif r.status_code == 416:             # already complete
            part.replace(dest)
            return dest
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0)) + have if r.headers.get("Content-Length") else 0
        mode = "ab" if have else "wb"
        done = have
        with open(part, mode) as f:
            for chunk in r.iter_content(CHUNK):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)

    if expected_size is not None and part.stat().st_size != expected_size:
        raise IOError(f"Download size mismatch for {dest.name}: "
                      f"got {part.stat().st_size}, expected {expected_size}. Try again.")
    part.replace(dest)
    return dest
