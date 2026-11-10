"""Translation and word meanings with a local model (GGUF in models/llm, run by llama-server)."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable, Optional

from . import paths
from .llamaserver import LlamaServer, find_exe, install

MODEL_CATALOG = {
    "plamo": {
        "label": "PLaMo 3 Translate 2B (~1.8 GB) – Japanese↔English specialist, recommended",
        "url": "https://huggingface.co/pfnet/plamo-3-translate-2b-GGUF/resolve/main/"
               "plamo-3-translate-2b-Q4_K_M.gguf",
    },
    "plamo8": {
        "label": "PLaMo 3 Translate 8B (~5 GB) – most accurate, best with a GPU",
        "url": "https://huggingface.co/pfnet/plamo-3-translate-8b-GGUF/resolve/main/"
               "plamo-3-translate-8b-Q4_K_M.gguf",
    },
    "small": {
        "label": "Small – Qwen2.5 3B Instruct Q4_K_M (~2 GB, fine on CPU)",
        "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
               "qwen2.5-3b-instruct-q4_k_m.gguf",
    },
    "medium": {
        "label": "Medium – Qwen2.5 7B Instruct Q4_K_M (~4.7 GB, better, best with GPU)",
        "url": "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/"
               "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    },
}

SYSTEM_PROMPT = (
    "You are an expert Japanese-to-English translator writing flashcards for a learner. "
    "The Japanese is often casual spoken dialogue: subjects and particles get dropped, and "
    "words like うち (my place / home / our family), バイト (part-time job) and 直行 (going "
    "straight somewhere) are common. Translate exactly what the Japanese says: keep time "
    "words precise (今週 = this week, 来週 = next week, 先週 = last week), keep who does what, "
    "keep the tone, and never add or invent information. A word list is given to show how "
    "the sentence splits up (dictionary forms in brackets).\n"
    "Reply in exactly this format:\n"
    "Notes: <one short line on the structure and any tricky words>\n"
    "Translation: <one natural English sentence>"
)

FEW_SHOT = [
    ("Target word: 集合 (meeting up)\n"
     "Sentence: 明日さ、部活終わったら駅前のカフェ集合ね。\n"
     "Words: 明日 | さ | 部活 | 終わっ(終わる) | たら | 駅前 | の | カフェ | 集合 | ね",
     "Notes: casual; たら = once/after; 集合ね = let's meet up; 部活 = club activities.\n"
     "Translation: Tomorrow, once club's over, let's meet up at the café in front of the station."),
    ("Target word: 失う (to lose)\n"
     "Sentence: 彼は地震で親を失いました。\n"
     "Words: 彼 | は | 地震 | で | 親 | を | 失い(失う) | まし(ます) | た",
     "Notes: で marks the cause; 親 = parents; polite past tense.\n"
     "Translation: He lost his parents in the earthquake."),
]


MEANING_PROMPT = (
    "You write the English meaning of a Japanese word for a language learner's flashcard. "
    "Use the example sentence to pick the sense of the word that fits it. If dictionary senses "
    "are given, choose from them. Reply with ONE to FOUR short English glosses separated by "
    "commas and nothing else: no quotes, no full sentences, no explanations."
)

MEANING_FEW_SHOT = [
    ("Word: 掛ける (かける)\nSentence: 彼はいつも眼鏡を掛けている。\n"
     "Dictionary senses:\n1. to hang up, to hang on\n2. to put on (glasses, etc.), to wear\n"
     "3. to spend (time, money)\n4. to make a phone call",
     "to wear, to put on (glasses)"),
    ("Word: 甘い (あまい)\nSentence: 子供に甘すぎるのは良くない。",
     "lenient, indulgent, soft on"),
]


def clean_meaning_output(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^(meaning|answer|english)\s*:\s*", "", line, flags=re.I)
    line = re.sub(r"^\d+\.\s*", "", line)
    line = line.strip().rstrip(".。").strip().strip('"“”「」\'').rstrip(".。").strip()
    return line[:80]


# --------------------------------------------------------------------------- PLaMo 3 Translate
# PLaMo 3 Translate is a translation-only model (Preferred Networks, PLaMo Community
# Licence: free for personal use). It doesn't follow chat instructions; it takes its
# own "PFML3" prompt format. llama.cpp adds <|plamo:bos|> itself.
PLAMO_STOP = ["<|plamo:tag|>", "<|plamo:bos|>"]


def is_plamo(model_path: str) -> bool:
    return "plamo" in Path(model_path).name.lower()


def pfml3_prompt(text: str, context: str = "") -> str:
    p = "<|plamo:tag|>dataset<|plamo:msg|>translation"
    if context:
        p += f"<|plamo:tag|>context<|plamo:msg|>{context}"
    p += (f"<|plamo:tag|>input<|plamo:key|>lang<|plamo:val|>ja<|plamo:msg|>{text}"
          "<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>en<|plamo:msg|>")
    return p


def _clean_plamo(text: str) -> str:
    for t in PLAMO_STOP + ["<|plamo:msg|>"]:
        text = text.split(t)[0]
    return " ".join(text.split()).strip()


def model_url(choice: str, custom_url: str) -> str:
    if choice == "custom":
        return custom_url.strip()
    return MODEL_CATALOG[choice]["url"]


def model_dest(url: str) -> Path:
    name = url.rsplit("/", 1)[-1].split("?")[0] or "model.gguf"
    return paths.LLM_DIR / name


def clean_output(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    # prefer the "Translation:" line; fall back to the first non-notes line
    m = re.findall(r"(?im)^\s*translation\s*:\s*(.+)$", text)
    if m:
        line = m[-1]
    else:
        lines = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not re.match(r"(?i)^\s*notes?\s*:", ln)]
        line = lines[0] if lines else ""
        line = re.sub(r"^(english)\s*:\s*", "", line, flags=re.I)
    return line.strip().strip('"“”「」').strip()


class Translator:
    """Talks to a llama-server process that Mimamori starts and stops itself."""

    def __init__(self) -> None:
        self.server = LlamaServer()
        self.kind = "chat"
        self._lock = threading.Lock()
        self.runtime_url = ""          # optional manual llama.cpp download link

    def load(self, model_path: str, gpu_layers: int = 0, threads: int = 0,
             status: Optional[Callable[[str], None]] = None) -> None:
        status = status or (lambda _m: None)
        with self._lock:
            if self.loaded and self.server.model == model_path and self.server.gpu_layers == gpu_layers:
                return
            if not model_path or not Path(model_path).exists():
                raise FileNotFoundError("Translation model isn't downloaded yet.")
            flavour = "vulkan" if gpu_layers != 0 else "cpu"
            exe = find_exe(flavour) or install(flavour, status, manual_url=self.runtime_url)
            self.server.start(exe, model_path, gpu_layers, threads, status=status)
            self.kind = "plamo" if is_plamo(model_path) else "chat"

    def unload(self) -> None:
        with self._lock:
            self.server.stop()

    @property
    def loaded(self) -> bool:
        return self.server.running()

    def _plamo(self, text: str, context: str = "", max_tokens: int = 512) -> str:
        with self._lock:
            out = self.server.complete(pfml3_prompt(text, context), max_tokens, PLAMO_STOP)
        return _clean_plamo(out)

    def _chat(self, messages: list[dict], max_tokens: int, temperature: float = 0.0) -> str:
        with self._lock:
            return self.server.chat(messages, max_tokens, temperature)

    def define(self, word: str, reading: str, sentence: str, senses: list[str]) -> str:
        """Short English meaning of `word` as it's used in `sentence`."""
        if not self.loaded:
            raise RuntimeError("Translation model isn't loaded.")
        if self.kind == "plamo":
            # translate just the word, with the sentence as context -> the sense that fits
            return clean_meaning_output(self._plamo(word, context=sentence, max_tokens=40))
        head = f"Word: {word} ({reading})" if reading and reading != word else f"Word: {word}"
        user = f"{head}\nSentence: {sentence}"
        if senses:
            user += "\nDictionary senses:\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(senses, 1))
        messages = [{"role": "system", "content": MEANING_PROMPT}]
        for q, a in MEANING_FEW_SHOT:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": user})
        return clean_meaning_output(self._chat(messages, max_tokens=40, temperature=0.1))

    def translate(self, sentence: str, word: str = "", meaning: str = "", words: str = "") -> str:
        if not self.loaded:
            raise RuntimeError("Translation model isn't loaded.")
        if self.kind == "plamo":
            return self._plamo(sentence)
        user = f"Target word: {word} ({meaning})\n" if word else ""
        user += f"Sentence: {sentence}"
        if words:
            user += f"\nWords: {words}"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for q, a in FEW_SHOT:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": user})
        return clean_output(self._chat(messages, max_tokens=300))
