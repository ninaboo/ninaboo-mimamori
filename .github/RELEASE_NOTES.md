Mimamori watches an Anki deck and finishes the Japanese cards you mine with Yomitan: natural voice audio (AivisSpeech), furigana, a meaning that fits the sentence and an English translation, all made on your own PC.

## What's new in v0.2.1

- **Updates itself:** Mimamori now checks for new releases. When one is out, an **Update** button appears at the top; one click downloads it and restarts into the new version, keeping your settings, voices and models.
- **Voice manager:** *Setup → Voices → Manage voices…* lists your AivisSpeech voices and lets you add new ones (paste an AivisHub link or choose an `.aivmx` file), update them when a new version is out, or remove them.
- **Can't get stuck in the background any more:** only one Mimamori runs at a time (opening it again brings the existing window forward), and the voice engine and translation server now always close together with Mimamori, even if it crashes.
- Coming from **v0.2.0**? That version can't update itself yet, so update by hand once: quit Mimamori, delete the old `Mimamori.exe` and `_internal`, and copy in the new ones from this zip. From now on it's one click.

## Download and run

1. Download **Mimamori-…-windows.zip** below and unzip it anywhere (e.g. your Documents folder).
2. Run **Mimamori.exe**. Windows may show a SmartScreen warning because the app isn't code-signed. Click **More info → Run anyway**.
3. Follow the **Setup** tab: create the note type, point Yomitan at it, then download the voice engine and translation model. See the [README](https://github.com/ninaboo/ninaboo-mimamori#getting-started) for the full walkthrough, including the Yomitan field settings.

No Python and no installer needed. Everything Mimamori downloads stays inside its folder; delete the folder to uninstall.

## You'll need

- Windows 10 (22H2) or 11, 64-bit
- [Anki](https://apps.ankiweb.net/) with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on, and [Yomitan](https://github.com/yomidevs/yomitan) in your browser
- About 4 GB of free space. On first run Mimamori downloads the AivisSpeech voice engine (~900 MB of voice data), llama.cpp, and a translation model (PLaMo 3 Translate 2B, ~1.8 GB)

## Highlights

- Watches a deck and fills new Yomitan cards within a couple of seconds
- Several AivisSpeech voices: one voice per card, picked at random, reads both the word and the sentence
- Uses the sentence you copied just before mining, if it contains the word
- Contextual word meanings and translations from PLaMo 3 Translate, a Japanese↔English specialist model that runs on CPU
- Furigana with the mined word in bold, and a card layout with your own font
- Pink dark and light themes, a tray icon (start/stop watching, retry failed cards) and an option to start with Windows

The translation models and AivisSpeech voices come with their own licences (PLaMo: free for personal use). See the README for details.
