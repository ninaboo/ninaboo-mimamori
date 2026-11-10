"""Tokenising, bolding and sentence furigana (fugashi + unidic-lite)."""
from __future__ import annotations

import html
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .textutil import align_furigana, kata_to_hira, pieces_to_anki

_tagger = None


@dataclass
class Token:
    surface: str
    start: int
    end: int
    reading: Optional[str]   # katakana/hiragana reading of the surface form
    lemma: str
    base: str                # written base form (orthBase)
    pos1: str
    pos2: str


def _feat(f, name: str) -> Optional[str]:
    v = getattr(f, name, None)
    return None if v in (None, "", "*") else v


def _find_unidic_dir() -> Optional[Path]:
    """Locate unidic-lite's dictionary folder, even if its __init__ wasn't bundled."""
    try:
        import unidic_lite
        d = getattr(unidic_lite, "DICDIR", None)
        if d and Path(d, "sys.dic").exists():
            return Path(d)
    except ImportError:
        pass
    candidates = []
    spec = importlib.util.find_spec("unidic_lite")
    if spec and spec.submodule_search_locations:
        candidates += [Path(p) / "dicdir" for p in spec.submodule_search_locations]
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    candidates += [base / "unidic_lite" / "dicdir", base / "_internal" / "unidic_lite" / "dicdir"]
    for c in candidates:
        if (c / "sys.dic").exists():
            return c
    return None


def get_tagger():
    global _tagger
    if _tagger is None:
        import fugashi  # imported lazily so the GUI opens fast
        dicdir = _find_unidic_dir()
        if dicdir is None:
            raise RuntimeError("Japanese dictionary (unidic-lite) not found in the app bundle.")
        rc = dicdir / "mecabrc"
        if not rc.exists():               # MeCab insists on an rc file; an empty one is fine
            from . import paths
            rc = paths.TEMP / "mecabrc"
            rc.parent.mkdir(parents=True, exist_ok=True)
            rc.touch()
        args = f'-d "{dicdir}" -r "{rc}"'
        _tagger = fugashi.Tagger(args)
    return _tagger


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    for w in get_tagger()(text):
        surf = w.surface
        idx = text.find(surf, pos)
        if idx < 0:
            continue
        f = w.feature
        lemma = (_feat(f, "lemma") or surf).split("-")[0]
        tokens.append(
            Token(
                surface=surf,
                start=idx,
                end=idx + len(surf),
                reading=_feat(f, "kana") or _feat(f, "pron"),
                lemma=lemma,
                base=_feat(f, "orthBase") or lemma,
                pos1=_feat(f, "pos1") or "",
                pos2=_feat(f, "pos2") or "",
            )
        )
        pos = idx + len(surf)
    return tokens


def _extends_word(t: Token) -> bool:
    """Tokens that belong to a conjugated word: 失い|まし|た, 失っ|て."""
    if t.pos1 == "助動詞":
        return True
    if t.pos1 == "助詞" and t.pos2 == "接続助詞" and t.surface in ("て", "で"):
        return True
    if t.pos1 == "接尾辞" and t.pos2 in ("形容詞的", "動詞的"):
        return True
    return False


def find_target_span(
    text: str, tokens: list[Token], word: str, reading: str = ""
) -> Optional[tuple[int, int]]:
    """Locate the mined word (in any conjugation) inside the sentence."""
    word_h = kata_to_hira(reading) if reading else ""
    for i, t in enumerate(tokens):
        hit = word in (t.base, t.lemma, t.surface)
        if not hit and word_h and t.reading:
            # kana-written word, e.g. Yomitan word うしなう vs token 失う
            hit = kata_to_hira(t.base) == word_h
        if hit:
            end = t.end
            for nxt in tokens[i + 1:]:
                if not _extends_word(nxt):
                    break
                end = nxt.end
            return (t.start, end)
    # literal fallback (multi-token words)
    idx = text.find(word)
    if idx >= 0:
        end = idx + len(word)
        for t in tokens:
            if t.start < end <= t.end:
                end = t.end
        return (idx, end)
    return None


def sentence_furigana(text: str, tokens: list[Token], span: Optional[tuple[int, int]]) -> str:
    """Build the SentenceFurigana field: furigana on kanji, target word bolded."""
    out: list[str] = []
    pos = 0
    bold = False
    for t in tokens:
        if t.start > pos:
            out.append(html.escape(text[pos:t.start], quote=False))
        in_span = bool(span) and t.start < span[1] and t.end > span[0]
        if in_span and not bold:
            out.append("<b>")
            bold = True
        elif not in_span and bold:
            out.append("</b>")
            bold = False
        out.append(pieces_to_anki(align_furigana(t.surface, t.reading)))
        pos = t.end
    if bold:
        out.append("</b>")
    if pos < len(text):
        out.append(html.escape(text[pos:], quote=False))
    return "".join(out).strip()


_POS_JP = {
    "動詞": "Verb", "名詞": "Noun", "形容詞": "I-adjective", "形状詞": "Na-adjective",
    "副詞": "Adverb", "代名詞": "Pronoun", "連体詞": "Pre-noun adjectival",
    "接続詞": "Conjunction", "感動詞": "Interjection", "助詞": "Particle",
}


def guess_pos(word: str) -> str:
    """Part of speech from the word itself (dictionary form)."""
    toks = tokenize(word)
    if not toks:
        return ""
    first = toks[0]
    # する-verbs written as one word (勉強する) tokenise as noun + する
    if len(toks) > 1 and first.pos1 == "名詞" and toks[-1].base in ("する", "為る"):
        return "Verb"
    return _POS_JP.get(first.pos1, "")


def word_hints(tokens: list[Token]) -> str:
    """'バイト | 来週 | から | 終わっ(終わる) | …' – shows the model how the sentence splits."""
    parts = []
    for t in tokens:
        if t.pos1 in ("補助記号", "空白") or not t.surface.strip():
            continue
        base = t.base or t.lemma
        parts.append(f"{t.surface}({base})" if base and base != t.surface else t.surface)
    return " | ".join(parts)
