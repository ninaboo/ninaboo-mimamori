import time

from mimamori import japanese, pipeline
from mimamori.pipeline import Context, migrate_tags, pick_voice, process_note
from tests.conftest import fake_tokenize


class FakeAnki:
    def __init__(self, tags=None):
        self.media, self.tags = {}, tags or {}

    def store_media(self, name, data):
        self.media[name] = data

    def find_notes(self, query):
        tag = query.split(":", 1)[1]
        return [n for n, ts in self.tags.items() if tag in ts]

    def add_tags(self, ids, tag):
        for i in ids:
            self.tags[i].add(tag)

    def remove_tags(self, ids, tag):
        for i in ids:
            self.tags[i].discard(tag)


class FakeEngine:
    def synth(self, text, speaker, speed=1.0, volume=1.0):
        return f"{speaker}:{text}".encode()


class FakeTranslator:
    loaded = True

    def __init__(self):
        self.calls = []

    def define(self, word, reading, sentence, senses):
        self.calls.append(("define", senses))
        return "to lose (a person)"

    def translate(self, sentence, word="", meaning="", words=""):
        self.calls.append(("translate", meaning, words))
        return "He lost his parents in the earthquake."


def make_note(**fields):
    base = {
        "Word": "失う", "WordReading": "失[うしな]う", "PartOfSpeech": "Godan verb",
        "Sentence": "彼は地震で親を<b>失いました</b>。", "SentenceFurigana": "",
        "WordMeaning": "<ol><li>to lose</li><li>to miss</li></ol>", "SentenceEnglish": "",
        "WordAudio": "[sound:yomitan.mp3]", "SentenceAudio": "", "Frequency": "",
    }
    base.update(fields)
    return {"noteId": 42, "fields": {k: {"value": v} for k, v in base.items()}}


def run(note, cfg, clipboard=(), translator=None, anki=None):
    ctx = Context(cfg, anki or FakeAnki(), FakeEngine(), translator or FakeTranslator(),
                  lambda: list(clipboard), lambda _msg: None)
    return process_note(note, ctx)


def test_fills_every_field(cfg):
    cfg["speaker_ids"] = [7]
    tr, anki = FakeTranslator(), FakeAnki()
    up = run(make_note(), cfg, translator=tr, anki=anki).updates
    assert up["SentenceFurigana"] == "彼[かれ]は 地震[じしん]で 親[おや]を<b> 失[うしな]いました</b>。"
    assert up["WordMeaning"] == "to lose (a person)"
    assert up["SentenceEnglish"] == "He lost his parents in the earthquake."
    assert up["PartOfSpeech"] == "Verb"
    # Yomitan's word audio is replaced, and word + sentence use the same voice
    assert up["WordAudio"].startswith("[sound:mimamori_42_word_")
    assert {d.decode().split(":")[0] for d in anki.media.values()} == {"7"}
    # the translator got the dictionary senses, the chosen meaning and the word list
    assert tr.calls[0] == ("define", ["to lose", "to miss"])
    assert tr.calls[1][1] == "to lose (a person)"
    assert "失い(失う)" in tr.calls[1][2]


def test_kana_only_reading_becomes_kanji_with_furigana(cfg):
    assert run(make_note(WordReading="うしなう"), cfg).updates["WordReading"] == "失[うしな]う"


def test_unknown_part_of_speech_is_guessed(cfg):
    for word, expected in (("羨ましい", "I-adjective"), ("青春", "Noun"), ("勉強する", "Verb")):
        note = make_note(Word=word, WordReading="x[y]", PartOfSpeech="Unknown", Sentence="")
        assert run(note, cfg).updates["PartOfSpeech"] == expected


def test_clipboard_sentence_replaces_yomitans(cfg):
    clip = [(time.time() - 2, "彼は地震で親を\n失いました。")]      # copied across two lines
    up = run(make_note(Sentence="違う文。"), cfg, clipboard=clip).updates
    assert up["Sentence"] == "彼は地震で親を<b>失いました</b>。"
    assert up["SentenceFurigana"].startswith("彼[かれ]は")


def test_no_voice_ticked_skips_audio(cfg):
    cfg["speaker_ids"] = []
    res = run(make_note(), cfg)
    assert "WordAudio" not in res.updates
    assert res.warnings == ["No voice selected; skipped audio"]


def test_pick_voice_never_repeats_twice_in_a_row():
    picks = [pick_voice([1, 2, 3]) for _ in range(30)]
    assert all(a != b for a, b in zip(picks, picks[1:]))


def test_migrate_old_tags(cfg):
    anki = FakeAnki({1: {"aaf_done"}, 2: {"aaf_error"}, 3: {"aaf_done", "x"}})
    assert migrate_tags(anki, cfg) == 3
    assert anki.tags == {1: {"mimamori"}, 2: {"mimamori_error"}, 3: {"mimamori", "x"}}
    assert migrate_tags(anki, cfg) == 0


def test_word_hints():
    assert japanese.word_hints(fake_tokenize("彼は地震で親を失いました。")) == \
        "彼 | は | 地震 | で | 親 | を | 失い(失う) | まし(ます) | た"
