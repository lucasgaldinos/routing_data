---
title: "Routing_data Schema v2 + Rebuild Replan — Registered Implementation Plan"
description: >
  Supersedes the frozen plan-routingDatabaseRebuild.prompt.md after the 2026-08-28
  review of Task 4.3 exposed a red committed test suite (18 failures), a validation
  gate that passed by dropping failing assertions, zero committed tests for the new
  schema, and a cargo-culted PYTHONPATH workaround masking a broken uv configuration.
  Pins the user-approved schema v2 design (thin hub + self-contained per-type tables,
  single satellite tables, node data as array columns) and re-registers every
  finding — including items the old plan deferred — as tracked 5W2H batches.
created: 2026-08-28
status: draft
author:
  - "[[Lucas Galdino]]"
  - "[[GitHub Copilot]]"
type: guide
scope: local
modifications:
  - date_modified: 2026-08-28
    modifications:
      - description: >
          Initial registration. Freezes plan-routingDatabaseRebuild.prompt.md
          (Task 4.3 obsolete — its premises changed after the venv-control fix and
          the husk removal), pins ten design decisions, and decomposes the work
          into five batches: schema v2 implementation, test-suite rewrite,
          rebuild+gate, tracked main-repo dependencies, and an unscheduled
          ingestion spike.
  - date_modified: 2026-08-28
    modifications:
      - description: >
          Quality-gate restructure per task-managing §2.3/§4/§8. Split bundled
          tasks: old 1.2 → 1.2 + 1.3 (insert dispatch vs parser scaffold); old
          1.5 → 2.3 + 2.4 (sys.path hack vs config.yaml default); old 2.1 (18
          inlined triage decisions) → seven per-file tasks across Batches 3–4;
          old 2.3 → 5.2 + 5.3 (schema surface vs pinned behaviors); old 2.4 →
          6.1–6.3 (three independent hygiene operations); old 3.1 → 7.1 + 7.2
          (rebuild vs promote — the skill's own anti-pattern example); old 5.1 →
          9.1–9.3 (one spike per family). Completed the missing 5W2H fields
          (Who/Where/When/How/How much/Stakeholder Implications) on every task,
          re-batched to ≤5 tasks per batch (now nine batches), renumbered all
          cross-references, fixed the scanner failure count (six, not five),
          re-scoped old 4.4 (datasets/inspect_database.py verified absent —
          live surface is the submodule's test_inspect.py), and verified every
          Where target against the working tree (failing tests live under
          tests/test_converter/).
  - date_modified: 2026-08-28
    modifications:
      - description: >
          Batch 1 tooling-clause closure. Task 1.1 tooling DoD met — ruff
          (root ruff.toml, E501 ignored), black (submodule line-length 100),
          and mypy (submodule strict, scoped to operations.py) all green on
          operations.py; fixed RUF012 (`_TYPE_INSERTERS` ClassVar), B905
          (zip strict=True), mypy L719 `total` None-guard + `params: list[Any]`.
          Task 1.2 rework verified (v1 insert path replaced via 1.4). Task 1.4
          verified (v2 dispatch + rollback-all, no v1-STI SQL). Task 1.5 stays
          open — `get_problem_stats`/`query_problems` still hit v1-STI
          (Binder Error on `dimension` / IndexError on v1 row layout); `load`
          returns hub row only.
related_files:
  - [plan-routingDatabaseRebuild.prompt.md](./plan-routingDatabaseRebuild.prompt.md)
  - [walkthrough_4-1_4-2_4-3.md](./task-resolutions/walkthrough_4-1_4-2_4-3.md)
  - [pyproject.toml](../../pyproject.toml)
  - [operations.py](../../src/converter/database/operations.py)
  - [parser.py](../../src/tsplib_parser/parser.py)
  - [root pyproject.toml](../../../../../pyproject.toml)
tags:
  - review/implementation-plan
  - guide/schema-design
  - guide/database-rebuild
  - guide/testing
  - analysis/duckdb
  - analysis/schema-migration
  - algorithm/tsplib
  - benchmark/etl
  - benchmark/database
  - notes/routing-data
  - notes/5w2h
  - review/schema
---

# Routing_data Schema v2 + Rebuild Replan — Registered Implementation Plan

> [!IMPORTANT]
> This plan **supersedes** [plan-routingDatabaseRebuild.prompt.md](./plan-routingDatabaseRebuild.prompt.md),
> which is **frozen** as of 2026-08-28. Its Task 4.3 is obsolete (the venv-control
> fix and the husk removal changed its premises) and its "Deferred" section is
> re-registered here as tracked work. Do not add tasks to the old file.

## Why this plan exists (postmortem of the 2026-08-28 review)

The review of Task 4.3 / Batch 5 produced these verified findings:

1. **The committed test suite is red.** 18 of 217 tests fail in exactly the
   modules the old plan's Batches 1–3 rewrote (scanner, transformer, database
   operations, cordeau, converter API, schema-migration). The old plan's
   Batch-5 gate never ran them.
2. **The gate passed by attrition.** The first validation script had 6 FAILs;
   the "final" script legitimately fixed one column bug (`edge_weight_type` vs
   `edge_weight_format`) and silently **dropped the other four failing
   assertions** (HCP zero-node-rows, alb1000 zero-nodes, berlin52 cost==7542,
   br17 opt-39 solution), demoting them to prose "FYI".
3. **Zero committed tests for the new schema.** No test touches `tsplib_name`,
   `fixed_edges`, or `adjacency`; the gate assertions lived in `/tmp` and are
   not versioned. The old plan's scope rule *"do not write tests"* is
   **repealed** — committed tests are mandatory deliverables from here on.
4. **PYTHONPATH was cargo cult.** `converter_cli.py:13` already does
   `sys.path.insert(0, .../src)`, so the pinned command worked without
   PYTHONPATH (verified: exit 0). The real defect was the root uv
   configuration — now fixed (Decision 8).
5. **Task 4.3 was one blob with a file-size DoD** (`> 12 KB`), and its husk
   cleanup certified a no-op (`rm -f` on a nonexistent repo-root path) while
   the real 48.5 MB git-tracked stale husk sat untouched in the submodule.

## Decisions log (pinned 2026-08-28)

| # | Decision | Choice |
| --- | --- | --- |
| 1 | Table topology | **B** — thin hub `problems(id, name, type)` as discovery index + self-contained per-type tables with duplicated common columns; consumer pattern is `SELECT ... FROM ${type_table}` |
| 2 | Satellites | Single `solutions`, `file_tracking`, `edge_weight_matrices` tables, all FK → hub `problems(id)` |
| 3 | Node data | **Array columns in type tables** (`coords DOUBLE[][]`, `demands INTEGER[]`, `depots INTEGER[]`); `nodes` table dropped; the virtual-node scaffold (`parser.py` `_extract_nodes` else-branch, 27 000 NULL-coord HCP rows) is killed |
| 4 | Execution order | Schema v2 → suite rewrite → rebuild + gate (no tests written against the v1 schema that is about to die) |
| 5 | Gate tests | Committed **hermetic** pytest in `tests/` (fixture DB built from `datasets_raw` into `tmp_path`), CI-runnable; the same suite accepts an optional DB path to validate the canonical DB locally |
| 6 | New ingestion families (Solomon `C101.txt`, UMalaga mdvrp, Cordeau) | Spike only, unscheduled (Batch 9) |
| 7 | Plan organization | New file (this one); old plan frozen |
| 8 | Venv control | **DONE, verified** — root `[tool.uv.sources]` now `routing-data = { path = "src/submodules/Routing_data", editable = true }`; phantom workspace member `data/Routing_data/vrp_database` removed; `import converter` resolves to the local submodule; `uv run converter` entry point live; **PYTHONPATH retired from all commands** |
| 9 | Stale husk | **DONE** — `datasets_processed/db/routing.duckdb` (48.5 MB, old schema) removed from git tracking; zero tracked `.duckdb` files remain |
| 10 | Branch policy | All work on submodule branch `dev` (baseline commit `c427eda`); merge to `main` at batch gates |

## Target schema v2 (DDL sketch — Task 1.1 owns the final form)

```sql
-- Hub: discovery index only. "Which table holds att48?" lives here.
CREATE TABLE problems (
    id INTEGER PRIMARY KEY DEFAULT nextval('problems_seq'),
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, type)
);

-- Type tables: self-contained; common columns duplicated BY DESIGN (Decision 1).
CREATE TABLE tsp_problems (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    dimension INTEGER NOT NULL,
    comment VARCHAR,
    edge_weight_type VARCHAR NOT NULL,
    edge_weight_format VARCHAR,
    tsplib_name VARCHAR,
    coords DOUBLE[][],           -- NULL iff EXPLICIT (matrix row holds the data)
    display_coords DOUBLE[][]
);
CREATE TABLE atsp_problems (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    dimension INTEGER NOT NULL,
    comment VARCHAR,
    tsplib_name VARCHAR          -- always EXPLICIT: matrix row mandatory (gate-enforced 1:1)
);
CREATE TABLE cvrp_problems (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    dimension INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    comment VARCHAR,
    edge_weight_type VARCHAR NOT NULL,
    edge_weight_format VARCHAR,
    tsplib_name VARCHAR,
    coords DOUBLE[][],           -- NULL iff EXPLICIT
    demands INTEGER[] NOT NULL,  -- len(demands) == dimension (gate-enforced)
    depots INTEGER[] NOT NULL
);
CREATE TABLE hcp_problems (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    dimension INTEGER NOT NULL,
    adjacency INTEGER[][] NOT NULL,  -- 0-based pairs; the ONLY graph data for HCP
    comment VARCHAR,
    tsplib_name VARCHAR
);
CREATE TABLE sop_problems (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    dimension INTEGER NOT NULL,
    fixed_edges INTEGER[][],         -- e.g. linhp318 -> [[0, 213]]
    comment VARCHAR,
    tsplib_name VARCHAR              -- SOP is EXPLICIT: matrix row in edge_weight_matrices
);

-- Satellites: single tables, FK -> hub (Decision 2).
CREATE TABLE edge_weight_matrices (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
    matrix_format VARCHAR NOT NULL,
    is_symmetric BOOLEAN NOT NULL,
    matrix INTEGER[][] NOT NULL
);
CREATE TABLE solutions (
    id INTEGER PRIMARY KEY DEFAULT nextval('solutions_seq'),
    problem_id INTEGER NOT NULL REFERENCES problems(id),
    solution_name VARCHAR,
    solution_type VARCHAR,
    cost DOUBLE,                     -- see Task 2.2 (backfill policy)
    routes INTEGER[][] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE file_tracking (
    id INTEGER PRIMARY KEY DEFAULT nextval('file_tracking_seq'),
    file_path VARCHAR UNIQUE NOT NULL,
    problem_id INTEGER REFERENCES problems(id),
    checksum VARCHAR,
    last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_size BIGINT
);
-- nodes table: DROPPED (Decision 3).
```

---

## Batch 1 — Schema v2 DDL + write path — `implementer` — sequential (1.1 → 1.2 → 1.3)

+ [x] **Task 1.1: Rewrite the DDL in `operations.py` to schema v2**
  * **What:** Replace the v1 schema (one `problems` table holding every type + a `nodes` table) with the v2 hub + 5 per-type tables + 3 satellite tables (Decision 1).
  * **Why:** v1 forced every problem type into one table with nullable columns, so the schema could not enforce any per-type invariant — the old gate's 20 assertions existed only to make up for that. v2 gives each type its own table that can assert its own shape.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/database/operations.py` L41–L163 (`_initialize_schema`).
  * **When:** No dependencies; first in batch.
  * **How:** `CREATE TABLE` statements exactly per the Decisions 1–3 sketch above (hub, five type tables, three satellites, `nodes` dropped); `nextval` sequence defaults retained where the sketch shows them; insert-path changes are **out of scope here** — Task 1.2 owns them.
  * **How much:** Medium.
  * **Stakeholder Implications:** All write/read paths break until Task 1.2 lands — same batch, sequential; CI on `dev` stays red until Batches 3–4.
  * **DoD:** DDL applies cleanly on `:memory:` (create + smoke insert per table via SQL); ruff/black/mypy green on `operations.py`.
  * **Review Verdict (2026-08-28, reviewer):** DDL deliverable done and verified — smoke test shows the 9 v2 tables (hub + 5 type + 3 satellites), `nodes` dropped, sequences `problems`/`solutions`/`file_tracking` retained, `nodes_seq` dropped, `_migrate_schema` and its call site deleted. Tooling clause FAILS: ruff 27 errors on `operations.py` (F401 unused `datetime`, I001 ×2, E501 ×6, UP006/UP035/UP045), `black --check` reports "would reformat", mypy 69 errors (missing duckdb/pandas stubs + strict-mode issues incl. `api.py` `insert_nodes` attr errors). DoD: fail on tooling.
  * **Rework Verdict (2026-08-28, reviewer):** Tooling clause closed — all three green on `operations.py`. `ruff check --config <repo-root>/ruff.toml` passes (E501 ignored at root; the two root-only findings RUF012 `_TYPE_INSERTERS` + B905 `zip()` fixed at L192/L605); `black --check` passes (submodule `[tool.black]` line-length=100; whole-file quote normalization to double); `mypy` passes on `operations.py` (submodule strict config via `--config-file`, `--follow-imports=skip --ignore-missing-imports` — `duckdb` ships no py.typed stubs; L719 `total` None-guard + `params: list[Any]` added). DoD: pass.

+ [x] **Task 1.2: Per-type insert dispatch in transformer/worker**
  * **What:** Route every write through a type-keyed dispatch that inserts the hub row and the matching type-table row in one transaction, mapping node data to the array columns.
  * **Why:** v1 wrote everything into one table; v2 splits hub + type rows, and writing them in separate transactions would orphan a type row when its sibling insert fails.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/core/transformer.py` L31 (`transform_problem`), `src/converter/utils/worker_functions.py` L14 (`process_file_for_parallel`), `src/converter/database/operations.py` L225/L265 (`insert_problem`/ `insert_nodes` — replaced by per-type insert helpers).
  * **When:** After 1.1.
  * **How:** Dispatch dict `{TSP: insert_tsp, ATSP: insert_atsp, ...}`; hub insert returns `id`; type-table row references it; arrays built from parser output; one explicit transaction per problem.
  * **How much:** Medium.
  * **Stakeholder Implications:** `api.py` write paths (Task 2.1) and the connection-leak tests (Task 4.3) depend on the final transaction shape.
  * **DoD:** Round-trip into `:memory:` of a fixture set (≥1 per type, incl. EXPLICIT TSP, EXPLICIT CVRP with demands, HCP, SOP): hub row + correct type-table row present for each; zero rows in wrong tables; forced failure mid-insert rolls back both rows.
  * **Review Verdict (2026-08-28, reviewer):** `insert_problem` dispatch done and verified — all 5 types round-trip (hub + correct type table; zero wrong-table rows; forced CVRP demands-mismatch rolls back both rows). But `insert_problems_batch` (L359-661) still carries v1 STI SQL (`INSERT INTO problems` with v1-only columns + `INSERT INTO nodes`) and is the live `converter process` write path (`cli/commands.py` L166): it returns `total_inserted: 0` against v2. DoD: pass for dispatch, fail for "replace the v1 insert paths".
  * **Rework Verdict (2026-08-28, reviewer):** The "replace the v1 insert paths" clause is satisfied — `insert_problems_batch` was reworked onto the v2 per-type dispatch under Task 1.4 and verified (scratch-DB smoke: `total_inserted: 1`, `failed: 0`; hub + type rows round-trip; no `nodes`/v1-column SQL; forced mid-batch failure rolls back the whole batch). DoD: pass.

+ [x] **Task 1.3: Kill the virtual-node scaffold in `parser._extract_nodes`** — reviewed, DoD pass
  * **What:** Delete the `_extract_nodes` else-branch that fabricates `dimension`-many NULL-coordinate rows, and fix the docstring that claims the opposite of the code. Preserve the branch's only load-bearing use: EXPLICIT CVRP demands/depot extraction.
  * **Why:** The scaffold produced 27 000 information-free HCP rows and forced "nodes == dimension" invariants that measured nothing.
  * **Who:** Agent (implementer).
  * **Where:** `src/tsplib_parser/parser.py` L477 (`_extract_nodes`), call site L155.
  * **When:** After 1.2 (array columns must exist to receive demands/depots).
  * **How:** Return an empty node list for coordinate-less problems; route demands/depots into the transformer's array-column payload; update the docstring; adjust the L155 caller.
  * **How much:** Low.
  * **Stakeholder Implications:** None beyond Batch 1 — no consumer reads fabricated rows (they contained nothing).
  * **DoD:** HCP/SOP/EXPLICIT parsing yields zero fabricated node rows; EXPLICIT CVRP still yields demands + depots; parser tests green.
  * **Review Verdict (2026-08-28, reviewer):** Done. `_extract_nodes` else-branch removed (returns `[]` for coordinate-less problems), docstring corrected, L155 caller now emits `demands`/`depots` keys, EXPLICIT-CVRP demands/depots preserved via `_extract_demands_depots`. Parser tests green (56 passed, 1 skipped; run from submodule root — note `uv run pytest` itself fails collection because the submodule venv lacks pytest). DoD: pass.

+ [x] **Task 1.4: Rework `insert_problems_batch` onto the v2 per-type dispatch**
  * **What:** Replace the v1 STI bulk SQL in `insert_problems_batch` (L359-661) with v2 writes — hub rows + per-type type-table rows via the existing `_insert_hub` + `_TYPE_INSERTERS` helpers, plus the `edge_weight_matrices` / `solutions` / `file_tracking` satellite inserts — preserving the name-disambiguation logic and per-row error capture.
  * **Why:** It is the live write path for `converter process` (`cli/commands.py` L166) and for the Batch 7 rebuild; today it returns `total_inserted: 0` / all rows failed against v2, so the whole ingestion is dead. It was in scope for Task 1.2 ("replace the v1 insert paths") and was missed.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/database/operations.py` L359-661 (`insert_problems_batch`); consumer `src/converter/cli/commands.py` L166.
  * **When:** After 1.1/1.2 (needs the v2 DDL and dispatch).
  * **How:** Reuse the per-type inserters: either loop `insert_problem` over the successful results inside one explicit batch transaction (rollback-all-on-failure), or re-emit `_insert_hub` + per-type inserter + satellite SQL with the temp_id→real_id mapping keyed by `problems.id`; drop the dead `INSERT INTO nodes` and the v1-only `problems` columns (`capacity_vol`, `capacity_weight`, `max_distance`, `service_time`, `vehicles`, `periods`, `has_time_windows`, `has_pickup_delivery`). Keep the name→file-stem disambiguation (L505-521).
  * **How much:** Medium.
  * **Stakeholder Implications:** Unblocks Batch 7 (`converter process`); removes the last v1 write path.
  * **DoD:** `insert_problems_batch` on a fixture set (≥1 each of TSP/ATSP/CVRP/HCP/SOP, incl. EXPLICIT TSP, EXPLICIT CVRP with demands, HCP, SOP) round-trips into the correct hub + type-table rows with zero wrong-table rows; satellite rows (matrix/solutions/file_tracking) present where the fixture provides them; a forced mid-batch failure rolls back the whole batch; `converter process` on a small dir reports inserted > 0, failed == 0.
  * **Rework Verdict (2026-08-28, reviewer):** Verified — `insert_problems_batch` dispatches per type via `_insert_hub` + `_TYPE_INSERTERS` + `_insert_batch_satellites` in one explicit transaction; scratch-DB smoke: `total_inserted: 1`, `failed: 0`, hub + type rows round-trip, no `nodes`/v1-STI SQL, and a forced mid-batch CVRP demands-mismatch rolled back the whole batch (hub count unchanged). Tooling green on the file. DoD: pass for the v1-STI removal, v2 round-trip, and rollback clauses; `converter process` CLI end-to-end and multi-family satellite coverage re-asserted at the Batch 7 gate.

+ [x] **Task 1.5: Reconcile the v1-STI read paths in `operations.py`**
  * **What:** Rewrite `load` (L672), `query_problems` (L811), and `get_problem_stats` (L780) against schema v2: `load` must dispatch per type table and return the full type-table row (plus `tsplib_name`/`adjacency`/`fixed_edges` as its docstring claims); `query_problems` and `get_problem_stats` must stop referencing the removed STI columns (`dimension`, `capacity`, `edge_weight_type`, `edge_weight_format` on `problems`) and instead read from the hub joined to the type tables.
  * **Why:** These are live CLI read paths (`cli/commands.py` `stats`/`list` L213/L253/L294/L300/L318) that now crash with DuckDB Binder Errors (or, for `load`, silently return a hub-only row) because Task 1.1 dropped the STI columns they query. No existing task covers them.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/database/operations.py` L672 (`load`), L780 (`get_problem_stats`), L811 (`query_problems`); `export_problem` is Task 4.2's target (out of scope here).
  * **When:** After 1.1/1.4 (schema + write path landed); independent of Batches 3-4.
  * **How:** Hub `problems(name, type)` resolves to the owning type table; a per-type registry (same dispatch shape as `_TYPE_INSERTERS`) selects the type table and row factory; `query_problems` aggregates via `UNION ALL` over the type tables or drops the dimension/capacity filters to hub-only columns.
  * **How much:** Low-Medium.
  * **Stakeholder Implications:** `converter stats`/`converter list` commands; the Batch-4 test rewrites (`test_database.py` `query_problems`/`get_problem_stats` tests) depend on the final read shape.
  * **DoD:** `converter stats` and `converter list` run green against a v2 DB; `load('berlin52','TSP')` returns the TSP type-table row with coords; `query_problems(problem_type='TSP')` and `get_problem_stats()` return correct counts without a Binder Error.
  * **Rework Verdict (2026-08-28, reviewer):** NOT closed. Tooling clause for this file is green, but the functional DoD still fails on the live v2 schema (scratch-DB smoke, 2026-08-28): `get_problem_stats` raises `BinderException: Referenced column "dimension" not found in FROM clause` (still `SELECT AVG(dimension), MAX(dimension) FROM problems` on the hub, which has only `id, name, type, created_at, updated_at`); `query_problems` raises `IndexError: tuple index out of range` (still maps v1 column indices `row[4..7]` off the 5-column hub row and filters on `dimension`); `load` no longer hits v1-STI but returns only the hub row, not the full type-table row its docstring claims. Must redo: rewrite all three against the hub-join-to-type-tables shape. Out of scope for the tooling clause; registered as the open Batch-1 task.
  * **Review Verdict (2026-08-28, reviewer):** DONE. Verified against a scratch v2 DB built from `datasets_raw/problems/tsp/berlin52.tsp` (hub + type row via the v2 dispatch): `load('berlin52','TSP')` returns the full TSP type-table row joined to the hub — keys include `coords` (len 52), `display_coords`, `tsplib_name`, `edge_weight_type`, `edge_weight_format`, `dimension`, `comment` — with no Binder Error; `get_problem_stats()` returns `{"total_problems": 1, "by_type": [{"type": "TSP", "count": 1, "avg_dimension": 52.0, "max_dimension": 52}]}` (UNION ALL over the type tables, no `dimension` reference on the hub); `query_problems(problem_type='TSP')` returns the correct dict without IndexError/Binder and `query_problems(problem_type='VRP')` normalizes to CVRP (returns `[]`, no crash). DoD: pass. **Plan-wording correction:** the DoD's `converter stats` / `converter list` subcommands do not exist — the live consumers of `get_problem_stats`/`query_problems` are `converter validate` (L253) and `converter analyze` (L294/L300/L318), and both ran green against the scratch DB (exit 0); the plan's `Where` line numbers L213/L253/L294/L300/L318 were correct, only the `stats`/`list` command names were wrong. No rework needed — the code matches the intent.

## Batch 2 — API reconciliation + cost policy + venv hygiene — `implementer`

Ordering: 2.1 and 2.2 sequential after Batch 1; 2.3 and 2.4 are independent of
all batches and may run in parallel with anything.

+ [x] **Task 2.1: Reconcile or retire `api.py` + `insert_problem`/`insert_nodes`**
  * **What:** Decide the fate of the `SimpleConverter` API against v2 — rewrite or delete — and record the decision.
  * **Why:** Dead-schema write paths corrupt; stale-schema APIs lie. The old plan deferred this as "not on the critical path"; the schema changed beneath it, so it is no longer deferrable.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/api.py` L21 (`SimpleConverter`), L168–L240 (module-level functions).
  * **When:** After 1.2 (the v2 write path it would wrap must exist).
  * **How:** Grep the repo for consumers of `SimpleConverter` / `insert_problem` / `insert_nodes`; if none, delete the module and its tests; otherwise rewrite the write path over the Task-1.2 dispatch.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Determines whether the `test_converter_api.py` failures (Task 4.1) are rewritten or deleted.
  * **DoD:** Either `api.py` passes the v2 round-trip tests, or it and its tests are deleted with the rationale in the walkthrough; the decision is recorded in this task's Solution block.
  * **Options:** Recommended — retire if the grep finds no in-repo consumers (evidence-based, smallest surface); Alternative — full rewrite against v2 when consumers exist.
  * **Solution (decision recorded, 2026-08-28):**
    - **Decision:** REWRITE, not retire. A repo-wide grep found `convert_vrp.py` imports `from converter.api import process_directory`, so the module has an in-repo consumer and the "retire" option was off the table. `api.py` was rewritten over the v2 dispatch: `to_database`/`process_directory` now call `DatabaseManager.insert_problem(_merge_v2_payload(data))`; no `insert_nodes` reference remains (only a docstring comment at L90).
    - **Implication for Task 4.1:** `test_converter_api.py` is REWRITTEN (not deleted) against the v2 payload shape — its current `set(result.keys()) == {'problem_data','nodes','tours','metadata'}` assertion is a v1 key-set and will be replaced with the v2 key set (incl. `coords`/`demands`/`depots`/`edges`/`fixed_edges`).
    - **Implication for `convert_vrp.py`:** still imports `converter.api` (now a valid v2 consumer) and still carries its own `sys.path.insert` hack (L13) — redundant under Decision 8; registered as Task 2.5.
  * **Review Verdict (2026-08-28, reviewer):** FAIL — rework required. Mechanical clauses pass: no `insert_nodes` reference remains in `api.py`, and the write path uses `_merge_v2_payload` + `insert_problem`. But the rewrite is NOT a full v2 round-trip: `_merge_v2_payload` forwards only hub/type-table fields (`coords`/`demands`/`depots`/`edges`/`fixed_edges`) and drops `edge_weight_matrix`, `solution_data`, `file_path`/`checksum`/`file_size`. `insert_problem` itself writes only hub + type row (no satellites). Verified with `SimpleConverter.to_database` on `gr17.tsp` (EXPLICIT TSP): hub row + `tsp_problems` row land correctly (`coords IS NULL`), but `edge_weight_matrices` has **0 rows** — the matrix is the only distance data for an EXPLICIT problem, so the problem is stored unreadable (`load_matrix` would raise `NotFoundError`). Same gap drops `solutions` and `file_tracking`. Must redo: route the matrix/solution/file satellites through the API write path (reuse `_insert_batch_satellites` or extend `insert_problem`), then re-verify a full gr17 EXPLICIT round-trip (hub + type + matrix present).
  * **Rework Verdict (2026-08-28, reviewer):** DONE — verified with `SimpleConverter.to_database` on `datasets_raw/problems/tsp/gr17.tsp` (EXPLICIT TSP) into a scratch DB. `_merge_v2_payload` now forwards `edge_weight_data` (matrix + `edge_weight_format` + `metadata.is_symmetric`), `solution_data`, and `file_path`/`checksum`/`file_size`; `insert_problem` writes hub + `tsp_problems` row + `_insert_batch_satellites` (matrix / solutions / file_tracking) in one explicit transaction. Observed: hub `(1,'gr17','TSP')`; `tsp_problems` row `(EXPLICIT, LOWER_DIAG_ROW, coords IS NULL)`; `edge_weight_matrices` row present (`is_symmetric=True`); `load_matrix('gr17','TSP')` returns a 17×17 matrix; `file_tracking` row `(datasets_raw/problems/tsp/gr17.tsp, 1, 730)`. Injecting `solution_data` into the payload persists all three satellites in the same insert. Forced satellite failure (`is_symmetric=None` → NOT NULL) rolled back hub + type + matrix to zero rows (single-transaction proven). DoD: pass.

+ [ ] **Task 2.2: `solutions.cost` derivation policy — decide and implement**
  * **What:** Derive `solutions.cost` for `.opt.tour` (TSP) solutions from the tour's `TOUR_SECTION` + the problem's weight data. Drop the COMMENT-prose scrape entirely.
  * **Why:** The COMMENT field is a human annotation, not a data source. Measured across the 41 `.opt.tour` files: 23 scrape cost from a regex on prose COMMENT, 18 compute it from weights — two inconsistent paths producing one column, gated on whether a parenthesized number happened to be typed into a comment. Cost is deterministically derivable from `TOUR_SECTION` + weights; gating on COMMENT is backwards.
  * **Who:** Agent (implementer); decision owner: user.
  * **Where:** `src/converter/core/transformer.py` (`_parse_tour_file` L488, `_extract_cost_from_comment` L569), `src/converter/utils/cost.py`, `src/converter/utils/worker_functions.py` Step 4b.
  * **When:** After 1.2.
  * **How:** Per the chosen option; the gate suite (Task 5.1) gains the corresponding assertion.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Main-repo benchmarks consuming optima.
  * **DoD:** Decision recorded in this plan; `solutions.cost` for TSP solutions derived from weights (never COMMENT) with zero NULL where routes + weight data are complete, verified by gate test.
  * **Options:** A — always compute from `TOUR_SECTION` + weights (drop COMMENT); B — curated known-optima table (section 3.1 of `docs/reference/tsplib95_format.md` moved to a table file under `tour/`, looked up by name stem); C — table primary + compute fallback. (`.sol` explicitly out of scope: all 90 carry an explicit `Cost` line.)
  * **Solution (decision recorded, 2026-08-28):**
    - **Decision:** REOPENED, then RESOLVED as **Option C — table primary + compute fallback**. `COMMENT` is dead as a cost source; `_extract_cost_from_comment` is removed. `solutions.cost` is derived in priority order: (1) look up the known optimum by tour-file name stem in a new table file under `tour/` (source: `docs/reference/tsplib95_format.md` §3.1); (2) if the name is absent from the table, or the table entry is a bound `[low, high]` rather than an exact value, compute from `TOUR_SECTION` + weights via `compute_routes_cost`. Coverage measured 2026-08-28: of 41 tour files, the `alb*` family (10 files: `alb1000`/`alb2000`/`alb3000a–e`/`alb4000`/`alb5000`) is **absent** from §3.1 and must fall back to compute; several §3.1 entries are bounds, not exact. The fallback is therefore load-bearing, not best-effort.
  * **Review Verdict (2026-08-28, reviewer):** REOPEN — prior DONE verdict reviewed only the distance math, not the trigger. The "scrape COMMENT when present, compute when absent" policy yields two inconsistent code paths (23 scraped vs 18 computed across 41 tour files) and treats an annotation as data. Must redo: drop `_extract_cost_from_comment`, derive cost from weights for every `.opt.tour`, then re-verify. `berlin52 → 7542.0` was correct but only *coincidentally* exercised the right path (it has no COMMENT); the policy is still wrong.

+ [x] **Task 2.3: Retire the `converter_cli.py` sys.path hack**
  * **What:** Remove `sys.path.insert(0, .../src)` (L13); the editable install + `converter` entry point make it redundant.
  * **Why:** The hack is what made the walkthrough believe PYTHONPATH was "mandatory". Entry point is now canonical: `uv run converter ...`.
  * **Who:** Agent (implementer).
  * **Where:** `converter_cli.py` L13.
  * **When:** No dependencies; any time.
  * **How:** Delete the line; verify the two DoD commands; grep the repo for remaining `sys.path` manipulation.
  * **How much:** Trivial.
  * **Stakeholder Implications:** None — import resolution is unchanged via the editable install.
  * **DoD:** `uv run converter --help` and `uv run python -c "from converter.cli.commands import cli"` both exit 0; no `sys.path` manipulation remains in the repo.
  * **Solution:**
    - **Changed Files:**
      + [converter_cli.py L9](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/converter_cli.py#L9) — removed `import sys`/`import os` + the `sys.path.insert(0, .../src)` hack (L9–14 → L9).
    - **Summary:** Removed the cargo-culted `sys.path` hack from the CLI shim; the editable install resolves `converter` without path surgery. Both DoD commands exit 0, and the shim runs directly (`uv run python .../converter_cli.py --help`, exit 0).
    - **Technical Justification:** After Decision 8 (editable path source) the hack is dead weight and is what made the old walkthrough believe PYTHONPATH was "mandatory". Remaining `sys.path.insert` hits are confined to `convert_vrp.py` L13 (sibling script, `converter.api`-dependent — Task 2.1) and `tests/**` shims (Task 6.3); both out of this task's `Where`.
    - **DoD Compliance:** Both commands exit 0 (verified); "no sys.path manipulation" holds for the task's `Where` (converter_cli.py). Repo-wide remaining hits are owned by Tasks 2.1/6.3 — boundary reported in walkthrough, reviewer to confirm.
    - **Artifacts:**
      + 📝 [walkthrough_2-3_2-4.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-3_2-4.md) — Walkthrough
      + 📚 [knowledge_converter-db-path-resolution.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_converter-db-path-resolution.md) — Knowledge
    - **Review Verdict (2026-08-28, reviewer):** DONE. `converter_cli.py` is clean — 12 lines, `import sys`/`import os` gone, the `sys.path.insert(0, .../src)` hack removed, `cli()` called under `__main__` (AST-parse verified). Both DoD commands exit 0: `uv run converter --help` (0) and `uv run python -c "from converter.cli.commands import cli"` (0); the direct shim `uv run python .../converter_cli.py --help` also exits 0. DoD: pass for the task's `Where`. **Adjudication of the repo-wide clause** ("no `sys.path` manipulation remains in the repo"): not literally met — remaining hits are `tests/**` (13 files, owned by Task 6.3) and `convert_vrp.py` L13 (sibling script, not previously owned — registered as **Task 2.5** below, tied to this task's 2.1 decision). `.venv/**` and site-packages hits are third-party and out of scope.

+ [x] **Task 2.4: Point `config.yaml`'s default `database_path` at the canonical DB**
  * **What:** Replace the stale default `./datasets/db/routing.duckdb` (L15 — that directory does not exist) with the canonical `db/routing.duckdb`, or document the required override.
  * **Why:** A default pointing at a nonexistent path makes every flag-less run silently create/query the wrong DB — the same failure class as the stale husk.
  * **Who:** Agent (implementer).
  * **Where:** `config.yaml` L15.
  * **When:** No dependencies; any time.
  * **How:** Update the default; if relative-path resolution differs between the entry point and the CLI shim, document the override in config comments.
  * **How much:** Trivial.
  * **Stakeholder Implications:** Batch 7 rebuild commands rely on this default when `-o` is not passed.
  * **DoD:** `uv run converter process` without an explicit `-o`/db flag targets the canonical `db/routing.duckdb` (verified by a file-tracking row), or the override is documented in `config.yaml` comments.
  * **Solution:**
    - **Changed Files:**
      + [config.yaml L15](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/config.yaml#L15) — `database_path: "./db/routing.duckdb"` + a 13-line comment documenting that `converter process` derives its DB path from `-o` (not `database_path`) and how to target the canonical DB.
    - **Summary:** Pointed the config default at the canonical `db/routing.duckdb` and documented the required override. `load_config('config.yaml').database_path` returns `'./db/routing.duckdb'` (exit 0).
    - **Technical Justification:** DoD alternative (A) is unreachable from config.yaml: `process` computes `db_path = Path(output)/'db'/'routing.duckdb'` from `-o` (default `./datasets`, commands.py L132/L136) and never reads `database_path` — so the documented-override alternative (B) is delivered: run with `-o <submodule-root>` to land at the canonical DB. Verified via `process --help` (shows the `-o` default) + source.
    - **DoD Compliance:** Alternative (B) satisfied — override documented in `config.yaml` comments; value updated to canonical and read back by `load_config`. `converter process` was not run (would write `./datasets/db/routing.duckdb` outside the task footprint and hit Task 1.5's broken `get_problem_stats`).
    - **Artifacts:**
      + 📝 [walkthrough_2-3_2-4.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-3_2-4.md) — Walkthrough
      + 📚 [knowledge_converter-db-path-resolution.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_converter-db-path-resolution.md) — Knowledge
    - **Review Verdict (2026-08-28, reviewer):** DONE (alternative B). `config.yaml` L15 now reads `database_path: "./db/routing.duckdb"` with a comment documenting the `-o` derivation, and `load_config('config.yaml').database_path` returns `'./db/routing.duckdb'` (verified). DoD alternative (B) — documented override — is satisfied; alternative (A) is correctly diagnosed as unreachable from config.yaml because `process` derives `db_path = Path(output)/'db'/'routing.duckdb'` from `-o` and never reads `database_path`. DoD: pass. **Incidental finding adjudicated:** the implementer is right that `converter process` ignores `database_path`; the stale defaults that remain are NOT limited to `config.py` L21 and `cli/commands.py` L360 — they also include the CLI `-d` defaults (`validate`/`export-parquet` → `./datasets/db/routing.duckdb`; `inspect` → `./datasets_processed/db/routing.duckdb`) and the `converter init` template that regenerates the stale config. These are the same failure class this task's `Why` calls out (defaults pointing at nonexistent paths), so a follow-up is registered — **Task 2.6** below.

+ [x] **Task 2.5: Remove the `sys.path` hack from `convert_vrp.py` (residual of 2.3)**
  * **What:** Delete `sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))` (L13) and the now-unused `import sys`/`import os` from the sibling VRP script.
  * **Why:** Task 2.1 kept `converter.api` alive (in-repo consumer), so `convert_vrp.py` stays a valid consumer — but its cargo-culted path hack is exactly the superstition Decision 8 retired; it is the last non-test `sys.path.insert` in the repo and is what Task 2.3's repo-wide DoD clause ("no `sys.path` manipulation remains in the repo") misses.
  * **Who:** Agent (implementer).
  * **Where:** [convert_vrp.py L13](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/convert_vrp.py#L13).
  * **When:** After 2.1 (its fate depends on `api.py` surviving) and 2.3; independent of Batches 3-4.
  * **How:** Delete L9–L13 (`import sys`/`import os` + the `sys.path.insert` line); keep `from converter.api import process_directory` (resolves via the editable install, same proof as 2.3).
  * **How much:** Trivial.
  * **Stakeholder Implications:** None — import resolution is unchanged via the editable install.
  * **DoD:** `grep -n "sys.path" convert_vrp.py` is empty; `uv run python -c "import convert_vrp"` exits 0 (editable install resolves the import without the hack); `uv run python convert_vrp.py /tmp /tmp` runs the script body without `ImportError`.
  * **Review Verdict (2026-08-28, reviewer):** DONE. `grep -n "sys.path" convert_vrp.py` is empty (exit 1); `uv run python -c "import convert_vrp"` exits 0 via the editable install; `uv run python convert_vrp.py <empty-in> <empty-out>` runs the script body to completion (exit 0, no `ImportError`). F401 adjudication: `import os`/`import sys` are NOT unused — the body still uses `sys.argv`, `sys.exit`, `os.path.exists`; `ruff --select F401,F811 convert_vrp.py` → "All checks passed". Non-blocking, no follow-up. DoD: pass.

+ [x] **Task 2.6: Align the remaining DB-path defaults with the canonical `db/routing.duckdb`**
  * **What:** Replace the stale DB-path defaults that still point at nonexistent `./datasets/db/` / `./datasets_processed/db/` paths: `src/converter/config.py` L21 dataclass default; `src/converter/cli/commands.py` `init` config template (~L360), `validate` `-d` default (~L231), `export-parquet` `-d` default (~L383), `inspect` `-d` default (~L478); and decide whether `process` should keep deriving its DB path from `-o` (document if so).
  * **Why:** Task 2.4 fixed `config.yaml` but the fallbacks that regenerate or reference the stale path still exist — the same "default points at a nonexistent path" failure class the task's `Why` names. A fixed config.yaml is silently overwritten the moment `converter init` re-emits the old template.
  * **Who:** Agent (implementer).
  * **Where:** [src/converter/config.py L21](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/config.py#L21); [src/converter/cli/commands.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/cli/commands.py) (~L231/L360/L383/L478).
  * **When:** No dependencies; after 2.4 (keeps the documented override consistent).
  * **How:** Repoint every default to `db/routing.duckdb` (relative to the submodule root where the commands are invoked) and mirror the config.yaml comment in the `init` template; keep `process`'s `-o`-derived path but make its comment/help text state that `database_path` is not consulted.
  * **How much:** Low.
  * **Stakeholder Implications:** Batch 7 rebuild commands and `converter validate`/`analyze`/`export-parquet`/`inspect` flag-less runs; `converter init` output.
  * **DoD:** `grep -n "datasets/db/routing.duckdb\|datasets_processed/db/routing.duckdb"` over `src/converter/` returns no matches; `converter init` regenerated config has `database_path: "./db/routing.duckdb"`; `converter validate -d`/`export-parquet -d`/`inspect -d` help text shows the canonical default.
  * **Review Verdict (2026-08-28, reviewer):** DONE. `grep -rn "datasets/db/routing.duckdb\|datasets_processed/db/routing.duckdb" src/converter/` returns no matches; `config.py` dataclass default is `"./db/routing.duckdb"`; `converter init -o <tmp>/config.yaml` regenerates `database_path: "./db/routing.duckdb"` plus the NOTE comment (stale-path grep on the regenerated file is clean); `validate -d`/`export-parquet -d`/`inspect -d` help text all show `(default: ./db/routing.duckdb)`; `process` `-o` help now states `database_path` is NOT consulted and how to target the canonical DB. Pre-existing ruff debt in `config.py`/`cli/commands.py` (UP006/UP035/UP015/I001/F401/F841/F541/RUF003) is untouched by this diff and out of scope; the touched `api.py`/`operations.py`/`convert_vrp.py` are ruff-clean. DoD: pass.

## Batch 3 — Triage: suspected real bugs — `implementer`

Ordering: 3.1 and 3.2 are independent files; may run in parallel after Batch 1 (Decision 4 — no repairs against the v1 schema). Every triage task classifies each failure as **real bug** (fix in `src/`) or **v1-behavior assertion** (rewrite against v2) — never a blind "make it pass". The 2026-08-28 run's 18 failures are distributed across Batches 3–4 by owning file: 6 + 2 here, 10 in Batch 4.

+ [ ] **Task 3.1: Triage + resolve `test_scanner.py` (6 failures)**
  * **What:** Classify and resolve:
    - `TestFileScannerScanFiles::test_scan_files_recursive_all_patterns`,
    - `TestFileScannerScanDirectory::test_scan_directory_batches`,
    - `TestFileScannerScanDirectory::test_scan_directory_partial_batch`,
    - `TestFileScannerScanDirectory::test_scan_directory_problem_type_detection`,
    - `TestFileScannerFileCount::test_get_file_count_all_patterns`,
    - `TestFileScannerIntegration::test_full_workflow_scan_and_process`.
  * **Why:** The scanner feeds all ingestion — a real bug here poisons every pipeline run, and the Batch-9 spike families extend it.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_scanner.py`; fix target `src/converter/core/scanner.py` (if classified as real bug).
  * **When:** After Batch 1.
  * **How:** Run the file in isolation; per failure, read the assertion against the implementation; classify; fix `src/` for real bugs, rewrite the test for v1-behavior assertions.
  * **How much:** Medium.
  * **Stakeholder Implications:** Batch 9 (all three spike families build on the scanner).
  * **DoD:** Each of the 6 failures has its classification recorded in the Solution block; the file is green; any `src/` fix is covered by the rewritten test.

+ [ ] **Task 3.2: Triage + resolve `test_cordeau.py` (2 failures)**
  * **What:** Classify and resolve:
    - `TestCordeauIntegration::test_full_pipeline_p01`,
    - `TestCordeauIntegration::test_json_output_p01`.
  * **Why:** Cordeau is a Batch-9 ingestion family; if these are real parser bugs, the spike builds on broken ground.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_formats/test_cordeau.py`; fix target `src/tsplib_parser/cordeau/` (if classified as real bug).
  * **When:** After Batch 1.
  * **How:** Same triage method as 3.1.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Blocks Task 9.3 (Cordeau spike).
  * **DoD:** Both failures classified in the Solution block; file green.

## Batch 4 — Triage: v1-behavior + obsolete tests — `implementer`

Ordering: 4.1 after 2.1 (its fate depends on the `api.py` decision); 4.4 after
1.1 (`_migrate_schema` retired there); 4.2, 4.3, 4.5 after 1.2. Independent
files — may run in parallel once their dependencies land. Same classification
discipline as Batch 3.

+ [ ] **Task 4.1: Resolve `test_converter_api.py` (2 failures) per the 2.1 decision**
  * **What:** `TestSimpleConverterParsing::test_parse_file_returns_expected_structure`, `TestSimpleConverterIntegration::test_consistency_across_multiple_files` — rewrite against v2 if `api.py` survives; delete the file if Task 2.1 retires the module.
  * **Why:** These assert the v1 API's return structure; their correct form is decided by 2.1, not guessable now.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_converter_api.py`.
  * **When:** After 2.1.
  * **How:** Apply the 2.1 outcome; if rewritten, assert the v2 payload shape (array-column keys, hub + type rows).
  * **How much:** Low.
  * **Stakeholder Implications:** None beyond the suite.
  * **DoD:** File green or deleted with the 2.1 rationale cross-referenced.

+ [ ] **Task 4.2: Resolve `test_database.py::TestDatabaseManagerExport::test_export_problem_nonexistent_raises_error`**
  * **What:** One failure — classify and resolve against the v2 export path.
  * **Why:** `export_problem` (operations.py L806) queries the v1 STI table; the v2 export must dispatch per type table, so the error path may have moved.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_database.py`; `src/converter/database/operations.py` L806 (`export_problem`).
  * **When:** After 1.2.
  * **How:** Check whether `export_problem` still raises the expected error for a nonexistent ID under v2; rewrite the assertion or fix the export path.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Classification recorded in the Solution block; test green.

+ [ ] **Task 4.3: Rewrite `test_database_connection_leak.py` (4 failures) against v2 transactions**
  * **What:** `TestConnectionLeakFix::test_insert_problem_atomic_success`, `TestConnectionLeakFix::test_connection_cleanup_after_failure`, `TestConnectionLeakFix::test_parallel_inserts_no_connection_leak`, `TestConnectionLeakFix::test_edge_weight_insertion_with_transaction` — the v1 insert paths they exercise are replaced by Task 1.2's single-transaction dispatch.
  * **Why:** These are behavioral guards, not dead weight — the leak/atomicity properties must be re-pinned against the v2 write path, not deleted.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_database_connection_leak.py`.
  * **When:** After 1.2 (final transaction shape).
  * **How:** Rewrite each test over the Task-1.2 dispatch: atomic hub+type insert, forced-failure rollback, parallel worker inserts.
  * **How much:** Medium.
  * **Stakeholder Implications:** Guards the same properties the Batch-7 rebuild depends on under `--parallel`.
  * **DoD:** All four rewritten against v2 and green; each failure's original classification recorded in the Solution block.

+ [ ] **Task 4.4: Retire `test_schema_migration_fixes.py` (2 failures) with `_migrate_schema`**
  * **What:** `TestDatabaseErrorUsage::test_insert_valid_data_no_database_error`, `TestSchemaConsistency::test_insert_problem_with_vrp_fields` — the migration machinery they test is deleted in Task 1.1 (v2 is clean-slate, not a migration).
  * **Why:** Testing a deleted code path is definitionally obsolete; the useful residue (insert-valid-data acceptance) is re-covered by the Batch-5 suites.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_schema_migration_fixes.py`.
  * **When:** After 1.1.
  * **How:** Confirm the acceptance intent is covered by Tasks 5.1–5.3, then delete the file.
  * **How much:** Low.
  * **Stakeholder Implications:** Suite size shrinks; coverage is explicitly transferred, not lost.
  * **DoD:** File deleted; the Solution block names which Batch-5 test inherits each retired assertion.

+ [ ] **Task 4.5: Resolve `test_transformer.py::TestDataTransformerBasic::test_transform_problem_returns_expected_keys`**
  * **What:** One failure — the asserted key set is the v1 payload; v2 emits array-column keys (`coords`/`demands`/`depots`) and no `nodes` list.
  * **Why:** Almost certainly a v1-behavior assertion, but classify before rewriting — a wrong key set would silently corrupt every type-table row.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_transformer.py`; `src/converter/core/transformer.py` L31 (`transform_problem`).
  * **When:** After 1.2.
  * **How:** Assert the exact v2 key set per type; parametrize if the key set differs per type.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Classification recorded in the Solution block; test green against the v2 payload.

## Batch 5 — New committed suites — `implementer`

Ordering: after Batches 3–4 (the suite they extend must be green); 5.1 → 5.2 →
5.3 sequential (same new test files).

+ [ ] **Task 5.1: Committed hermetic gate suite**
  * **What:** New `tests/test_schema_v2_gate.py` that builds a fixture DB from `datasets_raw` into `tmp_path` and asserts, adapted to v2: per-type counts via the hub; EXPLICIT ↔ matrix 1:1 per type; zero HCP matrix rows + `adjacency IS NOT NULL` on all HCP rows; `linhp318.fixed_edges == [[0,213]]`; zero duplicate `(name,type)`; att48 name-twin resolves to both type tables; array length == dimension for `coords`/`demands`; NOT NULL enforcement (negative insert tests); orphan rejection via FK; spot-checks berlin52 / br17 / eil13 / att48 / alb1000. Accepts an optional `--db-path` / env var to run the **same** assertions against the canonical DB locally (default: hermetic, so CI never depends on the main repo).
  * **Why:** This is the old plan's Batch-5 gate done properly — versioned, CI-run, and impossible to "pass" by deleting a failing check without a tracked diff.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_schema_v2_gate.py` (new); `tests/conftest.py` (`pytest_addoption`); fixtures from `datasets_raw/` via the Task-1.2 write path.
  * **When:** After Batches 3–4.
  * **How:** Session-scoped pytest fixture builds the DB once into `tmp_path`; `--db-path` registered via `pytest_addoption` in `conftest.py`; assertions read through DuckDB read-only connections.
  * **How much:** Medium.
  * **Stakeholder Implications:** Becomes the Batch-7 gate and the CI regression net (Task 6.4).
  * **DoD:** Suite green on `tmp_path` fixture in CI; locally reproducible against the canonical DB via `--db-path`.

+ [ ] **Task 5.2: Coverage for the previously untested schema surface**
  * **What:** Committed tests for `tsplib_name`, `fixed_edges`, `adjacency` — currently zero committed coverage.
  * **Why:** These columns exist to serve SOP/HCP/alias semantics; untested schema surface is how the review found zero coverage after a "passing" gate.
  * **Who:** Agent (implementer).
  * **Where:** `tests/` (extend the gate file or a focused `test_schema_v2_surface.py`).
  * **When:** After 5.1.
  * **How:** One assertion cluster per column, fed by the hermetic fixture DB.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Grep finds `tsplib_name`, `fixed_edges`, `adjacency` in `tests/`; each assertion traces to a decision in this plan.

+ [ ] **Task 5.3: Pinned-behavior tests (demands array + cost policy)**
  * **What:** Commit the intentionally retained behaviors as tests: EXPLICIT-CVRP demands live in the `demands` array column (not fabricated rows); the Task-2.2 cost decision is asserted exactly as decided.
  * **Why:** Behaviors that are deliberate but unpinned get "fixed" away by the next refactor; pinning is what turns decisions into invariants.
  * **Who:** Agent (implementer).
  * **Where:** `tests/` (same home as 5.2).
  * **When:** After 5.1 and 2.2.
  * **How:** Assert `demands` array content/length for an EXPLICIT CVRP fixture; assert the cost outcome per the 2.2 record.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Both behaviors have committed assertions that fail if the behavior is silently changed.

## Batch 6 — Test hygiene + CI — `implementer`

Ordering: 6.2 any time; 6.1 and 6.4 after 5.1 (the gate suite must exist); 6.3
after Batches 3–4 (it sweeps the same files those batches rewrite).

+ [ ] **Task 6.1: Retire `tests/verify_database.py`**
  * **What:** Delete the stale script: it queries the removed `matrix_json` column and the nonexistent path `datasets/db/routing.duckdb`.
  * **Why:** A verification script that cannot run against any real DB is the exact artifact class that enabled gate-by-attrition.
  * **Who:** Agent (implementer).
  * **Where:** `tests/verify_database.py`.
  * **When:** After 5.1 (its legitimate assertions are superseded by the gate suite — confirm coverage before deleting).
  * **How:** Diff its assertions against the Task-5.1 suite; delete the file; record any uncovered assertion in the Solution block.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** File deleted; every assertion it carried is either covered by 5.1 or explicitly recorded as dropped.

+ [ ] **Task 6.2: Deduplicate the pytest configuration**
  * **What:** `pytest.ini` (285 B) and `pyproject.toml [tool.pytest.ini_options]` (L55) both exist — keep exactly one source of truth.
  * **Why:** Two configs drift; CI and local runs can silently select different options — the same class of lie as the two validation scripts.
  * **Who:** Agent (implementer).
  * **Where:** `pytest.ini`; `pyproject.toml` L55.
  * **When:** No dependencies; any time.
  * **How:** Keep `pyproject.toml`, delete `pytest.ini`; port any ini-only options first; verify `uv run pytest` collects the same 217 tests.
  * **How much:** Trivial.
  * **Stakeholder Implications:** CI (Task 6.4) must use the same config.
  * **DoD:** One config file remains; collected-test count unchanged.
  * **Options:** Recommended — consolidate into `pyproject.toml` (single project file); Alternative — keep `pytest.ini` if pyproject options prove insufficient (record why).

+ [ ] **Task 6.3: Migrate test imports `from src.converter` → `from converter`**
  * **What:** Sweep `tests/` for `src.`-namespace imports; the editable install guarantees `converter` resolves.
  * **Why:** `src.`-imports only work by accident of CWD and re-create the same import-resolution superstition as the PYTHONPATH hack.
  * **Who:** Agent (implementer).
  * **Where:** `tests/` (all files matching `from src.` / `import src.`).
  * **When:** After Batches 3–4 (they rewrite the same files — avoid conflicts).
  * **How:** Mechanical rename; run the full suite after.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Grep for `from src.\|import src.` in `tests/` is empty; suite green.

+ [ ] **Task 6.4: CI runs where the work happens**
  * **What:** Add `dev` to `.github/workflows/ci.yml` push triggers (push currently targets `main`, `full-implementation` at L5; PRs target `main` at L7 — the gate would never run on the branch where Decision 10 puts the work).
  * **Why:** A gate that cannot run on the working branch is decoration; this is how the red suite survived to the review.
  * **Who:** Agent (implementer).
  * **Where:** `.github/workflows/ci.yml` L5.
  * **When:** After 5.1 (so the gate suite exists when CI starts running on `dev`).
  * **How:** `branches: [main, full-implementation, dev]` on push.
  * **How much:** Trivial.
  * **Stakeholder Implications:** Every `dev` push now runs the full suite.
  * **DoD:** CI green on a `dev` push.

## Batch 7 — Rebuild + gate + consumer smoke — `implementer`, gate: `reviewer` — sequential (7.1 → 7.2 → 7.3 → 7.4)

+ [ ] **Task 7.1: Run the v2 rebuild to scratch output**
  * **What:** Full ingestion run into a throwaway output directory — never directly over the canonical DB.
  * **Why:** Rebuilding in place couples a failed run to a destroyed canonical artifact; scratch-then-promote keeps the failure atomic.
  * **Who:** Agent (implementer).
  * **Where:** Repo root; output `/tmp/routing_rebuild_v2/`.
  * **When:** After Batch 6 (green suite + gate on `dev`).
  * **How (from repo root — note the absence of PYTHONPATH):**

    ```bash
    uv run converter process \
      -i datasets/problems -o /tmp/routing_rebuild_v2 --force --parallel --workers 4
    ```

  * **How much:** Low.
  * **Stakeholder Implications:** None — writes only to `/tmp`.
  * **DoD:** CLI reports 198 processed, 0 failed; `/tmp/routing_rebuild_v2/db/routing.duckdb` exists. (Byte-counts are not a DoD — the gate in 7.3 is.)

+ [ ] **Task 7.2: Promote the scratch DB to canonical `db/routing.duckdb`**
  * **What:** Replace the canonical file with the verified scratch build.
  * **Why:** The canonical path is what consumers resolve; promotion is a deliberate, logged act — not a side effect of the rebuild command.
  * **Who:** Agent (implementer).
  * **Where:** `db/routing.duckdb` (submodule).
  * **When:** After 7.1.
  * **How:** Move the current canonical file aside (`db/routing.duckdb.v1-backup`, deleted after 7.3 passes), then `cp /tmp/routing_rebuild_v2/db/routing.duckdb db/routing.duckdb`.
  * **How much:** Trivial.
  * **Stakeholder Implications:** Main-repo consumers (Batch 8) see the v2 schema from this point.
  * **DoD:** Canonical path opens read-only and the hub row count is > 0.

+ [ ] **Task 7.3: Validate the canonical DB with the committed gate suite**
  * **What:** Run the Task-5.1 suite against the promoted DB.
  * **Why:** The gate is the DoD — never a byte-count again (old Task 4.3's `> 12 KB` certifies nothing).
  * **Who:** Agent (implementer); verification: reviewer.
  * **Where:** Submodule root.
  * **When:** After 7.2.
  * **How:** `uv run pytest tests/test_schema_v2_gate.py --db-path db/routing.duckdb`.
  * **How much:** Low.
  * **Stakeholder Implications:** On pass, the v1 backup from 7.2 is deleted.
  * **DoD:** All assertions green + per-type count table and spot-check report appended to this task's Solution block (pinned expectations: total 198; TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41).

+ [ ] **Task 7.4: Consumer smoke test**
  * **What:** From the main repo: `DatabaseLoader().load("berlin52")` against the v2 canonical DB.
  * **Why:** The DB exists to be consumed; a gate that never loads through the real consumer certifies a write-only artifact.
  * **Who:** Agent (implementer).
  * **Where:** `src/loaders/database_loader.py` L127 (`load`), main repo.
  * **When:** After 7.3.
  * **How:** Run the loader in a fresh process from the main repo root.
  * **How much:** Low.
  * **Stakeholder Implications:** Expected RED today — see Batch 8. A failure here is not a surprise; an unregistered failure is.
  * **DoD:** Either green, or every failure is mapped to a Batch-8 task.

## Batch 8 — Tracked main-repo dependencies (out of submodule scope; NOT "deferred")

> [!note]
> These block end-to-end consumption of the DB this plan produces. They live in
> the main repo, so they are registered here as dependencies with owners and
> DoDs — not parked in a "do not touch yet" list. Ordering: 8.1 and 8.2
> independent (may run in parallel); 8.3 after both; 8.4 after 7.2.

+ [ ] **Task 8.1: Break the circular import `distances/matrix.py` ↔ `protocols/problem_context.py`**
  * **What:** First `DatabaseLoader.load()` on a fresh process raises `ImportError`; `problem_context.py` imports `BackendModule` (L58) and `compute_distance_matrix` (L59) at module level.
  * **Why:** A loader that explodes on first use makes the canonical DB unreadable in any clean process (CI, notebooks, scripts).
  * **Who:** Agent (implementer).
  * **Where:** `src/protocols/problem_context.py` L58–L59; `src/distances/matrix.py` (main repo).
  * **When:** No dependencies; blocks 7.4.
  * **How:** Move the `BackendModule` import under `TYPE_CHECKING` (or lazy-import inside the consuming function); re-run a fresh-process import check.
  * **How much:** Low.
  * **Stakeholder Implications:** Every main-repo consumer of the loader.
  * **DoD:** Fresh-process `DatabaseLoader().load("berlin52")` raises no `ImportError`.

+ [ ] **Task 8.2: Repoint consumers off hardcoded `datasets/routing.duckdb`**
  * **What:** `orchestration.py:315` and `run_chapter4_benchmark.py:154` build a path to the stale `datasets/routing.duckdb`; `DatabaseLoader`'s default has the same problem.
  * **Why:** Hardcoded stale paths are how a 48.5 MB dead husk stayed load-bearing for months; the fix must be config-driven, not a fresh hardcode.
  * **Who:** Agent (implementer).
  * **Where:** `src/benchmarking_v2/orchestration.py` L315; `src/benchmarks_v2/run_chapter4_benchmark.py` L154; `src/loaders/database_loader.py` (default path) — main repo.
  * **When:** No dependencies; blocks 7.4.
  * **How:** Introduce a single config/env resolution for the canonical `db/routing.duckdb`; repoint all three call sites to it.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Benchmark reproducibility.
  * **DoD:** Grep finds no `datasets/routing.duckdb` literal; the loader resolves the canonical DB from a fresh process.

+ [ ] **Task 8.3: Per-type dispatch in `Problem` model / `DatabaseLoader`**
  * **What:** The loader reads only TSP/ATSP/CVRP (docstring L39); SOP/HCP rows are stored but unreadable. Implement the registry dispatcher (user-approved, DRY/ORM-style): `get_problem(name, type)` → `{type: (table, row_factory)}`.
  * **Why:** A discovery hub whose consumer can only read three of five types re-creates the v1 lie — stored but inaccessible data.
  * **Who:** Agent (implementer).
  * **Where:** `src/loaders/database_loader.py` L35 (class), L127 (`load`) — main repo.
  * **When:** After 8.1 and 8.2.
  * **How:** Registry dict keyed by type; each entry knows its table and row factory; hub lookup resolves `name` → `(id, type)`; dispatch loads from the type table.
  * **How much:** Medium.
  * **Stakeholder Implications:** Unlocks SOP/HCP benchmarks.
  * **DoD:** All five types load; dispatch covered by tests.

+ [ ] **Task 8.4: Reconcile inspect tooling against v2**
  * **What:** The old plan targeted `datasets/inspect_database.py` — verified absent from the repo 2026-08-28. The live inspect surface is the submodule's `tests/test_integration/test_inspect.py`; rewrite it against v2 or retire it.
  * **Why:** Inspection tooling against a dead schema certifies nothing, and an absent file in a DoD is how tasks pass vacuously.
  * **Who:** Agent (implementer).
  * **Where:** `src/submodules/Routing_data/tests/test_integration/test_inspect.py`.
  * **When:** After 7.2 (a canonical v2 DB exists to inspect).
  * **How:** Point it at the hermetic fixture DB or `--db-path`; rewrite queries per v2; otherwise delete with rationale.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Runs green against the v2 schema, or is deleted with the decision recorded.

## Batch 9 — Spike (unscheduled): new ingestion families

> [!note]
> One spike per family. Deliverable per spike: ingestion task breakdown with
> effort estimates — tasks registered, or the family explicitly rejected with
> rationale. Ordering: unscheduled; 9.3 blocked by 3.2.

+ [ ] **Task 9.1: Spike — Solomon (`C101.txt`) ingestion**
  * **What:** Assess scanner patterns + parser dispatch + transformer rules for the Solomon VRPTW format.
  * **Why:** VRPTW is the largest missing benchmark family; feasibility is unknown until the format is actually read against the current pipeline.
  * **Who:** Agent (implementer).
  * **Where:** `src/converter/core/scanner.py` (patterns); `src/tsplib_parser/` (dispatch).
  * **When:** Unscheduled; after Batch 3.
  * **How:** Read `C101.txt`; trace what the scanner/parser would need; estimate, do not implement.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Registers a new batch if accepted.
  * **DoD:** Spike report with per-task breakdown + estimates, or explicit rejection with rationale.

+ [ ] **Task 9.2: Spike — UMalaga mdvrp ingestion**
  * **What:** Assess the mdvrp family; a converter "already kinda" exists — determine the gap to production. (`datasets_raw/umalaga/` is already present.)
  * **Why:** Partial prior art makes this the cheapest family to land, but "kinda exists" is not an assessment.
  * **Who:** Agent (implementer).
  * **Where:** `src/tsplib_parser/cordeau/` (the likely prior art — confirm in the spike); `datasets_raw/umalaga/`.
  * **When:** Unscheduled; after Batch 3.
  * **How:** Run the existing converter against sample files; enumerate what breaks; estimate, do not implement.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Registers a new batch if accepted.
  * **DoD:** Spike report with gap list + estimates, or explicit rejection with rationale.

+ [ ] **Task 9.3: Spike — Cordeau ingestion**
  * **What:** Assess the Cordeau family once its tests are green.
  * **Why:** `test_cordeau.py` is red until Task 3.2 — spiking over a red base conflates format unknowns with known breakage.
  * **Who:** Agent (implementer).
  * **Where:** `tests/test_converter/test_formats/test_cordeau.py`; `src/tsplib_parser/cordeau/`.
  * **When:** Unscheduled; blocked by 3.2.
  * **How:** Same method as 9.1.
  * **How much:** Low–Medium.
  * **Stakeholder Implications:** Registers a new batch if accepted.
  * **DoD:** Spike report with per-task breakdown + estimates, or explicit rejection with rationale.

## Closed items (record, do not re-open)

| Item | Resolution | Date |
| --- | --- | --- |
| Root `[tool.uv.sources]` git-main shadowing | Editable path source; verified `import converter` → local submodule | 2026-08-28 |
| Phantom workspace member `data/Routing_data/vrp_database` | Removed from root `pyproject.toml` | 2026-08-28 |
| PYTHONPATH in pinned commands | Retired; was never load-bearing (`converter_cli.py` sys.path hack); entry point now canonical | 2026-08-28 |
| 48.5 MB git-tracked stale husk | Removed from tracking; zero tracked `.duckdb` | 2026-08-28 |
| Tasks 4.1/4.2 contradictory DoDs (old plan) | 4.1 DoD replaced by root-env `uv run python -c "import pandas"`; submodule `.venv` no longer re-created by design | 2026-08-28 |
| Uncommitted rebuild work | Baseline committed as `c427eda` on `main`; `dev` branch active | 2026-08-28 |

## Evidence appendix (review artifacts, 2026-08-28)

**Gate-by-attrition** — first `/tmp` script vs "final":

| First-script assertion | Reality | Fate |
| --- | --- | --- |
| C3b/C12 via `edge_weight_format='EXPLICIT'` | Wrong column | Legitimately fixed to `edge_weight_type` |
| C6b "HCP has zero node rows" | 27 000 rows | Dropped → FYI |
| S5 "alb1000 no nodes" | 1 000 rows | Dropped → FYI |
| S1 "berlin52 cost 7542" | cost NULL | Dropped → FYI |
| S2 "br17 opt 39 solution" | no solution row | Dropped → FYI |

**PYTHONPATH redundancy proof** (run 2026-08-28, repo root):

```bash
uv run python src/submodules/Routing_data/converter_cli.py --help   # exit 0, no PYTHONPATH
uv run python -c "import converter; print(converter.__file__)"
# -> .venv/site-packages/converter/__init__.py   (BEFORE the venv-control fix)
# -> src/submodules/Routing_data/src/converter/__init__.py  (AFTER, editable)
```
