"""Shared test setup.

The tests cover Mimamori's pure logic (furigana, bolding, clipboard picking,
field processing, config migration…). They don't need Anki, AivisSpeech,
llama.cpp or even the Japanese dictionary: tokenising is faked with a small
table so the tests run anywhere with `python -m pytest`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mimamori import config, japanese, paths  # noqa: E402
from mimamori.japanese import Token  # noqa: E402

# surface, reading, base form, pos1, pos2
TOKENS = {
    "彼は地震で親を失いました。": [
        ("彼", "カレ", "彼", "代名詞", ""), ("は", "ハ", "は", "助詞", "係助詞"),
        ("地震", "ジシン", "地震", "名詞", ""), ("で", "デ", "で", "助詞", "格助詞"),
        ("親", "オヤ", "親", "名詞", ""), ("を", "ヲ", "を", "助詞", "格助詞"),
        ("失い", "ウシナイ", "失う", "動詞", ""), ("まし", "マシ", "ます", "助動詞", ""),
        ("た", "タ", "た", "助動詞", ""), ("。", None, "。", "補助記号", ""),
    ],
    "失う": [("失う", "ウシナウ", "失う", "動詞", "")],
    "羨ましい": [("羨ましい", "ウラヤマシイ", "羨ましい", "形容詞", "")],
    "青春": [("青春", "セイシュン", "青春", "名詞", "")],
    "勉強する": [("勉強", "ベンキョウ", "勉強", "名詞", ""), ("する", "スル", "する", "動詞", "")],
}


def fake_tokenize(text: str) -> list[Token]:
    out, pos = [], 0
    for surf, reading, base, p1, p2 in TOKENS.get(text, []):
        i = text.find(surf, pos)
        out.append(Token(surf, i, i + len(surf), reading, base, base, p1, p2))
        pos = i + len(surf)
    return out


@pytest.fixture(autouse=True)
def fake_japanese(monkeypatch):
    monkeypatch.setattr(japanese, "tokenize", fake_tokenize)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A Config that reads/writes a temporary config.json."""
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config.json")
    return config.Config()
