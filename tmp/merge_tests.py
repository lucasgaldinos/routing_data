"""Merge two pytest modules into one, preserving bodies verbatim."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

STDLIB = {
    "argparse", "collections", "copy", "csv", "datetime", "itertools", "json",
    "logging", "math", "os", "pathlib", "random", "re", "shutil", "statistics",
    "string", "subprocess", "sys", "tempfile", "textwrap", "typing",
}
THIRD_PARTY = {"click", "duckdb", "pandas", "psutil", "pytest", "yaml"}


def import_key_and_names(node: ast.AST):
    if isinstance(node, ast.ImportFrom):
        key = ("from", node.module or "", node.level)
        names = [(a.name, a.asname) for a in node.names]
    else:
        key = ("import",)
        names = [(a.name, a.asname) for a in node.names]
    return key, names


def collect(text: str):
    tree = ast.parse(text)
    lines = text.splitlines()
    doc = None
    imports: list[ast.AST] = []
    body: list[ast.AST] = []
    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            doc = ast.get_source_segment(text, node)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
            continue
        body.append(node)
    return doc, imports, body, lines, text


def node_text(node: ast.AST, text: str) -> str:
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    end = node.end_lineno
    return "\n".join(text.splitlines()[start - 1 : end])


def group_for(module: str) -> int:
    top = module.split(".")[0]
    if top in STDLIB:
        return 0
    if top in THIRD_PARTY:
        return 1
    return 2


def render_imports(order, from_map, plain_map) -> str:
    groups: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for key in order:
        if key[0] == "import":
            module, asname = plain_map[key]
            line = f"import {module}" + (f" as {asname}" if asname else "")
            groups[group_for(module)].append(line)
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
    chunks = []
    for idx in (0, 1, 2):
        if groups[idx]:
            chunks.append("\n".join(groups[idx]))
    return "\n\n".join(chunks)


def merge(target: Path, source: Path, label: str) -> None:
    t_doc, t_imports, t_body, _, t_text = collect(target.read_text())
    s_doc, s_imports, s_body, _, s_text = collect(source.read_text())
    order = []
    from_map: dict = {}
    plain_map: dict = {}
    for node in [*t_imports, *s_imports]:
        key, names = import_key_and_names(node)
        if key not in order:
            order.append(key)
        if key[0] == "import":
            module, asname = names[0]
            plain_map[key] = (module, asname)
            continue
        bucket = from_map.setdefault(key, [])
        for name, asname in names:
            if (name, asname) not in bucket:
                bucket.append((name, asname))
    header = t_doc or ""
    parts = [header.strip(), render_imports(order, from_map, plain_map)]
    for node in t_body:
        parts.append(node_text(node, t_text))
    parts.append(
        f"# ---------------------------------------------------------------------------\n"
        f"# Merged from {label} on 2026-10-20; bodies unchanged.\n"
        f"# ---------------------------------------------------------------------------"
    )
    for node in s_body:
        parts.append(node_text(node, s_text))
    target.write_text("\n\n\n".join(part.strip("\n") for part in parts if part.strip()) + "\n")


if __name__ == "__main__":
    merge(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
