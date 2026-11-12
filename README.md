# Mimamori 見守り

Mimamori watches an Anki deck and finishes the Japanese cards you mine with
[Yomitan](https://github.com/yomidevs/yomitan). Add a card from Yomitan and, a
couple of seconds later, it has natural voice audio, furigana, a contextual
meaning and an English translation, all made on your own PC.

## What it fills in

| Field | Where it comes from |
|---|---|
| Word, Frequency | Yomitan |
| WordReading | Yomitan, rebuilt as kanji with furigana if it's only kana |
| PartOfSpeech | Yomitan, shortened to "Verb", "Noun"…; worked out from the word if Yomitan says "Unknown" |
| Sentence | Yomitan's sentence, or the text you copied just before mining (see below) |
| SentenceFurigana | Furigana on every kanji, with the mined word in bold |
| WordMeaning | The meaning that fits the sentence, picked by the translation model |
| SentenceEnglish | Translated by a local model |
| WordAudio, SentenceAudio | [AivisSpeech](https://aivis-project.com/) voices, one voice per card, picked at random from the voices you tick |

On review, flipping a card plays the word, then the sentence.

## Requirements

- Windows 10 (22H2) or 11, 64-bit
- [Anki](https://apps.ankiweb.net/) with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on
- Yomitan in your browser
- About 4 GB of free disk space for the voice engine and translation model, which Mimamori downloads on first run

## Getting started

1. Download the latest release zip, unzip it anywhere and run `Mimamori.exe`.
2. **Setup tab → 1 · Anki:** with Anki open, click **Create / update note type**. This makes a note type called **Mimamori**.
3. **Yomitan:** Settings → Anki → Card format. Pick the **Mimamori** note type and set the fields as shown on the Setup tab:

   | Field | Yomitan marker |
   |---|---|
   | Word | `{expression}` |
   | WordReading | `{furigana-plain}` |
   | PartOfSpeech | `{part-of-speech}` |
   | Sentence | `{cloze-prefix}<b>{cloze-body}</b>{cloze-suffix}` |
   | WordMeaning | `{glossary-brief}` |
   | Frequency | `{frequency-harmonic-rank}` |

   Leave SentenceFurigana, SentenceEnglish, WordAudio and SentenceAudio empty.
4. **2 · Voices:** click **Download engine**. The first start downloads about 900 MB of voice data and takes a few minutes. Tick the voices you like (double-click one to preview it) and set the speed and volume.
5. **3 · Translation:** pick **PLaMo 3 Translate 2B** and click **Download model**, then **Test translation**.
6. **Watch tab:** pick your deck and click **Start watching**.

### Where the sentence comes from

With **Auto** (the default), copying text that contains the word just before you mine it makes that text the card's sentence. Lines are joined up, so a sentence copied across several lines works. Otherwise Yomitan's sentence is used. Only copies from the last 5 minutes count.

### Tray and startup

Minimising or closing the window keeps Mimamori running in the tray. Right-click the tray icon to start or stop watching, retry failed cards, open the window or quit. Under **Setup → 4 · Startup** you can have it start with Windows (quietly, in the tray) and begin watching automatically.

### Which cards get processed

Cards in the watched deck (and its subdecks) that use the **Mimamori** note type and don't have a `mimamori` (done) or `mimamori_error` (failed) tag yet. Fix whatever failed and click **Retry errors**. To redo a finished card, remove its `mimamori` tag in Anki.

## Updating

Mimamori checks GitHub for a new release when it starts (and twice a day while it runs). When there is one, an **Update to vX** button appears at the top. Click it and Mimamori downloads the new version, closes, swaps in the new `Mimamori.exe` and `_internal`, and starts again. If it was watching, it picks up where it left off. Your settings, voices and models aren't touched. A log of the swap is written to `logs\update.log`.

You can turn the check off, or run it by hand, under **Setup → 4 · Startup**.

To update by hand instead: quit Mimamori, delete the old `Mimamori.exe` and `_internal`, and copy the new ones in from the release zip.

## Everything stays in one folder

```
Mimamori\
├── Mimamori.exe, _internal\   the app
├── config.json                your settings
├── engines\                   AivisSpeech and llama.cpp (downloaded)
├── models\llm\                translation model (downloaded)
├── logs\                      app.log, aivisspeech.log, llama-server.log
└── temp\
```

To uninstall, delete the folder. Two things live outside it:
- The **Start with Windows** option adds one entry to Windows' startup list. Untick it first, or remove it under Task Manager → Startup apps.
- AivisSpeech keeps its voice models in `%APPDATA%\AivisSpeech-Engine`.

Your cards and their audio are stored in Anki, so they're kept either way.

## Translation models

| Option | Size | Notes |
|---|---|---|
| PLaMo 3 Translate 2B | ~1.8 GB | Japanese↔English specialist. Recommended, and fine on CPU |
| PLaMo 3 Translate 8B | ~5 GB | Most accurate. Best with a GPU |
| Qwen2.5 3B / 7B Instruct | 2–4.7 GB | General chat models |

The models run in llama.cpp's own `llama-server.exe`, which Mimamori downloads on first use. Set **GPU layers** to `-1` to run on your graphics card; that downloads llama.cpp's Vulkan build.

## Building from source

Needs Python 3.11 or 3.12 (64-bit) from python.org.

```
build.bat
```

The app ends up in `dist\Mimamori\`. Re-running `build.bat` only replaces the exe and `_internal`, so your settings and downloads in that folder are kept. `run_dev.bat` runs it straight from the source.

Tests (pure logic, no Anki or models needed):

```
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

## Licence

Mimamori is released under the [MIT License](LICENSE).

## Credits

Mimamori downloads these on first run, rather than bundling them:

- [AivisSpeech Engine](https://github.com/Aivis-Project/AivisSpeech-Engine) (LGPL-3.0). Each voice model has its own terms (listed on AivisHub); check them before sharing generated audio publicly.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT)
- [PLaMo 3 Translate](https://huggingface.co/pfnet/plamo-3-translate-2b-GGUF) by Preferred Networks, under the PLaMo Community License (free for personal use).
- [Qwen2.5](https://huggingface.co/Qwen): the 7B model is Apache-2.0; the 3B model uses the Qwen Research License (non-commercial)

The app itself is built on [PySide6](https://doc.qt.io/qtforpython-6/) (LGPL-3.0), and on [fugashi](https://github.com/polm/fugashi) (MIT) with [unidic-lite](https://github.com/polm/unidic-lite) (UniDic, BSD licence option).
