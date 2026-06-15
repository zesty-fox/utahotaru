"""为 zh_CN 生成恒等 .ts（source == translation），用 lrelease 编出 .qm。

源串本身就是简体中文：把每条 source 复制到 translation 字段，去掉
``type="unfinished"``。流程对称、便于做翻译 QA（缺翻译时切到日文/伪
语言可被立刻发现）；运行时 LocalizationManager 仍能正常加载。
"""
from __future__ import annotations

import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    # 先复用 extract_ts.py 抽出最新 ja_JP.ts，按 source 拷一份做 zh_CN.ts
    src_ts = ROOT / "src/strange_uta_game/frontend/localization/translations/app.ja_JP.ts"
    dst_ts = ROOT / "src/strange_uta_game/frontend/localization/translations/app.zh_CN.ts"

    tree = ET.parse(src_ts)
    root = tree.getroot()
    root.set("language", "zh_CN")

    n = 0
    for ctx in root.findall("context"):
        for msg in ctx.findall("message"):
            src_el = msg.find("source")
            tr_el = msg.find("translation")
            if src_el is None or tr_el is None or not src_el.text:
                continue
            tr_el.text = src_el.text
            tr_el.attrib.pop("type", None)
            n += 1

    tree.write(dst_ts, encoding="utf-8", xml_declaration=True)
    print(f"wrote {n} identity translations → {dst_ts}")


if __name__ == "__main__":
    main()
