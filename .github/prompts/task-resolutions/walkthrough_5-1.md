---
title: "Walkthrough: Task 5.1 — Database Validation Gate"
task_id: "5.1"
description: >
  Executes the Batch 5 validation gate for the Routing_data database rebuild:
  runs the pinned SQL assertion suite and spot-checks against the freshly built
  db/routing.duckdb (strictly read-only), records per-criterion pass/fail with
  query evidence, and registers the PASS verdict in the plan.
created: 2026-08-27
status: final
author:
  - "[[Lucas Galdino]]"
type: report
scope: local
modifications:
  - date_modified: 2026-08-27
    modifications:
      - description: >
          Initial registration: full assertion suite executed (20/20 pass), gate
          verdict PASS, evidence table recorded, three FYI findings documented,
          Tasks 1.4/4.1/4.2/4.3/5.1 marked reviewed in the plan.
related_files:
  - [plan-routingDatabaseRebuild.prompt.md](./plan-routingDatabaseRebuild.prompt.md)
tags:
  - review/validation
  - review/implementation-plan
  - benchmark/database
  - benchmark/etl
  - analysis/duckdb
  - guide/database-rebuild
  - algorithm/tsplib
  - notes/5w2h
  - review/registration
  - benchmark/validation
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
---

# Walkthrough: Task 5.1 — Database Validation Gate

## Objective

Run the full pinned assertion suite against `db/routing.duckdb` (rebuilt in
Batch 4), confirm the rebuild matches the eleven pinned decisions, mark the
validation outcome in the plan, and report per-criterion pass/fail with
evidence. Read-only: the DB was opened with
`duckdb.connect(path, read_only=True)` and verified immutable afterward.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| Task 5.1 criteria | [plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md) | Pins the 8 assertions + 5 spot-checks gated here; the plan wins over this prompt |
| Built artifact | [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb) | 21.0 MB (22 032 384 bytes), mtime 2026-08-27 18:51:35 — unchanged after every gate query |
| Schema reference | [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py) | `problems` (+ `tsplib_name`/`fixed_edges`/`adjacency`, `UNIQUE(name,type)`), `nodes`, `edge_weight_matrices` (`matrix INTEGER[][]`), `solutions`, `file_tracking` |
| Batch 4 claims | [walkthrough_4-1_4-2_4-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_4-1_4-2_4-3.md) | 198 processed / 0 failed; matrices=80, nodes=334813, solutions=43 — treated as claims to verify, not facts |
| Toolchain | DuckDB 1.5.5 via `uv run python` (repo root env) | `duckdb_constraints()` used for the UNIQUE check; nested-array columns returned as native lists |

---

## Impact Analysis

### Root Cause

Batch 4 rebuilt the DB; nothing had verified the content against the pinned
acceptance criteria. This gate is the plan's final check before sign-off.

### Design Decisions

| Component | Decision | Rationale |
| --- | --- | --- |
| EXPLICIT identification | `edge_weight_type='EXPLICIT'` (80 rows), **not** `edge_weight_format` | `edge_weight_format` holds the TSPLIB layout token (`FULL_MATRIX` 62, `LOWER_DIAG_ROW` 12, `UPPER_DIAG_ROW` 3, `UPPER_ROW` 3, `FUNCTION` 2, NULL 116). First harness run used the wrong column and reported a false FAIL |
| Spot-check scope | Assert only what the plan pins | berlin52 cost=7542 and br17 solution rows were over-assertions in the first harness run — berlin52.opt.tour has no length comment and the dataset ships no br17 tour sidecar (both source-verified) |
| HCP node rows | Not a pinned criterion — reported as FYI | 9 HCP problems each get `dimension`-many virtual node rows with NULL coords (parser `_extract_nodes` else-branch, pre-existing design) |
| Read-only guarantee | `read_only=True` + mtime/size re-check | DB immutable across all 30+ queries of the gate |

### Failure / Correction Log

| Attempt / Event | Evidence Read | Correction / Decision | Outcome |
| --- | --- | --- | --- |
| Harness run 1: 6 failures | `FORMATS` query: `FULL_MATRIX`/`LOWER_DIAG_ROW`/… and `edge_weight_type='EXPLICIT' → 80` | C3b/C12 used `edge_weight_format`; switched to `edge_weight_type='EXPLICIT'` | EXPLICIT↔matrix 1:1 verified 0/0 both directions |
| Harness run 1: berlin52 FAIL | `berlin52.opt.tour` has no `COMMENT` line (read directly) | Dropped the unpinned cost=7542 assertion; kept the pinned tour assertion | S1 pass: 0-based permutation of 0..51 |
| Harness run 1: br17 FAIL | `datasets/problems/atsp/` contains only `br17.atsp`; no `.opt.tour` in `tour/` | Dropped the unpinned solution-row assertion | S2 pass: 17×17 asymmetric matrix |
| Harness run 1: alb1000 FAIL | `alb1000.hcp` has no `NODE_COORD_SECTION` (grep 0); nodes in DB = virtual stubs | Dropped the unpinned "no nodes" assertion; recorded as FYI | S5 pass: 1998 adjacency pairs, zero matrix rows |

---

## Affected Files

### Data (read-only, 0 files changed)

1. [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb) — queried read-only only; no INSERT/UPDATE/DELETE/rebuild.
2. [plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md) — registration only (verdicts + checkboxes), the one file this reviewer edits.
3. [TODO.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/TODO.md) — validation-gate state updated to EXECUTED — PASS.

---

## Change Checklist

- [x] 1. Read-only assertion suite run (20 checks) against `db/routing.duckdb`.
- [x] 2. Five spot-check loads executed with query evidence.
- [x] 3. Gate verdict + per-task annotations registered in the plan.
- [x] 4. `TODO.md` validation state updated.
- [x] 5. DB immutability confirmed (mtime/size unchanged after the gate).

---

## Validation Evidence

**Gate verdict: PASS — 20/20.**

| # | Criterion (pinned) | Evidence (query) | Result |
| --- | --- | --- | --- |
| C1 | 198 problems total | `SELECT count(*) FROM problems` → 198 | ✅ pass |
| C2 | TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41 | `GROUP BY type` → `{TSP:113, ATSP:19, CVRP:16, HCP:9, SOP:41}` | ✅ pass |
| C3 | matrices=80 (claim) | `SELECT count(*) FROM edge_weight_matrices` → 80; `edge_weight_type='EXPLICIT'` → 80 | ✅ pass |
| C4 | matrix dim == problem dim on all 80 EXPLICIT | join `edge_weight_matrices`↔`problems`: 80 checked, rows=dim and every row len=dim | ✅ pass |
| C5 | zero HCP matrix rows | matrix rows joined to `type='HCP'` → 0 | ✅ pass |
| C6 | all 9 HCP adjacency non-null | null count → 0; lens per problem: 1998/3996/5993/5997/5999/5996/5996/7997/9999 | ✅ pass |
| C7 | zero duplicate (name, type) | `GROUP BY name,type HAVING count(*)>1` → ∅; `duckdb_constraints()` → `UNIQUE(name, type)` present | ✅ pass |
| C8 | `linhp318.fixed_edges == [[0,213]]` | row `('linhp318','lin318','TSP',318,[[0,213]])` | ✅ pass |
| C9 | every solution links to a problem; 43 solutions (claim) | 43 rows; LEFT JOIN orphans → 0 | ✅ pass |
| C10 | every node links; 334813 nodes (claim); 0-based contiguous | 334813; orphans → 0; `node_id <0 OR >=dimension` → 0; per-problem count==dimension → 0 violations | ✅ pass |
| C11 | file_tracking 198, linked | 198 rows; orphans → 0 | ✅ pass |
| C12 | EXPLICIT ↔ matrix 1:1 | explicit-without-matrix → 0; non-explicit-with-matrix → 0 | ✅ pass |

**Spot-checks (pinned):**

| # | Spot-check | Evidence | Result |
| --- | --- | --- | --- |
| S1 | berlin52 (EUC_2D) | TSP, dim 52, `EUC_2D`, 0 matrix rows; tour = 1 route × 52 nodes, `sorted(route)==0..51`, first node 0 | ✅ pass |
| S2 | br17 (ATSP EXPLICIT) | ATSP, dim 17, `EXPLICIT`, 17×17, `is_symmetric=False`, matrix ≠ transpose; no tour sidecar in dataset → no solution row (expected) | ✅ pass |
| S3 | eil13 (CVRP EXPLICIT expanded) | CVRP, dim 13, 13×13, row 0 all zero, col 0 all zero, `m[1][1]==9` | ✅ pass |
| S4 | att48 as TSP and as CVRP | ids 19 (TSP) ≠ 124 (CVRP), dim 48 each, node rows 48 each | ✅ pass |
| S5 | alb1000 (HCP adjacency only) | HCP, dim 1000, adjacency 1998 0-based pairs (sample `[[999,592],[999,455]]`), 0 matrix rows | ✅ pass |

**Environmental DoDs (Tasks 4.2/4.3, verified at the gate):**

| Check | Evidence | Result |
| --- | --- | --- |
| stray `.venv` gone (4.2) | `ls src/submodules/Routing_data/.venv` → No such file or directory | ✅ pass |
| pandas declared (4.1) | `uv run --project src/submodules/Routing_data python -c "import pandas"` → `pandas 3.0.5`; note: `--project` transiently re-created the submodule `.venv` — removed immediately after | ✅ pass |
| DB > 12 KB (4.3) | 21.0 MB / 22 032 384 bytes | ✅ pass |
| stale husk cleared (4.3) | repo-root `datasets_processed/` → absent | ✅ pass |
| tracked submodule husk untouched (ambient fact) | `src/submodules/Routing_data/datasets_processed/db/routing.duckdb` still present | ✅ expected |
| Task 1.4 (REQ-2) | parser.py L7 relative `from .models import StringField`; literal DoD command (`PYTHONPATH=… .venv/bin/python …/converter_cli.py --help`) exits 0; absolute path no longer resolves | ✅ pass |

**Boundary:** DB mtime (2026-08-27 18:51:35) and size re-checked after the gate —
unchanged. What was NOT validated here: main-repo consumer behavior (Deferred
list), submodule tests/docs (out of pinned scope).

---

## Deep Analysis

**EXPLICIT identification.** The plan's "80 EXPLICIT problems" maps to
`problems.edge_weight_type='EXPLICIT'`. `edge_weight_format` stores the TSPLIB
layout token, and the matrix population by type (ATSP=19, CVRP=3, SOP=41,
TSP=17 → 80) equals the EXPLICIT count exactly — the 1:1 correspondence
(C12) holds in both directions.

**Solution cost provenance.** `_parse_tour_file` extracts cost from the tour
file's COMMENT via `_extract_cost_from_comment`. 19/43 rows are NULL because
their source tour files carry no length comment (verified for berlin52 by
reading the file). Known-optimum rows are correct where present (eil51=426,
gr48=5046, rd100=7910, kroC100=20749, pcb442=50778).

**Virtual node rows.** For every problem without coordinates (HCP, and all
EXPLICIT problems), parser `_extract_nodes` (else-branch) creates
`dimension`-many node rows with NULL x/y/z — a pre-existing, intentional
pattern ("Create virtual nodes based on dimension"). HCP contributes 27000 of
the 334813 node rows. TODO's "adjacency is their only graph data" concerns
graph data (no matrix, adjacency present); the node-id scaffold is orthogonal
and out of pinned scope.

**Name storage.** Names with no same-type collision keep the file-declared
NAME verbatim (e.g. `ulysses16.tsp`, `pa561.tsp` — the files literally declare
`NAME : ulysses16.tsp`), per the TODO name-twin rule (rewrite only on
collision: `linhp318`/`tsplib_name='lin318'` verified at C8).

---

## Additional Findings

> [!NOTE]
> **FYI-1 — solution cost NULLs.** 19/43 solutions have `cost IS NULL` because
> the source tour lacks a length comment. Faithful to source; solution cost is
> not a pinned criterion and `solution_name` cleanup is already deferred in the
> TODO. No action.

> [!NOTE]
> **FYI-2 — virtual node stubs.** HCP/EXPLICIT problems carry dimension-many
> NULL-coordinate node rows (27000 for HCP). Pre-existing `_extract_nodes`
> design, not introduced by Batches 1–4. No pinned criterion covers it. If a
> consumer expects zero node rows for HCP, that is a separate decision.

> [!NOTE]
> **FYI-3 — dataset tour coverage.** 43 solutions for 198 problems
> (TSP=32, HCP=9, CVRP=2; SOP/ATSP=0). br17 has no tour sidecar in
> `datasets/problems/tour/`. Dataset provenance, not a defect.

---

## Review Notes

- No pinned criterion failed → no new tasks registered in the plan.
- Per-task registration: verdicts appended to Tasks 1.4 / 4.1 / 4.2 / 4.3 / 5.1
  Solution blocks; checkboxes marked `[x]` in the plan; `TODO.md` state
  updated to EXECUTED — PASS.
- Task 1.3 remains `[ ]` with the pre-existing `[MUST REDO: REQ-2]` tag; the
  redo (Task 1.4) is now marked `[x]` and verified live.
