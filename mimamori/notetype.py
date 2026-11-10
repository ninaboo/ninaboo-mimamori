"""The note type the app creates in Anki (fields, card templates, CSS).

Audio: both sound tags sit only on the back, word first then sentence.
Anki autoplays sounds in template order, so flipping the card plays
word -> sentence. The front has no audio and the back doesn't include
{{FrontSide}}, so nothing is played twice.
"""
from __future__ import annotations

from .anki import AnkiConnect

FIELDS = [
    "Word",              # Yomitan {expression}
    "WordReading",       # Yomitan {furigana-plain}       e.g. 失[うしな]う
    "PartOfSpeech",      # Yomitan {part-of-speech}       (normalised to "Verb" etc.)
    "Sentence",          # Yomitan {cloze-prefix}<b>{cloze-body}</b>{cloze-suffix}  or clipboard
    "SentenceFurigana",  # app: furigana + bold
    "WordMeaning",       # Yomitan {glossary-brief}; the model picks the sense that fits
    "SentenceEnglish",   # app: LLM translation
    "WordAudio",         # app: AivisSpeech
    "SentenceAudio",     # app: AivisSpeech
    "Frequency",         # Yomitan {frequency-harmonic-rank}
]

# Which Yomitan marker to put in each field (shown in the app + README).
YOMITAN_MAPPING = {
    "Word": "{expression}",
    "WordReading": "{furigana-plain}",
    "PartOfSpeech": "{part-of-speech}",
    "Sentence": "{cloze-prefix}<b>{cloze-body}</b>{cloze-suffix}",
    "SentenceFurigana": "",
    "WordMeaning": "{glossary-brief}",
    "SentenceEnglish": "",
    "WordAudio": "",
    "SentenceAudio": "",
    "Frequency": "{frequency-harmonic-rank}",
}

TEMPLATE_NAME = "Recognition"
LEGACY_NAMES = ("AnkiAutoFill JP", "Mimamori JP")

FRONT = """\
<div class="japanese" style="font-size:60px;">{{Word}}</div>

<div style="font-size: 16px; ">{{PartOfSpeech}}</div>
<br/><br/><br/><br/><br/>
<div id="example-sentence" class="japanese" style="font-size:40px;">{{Sentence}}</div>
"""

BACK = """\
<div>{{WordAudio}}{{SentenceAudio}}</div>
<div class="japanese" style="font-size:60px;">{{furigana:WordReading}}</div>

<div style="font-size: 14px; ">{{PartOfSpeech}}</div>

<div style="font-size: 16px; ">{{WordMeaning}}</div>

<hr id=answer>

{{#SentenceFurigana}}<div class="japanese" style="font-size: 40px; ">{{furigana:SentenceFurigana}}</div>{{/SentenceFurigana}}
{{^SentenceFurigana}}<div class="japanese" style="font-size: 40px; ">{{Sentence}}</div>{{/SentenceFurigana}}
<div style="font-size: 20px; ">{{SentenceEnglish}}</div>
<!---->

<div style="font-size: 14pt;">
<a class="japanese ios-only" href="mkdaijirin://jp.monokakido.DAIJIRIN/search?text={{text:Word}}&srcname=Anki&src=anki://">大辞林</a><a class="japanese ios-only" href="mkwisdom2://jp.monokakido.WISDOM2/search?text={{text:Word}}&srcname=Anki&src=anki://">ウィズダム</a><a class="japanese" href="https://thesaurus.weblio.jp/content/{{text:Word}}">類語辞典</a><a class="ios-only" href="ebpocket://search?text={{text:Word}}#anki://">EBPocket</a><a href="https://jisho.org/search/{{text:Word}}">jisho</a><a href="https://ejje.weblio.jp/content/{{text:Word}}">weblio</a>
</div>
<br/>
<!--<div style="font-size: 10pt;">{{Frequency}}</div>-->
"""

CSS = """\
@font-face { font-family: stroke; src: url('_stroke.ttf'); }
@font-face { font-family: textbook; src: url('_HGSKyokashotai.ttf'); }
@font-face {
   font-family: 'localnoto';
   font-style: normal;
   font-weight: 400;
   src: url('_NotoSansJP-Medium.otf') format('opentype');
 }

.card {
 font-family:  'localnoto', 'notosans', 'ヒラギノ明朝 ProN', 'Hiragino Mincho Pro', 'serif';
 font-size: 25px;
 text-align: center;
 color: White;
 background-color: Black;
}

img {
 max-height: 150px;
 margin: 10px;
}

div {
 padding-top:5px;
 padding-bottom:5px;
}

a {
 color: turquoise;
 margin: 5px;
}

.ios-only { display: none; }
.mac-only { display: none; }

.mobile .ios-only { display: inline; }
.mac .mac-only { display: inline; }

.stroke { font-family: "stroke"; }
.japanese { font-family: "Meiryo"; }

.mac { font-family: 'ヒラギノ明朝 ProN', 'Hiragino Mincho Pro', 'serif'; }
.mac .stroke { font-family: stroke; }
.mac .japanese { font-family: Meiryo; }

.mobile { font-family: textbook, 'Hiragino Mincho Pro', 'serif'; }
"""


def ensure_note_type(anki: AnkiConnect, name: str) -> str:
    """Create the note type, or update templates/CSS if it already exists.

    Returns a short message describing what happened.
    """
    models = anki.model_names()
    if name not in models:
        legacy = [m for m in LEGACY_NAMES if m in models and m != name]
        if legacy:
            return (f"Your cards still use the note type '{legacy[0]}'. In Anki, go to Tools → "
                    f"Manage Note Types, select it, click Rename and call it '{name}'. "
                    f"Then click this button again.")
    if name in models:
        missing = [f for f in FIELDS if f not in anki.model_field_names(name)]
        anki.invoke(
            "updateModelTemplates",
            model={"name": name, "templates": {TEMPLATE_NAME: {"Front": FRONT, "Back": BACK}}},
        )
        anki.invoke("updateModelStyling", model={"name": name, "css": CSS})
        if missing:
            return f"Updated '{name}' templates, but it's missing fields: {', '.join(missing)}"
        return f"Updated templates and styling for '{name}'."

    anki.invoke(
        "createModel",
        modelName=name,
        inOrderFields=FIELDS,
        css=CSS,
        isCloze=False,
        cardTemplates=[{"Name": TEMPLATE_NAME, "Front": FRONT, "Back": BACK}],
    )
    return f"Created note type '{name}'."
