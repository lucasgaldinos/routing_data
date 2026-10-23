"""Add PEP 585/604 annotations to test functions and fixtures missing them."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PARAM_TYPES = {
    "tmp_path": "Path",
    "test_data_dir": "Path",
    "tsp_dir": "Path",
    "temp_directory": "Path",
    "cordeau_mdvrp_dir": "Path",
    "dataset_path": "Callable[..., str]",
    "cli_runner": "CliRunner",
    "sample_data": "dict[str, Any]",
    "batch_data": "list[dict[str, Any]]",
    "transformer": "DataTransformer",
    "parsed_data": "dict[str, Any]",
    "transformed": "dict[str, Any]",
}
RETURN_TYPES = {
    "temp_directory": "Path",
    "sample_data": "dict[str, Any]",
    "batch_data": "list[dict[str, Any]]",
}


def build_signature(node: ast.FunctionDef, lines: list[str]) -> str:
    indent = " " * node.col_offset
    args = []
    positional = node.args.posonlyargs + node.args.args
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults, strict=True):
        if arg.arg == "self":
            args.append("self")
            continue
        annotation = ast.unparse(arg.annotation) if arg.annotation else PARAM_TYPES.get(arg.arg, "Any")
        piece = f"{arg.arg}: {annotation}"
        if default is not None:
            piece += f" = {ast.unparse(default)}"
        args.append(piece)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        annotation = ast.unparse(arg.annotation) if arg.annotation else PARAM_TYPES.get(arg.arg, "Any")
        piece = f"{arg.arg}: {annotation}"
        if default is not None:
            piece += f" = {ast.unparse(default)}"
        args.append(piece)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")

    if node.returns:
        returns = ast.unparse(node.returns)
    elif node.name.startswith("test_"):
        returns = "None"
    else:
        returns = RETURN_TYPES.get(node.name, "Any")

    prefix = f"def {node.name}("
    single = prefix + ", ".join(args) + f") -> {returns}:"
    if len(indent) + len(single) <= 118:
        return indent + single
    inner = ",\n".join(" " * (node.col_offset + 2) + arg for arg in args)
    return f"{indent}def {node.name}(\n{inner}\n{indent}) -> {returns}:"


def annotate(path: Path) -> None:
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines()
    changes: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        needs_return = node.returns is None
        needs_param = any(
            arg.annotation is None
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            if arg.arg != "self"
        )
        if not (needs_return or needs_param):
            continue
        start = node.lineno - 1
        end = start
        depth = 0
        while True:
            depth += lines[end].count("(") - lines[end].count(")")
            if depth <= 0 and lines[end].rstrip().endswith(":"):
                break
            end += 1
        changes.append((start, end, build_signature(node, lines)))

    for start, end, signature in sorted(changes, reverse=True):
        lines[start : end + 1] = [signature]
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    for name in sys.argv[1:]:
        annotate(Path(name))
