---
title: Test suite reorganization decisions
description: >
  Decision record and implementation plan for restructuring routing_data/tests:
  the target tree, filename and marker conventions, test-level classification
  rules, consolidations, disposal of dead scripts, handling of stale v1 tests
  during the ongoing refactor, batching, and verification protocol. Written so
  that a human or another agent can continue the work without re-deriving the
  analysis.
created: 2026-10-20
modifications:
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Initial evidence collection: file inventory, test-function listing,
          baseline suite run, failure attribution, module-to-test mapping,
          quality metrics, and coverage gaps.
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Rewrote the document as a decision record: removed the option
          comparisons, kept the evidence, and added the chosen layout, filename
          scheme, marker model, classification rules, batch plan, and
          verification protocol.
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Recorded Batch 1 execution: moves, merges, Cordeau split, deletions,
          instruction and README updates, the fixture defect caught during split,
          and the per-package verification counts.
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Recorded Batch 2 execution: v2 ports, single E2E test, JSON schema
          assertion, unskipped br17 baseline, salvaged corpus matrix test, and
          early marker registration. Full suite now green (278 passed).
  - date_modified: 2026-10-21
    modifications:
      - description: >
          Recorded Batch 4: warn-only level-derivation hook with its own tests,
          per-test orthogonal markers (regression scope A), marker gates, and
          README completion. Suite 287 passed, ruff clean.
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Recorded Batch 3 (full sweep): annotations, shared fixtures, tmp_path
          migration, dataset_path fixtures, print removal, raises(match=), broken
          fixture deletion, and single pytest config. Suite green, ruff clean.
  - date_modified: 2026-10-20
    modifications:
      - description: >
          Audited Batch 2 against the plan and corrected stale documentation:
          status line, baseline labeling, trees, move map, resolution markers,
          contract-test path, README test commands/counts, and the README
          implementation-status note. Recorded deferred gaps (TODO ledger,
          in_memory_db, stale nodes input, dual pytest config).
related_files:
  - [testing_instructions.instructions.md](../.github/instructions/testing_instructions.instructions.md)
  - [test.instructions.md](../.github/instructions/test.instructions.md)
  - [TODO.md](../TODO.md)
  - [conftest.py](../tests/conftest.py)
  - [pytest.ini](../pytest.ini)
tags:
  - review/test-suite
  - review/organization
  - analysis/test-inventory
  - analysis/coverage-gaps
  - analysis/refactor-impact
  - testing/pytest
  - testing/fixtures
  - testing/markers
  - testing/organization
  - notes/test-migration
  - notes/repository-structure
---

# Test suite reorganization decisions

Status: Batches 1–4 implemented on 2026-10-20/21. Batch 5 (coverage gaps) is deferred until the refactor lands.

Current state at a glance:

| Item | Value |
| --- | --- |
| Suite | 287 passed, 0 failed, 0 skipped, ~22 s (21.78–22.94 s observed) |
| Levels | 234 `unit`, 52 `integration`, 1 `e2e` (derived from filenames) |
| Orthogonal tags | 132 `requires_dataset`, 45 `database`, 21 `cli`, 9 `regression`, 2 `slow` |
| Lint | `ruff check tests` clean |
| Layout | `tests/tsplib_parser/`, `tests/converter/`, `tests/e2e/`, plus `tests/test_unit_conftest.py` for infrastructure |
| Contracts | `tests/README.md` (conventions), `pytest.ini` (single config) |

Sections 3 and 4 describe the pre-reorganization baseline and the evidence that drove each decision.
Section 10 is the execution log; where a decision changed during execution, the log records the final behaviour and section 5 has been rewritten to match it.

Scope: `routing_data/tests/**`. The `gpu_accelerated_clean` workspace folder is out of scope.

Audience: the human maintainer, or any agent asked to continue the work.
Sections 1–4 are context and evidence.
Section 5 onward is binding: do not re-open a decision without new evidence.

## 1. How to use this document

- Read sections 1–4 to understand the repository state and why the decisions exist.
- Use section 8 for the remaining batch and section 10 for what was actually executed.
  Batch boundaries are the only test-run points.
- Apply section 7 when classifying a test or naming a file.
- If a fact in section 2 or 4 is contradicted by the repository, stop and correct this document before continuing.
  Do not silently deviate.
- `src/**` is out of scope for this work.
  The refactor in progress belongs to a different task.

## 2. Repository and environment context

`routing_data` is a TSPLIB95 ETL project with two source packages:

| Package | Responsibility |
| ------- | -------------- |
| `src/tsplib_parser` | Parse TSPLIB95 files: `parser`, `matrix`, `models`, `validation`, `types`, `exceptions`, `cordeau/` adapter |
| `src/converter` | ETL pipeline: `api`, `core/scanner`, `core/transformer`, `database/operations`, `output/json_writer`, `output/parquet_writer`, `cli/commands`, `utils/*` |

Test runner:

- pytest exists only in the project virtualenv: `.venv/bin/python -m pytest`.
  The global interpreter has no pytest.
- `pytest.ini` is the only pytest configuration; the duplicate `[tool.pytest.ini_options]` block was removed from `pyproject.toml` in Batch 3.
  It sets `pythonpath = src`, `--strict-markers`, and registers the level and orthogonal markers.
- Collection uses `python_files = test_*.py`, which supports the `test_<level>_<module>.py` naming.
- Level markers are derived from filenames by `pytest_collection_modifyitems` in `tests/conftest.py`; orthogonal tags are per-test decorators.

In-progress refactor (uncommitted on branch `dev`):

- `src/tsplib_parser` moved to a v2 model: array-column output, `types.py` added, `models.py` and `validation.py` reworked.
- `src/converter` changed in `core/transformer.py`, `utils/cost.py`, `utils/parallel.py`.
- Consequence: the tests were partly on the v1 contract.
  Batches 1–2 ported them to v2; the suite is green as of 2026-10-21. The refactor itself is still in flight.

Pre-reorganization baseline measured on 2026-10-20 with `.venv/bin/python -m pytest -q`:

```text
278 collected — 271 passed, 6 failed, 1 skipped — 22.83 s
```

Current baseline measured on 2026-10-21 after Batch 4:

```text
287 passed — 0 failed, 0 skipped — 22.94 s (latest re-run)
```

The pre-reorganization `tests/` also contained three root-level scripts that contributed zero collected tests; they were deleted in Batch 1.

## 3. Pre-reorganization inventory (baseline, 2026-10-20)

The paths and counts below are historical: they are what the suite looked like
before Batch 1. For the current tree and counts, read section 10.

| File | Test functions | Module(s) under test | Current level | Status |
| ---- | -------------- | -------------------- | ------------- | ------ |
| `test_format/test_format_parser.py` | 11 | `tsplib_parser.parser` | unit, real files | pass |
| `test_format/test_matrix_equivalence.py` | 14 | `tsplib_parser.matrix` | unit, real files | 1 stale skip |
| `test_format/test_matrix_validation.py` | 14 | `tsplib_parser.matrix` | unit | pass |
| `test_format/test_matrix_value_access.py` | 12 | `tsplib_parser.matrix` | unit | pass |
| `test_format/test_parser_contract.py` | 16 | `parser`, `models`, `types`, `validation` | unit, fixtures | pass |
| `test_format/test_parser_robustness.py` | 10 | `parser`, `validation` | unit, malformed input | pass |
| `test_format/test_problem_validation_and_consistency.py` | 11 | `validation`, `parser` | unit + 239-file corpus | pass |
| `test_format/test_section_grammars.py` | 13 | `types`, `parser` | unit + corpus | pass |
| `test_converter/test_converter_api.py` | 13 | `converter.api` | integration | pass |
| `test_converter/test_cost.py` | 15 | `converter.utils.cost` | unit | pass |
| `test_converter/test_database.py` | 21 | `converter.database.operations` | unit, DuckDB | pass |
| `test_converter/test_database_connection_leak.py` | 5 | `converter.database.operations` | unit, DuckDB | pass |
| `test_converter/test_formats/test_cordeau.py` | 10 | `tsplib_parser.cordeau.*` | mixed unit + integration | pass |
| `test_converter/test_json_writer.py` | 17 | `converter.output.json_writer` | unit, files | 1 fail, stale |
| `test_converter/test_json_writing_fixes.py` | 4 | `converter.api`, `json_writer` | regression | pass |
| `test_converter/test_scanner.py` | 17 | `converter.core.scanner` | unit, tmp dirs | pass |
| `test_converter/test_transformer.py` | 11 | `converter.core.transformer` | unit | pass |
| `test_integration/test_cli.py` | 18 | `converter.cli.commands` | integration | pass |
| `test_integration/test_inspect.py` | 4 | `converter.cli.commands` | integration | pass |
| `test_integration/test_pipeline.py` | 9 | scanner + transformer + json + db | integration, v1 contract | 5 fail, stale |
| `test_edge_weights.py` | 0 | parser + transformer | manual script | uncollected |
| `test_full_pipeline.py` | 0 | parser + transformer + db | manual script | uncollected, broken |
| `verify_database.py` | 0 | production DuckDB file | manual script | uncollected, broken |
| `conftest.py` | 27 fixtures | shared | — | partially stale |

Parametrization expands the collected count beyond the function counts above (for example `test_cordeau.py` 10 functions → 22 collected, `test_section_grammars.py` 13 → 22, `test_parser_contract.py` 16 → 18).

## 4. Findings that drive the decisions

### 4.1 Six failures are stale v1 tests

Schema probe run against the current `src`:

```text
transform keys: coords, demands, depots, display_coords, edge_weight_matrix,
                edges, fixed_edges, metadata, problem_data, tours
payload keys:   adjacency, capacity, checksum, comment, coords, demands,
                depots, dimension, display_coords, display_data_type,
                edge_data_format, edge_weight_data, edge_weight_format,
                edge_weight_type, file_path, file_size, fixed_edges, name,
                node_coord_type, type
DatabaseManager: insert_problem, insert_problems_batch, get_file_info,
                get_problem_stats, query_problems, export_problem
```

| Failing test | Cause | Blame |
| ------------ | ----- | ----- |
| `test_json_writer.py::test_written_json_has_correct_structure` | Expects top-level keys `{problem, tours, metadata}`; writer now also emits array columns | Test is v1 |
| `test_pipeline.py::test_parse_and_transform_gr17` | Asserts `nodes` in transformed data; v2 emits arrays | Test is v1 |
| `test_pipeline.py::test_parse_transform_multiple_files` | Counts successes through the removed `nodes` key → 0 | Test is v1 |
| `test_pipeline.py::test_write_transformed_data_to_json` | Asserts `nodes` in JSON | Test is v1 |
| `test_pipeline.py::test_write_transformed_data_to_database` | Calls removed `DatabaseManager.insert_nodes` | Test is v1 |
| `test_pipeline.py::test_full_pipeline_scan_parse_transform_write` | Same removed `insert_nodes`; files are skipped and counted as failures | Test is v1 |

`test_database.py` and `test_database_connection_leak.py` pass.
The database layer itself is not broken; only the pipeline test that still calls the removed v1 method is.

Resolution: Batch 2 replaced these cases (section 10). The table is kept as the
worked example of the attribution rule.

### 4.2 The single skip is stale

`test_matrix_equivalence.py:256` skips with reason "BUG: Parser returns `List[List]` instead of Matrix object - needs `_create_explicit_matrix()` implementation".
The repository TODO (`B2`) states the method now exists.
The repository rule forbids bug-documenting skips; the case must be unskipped and, if it fails, fixed or deleted with evidence.

Resolution: Batch 2 unskipped and rewrote it as
`test_br17_atsp_full_matrix_matches_file`, and added the corpus-wide matrix
value check. No skip or xfail remains in `tests/**`.

### 4.3 Three root-level scripts are dead code inside `tests/`

- `test_edge_weights.py`: 262 lines, 56 `print`, 0 collected tests, hardcoded `/tmp` path, statistical sampling of matrix values.
- `test_full_pipeline.py`: 138 lines, 35 `print`, calls `insert_problem_atomic` (renamed to `insert_problem`), so it is broken.
- `verify_database.py`: 76 lines, 21 `print`, opens `datasets/db/routing.duckdb`; that path does not exist in this checkout.

Resolution: all three were deleted in Batch 1; Batch 2 salvaged the corpus
matrix assertion and replaced the pipeline script with the E2E test.

### 4.4 Duplicated fixtures and hardcoded paths

- 52 occurrences of a literal `datasets_raw/...` or `/tmp/...` path.
- Local `tmpdir` / `temp_directory` fixtures duplicate `tmp_path` and `temp_output_dir` in 8 files.
- `cli_runner` is defined identically in `test_cli.py` and `test_inspect.py`.
- `in_memory_db` in `conftest.py` is unused and unusable as written: `DatabaseManager` opens and closes a connection per method, so a `:memory:` database loses its schema between calls.
- Verified by reading `operations.py` (every method does `with duckdb.connect(...)`).

### 4.5 No markers are applied

`pytest.ini` registers four markers under `--strict-markers`, but only `parametrize` and one `skip` appear in the suite.
There is no way to select a fast gate, a dataset-free gate, or an E2E gate without listing files.

### 4.6 Mixed and oversized files

- `test_database.py` (532 lines) mixes schema creation, CRUD, query, stats, export, and file tracking.
- `test_problem_validation_and_consistency.py` (531 lines) mixes validation rules with a 239-file corpus sweep.
- `test_json_writing_fixes.py` and `test_database_connection_leak.py` are regression suites for closed issues that belong beside the module under test.

### 4.7 Error assertions are half-checked

39 `pytest.raises` blocks, 24 with `match=`.
The repository rule asks for type and message.

### 4.8 Misplaced concern

`tests/test_converter/test_formats/test_cordeau.py` tests `src/tsplib_parser/cordeau/`, not the converter package.

### 4.9 Coverage gaps confirmed by the repository ledger

No tests exist for `converter/config.py`, `converter/output/parquet_writer.py`, `converter/utils/update.py`, `converter/utils/parallel.py`, and `converter/utils/worker_functions.py`.
VRP preprocessing (`G1`), solution discovery (`G2`), parquet export (`G4`), and the update path (`G5`) are untested.
`test_process_with_force_flag` asserts a log substring rather than database state (`G6`).
These are recorded and deliberately deferred; see section 9.

## 5. Decisions

### D1 — Layout mirrors `src`, filename carries the level

Chosen tree:

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

Filename rule: `test_<level>_<module>[_<concern>].py`, where `level` is one of `unit`, `integration`, `e2e`, `performance`, and `module` is the source module name (`parser`, `matrix_formats`, `database`, `json_writer`, `cli_commands`).
The optional concern distinguishes several files for the same module.

Why: there is exactly one place to look for "where is module X tested"; the level is visible without opening the file or reading markers; no second directory tree encodes the same information; reclassification is a rename, not a move between trees, so `git log --follow` keeps per-module history.

Consequences:

- `test_converter/test_formats/test_cordeau.py` was split across the two `cordeau` files because it tests the parser package, not the converter.
- `.github/instructions/testing_instructions.instructions.md` §4 was updated in Batch 1 to the package folders and the filename rule. Its intent ("one concern, one folder") is preserved.
- `tests/README.md` records the level rule, the hook behaviour, the marker table, and the parser-file boundaries so the four `parser_*` files do not absorb each other's cases.
- `tests/test_unit_conftest.py` is the documented infrastructure exception: it tests the root `conftest.py`, which belongs to no source package.

### D2 — Cross-package E2E lives in a level folder

The full scan → parse → transform → write → DB chain is `tests/e2e/test_e2e_pipeline.py`.

Why: the chain spans both packages, so assigning it to `tsplib_parser/` or `converter/` would misstate ownership.
A dedicated level folder keeps the level taxonomy consistent.
A root-level `tests/test_e2e_pipeline.py` was rejected because the root-file pattern is exactly what produced the three dead scripts.

Inside `tests/e2e/`, the prefix is kept (`test_e2e_pipeline.py`), not dropped: one rule for every directory is easier to apply than one exception.

### D3 — Consolidation: three merges, one split, no splitting of large files yet

Merges:

- `test_database_connection_leak.py` → `test_unit_database.py`
- `test_json_writing_fixes.py` → `test_unit_json_writer.py`
- `test_matrix_equivalence.py` + `test_matrix_validation.py` → `test_unit_matrix_formats.py`

Split:

- `test_cordeau.py` → `test_unit_cordeau.py` (parser + converter classes) and `test_integration_cordeau.py` (the pipeline/JSON classes).

`test_matrix_value_access.py` stays separate: it asserts `__getitem__` semantics, a distinct concern from format/size/conversion.

`test_database.py` and `test_problem_validation_and_consistency.py` are not split now.
They are large but single-module concerns; splitting adds files without changing what is asserted.
Revisit only if they become hard to review.

### D4 — Level markers are derived; orthogonal markers are typed per test

Two axes, both implemented in Batch 4.

Axis A, level (`unit`, `integration`, `e2e`, `performance`): derived from the filename prefix by `pytest_collection_modifyitems` in `tests/conftest.py`.
Nobody types these tags; a rename re-tags automatically.
The hook:

- maps `test_unit_` → `unit`, `test_integration_` → `integration`, `test_e2e_` → `e2e`, `test_performance_` → `performance`;
- collects a file with an unrecognised prefix but emits one `PytestWarning` per file and applies no level marker (warn-only policy, chosen over failing collection);
- never adds a level marker twice;
- is tested by `tests/test_unit_conftest.py` (mapping, application, no-duplicate, one-warning-per-file).

Axis B, orthogonal traits, applied as per-test decorators (the chosen granularity):

| Marker | Current count | Applied when |
| ------ | ------------- | ------------ |
| `slow` | 2 | Measured wall time > 1 s |
| `requires_dataset` | 132 | The test opens `datasets_raw/**`, directly or through a fixture |
| `database` | 45 | The test actually opens DuckDB, including CLI, pipeline DB cases and E2E |
| `cli` | 21 | The test drives `click.testing.CliRunner` |
| `regression` | 9 | The docstring names a closed issue. Scope A: Issues #3/#4 (JSON writing, 4 tests) and #6 (connection leak, 5 tests) |
| `performance` | 0 | Registered; used only for time/resource assertions |
| `serial` | 0 | Registered; use only if xdist is introduced |

Why derived levels: typing 287 level tags by hand is the maintenance trap this reorganization exists to avoid.
Why typed orthogonal tags: whether a test needs the corpus, opens a database, or guards a specific defect is a per-test fact that no path can express, and those tags are the CI gates.
`performance` and `serial` remain registered but empty; an empty selection is expected, documented in `tests/README.md`.

### D5 — `slow` means measured > 1 s

Threshold: wall time per test greater than 1 second, measured with `pytest --durations=0`.

Measured on 2026-10-21 after Batch 3:

| Test | Time |
| ---- | ---- |
| `tests/tsplib_parser/test_unit_parser_validation.py::TestCorpusDeclaredVsExtractedConsistency::test_all_corpus_files_match_declared_types_and_dimensions` | 8.35 s |
| `tests/tsplib_parser/test_unit_matrix_formats.py::TestRealTSPLIBData::test_corpus_full_matrix_values_match_raw_sections` | 6.83 s |
| Next slowest | below 1 s |

Exactly two tests are `slow`; both carry the marker. Re-measure after any change to corpus-wide tests and update `tests/README.md`.

### D6 — Dead scripts are removed, with one assertion salvaged

- `verify_database.py`: delete. Its target database does not exist and it duplicates `converter validate` / `converter inspect`.
- `test_full_pipeline.py`: delete after the v2 E2E case exists. The E2E test is its replacement.
- `test_edge_weights.py`: salvage its only valuable idea — value checks of weight matrices across real corpus files, which today only cover `br17` — into `test_unit_matrix_formats.py` as a `requires_dataset` test. Then delete the script.

The salvage is a real coverage addition, not a mechanical port: it must assert declared dimension against extracted matrix shape and spot-check values against the raw file, not sample randomly and print.

### D7 — Stale tests: port the small cases, replace the pipeline cases

- Port the three single-component cases in `test_pipeline.py` that assert `nodes` to the v2 array-column schema.
- The two multi-file pipeline cases are deleted. Their coverage is replaced by the single E2E test, written against v2 once, not maintained twice.
- `test_json_writer.py::test_written_json_has_correct_structure` is updated to the current key set and, where possible, asserts values instead of only the key set.
- The skipped matrix case is unskipped and rewritten. If it still fails after a real investigation, it is deleted with the evidence recorded in the commit message; it is not re-skipped.
- No `xfail` for migration work. No weakened assertion to make a gate green.

Why: the refactor is still in flight, so a wholesale rewrite of the pipeline test now risks doing the work twice. Porting the three cheap cases preserves their value; collapsing the multi-file cases into one E2E avoids maintaining a test suite against two schemas.

### D8 — `tests/README.md` is the conventions document

It contains:

- The level decision rule and the filename prefix table.
- The layout tree, including the `test_unit_conftest.py` infrastructure exception.
- The hook behaviour, including the warn-only policy for unprefixed files.
- The marker table with current counts, the regression scope, and the unused markers.
- The boundaries of the four `parser_*` files.
- The command map: fast, dataset, level, cli, database, regression, slow, e2e, per-package.
- The `slow` threshold and the date of the last measurement.
- The current suite size and status.

Without it, the next edit re-merges the concerns the reorganization just separated.

## 6. Move map

| Old | New |
| --- | --- |
| `test_format/test_format_parser.py` | `tsplib_parser/test_unit_parser.py` |
| `test_format/test_parser_contract.py` | `tsplib_parser/test_unit_parser_contract.py` |
| `test_format/test_parser_robustness.py` | `tsplib_parser/test_unit_parser_robustness.py` |
| `test_format/test_problem_validation_and_consistency.py` | `tsplib_parser/test_unit_parser_validation.py` |
| `test_format/test_section_grammars.py` | `tsplib_parser/test_unit_parser_section_grammars.py` |
| `test_format/test_matrix_equivalence.py` + `test_matrix_validation.py` | `tsplib_parser/test_unit_matrix_formats.py` |
| `test_format/test_matrix_value_access.py` | `tsplib_parser/test_unit_matrix_value_access.py` |
| `test_converter/test_formats/test_cordeau.py` (parser + converter classes) | `tsplib_parser/test_unit_cordeau.py` |
| `test_converter/test_formats/test_cordeau.py` (integration class) | `tsplib_parser/test_integration_cordeau.py` |
| `test_converter/test_database.py` + `test_database_connection_leak.py` | `converter/test_unit_database.py` |
| `test_converter/test_json_writer.py` + `test_json_writing_fixes.py` | `converter/test_unit_json_writer.py` |
| `test_converter/test_converter_api.py` | `converter/test_integration_api.py` |
| `test_converter/test_scanner.py` | `converter/test_unit_scanner.py` |
| `test_converter/test_transformer.py` | `converter/test_unit_transformer.py` |
| `test_converter/test_cost.py` | `converter/test_unit_cost.py` |
| `test_integration/test_cli.py` | `converter/test_integration_cli_commands.py` |
| `test_integration/test_inspect.py` | `converter/test_integration_cli_inspect.py` |
| `test_integration/test_pipeline.py` (component cases) | `converter/test_integration_pipeline.py` (ported to v2) |
| `test_integration/test_pipeline.py` (full chain) | `e2e/test_e2e_pipeline.py` (rewritten as one E2E test) |
| `test_edge_weights.py`, `test_full_pipeline.py`, `verify_database.py` | deleted (salvage per D6) |
| (new, not a move) | `test_unit_conftest.py` — tests the root conftest hook |

## 7. Classification rules

### 7.1 Test level

| Level | Rule | Edge cases resolved by this rule |
| ----- | ---- | -------------------------------- |
| `unit` | Exactly one `src` module under test. `tmp_path` and a local DuckDB file are allowed. | `json_writer` is unit although it writes files; `database` is unit although it opens DuckDB; `matrix` is unit although some cases read corpus files (they also carry `requires_dataset`). |
| `integration` | Two or more `src` modules composed, a CLI runner, or an adapter whose job is composition. | `SimpleConverter.parse/to_json` is integration (parser + transformer + writer); CLI tests are integration; Cordeau adapter cases are integration. |
| `e2e` | The full scan → parse → transform → write → DB chain across packages. | Only the pipeline test. |
| `performance` | Asserts on time or resources. | No current case; do not use it as a synonym for "slow". |

### 7.2 Boundaries of the four parser test files

| File | Owns | Does not own |
| ---- | ---- | ------------ |
| `test_unit_parser.py` | Public `FormatParser.parse_file` behavior on real corpus files: structure, metadata, declared dimensions, coordinate and matrix values | Malformed input (robustness), cross-field invariants (validation), section grammar oracle (section grammars) |
| `test_unit_parser_contract.py` | Behavioral contracts: comments in sections, duplicate keys, `EDGE_WEIGHT_FORMAT: FUNCTION`, unregistered/stripped sections, temporary-file isolation, removed legacy parser, callable naming, coordinate-dimension validation | Whole-file rejection of corrupted sections (robustness) |
| `test_unit_parser_robustness.py` | Malformed section content must fail loudly; exception-type contract; structural violations; real-world format variants (tab-separated, `FIXED_EDGES :`, adjacency lists) | Declared-vs-extracted validation rules (validation) |
| `test_unit_parser_validation.py` | `validate_problem_data` / `validate_parse_result` rules and the 239-file declared-vs-extracted sweep | Section-level line grammar (section grammars) |
| `test_unit_parser_section_grammars.py` | `SECTION_GRAMMARS` as the oracle: columns, types, terminators, parsed values re-based to 0-based output | Any rule not expressed in the grammar table |

A new parser test goes into exactly one of these, chosen by the table. If it fits two, the assertion is probably two assertions.

### 7.3 Marker application

Implemented policy (Batch 4): orthogonal tags are **per-test decorators**, because the trait is a property of the individual test, not of the file. Counts are recorded in D4 and `tests/README.md`.

- Apply `slow` from measurement only. Record the measurement and date in `tests/README.md`.
- Apply `requires_dataset` when the test opens `datasets_raw/**`, directly or through a fixture. At the time of writing: 132 tests.
- Apply `database` when the test actually opens DuckDB, including CLI and pipeline cases. At the time of writing: 45 tests.
- Apply `cli` when the test drives `CliRunner`. At the time of writing: 21 tests.
- Apply `regression` only when the docstring names a closed issue. Scope A: Issues #3/#4 and #6, 9 tests. Parser PB contracts and the br17 baseline are deliberately excluded.
- Do not apply `fast`; it is the complement of `slow`.
- Do not invent module markers (`parser`, `matrix`); the path and filename already carry that information.
- `performance` and `serial` stay registered but empty until a test needs them.

## 8. Implementation batches

Batches 1–4 are executed; the outcomes are in section 10. Batch 5 remains.

Only batch boundaries trigger test runs. Do not run pytest after an individual move, rename, or import fix.

### Batch 1 — Structure

Work:

1. Create `tests/tsplib_parser/`, `tests/converter/`, `tests/e2e/`, and `__init__.py` only if a duplicate module basename would otherwise collide.
2. Execute the move map, with `git mv` where possible to preserve history.
3. Split `test_cordeau.py`; merge the three pairs.
4. Delete the three dead scripts. Do not salvage yet; that is Batch 2.
5. Update `.github/instructions/testing_instructions.instructions.md` §4 to the new folders and filename rule.
6. Create `tests/README.md` skeleton (taxonomy text can be filled in Batch 4).

Verification, once each:

```bash
.venv/bin/python -m pytest tests/tsplib_parser -q
.venv/bin/python -m pytest tests/converter -q
.venv/bin/python -m pytest tests/e2e -q
```

Expected: the same pass/fail counts as the baseline for each moved file.
An import or collection error here is a migration fault: fix the path, never the assertion.

### Batch 2 — Stale tests

Work:

1. Port the three single-component pipeline cases to v2 (`coords`, `demands`, `depots`, `insert_problem`).
2. Write `tests/e2e/test_e2e_pipeline.py` as the single cross-package E2E case.
3. Delete the two multi-file pipeline cases.
4. Update the JSON writer key-set assertion to the current schema, asserting values where possible.
5. Unskip and rewrite the matrix explicit-matrix case.
6. Salvage the corpus matrix-value check from `test_edge_weights.py` into `test_unit_matrix_formats.py`.

Verification, once:

```bash
.venv/bin/python -m pytest tests/e2e tests/tsplib_parser/test_unit_matrix_formats.py -q
.venv/bin/python -m pytest tests/converter/test_unit_json_writer.py -q
```

Expected: zero failures. If a port fails, determine whether the schema changed again (refactor fault) or the port is wrong (migration fault). Do not weaken the assertion.

### Batch 3 — Fixtures and quality

Work:

1. Move shared fixtures into `conftest.py`; remove local `tmpdir`, `temp_directory`, and the duplicate `cli_runner`.
2. Replace `print()` in live tests with assertions or `logging`.
3. Add `match=` to the 15 `pytest.raises` blocks that assert type only, where the message is part of the contract.
4. Fix or delete `in_memory_db` (per-method connections make `:memory:` unusable).
5. Remove the duplicate pytest configuration (keep `pytest.ini`, delete `[tool.pytest.ini_options]`, or the reverse; one file must win explicitly).
6. Replace hardcoded `datasets_raw/...` paths with fixtures. `/tmp` paths become `tmp_path`.

Verification, once on the touched files:

```bash
.venv/bin/python -m pytest <touched paths> -q
```

### Batch 4 — Markers and documentation

Work:

1. Add the level-derivation hook and its test to `tests/conftest.py`.
2. Register `slow`, `requires_dataset`, `regression`, `cli`, `database`, `performance`, `serial` in `pytest.ini`.
3. Apply orthogonal tags per section 7.3, using the `--durations=0` data.
4. Complete `tests/README.md`.

Verification, once each:

```bash
.venv/bin/python -m pytest --collect-only -q
.venv/bin/python -m pytest -m "not slow and not requires_dataset" -q
.venv/bin/python -m pytest -m requires_dataset -q
.venv/bin/python -m pytest tests/e2e -q
```

### Batch 5 — Coverage (separate task)

Only after the refactor lands. Add tests for `config`, `parquet_writer`, `update`, `parallel`, `worker_functions`, VRP preprocessing (`G1`), and solution discovery (`G2`).
Each gets its own new-file and baseline; none is part of the reorganization.

## 9. Verification, attribution, and risks

Verification summary (2026-10-21, after the Batch 4 review pass):

| Gate | Command | Result |
| ---- | ------- | ------ |
| Full suite | `.venv/bin/python -m pytest -q` | 287 passed, 0 failed, 0 skipped, 22.94 s |
| Hook tests | `.venv/bin/python -m pytest tests/test_unit_conftest.py -q` | 9 passed |
| Lint | `.venv/bin/ruff check tests` | All checks passed |
| Fast gate | `-m "not slow and not requires_dataset"` | 155 passed, ~1.8 s |
| Dataset gate | `-m requires_dataset` | 132 passed, ~19.8 s |
| E2E + regression | `-m "e2e or regression"` | 10 passed, ~1.0 s |

Attribution rule after a structural batch:

- Import error, collection error, fixture not found, duplicate module basename: migration fault. Fix the path or `conftest.py`; the test body is not the cause.
- Failure against `nodes` or `insert_nodes`, or a JSON key set containing array columns: refactor fault. The baseline at `HEAD` proves it predates the move.
- A test that passed before the move and whose body was not edited must pass after it. If it does not, the move is wrong.

Risks and open facts:

- The refactor is in flight. The v2 schema may change again; the Batch 2 ports are intentionally minimal for that reason.
- Per-test orthogonal tags are typed by hand; if a test body starts opening the corpus or DuckDB, its marker must be updated manually. The rules are in section 7.3.
- `tests/tsplib_parser/test_unit_cordeau.py` and `tests/tsplib_parser/test_integration_cordeau.py` depend on `datasets_raw/umalaga/mdvrp/C-mdvrp`; they carry `requires_dataset` (and the integration file also `database`).
- `performance` and `serial` are registered but unused. An empty selection is expected, not a defect.
- Coverage gaps (section 4.9) remain open by design; they are Batch 5 and are not a reason to delay Batches 1–4, which are complete.
- The historical ledgers (root `TODO.md`, `src/*/TODO.md`, `.agents/skills/plan-routing-schema-v2/SKILL.md`) still reference retired paths and stale findings; they are dated records, not live test documentation.

## 10. Execution log

### Batch 1 — completed 2026-10-20

- Created `tests/tsplib_parser/`, `tests/converter/`, `tests/e2e/`; removed the three old folders.
- Moved 17 test modules per the section 6 map, preserving tracked files with `git mv` and moving the four untracked modules with `mv`.
- Merged the three pairs and split Cordeau into unit + integration. Bodies were carried over verbatim; only module docstrings and import blocks were reconciled. Collected count is unchanged (278), which is the check that no test was dropped or duplicated.
- Deleted `test_edge_weights.py`, `test_full_pipeline.py`, `verify_database.py`, and `test_converter/test_formats/__init__.py`.
- Updated `.github/instructions/testing_instructions.instructions.md` §4 and created `tests/README.md`.
- One defect introduced during the split was caught and fixed: the `format_parser` fixture was dropped from the integration file, producing 12 fixture errors. Restored; parser package then green.

Verification, one run per package:

```text
tests/tsplib_parser   144 passed, 1 skipped
tests/converter       124 passed, 1 failed
tests/e2e               3 passed, 5 failed
total                 278 collected — 271 passed, 6 failed, 1 skipped
```

The six failures are the same six as the pre-move baseline, with the same
causes (section 4.1). No migration fault remains.

Next: Batch 2 (section 8).

### Batch 2 — completed 2026-10-20

- Ported the parser→transformer, JSON writer and database cases to the v2
  schema in a new `tests/converter/test_integration_pipeline.py`. This is a
  deliberate refinement of the move map: those cases compose two modules but
  are not the full chain, so they are integration-level and cannot live in
  `tests/e2e/`. The e2e folder now holds only the cross-package chain.
- Rewrote `tests/e2e/test_e2e_pipeline.py` as one test: copy `gr17.tsp` and
  `berlin52.tsp` into a temp dir, scan → parse → transform → JSON + DuckDB,
  then assert both outputs and the loaded rows.
- Deleted the two multi-file pipeline cases
  (`test_parse_transform_multiple_files`, `test_full_pipeline_scan_parse_transform_write`)
  and their swallowed exceptions.
- Updated the JSON writer structure test to the exact v2 key set and value
  assertions (gr17 has `coords is None`, `tours == []`).
- Unskipped the br17 baseline as `test_br17_atsp_full_matrix_matches_file`
  (`FullMatrix`, size 17, first row and spot values).
- Salvaged the deleted script's only unique assertion as
  `test_corpus_full_matrix_values_match_raw_sections`: for all 21
  EXPLICIT/FULL_MATRIX corpus files, size and every flattened value equal the
  raw `EDGE_WEIGHT_SECTION`. Measured 7.81 s, so it carries `slow` and
  `requires_dataset`.
- Registered the marker set in `pytest.ini` (required by `requires_dataset`
  under `--strict-markers`). Batch 4 still owns the derivation hook and the
  remaining tag application.

Verification:

```text
touched files      57 passed
full suite        278 passed in 24.73 s — 0 failed, 0 skipped
```

Next: Batch 3 (fixtures and quality).

### Batch 2 audit vs plan (2026-10-20)

Plan items, checked one by one:

| Section 8 Batch 2 item | Status | Evidence |
| --- | --- | --- |
| Port the three single-component pipeline cases to v2 | done | `tests/converter/test_integration_pipeline.py` |
| Write the cross-package E2E | done | one test in `tests/e2e/test_e2e_pipeline.py` |
| Delete the two multi-file pipeline cases | done | not present; no `insert_nodes` call remains |
| Update the JSON writer key-set assertion | done | exact v2 key set plus value assertions |
| Unskip and rewrite the matrix case | done | `test_br17_atsp_full_matrix_matches_file`; no skip/xfail in `tests/**` |
| Salvage the corpus matrix check | done | 21 FULL_MATRIX files, value-for-value; `slow` + `requires_dataset` |

Documentation gaps found during the audit and fixed:

- The status line still claimed that no file had been moved; it now records
  Batches 1–2 as implemented.
- Section 3 was titled "Current test inventory" but listed pre-move paths; it is
  now explicitly labeled as the baseline, with a pointer to section 10.
- The D1 tree and `tests/README.md` tree omitted
  `converter/test_integration_pipeline.py`; both now include it.
- The move map still showed a single destination for `test_pipeline.py`; it now
  records the split into component cases and the E2E chain.
- Findings 4.1–4.3 had no resolution markers; each now points to the Batch 2
  outcome. The risks list no longer claims five tests are red or names the old
  Cordeau path.
- `tests/README.md` described the level-marker hook as if it existed. It now
  states that Batches 1–2 are done, that the hook and most tags are Batch 4 work,
  and that only `slow` + `requires_dataset` are currently applied.
- `tests/tsplib_parser/test_unit_parser_contract.py` still named
  `tests/test_format/` in its module docstring; corrected.
- The root `README.md` advertised 134 tests and the retired `tests/test_format/`,
  `tests/test_converter/`, `tests/test_integration/` commands; corrected to 278
  tests, 146 / 131 / 1 per package, with coverage figures labeled as not re-measured. Two further status lines still said 134/134 and were corrected.
- `.github/instructions/test.instructions.md` had `applyTo: 'tests/*.py'`. Now that every test lives in a subfolder, that pattern matched nothing; it is broadened to `tests/**/*.py`.

Known gaps, deliberately deferred and recorded here so they are not lost:

- `src/tsplib_parser/TODO.md` is a dated ledger (2026-10-14). It still names
  `tests/test_format/`, and its `PB2` stale-skip item, `PP7` skip item and
  `PB14` ruff-debt item are affected by this work (PB2/PP7 are now resolved,
  PB14 remains open). Update it in Batch 5 or a separate ledger pass; it is not
  a test file.
- The root `TODO.md`, `src/converter/TODO.md`, and `.agents/skills/plan-routing-schema-v2/SKILL.md` still reference the retired `tests/test_*` paths. They are historical records of earlier passes, not live test documentation; leave them unless a ledger-cleanup task is opened.
- `tests/conftest.py::in_memory_db` — closed in Batch 3: the fixture was removed
  (per-method connections make `:memory:` unusable).
- The v1 `"nodes": []` input in `test_write_problem_with_missing_fields` — closed
  in Batch 3: replaced with the `coords` array column.
- The full `pytest.raises(match=...)` sweep — closed in Batch 3: 15 bare raises
  now assert message content. Level-marker derivation and the remaining tags are
  still Batch 4.
- The duplicate pytest configuration — closed in Batch 3: `[tool.pytest.ini_options]`
  was removed from `pyproject.toml`; `pytest.ini` is the only config.
- No test run was added beyond the batch boundary; no per-edit runs were made.

### Batch 3 — completed 2026-10-20

Full sweep across the test tree, as authorized:

- Annotations: every test function and fixture now has parameter and return
  annotations (PEP 585 built-in generics, no `typing.List`/`Optional`); module
  files that only use a type in annotations use
  `from __future__ import annotations` plus a `TYPE_CHECKING` block.
- Fixtures: `tmpdir`/`temp_directory` local fixtures removed; tests use the
  builtin `tmp_path: Path`. The one remaining `temp_directory` fixture builds
  its files on `tmp_path` rather than calling `tempfile.mkdtemp`.
- Shared fixtures: `dataset_path`, `datasets_raw_dir`, `tsp_dir`,
  `berlin52_tsp`, `br17_atsp`, `ft53_atsp`, `ft70_atsp`,
  `cordeau_mdvrp_dir`, and `cli_runner` live in `conftest.py`. The duplicated
  `cli_runner` and local `test_data_dir` shadowing in the CLI suite are gone.
- Dataset paths: zero `datasets_raw` literals outside `conftest.py`. Cordeau
  suites use `cordeau_mdvrp_dir`; TSP/ATSP cases use `dataset_path(...)` or the
  named fixtures.
- `print()` in live tests: zero. The ATSP asymmetry test now asserts every file
  was checked instead of printing a summary.
- `pytest.raises`: all 15 bare calls now assert message content via `match=`.
- `in_memory_db`: deleted (unusable with per-method connections).
- `pyproject.toml`: duplicate `[tool.pytest.ini_options]` removed; `pytest.ini`
  is the only pytest configuration.
- `pytest.ini` marker registry retained from Batch 2.
- `ruff check tests` is clean (was 105 findings, including 85 missing
  annotations, 9 unused variables, 4 unused imports, one hardcoded `/tmp`).

Verification, one run at the batch boundary:

```text
278 passed in 20.59 s — 0 failed, 0 skipped
ruff check tests: All checks passed!
```

Acceptance metrics:

| Check | Result |
| --- | --- |
| `print()` in tests | 0 |
| local `tmpdir` fixtures | 0 |
| `cli_runner` definitions | 1 (conftest) |
| `pytest.raises` without `match=` | 0 |
| `datasets_raw` literals outside conftest | 0 |
| duplicate pytest config blocks | 0 |
| ruff findings in `tests/` | 0 |

Next: Batch 4 (marker derivation hook, remaining tags, README completion).

### Batch 4 — completed 2026-10-21

Decisions applied:

- Hook: `level_marker_for()` plus `pytest_collection_modifyitems` in
  `tests/conftest.py`. Known prefixes map to `unit`, `integration`, `e2e`,
  `performance`. An unprefixed file is collected, emits one `PytestWarning`, and
  receives no level marker (warn-only, per the chosen policy). An explicit
  marker is never duplicated.
- Hook tests: `tests/test_unit_conftest.py` (9 tests: 6 mapping cases, marker
  application, no-duplicate rule, one-warning-per-file rule). This is the
  documented infrastructure exception to "no root-level test files".
- Orthogonal tags are per-test decorators, as chosen. Counts after application:

```text
unit 234, integration 52, e2e 1
requires_dataset 132, database 45, cli 21, regression 9, slow 2
performance 0, serial 0 (registered, unused)
```

- `regression` scope is A: the merged JSON-fix classes (Issues #3/#4, 4 tests)
  and the connection-leak class (Issue #6, 5 tests). Parser PB contracts and the
  br17 baseline are deliberately not tagged.
- `slow` re-measured on 2026-10-21: 239-file corpus sweep 8.35 s, corpus matrix
  value check 6.83 s. Both carry `slow`; the matrix test already carried it.
- `database` covers every test that actually opens DuckDB (unit database suite,
  CLI process/analyze/validate, inspect except `--help`, the pipeline DB case,
  the Cordeau full-pipeline case, and the E2E test). `cli` covers both CLI
  suites.

Verification:

```text
fast gate  -m "not slow and not requires_dataset"   155 passed in 1.78 s
dataset    -m requires_dataset                      132 passed in 19.82 s
e2e+reg    -m "e2e or regression"                    10 passed in 1.03 s
full suite                                           287 passed in 21.78 s
ruff check tests                                     All checks passed
```

Documentation: `tests/README.md` now records the implemented tree
(including `test_unit_conftest.py`), the hook behavior, per-test tag policy,
regression scope, updated `slow` measurements, current counts, and the expanded
command map. Root `README.md` counts updated to 287.

### Batch 4 review pass — 2026-10-21

Self-review against `code-review-and-quality` (correctness, readability,
architecture, security, performance) before closing the batch.

Defect found and fixed (correctness): the hook's warn-once bookkeeping keyed on
`item.path.name`, so two unprefixed files with the same basename in different
directories would warn once instead of twice, and the second file's warning
would be suppressed by an unrelated file. The key is now the full
`item.path`. `tests/test_unit_conftest.py` already exercises the one-warning
rule per path.

Second defect found and fixed (quality gate): `ruff check tests` reported two
findings in `tests/test_unit_conftest.py` — an unsorted import block (I001) and a
standard-library import that belongs in `TYPE_CHECKING` (TC003). Both are fixed;
the lint gate is now genuinely clean, which the Batch 4 entry above had claimed
prematurely.

Re-verification after both fixes: hook tests 9 passed, full suite 287 passed in
22.94 s, `ruff check tests` clean.

Documentation corrections made in the same pass:

- Sections 5 (D1/D4/D5/D8), 6, 7.3, 8 and 9 were rewritten from future tense to
the implemented behaviour, with the current counts and the 2026-10-21 `slow`
measurements.
- The "ignore unknown prefix" wording in D4 was corrected to the actual
warn-only policy.
- The move map gained the `test_unit_conftest.py` row; the risk list lost the
resolved duplicate-config and untagged-Cordeau items.

Next: Batch 5 (coverage gaps), a separate task after the refactor.
