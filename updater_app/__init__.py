"""StrangeUtaGame 独立更新器（Updater.exe）。

本目录与主程序源码完全解耦：

* 依赖标准库 + ``requests`` + ``PyQt6`` + ``qfluentwidgets``（GUI 模式）；
* qfluentwidgets 可用时自动启用 GUI 窗口（进度环 + 日志），不可用时回退控制台；
* ``--windowed`` 打包，不弹出控制台窗口。

打包通过 ``build_updater.py`` 完成，产物 ``dist/Updater/Updater.exe`` 应该被
``build.py`` 复制到主程序产物目录。
"""

__version__ = "1.0.0"
