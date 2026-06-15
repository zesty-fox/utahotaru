"""把 translations_ja_JP.json 的日文条目灌入 app.ja_JP.ts（按 source 匹配）。

输出后用 pyside6-lrelease 编译为 app.ja_JP.qm。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    ts_path = root / "src/strange_uta_game/frontend/localization/translations/app.ja_JP.ts"
    json_path = root / "scripts/translations_ja_JP.json"

    with json_path.open(encoding="utf-8") as f:
        translations: dict[str, str] = json.load(f)

    tree = ET.parse(ts_path)
    tree_root = tree.getroot()

    matched = 0
    unmatched: list[tuple[str, str]] = []  # (context, source)
    total = 0
    for ctx_el in tree_root.findall("context"):
        ctx_name_el = ctx_el.find("name")
        ctx_name = ctx_name_el.text if ctx_name_el is not None else ""
        for msg in ctx_el.findall("message"):
            total += 1
            src_el = msg.find("source")
            tr_el = msg.find("translation")
            if src_el is None or tr_el is None or not src_el.text:
                continue
            src = src_el.text
            ja = translations.get(src)
            if ja is None:
                unmatched.append((ctx_name or "?", src))
                continue
            tr_el.text = ja
            tr_el.attrib.pop("type", None)  # 去掉 unfinished
            matched += 1

    tree.write(ts_path, encoding="utf-8", xml_declaration=True)

    print(f"total messages: {total}")
    print(f"matched: {matched}")
    print(f"unmatched: {len(unmatched)}")
    if unmatched and "--show-unmatched" in sys.argv:
        for ctx, src in unmatched[:60]:
            preview = src.replace("\n", "\\n")[:80]
            print(f"  [{ctx}] {preview}")
        if len(unmatched) > 60:
            print(f"  ... and {len(unmatched) - 60} more")


if __name__ == "__main__":
    main()
