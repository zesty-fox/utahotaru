"""列出仍含中文字面量但未走 tr() / QCoreApplication.translate() 的 UI 字符串。

启发式：
- 遍历 src/strange_uta_game/{frontend,updater} 下所有 .py
- 用 ast 找含中文（U+4E00..U+9FFF / U+3000..U+303F / U+3040..U+30FF 等）的 Constant str
- 顺着父节点链回溯：若最近的祖先 Call 是 self.tr / Class.tr / QCoreApplication.translate
  且当前字符串正是其字面参数，则跳过
- 其余视为可能未抽取
- 仍会包含文件路径过滤器、日志、注释里的字面量；人工取舍

输出：(file, line, context_class, snippet)
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    ROOT / "src/strange_uta_game/frontend",
    ROOT / "src/strange_uta_game/updater",
]

# 含 CJK / kana / fullwidth punct
CJK_RE = re.compile(r"[一-鿿　-〿぀-ヿ＀-￯]")


def _is_under_tr_call(node_chain: list[ast.AST]) -> bool:
    """从最里向外看链上是否有 Call(self.tr / obj.tr / translate) 且当前字符串
    正是该 Call 的字面参数（不是 dict 值/嵌套表达式）。"""
    # 当前节点 (Constant) 的父链最后一个是 Constant；倒数第二个起向上看
    for i in range(len(node_chain) - 2, -1, -1):
        n = node_chain[i]
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "tr":
                return True
            if (
                isinstance(f, ast.Attribute)
                and f.attr == "translate"
                and isinstance(f.value, ast.Name)
                and f.value.id == "QCoreApplication"
            ):
                return True
            # tr 是个 Name (module-level alias) — 早期代码用 `tr = lambda s: ...`
            if isinstance(f, ast.Name) and f.id in ("tr", "_tr"):
                return True
            # 走到一个不是 tr/translate 的 Call：不算 tr 包裹
            return False
        # 透过 keyword / BoolOp / IfExp / BinOp(+) / JoinedStr 继续往上找
        if isinstance(n, (ast.keyword, ast.BinOp, ast.IfExp, ast.JoinedStr)):
            continue
        # 进入了表达式语句 / Assign / Compare 等不是 Call 的容器 — 停
        if isinstance(n, ast.Call):
            return False
    return False


_DOCSTRING_HOLDERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _collect_docstring_ids(tree: ast.AST) -> set[int]:
    """收集所有 docstring Constant 节点 id，避免误报。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_HOLDERS) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.add(id(first.value))
    return out


class _Walker(ast.NodeVisitor):
    def __init__(self, path: Path, doc_ids: set[int]) -> None:
        self.path = path
        self.class_stack: list[str] = []
        self.parent_stack: list[ast.AST] = []
        self.doc_ids = doc_ids
        self.findings: list[tuple[int, str, str]] = []  # (line, ctx, source)

    def generic_visit(self, node: ast.AST) -> None:
        self.parent_stack.append(node)
        super().generic_visit(node)
        self.parent_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.parent_stack.append(node)
        super().generic_visit(node)
        self.parent_stack.pop()
        self.class_stack.pop()

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, str):
            return
        if id(node) in self.doc_ids:
            return
        s = node.value
        if not CJK_RE.search(s):
            return
        # 跳过显式的单字符 logic literal（"是"/"否"/"一"/"っ" 之类多为内部值）
        if len(s.strip()) <= 1:
            return
        # 跳过 logger / print 等开发用日志格式串
        if s.startswith("[") and "]" in s[:30]:
            # "[self-update] ..." 这类日志前缀
            return
        if _is_under_tr_call(self.parent_stack + [node]):
            return
        # 父节点：是否是某个 UI 方法的参数？
        # 当且仅当父链上有这样的 Call 才视为高信号：
        #   - 构造 QLabel / PushButton / PrimaryPushButton / CaptionLabel /
        #     QGroupBox / QCheckBox / QRadioButton / SettingCard /
        #     SettingCardGroup / SwitchSettingCard / ComboSettingCard /
        #     SpinSettingCard / Action / RoundMenu / QMessageBox(... text...)
        #   - 方法名 setText / setTitle / setWindowTitle / setToolTip /
        #     setPlaceholderText / setStatusTip / setSuffix / setPrefix /
        #     setHorizontalHeaderLabels / addAction / addItem / addItems /
        #     showMessage / setInformativeText
        #   - InfoBar.warning/success/info/error 的 title/content
        #   - QMessageBox.question/information/warning/critical 的 title/text
        UI_CONSTRUCT_NAMES = {
            "QLabel", "PushButton", "PrimaryPushButton", "CaptionLabel",
            "QGroupBox", "QCheckBox", "QRadioButton",
            "SettingCard", "SettingCardGroup",
            "SwitchSettingCard", "ComboSettingCard", "SpinSettingCard",
            "DoubleSpinSettingCard", "TextSettingCard", "FontSettingCard",
            "BrowseSettingCard", "MultiCheckSettingCard", "MultiBoolSettingCard",
            "ShortcutSettingCard", "ComboBox",
            "Action", "RoundMenu", "QMessageBox",
            "InfoBar", "StateToolTip",
        }
        UI_METHOD_NAMES = {
            "setText", "setTitle", "setWindowTitle", "setToolTip",
            "setPlaceholderText", "setStatusTip", "setSuffix", "setPrefix",
            "setHorizontalHeaderLabels", "setInformativeText",
            "setContent",
            "addAction", "addItem", "addItems", "addRow",
            "showMessage",
            "warning", "success", "info", "error",
            "question", "information", "critical",
        }
        for ancestor in reversed(self.parent_stack):
            if isinstance(ancestor, ast.Call):
                f = ancestor.func
                name = None
                if isinstance(f, ast.Name):
                    name = f.id
                elif isinstance(f, ast.Attribute):
                    name = f.attr
                if name in UI_CONSTRUCT_NAMES or name in UI_METHOD_NAMES:
                    ctx = self.class_stack[-1] if self.class_stack else "Global"
                    self.findings.append((node.lineno, ctx, s))
                    return
                # 一个非 UI 的 Call 包着了，继续找更外层（参数可能传给外层 UI 调用）
        # 不是 UI 上下文 → 跳过
        return


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, SyntaxError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    doc_ids = _collect_docstring_ids(tree)
    w = _Walker(path, doc_ids)
    w.visit(tree)
    return w.findings


def main() -> None:
    rows: list[tuple[Path, int, str, str]] = []
    for target in TARGETS:
        for path in sorted(target.rglob("*.py")):
            for line, ctx, s in scan_file(path):
                rows.append((path, line, ctx, s))
    # 排重 by (path, line, s)
    seen: set[tuple[str, int, str]] = set()
    unique: list[tuple[Path, int, str, str]] = []
    for r in rows:
        key = (str(r[0]), r[1], r[3])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    print(f"found {len(unique)} unwrapped chinese-bearing literals")
    by_file: dict[Path, list[tuple[int, str, str]]] = {}
    for p, ln, ctx, s in unique:
        by_file.setdefault(p, []).append((ln, ctx, s))
    for p, items in by_file.items():
        rel = p.relative_to(ROOT)
        print(f"\n== {rel} ==")
        for ln, ctx, s in items:
            preview = s.replace("\n", "\\n")
            if len(preview) > 100:
                preview = preview[:100] + "…"
            print(f"  L{ln} [{ctx}] {preview}")


if __name__ == "__main__":
    main()
