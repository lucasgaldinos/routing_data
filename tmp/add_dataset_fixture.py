"""Add the dataset_path fixture to functions that hardcode corpus literals."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PARAM = "dataset_path: Callable[..., str]"
IMPORT = "from collections.abc import Callable"


def param_line_for(node: ast.FunctionDef, lines: list[str]) -> int:
    """Return the 0-based index of the line holding the closing parenthesis."""
    start = node.lineno - 1
    depth = 0
    for index in range(start, len(lines)):
        depth += lines[index].count("(") - lines[index].count(")")
        if index == start and depth == 0:
            return start
        if index > start and depth <= 0:
            return index
    raise RuntimeError(f"unterminated signature at line {node.lineno}")


def annotate(path: Path) -> None:
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines()
    edits: list[tuple[int, int, str]] = []  # (start_line_idx, end_line_idx, replacement)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_doc = node.body[0] if node.body else None
        literals = []
        for child in ast.walk(node):
            if child is body_doc:
                continue
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if child.value.startswith("datasets_raw/problems/"):
                    literals.append(child)
        if not literals:
            continue
        if any(arg.arg == "dataset_path" for arg in node.args.args + node.args.kwonlyargs):
            continue

        for literal in literals:
            relative = literal.value.removeprefix("datasets_raw/problems/")
            parts = relative.split("/")
            call = "dataset_path(" + ", ".join(f'"{part}"' for part in parts) + ")"
            line_idx = literal.lineno - 1
            col = literal.col_offset
            end_col = literal.end_col_offset or col
            line = lines[line_idx]
            edits.append((line_idx, line_idx, line[:col] + call + line[end_col:]))

        close_idx = param_line_for(node, lines)
        line = lines[close_idx]
        if close_idx == node.lineno - 1 and ")" in line:
            idx = line.rindex(")")
            prefix = line[:idx].rstrip()
            if prefix.endswith("("):
                new_line = prefix + PARAM + line[idx:]
            else:
                new_line = prefix + ", " + PARAM + line[idx:]
            edits.append((close_idx, close_idx, new_line))
        else:
            indent = " " * (node.col_offset + 2)
            edits.append((close_idx, close_idx, indent + PARAM + ","))

    if not edits:
        return

    for start, end, replacement in sorted(edits, key=lambda item: (item[0], item[0]), reverse=True):
        lines[start : end + 1] = [replacement]

    result = "\n".join(lines) + "\n"
    if IMPORT not in result:
        result = result.replace("from pathlib import Path", IMPORT + "\nfrom pathlib import Path", 1)
        if IMPORT not in result:
            result = result.replace("import pytest", IMPORT + "\n\nimport pytest", 1)
    path.write_text(result)


if __name__ == "__main__":
    for name in sys.argv[1:]:
        annotate(Path(name))
