"""Small window for adding, updating and removing AivisSpeech voice models."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from . import tts


class VoiceManager(QDialog):
    COLS = ("Voice", "Styles", "Version", "Size", "Status")

    def __init__(self, parent, engine: tts.Engine, run_bg: Callable, log: Callable[[str], None],
                 on_changed: Callable[[], None]) -> None:
        super().__init__(parent)
        self.engine, self.run_bg, self.log, self.on_changed = engine, run_bg, log, on_changed
        self.models: list[tts.VoiceModel] = []
        self.setWindowTitle("Manage voices")
        self.resize(720, 460)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Voice models installed in AivisSpeech. Each model can have several "
                             "styles; tick the ones you want in the Voices list afterwards."))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(self.COLS)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False)
        self.tree.setUniformRowHeights(True)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(self.COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        lay.addWidget(self.tree, 1)

        self.busy = QProgressBar(visible=False)
        self.busy.setRange(0, 0)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.busy)
        lay.addWidget(self.status)

        row = QHBoxLayout()
        self.add_hub = QPushButton("Add from AivisHub…")
        self.add_hub.setToolTip("Paste an AivisHub link (or a model ID, or a link to an .aivmx file)")
        self.add_hub.clicked.connect(self.add_from_hub)
        self.add_file = QPushButton("Add from file…")
        self.add_file.clicked.connect(self.add_from_file)
        self.update_btn = QPushButton("Update", objectName="softBtn")
        self.update_btn.clicked.connect(self.update_selected)
        self.remove_btn = QPushButton("Remove", objectName="softBtn")
        self.remove_btn.clicked.connect(self.remove_selected)
        browse = QPushButton("Browse AivisHub", objectName="softBtn")
        browse.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(tts.HUB_PAGE)))
        close = QPushButton("Close", objectName="softBtn")
        close.clicked.connect(self.accept)
        for b in (self.add_hub, self.add_file, self.update_btn, self.remove_btn):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(browse)
        row.addWidget(close)
        lay.addLayout(row)

        self.refresh()

    # ------------------------------------------------------------------ helpers
    def _selected(self) -> tts.VoiceModel | None:
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.UserRole) if items else None

    def _update_buttons(self) -> None:
        m = self._selected()
        working = self.busy.isVisible()
        for b in (self.add_hub, self.add_file):
            b.setEnabled(not working)
        self.update_btn.setEnabled(bool(m and m.update_available and not working))
        self.remove_btn.setEnabled(bool(m and not working))

    def _work(self, label: str, fn: Callable, done_msg: str) -> None:
        self.busy.setVisible(True)
        self.status.setText(label)
        self._update_buttons()

        def done(_):
            self.busy.setVisible(False)
            self.status.setText(done_msg)
            self.log(done_msg)
            self.refresh()
            self.on_changed()

        def fail(e):
            self.busy.setVisible(False)
            self.status.setText(f"✗ {e}")
            self._update_buttons()

        self.run_bg(fn, done, fail)

    # ------------------------------------------------------------------ actions
    def refresh(self) -> None:
        def done(models):
            self.models = models
            self.tree.clear()
            for m in models:
                status = []
                if m.default:
                    status.append("built-in")
                if m.update_available:
                    status.append(f"update → {m.latest_version}")
                if m.loaded:
                    status.append("loaded")
                it = QTreeWidgetItem([m.name, str(m.styles), m.version, f"{m.size_mb:.0f} MB",
                                      ", ".join(status)])
                it.setData(0, Qt.UserRole, m)
                tip = f"{m.name}\nID: {m.uuid}"
                if m.creators:
                    tip += f"\nBy: {m.creators}"
                it.setToolTip(0, tip)
                self.tree.addTopLevelItem(it)
            if not self.busy.isVisible():
                self.status.setText(f"{len(models)} voice model{'s' if len(models) != 1 else ''} installed.")
            self._update_buttons()

        self.run_bg(self.engine.models, done,
                    lambda e: self.status.setText(f"✗ Couldn't list voices: {e}"))

    def add_from_hub(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Add from AivisHub",
            "Paste the AivisHub link of a voice\n(e.g. https://hub.aivis-project.com/aivm-models/…)")
        if not ok or not text.strip():
            return
        try:
            url = tts.model_source_url(text)
        except ValueError as e:
            self.status.setText(f"✗ {e}")
            return
        self._work("Downloading and installing the voice… (models are often 200–300 MB)",
                   lambda: self.engine.install_from_url(url), "Voice installed ♡")

    def add_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a voice model", "",
                                              "AivisSpeech voice models (*.aivmx)")
        if not path:
            return
        self._work("Installing the voice…", lambda: self.engine.install_from_file(path),
                   "Voice installed ♡")

    def update_selected(self) -> None:
        m = self._selected()
        if not m:
            return
        self._work(f"Updating {m.name}…", lambda: self.engine.update_model(m.uuid),
                   f"Updated {m.name} to {m.latest_version}.")

    def remove_selected(self) -> None:
        m = self._selected()
        if not m:
            return
        extra = ("\n\nThis is a built-in voice; AivisSpeech may not allow removing it."
                 if m.default else "")
        if QMessageBox.question(self, "Remove voice",
                                f"Remove {m.name} from AivisSpeech?{extra}") != QMessageBox.Yes:
            return
        self._work(f"Removing {m.name}…", lambda: self.engine.uninstall_model(m.uuid),
                   f"Removed {m.name}.")
