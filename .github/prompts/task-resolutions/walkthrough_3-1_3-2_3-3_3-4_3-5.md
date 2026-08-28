---
title: "Walkthrough: Tasks 3.1–3.5 — Worker Payload + Database Schema, Batch Insert, Query API"
task_id: "3.1-3.2-3.3-3.4-3.5"
description: >
  Batch 3 (highest-effort) of the Routing_data database rebuild: switched the
  worker payload from matrix_json/dimension to a nested-list matrix and added
  edges/fixed_edges (Decisions #2/#4, Task 3.1); added NotFoundError (Decision
  #7, Task 3.2); changed the DDL for problems + edge_weight_matrices (Tasks 3.3);
  replaced the name-keyed join with a temp_id-keyed INSERT…RETURNING mapping and
  added name disambiguation + graph columns (Decision #10, Task 3.4); and added
  load(name,type)/load_matrix + retired the three dead single-insert methods
  (Decisions #7/#8, Task 3.5).
created: "2026-08-27"
author:
  - "[[Lucas Galdino]]"
status: "in-review"
tags: [guide/database, benchmark/etl, notes/routing-data, analysis/duckdb, algorithm/tsplib, algorithm/hcp, algorithm/vrp]
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
  - "[knowledge_duckdb-returning-source-columns.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_duckdb-returning-source-columns.md)"
---

# Walkthrough: Tasks 3.1–3.5 — Worker + Database Batch

## Objective

Emit the new worker payload (`matrix` nested list + `edges`/`fixed_edges`,
Decision #2/#4), add `NotFoundError` (Decision #7), reshape the DuckDB DDL
(Decision #1/#2/#3), rebuild the batch-insert to a temp_id-keyed mapping with
name disambiguation and graph columns (Decision #10), and expose an
ambiguity-free `load(name, type)` loader while retiring the dead single-insert
paths (Decisions #7/#8). Edits confined to three files; `parser.py`,
`transformer.py`, `insert_problem`, `insert_nodes`, and `api.py` untouched.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| Worker (edited) | [worker_functions.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py) | Previously serialized `matrix_json` + `dimension`; dropped `edges`/`fixed_edges`; did not pass `problem_dimension` to the tour parse. |
| Exceptions (edited) | [exceptions.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py) | No not-found type; `load` needed a distinct domain exception (Decision #7). |
| Database ops (edited) | [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py) | Old schema had `matrix_json`+`dimension`; batch insert joined on `name` (att48/eil51/gil262/lin318 node cross-contamination); no `load`. |
| Transformer (read-only, Batch 2) | [transformer.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py) | `transform_problem` emits top-level `edges`/`fixed_edges` and `edge_weight_matrix` (full n×n); `parse_solution_data(..., problem_dimension=...)`. |
| Parser (read-only, Batch 1) | [parser.py L156-166](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L156) | Top-level `edges`/`fixed_edges` keys on the parse result. |
| Decision pin | [plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md) | Decisions #1/#2/#3/#4/#7/#8/#10. |
| Data | `datasets/problems/tsp/bayg29.tsp` | EXPLICIT TSP: worker should emit `matrix` (no `matrix_json`/`dimension`). |
| Data | `datasets/problems/hcp/alb1000.hcp` | HCP: worker emits `edges` (adjacency), no matrix. |
| Data | `datasets/problems/tsp/linhp318.tsp` | Declares `NAME: lin318`; `FIXED_EDGES_SECTION` → `fixed_edges == [[0, 213]]`. |

## Impact Analysis / Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Worker matrix (Task 3.1) | `edge_weight_data = {'matrix': matrix, 'matrix_format': ..., 'is_symmetric': ...}`; drop `matrix_json`/`dimension` | Decision #2. The nested list is the storage-native form; dropping `dimension` removes the redundant copy (matrix size is the dimension). |
| Problem dimension thread (Task 3.1) | `problem_dimension = transformed_data['problem_data'].get('dimension')` passed to `parse_solution_data` | Decision #6 — enables the Batch-2 tour DIMENSION pre-inject. |
| NotFoundError (Task 3.2) | New subclass with optional `name`/`type`, exported in `__all__` | Decision #7 — "zero rows" is a domain not-found, distinct from `DatabaseError`. |
| DDL (Task 3.3) | `problems` += `tsplib_name`, `fixed_edges`, `adjacency` + `UNIQUE(name, type)`; `edge_weight_matrices` `matrix INTEGER[][]` replaces `matrix_json`+`dimension` | Locked topology in TODO; graph columns hold HCP adjacency / fixed arcs; `UNIQUE(name,type)` makes `load` ambiguity-free. |
| Mapping key (Task 3.4) | `temp_id`-keyed mapping built from `INSERT … RETURNING id` zipped to `temp_id` by source row order | Decision #10. Removes the name-keyed join that cross-contaminated shared `name` rows across types. |
| RETURNING syntax (Task 3.4) | Used the documented **fallback** (`RETURNING id` zipped to temp_id by row order) | The installed DuckDB 1.5.5 rejects the pinned subquery `FROM (INSERT … RETURNING src_cols)` AND source-column RETURNING for non-selected columns; the fallback is authorized by Decision #10. |
| Name disambiguation (Task 3.4) | Post-collect pass: for duplicate `(name, type)` where file stem ≠ name, rewrite `name`=stem and set `tsplib_name`=original | TODO "name twins" rule; keeps cross-type twins (att48 as TSP and CVRP) unchanged (type disambiguates). |
| Loader (Task 3.5) | `load(name, type)` (both required, raise `NotFoundError` on 0 rows) + `load_matrix(name, type)` returning nested list | Decision #7/#8. `UNIQUE(name,type)` guarantees at most one match. |
| Dead paths (Task 3.5) | Deleted `insert_edge_weights`, `_insert_problem_internal`, `insert_problem_atomic` | Decision #8 — they encode the old `matrix_json`/`dimension` schema and are unused by the batch path. |

## Failure / Correction Log

| Attempt | Evidence | Correction |
| --- | --- | --- |
| Pinned subquery syntax `FROM (INSERT … RETURNING …) p` | DuckDB 1.5.5: `ParserException: syntax error at or near "INTO"` | Moved to the Decision #10 fallback: `RETURNING id` captured in python, zipped to `temp_id` by source order. |
| Source-column `RETURNING problems.id, problems_temp.temp_id` | `BinderException: Referenced table "problems_temp" not found`; unqualified `temp_id` → `not found in FROM clause` (only SELECT-output columns are referenceable) | `temp_id` is not in the INSERT target, so it cannot be a RETURNING binding; fallback path confirmed correct via sandbox. |
| Registered-DataFrame source in RETURNING | `Referenced table not found` for a `conn.register` view | `RETURNING id` works against a registered DataFrame (verified); only source-column references need a real table. |

## Affected Files (Detailed)

### python — `src/converter/utils/worker_functions.py`

1. [worker_functions.py L4](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L4) — removed now-unused `import json`.
2. [worker_functions.py L73-76](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L73) — thread `problem_dimension` into `parse_solution_data`.
3. [worker_functions.py L80-88](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L80) — `edge_weight_data` now `{matrix, matrix_format, is_symmetric}` (dropped `dimension`/`matrix_json`).
4. [worker_functions.py L98-100](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L98) — result gains `edges`/`fixed_edges` top-level keys.

### python — `src/converter/utils/exceptions.py`

1. [exceptions.py L252](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py#L252) — new `NotFoundError(ConverterError)` with optional `name`/`type` context.
2. [exceptions.py L315](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py#L315) — exported in `__all__`.

### python — `src/converter/database/operations.py`

1. [operations.py L9](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L9) — import `NotFoundError`.
2. [operations.py L41-67](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L41) — `_initialize_schema`: `problems` gains `tsplib_name`, `fixed_edges`, `adjacency`, `UNIQUE (name, type)`.
3. [operations.py L99](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L99) — `edge_weight_matrices` replaced `matrix_json`+`dimension` with `matrix INTEGER[][]`.
4. [operations.py L299](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L299) — `insert_problems_batch` rewritten: temp_id-keyed mapping, name disambiguation, graph columns, matrix insert.
5. [operations.py L591](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L591) — new `load(name, type)` raising `NotFoundError`.
6. [operations.py L625](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L625) — new `load_matrix(name, type)` returning a nested list.
7. Deleted methods (removed by line-boundary splice, ~235 lines): `insert_edge_weights`, `_insert_problem_internal`, `insert_problem_atomic`.

`insert_problem`, `insert_nodes`, and `api.py` are untouched (out of scope, deferred).

## Change Checklist

- [x] 3.1 — `edge_weight_data` uses nested-list `matrix` (no `matrix_json`/`dimension`); result carries `edges`/`fixed_edges`; `problem_dimension` threaded to tour parse.
- [x] 3.2 — `NotFoundError(ConverterError)` with optional `name`/`type`; exported in `__all__`.
- [x] 3.3 — DDL: `problems` +`tsplib_name`/`fixed_edges`/`adjacency`/`UNIQUE(name,type)`; `edge_weight_matrices` `matrix INTEGER[][]`, no `matrix_json`/`dimension`.
- [x] 3.4 — batch insert uses temp_id-keyed `INSERT…RETURNING` mapping; duplicate `(name,type)` disambiguated (name=file stem, `tsplib_name`=original); `adjacency`/`fixed_edges`/`matrix` populated.
- [x] 3.5 — `load(name,type)` + `load_matrix(name,type)` added; three dead single-insert methods deleted.
- [x] Only the 3 task files edited; `parser.py`/`transformer.py`/`api.py`/`insert_problem`/`insert_nodes` untouched.

## Validation Evidence

Sanity import (with `PYTHONPATH=src/submodules/Routing_data/src`):

```text
import converter.database.operations, converter.utils.worker_functions, converter.utils.exceptions -> imports OK
```

End-to-end integration test against a temp DuckDB (DatabaseManager + `insert_problems_batch` + `load`/`load_matrix`):

```text
problems has tsplib_name/fixed_edges/adjacency -> True/True/True
problems DDL contains UNIQUE(name, type) -> True
edge_weight_matrices cols: [is_symmetric, matrix, matrix_format, problem_id]  (no matrix_json, no dimension)
insert result: 7 successful, 0 failed
duplicate (name,type) count: 0
att48 TSP nodes: 48 | att48 CVRP nodes: 48
linhp318 fixed_edges: [[0, 213]]
alb1000 adjacency: [[0, 1], [1, 2]]
load eil51 TSP id != load eil51 CVRP id -> True
load('nope','TSP') -> NotFoundError: [nope/TSP] Problem 'nope' of type 'TSP' not found
load_matrix att48 TSP -> 48x48 nested list: True
```

Real-file worker payload (Task 3.1):

```text
bayg29 (EXPLICIT TSP): edge_weight_data keys = ['is_symmetric','matrix','matrix_format']; no matrix_json/dimension; matrix 29x29
alb3000d (HCP): edges count = 5993; edge_weight_data None
xray14012_2 (coordinate TSP): edge_weight_data None (expected; no EXPLICIT matrix)
```

- `get_errors` on all three edited files → **No errors found**.
- `grep` confirms `insert_edge_weights`/`_insert_problem_internal`/`insert_problem_atomic`/`matrix_json`/`problem_name_to_temp_id` are gone; `insert_problem`/`insert_nodes` remain.

Known boundary: the Decision #10 source-column RETURNING is not used because the installed DuckDB (1.5.5) rejects it; the documented row-order fallback is relied upon (single-process temp-table/DataFrame scan preserves `INSERT…SELECT` order — verified in sandbox). `api.py` and `insert_problem`/`insert_nodes` still target the pre-rebuild schema and are deferred.

## Deep Analysis

### Why `UNIQUE(name, type)` makes `load` ambiguity-free

Cross-type twins (att48 as TSP and as CVRP, eil51, gil262) share the same
`name`; the type column is the discriminator. The schema-level
`UNIQUE(name, type)` guarantees `load(name, type)` can match at most one row, so
the loader never has to guess. `NotFoundError` (Decision #7) signals the domain
"zero rows" condition separately from `DatabaseError` (an operation failure),
letting callers distinguish a bad lookup from a broken connection/query.

### Why the temp_id mapping eliminates the cross-contamination

The old batch path built `problem_id_mapping` by joining `problems_temp` to
`problems` on `name`. For shared names across types, this join could bind a node
row to the wrong problem id (the att48/eil51/gil262/lin318 contamination).
Decision #10 keys the mapping by the worker's `temp_id` (a per-batch ordinal),
which is unique within a batch, and derives the real id from `INSERT…RETURNING`.
Because `temp_id` is never a business key, the mapping is exact regardless of
name collisions.

### Why the fallback RETURNING is safe

The installed DuckDB 1.5.5 rejects both the pinned subquery syntax and
source-column RETURNING for columns not in the INSERT target (a limitation of
this version). The Decision #10 fallback materializes `RETURNING id` and zips it
to `temp_id` by source row order. This is safe here because the source is a
single registered DataFrame / temp table scanned in a single process with no
`ORDER BY`/parallel distribution, so DuckDB emits ids in insertion order. The
sandbox confirmed `[1,2,3,4]` maps to temp_ids `[1,2,3,4]`. For the exact
DuckDB behaviors and the general pattern, see
[knowledge_duckdb-returning-source-columns.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_duckdb-returning-source-columns.md).

### Why array columns are inserted via pandas, not row-by-row

DuckDB's pandas integration converts a column of python nested lists (with `None`
for non-graph rows) into `INTEGER[][]`/`LIST(LIST(INTEGER))` transparently, as
verified in the sandbox for `adjacency`, `fixed_edges`, and `matrix` (the latter
from float-typed worker lists, cast to `INTEGER`). This keeps the bulk path
columnar and avoids a per-row `executemany` for arrays, matching the batch's
performance rationale while satisfying the new schema.
