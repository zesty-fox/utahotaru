"""读音词典子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog
from qfluentwidgets import FluentIcon as FIF, PushButton, SettingCard, SettingCardGroup

from ..cards import SwitchSettingCard
from ..dictionary_dialog import DictionaryEditDialog
from .base import SubSettingInterface


class DictionarySubInterface(SubSettingInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_ref = None
        self._init_ui()

    def _init_ui(self):
        g = SettingCardGroup("读音词典", self.scrollWidget)
        dict_card = SettingCard(FIF.DICTIONARY, "自定义读音",
            "固定特定词汇的注音读法（最长匹配优先）", g)
        self.btn_open_dict = PushButton("编辑词典", dict_card)
        self.btn_open_dict.setFont(QFont("Microsoft YaHei", 10))
        self.btn_open_dict.clicked.connect(self._on_open_dictionary)
        dict_card.hBoxLayout.addWidget(self.btn_open_dict, 0, Qt.AlignmentFlag.AlignRight)
        dict_card.hBoxLayout.addSpacing(16)
        self.dict_card = dict_card

        self.card_annotate_katakana_with_english = SwitchSettingCard(
            FIF.LANGUAGE, "根据用户词典给片假名标注英文",
            "开启后，用户词典中纯片假名词条或读音为英文的词条将被应用；关闭时拦截这类词条",
            parent=g)
        g.addSettingCard(self.dict_card)
        g.addSettingCard(self.card_annotate_katakana_with_english)
        self.expandLayout.addWidget(g)

    def _on_open_dictionary(self):
        if self._settings_ref is None:
            return
        entries = self._settings_ref.load_dictionary()
        dialog = DictionaryEditDialog(entries, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings_ref.save_dictionary(dialog.get_entries())

    def connect_signals(self):
        self.card_annotate_katakana_with_english.checked_changed.connect(self._notify_changed)

    def load_settings(self, s):
        self._settings_ref = s
        self.card_annotate_katakana_with_english.setChecked(
            s.get("ruby_dictionary.annotate_katakana_with_english", False))

    def collect_settings(self, s):
        s.set("ruby_dictionary.annotate_katakana_with_english",
              self.card_annotate_katakana_with_english.isChecked())
