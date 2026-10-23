"""Rewrite the import block of a module in isort order."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, "tmp")
from merge_tests import collect, group_for, import_key_and_names  # noqa: E402


def fix(path: Path) -> None:
    text = path.read_text()
    doc, imports, body, lines, _ = collect(text)
    tree = ast.parse(text)
    doc_end = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            doc_end = node.end_lineno
            break
    first = body[0]
    start = min([first.lineno] + [d.lineno for d in getattr(first, "decorator_list", [])])
    order, from_map, plain_map = [], {}, {}
    for node in imports:
        key, names = import_key_and_names(node)
        if key not in order:
            order.append(key)
        if key[0] == "import":
            plain_map[key] = names[0]
        else:
            bucket = from_map.setdefault(key, [])
            for name, asname in names:
                if (name, asname) not in bucket:
                    bucket.append((name, asname))
    groups: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for key in order:
        if key[0] == "import":
            module, asname = plain_map[key]
            groups[group_for(module)].append(f"import {module}" + (f" as {asname}" if asname else ""))
            continue
        _, module, level = key
        names = from_map[key]
        rendered = ", ".join(n + (f" as {a}" if a else "") for n, a in names)
        prefix = "." * level + module
        line = f"from {prefix} import {rendered}"
        if len(line) > 100:
            inner = ",\n".join("  " + n + (f" as {a}" if a else "") for n, a in names)
            line = f"from {prefix} import (\n{inner},\n)"
        groups[group_for(module)].append(line)
    blocks = ["\n".join(sorted(groups[i])) for i in (0, 1, 2) if groups[i]]
    block = "\n\n".join(blocks)
    new_lines = lines[:doc_end] + ["", *block.splitlines(), ""] + lines[start - 1 :]
    path.write_text("\n".join(new_lines).rstrip() + "\n")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        fix(Path(arg))
