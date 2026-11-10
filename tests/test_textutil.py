import time

from mimamori.textutil import (
    align_furigana, bold_html, clean_meaning, extract_bold, glossary_senses, normalize_pos,
    parse_furigana_field, pick_clipboard_sentence, pieces_to_anki,
)


def test_align_furigana_keeps_okurigana_outside():
    assert align_furigana("失い", "ウシナイ") == [("失", "うしな"), ("い", None)]
    assert pieces_to_anki(align_furigana("取り扱い", "トリアツカイ")) == " 取[と]り 扱[あつか]い"


def test_align_furigana_without_kanji_is_untouched():
    assert align_furigana("ブッキング", "ブッキング") == [("ブッキング", None)]


def test_extract_and_rebuild_bold():
    plain, span = extract_bold("彼は地震で親を<b>失いました</b>。")
    assert plain == "彼は地震で親を失いました。"
    assert plain[span[0]:span[1]] == "失いました"
    assert bold_html(plain, span) == "彼は地震で親を<b>失いました</b>。"


def test_parse_furigana_field():
    assert parse_furigana_field("失[うしな]う") == ("失う", "うしなう")
    assert parse_furigana_field(" 飲[の]み 物[もの]") == ("飲み物", "のみもの")


def test_glossary_senses_and_first_meaning():
    html = "<ol><li>to lose; to part with</li><li>to miss (an opportunity)</li></ol>"
    assert glossary_senses(html) == ["to lose; to part with", "to miss (an opportunity)"]
    assert clean_meaning(html) == "to lose; to part with"
    assert glossary_senses("") == []


def test_normalize_pos():
    assert normalize_pos("Godan verb with u ending, Transitive verb") == "Verb"
    assert normalize_pos("Noun, Suru verb") == "Noun"
    assert normalize_pos("副詞") == "Adverb"


def test_clipboard_uses_whole_copy_with_lines_joined():
    now = time.time()
    hist = [(now - 3, "「昨日はどうだった？」\n「楽しかったよ。\nまた行きたいな」")]
    assert pick_clipboard_sentence(hist, "昨日", 300, now) == "「昨日はどうだった？」「楽しかったよ。また行きたいな」"


def test_clipboard_matches_conjugated_word_and_respects_age():
    now = time.time()
    assert pick_clipboard_sentence([(now - 5, "彼は失いました")], "失う", 300, now) == "彼は失いました"
    assert pick_clipboard_sentence([(now - 900, "彼は失いました")], "失う", 300, now) is None
    assert pick_clipboard_sentence([(now - 5, "関係ない文")], "失う", 300, now) is None
