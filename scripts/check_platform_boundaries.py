#!/usr/bin/env python3
"""Reject direct operating-system checks in shared UI and business layers."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ROOTS = (
    Path("src/strange_uta_game/frontend"),
    Path("src/strange_uta_game/backend/domain"),
    Path("src/strange_uta_game/backend/application"),
)
FORBIDDEN_ATTRIBUTES = {
    ("sys", "platform"),
    ("os", "name"),
    ("platform", "system"),
}


def _attribute_name(node: ast.Attribute) -> tuple[str, str] | None:
    if isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def find_forbidden_checks(repo_root: Path = REPO_ROOT) -> list[str]:
    """Return stable ``path:line`` entries for forbidden platform checks."""

    violations: list[str] = []
    for relative_root in FORBIDDEN_ROOTS:
        root = repo_root / relative_root
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative_path = path.relative_to(repo_root).as_posix()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and _attribute_name(node) in FORBIDDEN_ATTRIBUTES
                ):
                    violations.append(f"{relative_path}:{node.lineno}")
    return sorted(set(violations))


def main() -> int:
    violations = find_forbidden_checks()
    if not violations:
        print("Platform boundary check passed.")
        return 0
    print("Direct platform checks must live in the runtime/infrastructure layer:")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
