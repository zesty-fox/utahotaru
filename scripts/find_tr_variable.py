"""扫所有 ``self.tr(变量)`` 调用——extractor 拿不到字面，运行时如
果 .ts 没有对应源串就会回退到中文显示。这是常见的"包了 tr 但仍然
不翻译"陷阱。"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / "src/strange_uta_game/frontend", ROOT / "src/strange_uta_game/updater"]


def scan_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        is_tr = False
        if isinstance(f, ast.Attribute) and f.attr == "tr":
            is_tr = True
        elif isinstance(f, ast.Name) and f.id in ("tr", "_tr"):
            is_tr = True
        if not is_tr or not node.args:
            continue
        arg = node.args[0]
        # 字面量 / 字面拼接 - OK
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            continue
        if isinstance(arg, ast.JoinedStr):
            # f-string 已经是抽取不了的
            pass
        # 字面 + 字面拼接也忽略
        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
            # 简化判断：两边都 Constant str
            ok = True
            for side in (arg.left, arg.right):
                if not (isinstance(side, ast.Constant) and isinstance(side.value, str)):
                    ok = False
                    break
            if ok:
                continue
        # 其余视为"变量参数"
        src = ast.unparse(arg)[:80]
        out.append((node.lineno, src))
    return out


def main():
    rows = []
    for target in TARGETS:
        for p in sorted(target.rglob("*.py")):
            for line, src in scan_file(p):
                rows.append((p, line, src))
    print(f"found {len(rows)} self.tr(variable) calls")
    cur = None
    for p, ln, src in rows:
        if p != cur:
            rel = p.relative_to(ROOT)
            print(f"\n== {rel} ==")
            cur = p
        print(f"  L{ln} tr({src})")


if __name__ == "__main__":
    main()
