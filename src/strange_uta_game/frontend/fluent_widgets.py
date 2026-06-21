"""Fluent 风格的通用控件 / 对话框封装。

集中存放用于替换原生 Qt 控件的 qfluentwidgets 封装，使其在深色模式下
（尤其 Win10）也能被 qfluentwidgets 主题正确接管，不再退化为系统原生外观。

- ``FluentGroupBox``：替代原生 ``QGroupBox``（qfluentwidgets 无 GroupBox，
  这里用受主题管理的 ``SimpleCardWidget`` + 标题实现）。
- ``message_info`` / ``message_warning`` / ``message_error`` / ``message_question``：
  替代 ``QMessageBox`` 的常见用法，内部使用 qfluentwidgets ``MessageBox``。
"""

from __future__ import annotations

from typing import Optional

from typing import Sequence

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    StrongBodyLabel,
)


class FluentMessageBox(MessageBox):
    """qfluentwidgets ``MessageBox`` 的定位修正版。

    qfluentwidgets 的 ``MaskDialogBase`` 在 ``__init__`` 里把遮罩固定为
    ``setGeometry(0, 0, parent.width(), parent.height())`` —— 即钉在**主屏原点**、
    大小取父窗口大小。仅当父窗口恰好最大化在主屏 (0,0) 时才正好覆盖；只要父窗口
    不在原点（**嵌入式下 SUG 是宿主里的子面板、宿主窗口通常不在原点**，或
    standalone 下窗口非最大化），遮罩就会跑到主屏左上角与可见区域错位：用户看不到
    对话框，点击落到被模态屏蔽的窗口上只听到系统禁止音。

    本类在显示时把遮罩重新定位/缩放到锚点窗口的**实际全局矩形**，使遮罩与对话框
    始终覆盖正确的窗口，standalone 与 embedded 两种模式下行为一致。
    """

    def __init__(self, title: str, content: str, parent: Optional[QWidget] = None):
        super().__init__(title, content, parent)
        # 锚点：父级所在的顶层窗口（_resolve_window 已把 parent 解析为窗口，
        # 这里 .window() 多为其自身；对子控件也能正确上溯）。
        self._anchorWindow = parent.window() if parent is not None else None

    def _reposition_over_anchor(self) -> None:
        win = self._anchorWindow
        if win is None or not win.isVisible():
            return
        top_left = win.mapToGlobal(QPoint(0, 0))
        self.setGeometry(top_left.x(), top_left.y(), win.width(), win.height())
        self.windowMask.resize(self.size())

    def showEvent(self, e):
        self._reposition_over_anchor()
        super().showEvent(e)


def make_message_box(
    parent: Optional[QWidget], title: str, content: str
) -> FluentMessageBox:
    """构建定位修正后的 Fluent 消息对话框（供各 message_* 封装与 winrt 引导复用）。"""
    return FluentMessageBox(title, content, _resolve_window(parent))


class FluentGroupBox(SimpleCardWidget):
    """受 qfluentwidgets 主题管理的"分组框"，替代原生 ``QGroupBox``。

    qfluentwidgets 不提供 GroupBox，而原生 QGroupBox 在 Win10 深色模式下标题
    会渲染为黑字、边框不跟随主题。``SimpleCardWidget`` 是受主题管理的卡片容器，
    深/浅色自动切换。本类在卡片顶部加一个标题标签，并暴露 ``contentLayout``
    供调用方添加内容。

    迁移方式：把
        gb = QGroupBox(title, parent)
        lay = QVBoxLayout(gb)
    改为
        gb = FluentGroupBox(title, parent)
        lay = gb.contentLayout
    其余 ``lay.addWidget(...)`` 调用保持不变。
    """

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rootLayout = QVBoxLayout(self)
        self._rootLayout.setContentsMargins(14, 10, 14, 12)
        self._rootLayout.setSpacing(8)

        self._titleLabel = StrongBodyLabel(title, self)
        self._rootLayout.addWidget(self._titleLabel)
        if not title:
            self._titleLabel.hide()

        # 内容布局：调用方往这里加控件（替代原 QVBoxLayout(group_box)）
        self.contentLayout = QVBoxLayout()
        self.contentLayout.setContentsMargins(0, 0, 0, 0)
        self.contentLayout.setSpacing(6)
        self._rootLayout.addLayout(self.contentLayout)

    def setTitle(self, text: str) -> None:
        self._titleLabel.setText(text)
        self._titleLabel.setVisible(bool(text))

    def title(self) -> str:
        return self._titleLabel.text()


def dialog_button_row(
    dialog: QDialog,
    *,
    ok_text: str = "确定",
    cancel_text: str = "取消",
) -> tuple[QLayout, PrimaryPushButton, PushButton]:
    """构建一行 Fluent 的"确定/取消"按钮，替代原生 ``QDialogButtonBox``。

    原生 QDialogButtonBox 内部是原生 QPushButton，在 Win10 深色模式下不跟随
    主题；改用 qfluentwidgets ``PrimaryPushButton`` / ``PushButton`` 受主题管理。

    Returns:
        (按钮行布局, 确定按钮, 取消按钮)。确定/取消已分别连到
        ``dialog.accept`` / ``dialog.reject``，调用方把布局加入对话框即可。
    """
    row = QHBoxLayout()
    row.addStretch(1)
    ok_btn = PrimaryPushButton(ok_text)
    cancel_btn = PushButton(cancel_text)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)
    row.addWidget(ok_btn)
    row.addWidget(cancel_btn)
    return row, ok_btn, cancel_btn


def _resolve_window(parent: Optional[QWidget]) -> Optional[QWidget]:
    """把传入的父控件解析为其顶层窗口。

    qfluentwidgets ``MessageBox`` 是遮罩式对话框，会遮住传入的父级，且**要求
    parent 非 None**（构造时会访问 ``parent.width()``）。这里：
    1. 优先返回传入控件的顶层窗口（遮罩覆盖整窗、居中显示）；
    2. parent 为 None 或无有效窗口时，回退到当前活动窗口 / 首个可见顶层窗口，
       避免 ``QMessageBox(None)`` 旧用法迁移后因 None parent 崩溃。
    """
    if parent is not None:
        try:
            win = parent.window()
            if win is not None:
                return win
        except Exception:
            pass

    app = QApplication.instance()
    if app is not None:
        active = app.activeWindow()
        if active is not None:
            return active
        for w in app.topLevelWidgets():
            if w.isVisible():
                return w
    return parent


def message_info(
    parent: Optional[QWidget],
    title: str,
    content: str,
    *,
    ok_text: str = "确定",
    copyable: bool = False,
) -> None:
    """信息提示（单个"确定"按钮）。替代 ``QMessageBox.information``。"""
    w = make_message_box(parent, title, content)
    w.yesButton.setText(ok_text)
    w.hideCancelButton()
    if copyable:
        w.setContentCopyable(True)
    w.exec()


# Fluent MessageBox 无 information/warning/critical 图标区分，三者外观一致；
# 保留独立函数名以表达语义并便于将来差异化。
message_warning = message_info
message_error = message_info


def message_question(
    parent: Optional[QWidget],
    title: str,
    content: str,
    *,
    yes_text: str = "确定",
    no_text: str = "取消",
    default_cancel: bool = False,
    copyable: bool = False,
) -> bool:
    """是/否确认。替代 ``QMessageBox.question``。

    Args:
        default_cancel: True 时把焦点放在"取消"按钮（用于删除等危险操作，
            避免回车误触确定）。

    Returns:
        True 表示用户点击了"是/确定"，False 表示取消或关闭。
    """
    w = make_message_box(parent, title, content)
    w.yesButton.setText(yes_text)
    w.cancelButton.setText(no_text)
    if copyable:
        w.setContentCopyable(True)
    if default_cancel:
        w.cancelButton.setFocus()
    return bool(w.exec())


def message_choice(
    parent: Optional[QWidget],
    title: str,
    content: str,
    buttons: Sequence[str],
    *,
    default: int = 0,
) -> int:
    """多选项（≥3 个按钮）对话框。替代带多个 ``addButton`` 的 ``QMessageBox``。

    第一个按钮使用主按钮样式；最后一个按钮作为取消/次要按钮。点击任意按钮都会
    关闭对话框。

    Args:
        buttons: 按钮文案列表（按显示顺序）。
        default: 默认获得焦点的按钮索引。

    Returns:
        被点击按钮的索引；若通过遮罩/Esc 关闭而未点击任何按钮，返回 -1。
    """
    w = make_message_box(parent, title, content)
    state = {"index": -1}

    def _pick(idx: int) -> None:
        state["index"] = idx

    ordered: list = [w.yesButton]
    w.yesButton.setText(buttons[0])
    w.yesButton.clicked.connect(lambda: _pick(0))

    # 中间按钮：插入到取消按钮之前，保持顺序
    for i in range(1, len(buttons) - 1):
        btn = PushButton(buttons[i], w.buttonGroup)
        btn.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        btn.clicked.connect(lambda _=False, idx=i: (_pick(idx), w.accept()))
        w.buttonLayout.insertWidget(
            w.buttonLayout.count() - 1, btn, 1, Qt.AlignmentFlag.AlignVCenter
        )
        ordered.append(btn)

    last = len(buttons) - 1
    w.cancelButton.setText(buttons[last])
    # cancelButton 基类已连 reject；这里仅追加记录索引（同步执行，先后无碍）
    w.cancelButton.clicked.connect(lambda: _pick(last))
    ordered.append(w.cancelButton)

    if 0 <= default < len(ordered):
        ordered[default].setFocus()

    w.exec()
    return state["index"]


def message_busy(
    parent: Optional[QWidget],
    title: str,
    content: str,
) -> FluentMessageBox:
    """构建一个无按钮的"忙碌/请稍候"遮罩对话框（不在此处 exec）。

    替代 ``QMessageBox`` + ``setStandardButtons(NoButton)`` 的用法：调用方拿到
    返回的对话框后自行 ``exec()`` 阻塞，并在后台完成时调用其 ``accept()`` 关闭。
    """
    w = make_message_box(parent, title, content)
    w.hideYesButton()
    w.hideCancelButton()
    return w
