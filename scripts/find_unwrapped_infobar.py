"""扫所有 InfoBar.{warning|success|info|error|...} / StateToolTip / QMessageBox
调用的位置参数与 title/content/text 关键字参数，检查内部出现的中文是否走
tr。报告未走 tr 的位置。

启发式 + AST：
- 找 ``Foo.bar(...)`` 这类 Call，func.attr 落在感兴趣集合
- 对每个 args/keywords，看是否是 Constant str 含 CJK 且不在 tr() / translate()
  / 含 f-string-format 的链路中
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [ROOT / "src/strange_uta_game/frontend", ROOT / "src/strange_uta_game/updater"]

CJK = re.compile(r"[一-鿿]")

INTERESTING_ATTRS = {
    "warning", "success", "info", "error",
    "information", "critical", "question",
    "showMessage",
}
INTERESTING_NAMES = {"InfoBar", "StateToolTip", "QMessageBox", "MessageBox"}

KEYWORDS_OF_INTEREST = {"title", "content", "text", "informativeText", "windowTitle"}


def _is_tr_call(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("tr", "translate"):
            return True
        if isinstance(f, ast.Name) and f.id in ("tr", "_tr"):
            return True
        # 形如 self.tr("...").format(...) 也算
        if isinstance(f, ast.Attribute) and f.attr == "format" and isinstance(f.value, ast.Call):
            return _is_tr_call(f.value)
    return False


def _contains_unwrapped_cjk(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if CJK.search(node.value):
            return node.value
        return None
    if _is_tr_call(node):
        return None
    if isinstance(node, ast.Call):
        for a in node.args:
            s = _contains_unwrapped_cjk(a)
            if s: return s
        for kw in node.keywords:
            s = _contains_unwrapped_cjk(kw.value)
            if s: return s
        return None
    if isinstance(node, (ast.BinOp, ast.JoinedStr, ast.IfExp)):
        for child in ast.iter_child_nodes(node):
            s = _contains_unwrapped_cjk(child)
            if s: return s
    return None


def _func_name(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Attribute):
        # Foo.bar(...)
        v = f.value
        owner = v.id if isinstance(v, ast.Name) else None
        if owner in INTERESTING_NAMES and f.attr in INTERESTING_ATTRS:
            return f"{owner}.{f.attr}"
        # widget.setText / setWindowTitle / setInformativeText
        if f.attr in ("setText", "setWindowTitle", "setInformativeText", "setToolTip", "showMessage"):
            return f.attr
    return None


def scan_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError):
        return []
    out: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _func_name(node)
        if name is None:
            continue
        # positional first arg (text=...) for setText etc., or all args for messageboxes
        candidates = list(node.args)
        for kw in node.keywords:
            if kw.arg in KEYWORDS_OF_INTEREST:
                candidates.append(kw.value)
        for v in candidates:
            bad = _contains_unwrapped_cjk(v)
            if bad:
                preview = bad.replace("\n", "\\n")[:80]
                out.append((node.lineno, name, preview))
                break
    return out


def main() -> None:
    rows: list[tuple[Path, int, str, str]] = []
    for target in TARGETS:
        for path in sorted(target.rglob("*.py")):
            for line, name, src in scan_file(path):
                rows.append((path, line, name, src))
    print(f"found {len(rows)} unwrapped InfoBar/MessageBox/StateToolTip strings")
    cur = None
    for p, ln, name, s in rows:
        if p != cur:
            rel = p.relative_to(ROOT)
            print(f"\n== {rel} ==")
            cur = p
        print(f"  L{ln} {name}: {s}")


if __name__ == "__main__":
    main()
