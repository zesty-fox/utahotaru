"""打包 ``UpdaterEx/UpdaterEx.exe`` —— 独立的 GUI 更新器（PyInstaller --onedir 产物）。

输出位置：``<repo>/updater_app/dist/UpdaterEx/UpdaterEx.exe``。
``UpdaterEx/`` 同目录的 ``_internal/`` 仅用于构建，不复制到主程序。
主程序 ``dist/StrangeUtaGame/`` 已有自身的 ``_internal/``，UpdaterEx.exe 直接复用。
在 ``build.py`` 中仅复制 UpdaterEx.exe 单文件到主程序目录。

使用：

.. code:: bat

    python updater_app\\build_updater.py

设计权衡：

* ``--onedir`` —— 产出一个独立目录，但仅其中的 UpdaterEx.exe 单文件被复制到主程序。
  UpdaterEx.exe 运行时通过同级 ``_internal/``（主程序的）加载 PyQt6 等依赖，
  避免在 UpdaterEx 内部重复打包。
* ``--windowed`` —— GUI 模式（PyQt6 窗口），不弹出控制台窗口。
* 引入 PyQt6 用于 GUI 显示进度条和日志窗口；PyQt6 不可用时自动回退到控制台。
* 命名为 ``UpdaterEx.exe`` 而非 ``Updater.exe``，使旧版 installer.py（≤v1.2.1）
  无法识别它，安全回退到磁盘上已有的旧 ``Updater.exe``。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    """强制 stdout/stderr 用 UTF-8。

    Windows 终端默认编码可能是 cp1252（GitHub Actions runner）或 cp936（中文系统），
    在那些环境下 ``print("中文")`` 会触发 ``UnicodeEncodeError``。Python 3.7+ 的
    ``TextIOWrapper.reconfigure`` 可以无侵入地改写已存在的 stdout/stderr 流。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 UpdaterEx.exe")
    ap.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="传给 PyInstaller --clean，完整重建（改了 import 或打包配置时使用）",
    )
    cli = ap.parse_args()

    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("缺少 pyinstaller。请先 `pip install pyinstaller`。", file=sys.stderr)
        return 1

    args = [
        str(PROJECT_ROOT / "main.py"),
        "--name=UpdaterEx",
        "--onedir",
        "--windowed",         # GUI 模式，不弹控制台窗口
        "--noconfirm",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT),
        # 标准库 + requests + PyQt6 + qfluentwidgets（GUI）
        "--hidden-import=requests",
        "--hidden-import=gui",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=qfluentwidgets",
        "--hidden-import=urllib3",
        "--hidden-import=charset_normalizer",
        "--hidden-import=idna",
        "--hidden-import=certifi",
        # ── 易被 PyInstaller `--exclude-module` 副作用漏掉的标准库 ───────────
        # `colorsys` 等是非常小的纯 Python 模块，但 PyInstaller 在分析
        # excluded-package 的子依赖时偶尔会过激；为安全起见全部显式声明。
        "--hidden-import=colorsys",
        "--hidden-import=encodings",
        "--hidden-import=encodings.idna",
        "--hidden-import=encodings.utf_8",
        "--hidden-import=encodings.utf_8_sig",
        "--hidden-import=encodings.cp1252",
        "--hidden-import=encodings.cp437",
        "--hidden-import=encodings.cp65001",
        "--hidden-import=encodings.gbk",
        "--hidden-import=encodings.mbcs",
        "--hidden-import=hashlib",
        "--hidden-import=zipfile",
        "--hidden-import=tempfile",
        "--hidden-import=ssl",
        "--hidden-import=_ssl",
        # ── 排除主程序的重型依赖，缩小体积 ──
        "--exclude-module=numpy",
        "--exclude-module=sounddevice",
        "--exclude-module=soundfile",
        "--exclude-module=pedalboard",
        "--exclude-module=av",
        "--exclude-module=pykakasi",
        "--exclude-module=sudachipy",
        "--exclude-module=sudachidict_core",
        "--exclude-module=jaconv",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=tkinter",
    ]

    # 图标（沿用主程序图标，找不到就跳过）
    icon = REPO_ROOT / "src" / "strange_uta_game" / "resource" / "icon.ico"
    if icon.exists():
        args.append(f"--icon={icon}")

    if cli.clean:
        args.append("--clean")

    import PyInstaller.__main__ as pi_main
    print("开始打包 UpdaterEx.exe ...")
    pi_main.run(args)
    print()
    exe = PROJECT_ROOT / "dist" / "UpdaterEx" / "UpdaterEx.exe"
    if exe.exists():
        print(f"✓ 打包完成: {exe}")
        print(f"  体积: {exe.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        print("! 未在 dist/UpdaterEx/UpdaterEx.exe 找到产物，请检查 PyInstaller 输出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
