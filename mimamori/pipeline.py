"""Per-note processing and the polling watcher (no Qt here)."""
from __future__ import annotations

import hashlib
import random
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import japanese
from .anki import AnkiConnect, AnkiError, quote_query
from .config import Config
from .llm import Translator
from .textutil import (
    align_furigana, bold_html, clean_meaning, extract_bold, glossary_senses, has_kanji, kata_to_hira, normalize_pos,
    parse_furigana_field, pick_clipboard_sentence, pieces_to_anki, strip_html,
)
from .tts import Engine

LogFn = Callable[[str], None]


@dataclass
class Context:
    cfg: Config
    anki: AnkiConnect
    engine: Engine
    translator: Translator
    clipboard: Callable[[], list[tuple[float, str]]]
    log: LogFn


@dataclass
class Result:
    updates: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.warnings


def _ensure_llm(ctx: "Context") -> None:
    if not ctx.translator.loaded:
        c = ctx.cfg
        ctx.translator.load(c["llm_path"], c["llm_gpu_layers"], c["llm_threads"],
                            status=lambda m: ctx.log(f"  {m}"))


def _h(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def _clipboard_miss_reason(history: list[tuple[float, str]], word: str, max_age: float) -> str:
    if not history:
        return "nothing copied since Mimamori started, used Yomitan's sentence"
    ts, text = history[-1]
    age = time.time() - ts
    snippet = " ".join(text.split())[:40]
    if age > max_age:
        return (f"last copy was {age / 60:.0f} min ago (only the last {max_age / 60:.0f} min count), "
                f"used Yomitan's sentence")
    return f"last copy ({age:.0f}s ago) doesn't contain {word}: 「{snippet}」, used Yomitan's sentence"


_last_voice: Optional[int] = None


def pick_voice(voices: list[int]) -> int:
    """Random voice for this card, avoiding the same voice twice in a row."""
    global _last_voice
    choices = [v for v in voices if v != _last_voice] if len(voices) > 1 else voices
    _last_voice = random.choice(choices)
    return _last_voice


def process_note(note: dict, ctx: Context) -> Result:
    cfg = ctx.cfg
    f = {k: v["value"] for k, v in note["fields"].items()}
    nid = note["noteId"]
    res = Result()
    up = res.updates

    word = strip_html(f.get("Word", ""))
    if not word:
        res.warnings.append("Word field is empty")
        return res

    # ---- reading --------------------------------------------------------------
    # WordReading must be kanji with furigana (失[うしな]う) so the back shows the
    # kanji with the reading above it. If Yomitan gave only kana, rebuild it.
    reading_field = f.get("WordReading", "")
    if strip_html(reading_field):
        shown, word_kana = parse_furigana_field(reading_field)
        if has_kanji(word) and not has_kanji(shown):
            word_kana = kata_to_hira(word_kana)
            up["WordReading"] = pieces_to_anki(align_furigana(word, word_kana)).strip()
    else:
        toks = japanese.tokenize(word)
        pieces = [p for t in toks for p in align_furigana(t.surface, t.reading)]
        up["WordReading"] = pieces_to_anki(pieces).strip()
        _, word_kana = parse_furigana_field(up["WordReading"])

    # ---- sentence -------------------------------------------------------------
    y_plain, y_span = extract_bold(f.get("Sentence", ""))
    plain, span, from_clip = y_plain, y_span, False
    mode = cfg["sentence_source"]
    if mode in ("auto", "clipboard"):
        history = ctx.clipboard()
        clip = pick_clipboard_sentence(history, word, cfg["clipboard_max_age"])
        if clip and clip != y_plain:
            plain, span, from_clip = clip, None, True
        elif clip:
            ctx.log("  clipboard: same sentence as Yomitan's")
        else:
            ctx.log("  clipboard: " + _clipboard_miss_reason(history, word, cfg["clipboard_max_age"]))
            if mode == "clipboard":
                res.warnings.append("No clipboard sentence with this word; used Yomitan's")
    if from_clip:
        ctx.log(f"  sentence from clipboard: {plain}")

    if plain:
        tokens = japanese.tokenize(plain)
        if span is None:
            span = japanese.find_target_span(plain, tokens, word, word_kana)
        if from_clip or (span and y_span is None):
            up["Sentence"] = bold_html(plain, span)
        if from_clip or not strip_html(f.get("SentenceFurigana", "")):
            up["SentenceFurigana"] = japanese.sentence_furigana(plain, tokens, span)
    else:
        res.warnings.append("No sentence (Yomitan field empty and nothing on clipboard)")

    # ---- meaning / part of speech -------------------------------------------
    # The LLM picks the sense that fits the sentence (from Yomitan's definitions if there
    # are any, otherwise on its own). Falls back to Yomitan's first definition.
    meaning_raw = f.get("WordMeaning", "")
    senses = glossary_senses(meaning_raw)
    meaning = clean_meaning(meaning_raw, cfg["first_definition_only"]) if senses else ""
    if plain:
        try:
            _ensure_llm(ctx)
            picked = ctx.translator.define(word, word_kana, plain, senses)
            if picked:
                meaning = picked
        except Exception as e:  # noqa: BLE001
            if not meaning:
                res.warnings.append(f"Translation failed (meaning): {e}")
    if meaning and meaning != meaning_raw:
        up["WordMeaning"] = meaning
    pos_raw = f.get("PartOfSpeech", "")
    if cfg["normalize_pos"]:
        pos = normalize_pos(pos_raw)
        if pos.strip().lower() in ("", "unknown", "?", "-"):
            # Yomitan writes "Unknown" when its dictionary has no part of speech
            pos = japanese.guess_pos(word) or pos
        if pos != pos_raw:
            up["PartOfSpeech"] = pos

    # ---- translation ----------------------------------------------------------
    if plain and (from_clip or not strip_html(f.get("SentenceEnglish", ""))):
        try:
            _ensure_llm(ctx)
            up["SentenceEnglish"] = ctx.translator.translate(plain, word, meaning,
                                                             japanese.word_hints(tokens))
        except Exception as e:  # noqa: BLE001
            res.warnings.append(f"Translation failed: {e}")

    # ---- audio ---------------------------------------------------------------
    # Word audio is always regenerated (replacing Yomitan's), and both clips use
    # the same voice, picked from the selected voices for this card.
    voices = [int(v) for v in (cfg["speaker_ids"] or [])]
    if not voices:
        res.warnings.append("No voice selected; skipped audio")
    else:
        speaker = pick_voice(voices)
        ctx.log(f"  voice: {cfg.voice_label(speaker)}")
        try:
            tts_text = word_kana or word   # kana avoids misread kanji
            name = f"mimamori_{nid}_word_{_h(f'{speaker}:{tts_text}')}.wav"
            ctx.anki.store_media(name, ctx.engine.synth(tts_text, speaker, cfg["speed"], cfg["volume"]))
            up["WordAudio"] = f"[sound:{name}]"
            if plain:
                name = f"mimamori_{nid}_sent_{_h(f'{speaker}:{plain}')}.wav"
                ctx.anki.store_media(name, ctx.engine.synth(plain, speaker, cfg["speed"], cfg["volume"]))
                up["SentenceAudio"] = f"[sound:{name}]"
        except Exception as e:  # noqa: BLE001
            res.warnings.append(f"Audio failed: {e}")

    return res


class Watcher:
    """Polls the chosen deck and processes new notes on a background thread."""

    def __init__(self, ctx: Context, on_count: Optional[Callable[[int, int], None]] = None) -> None:
        self.ctx = ctx
        self.on_count = on_count or (lambda ok, bad: None)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.ok = 0
        self.bad = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def query(self) -> str:
        c = self.ctx.cfg
        return (f'deck:"{quote_query(c["deck"])}" note:"{quote_query(c["note_type"])}" '
                f'-tag:{c["done_tag"]} -tag:{c["error_tag"]}')

    def _run(self) -> None:
        log = self.ctx.log
        log(f"Watching deck '{self.ctx.cfg['deck']}'…")
        try:
            name = self.ctx.cfg["note_type"]
            if name not in self.ctx.anki.model_names():
                log(f"※ Anki has no note type called '{name}', so no cards will be picked up. "
                    f"Rename your note type to '{name}' in Anki (Tools → Manage Note Types), "
                    f"or click 'Create / update note type' on the Setup tab.")
        except AnkiError:
            pass
        failures_in_a_row = 0
        waiting_logged = False
        while not self._stop.is_set():
            try:
                ids = self.ctx.anki.find_notes(self.query())
                if ids and self.ctx.cfg["speaker_ids"] and not self.ctx.engine.is_up():
                    # don't burn cards with "audio failed" while the engine is still starting
                    if not waiting_logged:
                        log("Waiting for the voice engine to finish starting…")
                        waiting_logged = True
                    self._stop.wait(2)
                    continue
                waiting_logged = False
                if ids:
                    time.sleep(0.5)  # let Yomitan/clipboard settle
                    for note in self.ctx.anki.notes_info(ids):
                        if self._stop.is_set():
                            break
                        self._handle(note)
                failures_in_a_row = 0
            except AnkiError as e:
                failures_in_a_row += 1
                if failures_in_a_row in (1, 10) or failures_in_a_row % 60 == 0:
                    log(f"※ {e}")
            except Exception:  # noqa: BLE001
                log("※ Unexpected error:\n" + traceback.format_exc())
            self._stop.wait(max(0.5, float(self.ctx.cfg["poll_seconds"])))
        log("Watcher stopped.")

    def _handle(self, note: dict) -> None:
        c, log, anki = self.ctx.cfg, self.ctx.log, self.ctx.anki
        nid = note["noteId"]
        word = strip_html(note["fields"].get("Word", {}).get("value", "")) or f"note {nid}"
        log(f"→ {word}")
        try:
            res = process_note(note, self.ctx)
            if res.updates:
                anki.update_fields(nid, res.updates)
                # AnkiConnect can silently skip updates while the note is open in Browse
                before = note["fields"]
                after = anki.notes_info([nid])[0]["fields"]
                changed = [k for k in res.updates if k in after]
                if changed and all(after[k]["value"] == before[k]["value"] for k in changed):
                    res.warnings.append("Anki didn't save the update — close the note in "
                                        "the Browse window and use 'Retry errors'")
            for w in res.warnings:
                log(f"  ※ {w}")
            hard_fail = any(w.startswith(("Audio failed", "Translation failed", "Anki didn't",
                                          "Word field")) for w in res.warnings)
            if hard_fail:
                anki.add_tags([nid], c["error_tag"])
                self.bad += 1
            else:
                anki.add_tags([nid], c["done_tag"])
                self.ok += 1
                log(f"  ✓ filled {', '.join(res.updates) or 'nothing (already complete)'}")
        except Exception as e:  # noqa: BLE001
            log(f"  ✗ {e}")
            try:
                anki.add_tags([nid], c["error_tag"])
            except AnkiError:
                pass
            self.bad += 1
        self.on_count(self.ok, self.bad)

    def retry_errors(self) -> int:
        c = self.ctx.cfg
        ids = self.ctx.anki.find_notes(
            f'deck:"{quote_query(c["deck"])}" note:"{quote_query(c["note_type"])}" tag:{c["error_tag"]}'
        )
        if ids:
            self.ctx.anki.remove_tags(ids, c["error_tag"])
        return len(ids)


def migrate_tags(anki: AnkiConnect, cfg: Config) -> int:
    """Move notes from old tag names (aaf_done, …) to the current ones."""
    from .config import LEGACY_DONE_TAGS, LEGACY_ERROR_TAGS
    moved = 0
    for old_tags, new in ((LEGACY_DONE_TAGS, cfg["done_tag"]), (LEGACY_ERROR_TAGS, cfg["error_tag"])):
        for old in old_tags:
            if old == new:
                continue
            ids = anki.find_notes(f"tag:{old}")
            if ids:
                anki.add_tags(ids, new)
                anki.remove_tags(ids, old)
                moved += len(ids)
    return moved
