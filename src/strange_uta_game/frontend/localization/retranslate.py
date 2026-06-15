"""热更新辅助：清空 widget 的 layout 以便 _init_ui 再跑一遍。

典型使用模式：

.. code-block:: python

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            detach_layout_for_rebuild(self)
            self._init_ui()
        super().changeEvent(event)

要求 ``_init_ui`` 在被调用时假定 widget 还没有 layout（典型 ``QVBoxLayout(self)``
开头）。``detach_layout_for_rebuild`` 把旧 layout 连同里面所有 widget 一并
拆掉、转移到临时弃用 widget，让旧 layout 被 Qt 回收掉，本 widget 回到
"无 layout"状态。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLayout, QWidget


def detach_layout_for_rebuild(widget: QWidget) -> None:
    """清空 widget 的 layout，准备 _init_ui 重新构建。

    Qt 不允许给 widget 重设 layout（``setLayout`` 在已有 layout 时是 no-op
    并打 warning）。变通做法：先把 layout 里所有 child widget 拆掉
    （setParent(None) + deleteLater 异步回收），再把空 layout 转移到一个
    throwaway QWidget，本 widget 就回到无 layout 状态，后续 _init_ui 里
    ``QVBoxLayout(self)`` 等就能正常工作。
    """
    layout = widget.layout()
    if layout is None:
        return
    _clear_layout_recursive(layout)
    # 把已空的旧 layout 转移到弃用 widget——本 widget 释放 layout 所有权
    QWidget().setLayout(layout)


def _clear_layout_recursive(layout: QLayout) -> None:
    """递归清空 layout 内所有 widget + 子 layout，全部 deleteLater。"""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        sub = item.layout()
        if sub is not None:
            _clear_layout_recursive(sub)
