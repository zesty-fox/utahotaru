"""打轴设定 + Offset校准子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from qfluentwidgets import FluentIcon as FIF, PushButton, SettingCard, SettingCardGroup

from ..calibration_dialog import CalibrationDialog
from ..cards import ComboSettingCard, SpinSettingCard, SwitchSettingCard
from .base import SubSettingInterface


class TimingSubInterface(SubSettingInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._calibration_dialog = None
        self._init_ui()

    def _init_ui(self):
        tr = self.tr
        # 打轴设定
        g = SettingCardGroup(tr("打轴设定"), self.scrollWidget)
        self._tr_register(g, title_source="打轴设定")
        self.card_offset = self._tr_register(
            SpinSettingCard(FIF.DATE_TIME, tr("按键补偿"),
                tr("建议用下方的offset校正来矫正，用于设备引起的反应延迟（负值=提前，正值=延后）"),
                min_val=-5000, max_val=5000, step=10, suffix=" ms", parent=g),
            title_source="按键补偿",
            content_source="建议用下方的offset校正来矫正，用于设备引起的反应延迟（负值=提前，正值=延后）")
        self.card_speed_correction = self._tr_register(
            SpinSettingCard(FIF.SPEED_MEDIUM, tr("速度补正"),
                tr("打轴时间戳的速度修正系数"),
                min_val=50, max_val=200, step=5, suffix=" %", parent=g),
            title_source="速度补正", content_source="打轴时间戳的速度修正系数")
        self.card_export_offset = self._tr_register(
            SpinSettingCard(FIF.HISTORY, tr("全局偏移"),
                tr("全局偏移，用于控制本软件内整体轴时间偏移（毫秒），（负值=提前，正值=延后）"),
                min_val=-5000, max_val=5000, step=10, suffix=" ms", parent=g),
            title_source="全局偏移",
            content_source="全局偏移，用于控制本软件内整体轴时间偏移（毫秒），（负值=提前，正值=延后）")
        self.card_timing_step = self._tr_register(
            SpinSettingCard(FIF.UP, tr("微调时间戳步长"),
                tr("Alt+↑/Alt+↓ 微调选中节奏点时间戳的步长"),
                min_val=1, max_val=500, step=1, suffix=" ms", parent=g),
            title_source="微调时间戳步长",
            content_source="Alt+↑/Alt+↓ 微调选中节奏点时间戳的步长")
        self.card_disable_click_jump = self._tr_register(
            SwitchSettingCard(FIF.CLOSE, tr("禁用单击跳转"),
                tr("关闭单击字符/节奏点延迟后跳转到目标行的功能（双击跳转不受影响）"), parent=g),
            title_source="禁用单击跳转",
            content_source="关闭单击字符/节奏点延迟后跳转到目标行的功能（双击跳转不受影响）")
        self.card_preview_guide = self._tr_register(
            SwitchSettingCard(FIF.VIEW, tr("打轴预览指引"),
                tr("打轴播放时在当前行以光标为锚用过渡色提示：上一个打的字(80%) / 正在打的字(50%) / 下一个要打的字(20%)"), parent=g),
            title_source="打轴预览指引",
            content_source="打轴播放时在当前行以光标为锚用过渡色提示：上一个打的字(80%) / 正在打的字(50%) / 下一个要打的字(20%)")
        self.card_keysound = self._tr_register(
            SwitchSettingCard(FIF.MUSIC, tr("按键音"),
                tr("打轴时按下按键播放按下音、抬起句尾按键播放抬起音"), parent=g),
            title_source="按键音", content_source="打轴时按下按键播放按下音、抬起句尾按键播放抬起音")
        self.card_keysound_volume = self._tr_register(
            SpinSettingCard(FIF.VOLUME, tr("按键音音量"),
                tr("按键音的播放音量（100 = 原始音量）"),
                min_val=0, max_val=200, step=5, suffix=" %", parent=g),
            title_source="按键音音量", content_source="按键音的播放音量（100 = 原始音量）")
        self.card_keysound_style = self._tr_register(
            ComboSettingCard(FIF.PALETTE, tr("按键音风格"),
                tr("选择按键音音效风格"),
                items=[tr("默认"), "osu", tr("街机风"), tr("金属感")], parent=g),
            title_source="按键音风格", content_source="选择按键音音效风格")
        for c in [self.card_offset, self.card_speed_correction, self.card_export_offset,
                  self.card_timing_step, self.card_disable_click_jump, self.card_preview_guide,
                  self.card_keysound, self.card_keysound_volume, self.card_keysound_style]:
            g.addSettingCard(c)
        self.expandLayout.addWidget(g)

        # Offset 校准
        cg = SettingCardGroup(tr("Offset 校准"), self.scrollWidget)
        self._tr_register(cg, title_source="Offset 校准")
        cal_card = self._tr_register(
            SettingCard(FIF.SPEED_HIGH, tr("节拍器校准"),
                tr("打开校准弹窗，跟随节拍器按空格键测量 Offset"), cg),
            title_source="节拍器校准",
            content_source="打开校准弹窗，跟随节拍器按空格键测量 Offset")
        self.btn_cal_open = PushButton(tr("开始校准"), cal_card)
        self._tr_register_text(self.btn_cal_open, "setText", "开始校准")
        self.btn_cal_open.setFont(QFont("Microsoft YaHei", 10))
        self.btn_cal_open.clicked.connect(self._open_calibration_dialog)
        cal_card.hBoxLayout.addWidget(self.btn_cal_open, 0, Qt.AlignmentFlag.AlignRight)
        cal_card.hBoxLayout.addSpacing(16)
        cg.addSettingCard(cal_card)
        self.expandLayout.addWidget(cg)

    def _open_calibration_dialog(self):
        self._calibration_dialog = CalibrationDialog(self)
        self._calibration_dialog.exec()
        if self._calibration_dialog is not None:
            self._calibration_dialog._stop_metronome()
        self._calibration_dialog = None

    def close_calibration(self):
        if self._calibration_dialog is not None:
            self._calibration_dialog.close()
            self._calibration_dialog = None

    def connect_signals(self):
        self.card_offset.value_changed.connect(self._notify_changed)
        self.card_speed_correction.value_changed.connect(self._notify_changed)
        self.card_export_offset.value_changed.connect(self._notify_changed)
        self.card_timing_step.value_changed.connect(self._notify_changed)
        self.card_disable_click_jump.checked_changed.connect(self._notify_changed)
        self.card_preview_guide.checked_changed.connect(self._notify_changed)
        self.card_keysound.checked_changed.connect(self._notify_changed)
        self.card_keysound_volume.value_changed.connect(self._notify_changed)
        self.card_keysound_style.index_changed.connect(self._notify_changed)

    _STYLE_KEYS = ["default", "osu", "arcade", "sci"]

    def load_settings(self, s):
        self.card_offset.setValue(s.get("timing.tag_offset_ms", -230))
        self.card_speed_correction.setValue(s.get("timing.speed_correction", 80))
        self.card_export_offset.setValue(s.get("export.offset_ms", 0))
        self.card_timing_step.setValue(s.get("timing.timing_adjust_step_ms", 10))
        self.card_disable_click_jump.setChecked(s.get("timing.disable_click_jump", False))
        self.card_preview_guide.setChecked(s.get("timing.preview_guide_enabled", False))
        self.card_keysound.setChecked(s.get("timing.keysound_enabled", True))
        self.card_keysound_volume.setValue(s.get("timing.keysound_volume", 100))
        style = s.get("timing.keysound_style", "default")
        idx = self._STYLE_KEYS.index(style) if style in self._STYLE_KEYS else 0
        self.card_keysound_style.setCurrentIndex(idx)

    def collect_settings(self, s):
        s.set("timing.tag_offset_ms", self.card_offset.value())
        s.set("timing.speed_correction", self.card_speed_correction.value())
        s.set("export.offset_ms", self.card_export_offset.value())
        s.set("timing.timing_adjust_step_ms", self.card_timing_step.value())
        s.set("timing.disable_click_jump", self.card_disable_click_jump.isChecked())
        s.set("timing.preview_guide_enabled", self.card_preview_guide.isChecked())
        s.set("timing.keysound_enabled", self.card_keysound.isChecked())
        s.set("timing.keysound_volume", self.card_keysound_volume.value())
        idx = self.card_keysound_style.currentIndex()
        s.set("timing.keysound_style", self._STYLE_KEYS[idx] if idx < len(self._STYLE_KEYS) else "default")
