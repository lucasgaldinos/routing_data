---
title: Test suite conventions
description: >
  Layout, filename, level and marker conventions for routing_data/tests, plus
  the command map used to select fast, dataset-free, slow and end-to-end test
  gates. Read this before adding, moving, or retagging a test.
created: 2026-10-20
modifications:
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Created with the package-mirroring layout, level-prefixed filenames,
          derived level markers, orthogonal marker table, parser-file
          boundaries, and command map.
  - date_modified: 2026-10-21
    modifications:
      - description: >
          Recorded the implemented state after Batches 1-4: per-test
          orthogonal tags with counts, warn-only hook behaviour, current suite
          size and level split, slow-test measurements, and a checklist for
          changing a test.
  - date_modified: 2026-10-22
    modifications:
      - description: >
          Updated counts following PP6 Cordeau integration: 300 tests total,
          136 requires_dataset tests (added CordeauProblem and lossless LKH-3 tests).
related_files:
  - [conftest.py](./conftest.py)
  - [testing_instructions.instructions.md](../.github/instructions/testing_instructions.instructions.md)
  - [test.instructions.md](../.github/instructions/test.instructions.md)
tags:
  - docs/guide/tests/layout
  - docs/guide/tests/naming
  - docs/guide/tests/markers/levels
  - docs/guide/tests/markers/orthogonal
  - docs/notes/repository-structure/tests
  - docs/notes/conventions/testing
  - docs/notes/pytest/collection
  - docs/notes/pytest/configuration
---

# Test suite conventions

> [!warning]
> README must be updated according to changes.
> If instructions do not tell to update the README when changing tests, please add when you see this message.

## Layout

The tree mirrors the source packages. Cross-package tests have their own level
folder because they belong to neither package.

```text
tests/
├── README.md
├── conftest.py
├── test_unit_conftest.py
├── e2e/
│   └── test_e2e_pipeline.py
├── tsplib_parser/
│   ├── test_unit_parser.py
│   ├── test_unit_parser_contract.py
│   ├── test_unit_parser_robustness.py
│   ├── test_unit_parser_validation.py
│   ├── test_unit_parser_section_grammars.py
│   ├── test_unit_matrix_formats.py
│   ├── test_unit_matrix_value_access.py
│   ├── test_unit_cordeau.py
│   └── test_integration_cordeau.py
└── converter/
    ├── test_unit_scanner.py
    ├── test_unit_transformer.py
    ├── test_unit_cost.py
    ├── test_unit_database.py
    ├── test_unit_json_writer.py
    ├── test_integration_api.py
    ├── test_integration_cli_commands.py
    ├── test_integration_cli_inspect.py
    └── test_integration_pipeline.py
```

`tests/test_unit_conftest.py` is the documented infrastructure exception: it
tests the root `conftest.py` (the marker hook and its mapping), which belongs to
no source package.

Current state (2026-10-21): Batches 1–4 of the reorganization are done
(structure, fixtures/quality, annotations, marker hook and tags). Batch 5
(coverage gaps) is pending. Suite: **306 passed, 0 failed, 0 skipped**, ~23 s;
`ruff check tests` clean. Levels: 248 `unit`, 57 `integration`, 1 `e2e`.
The rationale for every rule below is in
`tmp/analysis-test-suite-organization.md`.

## Filename rule

`test_<level>_<module>[_<concern>].py`

| Part | Meaning |
| ---- | ------- |
| `level` | `unit`, `integration`, `e2e`, `performance` |
| `module` | Source module name: `parser`, `matrix_formats`, `database`, `json_writer`, `cli_commands` |
| `concern` | Optional, when one module needs several files: `contract`, `robustness`, `validation`, `section_grammars` |

pytest's default `python_files = test_*.py` already collects this pattern.

## Level rules

| Level | Rule |
| ----- | ---- |
| `unit` | Exactly one source module under test. `tmp_path` and a file-backed DuckDB database are allowed. |
| `integration` | Two or more source modules composed, a `CliRunner` invocation, or an adapter whose job is composition. |
| `e2e` | The full scan → parse → transform → write → database chain across packages. |
| `performance` | Asserts on wall time or resource use. Not a synonym for "slow". |

Edge cases already decided by these rules:

- `test_unit_json_writer.py` is unit although it writes files.
- `test_unit_database.py` is unit although it opens DuckDB.
- `test_unit_matrix_formats.py` is unit although some cases read corpus files; those cases carry `requires_dataset`.
- `test_integration_api.py` is integration because `SimpleConverter.parse` and `to_json` compose parser, transformer and writer.
- `test_integration_pipeline.py` is integration: it composes two or more modules but stops short of the full chain.
- `test_integration_cordeau.py` is integration because it drives the whole chain for the adapter.

## Markers

Level markers are derived from the filename by `pytest_collection_modifyitems`
in `conftest.py`, using `level_marker_for()`. Do not write `@pytest.mark.unit` or
its siblings by hand; the filename is the single source of truth. An unprefixed
test file is still collected but emits one `PytestWarning` and gets no level.
The hook's own tests live in `tests/test_unit_conftest.py`.

Orthogonal markers are written explicitly on each test, only where the trait is
true:

| Marker | Apply when | Applied to |
| ------ | ---------- | ---------- |
| `slow` | Measured wall time > 1 s | 2 tests |
| `requires_dataset` | The test opens files under `datasets_raw/**`, directly or through a fixture | 136 tests |
| `regression` | The test guards a specific fixed defect named in the docstring | 9 tests: Issues #3/#4 and #6 |
| `cli` | The test drives `click.testing.CliRunner` | 21 tests |
| `database` | The test opens a DuckDB database | 45 tests |
| `performance` | The test asserts on time or resources | Registered, unused |
| `serial` | The test is unsafe under xdist | Registered, unused |

`performance` and `serial` stay registered but empty; an empty selection is
expected. `regression` is deliberately narrow: only suites whose docstring names
a closed issue (JSON writing #3/#4, connection leak #6). Parser contracts and the
unskipped br17 baseline are not tagged.

The counts above are hand-maintained. If a test body starts reading
`datasets_raw/**` or opening DuckDB, add the matching decorator in the same edit;
nothing derives these tags automatically.

Do not invent `fast`, `parser`, `matrix`, or `converter`: the first is the
complement of `slow`, and the others are already in the path and filename.

Last `slow` measurement: 2026-10-21, threshold 1 s. Two tests exceed it: the
239-file declared-vs-extracted sweep (8.35 s) and the corpus wide matrix value
check (6.83 s). Re-measure after any change to corpus-wide tests.

## Parser test boundaries

| File | Owns |
| ---- | ---- |
| `test_unit_parser.py` | Public `FormatParser.parse_file` behavior on real files: structure, metadata, dimensions, coordinate and matrix values |
| `test_unit_parser_contract.py` | Behavioral contracts: comments in sections, duplicate keys, `EDGE_WEIGHT_FORMAT: FUNCTION`, unregistered and stripped sections, temporary-file isolation, removed legacy parser (LSP), callable naming, coordinate-dimension validation, Field descriptor protocol |
| `test_unit_parser_robustness.py` | Malformed section content fails loudly; exception-type contract; structural violations; real-world format variants; registered LKH-3 headers keep their typed values |
| `test_unit_parser_validation.py` | `validate_problem_data` / `validate_parse_result` rules, problem class auto-dispatch registry, and the 239-file declared-vs-extracted sweep |
| `test_unit_parser_section_grammars.py` | `SECTION_GRAMMARS` as the oracle: columns, types, terminators, parsed values re-based to 0-based output |
| `test_unit_cordeau.py` | Cordeau MDVRP instance parsing (`CordeauParser`), data structures, and conversion to TSPLIB format |
| `test_integration_cordeau.py` | Cordeau benchmark pipeline integration through `FormatParser` and normalizers, plus `to_parse_result()` parity with the LKH file the converter writes |

A new parser test goes into exactly one file. If it fits two, it is probably two
tests.

## Changing a test

Checklist for any add, move, rename, or rewrite:

1. Name the file `test_<level>_<module>[_<concern>].py`. The level prefix is
   the only thing that decides the level marker.
2. If the file is renamed across levels, do not add a level decorator; the hook
   re-derives it.
3. Re-check the orthogonal tags against the body, not against the old file:
   corpus access → `requires_dataset`, DuckDB → `database`, `CliRunner` →
   `cli`, >1 s measured → `slow`, guards a named closed issue → `regression`.
4. Keep a WHAT / WHY / EXPECTED docstring and full annotations
   (`from __future__ import annotations`, PEP 585/604 types).
5. Use the shared fixtures in `conftest.py`; do not hardcode `datasets_raw/**`
   paths and do not call `print()`.
6. Update the tree, the counts, and the `slow` measurements in this file when
   they change.
7. Run the narrowest gate that covers the change, then the full suite once.

## Command map

```bash
# Everything (288 tests)
.venv/bin/python -m pytest -q

# Fast gate: no slow tests, no corpus dependency (156 tests, ~2 s)
.venv/bin/python -m pytest -m "not slow and not requires_dataset" -q

# Only tests that need datasets_raw/** (132 tests)
.venv/bin/python -m pytest -m requires_dataset -q

# Only the cross-package chain (1 test)
.venv/bin/python -m pytest -m e2e -q

# Scope gates
.venv/bin/python -m pytest -m unit -q
.venv/bin/python -m pytest -m integration -q
.venv/bin/python -m pytest -m cli -q
.venv/bin/python -m pytest -m database -q
.venv/bin/python -m pytest -m regression -q
.venv/bin/python -m pytest -m slow -q

# One package
.venv/bin/python -m pytest tests/tsplib_parser -q
.venv/bin/python -m pytest tests/converter -q

# Collect without running (validates naming and marker derivation)
.venv/bin/python -m pytest --collect-only -q
```

pytest is installed only in `.venv`. `pytest.ini` is the only pytest
configuration; `[tool.pytest.ini_options]` was removed from `pyproject.toml` in
the 2026-10-20 sweep. Do not add a second configuration.
