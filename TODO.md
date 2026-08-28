# TODO

## Context

+ Goal: rebuild `db/routing.duckdb` (currently an empty 12 KB husk, same for
  `datasets_processed/db/routing.duckdb`) from `datasets/problems` using the
  `Routing_data` submodule ETL.
+ 239 files on disk: 113 tsp, 19 atsp, 16 vrp, 9 hcp, 41 sop, 41 tour.
  Pipeline processes 198 of them: the CLI scans only tsp/atsp/vrp/hcp/sop;
  tours enter as solutions via sidecar `.opt.tour` discovery (46 linked rows
  in the test build; rd100 missed because its file has no DIMENSION).

## Database rebuild — locked design decisions

+ Destination: `db/routing.duckdb` canonical; delete the stale empty copies.
+ Schema topology: keep current ERD (problems + nodes + edge_weight_matrices +
  solutions + file_tracking). Keep the 9 VRP variant columns as they are.
+ `problems` additions: `tsplib_name VARCHAR`, `fixed_edges INTEGER[][]`,
  `adjacency INTEGER[][]`, `UNIQUE(name, type)`.
+ Name twins: `name` = file stem when the internal NAME collides within the
  same type; original NAME goes to `tsplib_name`
  (e.g. `linhp318.tsp` declares `NAME: lin318` -> stored as `linhp318`).
  Cross-type twins (att48 / eil51 / gil262 as TSP and CVRP) keep the same
  `name`; the `type` column disambiguates them.
+ Matrix: replace `matrix_json TEXT` + `dimension` column with a single
  `matrix INTEGER[][]` (full n x n, always). 12.7 MB for all 80 EXPLICIT
  problems (vs 14.3 MB JSON today). Keep `matrix_format` (source layout
  provenance) and `is_symmetric`.
+ VRP EXPLICIT: expand customer-only (n-1)x(n-1) matrices to n x n with a zero
  depot row/col at ETL (fixes eil7 / eil13 / eil31).
+ HCP: adjacency stored in `problems.adjacency` as flat `[from,to,...]` pairs;
  FIXED_EDGES_SECTION stored in `problems.fixed_edges` (linhp318: `[[0,213]]`).
  HCP rows have no coordinates and no matrix; adjacency is their only graph
  data.
+ Loader API: `load(name, type)` both required; raise NotFound on 0 rows;
  ambiguity impossible via UNIQUE(name, type).
+ Tour sidecar solutions: derive missing DIMENSION from the linked problem
  (rd100.opt.tour and similar).
+ Type vocabulary: `CVRP` (file-declared), not legacy `VRP`.
+ Unchanged: nodes merged demand/is_depot, file_tracking checksum upsert,
  solutions.routes INTEGER[][], tours stored only as solutions, 0-based ids.
+ Out of scope for now: solution_name cleanup, submodule docs updates,
  submodule tests, git commits/pushes (await explicit go-ahead).

## Implementation plan (Routing_data submodule only)

+ `src/converter/database/operations.py`
  * DDL: add tsplib_name / fixed_edges / adjacency, UNIQUE(name, type);
    swap matrix_json for `matrix INTEGER[][]`; keep matrix_format + is_symmetric.
  * Batch insert: replace the name-keyed `problem_id_mapping` join (source of
    the att48/eil51/gil262/lin318 node cross-contamination) with a
    temp_id-keyed mapping built from INSERT ... RETURNING.
  * Expand VRP (n-1) matrices to n x n before insert.
  * Query API: load(name, type) with NotFound semantics; full-matrix accessor.
+ `src/tsplib_parser/parser.py`
  * Extract EDGE_DATA_SECTION (EDGE_LIST / ADJ_LIST) and FIXED_EDGES_SECTION.
  * Sidecar tour parse: fall back to problem dimension when DIMENSION missing.
+ `src/converter/core/transformer.py`
  * Pass adjacency / fixed arcs through; stem-based name disambiguation
    (name vs tsplib_name).
+ `src/converter/utils/worker_functions.py`
  * Extend the worker payload with adjacency / fixed edges.
+ `pyproject.toml`
  * Declare pandas (batch insert imports it; a standalone submodule venv
    crashes without it - confirmed in the first test run).
+ Rebuild — **EXECUTED (Batch 4, 2026-08-27)**
  * Ran from the repo root with the local submodule code:
    `PYTHONPATH=src/submodules/Routing_data/src uv run python
    src/submodules/Routing_data/converter_cli.py process
    -i datasets/problems -o /tmp/routing_rebuild --force --parallel --workers 4`
    Result: 198 processed, 0 failed (TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41).
  * Copied `/tmp/routing_rebuild/db/routing.duckdb` → `db/routing.duckdb` (21 MB,
    replaces the 12 KB husk). `rm -f datasets_processed/db/routing.duckdb` run
    (repo root — path does not exist → no-op). Submodule's git-tracked
    `datasets_processed/db/routing.duckdb` left untouched (out of pinned scope).
  * Deleted the stray `.venv` the submodule dir acquired during testing (Task 4.2).
  * **Validation gate EXECUTED (Batch 5, reviewer, 2026-08-27) — PASS (20/20)**
    * 198 problems: TSP=113, ATSP=19, CVRP=16, HCP=9, SOP=41; matrices=80
      (= `edge_weight_type='EXPLICIT'`, 1:1 with matrix rows), nodes=334813,
      solutions=43, file_tracking=198 — all fully linked.
    * Matrix dim == problem dim on all 80 EXPLICIT rows; zero HCP matrix rows;
      9/9 HCP adjacency non-null (1998–9999 0-based pairs).
    * `linhp318.fixed_edges == [[0,213]]` (`tsplib_name='lin318'`); zero
      duplicate (name, type); UNIQUE constraint present.
    * Spot-checks pass: berlin52 (EUC_2D, 0-based tour permutation of 0..51),
      br17 (ATSP 17×17 asymmetric; no tour sidecar in the dataset → no solution
      row), eil13 (CVRP 13×13, zero depot row/col, m[1][1]=9), att48 TSP+CVRP
      (distinct ids, 48 nodes each), alb1000 (HCP, 1998 adjacency pairs, zero
      matrix rows).
    * FYI (no criterion violated): 19/43 solution `cost` NULL where the source
      tour has no length comment; HCP/EXPLICIT problems carry dimension-many
      virtual node rows (NULL coords) — pre-existing `_extract_nodes` design.

## Deferred — main repo issues (do not touch yet)

+ [ ] Circular import `src/distances/matrix.py` <-> `src/protocols/problem_context.py`:
  * `src/protocols/__init__.py` eagerly imports `problem_context`, which imports
    `..distances.matrix` (line 59), which imports `..protocols.backend` while the
    `src.protocols` package is still initializing.
  * Effect: the first `DatabaseLoader.load()` for a coordinate-based problem in
    any fresh process raises
    `ImportError: cannot import name 'compute_distance_matrix' from partially
    initialized module 'src.distances.matrix'`; the second call works (module cached).
  * Repro: `berlin52` via `DatabaseLoader` against any built routing.duckdb.
  * Candidate fix: move `BackendModule` import in `src/distances/matrix.py` under
    `TYPE_CHECKING` (annotation-only use).
+ [ ] Main-repo consumers hardcode `datasets/routing.duckdb`
      (`src/benchmarking_v2/orchestration.py:315`,
      `src/benchmarks_v2/run_chapter4_benchmark.py:154`,
      `DatabaseLoader` default). Canonical DB will live at `db/routing.duckdb`.
      Reconcile paths later.
+ [ ] `Problem` model / `DatabaseLoader` only support TSP/ATSP/CVRP.
      SOP/HCP/TOUR rows in the DB will be stored but not loadable by the model.
      Revisit if benchmarks extend beyond those types.
+ [ ] `datasets/inspect_database.py` is stale: default path points at
      datasets_processed/db/routing.duckdb (being deleted) and its detail view
      expects legacy tables (depots, demands, optimal_tours / optimal_routes)
      that the current schema does not have. Update or retire.
+ [ ] Root `pyproject.toml` `[tool.uv.workspace]` members entry
      `data/Routing_data/vrp_database` points to a directory that does not
      exist. Reconcile with the submodule layout or remove.
+ [ ] Main venv has `routing-data` installed from git `main`, which drifts from
      the local clone (commit 0e55b8c). Rebuilds must use the local src via
      PYTHONPATH; decide later whether to install the local clone as editable.
