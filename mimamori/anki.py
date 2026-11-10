"""Minimal AnkiConnect client (API version 6)."""
from __future__ import annotations

import base64
from typing import Any

import requests


class AnkiError(RuntimeError):
    pass


class AnkiConnect:
    def __init__(self, url: str = "http://127.0.0.1:8765", timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False  # never route localhost through a system proxy

    def invoke(self, action: str, **params: Any) -> Any:
        try:
            r = self.session.post(
                self.url,
                json={"action": action, "version": 6, "params": params},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise AnkiError(f"Can't reach AnkiConnect at {self.url}. Is Anki open? ({e})") from e
        data = r.json()
        if data.get("error"):
            raise AnkiError(f"{action}: {data['error']}")
        return data.get("result")

    # -- convenience wrappers -------------------------------------------------
    def version(self) -> int:
        return self.invoke("version")

    def deck_names(self) -> list[str]:
        return sorted(self.invoke("deckNames"))

    def model_names(self) -> list[str]:
        return self.invoke("modelNames")

    def model_field_names(self, model: str) -> list[str]:
        return self.invoke("modelFieldNames", modelName=model)

    def find_notes(self, query: str) -> list[int]:
        return self.invoke("findNotes", query=query)

    def notes_info(self, ids: list[int]) -> list[dict]:
        return self.invoke("notesInfo", notes=ids)

    def update_fields(self, note_id: int, fields: dict[str, str]) -> None:
        self.invoke("updateNoteFields", note={"id": note_id, "fields": fields})

    def add_tags(self, ids: list[int], tags: str) -> None:
        self.invoke("addTags", notes=ids, tags=tags)

    def remove_tags(self, ids: list[int], tags: str) -> None:
        self.invoke("removeTags", notes=ids, tags=tags)

    def store_media(self, filename: str, data: bytes) -> str:
        return self.invoke(
            "storeMediaFile", filename=filename, data=base64.b64encode(data).decode("ascii")
        )


def quote_query(value: str) -> str:
    """Escape a value for use inside "..." in an Anki search."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
