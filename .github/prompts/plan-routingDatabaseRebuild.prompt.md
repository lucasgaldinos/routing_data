---
title: "Routing_data Database Rebuild — Registered Implementation Plan"
description: >
  Decomposed, decision-pinned implementation plan for rebuilding db/routing.duckdb
  from datasets/problems via the Routing_data submodule ETL. Resolves the eleven
  open design decisions (matrix representation, edge/fixed-edge extraction, type
  vocabulary, temp-id mapping, NotFound semantics) into 5W2H tasks grouped into
  five context-shared batches.
created: 2026-08-26
status: draft
author:
  - "[[Lucas Galdino]]"
type: guide
scope: local
modifications:
  - date_modified: 2026-08-26
    modifications:
      - description: >
          Replaced the draft 11-step checklist with the finalized registered plan:
          pinned all eleven decisions, decomposed the work into five 5W2H batches,
          and assigned workers (implementer vs reviewer).
  - date_modified: 2026-08-27
    modifications:
      - description: >
          Reviewer registration pass over Batches 1-3: per-task review verdicts
          appended to each Solution block, checkboxes marked [x] where DoDs were
          live-verified (REQ-1 tour fix and Decision #10 row-order RETURNING
          fallback confirmed in code and against DuckDB 1.5.5), Task 1.3 reverted
          to [ ] with a must-redo note for REQ-2 (new repo-relative absolute
          import in parser.py breaks the documented rebuild command), and a new
          Task 1.4 registered for the fix.
  - date_modified: 2026-08-27
    modifications:
      - description: >
          Batch 5 validation gate executed (reviewer): all 20 pinned assertions
          and spot-checks pass against the rebuilt db/routing.duckdb (read-only).
          Tasks 1.4 (REQ-2 verified live), 4.2, 4.3 and 5.1 marked [x] with
          review verdicts; gate verdict PASS. Three FYI findings recorded on
          Task 5.1 (solution cost NULL where the source tour lacks a length
          comment; dimension-many virtual node rows for HCP/EXPLICIT problems;
          stored names keep the file-declared NAME unless a same-type twin
          exists) — none violates a pinned criterion, so no new tasks were
          registered.
related_files:
  - [TODO.md](./TODO.md)
tags:
  - review/implementation-plan
  - guide/database-rebuild
  - algorithm/tsplib
  - benchmark/etl
  - notes/routing-data
  - analysis/duckdb
  - guide/parser
  - guide/transformer
  - benchmark/database
  - review/schema
  - notes/5w2h
---

# Routing_data Database Rebuild — Registered Implementation Plan

## Scope & rules (unchanged from draft)

+ Touch only `src/submodules/Routing_data` plus the rebuild/copy commands below.
+ Do not commit, do not push, do not edit docs, do not write tests.
+ Main repo stays untouched — see **Deferred** section (kept at the end).
+ Source files are read-only for the reviewer; the implementer applies the
  decisions below.

## Source of truth

+ [TODO.md](./TODO.md) — locked design decisions (schema topology, name twins,
  matrix representation, loader API, type vocabulary, out-of-scope list).
+ This file — the registered plan (decisions pinned here win over any draft text).

---

## Decisions pinned

Each resolves a blocking/decision deficiency from the assess pass. Canonical
answers; the implementer applies them, the reviewer gates against them.

+ **#1 FIXED_EDGES_SECTION** — Extract in `parser.py` `FormatParser` via a new
  `_extract_fixed_edges(text)` raw-text helper (scan `FIXED_EDGES_SECTION` …
  `-1`, parse `from to` lines into 0-based `[from, to]` pairs). Do **not** add a
  field to `models.py.StandardProblem` — its field system has no FIXED_EDGES
  field and its `parse` loop drops unknown sections; raw-text extraction in the
  parser keeps `models.py` untouched and localizes the new logic.
+ **#2 matrix_json→matrix** — In `worker_functions.py` `process_file_for_parallel`,
  emit `edge_weight_data = {'matrix': matrix, 'matrix_format': ..., 'is_symmetric': ...}`
  (nested list, full n×n). Drop `matrix_json` and `dimension`. In `operations.py`
  `insert_problems_batch`, the edge INSERT becomes
  `INSERT INTO edge_weight_matrices (problem_id, matrix_format, is_symmetric, matrix)`.
+ **#3 ADJ_LIST/EDGE_LIST** — Parse in `parser.py` via a new `_extract_edges(text,
  edge_data_format)` raw-text helper: `EDGE_LIST` → one `[from,to]` per line;
  `ADJ_LIST` → `from: to1 to2 …` expanded to `(from,toi)` pairs; normalize to
  0-based. The existing `EdgeDataField` (models.py) expects weighted triples and
  is **not** reused for HCP. All 9 `.hcp` files declare `EDGE_DATA_FORMAT: EDGE_LIST`.
+ **#4 edges/fixed_edges key location** — Pin **top-level** keys `edges` and
  `fixed_edges` as siblings of `problem_data`/`nodes`/`edge_weight_data`/
  `solution_data` (parser result → transformer result → worker result), **not**
  nested in `problem_data`. Justification: `problem_data` maps 1:1 to the
  `problems` row; graph columns are populated by batch-insert from dedicated keys,
  matching the existing `edge_weight_data`/`solution_data` pattern.
+ **#5 transformer type argument** — Add `problem_type: Optional[str] = None` param
  to `_convert_edge_weights_to_matrix`, threaded from `transform_problem` via
  `problem_meta.get('type')`. Inside, if `problem_type in ('CVRP','VRP')` and
  `len(matrix) == dimension - 1`, expand to n×n with zeroed row 0 / col 0.
+ **#6 tour dimension fallback** — Pick **pre-inject DIMENSION into tour text**:
  in `transformer.py` `_parse_tour_file`, read the `.opt.tour` raw text; if it has
  no `DIMENSION` line, prepend `DIMENSION : <problem_dim>\n` and parse from a temp
  file. Thread the linked problem's dimension from the worker via
  `parse_solution_data(tour_file, parser, problem_dimension=...)` →
  `_parse_tour_file(...)`. Keeps `parser.parse_file`/`validate_problem` unchanged.
+ **#7 NotFound exception** — Add a new `NotFoundError(ConverterError)` class in
  `src/converter/utils/exceptions.py` (with optional `name`/`type` context),
  exported in `__all__`. Do **not** reuse `DatabaseError` — "zero rows" is a
  domain not-found condition, distinct from an operation failure.
+ **#8 dead single-insert paths** — Retire (delete) `insert_edge_weights`,
  `_insert_problem_internal`, and `insert_problem_atomic` from `operations.py`.
  They encode the old `matrix_json`/`dimension` schema and are unused by the
  production batch path (`insert_problems_batch`, the only path
  `cli/commands.py:166` calls). `insert_problem`/`insert_nodes`/`api.py` remain
  out of scope (not on the rebuild's critical path) — see Deferred.
+ **#9 CVRP vs VRP vocabulary** — EMPIRICALLY resolved: all 16 files under
  `datasets/problems/vrp/` declare `TYPE : CVRP`. Pin vocabulary **`CVRP`**
  (file-declared), not legacy `VRP`. The validation gate asserts per-type counts
  `TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41` (total 198).
+ **#10 INSERT…RETURNING temp_id (risk)** — Pin the DuckDB "return source columns"
  pattern (DuckDB ≥1.4 per `pyproject.toml` supports returning source columns):

  ```sql
  CREATE TEMP TABLE problem_id_mapping AS
    SELECT p.id, pt.temp_id
    FROM (INSERT INTO problems (name, type, comment, dimension, capacity, ...)
          SELECT name, type, comment, dimension, capacity, ... FROM problems_temp
          RETURNING problems.id, problems_temp.temp_id) p
  ```

  mapping is keyed by `temp_id` (never `name`). Fallback if the installed DuckDB
  rejects source-column RETURNING: materialize `RETURNING id` zipped to `temp_id`
  by row order (DuckDB preserves INSERT…SELECT source order).
+ **#11 validation gate (risk)** — Add the inverse assertion: `edge_weight_matrices`
  has **zero** rows for `type='HCP'` (HCP stores only adjacency), and all 9 HCP
  rows have non-null `adjacency`. Retain the forward assertion matrix-dim ==
  problem-dim on the 80 EXPLICIT rows.

---

## Batches

Execution batches → **implementer**. Validation gates → **reviewer**.

### Batch 1 — parser (extraction) — `implementer`

+ [x] **[REVIEWED]** **Task 1.1: Extract EDGE_LIST/ADJ_LIST edge data in parser.py**
  * **What:** Add `_extract_edges(text, edge_data_format)` to `FormatParser`,
    parsing `EDGE_DATA_SECTION` into 0-based `[from, to]` pairs for both
    `EDGE_LIST` and `ADJ_LIST` formats.
  * **Why:** HCP problems carry their only graph data as `EDGE_DATA_SECTION`
    (EDGE_LIST); today the parser drops it (no field wired to the result).
  * **Who:** Agent.
  * **Where:** [parser.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py)
  * **When:** No dependencies; first in batch.
  * **How:** Read raw `text` in `parse_file` (already loaded); split on
    `EDGE_DATA_SECTION`; for `EDGE_LIST` yield one pair per line; for `ADJ_LIST`
    expand `from: to1 to2 …`; subtract 1 for 0-based; return list of `[from,to]`.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `alb1000.hcp` returns ~2000 edge pairs (0-based); `alb4000.hcp`
    returns its full edge list without error.
  * **Solution:**
    - **Changed Files:**
      + [parser.py L647](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L647) — new `_extract_edges` (EDGE_LIST + ADJ_LIST, 0-based).
      + [parser.py L602](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L602) — new `_section_content` helper (stops at EOF / next `*_SECTION` / uppercase keyword header).
    - **Summary:** Added `_extract_edges(text, edge_data_format)` to `FormatParser`, parsing `EDGE_DATA_SECTION` for both `EDGE_LIST` (one `[from,to]` per line) and `ADJ_LIST` (`from: to1 to2 …` expanded), normalized to 0-based. A shared `_section_content` helper collects section lines and robustly stops at the next `*_SECTION`, EOF, or an uppercase keyword header (e.g. `FIXED_EDGES :` in `alb4000.hcp`).
    - **Technical Justification:** `models.py.EdgeDataField` expects weighted triples and is unusable for HCP; raw-text scanning in the parser keeps `models.py` untouched (Decisions #1/#3) and localizes the new logic.
    - **DoD Compliance:** `alb1000.hcp` → 1998 edge pairs (≈2000), all 0-based; `alb4000.hcp` → full 7997-edge list without error.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. Live-verified: `alb1000` → 1998 edges, `alb4000` → 7997 (no `FIXED_EDGES :` bleed, thanks to the keyword-header stop in `_section_content`), `alb3000d` → 5993, `berlin52` → `[]` (the no-`EDGE_DATA_FORMAT` fallback to `EDGE_LIST` is sound — `Problem.__getattribute__` returns the field default). DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_1-1_1-2_1-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_1-1_1-2_1-3.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 1.2: Extract FIXED_EDGES_SECTION in parser.py**
  * **What:** Add `_extract_fixed_edges(text)` to `FormatParser`, parsing
    `FIXED_EDGES_SECTION` … `-1` into 0-based `[from, to]` pairs.
  * **Why:** `linhp318.tsp` declares `FIXED_EDGES_SECTION` (`1 214`, `-1`), which
    must land in `problems.fixed_edges` as `[[0, 213]]`.
  * **Who:** Agent.
  * **Where:** [parser.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py)
  * **When:** Independent of Task 1.1.
  * **How:** Scan raw text between `FIXED_EDGES_SECTION` and the `-1` terminator;
    each line is `from to`; convert to 0-based pairs.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `linhp318.tsp` returns `fixed_edges == [[0, 213]]`; a file with no
    section returns `[]`.
  * **Solution:**
    - **Changed Files:**
      + [parser.py L706](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L706) — new `_extract_fixed_edges` (parses `FIXED_EDGES_SECTION` … `-1`, 0-based, returns `[]` when absent).
    - **Summary:** Added `_extract_fixed_edges(text)` to `FormatParser`, scanning raw text between `FIXED_EDGES_SECTION` and the `-1` terminator and converting each `from to` line to a 0-based `[from, to]` pair.
    - **Technical Justification:** `StandardProblem` has no `FIXED_EDGES` field and its parse loop drops unknown sections, so raw-text extraction in the parser (Decision #1) is the minimal change that keeps `models.py` untouched.
    - **DoD Compliance:** `linhp318.tsp` → `fixed_edges == [[0, 213]]`; `berlin52.tsp` (no section) → `[]`.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. Live-verified: `linhp318.tsp` → `fixed_edges == [[0, 213]]` (section sits before `NODE_COORD_SECTION`, so the next-`*_SECTION` stop is exercised); `berlin52` → `[]`. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_1-1_1-2_1-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_1-1_1-2_1-3.md) — Walkthrough

+ [ ] **[MUST REDO: REQ-2]** **Task 1.3: Expose edges/fixed_edges at top level of parse result**
  * **What:** Add `edges` and `fixed_edges` as top-level keys in the dict returned
    by `parse_file` (siblings of `problem_data`/`nodes`/`tours`/`metadata`).
  * **Why:** Decision #4 pins top-level keys so the transformer/worker/insert
    chain reads them uniformly.
  * **Who:** Agent.
  * **Where:** [parser.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py)
  * **When:** Depends on Tasks 1.1–1.2.
  * **How:** In `parse_file`, after building `result`, set `result['edges']` and
    `result['fixed_edges']` from the helpers.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `parse_file` output includes `edges` and `fixed_edges` keys for a
    sample HCP and TSP file.
  * **Solution:**
    - **Changed Files:**
      + [parser.py L156-166](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L156) — `parse_file` now initializes `result['edges']`/`result['fixed_edges']` to `[]` and sets them from the helpers; `edge_data_format` derived from `problem.edge_data_format` (default `EDGE_LIST`).
    - **Summary:** `parse_file` now exposes `edges` and `fixed_edges` as top-level keys, derived from the raw `text` via `_extract_edges`/`_extract_fixed_edges`, with `edge_data_format` read from the parsed `EDGE_DATA_FORMAT` header (default `EDGE_LIST`).
    - **Technical Justification:** Decision #4 pins top-level keys (siblings of `problem_data`/`nodes`/`tours`/`metadata`), matching the existing `edge_weight_data`/`solution_data` pattern so the transformer/worker/insert chain reads them uniformly. `models.py.StandardProblem` was not modified.
    - **DoD Compliance:** `parse_file` output includes `edges` and `fixed_edges` for HCP (`alb1000`, `alb4000`) and TSP (`linhp318`, `berlin52`) files.
    - **Review Verdict (2026-08-27, reviewer):** ⚠️ DoD passes (keys present and populated; live-verified on `alb1000`/`alb4000`/`linhp318`/`berlin52`), **but this task's diff introduced REQ-2**: the new absolute import `from submodules.Routing_data.src.tsplib_parser.models import StringField` (parser.py L7) breaks the documented rebuild command — `PYTHONPATH=src/submodules/Routing_data/src python src/submodules/Routing_data/converter_cli.py --help` dies with `ModuleNotFoundError: No module named 'submodules'` (reproduced 2026-08-27) — and couples `tsplib_parser` to the embedding repo layout. Rework required: see Task 1.4.
    - **Artifacts:**
      + 📝 [walkthrough_1-1_1-2_1-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_1-1_1-2_1-3.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 1.4: Fix repo-relative absolute import in parser.py (REQ-2)**
  * **What:** Replace `from submodules.Routing_data.src.tsplib_parser.models import StringField` (parser.py L7) with a package-relative import (e.g. `from .models import StringField`), or drop it entirely along with the bogus local annotation `edge_type: StringField = problem.edge_weight_type` (parser.py L830 — the value is a `str`, not a `StringField`).
  * **Why:** The absolute import resolves only when the main repo's `src/` directory is on `sys.path` (interactive/heredoc runs from the repo root). The documented rebuild command (Task 4.3: `PYTHONPATH=src/submodules/Routing_data/src uv run python src/submodules/Routing_data/converter_cli.py process ...`) fails at import with `ModuleNotFoundError: No module named 'submodules'` (reproduced 2026-08-27). It also couples `tsplib_parser` to the embedding repository layout (submodule no longer standalone) and, when it does resolve, imports `tsplib_parser.models` under two module identities (duplicate class objects).
  * **Who:** Agent (implementer).
  * **Where:** [parser.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L7)
  * **When:** Before Batch 4 (Task 4.3 depends on the CLI importing).
  * **How:** Use the relative import (models.py is in the same package and is already imported relatively at parser.py L9); fix or remove the `StringField` annotation at L830; re-run the Batch-1 verification set with the exact Task 4.3 invocation form.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** From the repo root, `PYTHONPATH=src/submodules/Routing_data/src python src/submodules/Routing_data/converter_cli.py --help` exits 0; the Batch-1 verification set (`alb1000`/`alb4000`/`linhp318`/`berlin52`) produces identical results.
  * **Solution:**
    - **Changed Files:** [parser.py L7](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L7) — absolute import replaced by relative `from .models import StringField`.
    - **Review Verdict (2026-08-27, reviewer, verified at Batch 5 gate):** ✅ Realized as planned. Live-verified: parser.py L7 is the relative import; the literal DoD command from the repo root (`PYTHONPATH=src/submodules/Routing_data/src .venv/bin/python src/submodules/Routing_data/converter_cli.py --help`) exits 0; the old absolute path `submodules.Routing_data.src.tsplib_parser...` no longer resolves (REQ-2 coupling gone). NITs (non-blocking): the bogus `edge_type: StringField` annotation at L830 was kept (harmless — local variable annotations are never evaluated); `.models` is now imported twice (L7 + L9) — merge on the next touch. DoD: pass.

### Batch 2 — transformer (matrix expansion + pass-through) — `implementer`

+ [x] **[REVIEWED]** **Task 2.1: Thread problem type + expand CVRP (n-1)→n matrix**
  * **What:** Add `problem_type` param to `_convert_edge_weights_to_matrix`; when
    CVRP/VRP and matrix is (n-1)×(n-1), expand to n×n with zeroed depot row/col.
  * **Why:** `eil7`/`eil13`/`eil31` CVRP files carry customer-only matrices;
    decision #5 fixes the dimension mismatch.
  * **Who:** Agent.
  * **Where:** [transformer.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py)
  * **When:** Depends on Batch 1 (edges keys exist) but logic is independent.
  * **How:** Thread `problem_meta.get('type')` from `transform_problem`; after
    reconstructing the 2D list, if `problem_type in ('CVRP','VRP')` and
    `len(matrix) == dimension - 1`, prepend zero row + zero col.
  * **How much:** Medium.
  * **Stakeholder Implications:** None.
  * **DoD:** `eil13` transforms to a 13×13 matrix with zero first row and column.
  * **Solution:**
    - **Changed Files:**
      + [transformer.py L74](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L74) — thread `problem_type=problem_meta.get('type')` into the matrix call.
      + [transformer.py L158](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L158) — `_convert_edge_weights_to_matrix` gains `problem_type`; both return paths route through `_expand_vrp_matrix`.
      + [transformer.py L230](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L230) — new `_expand_vrp_matrix` (zeroes depot row/col 0 when CVRP/VRP and `len == dimension-1`).
    - **Summary:** Added `problem_type: Optional[str] = None` to `_convert_edge_weights_to_matrix`, threaded from `transform_problem` via `problem_meta.get('type')`; a new `_expand_vrp_matrix` helper zeroes the depot row/col when a CVRP/VRP customer-only `(n-1)×(n-1)` matrix is detected, applied on both matrix paths.
    - **Technical Justification:** The transformer is the only component that sees both the parsed matrix and the normalized type + authoritative dimension, so expanding here guarantees the worker always receives a full n×n matrix (Decision #5). Routing both branches through one helper keeps the invariant single-sourced; the depot row/col is zeroed (no data exists for it).
    - **DoD Compliance:** `eil13` transforms to a 13×13 matrix with a zero first row and zero first column (verified).
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. `problem_type` threaded (transformer.py L71), both matrix paths route through `_expand_vrp_matrix` (L198). Live: `eil13` → `CVRP`, 13×13, zeroed depot row/col, `m[1][1]=9` preserved. All 16 `.vrp` files declare `TYPE : CVRP`; the only EXPLICIT ones are `eil7/eil13/eil31` — exactly the Decision #5 targets. FYI: variant types like `MC-VRP` (produced by `_extract_problem_data` when capacity_vol/TW/PD extras exist) would skip expansion; no such file exists in the dataset. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_2-1_2-2_2-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-1_2-2_2-3.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 2.2: Pass edges/fixed_edges through transform_problem**
  * **What:** Carry `edges` and `fixed_edges` from the parsed result into the
    transformed result unchanged.
  * **Why:** Decision #4 — transformer is the bridge from parser to worker.
  * **Who:** Agent.
  * **Where:** [transformer.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py)
  * **When:** Depends on Task 1.3.
  * **How:** In `transform_problem`, read `problem_data.get('edges')` /
    `problem_data.get('fixed_edges')` (or top-level) and re-emit as top-level keys
    on the result.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Transforming an HCP result preserves `edges`; a `linhp318` result
    preserves `fixed_edges`.
  * **Solution:**
    - **Changed Files:**
      + [transformer.py L90-106](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L90) — `transform_problem` reads top-level `edges`/`fixed_edges` and re-emits them on the result dict.
    - **Summary:** `transform_problem` now reads `edges`/`fixed_edges` from the top-level parse result (its `problem_data` argument) and re-emits them as top-level keys on the transformed result.
    - **Technical Justification:** Decision #4 pins `edges`/`fixed_edges` as siblings of `problem_data`/`nodes`/`tours`/`metadata`, so the transformer passes them through unchanged rather than nesting them (which would break the worker's uniform read).
    - **DoD Compliance:** HCP `alb1000` result preserves `edges` (1998 pairs); `linhp318` result preserves `fixed_edges == [[0, 213]]` (verified).
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned (transformer.py L91-92 read → L103-104 re-emit). Live: `alb1000` preserves 1998 edges; `linhp318` preserves `[[0, 213]]`. Keys are emitted even when `None` (parser always sets them; a hand-built dict caller would see `None`) — acceptable. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_2-1_2-2_2-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-1_2-2_2-3.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 2.3: Tour dimension fallback (pre-inject DIMENSION)**
  * **What:** In `_parse_tour_file`, pre-inject `DIMENSION : <problem_dim>` when a
    `.opt.tour` lacks DIMENSION; thread the linked problem's dimension from the
    worker via `parse_solution_data(..., problem_dimension=...)`.
  * **Why:** `rd100.opt.tour` has no DIMENSION and fails validation; decision #6.
  * **Who:** Agent.
  * **Where:** [transformer.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py)
  * **When:** Depends on Batch 1 (parser unchanged for this).
  * **How:** Read raw tour text; if no `DIMENSION` line, prepend one and parse via
    a temp file; forward `problem_dimension` from worker through
    `parse_solution_data`.
  * **How much:** Medium.
  * **Stakeholder Implications:** None.
  * **DoD:** `rd100.opt.tour` no longer raises a dimension validation error and its
    solution row appears in the build.
  * **Solution:**
    - **Changed Files:**
      + [transformer.py L301-360](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L301) — `parse_solution_data` gains optional `problem_dimension`, forwarded to `_parse_tour_file`.
      + [transformer.py L322-360](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L322) — `_parse_tour_file` pre-injects `DIMENSION : <problem_dim>` into a temp file when the tour text lacks one; temp file cleaned in a `finally`.
      + [transformer.py L443-445](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/core/transformer.py#L443) — **REQ-1 (resolved):** removed the second `node - 1` (`tour_nodes = [node - 1 for node in tour_nodes]`) so `_parse_tour_file` no longer double-subtracts; replaced the misleading "Convert from 1-based to 0-based" comment.
    - **Summary:** `_parse_tour_file` reads the raw tour text, and when it has no `DIMENSION` line and a `problem_dimension` is supplied, prepends `DIMENSION : <problem_dim>\n` and parses via a temp file. The dimension is threaded from `parse_solution_data(..., problem_dimension=...)`. The double node-index subtraction (REQ-1) was removed — the parser already returns 0-based nodes, so the route now matches DB node ids unchanged.
    - **Technical Justification:** Pre-injection (Decision #6) fixes `rd100` without weakening `parser.parse_file`/`validate_problem` for every other file; the transformer owns the fallback so the parser stays byte-identical. The temp file is created/removed inside the tour path, and `problem_dimension` defaults to `None` so current callers are unaffected until Batch 3 passes it. REQ-1: `_extract_tours` (parser.py L594) already applies `node - 1`, so re-subtracting in the transformer shifted every node an extra -1; the guard `routes = [tour_nodes] if tour_nodes else []` already covers the empty-tour case, so removing the redundant re-conversion is safe.
    - **DoD Compliance:** `rd100.opt.tour` parses with `problem_dimension=100` into a 100-node route with no dimension validation error (verified). REQ-1: `routes[0]` contains no negative indices and no value ≥ 100; min=0, max=99, no `-1` terminator (verified) — equals the parser's 0-based tour unchanged.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned, and **REQ-1 is confirmed fixed**: the second `node - 1` is gone; `_parse_tour_file` takes the parser's 0-based `tours[0]['nodes']` unchanged (transformer.py L442 comment documents why). Live: `berlin52.opt.tour` → 52 nodes, min 0, max 51, no negatives; `rd100.opt.tour` with `problem_dimension=100` → 100 nodes, min 0, max 99. Temp file cleaned in `finally`. NIT: `read_text(..., errors='latin-1')` relies on the codec-as-error-handler trick — works, but a conventional handler is clearer. DoD: pass.
    - **Review Note (REQ-1 — resolved):** The double node-index subtraction in `_parse_tour_file` was fixed by dropping the second `- 1` (see Changed Files L443-445). Every `.opt.tour` route now uses the parser's 0-based nodes unchanged, so `solutions.routes` matches 0-based DB node ids. Verify against a fresh DB before sign-off.
    - **Artifacts:**
      + 📝 [walkthrough_2-1_2-2_2-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-1_2-2_2-3.md) — Walkthrough

### Batch 3 — worker + database (schema, insert, query) — `implementer`

+ [x] **[REVIEWED]** **Task 3.1: Worker payload — matrix list + edges/fixed_edges**
  * **What:** Emit `edge_weight_data` with nested-list `matrix` (drop
    `matrix_json`/`dimension`) and add `edges`/`fixed_edges` to the worker result.
  * **Why:** Decisions #2 and #4.
  * **Who:** Agent.
  * **Where:** [worker_functions.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py)
  * **When:** Depends on Batch 2.
  * **How:** Build `matrix = transformed_data['edge_weight_matrix']`;
    `edge_weight_data = {'matrix': matrix, 'matrix_format': ..., 'is_symmetric': ...}`;
    pass through `edges`/`fixed_edges` and `problem_dimension` to the solution parse.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** Processing one EXPLICIT file returns `matrix` (no `matrix_json`/
    `dimension`); processing an HCP file returns `edges`.
  * **Solution:**
    - **Changed Files:**
      + [worker_functions.py L4](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L4) — dropped now-unused `import json`.
      + [worker_functions.py L73-76](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L73) — thread `problem_dimension` into `parse_solution_data`.
      + [worker_functions.py L80-88](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L80) — `edge_weight_data = {matrix, matrix_format, is_symmetric}` (dropped `matrix_json`/`dimension`).
      + [worker_functions.py L98-100](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/worker_functions.py#L98) — result gains top-level `edges`/`fixed_edges`.
    - **Summary:** `process_file_for_parallel` now emits `edge_weight_data` with the full n×n nested-list `matrix` (no `matrix_json`/`dimension`), threads the linked problem's dimension into `parse_solution_data`, and returns top-level `edges`/`fixed_edges` (Decision #2/#4).
    - **Technical Justification:** The nested list is the storage-native form for `matrix INTEGER[][]`; dropping the redundant `dimension` (matrix size is the dimension) and `matrix_json` (no longer serialized) aligns the worker payload with the batch insert.
    - **DoD Compliance:** Real EXPLICIT file `bayg29` → `edge_weight_data` keys `[is_symmetric, matrix, matrix_format]`, no `matrix_json`/`dimension`, 29×29; real HCP `alb3000d` → `edges` count 5993.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. `import json` dropped; `edge_weight_data = {matrix, matrix_format, is_symmetric}` (worker_functions.py L84-88); `problem_dimension` threaded (L73-75); top-level `edges`/`fixed_edges` (L99-100). Live: `bayg29` → keys `[is_symmetric, matrix, matrix_format]`, 29×29. NIT: docstring return-contract lines L38-39 got merged (missing line breaks after `EXPLICIT),` and `pairs),`) — cosmetic fix while in there. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 3.2: Add NotFoundError to exceptions.py**
  * **What:** Add `NotFoundError(ConverterError)` with optional `name`/`type`
    context; export in `__all__`.
  * **Why:** Decision #7 — `load(name, type)` must raise a distinct not-found.
  * **Who:** Agent.
  * **Where:** [exceptions.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py)
  * **When:** Independent; can run parallel to 3.1.
  * **How:** Subclass `ConverterError`; mirror `ExtractionError`'s optional-context
    pattern.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `NotFoundError` importable and raised by `load`.
  * **Solution:**
    - **Changed Files:**
      + [exceptions.py L252](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py#L252) — new `NotFoundError(ConverterError)` with optional `name`/`type`.
      + [exceptions.py L315](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/utils/exceptions.py#L315) — exported in `__all__`.
    - **Summary:** Added `NotFoundError(ConverterError)` mirroring `ExtractionError`'s optional-context pattern, with `name`/`type` context and export in `__all__`.
    - **Technical Justification:** Decision #7 — "zero rows" is a domain not-found condition, distinct from `DatabaseError` (an operation failure); a dedicated subclass lets callers distinguish a bad lookup from a broken query.
    - **DoD Compliance:** `NotFoundError` importable; `load('nope','TSP')` raises `NotFoundError: [nope/TSP] Problem 'nope' of type 'TSP' not found`.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. `NotFoundError(ConverterError)` with optional `name`/`type`, exported in `__all__` (exceptions.py L252/L315). Message format matches the documented example. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 3.3: Database DDL changes**
  * **What:** In `_initialize_schema`: `problems` gains `tsplib_name VARCHAR`,
    `fixed_edges INTEGER[][]`, `adjacency INTEGER[][]`, `UNIQUE(name, type)`;
    `edge_weight_matrices` replaces `matrix_json`+`dimension` with
    `matrix INTEGER[][]`, keeping `matrix_format`/`is_symmetric`.
  * **Why:** Locked schema topology in TODO + decisions #1/#3/#2.
  * **Who:** Agent.
  * **Where:** [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py)
  * **When:** Depends on 3.1/3.2 (worker/exceptions ready).
  * **How:** Edit `CREATE TABLE problems` and `CREATE TABLE edge_weight_matrices`;
    add a unique index/constraint on `(name, type)`.
  * **How much:** Medium.
  * **Stakeholder Implications:** Schema is destructive to any prior build (we
    rebuild from scratch with `--force`).
  * **DoD:** Fresh DB `PRAGMA table_info('problems')` shows the three new columns
    and `UNIQUE(name, type)`; `edge_weight_matrices` has `matrix INTEGER[][]` and
    no `matrix_json`/`dimension`.
  * **Solution:**
    - **Changed Files:**
      + [operations.py L41-67](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L41) — `problems` gains `tsplib_name`, `fixed_edges`, `adjacency`, `UNIQUE (name, type)`.
      + [operations.py L99](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L99) — `edge_weight_matrices` swaps `matrix_json`+`dimension` for `matrix INTEGER[][]`.
    - **Summary:** `_initialize_schema` now creates `problems` with `tsplib_name`/`fixed_edges`/`adjacency` + `UNIQUE(name, type)`, and `edge_weight_matrices` with a single `matrix INTEGER[][]` column (dropping `matrix_json`/`dimension`), keeping `matrix_format`/`is_symmetric`.
    - **Technical Justification:** Matches the locked TODO topology and Decisions #1/#2/#3: HCP adjacency/fixed arcs land on `problems`, EXPLICIT matrices are stored as native nested arrays, and `UNIQUE(name,type)` makes the loader ambiguity-free.
    - **DoD Compliance:** `PRAGMA table_info('problems')` shows the three new columns and `UNIQUE(name, type)`; `edge_weight_matrices` has `matrix` and no `matrix_json`/`dimension`.
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. `problems` DDL has `tsplib_name`/`fixed_edges`/`adjacency` + `UNIQUE (name, type)` (operations.py L41-67); `edge_weight_matrices` has `matrix INTEGER[][]`, no `matrix_json`/`dimension` (L96-101). FYI: `_migrate_schema` only adds the 9 VRP-variant columns, and CLI `--force` (commands.py L114-124) does NOT drop tables — a stale old-schema DB would silently lack the new columns. The current target is the empty husk, so Batch 4 is unaffected; reconcile before any future rebuild onto an old DB. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md) — Walkthrough

+ [x] **[REVIEWED]** **Task 3.4: Batch insert — temp_id mapping + name disambiguation + graph columns**
  * **What:** In `insert_problems_batch`: replace name-keyed join with temp_id-keyed
    `INSERT … RETURNING id, temp_id` (decision #10); disambiguate duplicate
    `(name, type)` in the collect step (name = file stem, `tsplib_name` = original);
    populate `adjacency`/`fixed_edges`/`matrix`.
  * **Why:** Removes att48/eil51/gil262/lin318 node cross-contamination.
  * **Who:** Agent.
  * **Where:** [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py)
  * **When:** Depends on 3.3.
  * **How:** In collect loop, detect duplicate `(name,type)`; rewrite name to file
    stem and set `tsplib_name`; build `problem_id_mapping` via temp_id; INSERT
    edges/matrix from `result['edges']`/`edge_weight_data['matrix']`.
  * **How much:** High.
  * **Stakeholder Implications:** None.
  * **DoD:** Zero duplicate `(name, type)`; `att48` TSP and `att48` CVRP each have
    48 node rows; `linhp318.fixed_edges == [[0,213]]`.
  * **Solution:**
    - **Changed Files:**
      + [operations.py L299](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L299) — `insert_problems_batch` rewritten: temp_id-keyed mapping from `INSERT…RETURNING id`, post-collect `(name,type)` disambiguation, `adjacency`/`fixed_edges`/`matrix` populated.
    - **Summary:** Replaced the name-keyed `problem_id_mapping` join with a temp_id-keyed mapping derived from `INSERT … RETURNING id` (Decision #10 fallback, since DuckDB 1.5.5 rejects source-column RETURNING), added a post-collect pass that rewrites duplicate `(name,type)` names to the file stem with `tsplib_name` set to the original NAME, and populates `adjacency`/`fixed_edges`/`matrix` from the worker result.
    - **Technical Justification:** Keying the mapping by `temp_id` (never `name`) eliminates the att48/eil51/gil262/lin318 node cross-contamination caused by name-keyed joins; `UNIQUE(name,type)` + the file-stem rewrite keep stored names collision-free while preserving the original NAME in `tsplib_name`.
    - **DoD Compliance:** Zero duplicate `(name, type)`; `att48` TSP and `att48` CVRP each have 48 node rows; `linhp318.fixed_edges == [[0, 213]]` (verified in integration test).
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned, using the Decision #10 **fallback** as pinned: `RETURNING id` zipped to `temp_id` by source row order (operations.py L508-512). Reviewer sandbox on DuckDB 1.5.5 reproduced both premises: registered-DataFrame `INSERT…SELECT…RETURNING id` emits ids in source row order (`[1,2,3]`), and source-column RETURNING is rejected (`BinderException: Referenced table not found`) — matching knowledge_duckdb-returning-source-columns.md. Disambiguation pass (L450-462) matches the TODO name-twins rule (`linhp318` → stored `name=linhp318`, `tsplib_name='lin318'`; cross-type twins keep `name`). NIT: `dict(zip(...))` silently truncates if `len(returned_ids) != len(all_problems)` — add an explicit length check so a mapping-order failure fails loudly instead of silently dropping node/solution rows. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md) — Walkthrough
      + 📚 [knowledge_duckdb-returning-source-columns.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_duckdb-returning-source-columns.md) — Knowledge

+ [x] **[REVIEWED]** **Task 3.5: Query API `load(name, type)` + retire dead paths**
  * **What:** Add `load(name, type)` (both required; raise `NotFoundError` on 0
    rows) and a full-matrix accessor returning nested list; delete
    `insert_edge_weights`, `_insert_problem_internal`, `insert_problem_atomic`.
  * **Why:** Decisions #7/#8; loader API must be ambiguity-free.
  * **Who:** Agent.
  * **Where:** [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py)
  * **When:** Depends on 3.4.
  * **How:** `SELECT * FROM problems WHERE name=? AND type=?`; raise on empty;
    matrix accessor selects `matrix` and casts to nested list.
  * **How much:** Medium.
  * **Stakeholder Implications:** None (tests out of scope).
  * **DoD:** `load('eil51','TSP')` and `load('eil51','CVRP')` differ;
    `load('nope','TSP')` raises `NotFoundError`; the three dead methods are gone.
  * **Solution:**
    - **Changed Files:**
      + [operations.py L9](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L9) — import `NotFoundError`.
      + [operations.py L591](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L591) — new `load(name, type)` (both required; raises `NotFoundError` on 0 rows).
      + [operations.py L625](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L625) — new `load_matrix(name, type)` returning a nested list.
      + [operations.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py) — deleted `insert_edge_weights`, `_insert_problem_internal`, `insert_problem_atomic`.
    - **Summary:** Added `load(name, type)` (both required; raises `NotFoundError` on zero rows) and `load_matrix(name, type)` returning the full matrix as a nested list; deleted the three dead single-insert methods that encoded the old `matrix_json`/`dimension` schema.
    - **Technical Justification:** `UNIQUE(name,type)` makes `load` ambiguity-free (Decision #7); `NotFoundError` is a distinct domain not-found, not a `DatabaseError` (Decision #7); the three methods are unused by the production batch path (Decision #8).
    - **DoD Compliance:** `load('eil51','TSP')` and `load('eil51','CVRP')` return different ids; `load('nope','TSP')` raises `NotFoundError`; the three dead methods are gone (grep-confirmed).
    - **Review Verdict (2026-08-27, reviewer):** ✅ Realized as planned. `load(name, type)` raises `NotFoundError` on 0 rows (operations.py L591-616; `.description` cursor API verified working on 1.5.5); `load_matrix` returns a nested list (L625-642). The three dead methods are gone from `src/` (grep-confirmed). FYI: `tests/` (`test_database_connection_leak.py`, `test_full_pipeline.py`, `test_schema_migration_fixes.py`) and `docs/`/`README.md` still reference the deleted methods and `matrix_json` — the submodule test suite currently fails if run; tests/docs updates are deferred per plan, but record this cleanup debt. DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md) — Walkthrough

### Batch 4 — setup + rebuild — `implementer`

+ [x] **[REVIEWED]** **Task 4.1: Declare pandas in pyproject.toml**
  * **What:** Add `"pandas>=2.0.0"` to `dependencies`.
  * **Why:** `insert_problems_batch` imports pandas; a standalone submodule venv
    crashes without it (confirmed in first test run).
  * **Who:** Agent.
  * **Where:** [pyproject.toml](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/pyproject.toml)
  * **When:** Independent; before rebuild.
  * **How:** Edit the `dependencies` list.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `uv run --project src/submodules/Routing_data python -c "import pandas"` succeeds.
  * **Solution:**
    - **Changed Files:** none — `pandas>=2.3.3` already declared at [pyproject.toml L29](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/pyproject.toml#L29) (no-op).
    - **Review Verdict (2026-08-27, reviewer, verified at Batch 5 gate):** ✅ Realized as planned. DoD command succeeds (`pandas 3.0.5` importable via `uv run --project`). Note: the `--project` form transiently re-created `src/submodules/Routing_data/.venv`; removed again immediately to preserve Task 4.2's state. DoD: pass.

+ [x] **[REVIEWED]** **Task 4.2: Clean stray .venv**
  * **What:** Remove the untracked `src/submodules/Routing_data/.venv`.
  * **Why:** Testing left junk in the submodule repo.
  * **Who:** Agent.
  * **Where:** `src/submodules/Routing_data/.venv`
  * **When:** Independent.
  * **How:** `rm -rf` the directory.
  * **How much:** Low.
  * **Stakeholder Implications:** None.
  * **DoD:** `ls src/submodules/Routing_data` shows no `.venv`.
  * **Solution:**
    - **Changed Files:** none (deletion of untracked artifact).
      + `src/submodules/Routing_data/.venv` — removed (`rm -rf`, was 171 MB, untracked; confirmed `git ls-files` returned nothing before removal).
    - **Summary:** Deleted the stray untracked `.venv` (171 MB) the submodule acquired during testing. The repo-root `.venv` and global uv venv were left untouched.
    - **Technical Justification:** The stray venv was unused by the pinned rebuild command (which runs `uv run python` from the repo root using the root project env + `PYTHONPATH` to the local submodule src); removing it cleans the submodule without affecting the build.
    - **DoD Compliance:** `ls src/submodules/Routing_data` shows no `.venv` (verified).
    - **Review Verdict (2026-08-27, reviewer, verified at Batch 5 gate):** ✅ Realized as planned. Live-verified: `ls src/submodules/Routing_data/.venv` → No such file or directory; repo-root/global venvs untouched (the pinned rebuild path uses `uv run` + PYTHONPATH). DoD: pass.
    - **Artifacts:**
      + 📝 [walkthrough_4-1_4-2_4-3.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_4-1_4-2_4-3.md) — Walkthrough

+ [ ] **[REDO]** **Task 4.3: Rebuild database + copy + delete stale husks**
  * **What:** Run the process command from repo root with local submodule src; copy
    the result to `db/routing.duckdb`; delete stale empty copies.
  * **Why:** Produce the canonical DB; avoid the git-main `routing-data` shadowing.
  * **Who:** Agent.
  * **Where:** `db/routing.duckdb`, `datasets_processed/db/routing.duckdb`.
  * **When:** Depends on Batches 1–3 + 4.1.
  * **How:**

    ```bash
    PYTHONPATH=src/submodules/Routing_data/src uv run python \
      src/submodules/Routing_data/converter_cli.py process \
      -i datasets/problems -o /tmp/routing_rebuild --force --parallel --workers 4
    cp /tmp/routing_rebuild/db/routing.duckdb db/routing.duckdb
    rm -f datasets_processed/db/routing.duckdb
    ```

  * **How much:** High.
  * **Stakeholder Implications:** None.
  * **DoD:** `db/routing.duckdb` exists and is > 12 KB; no stale husk remains.

### Batch 5 — validation gate — `reviewer`

+ [x] **[REVIEWED]** **Task 5.1: Validation gate (SQL assertions + spot-checks)**
  * **What:** Run the full assertion suite against `db/routing.duckdb`.
  * **Why:** Confirm the rebuild matches the pinned decisions before sign-off.
  * **Who:** Agent (reviewer role).
  * **Where:** [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb)
  * **When:** Depends on Task 4.3.
  * **How:**
    - 198 problems total.
    - Per-type counts: `TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41`.
    - Matrix dim == problem dim on all 80 EXPLICIT rows.
    - `edge_weight_matrices` has **zero** rows for `type='HCP'`.
    - All 9 HCP rows have non-null `adjacency`.
    - Zero duplicate `(name, type)`.
    - `linhp318.fixed_edges == [[0, 213]]`.
    - All solutions linked (no orphan solution rows).
    - Spot-check loads: `berlin52` (EUC_2D), `br17` (ATSP EXPLICIT), `eil13` (CVRP EXPLICIT 13×13 expanded), `att48` as TSP and as CVRP, `alb1000` (HCP adjacency only).
  * **How much:** Medium.
  * **Stakeholder Implications:** None.
  * **DoD:** Every assertion passes; report a per-type count table + spot-check
    results.
  * **Solution:**
    - **Changed Files:** none — read-only queries against [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb) via `duckdb.connect(..., read_only=True)` (DuckDB 1.5.5).
    - **Summary:** Ran the full pinned assertion suite (20 checks) + five spot-check loads. Every pinned criterion maps to one SQL assertion or spot-load; the DB was opened strictly read-only and was verified immutable (mtime/size unchanged after the gate).
    - **DoD Compliance:** 20/20 PASS. Evidence table in the walkthrough.
    - **Review Verdict (2026-08-27, reviewer):** ✅ **Gate PASS.** Claims verified: 198 problems (TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41); matrices=80 == `edge_weight_type='EXPLICIT'` (1:1 with matrix rows; ATSP=19, CVRP=3, SOP=41, TSP=17); matrix dim == problem dim on all 80; zero HCP matrix rows; 9/9 HCP adjacency non-null (1998–9999 0-based pairs); zero duplicate (name,type) + `UNIQUE(name, type)` constraint present; `linhp318.fixed_edges == [[0,213]]` with `tsplib_name='lin318'`; nodes=334813 + solutions=43 fully linked, node ids 0-based contiguous per problem, every single-route solution length == dimension; file_tracking=198, no orphans. Spot-checks: berlin52 (EUC_2D, no matrix, 0-based tour is a permutation of 0..51); br17 (ATSP 17×17 asymmetric — dataset has no br17 tour sidecar, so no solution row, expected); eil13 (CVRP 13×13, zero depot row/col, m[1][1]=9); att48 TSP+CVRP (distinct ids, 48 nodes each); alb1000 (HCP, 1998 adjacency pairs, zero matrix rows). **FYI (no pinned criterion violated, no new task):** (a) 19/43 solutions have NULL cost — cost is best-effort from the tour file COMMENT, and berlin52.opt.tour carries no length comment (source-verified); (b) HCP/EXPLICIT problems each get dimension-many virtual node rows with NULL coords (parser `_extract_nodes` else-branch, pre-existing design; 27000 HCP rows) — TODO's "adjacency is their only graph data" concerns graph data, not the node-id scaffold; (c) stored names like `ulysses16.tsp` keep the file-declared NAME (no same-type collision → no stem rewrite), per the TODO name-twin rule.
    - **Artifacts:**
      + 📝 [walkthrough_5-1.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_5-1.md) — Walkthrough

---

## Deferred — main repo issues (do not touch yet)

+ [ ] Circular import `src/distances/matrix.py` <-> `src/protocols/problem_context.py` (first `DatabaseLoader.load()` raises `ImportError` on a fresh process; candidate fix: move `BackendModule` import under `TYPE_CHECKING`).
+ [ ] Main-repo consumers hardcode `datasets/routing.duckdb` (`src/benchmarking_v2/orchestration.py:315`, `src/benchmarks_v2/run_chapter4_benchmark.py:154`, `DatabaseLoader` default). Canonical DB now lives at `db/routing.duckdb`.
+ [ ] `Problem` model / `DatabaseLoader` only support TSP/ATSP/CVRP; SOP/HCP/TOUR rows are stored but not loadable by the model.
+ [ ] `datasets/inspect_database.py` is stale (default path + legacy tables).
+ [ ] Root `pyproject.toml` `[tool.uv.workspace]` members entry `data/Routing_data/vrp_database` points to a nonexistent directory.
+ [ ] `api.py` + `insert_problem`/`insert_nodes` still use the pre-rebuild schema (no `tsplib_name`/`fixed_edges`/`adjacency`/`matrix`); not on the rebuild's critical path — reconcile or retire later.
+ [ ] Main venv `routing-data` installed from git `main` drifts from the local clone; rebuilds use local src via PYTHONPATH. Decide later whether to install the local clone as editable.
