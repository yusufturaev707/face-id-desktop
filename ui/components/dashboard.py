from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.styles import COLORS, FONT_FAMILY, stat_card_style


class StatCard(QWidget):
    def __init__(self, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(stat_card_style(color))
        self.setFixedHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setFont(QFont("Segoe UI", 13))
        self._title_label.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        layout.addWidget(self._title_label)

        self._value_label = QLabel(value)
        self._value_label.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self._value_label.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(self._value_label)

    def set_value(self, value: str):
        self._value_label.setText(value)


class StudentInfoCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            background-color: {COLORS['surface']};
            border-radius: 14px;
            border: 2px solid {COLORS['primary']};
            padding: 20px;
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        header = QLabel("Aniqlangan student")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {COLORS['primary']}; border: none;")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['divider']};")
        layout.addWidget(sep)

        self._name_label = self._info_row(layout, "Ism:")
        self._group_label = self._info_row(layout, "Guruh:")
        self._seat_label = self._info_row(layout, "O'rin:")
        self._gender_label = self._info_row(layout, "Jinsi:")
        self._confidence_label = self._info_row(layout, "Aniqlik:")

        self.clear()

    def _info_row(self, parent_layout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        key = QLabel(label_text)
        key.setFixedWidth(90)
        key.setFont(QFont("Segoe UI", 14))
        key.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        row.addWidget(key)

        value = QLabel("\u2014")
        value.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        value.setStyleSheet("border: none;")
        row.addWidget(value)
        row.addStretch()

        parent_layout.addLayout(row)
        return value

    def update_student(self, data: dict):
        self._name_label.setText(data.get("full_name", "\u2014"))
        self._group_label.setText(data.get("group_name", "\u2014"))
        self._seat_label.setText(data.get("seat_number", "\u2014"))

        gender = data.get("gender", 0)
        gender_display = {1: "Erkak", 2: "Ayol"}.get(gender, str(gender))
        self._gender_label.setText(gender_display)

        confidence = data.get("confidence", 0)
        pct = f"{confidence * 100:.1f}%"
        color = COLORS["success"] if confidence >= 0.6 else COLORS["warning"]
        self._confidence_label.setText(pct)
        self._confidence_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {color}; border: none;"
        )

    def clear(self):
        for lbl in [self._name_label, self._group_label, self._seat_label,
                     self._gender_label, self._confidence_label]:
            lbl.setText("\u2014")
            lbl.setStyleSheet("font-size: 15px; font-weight: 600; border: none;")


class Dashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Session info
        self.session_label = QLabel("Test: \u2014")
        self.session_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.session_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(self.session_label)

        # Stat cards row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)

        self.total_card = StatCard("Jami o'tganlar", "0", COLORS["primary"])
        stats_row.addWidget(self.total_card)

        self.male_card = StatCard("Erkaklar", "0", COLORS["male"])
        stats_row.addWidget(self.male_card)

        self.female_card = StatCard("Ayollar", "0", COLORS["female"])
        stats_row.addWidget(self.female_card)

        layout.addLayout(stats_row)

        # Student info card
        self.student_card = StudentInfoCard()
        layout.addWidget(self.student_card)

        layout.addStretch()

    def set_session_info(self, name: str, date: str, shift: int):
        self.session_label.setText(f"{name} | {date} | Smena: {shift}")

    def update_counts(self, total: int, male: int, female: int):
        self.total_card.set_value(str(total))
        self.male_card.set_value(str(male))
        self.female_card.set_value(str(female))

    def show_student(self, data: dict):
        self.student_card.update_student(data)
