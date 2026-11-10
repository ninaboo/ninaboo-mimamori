"""Pastel pink theme for Mimamori """
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from . import paths

# palette -------------------------------------------------------------------
PINK = "#ff8fb8"
PINK_HOVER = "#ff74a6"
PINK_PRESSED = "#f2588f"
PINK_SOFT = "#ffe3ee"
PINK_BORDER = "#ffd1e1"
PINK_DEEP = "#d44d86"
BG = "#fff0f6"
CARD = "#ffffff"
TEXT = "#6b3a52"
TEXT_SOFT = "#b5668a"
MINT = "#7fd8b5"
MINT_HOVER = "#66cba3"


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", paths.ROOT))
    return base / "assets" / name


def icon() -> QIcon:
    p = asset("mimamori.ico")
    if not p.exists():
        p = asset("mimamori.png")
    return QIcon(str(p))


def _url(name: str) -> str:
    return asset(name).as_posix()


def stylesheet() -> str:
    check, down, up = _url("check.svg"), _url("arrow_down.svg"), _url("arrow_up.svg")
    return f"""
* {{
    font-family: "M PLUS Rounded 1c", "Yu Gothic UI", "Meiryo UI", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QWidget#central {{ background: {BG}; }}

/* header ---------------------------------------------------------------- */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffd6e7, stop:1 #ffc2da);
    border-radius: 18px;
}}
QLabel#title {{ font-size: 20pt; font-weight: 800; color: {PINK_DEEP}; background: transparent; }}
QLabel#subtitle {{ font-size: 9.5pt; color: {TEXT_SOFT}; background: transparent; }}
QLabel#chip {{
    background: {CARD}; border-radius: 13px; padding: 5px 14px;
    color: {PINK_DEEP}; font-weight: 700;
}}
QLabel#chip[watching="true"] {{ background: {MINT}; color: white; }}
QLabel#logo {{ background: transparent; }}

/* tabs ------------------------------------------------------------------ */
QTabWidget::pane {{
    border: 2px solid {PINK_BORDER}; border-radius: 18px; background: #fffafc; top: -2px;
}}
QTabBar::tab {{
    background: {PINK_SOFT}; color: {PINK_DEEP}; font-weight: 700;
    padding: 8px 22px; margin: 0 4px 6px 4px; border-radius: 14px;
}}
QTabBar::tab:selected {{ background: {PINK}; color: white; }}
QTabBar::tab:hover:!selected {{ background: #ffd1e1; }}

/* group boxes = soft cards ------------------------------------------------ */
QGroupBox {{
    background: {CARD}; border: 2px solid {PINK_BORDER}; border-radius: 16px;
    margin-top: 16px; padding: 16px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 16px;
    padding: 3px 12px; background: {PINK_SOFT}; color: {PINK_DEEP};
    border-radius: 10px; font-weight: 800;
}}

/* buttons --------------------------------------------------------------- */
QPushButton {{
    background: {PINK}; color: white; border: none; border-radius: 13px;
    padding: 7px 16px; font-weight: 700;
}}
QPushButton:hover {{ background: {PINK_HOVER}; }}
QPushButton:pressed {{ background: {PINK_PRESSED}; }}
QPushButton:disabled {{ background: #f6cddd; color: #fff6fa; }}

QPushButton#watchBtn {{
    font-size: 13pt; padding: 12px; border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff8fb8, stop:1 #ffab91);
}}
QPushButton#watchBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff74a6, stop:1 #ff9a7b);
}}
QPushButton#watchBtn[watching="true"] {{ background: {MINT}; }}
QPushButton#watchBtn[watching="true"]:hover {{ background: {MINT_HOVER}; }}

QPushButton#softBtn {{ background: {PINK_SOFT}; color: {PINK_DEEP}; }}
QPushButton#softBtn:hover {{ background: #ffd1e1; }}

/* inputs ---------------------------------------------------------------- */
QLineEdit, QComboBox, QAbstractSpinBox {{
    background: {CARD}; border: 2px solid {PINK_BORDER}; border-radius: 11px;
    padding: 4px 10px; min-height: 22px;
    selection-background-color: {PINK}; selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{ border-color: {PINK_HOVER}; }}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
    background: #fdf3f7; color: #c9a3b5;
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 2px solid {PINK_BORDER}; border-radius: 10px;
    selection-background-color: {PINK_SOFT}; selection-color: {PINK_DEEP}; outline: none;
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    border: none; background: transparent; width: 18px;
}}
QAbstractSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}

/* voice list ------------------------------------------------------------ */
QListWidget {{
    background: {CARD}; border: 2px solid {PINK_BORDER}; border-radius: 14px;
    padding: 6px; outline: none;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 8px; }}
QListWidget::item:hover {{ background: #fff3f8; }}
QListWidget::item:selected {{ background: {PINK_SOFT}; color: {PINK_DEEP}; }}
QListWidget::indicator {{
    width: 16px; height: 16px; border-radius: 6px;
    border: 2px solid {PINK_BORDER}; background: white;
}}
QListWidget::indicator:checked {{
    background: {PINK}; border-color: {PINK}; image: url("{check}");
}}

/* check boxes ----------------------------------------------------------- */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 6px;
    border: 2px solid {PINK_BORDER}; background: white;
}}
QCheckBox::indicator:checked {{ background: {PINK}; border-color: {PINK}; image: url("{check}"); }}
QCheckBox::indicator:disabled {{ background: #fdf3f7; }}

/* radio buttons --------------------------------------------------------- */
QRadioButton::indicator {{
    width: 14px; height: 14px; border-radius: 9px;
    border: 2px solid {PINK_BORDER}; background: white;
}}
QRadioButton::indicator:checked {{ background: {PINK}; border-color: {PINK}; }}

/* progress -------------------------------------------------------------- */
QProgressBar {{
    background: {PINK_SOFT}; border: none; border-radius: 9px; min-height: 18px;
    text-align: center; color: {PINK_DEEP}; font-weight: 700;
}}
QProgressBar::chunk {{
    border-radius: 9px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffb3cd, stop:1 #ff8fb8);
}}

/* log ------------------------------------------------------------------- */
QPlainTextEdit {{
    background: #fffafc; border: 2px solid {PINK_BORDER}; border-radius: 14px;
    padding: 8px; color: #8a4a64;
    selection-background-color: {PINK}; selection-color: white;
}}
QPlainTextEdit#log {{ font-family: "Cascadia Mono", "Consolas", "MS Gothic", monospace; font-size: 9pt; }}
QLabel#logTitle {{ color: {PINK_DEEP}; font-weight: 800; padding-left: 6px; }}

/* misc ------------------------------------------------------------------ */
QSplitter::handle {{ background: transparent; height: 10px; }}
QMenuBar {{ background: {BG}; }}
QMenuBar::item {{ padding: 4px 10px; border-radius: 8px; background: transparent; }}
QMenuBar::item:selected {{ background: {PINK_SOFT}; color: {PINK_DEEP}; }}
QMenu {{ background: {CARD}; border: 2px solid {PINK_BORDER}; border-radius: 10px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {PINK_SOFT}; color: {PINK_DEEP}; }}
QToolTip {{
    background: {CARD}; color: {TEXT}; border: 2px solid {PINK_BORDER};
    border-radius: 8px; padding: 4px 8px;
}}
QMessageBox {{ background: {BG}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #ffb3cd; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {PINK}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: #ffb3cd; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    for role, col in (
        (QPalette.Window, BG), (QPalette.WindowText, TEXT), (QPalette.Base, CARD),
        (QPalette.AlternateBase, "#fff6fa"), (QPalette.Text, TEXT), (QPalette.Button, PINK),
        (QPalette.ButtonText, "#ffffff"), (QPalette.ToolTipBase, CARD), (QPalette.ToolTipText, TEXT),
        (QPalette.Highlight, PINK), (QPalette.HighlightedText, "#ffffff"),
        (QPalette.PlaceholderText, "#d7a9bd"),
    ):
        p.setColor(role, QColor(col))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#c9a3b5"))
    app.setPalette(p)
    app.setStyleSheet(stylesheet())
    app.setWindowIcon(icon())


def repolish(widget) -> None:
    """Re-apply the stylesheet after changing a dynamic property."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
