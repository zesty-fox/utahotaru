"""LocalizationManager —— app 翻译器装载与语言注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QCoreApplication, QLocale, QObject, QTranslator, pyqtSignal


@dataclass(frozen=True)
class Language:
    """注册一种受支持的语言。

    Attributes:
        code: 后台代号，形如 ``"zh_CN"`` / ``"en_US"`` / ``"ja_JP"``。
        native_name: 在 UI 中显示给用户的语言名称（用其本族语写）。
        qlocale_name: 用于构造 :class:`QLocale` 与 ``.qm`` 文件名的字符串。
            通常与 ``code`` 相同；保留单独字段以便未来允许同一显示名
            对应不同 locale 文件。
    """

    code: str
    native_name: str
    qlocale_name: str

    def to_qlocale(self) -> QLocale:
        return QLocale(self.qlocale_name)


#: 受支持的语言列表。EN/JA 翻译就绪后再追加。
AVAILABLE_LANGUAGES: Tuple[Language, ...] = (
    Language(code="zh_CN", native_name="简体中文", qlocale_name="zh_CN"),
    # Language(code="en_US", native_name="English",  qlocale_name="en_US"),
    # Language(code="ja_JP", native_name="日本語",   qlocale_name="ja_JP"),
)


DEFAULT_LANGUAGE: Language = AVAILABLE_LANGUAGES[0]


def language_by_code(code: str) -> Language:
    """根据后台代号查找 Language；未知代号回退到默认。"""
    for lang in AVAILABLE_LANGUAGES:
        if lang.code == code:
            return lang
    return DEFAULT_LANGUAGE


def _translations_dir() -> Path:
    """app 翻译 ``.qm`` 所在目录。"""
    return Path(__file__).resolve().parent / "translations"


class _AppTranslator(QTranslator):
    """加载 ``localization/translations/app.<locale>.qm``。

    源字符串本身就是简体中文，因此 ``zh_CN`` 的 ``.qm`` 缺失也无妨：
    ``tr()`` 找不到翻译时直接返回源字符串。
    """

    def load_language(self, lang: Language) -> bool:
        qm = _translations_dir() / f"app.{lang.qlocale_name}.qm"
        if not qm.exists():
            # 未构建 .qm 时返回 False，但调用方可继续——源字符串会原样显示。
            return False
        return super().load(str(qm))


class LocalizationManager(QObject):
    """语言状态持有者 + translator 安装/卸载入口。

    生命周期：
        - app 启动时由 :func:`install_translators` 调用 :meth:`apply_language`
          完成首次安装。
        - 用户在「设置 → 关于」切换语言：UI 调用 :meth:`apply_language`，
          然后弹出"重启生效"提示（Qt 的运行时翻译切换需要每个 widget 主动
          响应 ``LanguageChange`` 事件，本期不做，按"重启"对待）。
    """

    language_changed = pyqtSignal(str)  # 发出新 code

    def __init__(self) -> None:
        super().__init__()
        self._app_translator: Optional[_AppTranslator] = None
        self._fluent_translator: Optional[QTranslator] = None
        self._current: Language = DEFAULT_LANGUAGE

    @property
    def current(self) -> Language:
        return self._current

    @property
    def current_code(self) -> str:
        return self._current.code

    def available(self) -> List[Language]:
        return list(AVAILABLE_LANGUAGES)

    def apply_language(self, code: str) -> Language:
        """切换到指定语言，安装 app 与 fluent translator。

        Args:
            code: ``Language.code``。未知值回退到默认语言。

        Returns:
            实际生效的 :class:`Language`。
        """
        lang = language_by_code(code)

        app = QCoreApplication.instance()
        if app is None:
            # 极少见——直接更新内部状态以便后续 install_translators 用。
            self._current = lang
            return lang

        # ── 卸载旧的 translator ─────────────────────────────────────
        if self._app_translator is not None:
            app.removeTranslator(self._app_translator)
            self._app_translator = None
        if self._fluent_translator is not None:
            app.removeTranslator(self._fluent_translator)
            self._fluent_translator = None

        # ── 安装 app translator（源字符串=zh_CN，缺失 .qm 也无碍）──
        app_tr = _AppTranslator()
        app_tr.load_language(lang)
        app.installTranslator(app_tr)
        self._app_translator = app_tr

        # ── 安装 qfluentwidgets 自带 translator（OK/Cancel/Cut/Copy 等）──
        # 注意：在同时装了 PyQt-Fluent-Widgets (PyQt5) 与 PyQt6-Fluent-Widgets
        # 的混合环境里，磁盘上的 ``qfluentwidgets`` 包可能是 PyQt5 变种；其
        # ``FluentTranslator`` 继承的是 ``PyQt5.QtCore.QTranslator``，被
        # PyQt6 的 ``installTranslator`` 拒绝并抛 TypeError。我们把这视为
        # "本环境无 qfluentwidgets 翻译"，静默回退——qfluentwidgets 内部 UI
        # 仍然工作，只是右键 Cut/Copy/Paste 等会显示英文源字符串。
        fluent_tr = _build_fluent_translator(lang)
        if fluent_tr is not None:
            try:
                app.installTranslator(fluent_tr)
            except TypeError:
                fluent_tr = None
            else:
                self._fluent_translator = fluent_tr

        self._current = lang
        self.language_changed.emit(lang.code)
        return lang


def _build_fluent_translator(lang: Language) -> Optional[QTranslator]:
    """构造 qfluentwidgets 的 FluentTranslator。

    qfluentwidgets 现已发布到 PyQt5/6/PySide6 三套；只要包能正常 import
    就能拿到 :class:`FluentTranslator`。失败时（包结构变化或环境异常）返回
    ``None``——qfluentwidgets 内部 UI 仍可用，只是字符串回落到英文源。
    """
    try:
        from qfluentwidgets import FluentTranslator  # type: ignore
    except Exception:
        return None
    try:
        return FluentTranslator(lang.to_qlocale())
    except Exception:
        return None


#: 进程内单例。由 :func:`install_translators` 初始化，由 UI 切换语言时复用。
localization = LocalizationManager()


def install_translators(language_code: Optional[str] = None) -> Language:
    """app 启动时调用一次。在 :class:`QApplication` 创建后立即调用。

    Args:
        language_code: 来自 ``AppSettings("ui.language")``。``None`` 时用
            默认（``zh_CN``）。

    Returns:
        实际生效的 :class:`Language`。
    """
    code = language_code or DEFAULT_LANGUAGE.code
    return localization.apply_language(code)
