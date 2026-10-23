"""Attach orthogonal pytest markers per test from actual dependencies."""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

DATASET_PARAMS = {
    "dataset_path", "test_data_dir", "tsp_dir", "gr17_tsp", "berlin52_tsp",
    "br17_atsp", "ft53_atsp", "ft70_atsp", "sample_data", "batch_data",
    "parsed_data", "transformed_gr17", "cordeau_mdvrp_dir", "br17_path",
    "temp_input_with_file", "db_with_data", "atsp_files", "tsp_files_small",
    "tsp_files_medium", "vrp_files",
}
DB_PARAMS = {"db", "db_with_data", "inspect_db"}
DB_CLASSES = {
    "TestProcessCommand", "TestAnalyzeCommand", "TestValidateCommand", "TestCLIIntegration",
}
DB_FREE_CLI_TESTS = {"test_process_requires_input", "test_process_nonexistent_input"}
REGRESSION = {
    "tests/converter/test_unit_json_writer.py": {"TestRemoveDeadEdgesField", "TestJSONWritingDeduplication"},
    "tests/converter/test_unit_database.py": {"TestConnectionLeakFix"},
}
SLOW = {
    "test_all_corpus_files_match_declared_types_and_dimensions",
    "test_corpus_full_matrix_values_match_raw_sections",
}


def classify(path: Path) -> list[tuple[ast.FunctionDef, str, list[str]]]:
    text = path.read_text()
    tree = ast.parse(text)
    found = []
    for node in tree.body:
        classes = [node] if isinstance(node, ast.ClassDef) else []
        functions = [(None, child) for child in ast.walk(node) if isinstance(child, ast.FunctionDef)] if not classes else []
        if isinstance(node, ast.FunctionDef):
            functions = [(None, node)]
        for cls in classes:
            functions.extend((cls.name, child) for child in cls.body if isinstance(child, ast.FunctionDef))
        for class_name, fn in functions:
            if not fn.name.startswith("test_"):
                continue
            params = {arg.arg for arg in fn.args.args + fn.args.kwonlyargs}
            source = ast.get_source_segment(text, fn) or ""
            tags = []
            if params & DATASET_PARAMS or "dataset_path(" in source or "test_data_dir" in source:
                tags.append("requires_dataset")
            opens_db = bool(params & DB_PARAMS) or "DatabaseManager(" in source or "duckdb.connect" in source
            if path.name == "test_integration_cli_commands.py" and class_name in DB_CLASSES and fn.name not in DB_FREE_CLI_TESTS:
                opens_db = True
            if opens_db:
                tags.append("database")
            if "cli_runner" in params:
                tags.append("cli")
            if class_name in REGRESSION.get(str(path), set()):
                tags.append("regression")
            if fn.name in SLOW:
                tags.append("slow")
            if tags:
                found.append((fn, class_name, tags))
    return found


def apply(path: Path, dry_run: bool) -> Counter:
    text = path.read_text()
    lines = text.splitlines()
    found = classify(path)
    counts: Counter = Counter()
    edits: list[tuple[int, list[str]]] = []
    for fn, _, tags in found:
        existing = {
            deco.attr for deco in fn.decorator_list if isinstance(deco, ast.Attribute) and deco.attr in
            {"unit", "integration", "e2e", "performance", "slow", "requires_dataset", "regression", "cli", "database", "serial"}
        }
        new = [tag for tag in tags if tag not in existing]
        if not new:
            continue
        counts.update(new)
        indent = " " * fn.col_offset
        edits.append((fn.lineno - 1, [f"{indent}@pytest.mark.{tag}" for tag in new]))
    if not dry_run:
        for index, decorators in sorted(edits, reverse=True):
            lines[index:index] = decorators
        path.write_text("\n".join(lines) + "\n")
    return counts


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    total: Counter = Counter()
    for name in sys.argv[1:]:
        if name == "--apply":
            continue
        counts = apply(Path(name), dry)
        if counts:
            print(f"{name}: {dict(sorted(counts.items()))}")
            total.update(counts)
    print(("DRY-RUN " if dry else "APPLIED ") + f"totals: {dict(sorted(total.items()))}")
