"""一键构建当前平台的所有发布目标。

每个目标的构建流程：
  1. python updater_app/build_updater.py   构建 Updater.exe（Windows 专用）
  2. python build.py --target <target>     构建共享主程序

产物位置：
  dist/StrangeUtaGame/          main
  dist/StrangeUtaGame-noWinIME/ noWinIME
  dist/StrangeUtaGame-mac/      mac（在 macOS 上构建）

用法：
  python build_all.py [--clean] [--targets windows-x86_64-windows-installer]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.release_tools.targets import SUPPORTED_TARGETS

PROJECT_ROOT = Path(__file__).parent.absolute()

# 各原生 runner 默认构建的发布目标
_PLATFORM_TARGETS: dict[str, list[str]] = {
    "win32": ["windows-x86_64-windows-installer"],
    "darwin": ["macos-universal2-macos-dmg"],
    "linux": [
        "linux-x86_64-appimage",
        "linux-x86_64-flatpak",
        "linux-x86_64-deb",
    ],
}


def _force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()


def run_step(cmd: list[str], step_name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f">>> {step_name}")
    print(f"    {' '.join(str(c) for c in cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"\n✗ 步骤失败（退出码 {result.returncode}）: {step_name}")
        sys.exit(result.returncode)
    print(f"✓ 完成: {step_name}")


def build_target(target: str, clean: bool) -> None:
    """构建单个发布目标。"""
    # 1. 构建 Updater.exe（仅 Windows）
    if sys.platform == "win32":
        updater_cmd = [sys.executable, "updater_app/build_updater.py"]
        if clean:
            updater_cmd.append("--clean")
        run_step(updater_cmd, f"构建 Updater.exe（供 {target} 使用）")

    # 2. 构建主程序
    main_cmd = [sys.executable, "build.py", "--target", target]
    if clean:
        main_cmd.append("--clean")
    run_step(main_cmd, f"构建主程序 target={target}")


def main() -> int:
    ap = argparse.ArgumentParser(description="一键构建当前平台的发布目标")
    ap.add_argument("--clean", action="store_true", help="传给 PyInstaller --clean，完整重建")
    ap.add_argument(
        "--targets",
        nargs="+",
        choices=sorted(SUPPORTED_TARGETS),
        default=None,
        help="指定发布目标（默认按平台自动选择）",
    )
    cli = ap.parse_args()

    platform_key = sys.platform if sys.platform in _PLATFORM_TARGETS else "linux"
    targets: list[str] = cli.targets or _PLATFORM_TARGETS[platform_key]

    print(f"平台: {sys.platform}")
    print(f"将构建以下目标: {targets}")

    for target in targets:
        print(f"\n{'#' * 60}")
        print(f"# 目标: {target}")
        print(f"{'#' * 60}")
        build_target(target, cli.clean)

    print(f"\n{'=' * 60}")
    print(f"✓ 全部目标构建完成: {targets}")
    print("共享载荷位置: dist/StrangeUtaGame/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
