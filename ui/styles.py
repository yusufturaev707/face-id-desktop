# Material Design Color Palette
COLORS = {
    "primary": "#1565C0",
    "primary_light": "#1E88E5",
    "primary_dark": "#0D47A1",
    "secondary": "#00897B",
    "secondary_light": "#26A69A",
    "accent": "#FF6D00",
    "background": "#F5F5F5",
    "surface": "#FFFFFF",
    "error": "#D32F2F",
    "success": "#2E7D32",
    "warning": "#F9A825",
    "on_primary": "#FFFFFF",
    "on_surface": "#212121",
    "text_primary": "#212121",
    "text_secondary": "#757575",
    "divider": "#BDBDBD",
    "card_shadow": "rgba(0, 0, 0, 0.12)",
    "male": "#1976D2",
    "female": "#E91E63",
}

# Font constants
FONT_FAMILY = "'Segoe UI', 'Roboto', 'Arial', sans-serif"
FONT_SIZE_XS = "12px"
FONT_SIZE_SM = "14px"
FONT_SIZE_MD = "16px"
FONT_SIZE_LG = "18px"
FONT_SIZE_XL = "22px"
FONT_SIZE_XXL = "28px"
FONT_SIZE_HERO = "36px"

GLOBAL_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['background']};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD};
    color: {COLORS['text_primary']};
}}

QPushButton {{
    background-color: {COLORS['primary']};
    color: {COLORS['on_primary']};
    border: none;
    border-radius: 8px;
    padding: 12px 28px;
    font-size: {FONT_SIZE_MD};
    font-weight: 600;
    min-height: 42px;
    font-family: {FONT_FAMILY};
}}
QPushButton:hover {{
    background-color: {COLORS['primary_light']};
}}
QPushButton:pressed {{
    background-color: {COLORS['primary_dark']};
}}
QPushButton:disabled {{
    background-color: {COLORS['divider']};
    color: {COLORS['text_secondary']};
}}

QPushButton[class="secondary"] {{
    background-color: {COLORS['secondary']};
}}
QPushButton[class="secondary"]:hover {{
    background-color: {COLORS['secondary_light']};
}}

QPushButton[class="danger"] {{
    background-color: {COLORS['error']};
}}

QPushButton[class="success"] {{
    background-color: {COLORS['success']};
}}

QLineEdit {{
    border: 2px solid {COLORS['divider']};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: {FONT_SIZE_MD};
    font-family: {FONT_FAMILY};
    background-color: {COLORS['surface']};
}}
QLineEdit:focus {{
    border-color: {COLORS['primary']};
}}

QComboBox {{
    border: 2px solid {COLORS['divider']};
    border-radius: 8px;
    padding: 10px 16px;
    font-size: {FONT_SIZE_MD};
    font-family: {FONT_FAMILY};
    background-color: {COLORS['surface']};
    min-height: 42px;
}}
QComboBox:focus {{
    border-color: {COLORS['primary']};
}}
QComboBox::drop-down {{
    border: none;
    width: 36px;
}}

QLabel {{
    font-size: {FONT_SIZE_MD};
    font-family: {FONT_FAMILY};
}}
QLabel[class="title"] {{
    font-size: {FONT_SIZE_XXL};
    font-weight: 700;
    color: {COLORS['primary_dark']};
}}
QLabel[class="subtitle"] {{
    font-size: {FONT_SIZE_LG};
    color: {COLORS['text_secondary']};
}}
QLabel[class="card-title"] {{
    font-size: {FONT_SIZE_LG};
    font-weight: 600;
}}

QListWidget {{
    border: 2px solid {COLORS['divider']};
    border-radius: 8px;
    background-color: {COLORS['surface']};
    padding: 6px;
    font-size: {FONT_SIZE_MD};
    font-family: {FONT_FAMILY};
}}
QListWidget::item {{
    padding: 14px 12px;
    border-bottom: 1px solid {COLORS['divider']};
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: {COLORS['on_primary']};
}}
QListWidget::item:hover {{
    background-color: #E3F2FD;
}}

QProgressBar {{
    border: none;
    border-radius: 5px;
    background-color: #E0E0E0;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {COLORS['primary']};
    border-radius: 5px;
}}

QFrame[class="card"] {{
    background-color: {COLORS['surface']};
    border-radius: 14px;
    border: 1px solid #E0E0E0;
}}

QGroupBox {{
    font-size: {FONT_SIZE_MD};
    font-weight: 600;
    border: 2px solid {COLORS['divider']};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 18px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['divider']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['text_secondary']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def card_style():
    return f"""
        background-color: {COLORS['surface']};
        border-radius: 14px;
        border: 1px solid #E0E0E0;
        padding: 20px;
    """


def stat_card_style(color: str):
    return f"""
        background-color: {COLORS['surface']};
        border-radius: 14px;
        border-left: 4px solid {color};
        border-top: 1px solid #E0E0E0;
        border-right: 1px solid #E0E0E0;
        border-bottom: 1px solid #E0E0E0;
        padding: 20px;
    """


def nav_btn_style(bg_color: str, hover_color: str, text_color: str = "white"):
    """Reusable style for navigation buttons (Chiqish, Orqaga, etc.)."""
    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            border: none;
            border-radius: 10px;
            padding: 0 20px;
            font-family: {FONT_FAMILY};
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
    """


def nav_btn_outline_style(color: str):
    """Outlined nav button style."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {color};
            border: 2px solid {color};
            border-radius: 10px;
            padding: 0 20px;
            font-family: {FONT_FAMILY};
        }}
        QPushButton:hover {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
    """
