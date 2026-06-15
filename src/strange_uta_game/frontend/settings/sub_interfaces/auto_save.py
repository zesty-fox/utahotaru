"""自动保存子页面。"""

from __future__ import annotations

from qfluentwidgets import FluentIcon as FIF, SettingCardGroup

from ..cards import SpinSettingCard, SwitchSettingCard
from .base import SubSettingInterface


class AutoSaveSubInterface(SubSettingInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        tr = self.tr
        g = SettingCardGroup(tr("自动保存"), self.scrollWidget)
        self._tr_register(g, title_source="自动保存")
        self.card_auto_save_enabled = SwitchSettingCard(FIF.SAVE, tr("启用定时自动保存"),
            tr("定时将项目保存为临时文件，防止闪退丢失数据"), parent=g)
        self._tr_register(self.card_auto_save_enabled,
            title_source="启用定时自动保存",
            content_source="定时将项目保存为临时文件，防止闪退丢失数据")
        self.card_auto_save_interval = SpinSettingCard(FIF.HISTORY, tr("自动保存间隔"),
            tr("每隔多少分钟自动保存一次（1~60分钟）"),
            min_val=1, max_val=60, step=1, suffix=tr(" 分钟"), parent=g)
        self._tr_register(self.card_auto_save_interval,
            title_source="自动保存间隔",
            content_source="每隔多少分钟自动保存一次（1~60分钟）",
            suffix_source=" 分钟")
        g.addSettingCard(self.card_auto_save_enabled)
        g.addSettingCard(self.card_auto_save_interval)
        self.expandLayout.addWidget(g)

    def connect_signals(self):
        self.card_auto_save_enabled.checked_changed.connect(self._notify_changed)
        self.card_auto_save_interval.value_changed.connect(self._notify_changed)

    def load_settings(self, s):
        self.card_auto_save_enabled.setChecked(s.get("auto_save.enabled", True))
        self.card_auto_save_interval.setValue(s.get("auto_save.interval_minutes", 5))

    def collect_settings(self, s):
        s.set("auto_save.enabled", self.card_auto_save_enabled.isChecked())
        s.set("auto_save.interval_minutes", self.card_auto_save_interval.value())
