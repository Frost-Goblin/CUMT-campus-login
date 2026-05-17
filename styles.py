from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from constants import BUNDLED_FONT_PATHS, TYPOGRAPHY, UI_RADIUS
from paths import ICON_DIR, append_runtime_log

APP_STYLE_TEMPLATE = """
QWidget {
    color: #152033;
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_APP_SIZE__px;
    font-weight: __TYPO_APP_WEIGHT__;
}
QMainWindow, QWidget#root {
    background: #f3f6fb;
}
QLabel {
    background: transparent;
}
QFrame#windowSurface {
    background: #f3f6fb;
    border: none;
    border-radius: 0px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 6px 0 6px 0;
}
QScrollBar::handle:vertical {
    background: #c8d4e6;
    min-height: 44px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #aebfd9;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QFrame#titleBar {
    background: #f3f6fb;
    border: none;
    border-top-left-radius: __RADIUS__px;
    border-top-right-radius: __RADIUS__px;
}
QLabel#windowTitle {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_WINDOW_TITLE_SIZE__px;
    font-weight: __TYPO_WINDOW_TITLE_WEIGHT__;
}
QLabel#titleBrand {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_TITLE_BRAND_SIZE__px;
    font-weight: __TYPO_TITLE_BRAND_WEIGHT__;
    color: #ffffff;
    background: #122E8A;
    border-radius: __RADIUS__px;
    padding: 4px 4px 6px 4px;
}
QLabel#titleText {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_TITLE_TEXT_SIZE__px;
    font-weight: __TYPO_TITLE_TEXT_WEIGHT__;
    color: #061934;
}
QPushButton#titleButton,
QPushButton#titleSettingsButton,
QPushButton#titleMinButton {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: #314158;
    font-family: "Segoe Fluent Icons";
}
QPushButton#titleButton {
    font-size: __TYPO_TITLE_BUTTON_ICON_SIZE__px;
    font-weight: __TYPO_TITLE_BUTTON_ICON_WEIGHT__;
}
QPushButton#titleSettingsButton {
    font-size: __TYPO_TITLE_SETTINGS_ICON_SIZE__px;
    font-weight: __TYPO_TITLE_SETTINGS_ICON_WEIGHT__;
}
QPushButton#titleMinButton {
    font-size: __TYPO_TITLE_MIN_ICON_SIZE__px;
    font-weight: __TYPO_TITLE_MIN_ICON_WEIGHT__;
}
QPushButton#titleButton:hover,
QPushButton#titleSettingsButton:hover,
QPushButton#titleMinButton:hover {
    background: #e7edf7;
}
QPushButton#titleCloseButton {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: #314158;
    font-family: "Segoe Fluent Icons";
    font-size: __TYPO_TITLE_CLOSE_ICON_SIZE__px;
    font-weight: __TYPO_TITLE_CLOSE_ICON_WEIGHT__;
}
QPushButton#titleCloseButton:hover {
    background: #d92d20;
    color: #ffffff;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #d9e3f0;
    border-radius: __RADIUS__px;
}
QFrame#settingsPanel {
    background: #ffffff;
    border: 1px solid #d9e3f0;
    border-radius: __RADIUS__px;
}
QLabel#subtitle {
    font-family: __FONT_FAMILY__;
    color: #5d6b82;
    font-size: __TYPO_SUBTITLE_SIZE__px;
    font-weight: __TYPO_SUBTITLE_WEIGHT__;
}
QLabel#hint {
    font-family: __FONT_FAMILY__;
    color: #5d6b82;
    font-size: __TYPO_HINT_SIZE__px;
    font-weight: __TYPO_HINT_WEIGHT__;
}
QLabel#formLabel {
    font-family: __FONT_FAMILY__;
    color: #1f2f49;
    font-size: __TYPO_FORM_LABEL_SIZE__px;
    font-weight: __TYPO_FORM_LABEL_WEIGHT__;
}
QLabel#statusBadge {
    border-radius: __RADIUS__px;
    padding: 5px 11px;
    color: #ffffff;
    background: #64748b;
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_STATUS_BADGE_SIZE__px;
    font-weight: __TYPO_STATUS_BADGE_WEIGHT__;
}
QLabel#statusIcon {
    background: transparent;
    min-width: 30px;
    min-height: 30px;
    max-width: 30px;
    max-height: 30px;
    color: #24324d;
    font-family: "Segoe Fluent Icons";
    font-size: __TYPO_STATUS_ICON_SIZE__px;
    font-weight: __TYPO_STATUS_ICON_WEIGHT__;
}
QLabel#sectionTitle {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_SECTION_TITLE_SIZE__px;
    font-weight: __TYPO_SECTION_TITLE_WEIGHT__;
}
QLabel#settingsTitle {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_SETTINGS_TITLE_SIZE__px;
    font-weight: __TYPO_SETTINGS_TITLE_WEIGHT__;
}
QLabel#settingsSection {
    font-family: __FONT_FAMILY__;
    color: #22324f;
    font-size: __TYPO_SETTINGS_SECTION_SIZE__px;
    font-weight: __TYPO_SETTINGS_SECTION_WEIGHT__;
}
QLabel#settingsOptionLabel {
    font-family: __FONT_FAMILY__;
    color: #152033;
    font-size: __TYPO_SETTINGS_OPTION_SIZE__px;
    font-weight: __TYPO_SETTINGS_OPTION_WEIGHT__;
}
QCheckBox#settingsOptionCheck {
    spacing: 10px;
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_SETTINGS_OPTION_SIZE__px;
    font-weight: __TYPO_SETTINGS_OPTION_WEIGHT__;
    color: #152033;
}
QLineEdit, QComboBox, QPlainTextEdit {
    font-family: __FONT_FAMILY__;
    background: #fbfdff;
    border: 1px solid #cfd8e6;
    border-radius: __RADIUS__px;
    padding: 6px 38px 6px 12px;
    font-size: __TYPO_FIELD_SIZE__px;
    font-weight: __TYPO_FIELD_WEIGHT__;
}
QLineEdit:focus, QPlainTextEdit:focus,
QComboBox:focus {
    border: 1px solid #cfd8e6;
}
QLineEdit#plainInput {
    padding: 6px 12px;
}
QPushButton {
    min-height: 44px;
    min-width: 104px;
    border-radius: __RADIUS__px;
    border: none;
    padding: 0 16px;
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_BUTTON_SIZE__px;
    font-weight: __TYPO_BUTTON_WEIGHT__;
}
QPushButton#primary {
    background: #2563eb;
    color: #ffffff;
}
QPushButton#primary:hover {
    background: #1d4ed8;
}
QPushButton#primary:disabled {
    background: #d8e0ec;
    color: #8b9ab0;
}
QPushButton#secondary {
    background: #e8eef8;
    color: #16345f;
}
QPushButton#secondary:hover {
    background: #dce7f7;
}
QPushButton#secondary:disabled {
    background: #edf2f8;
    color: #9aa8ba;
}
QPushButton#danger {
    background: #ef4444;
    color: #ffffff;
}
QPushButton#danger:hover {
    background: #dc2626;
}
QPushButton#danger:disabled {
    background: #fecaca;
    color: #ffffff;
}
QPushButton#ghost {
    background: #e8eef8;
    color: #16345f;
    border: 1px solid #d7e2f2;
}
QPushButton#ghost:hover {
    background: #dce7f7;
}
QPushButton#ghost:checked {
    background: #d3e2fb;
    color: #12315d;
    border: 1px solid #b9cdf0;
}
QPushButton#statusActionButton {
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
    border-radius: 19px;
    border: none;
    background: transparent;
}
QPushButton#statusActionButton:hover {
    background: transparent;
}
QPushButton#statusActionButton[refreshing="true"] {
    background: transparent;
}
QPushButton#statusActionButton:disabled {
    background: transparent;
    opacity: 0.45;
}
QToolTip {
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_TOOLTIP_SIZE__px;
    font-weight: __TYPO_TOOLTIP_WEIGHT__;
    color: #f8fafc;
    background: #2f3136;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 5px 8px;
}
QCheckBox {
    spacing: 10px;
    font-family: __FONT_FAMILY__;
    font-size: __TYPO_CHECKBOX_SIZE__px;
    font-weight: __TYPO_CHECKBOX_WEIGHT__;
    color: #152033;
}
QCheckBox:disabled {
    color: #a7b4c6;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #c3d2e7;
    background: #fbfdff;
}
QCheckBox::indicator:checked {
    border: 1px solid #2563eb;
    background: #ffffff;
    image: url(__CHECKBOX_CHECK_ICON__);
}
QCheckBox::indicator:disabled {
    border: 1px solid #d8e0ea;
    background: #f6f8fc;
}
QCheckBox::indicator:disabled:checked {
    border: 1px solid #d8e0ea;
    background: #f6f8fc;
    image: url(__CHECKBOX_CHECK_ICON_DISABLED__);
}
QComboBox:disabled {
    background: #f6f8fc;
    color: #a7b4c6;
    border: 1px solid #dde4ef;
}
QComboBox:disabled::drop-down {
    border-left: 1px solid #e4e9f1;
    background: #f6f8fc;
}
QPlainTextEdit {
    background: #0f172a;
    color: #dbe7fb;
    border: 1px solid #22314b;
}
"""

_CACHED_BUNDLED_FONT_FAMILIES: set[str] | None = None


def quote_font_family(font_family: str) -> str:
    escaped = font_family.replace('"', '\\"')
    return f'"{escaped}"'


def build_app_style(font_family: str) -> str:
    checkbox_check_icon = (ICON_DIR / "checkbox-check-blue.svg").resolve().as_posix()
    checkbox_check_icon_disabled = (ICON_DIR / "checkbox-check-disabled.svg").resolve().as_posix()
    style = (
        APP_STYLE_TEMPLATE.replace("__RADIUS__", str(UI_RADIUS))
        .replace("__FONT_FAMILY__", font_family)
        .replace("__CHECKBOX_CHECK_ICON__", checkbox_check_icon)
        .replace("__CHECKBOX_CHECK_ICON_DISABLED__", checkbox_check_icon_disabled)
    )
    for role, values in TYPOGRAPHY.items():
        token = role.upper()
        style = style.replace(f"__TYPO_{token}_SIZE__", str(values["size"]))
        style = style.replace(f"__TYPO_{token}_WEIGHT__", str(values["weight"]))
    return style


def load_bundled_font_families() -> set[str]:
    global _CACHED_BUNDLED_FONT_FAMILIES
    if _CACHED_BUNDLED_FONT_FAMILIES is not None:
        return _CACHED_BUNDLED_FONT_FAMILIES

    loaded_families: set[str] = set()
    for font_path in BUNDLED_FONT_PATHS:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            append_runtime_log(f"Failed to load bundled font: {font_path}")
            continue
        loaded_families.update(QFontDatabase.applicationFontFamilies(font_id))

    _CACHED_BUNDLED_FONT_FAMILIES = loaded_families
    if loaded_families:
        append_runtime_log(f"Bundled font families loaded: {', '.join(sorted(loaded_families))}")
    else:
        append_runtime_log("Bundled MiSans fonts not loaded, using fallback system fonts")
    return loaded_families


def pick_font_family(loaded_families: set[str], *preferred: str, fallback: str) -> str:
    for family in preferred:
        if family in loaded_families:
            return family
    return fallback

