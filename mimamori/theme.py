"""Pink themes for Mimamori: dark (default) and light."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from . import paths

# palettes ------------------------------------------------------------------
_COMMON = {
    "pink": "#ff8fb8", "pink_hover": "#ff74a6", "pink_pressed": "#f2588f",
    "mint": "#7fd8b5", "mint_hover": "#66cba3",
    "watch1": "#ff8fb8", "watch2": "#ffab91", "watch1_hover": "#ff74a6", "watch2_hover": "#ff9a7b",
}

THEMES = {
    "dark": {
        **_COMMON,
        "bg": "#1d181b", "card": "#282126", "pane": "#221c20", "text": "#f6e6ee",
        "text_soft": "#c597ad", "accent": "#ff9cc4", "soft": "#3a2833", "soft_hover": "#4a3140",
        "border": "#45313c", "header1": "#3a2432", "header2": "#4b2a3d",
        "item_hover": "#33272e", "indicator_bg": "#1d181b", "scroll": "#6e4459",
        "log_text": "#e7c3d4", "disabled_bg": "#4a3540", "disabled_text": "#9d8090",
        "input_disabled_bg": "#241e22", "input_disabled_text": "#7d6672",
        "placeholder": "#8f6f80", "chip_bg": "#282126",
    },
    "light": {
        **_COMMON,
        "bg": "#fff0f6", "card": "#ffffff", "pane": "#fffafc", "text": "#6b3a52",
        "text_soft": "#b5668a", "accent": "#d44d86", "soft": "#ffe3ee", "soft_hover": "#ffd1e1",
        "border": "#ffd1e1", "header1": "#ffd6e7", "header2": "#ffc2da",
        "item_hover": "#fff3f8", "indicator_bg": "#ffffff", "scroll": "#ffb3cd",
        "log_text": "#8a4a64", "disabled_bg": "#f6cddd", "disabled_text": "#fff6fa",
        "input_disabled_bg": "#fdf3f7", "input_disabled_text": "#c9a3b5",
        "placeholder": "#d7a9bd", "chip_bg": "#ffffff",
    },
}

_current = "dark"


def current() -> dict:
    """The active palette (used for the few colours set in code)."""
    return THEMES[_current]


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


def stylesheet(c: dict) -> str:
    check, down, up = _url("check.svg"), _url("arrow_down.svg"), _url("arrow_up.svg")
    return f"""
* {{
    font-family: "M PLUS Rounded 1c", "Yu Gothic UI", "Meiryo UI", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {c["text"]};
}}
QMainWindow, QWidget#central {{ background: {c["bg"]}; }}

/* header ---------------------------------------------------------------- */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["header1"]}, stop:1 {c["header2"]});
    border-radius: 18px;
}}
QLabel#title {{ font-size: 20pt; font-weight: 800; color: {c["accent"]}; background: transparent; }}
QLabel#subtitle {{ font-size: 9.5pt; color: {c["text_soft"]}; background: transparent; }}
QLabel#chip {{
    background: {c["chip_bg"]}; border-radius: 13px; padding: 5px 14px;
    color: {c["accent"]}; font-weight: 700;
}}
QLabel#chip[watching="true"] {{ background: {c["mint"]}; color: white; }}
QLabel#logo {{ background: transparent; }}

/* tabs ------------------------------------------------------------------ */
QTabWidget::pane {{
    border: 2px solid {c["border"]}; border-radius: 18px; background: {c["pane"]}; top: -2px;
}}
QTabBar::tab {{
    background: {c["soft"]}; color: {c["accent"]}; font-weight: 700;
    padding: 8px 22px; margin: 0 4px 6px 4px; border-radius: 14px;
}}
QTabBar::tab:selected {{ background: {c["pink"]}; color: white; }}
QTabBar::tab:hover:!selected {{ background: {c["soft_hover"]}; }}

/* group boxes = soft cards ------------------------------------------------ */
QGroupBox {{
    background: {c["card"]}; border: 2px solid {c["border"]}; border-radius: 16px;
    margin-top: 16px; padding: 16px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 16px;
    padding: 3px 12px; background: {c["soft"]}; color: {c["accent"]};
    border-radius: 10px; font-weight: 800;
}}

/* buttons --------------------------------------------------------------- */
QPushButton {{
    background: {c["pink"]}; color: white; border: none; border-radius: 13px;
    padding: 7px 16px; font-weight: 700;
}}
QPushButton:hover {{ background: {c["pink_hover"]}; }}
QPushButton:pressed {{ background: {c["pink_pressed"]}; }}
QPushButton:disabled {{ background: {c["disabled_bg"]}; color: {c["disabled_text"]}; }}

QPushButton#watchBtn {{
    font-size: 13pt; padding: 12px; border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["watch1"]}, stop:1 {c["watch2"]});
}}
QPushButton#watchBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["watch1_hover"]}, stop:1 {c["watch2_hover"]});
}}
QPushButton#watchBtn[watching="true"] {{ background: {c["mint"]}; }}
QPushButton#watchBtn[watching="true"]:hover {{ background: {c["mint_hover"]}; }}

QPushButton#softBtn {{ background: {c["soft"]}; color: {c["accent"]}; }}
QPushButton#softBtn:hover {{ background: {c["soft_hover"]}; }}

/* inputs ---------------------------------------------------------------- */
QLineEdit, QComboBox, QAbstractSpinBox {{
    background: {c["card"]}; border: 2px solid {c["border"]}; border-radius: 11px;
    padding: 4px 10px; min-height: 22px;
    selection-background-color: {c["pink"]}; selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{ border-color: {c["pink_hover"]}; }}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
    background: {c["input_disabled_bg"]}; color: {c["input_disabled_text"]};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {c["card"]}; border: 2px solid {c["border"]}; border-radius: 10px;
    selection-background-color: {c["soft"]}; selection-color: {c["accent"]}; outline: none;
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    border: none; background: transparent; width: 18px;
}}
QAbstractSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}

/* voice list ------------------------------------------------------------ */
QListWidget {{
    background: {c["card"]}; border: 2px solid {c["border"]}; border-radius: 14px;
    padding: 6px; outline: none;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 8px; }}
QListWidget::item:hover {{ background: {c["item_hover"]}; }}
QListWidget::item:selected {{ background: {c["soft"]}; color: {c["accent"]}; }}
QListWidget::indicator {{
    width: 16px; height: 16px; border-radius: 6px;
    border: 2px solid {c["border"]}; background: {c["indicator_bg"]};
}}
QListWidget::indicator:checked {{
    background: {c["pink"]}; border-color: {c["pink"]}; image: url("{check}");
}}

/* check boxes ----------------------------------------------------------- */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 6px;
    border: 2px solid {c["border"]}; background: {c["indicator_bg"]};
}}
QCheckBox::indicator:checked {{ background: {c["pink"]}; border-color: {c["pink"]}; image: url("{check}"); }}
QCheckBox::indicator:disabled {{ background: {c["input_disabled_bg"]}; }}

/* radio buttons --------------------------------------------------------- */
QRadioButton::indicator {{
    width: 14px; height: 14px; border-radius: 9px;
    border: 2px solid {c["border"]}; background: {c["indicator_bg"]};
}}
QRadioButton::indicator:checked {{ background: {c["pink"]}; border-color: {c["pink"]}; }}

/* progress -------------------------------------------------------------- */
QProgressBar {{
    background: {c["soft"]}; border: none; border-radius: 9px; min-height: 18px;
    text-align: center; color: {c["accent"]}; font-weight: 700;
}}
QProgressBar::chunk {{
    border-radius: 9px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c["scroll"]}, stop:1 {c["pink"]});
}}

/* log ------------------------------------------------------------------- */
QPlainTextEdit {{
    background: {c["pane"]}; border: 2px solid {c["border"]}; border-radius: 14px;
    padding: 8px; color: {c["log_text"]};
    selection-background-color: {c["pink"]}; selection-color: white;
}}
QPlainTextEdit#log {{ font-family: "Cascadia Mono", "Consolas", "MS Gothic", monospace; font-size: 9pt; }}
QLabel#logTitle {{ color: {c["accent"]}; font-weight: 800; padding-left: 6px; }}

/* misc ------------------------------------------------------------------ */
QSplitter::handle {{ background: transparent; height: 10px; }}
QMenuBar {{ background: {c["bg"]}; }}
QMenuBar::item {{ padding: 4px 10px; border-radius: 8px; background: transparent; }}
QMenuBar::item:selected {{ background: {c["soft"]}; color: {c["accent"]}; }}
QMenu {{ background: {c["card"]}; border: 2px solid {c["border"]}; border-radius: 10px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {c["soft"]}; color: {c["accent"]}; }}
QToolTip {{
    background: {c["card"]}; color: {c["text"]}; border: 2px solid {c["border"]};
    border-radius: 8px; padding: 4px 8px;
}}
QMessageBox {{ background: {c["bg"]}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {c["scroll"]}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c["pink"]}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: {c["scroll"]}; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


def apply(app: QApplication, name: str = "dark") -> None:
    global _current
    _current = name if name in THEMES else "dark"
    c = THEMES[_current]
    app.setStyle("Fusion")
    p = QPalette()
    for role, col in (
        (QPalette.Window, c["bg"]), (QPalette.WindowText, c["text"]), (QPalette.Base, c["card"]),
        (QPalette.AlternateBase, c["pane"]), (QPalette.Text, c["text"]), (QPalette.Button, c["pink"]),
        (QPalette.ButtonText, "#ffffff"), (QPalette.ToolTipBase, c["card"]),
        (QPalette.ToolTipText, c["text"]), (QPalette.Highlight, c["pink"]),
        (QPalette.HighlightedText, "#ffffff"), (QPalette.PlaceholderText, c["placeholder"]),
    ):
        p.setColor(role, QColor(col))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(c["input_disabled_text"]))
    app.setPalette(p)
    app.setStyleSheet(stylesheet(c))
    app.setWindowIcon(icon())


def repolish(widget) -> None:
    """Re-apply the stylesheet after changing a dynamic property."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
