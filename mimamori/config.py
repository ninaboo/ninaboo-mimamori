"""Settings stored in config.json next to the exe."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "config_version": 2,
    # Anki
    "anki_url": "http://127.0.0.1:8765",
    "deck": "",
    "note_type": "Mimamori",
    "poll_seconds": 2.0,
    "done_tag": "mimamori",
    "error_tag": "mimamori_error",

    # Sentence source: "auto" | "yomitan" | "clipboard"
    #   auto      -> clipboard if it contains the word, otherwise Yomitan
    "sentence_source": "auto",
    "clipboard_max_age": 300,   # seconds; older clipboard entries are ignored

    # Look
    "theme": "dark",                       # "dark" | "light"

    # Startup / tray
    "start_with_windows": False,           # mirrors the registry entry (see autostart.py)
    "auto_watch": False,                   # start watching as soon as Mimamori opens
    "close_to_tray": True,                 # ✕ hides to the tray instead of quitting
    "tray_hint_shown": False,

    # Field clean-up
    "first_definition_only": True,
    "normalize_pos": True,

    # AivisSpeech
    "engine_mode": "managed",              # "managed" (we run it) | "external"
    "engine_port": 10111,                  # managed engine port (avoids AivisSpeech app's 10101)
    "engine_external_url": "http://127.0.0.1:10101",
    "engine_gpu": False,
    "engine_exe": "",                      # set after download
    "engine_asset_url": "",                # optional manual download URL override
    "speaker_id": None,                    # legacy single voice (migrated to speaker_ids)
    "speaker_label": "",
    "speaker_ids": [],                     # voices to pick from; one is chosen per card
    "voice_cache": [],                     # [[label, id], ...] last list seen from the engine
    "speed": 1.0,
    "volume": 0.15,                         # 1.0 = AivisSpeech default loudness

    # Translation LLM
    "llm_choice": "plamo",                 # key in llm.MODEL_CATALOG or "custom"
    "llm_custom_url": "",
    "llm_path": "",                        # set after download
    "llm_gpu_layers": 0,                   # -1 = everything on GPU (needs a CUDA build)
    "llm_threads": 0,                      # 0 = auto
    "llm_runtime_url": "",                 # optional manual llama.cpp zip link
}


CONFIG_VERSION = 2
LEGACY_DONE_TAGS = ("aaf_done", "mimamori_done")
LEGACY_ERROR_TAGS = ("aaf_error",)
PATH_KEYS = ("engine_exe", "llm_path")   # stored relative to the app folder so it can move


def _to_abs(p: str) -> str:
    if not p:
        return p
    path = Path(p)
    return str(path if path.is_absolute() else (paths.ROOT / path).resolve())


def _to_rel(p: str) -> str:
    if not p:
        return p
    try:
        return str(Path(p).resolve().relative_to(paths.ROOT.resolve()))
    except ValueError:
        return p   # outside the app folder: keep absolute


class Config:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        saved_version = CONFIG_VERSION
        if paths.CONFIG_FILE.exists():
            try:
                saved = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
                saved_version = int(saved.get("config_version", 1))
                self.data.update({k: v for k, v in saved.items() if k in DEFAULTS})
            except (OSError, json.JSONDecodeError, ValueError):
                pass  # keep defaults; a broken file gets rewritten on next save
        for k in PATH_KEYS:
            self.data[k] = _to_abs(self.data[k])
        if saved_version < 2:
            # v2: renamed to Mimamori, quieter default voice volume
            if self.data["note_type"] in ("AnkiAutoFill JP", "Mimamori JP"):
                self.data["note_type"] = "Mimamori"
            if self.data["done_tag"] in LEGACY_DONE_TAGS:
                self.data["done_tag"] = "mimamori"
            if self.data["error_tag"] in LEGACY_ERROR_TAGS:
                self.data["error_tag"] = "mimamori_error"
            if self.data["volume"] == 0.6:      # untouched old default
                self.data["volume"] = 0.15
        self.data["config_version"] = CONFIG_VERSION
        # migrate the old single-voice setting
        if not self.data["speaker_ids"] and self.data["speaker_id"] is not None:
            sid = int(self.data["speaker_id"])
            self.data["speaker_ids"] = [sid]
            if not self.data["voice_cache"]:
                self.data["voice_cache"] = [[self.data["speaker_label"] or str(sid), sid]]

    def voice_label(self, sid: int) -> str:
        for label, vid in self.data["voice_cache"]:
            if int(vid) == int(sid):
                return label
        return str(sid)

    def save(self) -> None:
        with self._lock:
            out = dict(self.data)
            for k in PATH_KEYS:
                out[k] = _to_rel(out[k])
            tmp = paths.CONFIG_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(paths.CONFIG_FILE)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    @property
    def engine_url(self) -> str:
        if self.data["engine_mode"] == "external":
            return self.data["engine_external_url"].rstrip("/")
        return f"http://127.0.0.1:{self.data['engine_port']}"
