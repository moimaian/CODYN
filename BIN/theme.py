# -*- coding: utf-8 -*-
"""Tema visual do CODYN (mesma identidade escura do CODRUG).

- PALETTE: cores nomeadas, para uso em código novo (evita hex solto pela interface);
- SS_MAIN: stylesheet global (aplicar com QApplication.setStyleSheet);
- SS_BTN_*: estilos de botão por "papel" (primary, select, secondary, danger, orange, nav, flat);
- set_role(btn, role): marca o botão e aplica o estilo do papel;
- ensure_button_fits(btn): garante que o texto do botão não seja cortado (usado após trocar idioma).
"""

PALETTE = {
    "bg": "#0D1B2A",          # fundo da janela / grupos
    "panel": "#14253A",       # painel das abas, tabelas
    "field": "#1C3249",       # campos de entrada, hover
    "border": "#2A4A6B",
    "text": "#C9D1D9",
    "muted": "#6E8CA8",
    "accent": "#2ECC71",      # verde de destaque (seleção, foco, títulos)
    "accent_dark": "#27AE60",
    "ok": "#27AE60",
    "warn": "#F5A623",
    "danger": "#E74C3C",
    "danger_soft": "#F39A8A",
    "brand": "#F57C6F",
    "info": "#69B7FF",
    "console_bg": "#0A1520",
}

SS_MAIN = """
QMainWindow, QWidget {
    background-color: #0D1B2A;
    font-family: 'DejaVu Sans', 'Segoe UI', sans-serif;
    font-size: 10pt;
    color: #C9D1D9;
}

QTabWidget#main_tabs::pane {
    border: 1px solid #2A4A6B;
    border-radius: 6px;
    background: #14253A;
}
QTabWidget#main_tabs QTabBar::tab {
    background: #0D1B2A;
    color: #6E8CA8;
    padding: 7px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
    min-width: 70px;
}
QTabWidget#main_tabs QTabBar::tab:selected {
    background: #14253A;
    color: #2ECC71;
    border-bottom: 3px solid #2ECC71;
}
QTabWidget#main_tabs QTabBar::tab:hover:!selected {
    background: #1C3249;
    color: #C9D1D9;
}

QTabWidget#step6_side_tabs::pane {
    border: 1.5px solid #2A4A6B;
    border-radius: 6px;
    background: #14253A;
}
QTabWidget#step6_side_tabs QTabBar::tab {
    background: #0D1B2A;
    color: #6E8CA8;
    padding: 6px 6px;
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
    font-weight: bold;
    min-height: 70px;
    min-width: 30px;
    font-size: 9pt;
}
QTabWidget#step6_side_tabs QTabBar::tab:selected {
    background: #14253A;
    color: #2ECC71;
    border-right: 3px solid #2ECC71;
    border-bottom: none;
}
QTabWidget#step6_side_tabs QTabBar::tab:hover:!selected {
    background: #1C3249;
    color: #C9D1D9;
}

QGroupBox {
    font-weight: bold;
    border: 1.5px solid #2A4A6B;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    background: #0D1B2A;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #2ECC71;
}
QGroupBox QLabel {
    background: transparent;
}
QLabel {
    background: transparent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QListWidget, QTableWidget {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    padding: 4px 8px;
    background: #1C3249;
    color: #C9D1D9;
    selection-background-color: #27AE60;
}

QComboBox {
    min-height: 22px;
    padding-right: 28px;
}

QComboBox:editable {
    background: #1C3249;
}

QComboBox QLineEdit {
    border: none;
    background: transparent;
    color: #C9D1D9;
    padding: 0;
    selection-background-color: #27AE60;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QListWidget:focus, QTableWidget:focus {
    border-radius: 4px;
    border: 2px solid #2ECC71;
}

QComboBox:focus {
    border-radius: 4px;
    border-top: 2px solid #2ECC71;
    border-right: 2px solid #2ECC71;
    border-bottom: 2px solid #2ECC71;
    border-left: 2px solid #2ECC71;
    background: #1C3249;
}

QComboBox QLineEdit:focus {
    border: none;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    background: #14253A;
    border-left: 1px solid #2A4A6B;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QComboBox:focus::drop-down {
    border-left: 1px solid #2ECC71;
}

QComboBox::down-arrow {
    image: none;
    width: 1px;
    height: 1px;
    border-left: 2px solid transparent;
    border-right: 2px solid transparent;
    border-top: 2px solid #6E8CA8;
}
QComboBox::down-arrow:on {
    border-top: 2px solid #2ECC71;
}

QComboBox QAbstractItemView {
    background: #0D1B2A;
    color: #C9D1D9;
    border: 1.5px solid #2A4A6B;
    border-radius: 4px;
    padding: 2px;
    selection-background-color: #1A4A30;
    selection-color: #2ECC71;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 5px 8px;
    min-height: 24px;
}
QComboBox QAbstractItemView::item:hover {
    background: #1C3249;
    color: #C9D1D9;
}

/* Controles desabilitados "apagados": fundo/borda próximos do painel e texto escuro, para ficar
   claro que não aceitam seleção/edição (antes o fundo era o mesmo dos campos ativos). */
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QTextEdit:disabled, QListWidget:disabled, QTableWidget:disabled {
    background: #132131;
    border: 1px solid #1C2E42;
    color: #4F6A84;
}
QComboBox:disabled::drop-down {
    background: #132131;
    border-left: 1px solid #1C2E42;
}
QComboBox:disabled QLineEdit {
    color: #4F6A84;
}

QScrollBar:vertical {
    background: #0D1B2A;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #2A4A6B;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #2ECC71;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #0D1B2A;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #2A4A6B;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #2ECC71;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QProgressBar {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    text-align: center;
    background: #1C3249;
    color: #C9D1D9;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #145A32, stop:1 #1E8449);
    border-radius: 4px;
}
QCheckBox, QRadioButton {
    color: #C9D1D9;
    spacing: 6px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
}
QCheckBox::indicator {
    border: 1px solid #2A4A6B;
    border-radius: 3px;
    background: #1C3249;
}
QCheckBox::indicator:checked {
    background: #2ECC71;
    border-color: #2ECC71;
}
QCheckBox:disabled, QRadioButton:disabled {
    color: #4F6A84;
}
QCheckBox::indicator:disabled {
    background: #132131;
    border-color: #1C2E42;
}
QCheckBox::indicator:checked:disabled {
    background: #1E5C3A;
    border-color: #1E5C3A;
}
QMenuBar {
    background: #0D1B2A;
    color: #C9D1D9;
    border-bottom: 1px solid #2A4A6B;
}
QMenuBar::item:selected {
    background: #1C3249;
    color: #2ECC71;
}
QMenu {
    background: #14253A;
    color: #C9D1D9;
    border: 1px solid #2A4A6B;
}
QMenu::item:selected {
    background: #1C3249;
    color: #2ECC71;
}
QSplitter::handle {
    background: #2A4A6B;
}
QTableWidget {
    background: #14253A;
    color: #C9D1D9;
    gridline-color: #2A4A6B;
    alternate-background-color: #1C3249;
}
QHeaderView::section {
    background: #0D1B2A;
    color: #C9D1D9;
    font-weight: bold;
    padding: 4px;
    border: none;
}
QToolTip {
    background: #1C3249;
    color: #C9D1D9;
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    padding: 4px;
}
QPushButton {
    background: #1A4A30;
    color: #2ECC71;
    font-weight: bold;
    border: 1px solid #2ECC71;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover {
    background: #27AE60;
    color: #0D1B2A;
}
QPushButton:pressed {
    background: #1E8449;
    color: #FFF;
}
QPushButton:disabled {
    background: #1C2E20;
    color: #3D6B4A;
    border-color: #2A4A36;
}
"""

SS_BTN_PRIMARY = """
QPushButton {
    background: #1A4A30;
    color: #2ECC71;
    font-weight: bold;
    border: 1px solid #2ECC71;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #27AE60; color: #0D1B2A; }
QPushButton:pressed { background: #1E8449; color: #FFF; }
QPushButton:disabled { background: #1C2E20; color: #3D6B4A; border-color: #2A4A36; }
"""

SS_BTN_SELECT = """
QPushButton {
    background: #163A5A;
    color: #69B7FF;
    font-weight: bold;
    border: 1px solid #4AA3DF;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #2D6F9F; color: #0D1B2A; }
QPushButton:pressed { background: #1E567C; color: #FFF; }
QPushButton:disabled { background: #1A2732; color: #4B6D87; border-color: #2B4960; }
"""

SS_BTN_SECONDARY = """
QPushButton {
    background: #243746;
    color: #A9BED1;
    font-weight: bold;
    border: 1px solid #6E8CA8;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #37536C; color: #C9D1D9; }
QPushButton:pressed { background: #1C3249; color: #FFF; }
QPushButton:disabled { background: #1B2730; color: #4F6577; border-color: #344654; }
"""

SS_BTN_DANGER = """
QPushButton {
    background: #4A2A2A;
    color: #F39A8A;
    font-weight: bold;
    border: 1px solid #F39A8A;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #F0AA9D; color: #0D1B2A; }
QPushButton:pressed { background: #D98979; color: #FFF; }
QPushButton:disabled { background: #352323; color: #8D6A66; border-color: #5A4340; }
"""

# Botão só-símbolo (ex.: "+" / "−" da grade de hiperparâmetros): sem fundo nem contorno.
SS_BTN_FLAT = """
QPushButton {
    background: transparent;
    border: none;
    color: #C9D1D9;
    font-size: 16pt;
    font-weight: bold;
    padding: 0px 4px;
}
QPushButton:hover { color: #2ECC71; }
QPushButton:pressed { color: #27AE60; }
QPushButton:disabled { color: #4A5A6B; }
"""

SS_BTN_ORANGE = """
QPushButton {
    background: #4A3419;
    color: #F5A623;
    font-weight: bold;
    border: 1px solid #F5A623;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #F0A83C; color: #0D1B2A; }
QPushButton:pressed { background: #D98F1F; color: #FFF; }
QPushButton:disabled { background: #362B1D; color: #8D7355; border-color: #5A4A30; }
"""

SS_BTN_NAV = """
QPushButton {
    background: transparent;
    border: none;
    color: #14253A;
    font-size: 12pt;
    font-weight: bold;
}
QPushButton:hover { color: #C9D1D9; }
QPushButton:pressed { color: #27AE60; }
"""

SS_GROUPBOX_PANEL = "QGroupBox { background-color: #0D1B2A; border: 1.5px solid #2A4A6B; border-radius: 6px; }"
SS_FIELD_READONLY = "background-color: #1C3249; color: #C9D1D9; border: 1px solid #2A4A6B; border-radius: 4px; padding: 5px;"

_ROLE_MAP = {
    "primary": SS_BTN_PRIMARY,
    "select": SS_BTN_SELECT,
    "secondary": SS_BTN_SECONDARY,
    "danger": SS_BTN_DANGER,
    "orange": SS_BTN_ORANGE,
    "nav": SS_BTN_NAV,
    "flat": SS_BTN_FLAT,
}


def set_role(button, role):
    """Define o papel visual do botão (primary|select|secondary|danger|orange|nav|flat)."""
    button.setProperty("role", role)
    button.setStyleSheet(_ROLE_MAP.get(role, SS_BTN_PRIMARY))
    return button


def ensure_button_fits(button):
    """Só cresce botões de largura fixa/mínima quando o texto (ex.: após troca de idioma) não cabe."""
    text = button.text() or ""
    if not text.strip():
        return
    button.ensurePolished()
    required = button.sizeHint().width() + 8
    cur_min, cur_max = button.minimumWidth(), button.maximumWidth()
    if cur_min > 0 and cur_min == cur_max:
        if cur_min < required:
            button.setFixedWidth(required)
    elif cur_min < required:
        button.setMinimumWidth(required)
