# ============================================================
# settings_window.py — tái dựng từ bytecode Python 3.13
# Cửa sổ cài đặt (QDialog) cho "Nghề Gỗ": số vòng chặt cây,
# mục tiêu cưa (bỏ qua / ván / củi) và cấu hình bán (Shop).
# Cấu hình lưu tại %APPDATA%\Panda\settings_woodcutting_gta5vn.json
# ============================================================
import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QRadioButton, QGroupBox, QButtonGroup, QCheckBox,
)
from PySide6.QtCore import Qt
from utils import config_path_AppData

DEFAULT_SETTINGS = {
    "wood_loops": 3,
    "craft_target": "none",  # 'none' | 'plank' | 'firewood'
    "sell": {"log": True, "plank": True, "firewood": True},
}


def merge_settings(default: dict, user: dict) -> dict:
    result = default.copy()
    for key, value in default.items():
        if key not in user:
            continue
        if isinstance(value, dict) and isinstance(user[key], dict):
            result[key] = merge_settings(value, user[key])
        else:
            result[key] = user[key]
    return result


def load_settings():
    path = config_path_AppData("settings_woodcutting_gta5vn.json")
    if not os.path.exists(path):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return merge_settings(DEFAULT_SETTINGS, data)
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    path = config_path_AppData("settings_woodcutting_gta5vn.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.setWindowTitle("C\u00e0i \u0111\u1eb7t Ngh\u1ec1 G\u1ed7")
        self.setFixedSize(380, 350)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: white; }
            QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; color: #03A9F4; }
            QLabel, QRadioButton, QCheckBox { font-size: 13px; color: white; }
            QSpinBox { background-color: #2C2F33; border: 1px solid #555; border-radius: 4px; padding: 4px; color: white; }
            QPushButton { background-color: #2C2F33; border: 1px solid #555; border-radius: 6px; padding: 6px 14px; color: white; }
            QPushButton:hover { background-color: #03A9F4; color: black; }
        """)

        main_layout = QVBoxLayout(self)

        # --- Nhóm: Chặt cây ---
        mining_group = QGroupBox("Ch\u1eb7t c\u00e2y")
        mining_layout = QHBoxLayout()
        self.mining_spin = QSpinBox()
        self.mining_spin.setRange(1, 999)
        self.mining_spin.setValue(self.settings["wood_loops"])
        mining_layout.addWidget(QLabel("S\u1ed1 v\u00f2ng l\u1eb7p ch\u1eb7t c\u00e2y:"))
        mining_layout.addStretch()
        mining_layout.addWidget(self.mining_spin)
        mining_group.setLayout(mining_layout)
        main_layout.addWidget(mining_group)

        # --- Nhóm: Máy cưa ---
        craft_group = QGroupBox("M\u00e1y c\u01b0a")
        craft_layout = QVBoxLayout()
        self.radio_none = QRadioButton("B\u1ecf qua m\u00e1y c\u01b0a (Ch\u1ec9 b\u00e1n G\u1ed7 Th\u00f4)")
        self.radio_plank = QRadioButton("C\u01b0a V\u00e1n G\u1ed7")
        self.radio_firewood = QRadioButton("C\u01b0a C\u1ee7i (G\u1ed7 -> V\u00e1n -> C\u1ee7i)")
        self.craft_group_btn = QButtonGroup(self)
        self.craft_group_btn.addButton(self.radio_none)
        self.craft_group_btn.addButton(self.radio_plank)
        self.craft_group_btn.addButton(self.radio_firewood)
        t = self.settings["craft_target"]
        if t == "plank":
            self.radio_plank.setChecked(True)
        elif t == "firewood":
            self.radio_firewood.setChecked(True)
        else:
            self.radio_none.setChecked(True)
        craft_layout.addWidget(self.radio_none)
        craft_layout.addWidget(self.radio_plank)
        craft_layout.addWidget(self.radio_firewood)
        craft_group.setLayout(craft_layout)
        main_layout.addWidget(craft_group)

        # --- Nhóm: Bán (Shop) ---
        sell_group = QGroupBox("Thi\u1ebft l\u1eadp B\u00e1n (Shop)")
        sell_layout = QHBoxLayout()
        self.chk_log = QCheckBox("B\u00e1n G\u1ed7 Th\u00f4")
        self.chk_plank = QCheckBox("B\u00e1n V\u00e1n G\u1ed7")
        self.chk_firewood = QCheckBox("B\u00e1n C\u1ee7i")
        self.chk_log.setChecked(self.settings["sell"]["log"])
        self.chk_plank.setChecked(self.settings["sell"]["plank"])
        self.chk_firewood.setChecked(self.settings["sell"]["firewood"])
        sell_layout.addWidget(self.chk_log)
        sell_layout.addWidget(self.chk_plank)
        sell_layout.addWidget(self.chk_firewood)
        sell_group.setLayout(sell_layout)
        main_layout.addWidget(sell_group)

        # --- Nút Lưu / Hủy ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton("L\u01b0u")
        self.cancel_button = QPushButton("H\u1ee7y")
        self.save_button.clicked.connect(self.on_save)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def on_save(self):
        self.settings["wood_loops"] = self.mining_spin.value()
        if self.radio_plank.isChecked():
            self.settings["craft_target"] = "plank"
        elif self.radio_firewood.isChecked():
            self.settings["craft_target"] = "firewood"
        else:
            self.settings["craft_target"] = "none"
        self.settings["sell"] = {
            "log": self.chk_log.isChecked(),
            "plank": self.chk_plank.isChecked(),
            "firewood": self.chk_firewood.isChecked(),
        }
        save_settings(self.settings)
        self.accept()

    def get_settings(self):
        return self.settings
