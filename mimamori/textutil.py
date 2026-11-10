"""Pure text helpers (no third-party dependencies, unit-testable)."""
from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser
from typing import Iterable, Optional

KANJI_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヵヶ]")
TAG_RE = re.compile(r"(<[^>]+>)")
FURIGANA_FIELD_RE = re.compile(r" ?([^ \[\]>]+?)\[([^\]]*)\]")


# --------------------------------------------------------------------------- basics
def has_kanji(s: str) -> bool:
    return bool(KANJI_RE.search(s))


def is_hiragana(ch: str) -> bool:
    return "ぁ" <= ch <= "ゟ"


def kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def strip_html(s: str) -> str:
    s = re.sub(r"(?i)<br\s*/?>", " ", s or "")
    s = TAG_RE.sub("", s)
    return html.unescape(s).replace(" ", " ").strip()


def extract_bold(html_text: str) -> tuple[str, Optional[tuple[int, int]]]:
    """Return (plain_text, (start, end) of the first <b>/<strong> run or None)."""
    plain: list[str] = []
    length = 0
    depth = 0
    span_start: Optional[int] = None
    span: Optional[tuple[int, int]] = None
    for part in TAG_RE.split(re.sub(r"(?i)<br\s*/?>", " ", html_text or "")):
        if not part:
            continue
        if part.startswith("<"):
            tag = part.lower()
            if re.match(r"<\s*(b|strong)\b", tag):
                if depth == 0 and span is None:
                    span_start = length
                depth += 1
            elif re.match(r"<\s*/\s*(b|strong)\b", tag):
                depth = max(0, depth - 1)
                if depth == 0 and span_start is not None and span is None:
                    span = (span_start, length)
            continue
        text = html.unescape(part).replace(" ", " ")
        plain.append(text)
        length += len(text)
    if span_start is not None and span is None:
        span = (span_start, length)
    full = "".join(plain)
    # trim outer whitespace and shift the span accordingly
    lead = len(full) - len(full.lstrip())
    full_stripped = full.strip()
    if span:
        s, e = span[0] - lead, span[1] - lead
        s, e = max(0, s), min(len(full_stripped), e)
        span = (s, e) if e > s else None
    return full_stripped, span


def bold_html(plain: str, span: Optional[tuple[int, int]]) -> str:
    if not span:
        return html.escape(plain, quote=False)
    s, e = span
    esc = lambda t: html.escape(t, quote=False)  # noqa: E731
    return f"{esc(plain[:s])}<b>{esc(plain[s:e])}</b>{esc(plain[e:])}"


# --------------------------------------------------------------------------- furigana
def align_furigana(surface: str, reading: Optional[str]) -> list[tuple[str, Optional[str]]]:
    """Split a word into (text, ruby) pieces, keeping okurigana outside the ruby.

    align_furigana("失い", "ウシナイ") -> [("失", "うしな"), ("い", None)]
    """
    if not reading or not has_kanji(surface):
        return [(surface, None)]
    reading = kata_to_hira(reading)
    runs: list[tuple[str, bool]] = []  # (text, is_kanji)
    for ch in surface:
        k = bool(KANJI_RE.match(ch))
        if runs and runs[-1][1] == k:
            runs[-1] = (runs[-1][0] + ch, k)
        else:
            runs.append((ch, k))
    pattern = "".join("(.+?)" if k else re.escape(kata_to_hira(t)) for t, k in runs)
    m = re.fullmatch(pattern, reading)
    if not m:
        return [(surface, reading)]
    out: list[tuple[str, Optional[str]]] = []
    gi = 1
    for text, k in runs:
        if k:
            out.append((text, m.group(gi)))
            gi += 1
        else:
            out.append((text, None))
    return out


def pieces_to_anki(pieces: Iterable[tuple[str, Optional[str]]]) -> str:
    """Anki furigana syntax: ' 漢字[かんじ]' (leading space marks where ruby starts)."""
    out = []
    for text, ruby in pieces:
        t = html.escape(text, quote=False)
        out.append(f" {t}[{ruby}]" if ruby else t)
    return "".join(out)


def parse_furigana_field(value: str) -> tuple[str, str]:
    """'失[うしな]う' -> ('失う', 'うしなう')  (plain, kana)."""
    v = strip_html(value)
    plain = FURIGANA_FIELD_RE.sub(lambda m: m.group(1), v).replace(" ", "")
    kana = FURIGANA_FIELD_RE.sub(lambda m: m.group(2), v).replace(" ", "")
    return plain, kana


# --------------------------------------------------------------------------- meaning
class _FirstLi(HTMLParser):
    """Collects the text of the first <li>, separating nested items with ', '."""

    BREAKS = {"li", "br", "div", "p", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0          # depth inside the first li (0 = not inside)
        self.done = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if self.depth == 0:
            if tag == "li":
                self.depth = 1
            return
        if tag == "li":
            self.depth += 1
        if tag in self.BREAKS:
            self.parts.append("\x00")

    def handle_endtag(self, tag):
        if self.done or self.depth == 0:
            return
        if tag == "li":
            self.depth -= 1
            if self.depth == 0:
                self.done = True
            else:
                self.parts.append("\x00")

    def handle_startendtag(self, tag, attrs):
        if self.depth and not self.done and tag == "br":
            self.parts.append("\x00")

    def handle_data(self, data):
        if self.depth and not self.done:
            self.parts.append(data)


def _join_parts(parts: list[str]) -> str:
    chunks, cur = [], []
    for p in parts:
        if p == "\x00":
            chunks.append("".join(cur))
            cur = []
        else:
            cur.append(p)
    chunks.append("".join(cur))
    cleaned = [re.sub(r"\s+", " ", c).strip(" ,;") for c in chunks]
    return ", ".join(c for c in cleaned if c)


class _AllLi(HTMLParser):
    """Text of every top-level <li> (one per dictionary sense)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.items: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.depth += 1
            if self.depth == 1:
                self.items.append([])
                return
        if self.depth and tag in _FirstLi.BREAKS:
            self.items[-1].append("\x00")

    def handle_endtag(self, tag):
        if tag == "li" and self.depth:
            self.depth -= 1
            if self.depth:
                self.items[-1].append("\x00")

    def handle_startendtag(self, tag, attrs):
        if self.depth and tag == "br":
            self.items[-1].append("\x00")

    def handle_data(self, data):
        if self.depth:
            self.items[-1].append(data)


def glossary_senses(value: str, limit: int = 12) -> list[str]:
    """Every definition Yomitan put in the field, as plain text, one per sense."""
    if not value or not strip_html(value):
        return []
    if re.search(r"(?i)<li\b", value):
        p = _AllLi()
        p.feed(value)
        senses = [_join_parts(parts) for parts in p.items]
        senses = [x for x in senses if x]
        if senses:
            return senses[:limit]
    return [re.sub(r"\s+", " ", strip_html(value)).strip()]


def clean_meaning(value: str, first_only: bool = True) -> str:
    if not value:
        return ""
    if first_only and re.search(r"(?i)<li\b", value):
        p = _FirstLi()
        p.feed(value)
        text = _join_parts(p.parts)
        if text:
            return text
    return re.sub(r"\s+", " ", strip_html(value)).strip()


# --------------------------------------------------------------------------- part of speech
_POS_RULES = [
    (("adverb", "副詞"), "Adverb"),
    (("i-adjective", "adjective (keiyoushi)", "形容詞"), "I-adjective"),
    (("na-adjective", "adjectival noun", "形容動詞", "形状詞"), "Na-adjective"),
    (("adjective",), "Adjective"),
    (("verb", "動詞"), "Verb"),
    (("pronoun", "代名詞"), "Pronoun"),
    (("noun", "名詞"), "Noun"),
    (("expression", "表現", "連語"), "Expression"),
    (("particle", "助詞"), "Particle"),
    (("conjunction", "接続詞"), "Conjunction"),
    (("interjection", "感動詞"), "Interjection"),
    (("counter", "助数詞"), "Counter"),
    (("prefix", "接頭"), "Prefix"),
    (("suffix", "接尾"), "Suffix"),
]


def normalize_pos(value: str) -> str:
    text = strip_html(value)
    if not text:
        return ""
    for item in re.split(r"[,、;/]", text):
        low = item.strip().lower()
        for keys, label in _POS_RULES:
            if any(k in low for k in keys):
                return label
    return text


# --------------------------------------------------------------------------- clipboard


def word_stems(word: str) -> list[str]:
    stems = [word]
    if len(word) >= 2 and is_hiragana(word[-1]) and has_kanji(word):
        stems.append(word[:-1])
        base = word.rstrip("".join(c for c in word if is_hiragana(c)))
        if base and base not in stems:
            stems.append(base)
    elif len(word) >= 3 and is_hiragana(word[-1]):
        stems.append(word[:-1])
    return stems


def pick_clipboard_sentence(
    history: list[tuple[float, str]],
    word: str,
    max_age: float,
    now: Optional[float] = None,
) -> Optional[str]:
    """Newest clipboard entry (within max_age) that contains the word.

    The whole copied text is used (line breaks joined up), not just the
    sentence containing the word.
    """
    now = time.time() if now is None else now
    stems = word_stems(word)
    for ts, text in reversed(history):
        if now - ts > max_age:
            break
        text = (text or "").strip()
        if not text or len(text) > 1000:
            continue
        if any(stem and stem in text for stem in stems):
            joined = re.sub(r"[ \t\u3000]*\r?\n[ \t\u3000]*", "", text)   # Japanese lines join with no space
            joined = re.sub(r"\s+", " ", joined).strip()
            return joined or None
    return None
