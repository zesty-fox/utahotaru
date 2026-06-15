"""设置子页面基类。

每个 SubSettingInterface 负责：
  1. 创建自己的 UI 控件（_init_ui）
  2. 将 UI 控件的变更信号连接到自己的 _on_any_changed（_connect_signals）
  3. 从 AppSettings 读取初始值写入 UI（load_settings）
  4. 从 UI 读取当前值写回 AppSettings（collect_settings）

SettingsInterface（外层）负责：
  - 在 preload 阶段依次调用各子页面的 load_settings
  - 在需要保存时调用各子页面的 collect_settings，然后 settings.save() + notify
  - 把"有值变化"事件从子页面冒泡到 SettingsInterface._schedule_auto_save
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ExpandLayout, ScrollArea


class SubSettingInterface(ScrollArea):
    """设置子页面基类。

    子类实现：
        _init_ui(self)          — 创建控件并加入 expandLayout
        connect_signals(self)   — 把各控件的变更信号连接到 _notify_changed
        load_settings(self, s)  — 从 AppSettings s 读取值填写 UI
        collect_settings(self, s) — 从 UI 读取值写入 AppSettings s
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._change_callback: Optional[Callable] = None
        self._silent_save_callback: Optional[Callable[[str, Any], None]] = None

        # 精准 retranslate 注册表。每项 (widget, title_src, content_src, suffix_src)。
        # 子类在 _init_ui 内调用 _tr_register/_tr_register_text 登记需要随语言刷新
        # 的控件；_rebuild_for_language_change 直接遍历这张表 setText/setSuffix，
        # 不再 setWidget 替换 scrollWidget（详见 about.py 上踩的坑）。
        self._tr_registry: list = []
        self._tr_text_registry: list = []

        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("subSettingInterface")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 断开 autoFillBackground 对系统 QPalette 的依赖
        self.viewport().setAutoFillBackground(False)
        self.scrollWidget.setAutoFillBackground(False)

        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(20, 20, 20, 20)

    def set_change_callback(self, cb: Callable) -> None:
        """由 SettingsInterface 注入，有设置变更时调用。"""
        self._change_callback = cb

    def set_silent_save_callback(self, cb: Callable[[str, Any], None]) -> None:
        """由 SettingsInterface 注入：把单个 key 静默写入 AppSettings 并落盘，
        不触发 settings_changed / store.notify("settings") cascade。

        用于"只在导出/导入时才被消费、改完不影响任何运行时状态"的设置项
        （如 ``export.software_compensation_ms``），避免每次微调都跑一遍
        timing_interface._apply_settings 全量重应用。
        """
        self._silent_save_callback = cb

    def _notify_changed(self, *_args) -> None:
        """控件变更时通知外层触发自动保存。"""
        if self._change_callback is not None:
            self._change_callback()

    def _silent_save(self, path: str, value: Any) -> None:
        """直接写 ``path → value`` 到 AppSettings 并落盘，不触发 cascade。"""
        if self._silent_save_callback is not None:
            self._silent_save_callback(path, value)

    # ── 子类必须实现的接口 ──────────────────────────────────────────

    def connect_signals(self) -> None:
        """把各控件的变更信号连到 self._notify_changed。子类实现。"""

    def load_settings(self, settings) -> None:
        """从 AppSettings 读取值填写 UI 控件。子类实现。"""

    def collect_settings(self, settings) -> None:
        """从 UI 控件读取值写入 AppSettings。子类实现。"""

    # ── 精准 retranslate 注册 API ───────────────────────────────────

    def _tr_register(
        self,
        widget,
        title_source: Optional[str] = None,
        content_source: Optional[str] = None,
        suffix_source: Optional[str] = None,
    ):
        """登记一个 SettingCard/SettingCardGroup，便于语言切换时刷新文本。

        ``title_source``/``content_source`` 是**未翻译**的源字符串——切语言时
        基类自动 ``self.tr(...)`` 重新翻译并 ``setText``；构造控件时仍需
        显式传入 ``self.tr(...)`` 后的值（保证首次渲染就正确）。

        Args:
            widget: 必须暴露 ``titleLabel`` / ``contentLabel`` 之一；带
                ``spin`` 子控件（``SpinSettingCard``）可附带 ``suffix_source``。
        """
        self._tr_registry.append((widget, title_source, content_source, suffix_source))
        return widget

    def _tr_register_text(self, widget, attr: str, source: str):
        """登记普通文本控件：(widget, attr_name, source) → ``setattr`` 风格回放。

        - ``attr`` 通常是 ``"setText"`` / ``"setPlaceholderText"`` /
          ``"setToolTip"``，即在 widget 上调用 ``getattr(widget, attr)(tr(source))``。
        """
        self._tr_text_registry.append((widget, attr, source))
        return widget

    # ── 热更新：Qt 自动派发 LanguageChange 时刷新本子页面 ──────────

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._rebuild_for_language_change()
        super().changeEvent(event)

    def _rebuild_for_language_change(self) -> None:
        """默认精准 retranslate：遍历两张注册表 setText/setSuffix。

        之前用 ``setWidget(new_scrollWidget)`` 整张拆掉重建：在 about 页会
        丢失「关于」组和重置按钮（疑似 ExpandLayout 中途 addWidget 与析构
        顺序冲突）。改成精准刷新——子类负责在 ``_init_ui`` 内把要刷新的
        控件 ``_tr_register`` 登记一遍即可。
        """
        for widget, title_src, content_src, suffix_src in self._tr_registry:
            try:
                if title_src is not None and hasattr(widget, "titleLabel"):
                    widget.titleLabel.setText(self.tr(title_src))
                if content_src is not None and hasattr(widget, "contentLabel"):
                    widget.contentLabel.setText(self.tr(content_src))
                if suffix_src is not None and hasattr(widget, "spin"):
                    widget.spin.setSuffix(self.tr(suffix_src))
            except Exception:
                pass
        for widget, attr, source in self._tr_text_registry:
            try:
                getattr(widget, attr)(self.tr(source))
            except Exception:
                pass
