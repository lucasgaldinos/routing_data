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
  - date_modified: 2026-10-24
    modifications:
      - description: >
          Recorded step A2: added test_unit_solutions.py to the tree and its
          boundary row, refreshed suite and marker counts (353 passed, 6
          xfailed; 359 collected) and the command map, and documented the
          vocabulary drift guard that compares converter/types.py with the
          stored CHECK expressions.
      - description: >
          Recorded step A3: extended test_unit_solutions.py with the linking
          coverage (discovery from a problem path, stem-based linking, ambiguity
          refusal) and refreshed counts to 368 passed / 374 collected.
  - date_modified: 2026-10-26
    modifications:
      - description: >
          Added regressions for M10 (test_to_json_bare_filename_without_dir),
          M1 (test_analyze_handles_null_edge_weight_type), M2 (test_write_problem_prevents_path_traversal),
          and m2 (test_process_with_zero_workers_fails). Un-xfailed test_json_carries_the_explicit_matrix (F8/CV9 item 4).
          Resolved Objective 4 Gap 1: expanded DuckDB problems.type CHECK constraint to admit all 53 STORABLE_PROBLEM_TYPES,
          preserving hub problem identity while routing physical storage via _TYPE_TO_STORAGE; un-xfailed test_extended_type_keeps_its_identity.
          Refreshed test count: 406 collected (402 passed, 4 xfailed).
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
    ├── test_unit_solutions.py
    ├── test_unit_cost.py
    ├── test_unit_database.py
    ├── test_unit_json_writer.py
    ├── test_integration_api.py
    ├── test_integration_cli_commands.py
    ├── test_integration_cli_inspect.py
    ├── test_integration_pipeline.py
    ├── test_integration_schema_contract.py
    ├── test_integration_type_coverage.py
    ├── test_integration_output_contract.py
    └── test_integration_batch_accounting.py
```

`tests/test_unit_conftest.py` is the documented infrastructure exception: it
tests the root `conftest.py` (the marker hook and its mapping), which belongs to
no source package.

Current state (2026-10-24): Batches 1–4 of the reorganization are done
(structure, fixtures/quality, annotations, marker hook and tags). Batch 5
(coverage gaps) is pending. Suite: **368 passed, 6 xfailed, 0 failed, 0 skipped**, ~25 s;
`ruff check tests` clean. Levels: 276 `unit`, 97 `integration`, 1 `e2e`.

The solution-parser tests (`test_unit_solutions.py`, 13 tests) that arrived with
step A2 are the first ones written against the new `converter/core/solutions.py`
layer; the old `DataTransformer` solution methods they will replace are still
covered by `test_unit_transformer.py` until the deletion in A4.

The 6 `xfailed` tests are deliberate: they pin a defect that is registered in
`TODO.md` / `src/converter/TODO.md` and marked `strict=True`, so the day the
defect is fixed the suite turns **red** until the test is updated. They are the
red-to-green targets for the converter rework (register items B1, B3, M12, CV9).
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
| `requires_dataset` | The test opens files under `datasets_raw/**`, directly or through a fixture | 162 tests |
| `regression` | The test guards a specific fixed defect named in the docstring | 9 tests: Issues #3/#4 and #6 |
| `cli` | The test drives `click.testing.CliRunner` | 21 tests |
| `database` | The test opens a DuckDB database | 85 tests |
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

### Converter characterization suite (added 2026-10-23)

These four files pin the write path before the converter rework touches it. They
are the contract every later change must keep or consciously amend.

| File | Owns |
| ---- | ---- |
| `test_integration_schema_contract.py` | The schema as a published artifact: all nine tables, column order, column types, nullability, the `problems.type` CHECK (admits 5, refuses `TOUR`/extended LKH-3), `UNIQUE (name, type)`, and the `solutions` constraints (`kind` and `quality` domains, `routes NOT NULL`, unique `source_file`, orphan rows allowed) |
| `test_integration_type_coverage.py` | One real corpus file per admitted type through worker → batch insert → read-back (type, dimension, payload); the declared-but-refused types as explicit known gaps |
| `test_integration_output_contract.py` | JSON document key set and values; parquet equals one file per table (nine, including `solutions`) with row counts matching the tables; JSON ↔ DB identity parity |
| `test_integration_batch_accounting.py` | Inputs equal inserted + failed + skipped; a refused sibling must not remove stored problems; an empty payload must be counted, not skipped |

### Solution parsing (added 2026-10-24, step A2)

| File | Owns |
| ---- | ---- |
| `test_unit_solutions.py` | `converter.core.solutions`: `parse_solution_file` for both shipped formats — `*.opt.tour` (single cycle, cost from the `COMMENT` parenthesis, `-1` terminator, missing/empty `TOUR_SECTION`) and `*.sol` (`Route #k : ...` with wrapped lines, `Cost` line incl. sign and exponent, file with no routes), unknown suffix, zero-based node ids rejected, non-UTF-8 bytes read as latin-1 — plus two corpus sweeps (82 tours, 390 `.sol`) asserting contiguity; and linking: `candidate_solution_files` (sibling `.sol`, `tour/` cousin, no tour for a route instance, both when both exist, none when none exists, corpus coverage 390/390 and 82/82) and `link_solution` (single match, `no_instance`, `ambiguous` with both ids, case-insensitive stem) |

The vocabulary in `converter/types.py` is checked against the database by
`test_solution_vocabularies_match_the_database` (in the schema contract file):
it reads `duckdb_constraints().expression` and compares the admitted literals with
`SOLUTION_KINDS` / `SOLUTION_QUALITIES`, so a value added on one side only fails.

An `xfail(strict=True)` in these files is a **registered defect**, not a tolerated
failure: the reason string names the register ID (`B1`, `B3`, `M12`, `CV9`), and
fixing the defect makes the suite fail until the test is rewritten to assert the
new behaviour.

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
# Everything (374 tests)
.venv/bin/python -m pytest -q

# Fast gate: no slow tests, no corpus dependency (212 tests, ~2 s)
.venv/bin/python -m pytest -m "not slow and not requires_dataset" -q

# Only tests that need datasets_raw/** (162 tests)
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

pytest is installed only in `.venv`. `[tool.pytest.ini_options]` in
`pyproject.toml` is the only pytest configuration.
