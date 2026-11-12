"""PySide6 window: setup (Anki / voice / translation) + watcher. Pink and cute """
from __future__ import annotations

import collections
import os
import sys
import threading
import time
import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit,
    QMenu, QProgressBar, QPushButton, QRadioButton, QScrollArea, QSpinBox, QSplitter,
    QSystemTrayIcon, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import APP_NAME, __version__, autostart, llm, notetype, paths, theme, tts
from .anki import AnkiConnect, AnkiError
from .config import Config
from .download import Cancelled, download
from .pipeline import Context, Watcher, migrate_tags


class Bridge(QObject):
    log = Signal(str)
    call = Signal(object)                  # run a callable on the GUI thread
    progress = Signal(str, object, object)  # key, done, total (object: may exceed int32)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} 見守り  ·  v{__version__}")
        self.setWindowIcon(theme.icon())
        self.resize(940, 820)

        self.cfg = Config()
        self._counts = (0, 0)
        theme.apply(QApplication.instance(), self.cfg["theme"])
        self.bridge = Bridge()
        self.bridge.log.connect(self._append_log)
        self.bridge.call.connect(lambda fn: fn())
        self.bridge.progress.connect(self._on_progress)

        self.anki = AnkiConnect(self.cfg["anki_url"])
        self.engine = tts.Engine(lambda: self.cfg.engine_url)
        self.translator = llm.Translator()
        self.translator.runtime_url = self.cfg["llm_runtime_url"]
        self.clip_history: collections.deque[tuple[float, str]] = collections.deque(maxlen=50)
        self.cancel_engine_dl = threading.Event()
        self.cancel_llm_dl = threading.Event()
        self.bars: dict[str, QProgressBar] = {}

        ctx = Context(self.cfg, self.anki, self.engine, self.translator,
                      lambda: list(self.clip_history), self.log)
        self.watcher = Watcher(ctx, on_count=lambda ok, bad: self.bridge.call.emit(
            lambda: self._set_counts(ok, bad)))

        self._quitting = False
        self._build_ui()
        self._build_tray()
        # Read the clipboard a moment AFTER a copy, never during it: grabbing it while
        # another app is still writing (multi-line / rich text copies) can make that copy fail.
        self._clip_timer = QTimer(self, singleShot=True, interval=400)
        self._clip_timer.timeout.connect(self._read_clipboard)
        QApplication.clipboard().dataChanged.connect(self._clip_timer.start)
        self._clip_timer.start()   # whatever was copied before Mimamori opened counts too

        self.log(f"App folder: {paths.ROOT}")
        self.check_anki()
        self._refresh_engine_ui()
        self._refresh_llm_ui()
        if self.cfg["engine_mode"] == "external" or self.cfg["engine_exe"]:
            self.start_engine()
        if self.cfg["auto_watch"] and self.cfg["deck"]:
            QTimer.singleShot(1500, lambda: self.watcher.running or self.toggle_watch())

    # ================================================================== helpers
    def log(self, msg: str) -> None:
        self.bridge.log.emit(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        try:
            with open(paths.LOGS / "app.log", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def run_bg(self, fn: Callable[[], Any], on_done: Optional[Callable[[Any], None]] = None,
               on_error: Optional[Callable[[Exception], None]] = None) -> None:
        def worker():
            try:
                result = fn()
            except Exception as e:  # noqa: BLE001
                if not isinstance(e, Cancelled):
                    self.log(f"※ {e}")
                    if not isinstance(e, (AnkiError, tts.EngineError, FileNotFoundError)):
                        self.log(traceback.format_exc())
                if on_error:
                    self.bridge.call.emit(lambda: on_error(e))
                return
            if on_done:
                self.bridge.call.emit(lambda: on_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, key: str, done: int, total: int) -> None:
        bar = self.bars[key]
        bar.setVisible(True)
        if not total:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 1000)
            bar.setValue(int(done * 1000 / total))
            bar.setFormat(f"{done / 1e6:,.0f} / {total / 1e6:,.0f} MB")

    def _progress_fn(self, key: str):
        last = [0.0]

        def fn(done, total):
            now = time.time()
            if now - last[0] > 0.1 or (total and done >= total):
                last[0] = now
                self.bridge.progress.emit(key, done, total)
        return fn

    def _read_clipboard(self) -> None:
        try:
            text = QApplication.clipboard().text()
        except Exception:  # noqa: BLE001  clipboard busy: skip this one
            return
        if text and text.strip():
            if self.clip_history and self.clip_history[-1][1] == text:
                self.clip_history[-1] = (time.time(), text)
            else:
                self.clip_history.append((time.time(), text))

    # ================================================================== UI
    def _build_ui(self) -> None:
        central = QWidget(objectName="central")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(14, 10, 14, 14)
        outer.setSpacing(10)
        outer.addWidget(self._header())

        tabs = QTabWidget()
        tabs.addTab(self._watch_tab(), "Watch")
        tabs.addTab(self._scroll(self._setup_tab()), "Setup")
        if not (self.cfg["engine_exe"] or self.cfg["engine_mode"] == "external") or not self.cfg["llm_path"]:
            tabs.setCurrentIndex(1)

        log_box = QWidget()
        lb = QVBoxLayout(log_box)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(4)
        lb.addWidget(QLabel("Diary", objectName="logTitle"))
        self.log_view = QPlainTextEdit(readOnly=True, objectName="log")
        self.log_view.setMaximumBlockCount(3000)
        lb.addWidget(self.log_view)

        split = QSplitter(Qt.Vertical)
        split.addWidget(tabs)
        split.addWidget(log_box)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, 1)
        self.setCentralWidget(central)

        m = self.menuBar().addMenu("&Folder")
        act = QAction("Open app folder", self)
        act.triggered.connect(lambda: os.startfile(paths.ROOT) if sys.platform == "win32" else None)
        m.addAction(act)

    def _header(self) -> QWidget:
        h = QFrame(objectName="header")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(16, 10, 18, 10)
        logo = QLabel(objectName="logo")
        logo.setPixmap(QPixmap(str(theme.asset("mimamori.png"))).scaled(
            58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(QLabel("Mimamori  見守り", objectName="title"))
        text.addWidget(QLabel("watching over your deck so your cards are ready ♡", objectName="subtitle"))
        self.chip = QLabel("resting…", objectName="chip")
        lay.addWidget(logo)
        lay.addSpacing(8)
        lay.addLayout(text, 1)
        lay.addWidget(self.chip, 0, Qt.AlignVCenter)
        return h

    @staticmethod
    def _scroll(widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidget(widget)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        return area

    def _set_counts(self, ok: int, bad: int) -> None:
        self._counts = (ok, bad)
        c = theme.current()
        self.filled_lbl.setText(f"<span style='font-size:20pt; font-weight:800; color:{c['accent']}'>{ok}</span>"
                                f"<br>cards filled ♡")
        self.err_lbl.setText(f"<span style='font-size:20pt; font-weight:800; color:{c['text_soft']}'>{bad}</span>"
                             f"<br>need a retry")

    def _apply_theme(self, name: str) -> None:
        self.cfg.set("theme", name)
        theme.apply(QApplication.instance(), name)
        self._set_counts(*self._counts)
        self.status_lbl.setStyleSheet(f"color: {theme.current()['text_soft']};")

    def _set_watching_look(self, watching: bool) -> None:
        self.watch_btn.setText("■  Stop watching" if watching else "♡  Start watching")
        self.watch_btn.setProperty("watching", watching)
        self.chip.setProperty("watching", watching)
        self.chip.setText(f"♡ watching {self.cfg['deck']}" if watching else "resting…")
        theme.repolish(self.watch_btn)
        theme.repolish(self.chip)
        if getattr(self, "tray", None):
            self.tray_watch_act.setText("Stop watching" if watching else "Start watching")
            self.tray.setToolTip(f"Mimamori – watching {self.cfg['deck']}" if watching
                                 else "Mimamori – resting")

    # ---------------------------------------------------------------- watch tab
    def _watch_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        deck_row = QHBoxLayout()
        self.deck_combo = QComboBox()
        self.deck_combo.setMinimumWidth(320)
        self.deck_combo.currentTextChanged.connect(
            lambda t: t and self.cfg.set("deck", t))
        btn = QPushButton("↻  Refresh", objectName="softBtn")
        btn.clicked.connect(self.load_decks)
        deck_row.addWidget(self.deck_combo, 1)
        deck_row.addWidget(btn)
        form.addRow("Deck to watch:", deck_row)

        self.source_combo = QComboBox()
        for key, label in (("auto", "Auto – clipboard if it contains the word, else Yomitan"),
                           ("yomitan", "Yomitan only"),
                           ("clipboard", "Clipboard (falls back to Yomitan)")):
            self.source_combo.addItem(label, key)
        self.source_combo.setCurrentIndex(self.source_combo.findData(self.cfg["sentence_source"]))
        self.source_combo.currentIndexChanged.connect(
            lambda: self.cfg.set("sentence_source", self.source_combo.currentData()))
        form.addRow("Sentence source:", self.source_combo)

        poll = QDoubleSpinBox(minimum=0.5, maximum=60, singleStep=0.5, suffix=" s")
        poll.setValue(float(self.cfg["poll_seconds"]))
        poll.valueChanged.connect(lambda v: self.cfg.set("poll_seconds", v))
        form.addRow("Check every:", poll)
        box = QGroupBox("What to watch")
        box.setLayout(form)
        lay.addWidget(box)

        row = QHBoxLayout()
        self.watch_btn = QPushButton(objectName="watchBtn")
        self.watch_btn.setMinimumHeight(52)
        self.watch_btn.clicked.connect(self.toggle_watch)
        retry = QPushButton("↻  Retry errors", objectName="softBtn")
        retry.setMinimumHeight(52)
        retry.clicked.connect(self.retry_errors)
        row.addWidget(self.watch_btn, 1)
        row.addWidget(retry)
        lay.addSpacing(6)
        lay.addLayout(row)

        stats = QHBoxLayout()
        self.filled_lbl = QLabel(alignment=Qt.AlignCenter)
        self.err_lbl = QLabel(alignment=Qt.AlignCenter)
        for lbl in (self.filled_lbl, self.err_lbl):
            card = QGroupBox()
            cl = QVBoxLayout(card)
            cl.addWidget(lbl)
            stats.addWidget(card)
        lay.addLayout(stats)
        self._set_counts(0, 0)

        self.status_lbl = QLabel()
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {theme.current()['text_soft']};")
        lay.addWidget(self.status_lbl)
        lay.addStretch(1)
        self._set_watching_look(False)
        return w

    # ---------------------------------------------------------------- setup tab
    def _setup_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # 1. Anki ----------------------------------------------------------
        g = QGroupBox("1 · Anki")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.anki_lbl = QLabel("Checking…")
        b1 = QPushButton("Check connection", objectName="softBtn")
        b1.clicked.connect(self.check_anki)
        b2 = QPushButton("Create / update note type")
        b2.clicked.connect(self.make_note_type)
        row.addWidget(self.anki_lbl, 1)
        row.addWidget(b1)
        row.addWidget(b2)
        gl.addLayout(row)
        mapping = "\n".join(f"{k:<17} {v}" for k, v in notetype.YOMITAN_MAPPING.items() if v)
        hint = QLabel(f"In Yomitan → Anki → Card format, pick note type "
                      f"<b>{self.cfg['note_type']}</b> and set:")
        gl.addWidget(hint)
        mp = QPlainTextEdit(mapping, readOnly=True, objectName="log")
        mp.setFixedHeight(110)
        gl.addWidget(mp)
        lay.addWidget(g)

        # 2. Voice ----------------------------------------------------------
        g = QGroupBox("2 · Voices – AivisSpeech")
        form = QFormLayout(g)

        mode_row = QHBoxLayout()
        self.mode_managed = QRadioButton("Download and run it for me")
        self.mode_external = QRadioButton("Use an engine that's already running:")
        grp = QButtonGroup(g)
        grp.addButton(self.mode_managed)
        grp.addButton(self.mode_external)
        (self.mode_external if self.cfg["engine_mode"] == "external" else self.mode_managed).setChecked(True)
        self.ext_url = QLineEdit(self.cfg["engine_external_url"])
        self.ext_url.editingFinished.connect(
            lambda: self.cfg.set("engine_external_url", self.ext_url.text().strip()))
        self.mode_managed.toggled.connect(self._on_mode_change)
        mode_row.addWidget(self.mode_managed)
        mode_row.addWidget(self.mode_external)
        mode_row.addWidget(self.ext_url, 1)
        form.addRow(mode_row)

        dl_row = QHBoxLayout()
        self.cpu_gpu = QComboBox()
        self.cpu_gpu.addItem("CPU", False)
        self.cpu_gpu.addItem("GPU (DirectML)", True)
        self.cpu_gpu.setCurrentIndex(1 if self.cfg["engine_gpu"] else 0)
        self.cpu_gpu.currentIndexChanged.connect(
            lambda: self.cfg.set("engine_gpu", self.cpu_gpu.currentData()))
        self.engine_dl_btn = QPushButton("Download engine")
        self.engine_dl_btn.clicked.connect(self.download_engine)
        self.engine_run_btn = QPushButton("Start engine")
        self.engine_run_btn.clicked.connect(self.toggle_engine)
        dl_row.addWidget(self.cpu_gpu)
        dl_row.addWidget(self.engine_dl_btn)
        dl_row.addWidget(self.engine_run_btn)
        dl_row.addStretch(1)
        form.addRow("Engine:", dl_row)

        self.bars["engine"] = QProgressBar(visible=False)
        form.addRow(self.bars["engine"])
        self.engine_lbl = QLabel()
        self.engine_lbl.setWordWrap(True)
        form.addRow("Status:", self.engine_lbl)

        voice_box = QHBoxLayout()
        self.voice_list = QListWidget()
        self.voice_list.setMinimumHeight(170)
        self.voice_list.itemChanged.connect(self._on_voice_checks)
        self.voice_list.itemDoubleClicked.connect(lambda _: self.preview_voice())
        side = QVBoxLayout()
        vr = QPushButton("↻  Refresh voices", objectName="softBtn")
        vr.clicked.connect(self.load_voices)
        vp = QPushButton("Preview")
        vp.setToolTip("Plays the highlighted voice (or double-click a voice)")
        vp.clicked.connect(self.preview_voice)
        vn = QPushButton("Untick all", objectName="softBtn")
        vn.clicked.connect(lambda: self._set_all_checks(False))
        self.speed = QDoubleSpinBox(minimum=0.5, maximum=2.0, singleStep=0.05, prefix="Speed ×")
        self.speed.setValue(float(self.cfg["speed"]))
        self.speed.valueChanged.connect(lambda v: self.cfg.set("speed", round(v, 2)))
        self.volume = QDoubleSpinBox(minimum=0.1, maximum=2.0, singleStep=0.05, prefix="Volume ×")
        self.volume.setToolTip("1.0 = normal AivisSpeech loudness. Lower is quieter.")
        self.volume.setValue(float(self.cfg["volume"]))
        self.volume.valueChanged.connect(lambda v: self.cfg.set("volume", round(v, 2)))
        self.voice_count_lbl = QLabel()
        self.voice_count_lbl.setWordWrap(True)
        for wdg in (vr, vp, vn, self.speed, self.volume, self.voice_count_lbl):
            side.addWidget(wdg)
        side.addStretch(1)
        voice_box.addWidget(self.voice_list, 1)
        voice_box.addLayout(side)
        form.addRow("Voices:", voice_box)
        form.addRow(QLabel("Tick every voice you want. Each card gets one of them at random, "
                           "and that voice reads both the word and the sentence."))
        self._fill_voice_list([tuple(v) for v in self.cfg["voice_cache"]])
        lay.addWidget(g)

        # 3. Translation ---------------------------------------------------
        g = QGroupBox("3 · Translation – local LLM")
        form = QFormLayout(g)
        self.llm_combo = QComboBox()
        for key, info in llm.MODEL_CATALOG.items():
            self.llm_combo.addItem(info["label"], key)
        self.llm_combo.addItem("Custom GGUF URL…", "custom")
        self.llm_combo.setCurrentIndex(max(0, self.llm_combo.findData(self.cfg["llm_choice"])))
        self.llm_combo.currentIndexChanged.connect(self._on_llm_choice)
        form.addRow("Model:", self.llm_combo)
        self.llm_url = QLineEdit(self.cfg["llm_custom_url"])
        self.llm_url.setPlaceholderText("https://huggingface.co/…/resolve/main/model.gguf")
        self.llm_url.editingFinished.connect(
            lambda: self.cfg.set("llm_custom_url", self.llm_url.text().strip()))
        form.addRow("Custom URL:", self.llm_url)

        row = QHBoxLayout()
        self.llm_dl_btn = QPushButton("Download model")
        self.llm_dl_btn.clicked.connect(self.download_llm)
        test = QPushButton("Test translation", objectName="softBtn")
        test.clicked.connect(self.test_translation)
        self.gpu_layers = QSpinBox(minimum=-1, maximum=200, prefix="GPU layers: ")
        self.gpu_layers.setToolTip("0 = CPU only. -1 = everything on the GPU (downloads llama.cpp's GPU build automatically).")
        self.gpu_layers.setValue(int(self.cfg["llm_gpu_layers"]))
        self.gpu_layers.valueChanged.connect(self._on_gpu_layers)
        row.addWidget(self.llm_dl_btn)
        row.addWidget(test)
        row.addWidget(self.gpu_layers)
        row.addStretch(1)
        form.addRow(row)
        self.bars["llm"] = QProgressBar(visible=False)
        form.addRow(self.bars["llm"])
        self.llm_lbl = QLabel()
        self.llm_lbl.setWordWrap(True)
        form.addRow("Status:", self.llm_lbl)
        lay.addWidget(g)

        # 4. Startup ---------------------------------------------------------
        g = QGroupBox("4 · Startup")
        sl = QVBoxLayout(g)
        self.boot_chk = QCheckBox("Start Mimamori when Windows starts (opens quietly in the tray)")
        if autostart.supported():
            self.boot_chk.setChecked(autostart.points_here())
        else:
            self.boot_chk.setEnabled(False)
            self.boot_chk.setToolTip("Only available in the built Mimamori.exe")
        self.boot_chk.toggled.connect(self._on_boot_toggled)
        auto = QCheckBox("Start watching automatically when Mimamori opens")
        auto.setChecked(bool(self.cfg["auto_watch"]))
        auto.toggled.connect(lambda v: self.cfg.set("auto_watch", v))
        tray = QCheckBox("Closing the window keeps Mimamori running in the tray")
        tray.setChecked(bool(self.cfg["close_to_tray"]))
        tray.toggled.connect(lambda v: self.cfg.set("close_to_tray", v))
        for c in (self.boot_chk, auto, tray):
            sl.addWidget(c)
        lay.addWidget(g)

        # 5. Look --------------------------------------------------------------
        g = QGroupBox("5 · Look")
        form = QFormLayout(g)
        look = QComboBox()
        look.addItem("Dark (pink)", "dark")
        look.addItem("Light (pink)", "light")
        look.setCurrentIndex(max(0, look.findData(self.cfg["theme"])))
        look.currentIndexChanged.connect(lambda: self._apply_theme(look.currentData()))
        form.addRow("Theme:", look)
        lay.addWidget(g)

        lay.addStretch(1)
        return w

    # ================================================================== Anki
    def check_anki(self) -> None:
        self.anki_lbl.setText("Checking…")

        def done(r):
            ver, has_model, moved = r
            if moved:
                self.log(f"Renamed old tags on {moved} note(s) to '{self.cfg['done_tag']}' / "
                         f"'{self.cfg['error_tag']}'.")
            mark = "✓" if has_model else "※ not found – see the button on the right"
            self.anki_lbl.setText(f"✓ AnkiConnect v{ver}   Note type: {mark}")
            self.load_decks()

        def fail(e):
            self.anki_lbl.setText("✗ Can't reach AnkiConnect – is Anki open with the add-on installed?")

        self.run_bg(lambda: (self.anki.version(),
                             self.cfg["note_type"] in self.anki.model_names(),
                             migrate_tags(self.anki, self.cfg)), done, fail)

    def load_decks(self) -> None:
        def done(decks):
            cur = self.cfg["deck"]
            self.deck_combo.blockSignals(True)
            self.deck_combo.clear()
            self.deck_combo.addItems(decks)
            if cur in decks:
                self.deck_combo.setCurrentText(cur)
            self.deck_combo.blockSignals(False)
            if not cur and decks:
                self.cfg.set("deck", self.deck_combo.currentText())
        self.run_bg(self.anki.deck_names, done)

    def make_note_type(self) -> None:
        self.run_bg(lambda: notetype.ensure_note_type(self.anki, self.cfg["note_type"]),
                    lambda msg: (self.log(msg), self.check_anki()))

    # ================================================================== engine
    def _on_mode_change(self) -> None:
        self.cfg.set("engine_mode", "managed" if self.mode_managed.isChecked() else "external")
        self._refresh_engine_ui()

    def _refresh_engine_ui(self) -> None:
        managed = self.cfg["engine_mode"] == "managed"
        installed = bool(self.cfg["engine_exe"]) and os.path.exists(self.cfg["engine_exe"])
        self.cpu_gpu.setEnabled(managed)
        self.engine_dl_btn.setEnabled(managed)
        self.engine_dl_btn.setText("Re-download engine" if installed else "Download engine")
        self.engine_run_btn.setEnabled(not managed or installed)
        self.engine_run_btn.setText("Stop engine" if self.engine.owns_process() else "Start engine")
        self.ext_url.setEnabled(not managed)
        if managed and not installed:
            self.engine_lbl.setText("Not installed.")

    def download_engine(self) -> None:
        if self.engine_dl_btn.text() == "Cancel":
            self.cancel_engine_dl.set()
            return
        self.engine.stop()
        self.cancel_engine_dl.clear()
        self.engine_dl_btn.setText("Cancel")
        status = lambda s: self.bridge.call.emit(lambda: self.engine_lbl.setText(s))  # noqa: E731

        def job():
            return tts.install_engine(self.cfg["engine_gpu"], status, self._progress_fn("engine"),
                                      self.cancel_engine_dl, self.cfg["engine_asset_url"])

        def done(exe):
            self.bars["engine"].setVisible(False)
            self.cfg.set("engine_exe", str(exe))
            self.log(f"Engine installed: {exe}")
            self._refresh_engine_ui()
            self.start_engine()

        def fail(e):
            self.bars["engine"].setVisible(False)
            self.engine_lbl.setText("Download cancelled." if isinstance(e, Cancelled) else f"✗ {e}")
            self._refresh_engine_ui()

        self.run_bg(job, done, fail)

    def toggle_engine(self) -> None:
        if self.engine.owns_process():
            self.engine.stop()
            self.engine_lbl.setText("Stopped.")
            self._refresh_engine_ui()
        else:
            self.start_engine()

    def start_engine(self) -> None:
        status = lambda s: self.bridge.call.emit(lambda: self.engine_lbl.setText(s))  # noqa: E731
        self.engine_run_btn.setEnabled(False)

        def job():
            if self.cfg["engine_mode"] == "external":
                if not self.engine.is_up():
                    raise tts.EngineError(f"No engine responding at {self.cfg.engine_url}")
                status(f"Connected to {self.cfg.engine_url}")
            else:
                self.engine.start(self.cfg["engine_exe"], self.cfg["engine_port"],
                                  self.cfg["engine_gpu"], status)

        def done(_):
            self._refresh_engine_ui()
            self.load_voices()

        def fail(e):
            self.engine_lbl.setText(f"✗ {e}")
            self._refresh_engine_ui()

        self.run_bg(job, done, fail)

    def load_voices(self) -> None:
        def done(voices):
            self.cfg.set("voice_cache", [[label, sid] for label, sid in voices])
            available = {sid for _, sid in voices}
            kept = [s for s in self.cfg["speaker_ids"] if s in available]
            if not kept and voices:
                kept = [voices[0][1]]
            self.cfg.set("speaker_ids", kept)
            self._fill_voice_list(voices)
            self.log(f"{len(voices)} voice styles available.")
        self.run_bg(self.engine.speakers, done)

    def _fill_voice_list(self, voices: list[tuple[str, int]]) -> None:
        checked = set(int(s) for s in self.cfg["speaker_ids"])
        self.voice_list.blockSignals(True)
        self.voice_list.clear()
        for label, sid in voices:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, int(sid))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if int(sid) in checked else Qt.Unchecked)
            self.voice_list.addItem(item)
        self.voice_list.blockSignals(False)
        self._update_voice_count()

    def _checked_voice_ids(self) -> list[int]:
        out = []
        for i in range(self.voice_list.count()):
            it = self.voice_list.item(i)
            if it.checkState() == Qt.Checked:
                out.append(int(it.data(Qt.UserRole)))
        return out

    def _on_voice_checks(self, *_):
        self.cfg.set("speaker_ids", self._checked_voice_ids())
        self._update_voice_count()

    def _set_all_checks(self, on: bool) -> None:
        self.voice_list.blockSignals(True)
        for i in range(self.voice_list.count()):
            self.voice_list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.voice_list.blockSignals(False)
        self._on_voice_checks()

    def _update_voice_count(self) -> None:
        n = len(self.cfg["speaker_ids"])
        self.voice_count_lbl.setText("No voices ticked – audio will be skipped" if n == 0
                                     else f"{n} voice{'s' if n != 1 else ''} ticked")

    def preview_voice(self) -> None:
        item = self.voice_list.currentItem()
        sid = item.data(Qt.UserRole) if item else (self.cfg["speaker_ids"] or [None])[0]
        if sid is None:
            return
        self.run_bg(lambda: tts.play_wav(
            self.engine.synth("彼は地震で親を失いました。", sid, self.cfg["speed"],
                              self.cfg["volume"])))

    # ================================================================== LLM
    def _on_llm_choice(self) -> None:
        self.cfg.set("llm_choice", self.llm_combo.currentData())
        self._refresh_llm_ui()

    def _on_gpu_layers(self, v: int) -> None:
        self.cfg.set("llm_gpu_layers", v)
        self.translator.unload()   # reload with new setting on next use

    def _refresh_llm_ui(self) -> None:
        self.llm_url.setEnabled(self.cfg["llm_choice"] == "custom")
        url = llm.model_url(self.cfg["llm_choice"], self.cfg["llm_custom_url"])
        target = llm.model_dest(url) if url else None
        if target and target.exists():
            self.llm_lbl.setText(f"✓ {target.name}")
            self.llm_dl_btn.setText("Downloaded")
            self.llm_dl_btn.setEnabled(False)
            if self.cfg["llm_path"] != str(target):
                self.cfg.set("llm_path", str(target))
                self.translator.unload()
        else:
            self.llm_lbl.setText("Not downloaded.")
            self.llm_dl_btn.setText("Download model")
            self.llm_dl_btn.setEnabled(True)

    def download_llm(self) -> None:
        if self.llm_dl_btn.text() == "Cancel":
            self.cancel_llm_dl.set()
            return
        url = llm.model_url(self.cfg["llm_choice"], self.cfg["llm_custom_url"])
        if not url:
            self.log("※ Enter a custom GGUF URL first.")
            return
        dest = llm.model_dest(url)
        self.cancel_llm_dl.clear()
        self.llm_dl_btn.setText("Cancel")
        self.llm_lbl.setText(f"Downloading {dest.name}…")

        def done(_):
            self.bars["llm"].setVisible(False)
            self.log(f"Model downloaded: {dest.name}")
            self._refresh_llm_ui()

        def fail(e):
            self.bars["llm"].setVisible(False)
            self.llm_lbl.setText("Download paused – click Download to resume."
                                 if isinstance(e, Cancelled) else f"✗ {e}")
            self.llm_dl_btn.setText("Download model")

        self.run_bg(lambda: download(url, dest, self._progress_fn("llm"), self.cancel_llm_dl),
                    done, fail)

    def test_translation(self) -> None:
        self.llm_lbl.setText("Loading model and translating…")

        status = lambda m: self.bridge.call.emit(lambda: self.llm_lbl.setText(m))  # noqa: E731

        def job():
            self.translator.load(self.cfg["llm_path"], self.cfg["llm_gpu_layers"],
                                 self.cfg["llm_threads"], status=status)
            status("Translating…")
            t0 = time.time()
            out = self.translator.translate("彼は地震で親を失いました。", "失う", "lose, miss")
            return out, time.time() - t0

        def done(r):
            self.llm_lbl.setText(f"✓ “{r[0]}”  ({r[1]:.1f}s)")

        self.run_bg(job, done, lambda e: self.llm_lbl.setText(f"✗ {e}"))

    # ================================================================== watcher
    def toggle_watch(self) -> None:
        if self.watcher.running:
            self.watcher.stop()
            self._set_watching_look(False)
            self.status_lbl.setText("")
            return
        problems = []
        if not self.cfg["speaker_ids"]:
            problems.append("no voices ticked (audio will be skipped)")
        if not self.cfg["llm_path"]:
            problems.append("no translation model (English will be skipped)")
        if not self.cfg["deck"]:
            QMessageBox.warning(self, APP_NAME, "Pick a deck first.")
            return
        if problems:
            self.status_lbl.setText("Note: " + "; ".join(problems))
        self.anki.url = self.cfg["anki_url"]
        if self.cfg["llm_path"] and not self.translator.loaded:
            self.log("Loading translation model in the background…")
            self.run_bg(lambda: self.translator.load(self.cfg["llm_path"], self.cfg["llm_gpu_layers"],
                                                     self.cfg["llm_threads"], status=self.log),
                        lambda _: self.log("Translation model ready."))
        self.watcher.start()
        self._set_watching_look(True)

    def retry_errors(self) -> None:
        def done(n):
            msg = f"{n} card{'s' if n != 1 else ''} queued for retry." if n else "No cards need a retry."
            self.log(msg)
            if self.tray and not self.isVisible():
                self.tray.showMessage("Mimamori", msg, theme.icon(), 3000)
        self.run_bg(self.watcher.retry_errors, done)

    # ================================================================== shutdown
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.tray and self.cfg["close_to_tray"] and not self._quitting:
            event.ignore()
            self.hide_to_tray()
            return
        self.watcher.stop()
        self.cancel_engine_dl.set()
        self.cancel_llm_dl.set()
        self.engine.stop()
        self.translator.unload()
        if self.tray:
            self.tray.hide()
        self.cfg.save()
        event.accept()
        QApplication.quit()

    def changeEvent(self, event) -> None:  # noqa: N802
        # minimise button -> tray
        if (event.type() == QEvent.WindowStateChange and self.isMinimized() and self.tray):
            QTimer.singleShot(0, self.hide_to_tray)
        super().changeEvent(event)

    def _on_boot_toggled(self, on: bool) -> None:
        try:
            autostart.set_enabled(on)
            self.cfg.set("start_with_windows", on)
            self.log("Mimamori will start with Windows." if on else "Removed Mimamori from Windows startup.")
        except OSError as e:
            self.log(f"※ Couldn't change Windows startup: {e}")

    # ================================================================== tray
    def _build_tray(self) -> None:
        self.tray: Optional[QSystemTrayIcon] = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(theme.icon(), self)
        menu = QMenu(self)
        def item(text: str, fn) -> QAction:
            act = menu.addAction(text)
            act.triggered.connect(lambda *_: fn())
            return act
        self.tray_watch_act = item("Start watching", self.toggle_watch)
        item("Retry errors", self.retry_errors)
        menu.addSeparator()
        item("Open Mimamori", self.show_from_tray)
        item("Quit Mimamori", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._set_watching_look(self.watcher.running)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    def hide_to_tray(self) -> None:
        self.hide()
        if self.tray and not self.cfg["tray_hint_shown"]:
            self.tray.showMessage("Mimamori is still here ♡",
                                  "It keeps running in the tray. Right-click the icon for options.",
                                  theme.icon(), 4000)
            self.cfg.set("tray_hint_shown", True)

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self._quitting = True
        self.close()


def run(start_minimized: bool = False) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)   # keeps running in the tray
    win = MainWindow()
    if not (start_minimized and win.tray):
        win.show()
    return app.exec()
