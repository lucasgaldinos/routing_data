---
title: "Walkthrough: Tasks 2.1–2.3 — Transformer CVRP Matrix Expansion + edges/fixed_edges Pass-through + Tour DIMENSION Fallback"
task_id: "2.1-2.2-2.3"
description: >
  Batch 2 of the Routing_data database rebuild: threaded problem_type through
  _convert_edge_weights_to_matrix to expand customer-only CVRP (n-1)×(n-1)
  matrices to n×n (Decision #5); passed top-level edges/fixed_edges through
  transform_problem (Decision #4); and pre-injected a missing DIMENSION line
  into .opt.tour files (Decision #6).
created: "2026-08-27"
author:
  - "[[Lucas Galdino]]"
status: "in-review"
tags: [guide/transformer, algorithm/tsplib, algorithm/vrp, algorithm/hcp, notes/routing-data, benchmark/etl]
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
---

# Walkthrough: Tasks 2.1–2.3 — Transformer Batch

## Objective

Make `transformer.py` the correct bridge from the Batch-1 parser result to the
Batch-3 worker: expand customer-only CVRP matrices to the full n×n problem
dimension (Decision #5), carry `edges`/`fixed_edges` through `transform_problem`
unchanged (Decision #4), and pre-inject a missing `DIMENSION` into `.opt.tour`
solution files using the linked problem's dimension (Decision #6). All edits
confined to `converter/core/transformer.py`; `parser.py` untouched.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| Transformer (edited) | [transformer.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py) | `_convert_edge_weights_to_matrix` had no `problem_type`; `transform_problem` dropped `edges`/`fixed_edges`; `_parse_tour_file` called `parser.parse_file` directly on the tour path. |
| Parser (read-only, Batch 1) | [parser.py L156-166](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L156) | `parse_file` now emits top-level `edges`/`fixed_edges` keys; `problem_data['type']` is normalized (e.g. `CVRP`). |
| Decision pin | [plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md) | Decisions #4 (top-level keys), #5 (CVRP n-1→n), #6 (tour DIMENSION pre-inject). |
| Data | `datasets/problems/vrp/eil13.vrp` | `TYPE : CVRP`, `DIMENSION : 13`; carries a customer-only 12×12 EXPLICIT matrix. |
| Data | `datasets/problems/hcp/alb1000.hcp` | `edges` only (adjacency); no matrix. |
| Data | `datasets/problems/tsp/linhp318.tsp` | `FIXED_EDGES_SECTION` → `fixed_edges == [[0, 213]]`. |
| Data | `datasets/problems/tour/rd100.opt.tour` | Has **no** `DIMENSION` line; previously failed `validate_problem` (dimension check). |

## Impact Analysis / Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Where to expand (Task 2.1) | New `_expand_vrp_matrix` helper applied to **both** matrix paths (Matrix-object and legacy nested-list path) | Keeps the expansion single-sourced; the Matrix-object path is the one that yields `matrix_size == dimension - 1` for CVRP customer-only files, while the legacy path is already `dimension×dimension` (helper is a no-op there). |
| `problem_type` source | `problem_meta.get('type')` threaded into the call | `type` is the normalized parser value (`CVRP`, not legacy `VRP`), per Decision #9. Checking both `('CVRP','VRP')` is defensive but the vocabulary is pinned to `CVRP`. |
| Pass-through (Task 2.2) | Read top-level `problem_data.get('edges')`/`.get('fixed_edges')` (the `transform_problem` argument *is* the parse result) and re-emit as top-level keys | Matches Decision #4: `edges`/`fixed_edges` are siblings of `problem_data`/`nodes`/`tours`/`metadata`/`edge_weight_matrix`. |
| DIMENSION fallback (Task 2.3) | Pre-inject `DIMENSION : <problem_dim>\n` into raw tour text and parse via a temp file | Decision #6 pins pre-injection over mutating `parser.parse_file`/`validate_problem`. Keeps parser behavior unchanged; only the transformer writes the temp file. |
| `problem_dimension` plumbing | Optional `problem_dimension: Optional[int] = None` on `parse_solution_data` → `_parse_tour_file` | Worker (Task 3.1) will pass the linked problem's dimension; the default `None` keeps current callers (`worker_functions.py:72`) working until Batch 3 lands. |

## Failure / Correction Log

| Attempt | Evidence | Correction |
| --- | --- | --- |
| None during execution | — | All three DoDs passed on first verification run against real files (`eil13`, `alb1000`, `linhp318`, `rd100`). No retry needed. |

## Affected Files (Detailed)

### python — `src/converter/core/transformer.py`

1. [transformer.py L74](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L74) — `transform_problem` threads `problem_type=problem_meta.get('type')` into `_convert_edge_weights_to_matrix`.
2. [transformer.py L90-106](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L90) — `transform_problem` reads top-level `edges`/`fixed_edges` and re-emits them on the result dict.
3. [transformer.py L158](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L158) — `_convert_edge_weights_to_matrix` gains `problem_type: Optional[str] = None`; both return paths route through `_expand_vrp_matrix`.
4. [transformer.py L230](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L230) — new `_expand_vrp_matrix` helper (zeroes depot row/col 0 when `problem_type in ('CVRP','VRP')` and `len == dimension-1`).
5. [transformer.py L301-360](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L301) — `parse_solution_data` gains `problem_dimension`; forwards to `_parse_tour_file`.
6. [transformer.py L322-360](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L322) — `_parse_tour_file` gains `problem_dimension`; pre-injects `DIMENSION` via a temp file when absent, cleans up the temp file in a `finally`.

No other files changed. `parser.py`, `models.py`, `worker_functions.py` untouched.

## Change Checklist

- [x] 2.1 — `_convert_edge_weights_to_matrix` takes `problem_type`; CVRP/VRP (n-1)×(n-1) matrices expanded to n×n with zeroed row/col 0.
- [x] 2.1 — `transform_problem` threads `problem_meta.get('type')`.
- [x] 2.2 — `edges`/`fixed_edges` re-emitted as top-level keys on the transformed result.
- [x] 2.3 — `parse_solution_data(..., problem_dimension=...)` → `_parse_tour_file`; pre-inject DIMENSION when missing.
- [x] 2.3 — `parser.parse_file`/`validate_problem` unchanged.
- [x] Only `transformer.py` edited.

## Validation Evidence

Run with `PYTHONPATH=src/submodules/Routing_data/src`:

```text
eil13 type= CVRP dim= 13 matrix= 13 x 13
row0= [0.0 x13]
col0= [0.0 x13]
HCP edges len= 1998 fixed_edges= []
linhp318 fixed_edges= [[0, 213]]
rd100 dim= 100
rd100 sol routes len= 100
ALL TASKS PASS
```

- **Task 2.1:** `eil13` → 13×13 matrix, first row and first column all zero (depot row/col). ✅
- **Task 2.2:** HCP `alb1000` result keeps `edges` (1998 pairs) and `fixed_edges == []`; `linhp318` keeps `fixed_edges == [[0, 213]]`. ✅
- **Task 2.3:** `rd100.opt.tour` parses with `problem_dimension=100`, yielding a 100-node route with **no** dimension validation error. ✅
- `get_errors` on `transformer.py` → **No errors found**.
- Sanity import: `from converter.core.transformer import DataTransformer` succeeds.

Known boundary: temp file for the DIMENSION pre-inject is created and removed within `_parse_tour_file`; the worker must actually pass `problem_dimension` (Batch 3, Task 3.1) for the fallback to fire — until then the default `None` preserves the pre-Batch-2 behavior for current callers.

## Deep Analysis

### Why expand in the transformer, not the parser or worker

Decision #5 pins the expansion at ETL time, and the transformer is the only
component that sees both the parsed matrix *and* the normalized problem type
together with the authoritative `dimension`. Expanding here guarantees the
`edge_weight_matrix` delivered to the worker (Task 3.1) is always full n×n, so
`operations.insert_problems_batch` (Task 3.4) writes `matrix INTEGER[][]` without
needing to know about the customer-only quirk. The depot row/col is zeroed (not
copied) because TSPLIB CVRP customer-only matrices have no depot distance data —
a zeroed depot is the standard convention and is safe for downstream solvers that
treat the depot as distance-0 to itself and disconnected otherwise.

### Why the helper covers both matrix paths

`_convert_edge_weights_to_matrix` has two branches: the `matrix.Matrix` object
path (which reflects the actual `size`, possibly `dimension-1`) and the legacy
nested-list path (already built at `dimension×dimension`). Routing **both**
returns through `_expand_vrp_matrix` centralizes the invariant "output is always
dimension×dimension" and makes the helper trivially a no-op on the legacy path.
This avoids duplicating the expansion logic and keeps the two paths consistent if
the legacy path ever receives a customer-only matrix.

### Why pre-inject DIMENSION instead of relaxing validation

`rd100.opt.tour` legitimately omits `DIMENSION`. Rather than weaken
`validate_problem` (which would risk masking real dimension defects on every other
file), Decision #6 chooses to **inject** the authoritative dimension from the
linked problem and parse through a temp file. This localizes the fix to the tour
parsing path in the transformer, leaves `parser.parse_file`/`validate_problem`
byte-identical, and guarantees the parsed tour's dimension always matches its
problem. The temp file is cleaned in a `finally` so a failed parse does not leak.

## Review Notes

- The `edges`/`fixed_edges` keys are emitted even when `None` (parser always sets
  them, so in practice they are lists; `None` would only occur if a caller feeds a
  hand-built dict missing those keys).
- `problem_type` check `('CVRP','VRP')` is intentionally defensive; the pinned
  vocabulary (Decision #9) is `CVRP`.
