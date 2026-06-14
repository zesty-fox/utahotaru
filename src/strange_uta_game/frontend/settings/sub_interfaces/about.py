"""关于子页面。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QMessageBox, QWidget
from qfluentwidgets import (
    FluentIcon as FIF,
    InfoBar, InfoBarPosition,
    PrimaryPushButton, PushButton,
    SettingCard, SettingCardGroup,
)

from strange_uta_game.__version__ import __version__ as _app_version
from strange_uta_game.frontend.localization import (
    AVAILABLE_LANGUAGES,
    DEFAULT_LANGUAGE,
    localization,
)
from ..cards import ComboSettingCard
from .base import SubSettingInterface


class AboutSubInterface(SubSettingInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_ref = None
        self._init_ui()

    def _init_ui(self):
        # ── 语言设置 ────────────────────────────────────────────
        # 当前仅注册简体中文 (zh_CN)；之后 EN/JA 翻译完成后扩展
        # AVAILABLE_LANGUAGES 即可，本卡片自动出现新选项。
        self.language_group = SettingCardGroup(self.tr("语言"), self.scrollWidget)
        self._language_codes = [lang.code for lang in AVAILABLE_LANGUAGES]
        self._language_card = ComboSettingCard(
            FIF.LANGUAGE,
            self.tr("界面语言"),
            self.tr("切换 UI 显示语言，更改后需重启软件生效"),
            [lang.native_name for lang in AVAILABLE_LANGUAGES],
            self.language_group,
        )
        self.language_group.addSettingCard(self._language_card)
        self.expandLayout.addWidget(self.language_group)

        self.about_group = SettingCardGroup(self.tr("关于"), self.scrollWidget)

        about_card = SettingCard(FIF.INFO, "StrangeUtaGame - 歌词打轴软件",
            f"版本 v{_app_version}  |  由 RhythmicaLyrics 启发", self.about_group)
        self.about_group.addSettingCard(about_card)

        link_card = SettingCard(FIF.GITHUB, "GitHub",
            "https://github.com/karaoke-studio/StrangeUtaGame", self.about_group)
        self.about_group.addSettingCard(link_card)

        self._path_card = SettingCard(FIF.FOLDER, "配置文件位置", "（未加载）", self.about_group)
        btn_open = PushButton("打开目录", self._path_card)
        btn_open.setFont(QFont("Microsoft YaHei", 10))
        btn_open.clicked.connect(self._open_config_dir)
        btn_change = PushButton("更改位置", self._path_card)
        btn_change.setFont(QFont("Microsoft YaHei", 10))
        btn_change.clicked.connect(self._change_config_dir)
        self._path_card.hBoxLayout.addWidget(btn_open, 0, Qt.AlignmentFlag.AlignRight)
        self._path_card.hBoxLayout.addWidget(btn_change, 0, Qt.AlignmentFlag.AlignRight)
        self._path_card.hBoxLayout.addSpacing(16)
        self.about_group.addSettingCard(self._path_card)

        # FFmpeg 路径设置卡
        self.tools_group = SettingCardGroup("工具配置", self.scrollWidget)
        self._ffmpeg_card = SettingCard(
            FIF.MOVIE, "FFmpeg 路径",
            "用于加载视频文件时提取音频（留空则使用系统环境变量）",
            self.tools_group,
        )
        self._ffmpeg_path_label = PushButton("（使用环境变量）", self._ffmpeg_card)
        self._ffmpeg_path_label.setFont(QFont("Microsoft YaHei", 9))
        self._ffmpeg_path_label.setEnabled(False)
        self._ffmpeg_path_label.setMaximumWidth(260)
        btn_browse_ffmpeg = PushButton("浏览", self._ffmpeg_card)
        btn_browse_ffmpeg.setFont(QFont("Microsoft YaHei", 10))
        btn_browse_ffmpeg.clicked.connect(self._browse_ffmpeg)
        btn_clear_ffmpeg = PushButton("清除", self._ffmpeg_card)
        btn_clear_ffmpeg.setFont(QFont("Microsoft YaHei", 10))
        btn_clear_ffmpeg.clicked.connect(self._clear_ffmpeg_path)
        self._ffmpeg_card.hBoxLayout.addWidget(self._ffmpeg_path_label, 0, Qt.AlignmentFlag.AlignRight)
        self._ffmpeg_card.hBoxLayout.addWidget(btn_browse_ffmpeg, 0, Qt.AlignmentFlag.AlignRight)
        self._ffmpeg_card.hBoxLayout.addWidget(btn_clear_ffmpeg, 0, Qt.AlignmentFlag.AlignRight)
        if sys.platform == "win32":
            self._btn_install_ffmpeg = PrimaryPushButton("一键安装", self._ffmpeg_card)
            self._btn_install_ffmpeg.setFont(QFont("Microsoft YaHei", 10))
            self._btn_install_ffmpeg.clicked.connect(self._install_ffmpeg)
            self._ffmpeg_card.hBoxLayout.addWidget(self._btn_install_ffmpeg, 0, Qt.AlignmentFlag.AlignRight)
        self._ffmpeg_card.hBoxLayout.addSpacing(16)
        self.tools_group.addSettingCard(self._ffmpeg_card)
        self.expandLayout.addWidget(self.about_group)
        self.expandLayout.addWidget(self.tools_group)

        # 保存/重置按钮
        btn_widget = QWidget(self.scrollWidget)
        btn_widget.setMinimumHeight(60)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 10, 0, 24)
        self.btn_save = PrimaryPushButton("保存设置", btn_widget)
        self.btn_save.setIcon(FIF.SAVE)
        self.btn_save.setMinimumHeight(36)
        self.btn_save.hide()
        self.btn_reset = PushButton("重置为默认设置", btn_widget)
        self.btn_reset.setIcon(FIF.DELETE)
        self.btn_reset.setMinimumHeight(36)
        # btn_save 保留属性供外层 signal 连接，但不在 UI 中显示
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        self.expandLayout.addWidget(btn_widget)

    def connect_signals(self):
        # 语言切换由本子页面自己处理（即时落盘 + 重启提示），不冒泡到外层
        # "保存设置" 流程——避免与其它即时生效的设置混在同一个 dirty 事务里。
        self._language_card.index_changed.connect(self._on_language_changed)
        # 其它按钮回调由外层连接

    def load_settings(self, s):
        self._settings_ref = s
        embedded = getattr(s, "_provider", None) is not None

        # ── 语言卡：embedded 下隐藏（语言归宿主独占，与主题同理，见 EMBEDDING.md §5）
        # standalone 下同步当前选项；embedded 下完全不显示，避免与宿主语言冲突。
        self.language_group.setVisible(not embedded)
        if not embedded:
            current_code = s.get("ui.language", DEFAULT_LANGUAGE.code)
            try:
                idx = self._language_codes.index(current_code)
            except ValueError:
                idx = 0
            # blockSignals 防止 load 阶段误触发"语言改变"提示
            self._language_card.combo.blockSignals(True)
            self._language_card.setCurrentIndex(idx)
            self._language_card.combo.blockSignals(False)
        # embedded 模式下配置走宿主存储，没有"配置文件目录"概念：
        # 隐藏整张「配置文件位置」卡片，并避免 setContent(str(None)) 显示 "None"。
        self._path_card.setVisible(not embedded)
        if not embedded:
            self._path_card.setContent(str(s._config_path))
        self.tools_group.setVisible(not embedded)
        ffmpeg_path = s.get("tools.ffmpeg_path", "")
        self._update_ffmpeg_label(ffmpeg_path)

    def collect_settings(self, s):
        pass  # 关于页的 FFmpeg 路径与语言均在切换时即时保存，无需在此收集

    def _on_language_changed(self, idx: int):
        if self._settings_ref is None:
            return
        # embedded 下卡片本应隐藏，但万一别处程序化触发了 index_changed，
        # 仍然直接返回——SUG 在 embedded 下绝不写自己的语言或调 translator。
        if getattr(self._settings_ref, "_provider", None) is not None:
            return
        if not (0 <= idx < len(self._language_codes)):
            return
        new_code = self._language_codes[idx]
        old_code = self._settings_ref.get("ui.language", DEFAULT_LANGUAGE.code)
        if new_code == old_code:
            return

        # 即时落盘（绕过外层 dirty 事务）
        self._settings_ref.set("ui.language", new_code)
        self._settings_ref.save()
        # 立刻安装新 translator——之后任何 _new_ tr() 调用会走新语言。
        # 但 Qt 的 setText(self.tr(...)) 在调用时就把翻译"烧"进了 widget；
        # 现有标签不会自动刷新。要真正生效必须重启进程或对每个 widget 实现
        # changeEvent(LanguageChange)→retranslateUi 的样板（工作量巨大）。
        # 务实做法：问用户是否立即重启进程（QProcess.startDetached 复用
        # 同一 argv，新进程读 ui.language 起来就是新语言）。
        localization.apply_language(new_code)

        msg = QMessageBox(self.window())
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(self.tr("语言已切换"))
        msg.setText(self.tr(
            "语言设置已保存。需要重启软件以完整应用新语言。\n是否立即重启？"
        ))
        btn_now = msg.addButton(self.tr("立即重启"), QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(self.tr("稍后"), QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_now)
        msg.exec()
        if msg.clickedButton() is btn_now:
            self._restart_app()

    def _restart_app(self) -> None:
        """保存脏数据后重启进程。

        - 项目脏 → 走主窗口的 ``flush_unsaved()`` 写崩溃恢复临时文件，重启后
          会被原本的 crash-recovery 流程接住，等同"未保存的临时项目"恢复。
        - 用 ``QProcess.startDetached(executable, argv)`` 启子进程，再
          ``QApplication.quit()`` 退当前进程——子进程读到最新 config 后从新
          语言起来。
        """
        main = self.window()
        try:
            if hasattr(main, "flush_unsaved"):
                main.flush_unsaved()
        except Exception:
            pass

        # 透传当前 sys.argv 给子进程；过滤掉首元素（脚本/exe 路径），由
        # QProcess 自己拼回去。PyInstaller 打包后 sys.executable 就是
        # StrangeUtaGame.exe；dev 模式下是 python.exe + main.py。
        program = sys.executable
        args = list(sys.argv[1:])
        if not sys.executable.endswith((".exe", ".EXE")):
            # dev 模式：python main.py 需要把 main.py 放回 args 首位
            if sys.argv and not sys.argv[0].endswith(".exe"):
                args = [sys.argv[0], *args]

        QProcess.startDetached(program, args)
        QApplication.quit()

    def _open_config_dir(self):
        if self._settings_ref is None or self._settings_ref._config_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._settings_ref._config_path.parent)))

    def _change_config_dir(self):
        if self._settings_ref is None or self._settings_ref._config_path is None:
            return
        s = self._settings_ref
        new_dir = QFileDialog.getExistingDirectory(self, "选择配置文件存储目录", str(s._config_path.parent))
        if not new_dir:
            return

        new_dir_path = Path(new_dir)
        program_dir = Path(sys.argv[0]).resolve().parent
        redirect_file = program_dir / ".config_redirect"

        if new_dir_path.resolve() == program_dir.resolve():
            try:
                if redirect_file.exists():
                    redirect_file.unlink()
            except Exception:
                pass
        else:
            try:
                redirect_file.write_text(str(new_dir_path), encoding="utf-8")
            except Exception as e:
                InfoBar.error(title="更改失败", content=f"无法写入重定向文件: {e}",
                    orient=Qt.Orientation.Horizontal, isClosable=True,
                    position=InfoBarPosition.TOP, duration=5000, parent=self)
                return

        old_path = s._config_path
        new_path = new_dir_path / "config.json"
        if old_path.exists() and old_path != new_path:
            try:
                import shutil
                new_dir_path.mkdir(exist_ok=True)
                shutil.copy2(str(old_path), str(new_path))
                for fname in ("dictionary.json", "network_dictionary.json", "singers.json"):
                    op = old_path.parent / fname
                    np = new_dir_path / fname
                    if op.exists() and op != np:
                        shutil.copy2(str(op), str(np))
            except Exception as e:
                InfoBar.warning(title="配置复制失败", content=f"请手动复制配置文件: {e}",
                    orient=Qt.Orientation.Horizontal, isClosable=True,
                    position=InfoBarPosition.TOP, duration=5000, parent=self)

        s._config_path = new_path
        s._dict_path = new_dir_path / "dictionary.json"
        s._network_dict_path = new_dir_path / "network_dictionary.json"
        s._singers_path = new_dir_path / "singers.json"
        self._path_card.setContent(str(new_path))
        InfoBar.success(title="配置位置已更改", content=f"配置文件将保存到: {new_path}",
            orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=5000, parent=self)

    def _update_ffmpeg_label(self, path: str):
        if path:
            label = Path(path).name
            self._ffmpeg_path_label.setText(label)
            self._ffmpeg_path_label.setToolTip(path)
        else:
            self._ffmpeg_path_label.setText("（使用环境变量）")
            self._ffmpeg_path_label.setToolTip("")

    def _browse_ffmpeg(self):
        if self._settings_ref is not None and getattr(self._settings_ref, "_provider", None) is not None:
            return
        current = ""
        if self._settings_ref:
            current = self._settings_ref.get("tools.ffmpeg_path", "") or ""
        init_dir = str(Path(current).parent) if current else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 FFmpeg 可执行文件", init_dir,
            "可执行文件 (ffmpeg.exe ffmpeg);;所有文件 (*.*)",
        )
        if not path:
            return
        self._save_ffmpeg_path(path)

    def _clear_ffmpeg_path(self):
        if self._settings_ref is not None and getattr(self._settings_ref, "_provider", None) is not None:
            return
        self._save_ffmpeg_path("")

    def _save_ffmpeg_path(self, path: str):
        if self._settings_ref is None:
            return
        if getattr(self._settings_ref, "_provider", None) is not None:
            return
        self._settings_ref.set("tools.ffmpeg_path", path)
        self._settings_ref.save()
        self._update_ffmpeg_label(path)
        if path:
            InfoBar.success(title="FFmpeg 路径已保存", content=path,
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=4000, parent=self)
        else:
            InfoBar.success(title="FFmpeg 路径已清除", content="将使用系统环境变量中的 ffmpeg",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self)

    def _install_ffmpeg(self):
        import ctypes
        # -Command 参数用双引号包裹，内部用单引号，避免转义冲突
        ps_args = (
            "-NoExit -Command \""
            "winget install Gyan.FFmpeg "
            "--accept-package-agreements --accept-source-agreements; "
            "Write-Host ''; "
            "Write-Host '>>> 安装完成，可关闭此窗口。<<<' -ForegroundColor Green; "
            "pause\""
        )
        # ShellExecuteW verb=runas 触发 UAC 提权，返回值 >32 表示成功启动
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell", ps_args, None, 1
        )
        if ret <= 32:
            InfoBar.error(
                title="无法启动安装",
                content=f"ShellExecute 返回 {ret}，请检查是否拒绝了 UAC 提权。",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=6000, parent=self,
            )
            return
        InfoBar.info(
            title="已请求管理员权限启动 FFmpeg 安装",
            content="安装完成后，重启软件即可通过环境变量自动使用，或点击「浏览」手动指定路径。",
            orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=8000, parent=self,
        )
