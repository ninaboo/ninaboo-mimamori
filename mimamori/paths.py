"""Every file the app creates lives inside the folder that holds the exe.

Delete that folder and the app is gone. Nothing is written to AppData,
the registry or the user's home folder by this app.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _root() -> Path:
    if getattr(sys, "frozen", False):          # PyInstaller / Nuitka build
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # running from source


ROOT = _root()
CONFIG_FILE = ROOT / "config.json"
LOGS = ROOT / "logs"
TEMP = ROOT / "temp"
ENGINES = ROOT / "engines"
AIVIS_DIR = ENGINES / "aivisspeech"
TOOLS_DIR = ENGINES / "tools"
MODELS = ROOT / "models"
LLM_DIR = MODELS / "llm"
DOWNLOADS = ROOT / "temp" / "downloads"


def ensure_dirs() -> None:
    for d in (LOGS, TEMP, ENGINES, AIVIS_DIR, TOOLS_DIR, MODELS, LLM_DIR, DOWNLOADS):
        d.mkdir(parents=True, exist_ok=True)


def make_portable_env() -> None:
    """Point temp/cache env vars at our folder.

    Child processes (the AivisSpeech engine) inherit these too, so their
    temp files also land inside the app folder.
    """
    ensure_dirs()
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    for var in ("TEMP", "TMP", "TMPDIR"):
        os.environ[var] = str(TEMP)
    os.environ["XDG_CACHE_HOME"] = str(TEMP / "cache")
