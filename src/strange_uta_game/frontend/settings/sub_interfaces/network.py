"""网络代理 + 应用更新子页面。

控件完全由 updater.ui.attach_proxy_group / attach_update_group 注入，
本页面自身不预留任何占位 SettingCardGroup。
注入函数要求 parent 提供：
  - parent.expandLayout
  - parent.scrollWidget
  - parent.get_settings()
"""

from __future__ import annotations

from .base import SubSettingInterface


class NetworkSubInterface(SubSettingInterface):
    """网络代理 + 应用更新设置页（内容由 updater 模块注入）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_ref = None
        self._updater_attached = False

    def get_settings(self):
        """供 updater 的 attach_* 函数调用。"""
        return self._settings_ref

    def attach_updater_ui(self, settings) -> None:
        """注入 updater UI（只执行一次）。"""
        if self._updater_attached:
            return
        self._settings_ref = settings
        self._updater_attached = True
        if getattr(settings, "_provider", None) is not None:
            return
        try:
            from strange_uta_game.updater.ui import attach_proxy_group, attach_update_group
            attach_proxy_group(self)
            attach_update_group(self)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("加载 updater UI 失败，已忽略", exc_info=True)

    def _rebuild_for_language_change(self) -> None:
        # 默认基类实现按 _tr_registry 走 self.tr，但 updater UI 的源
        # 字符串归在 UpdaterUI 上下文，self.tr 拿不到。手动用 _tr。
        super()._rebuild_for_language_change()
        from strange_uta_game.updater.ui.proxy_card import _tr as _updater_tr
        for attr, src in (("proxy_group", "网络与代理（更新源）"),
                          ("update_group", "应用更新")):
            group = getattr(self, attr, None)
            if group is None:
                continue
            try:
                group.titleLabel.setText(_updater_tr(src))
            except Exception:
                pass

    # load/collect/connect 由 updater 自己负责，这里是空实现
    def connect_signals(self):
        pass

    def load_settings(self, s):
        self._settings_ref = s

    def collect_settings(self, s):
        pass
