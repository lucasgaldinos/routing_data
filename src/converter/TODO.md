# TODO — `converter`

_Open problems in `src/converter/**`. Parser-side findings live in [`../tsplib_parser/TODO.md`](../tsplib_parser/TODO.md)._

_Registered 2026-10-13 from the `tsplib_parser` review decisions (P2/P3 in that file)._

## Distance layer (`utils/cost.py`)

This module owns the TSPLIB coordinate-distance registry (`_COORD_DISTANCES`). The parser deliberately does **not** compute weights — it records the declared `EDGE_WEIGHT_TYPE`, and the arithmetic lives here (decision **P2**, revised 2026-10-14: a parseable problem is never rejected for a missing cost function).

### CV1 — Implement XRAY1/XRAY2 distances — **done 2026-10-14**

- **What:** `XRAY1` and `XRAY2` are in `_COORD_DISTANCES`, implemented from the distribution's own `DEQ`/`DUN` listings in `datasets_raw/zips/xray.problems` plus the spec's §2.7 `×100` rounding proposal.
- **Where:** `src/converter/utils/cost.py` (`_xray`, `_xray1`, `_xray2`); tests in [`tests/converter/test_unit_cost.py`](../../tests/converter/test_unit_cost.py).
- **Verified:** six hand-computed pairs pass (360° wrap, per-axis motor speeds, sign, the 180° boundary) plus the canonical tour of both instances.
- **Oracle:** the `DEQ`/`DUN` routines were compiled with `gfortran -O2` and run over `xray14012_1.tsp` (identical coordinates to `xray14012_2.tsp`, verified by diff — only `NAME` and `EDGE_WEIGHT_TYPE` differ):

  ```text
  n = 14012
  XRAY1 sum(ICOST)      = 15429419
  XRAY2 sum(ICOST)      = 12943295
  XRAY1 nint(100*TCOST) = 15429513
  XRAY2 nint(100*TCOST) = 12943292
  ```

  The per-edge sums equal the python results exactly, so the implementation is faithful to the reference code rather than merely close to it.
- **Oracle decision (2026-10-15):** the Fortran stays a _reference_, not a runtime dependency. TSPLIB95 defines the crystallography distance _by_ those routines (its text points at the code), and upstream `rhgrant10/tsplib95` likewise treats `deq.f`/`duneq.f` as archival, porting the formula to python. Since the per-edge sums already agree exactly, the oracle is kept as a recipe instead of a committed test: the listing ships in-repo at `datasets_raw/zips/xray.problems` (`DEQ` and `DUN`, around lines 145-178), and the driver used here was a short `gfortran` program that reads `xray14012_1.tsp` and prints `n`, both per-edge sums and both single-rounding sums. Re-derivable in a minute; no compiler dependency added to the suite.
- **Open question (residue):** §2.8 publishes **15 429 219** (XRAY1) and **12 943 294** (XRAY2) for the same tour — deltas **+200 (1.3 × 10⁻⁵)** and **+1 (7.7 × 10⁻⁸)**. Every plausible aggregation was measured against them: per-edge rounding (15 429 419 / 12 943 295), single rounding `nint(100·Σcost)` (15 429 513 / 12 943 292), truncation (15 422 571 / 12 936 245), open tour without the closing edge (15 411 419 / 12 928 895), and wrapping the CHI/TWOTH axes at 360° (no effect). None reproduces the published pair, while the distribution's compiled routines reproduce this implementation — so the residue sits in the published numbers, not in the arithmetic. The test locks the computed values exactly and cross-checks the published ones within `1e-4`. Settling it further would need the original Bland/Shallcross routines for this instance.
- **Schema:** XRAY distances are bounded by `100 × 360 ÷ min(speed)`, i.e. at most 36 000, so `INTEGER` (int32) needs no change. Nothing in the schema was touched by this task.

### CV2 — `SPECIAL` dispatch hook — **done 2026-10-15**

- **What:** `compute_routes_cost(..., special=callable)` uses the caller's function for `EDGE_WEIGHT_TYPE: SPECIAL`, and `supported_weight_types()` answers "can this module compute a cost for this type" without raising.
- **Where:** `src/converter/utils/cost.py`; tests in [`tests/converter/test_unit_cost.py`](../../tests/converter/test_unit_cost.py) (`TestUnsupportedWeightTypes`, 7 tests).
- **Contract, as implemented:**
  + `SPECIAL` without a callable → `UnsupportedFeatureError` — never a silent `None`.
  + `SPECIAL` with a callable → that callable produces the distances.
  + a TSPLIB95 weight type with no registry entry → `UnsupportedFeatureError` (a supported-feature gap, not a malformed file). The distinction comes from `EDGE_WEIGHT_TYPES` (`src/tsplib_parser/types.py`, spec §1.1.6), so a legal type can never be reported as unknown.
  + a value that is not a TSPLIB95 weight type at all (`EUC_9D`) → `FormatError`, never a bare `KeyError`.
  + `None` keeps one meaning only: no weight source at all — no matrix, no coordinates, or `EXPLICIT` without its matrix.
  + `matrix` wins over `coords` when both are supplied.
- **Blast radius:** none yet — `compute_routes_cost` has no caller in `src/**`, so the new failure modes cannot break the current pipeline.
- **Layering:** `cost.py` now imports the parser's vocabulary and exceptions (`tsplib_parser.types`, `tsplib_parser.exceptions`) rather than keeping a second copy. Deliberate: the converter already depends on the parser, and one vocabulary is what stops producer and consumer drifting apart (PC8).
- **Caller error vs data limitation (review follow-up, 2026-10-15):** passing `special=` for a file that does not declare `EDGE_WEIGHT_TYPE: SPECIAL` now raises `ValueError`, because the two sides disagreeing is a caller/config bug — the callable would otherwise vanish the way the removed `special_func` did (`PB1`). `UnsupportedFeatureError` stays reserved for "the file asks for something this layer cannot compute".
- **`None` contract:** `None` means "no weight source at all" and has four causes, all documented on `compute_routes_cost`: no matrix and no coordinates; `EXPLICIT` without its matrix; coordinates without `edge_weight_type`; and a type whose distances do not exist (`HCP`, `TOUR`). The third is a broken file per §1.1.6, so it belongs to the validator, not here — `validate_problem_data` now reports it for the weight-bearing types (0 of 239 corpus files affected).

## Verification

**Cross-checks from the architecture pass (2026-10-15):** two converter-side gaps were reproduced with line references and need no new register entry — `database/operations.py:105` `CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP'))` cannot store `TOUR` (41 corpus files), registered as **M12** in [`../../TODO.md`](../../TODO.md); and `cli/commands.py:28` calls `setup_logging(level=log_level)` without `log_file`, so the CLI run log promised by **P7** does not exist (registered as **m12**, "`log_file` never wired").

```bash
uv run pytest tests/test_converter/test_cost.py -q
uv run pytest tests -q -k "cost or distance or xray"
```

`pytest` is installed in the venv since 2026-10-15, so the plain `uv run pytest` form works (before that, `uv run pytest` silently used `/usr/bin/pytest`, the system interpreter, which is what made a `duckdb` import error appear out of nowhere — see the finding below).

Notes:

- Keep a single rounding policy (`nint`) across every distance function — that is the spec's.
- XRAY distances are bounded by `100 × 360 ÷ min(speed)`, i.e. at most 36 000, so the `INTEGER` schema column is sufficient (`CV1`).

## Findings registered 2026-10-15

- **`pytest` is a runtime dependency.** `uv add pytest` placed `pytest>=9.1.1` in `[project] dependencies`, while the `dev` extra already listed `pytest>=8.4.2`. Consequence: anyone installing this package installs a test runner. Fix: `uv remove pytest` and `uv add --dev pytest` (or keep the `dev` extra alone), then re-run the suites. Left as a packaging decision — the user made the change deliberately to unblock the runs.
- **`EDGE_DATA_FORMAT` is ignored, and the spec's `ADJ_LIST` form loses data** — **PB12** in [`../tsplib_parser/TODO.md`](../tsplib_parser/TODO.md), found by the new section-grammar tests. Converter-side impact: a colon-less adjacency list arrives with edges missing and nothing here would notice.
- **`DISPLAY_DATA_SECTION` is dropped for coordinate-less problems** — **PB13**, same origin. Converter-side impact: `bayg29.tsp` ships 29 display rows that never reach `nodes`.

---

## Open Tasks & Findings Registered 2026-10-21

### CV3 — Rename `DataTransformer` -> `ProblemNormalizer` (Task 4.1)

- **Problem**: Naming collision between `tsplib_parser.transformers.Transformer` (format string deserializer) and `converter.core.transformer.DataTransformer` (ETL domain normalizer).
- **Plan**: Class-only rename `DataTransformer` -> `ProblemNormalizer` in `src/converter/core/transformer.py`. Update references in `src/converter/` and `tests/converter/`. Keep module filename intact to minimize blast radius.
- **Status**: OPEN. Deferred to the converter rework batch.

### CV4 — Pre-existing v1-schema assertion failures — **CLOSED (stale entry)**

- **Original report (2026-10-21)**: 14 tests in `tests/converter/test_unit_transformer.py` and `tests/converter/test_integration_pipeline.py` failed against retired v1 structures (`insert_nodes`, `nodes` table layout).
- **Re-measured 2026-10-23**: `.venv/bin/python -m pytest -q` → **306 passed, 0 failed**. Both files are green (`test_unit_transformer.py` 11 passed, `test_integration_pipeline.py` 6 passed via `test_integration_pipeline.py`).
- **Action**: none. Kept only so the entry does not reappear as folklore.

### CV5 — Lint and import cleanups in `src/converter/`

- **Problem**: `core/transformer.py:127` exceeded 120 columns; `utils/parallel.py:3` imported `_thread.LockType` at runtime and had unsorted imports.
- **Status**: **DONE 2026-10-23** — `.venv/bin/python -m ruff check src tests` → All checks passed. `LockType` sits under `if TYPE_CHECKING:`; the long comprehension is wrapped.

### CV6 — Expand database schema `CHECK` constraint for valid problem types

- **Problem**: `database/operations.py:105` defines `CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP'))`. This hard-fails and rolls back batches for:
  + 41 valid TSPLIB `TOUR` files in `datasets_raw/problems/`.
  + Extended LKH-3 benchmark problems (`CVRPTW`, `TSPTW`, `MDVRP`).
- **Action**: Align the `CHECK` constraints with `tsplib_parser.types.VALID_PROBLEM_TYPES` and `LKH_PROBLEM_TYPES`.
- **Status**: OPEN — this is **M12** in [`../../TODO.md`](../../TODO.md) and the user-confirmed success criterion for the rework.

### CV7 — Typing rework register (opened 2026-10-23)

`mypy` (2.4.0) is installed in `.venv` for the first time, so these were measured, not guessed.
Full `mypy src` → **18 errors in 5 files**; `tsplib_parser` contributes **0**.

| ID | Module | Errors | Locations | Cause |
| --- | --- | --- | --- | --- |
| **T1** | `utils/parallel.py` | 6 mypy; 7–17 pyright depending on profile | `:51,59,89,158,178,242` | Bare `Callable` (3), untyped `Queue()`, `_start_time` inferred `None`, and `dict[str, Any]` producer contract leaking `Unknown` through `Future`/`as_completed` |
| **T2** | `utils/update.py` | 7 | `:37,205,207,209,213,214,218` | `_change_cache` untyped → values are `object`, so `+ int` and `.append` fail |
| **T3** | `output/parquet_writer.py` | 3 | `:73,74,224` | `str` parameter reassigned as `Path`; `fetchone()` tuple indexed without a `None` guard |
| **T4** | `cli/commands.py` | 1 | `:552` | `fetchone()` tuple indexed without a `None` guard |
| **T5** | `config.py` | 1 note | `:7` | `pyyaml` has no `py.typed`; needs `types-PyYAML` (dev) or a targeted override |

**The contract decision that unblocks T1** (not yet approved): the worker boundary currently returns one
`dict[str, Any]` for two different shapes — success (`worker_functions.py:96-112`, 12 keys) and failure
(`:115-120`, 4 keys) — and `parallel.py` distinguishes them by `"success" in result`. Replacing that
with a named union (`WorkerSuccess | WorkerFailure`, or a `TypedDict` with `success: bool` plus
`NotRequired` payload keys) and making `process_files_parallel` generic over the worker's return type is
what removes all 23 flags at once. Everything downstream (`commands.py:151-161`, the DB writer) inherits
the same contract.

**Measured constraint for the isolation design (2026-10-23):** `duckdb` 1.5.6 rejects `SAVEPOINT` with a
`ParserException` (verified on a throwaway in-memory DB). Per-problem failure isolation therefore cannot
use savepoints inside one transaction; it has to be **pre-flight validation of each payload before it
reaches SQL** (required keys, `type` in the taxonomy, array lengths vs `dimension`) plus **one transaction
per problem** for the residue, or `INSERT ... ON CONFLICT` upserts where a rerun must be idempotent.
Budget the cost accordingly: one commit per problem is the price of "a bad file fails alone".

### CV9 — Write-path and output measurements (2026-10-23)

Four defects reproduced end-to-end against a throwaway database, not inferred from reading code:

1. **A single `TOUR` file destroys the whole batch.** `process_file_for_parallel("gr48.opt.tour")` succeeds
   (type `TOUR`), then `_normalize_type_for_schema` raises `DatabaseError`, the batch transaction rolls
   back, and a batch of `[berlin52.tsp, gr48.opt.tour]` reports `total_inserted=0` with `berlin52` gone
   too. The failure list repeats the same message for **every** row, so the guilty file is not even named.
   Corpus exposure: `82` files declare `TYPE : TOUR`, second only to `TSP` (`226`).
2. **Instance-type identity is collapsed.** `_normalize_type_for_schema` maps _anything_ containing `VRP`
   to `CVRP`, so `MDVRP` / `CVRPTW` / `VRPB` are stored with hub `type = 'CVRP'` and their extended
   attributes (`time_windows`, `service_times`, `pickup_and_delivery`, `vehicles`, `periods`,
   `depot_capacities`, `depot_durations`, `max_distance`) have no column to land in — silently dropped.
3. **Float matrices are rounded.** `edge_weight_matrices.matrix` is `INTEGER[][]`; inserting a `1.5`
   distance reads back as `2`. Confirmed by round-trip (`M3`).
4. **JSON output drops the distance matrix.** For `br17.atsp` (17×17 `FULL_MATRIX`) the transformed payload
   carries `edge_weight_matrix`, but `to_json_format` copies only `problem/tours/metadata/coords/
   display_coords/demands/depots/edges/fixed_edges`, so the written file is 942 bytes with **no** matrix —
   an EXPLICIT instance becomes unusable in JSON. `json.dump(..., default=str)` also masks serialization
   failures instead of raising.

Current storage surface for reference: hub `problems(id, name, type CHECK IN ('TSP','ATSP','CVRP','HCP','SOP'),
has_solution, created_at, updated_at, UNIQUE(name, type))`; type tables `tsp_problems`, `atsp_problems`,
`cvrp_problems`, `hcp_problems`, `sop_problems`; satellites `edge_weight_matrices(problem_id, matrix_format,
is_symmetric, matrix INTEGER[][])` and `file_tracking`. Parquet export is one `COPY … (FORMAT PARQUET)` per
table, so the artifact set is exactly the table set (8 files today) — every schema change changes the
consumer contract.

**Open modeling question (blocks the schema work):** `*.opt.tour` files are _solutions of_ an instance
(`gr48.opt.tour` ↔ `gr48.tsp`), not problems with geometry. Decision 11 deferred the `solutions` table.
Storing 82 tour files as `problem` rows may be the wrong model; linking them as solutions to their instance
may be the right one. Corpus weight: **390 `.sol`** (CVRPLIB route solutions) + **82 `.opt.tour`** = 472
solution files against 511 parseable problems, and neither kind has any storage today
(`process_solution_file` is dead code, G2/m4).

**Characterization suite landed 2026-10-23 (S0 of the rework).** Four new files pin the write path before
any behaviour changes; six `xfail(strict=True)` are the red-to-green targets for this register:

| File | Pins | Registered gaps it encodes |
| --- | --- | --- |
| `tests/converter/test_integration_schema_contract.py` | 8 tables, column order/types, `problems.type` CHECK, `UNIQUE (name, type)` | — (all pass; the snapshot changes only deliberately) |
| `tests/converter/test_integration_type_coverage.py` | worker → insert → read-back for TSP/ATSP/CVRP/HCP/SOP | `TOUR` refusal, `MDVRP` → `CVRP` collapse (2 xfail) |
| `tests/converter/test_integration_output_contract.py` | JSON key set/values, parquet = one file per table with matching counts, JSON↔DB identity | EXPLICIT matrix missing from JSON (1 xfail, CV9 item 4) |
| `tests/converter/test_integration_batch_accounting.py` | inputs == inserted + failed + skipped; siblings survive; empty payloads counted | batch-wide rollback, wrong attribution, silent skip (3 xfail, B1/B3) |

- **Problem**: `pyproject.toml` `dependencies` listed `mypy>=2.4.0`, `pytest>=9.1.1` and `ruff>=0.16.6`, while the `dev` extra listed lower pins of the same tools. Installing the package installed a type checker, a test runner and a linter.
- **Cause**: `uv add <tool>` defaults to the main dependency group.
- **Resolution**: `uv add --dev mypy pytest ruff` then `uv remove mypy pytest ruff`. Runtime dependencies are now `click`, `duckdb`, `pandas`, `psutil`, `pyyaml`; `[dependency-groups].dev` is canonical (CI runs `uv sync --dev`) and `[project.optional-dependencies].dev` is documented in-file as its mirror for `pip install -e ".[dev]"`. Verified: `mypy 2.4.0`, `ruff 0.17.0`, `pytest` → 306 passed.
- **Still open nearby (not this task)**: `pandas` has zero imports in `src/**` (**m20**).

### CV10 — Solutions storage (Option A) — decisions and step plan

Approved 2026-10-23. The parser can produce solutions and the converter cannot store them: **390 `.sol` +
82 `.opt.tour` = 472 solution files**, and `find_solution_file` / `parse_solution_data`
(`core/transformer.py:224`, `:258`) have **zero production callers**. `problems.has_solution` is never set
and the JSON `tours` key is always empty.

Decisions taken:

- **One row per solution.** `solutions.source_file` is `UNIQUE`; the same file is never stored twice.
- **Documented flaw.** A `*.opt.tour` declares only `NAME : <stem>.opt` and `TYPE : TOUR` — never the type
  of the instance it solves — and dimension does not disambiguate (`att48.tsp` and `att48.vrp` are both
  dimension 48). Measured corpus overlap: **2 instances** (`att48`, `eil51`) have a cross-type twin
  (`gil262` has a twin but no tour). When the stem matches several instances **the program cannot tell
  which problem the solution belongs to**, so the row is stored with `problem_id IS NULL` and a warning;
  it is never attached to a guess. Consumers must treat such rows as "solution of _some_ instance named
  X" and resolve it themselves.
- **Orphans are legal.** `problem_id` is nullable; a solution may arrive before its instance.
- **`.txt` instances are in scope.** 356 of the 390 `.sol` files belong to Holmberger-family instances
  shipped as `.txt`, which the scanner does not ingest today; those become orphans unless the scanner
  learns `.txt` (A5).
- **Scope of the first pass:** Option A in full, delivered as A1–A6.

| Step | Content | State |
| --- | --- | --- |
| **A1** | `solutions` table + sequence + index, contract tests, `docs/ARCHITECTURE.md` | **DONE 2026-10-23** |
| **A2** | `converter/types.py` (vocabularies) + `core/contracts.py` (`ParsedSolution` / `SolutionPayload`) + `core/solutions.py::parse_solution_file()` (in-memory, no temp file, raises on failure) + unit tests for both formats + corpus sweep | **DONE 2026-10-24** |
| **A3** | `candidate_solution_files()` + `solution_stem()` + `link_solution()`: forward link by corpus layout, backward link by stem, `Linked`/`Unlinked` result instead of a bare `None` (CV10) | **DONE 2026-10-24** |
| **A4** | `insert_solutions()` + batch integration + `has_solution` flip + solution accounting | open |
| **A5** | Scanner classifies `.opt.tour` / `.sol` as solutions (not problems) and ingests `.txt` instances; unblocks the 82 `TOUR` files | open |
| **A6** | Outputs: JSON `tours` populated, `solutions.parquet`, parity tests | open |

A2 detail: three modules, each with one job (see CV12 for why they are separate).

| Module | Owns | Contents |
| --- | --- | --- |
| `src/converter/types.py` | value vocabularies | `SolutionKind`, `SOLUTION_KINDS`, `SolutionQuality`, `SOLUTION_QUALITIES`, each tuple derived from its `Literal` via `get_args` |
| `src/converter/core/contracts.py` | boundary shapes, no logic | `ParsedSolution` (`kind`, `quality`, `source_file`, `cost`, `routes`); `SolutionPayload` = `ParsedSolution` + `problem_id` |
| `src/converter/core/solutions.py` | parsing | `parse_solution_file()`, `SolutionParseError`, `_parse_tour`, `_parse_sol`, `_cost_from_comment`, `_to_zero_based`, `_read_text` |

`ParsedSolution` deliberately has no `problem_id`: the parser cannot know it, and a placeholder would let
an unlinked row look linked. `SolutionPayload` is what the insert layer consumes. `_read_text` decodes
UTF-8 and falls back to latin-1, which closes **M9** (non-UTF-8 CVRPLIB files raised before).
`tests/converter/test_unit_solutions.py` holds 13 tests: eleven targeted cases (comment cost, absent cost,
many routes, signed/scientific cost, missing and empty `TOUR_SECTION`, `.sol` without routes, unknown
suffix, rejected zero-indexed id, latin-1 fallback, `-1` terminator) and two corpus sweeps (82
`*.opt.tour`, 390 `.sol`), each asserting the contiguity invariant
`sorted(nodes) == list(range(len(nodes)))`. No equivalence guard against `FormatParser` was needed:
`FormatParser` never parsed solutions, so there was nothing to compare against (CV11 entries corrected
accordingly).

The vocabulary is written down once, in `types.py`, while the DDL carries a static CHECK string; the drift
is closed by `test_solution_vocabularies_match_the_database`, which reads `duckdb_constraints().expression`
back out of the database and compares it with the tuples. Editing one side without the other fails the test.

A3 detail: linking has **two directions**, and only one of them can be ambiguous.

| Direction | Entry point | Information used | Ambiguity |
| --- | --- | --- | --- |
| forward (problem -> solution) | `candidate_solution_files(problem_path)` | the corpus layout: `X.vrp`/`X.txt` + `X.sol` are siblings, `tsp/X.tsp` + `tour/X.opt.tour` are cousins | impossible: the path names the instance |
| backward (solution -> problem) | `link_solution(parsed, problems_by_stem)` | the stem only, lowercased | possible; returns `Unlinked("ambiguous")` |

Measured 2026-10-24 before writing either rule:

| Claim | Measurement |
| --- | --- |
| every `.sol` has a same-stem sibling instance | 390/390 |
| every tour sits in `<family>/tour/<stem>.opt.tour` | 82/82, in both corpus trees |
| tours are named `.opt.tour`, not `.tour` | 82/82 (a `{stem}.tour` guess finds nothing) |
| a tour may belong to an `.hcp` instance | `alb1000` ships **only** as `hcp/alb1000.hcp`, yet has a tour |
| a tour must never go to a route instance | `att48` and `eil51` exist as `.tsp` **and** `.vrp`; the tour is the TSP twin's |
| stems that exist as more than one problem type | 3 (`att48`, `eil51`, `gil262`); only the first two ship tours |
| backward link over the whole corpus | 468 `Linked`, 4 `Unlinked("ambiguous")` (2 tours x 2 duplicate trees), 0 `no_instance` |

`TOUR_INSTANCE_SUFFIXES` (`{".tsp", ".atsp", ".sop", ".hcp"}`) is therefore not a guess: `.hcp` is required
by `alb1000` and `.vrp` exclusion is required by `att48`/`eil51`. `.atsp`/`.sop` ship no tour today, so their
inclusion changes nothing measurable and needs no later migration. The set lives in `solutions.py` beside
`TOUR_DIR_NAME`, because both describe **corpus layout**, not problem semantics -- no `ProblemType` is
duplicated (`M12` stays closed).

`link_solution` returns `Linked(problem_id)` or `Unlinked(reason, candidate_ids)` instead of a bare
`int | None`: "no instance yet" (356 `.sol` files whose `.txt` instances A5b has not ingested) and "two
instances" (the `att48` case) need different reporting, and `None` erases the difference. Both reasons are a
vocabulary, `UnlinkReason` in `converter/types.py`.

Three mutations were run to prove the tests are load-bearing: allowing `.vrp` to claim a tour, dropping
`.hcp`, and picking the first contender instead of refusing. Each turned the suite red, then was reverted.

A1 detail (amended after measuring the formats): both formats share **one** representation, `routes
INTEGER[][] NOT NULL` — a `*.opt.tour` cycle is a one-element `routes`, a `*.sol` holds its vehicle
routes. The original `tour` column and `is_optimal` boolean were dropped: `kind` is provenance (source
format) and `quality` (`proven_optimal` / `best_known` / `unknown`) is the claim the source makes, because
a boolean collapsed "best known" with "unknown". `CHECK (kind IN ('OPT_TOUR','SOL'))`,
`CHECK (quality IN (...))` and `routes NOT NULL` are verified by tests that insert violating rows
(`tests/converter/test_integration_schema_contract.py`), so the constraints are executable, not decorative.

Formats measured across all 472 solution files (2026-10-23):

| Family | Files | `Cost` line | id range | depot listed? | routes/file |
| --- | ---: | ---: | --- | ---: | --- |
| Holmberger `.sol` | 300 | 300/300 | 1 .. 600–1000 | never | 4–100 |
| VRP-set-D `.sol` | 12 | 12/12 | 1 .. 700–1000 | never | 12–64 |
| Vrp-Set-Li `.sol` | 12 | 12/12 | 1 .. 1040–1200 | never | 10–20 |
| Vrp-Set-Solomon `.sol` | 56 | 56/56 | 1 .. 100 | never | 3–20 |
| vrp-XXL `.sol` | 10 | 10/10 | 1 .. 16 000–30 000 | never | 46–684 |
| `.opt.tour` | 82 | — | 1 .. `DIMENSION`, unique | never | 1 tour, all nodes |

Conclusion: the two formats differ in cardinality and in whether a cost is present, **not** in numbering, so
one normalisation rule covers both (`index = id - 1`, depot excluded). Holmberger _instances_ list the depot
as `CUST NO. 0`, so the A5 `.txt` adapter must map `CUST NO. k` to index `k` or that rule breaks for that
family. `quality` defaults: `*.opt.tour` → `proven_optimal` (TSPLIB ships optimal tours), `*.sol` →
`best_known` (CVRPLIB/VRP-REP publish best-known solutions; UMA marks proven optima with `*`).

Still stale after A1: `docs/diagrams/database-schema.md` describes the **v1** topology (a `nodes` table and
no per-type tables); it needs the v2 diagram plus `solutions` once the write path is complete.

### CV11 — Solution parsing layer: full replacement plan (A2/A3/A4)

Measured 2026-10-24 before writing any code. The layer has **zero production callers** (only my own
docstring mentions `find_solution_file`), but it is not broken — it _works when called directly_:

| Probe | Result |
| --- | --- |
| `parse_solution_data("…/gr48.opt.tour", parser)` | `{'name': 'gr48.opt.tour', 'type': 'TOUR', 'cost': 5046.0, 'routes': [[…48 nodes]]}` — cost recovered from the `COMMENT` |
| `parse_solution_data("…/alb1000.opt.tour", parser)` | 1000 nodes, `cost=None` (no comment, no cost in file) |
| `find_solution_file("problems/tsp/gr48.tsp")` | `problems/tour/gr48.opt.tour` — the `parent.parent/tour` layout assumption holds for this tree |
| `find_solution_file("cvrplib/vrp-XXL/Leuven2.vrp")` | `cvrplib/vrp-XXL/Leuven2.sol` — sibling rule holds |

Defects that make it unfit for the write path — all latent, none of them exercised today:

1. `Path.read_text(encoding="utf-8", errors="latin-1")` puts an **encoding name in the error-handler slot**
   (`transformers.py` — `_parse_tour_file`). CPython resolves that handler lazily, so pure-ASCII tours parse
   fine and the first non-UTF-8 byte raises `LookupError`, which the broad `except` turns into `None`.
   Registered as **M9**; the register's wording ("tour files silently dropped") is therefore too strong —
   it only bites on non-UTF-8 input.
2. **Disk temp file** for DIMENSION injection (`tempfile.NamedTemporaryFile`), which violates §5.4 of
   `AGENTS.md` (in-memory parsing) and fails on a read-only filesystem.
3. `except Exception → return None`: a failed solution is indistinguishable from "no solution", the same
   silent-failure philosophy as S2/M4.
4. Untyped `dict[str, Any] | None` with invented fields (`name`, `type: "VRP"`).
5. `find_solution_file` knows exactly two layouts (hardcoded `parent.parent/tour`, `with_suffix(".sol")`)
   and returns the **first** hit, with no notion of ambiguity (CV10) or of `.txt` instances.

Target design (no half measures — the old symbols are replaced, then deleted):

```text
converter/core/contracts.py        # A2
  SolutionKind    = Literal["OPT_TOUR", "SOL"]
  SolutionQuality = Literal["proven_optimal", "best_known", "unknown"]

  class ParsedSolution(TypedDict):     # what a parser can know alone
      kind: SolutionKind
      quality: SolutionQuality
      source_file: str
      cost: float | None
      routes: list[list[int]]          # 0-based, depot excluded

  class SolutionPayload(ParsedSolution):  # + what only the linker can know
      problem_id: int | None

converter/core/solutions.py        # A2 (+ A3)
  parse_solution_file(path: Path) -> ParsedSolution     # raises SolutionParseError, never returns None
  candidate_solution_files(problem_path: Path) -> list[Path]   # A3
  link_solution(parsed, problems_by_stem) -> int | None        # A3, one row per file (CV10)
```

Splitting `ParsedSolution` from `SolutionPayload` avoids a `problem_id=None` placeholder that would lie
about who fills it.

| Existing symbol | Lines (`core/transformer.py`) | Fate | Step |
| --- | --- | --- | --- |
| `find_solution_file` | 224-256 | replaced by `candidate_solution_files` + `link_solution`; **deleted** | A3 |
| `parse_solution_data` | 258-286 | replaced by `parse_solution_file`; **deleted** | A2 (write) / A4 (delete) |
| `_parse_tour_file` | 288-367 | logic ported: in-memory `TOUR_SECTION` scan, no temp file, no `FormatParser` dependency; **deleted** | A2 / A4 |
| `_parse_sol_file` | 369-424 | logic ported (regex routes + `Cost`); **deleted** | A2 / A4 |
| `_extract_cost_from_comment` | 426-440 | kept, renamed `_cost_from_comment` in `solutions.py` (gr48 proves it works) | A2 |

### CV12 — Vocabulary ownership and the Holmberger (`.txt`) question

Opened 2026-10-24 while reviewing A2. Two decisions that must be written down before `contracts.py` exists,
otherwise the solution vocabulary becomes a third copy of the same closed set (the `M12`/`S5` failure mode).

**Resolved by A2 (2026-10-24):** the three modules exist as described below, and the drift guard is
`test_solution_vocabularies_match_the_database` in `tests/converter/test_integration_schema_contract.py`
(it parses each `CHECK` and compares the literal set with the tuple — so an extra value on either side
fails, not just a missing one).

**1. `SolutionKind` and `SolutionQuality` are hardcoded exactly once.**

They are _value vocabularies_ — closed sets of allowed values — not boundary shapes. The declaration is
the `Literal`, and everything else derives from it at runtime:

```python
SolutionKind = Literal["OPT_TOUR", "SOL"]
SOLUTION_KINDS: tuple[SolutionKind, ...] = get_args(SolutionKind)  # runtime truth, derived
```

Consumers, all reading from that one place: the parser dispatch in `solutions.py`, validation before an
insert, run-summary grouping, tests that iterate the domain, and the SQL `CHECK` — which stays a **static,
readable DDL string** (no string building, so no `m17`-style interpolation) and is held honest by a test
that reads the stored constraint back:

```sql
-- drift guard: SELECT expression FROM duckdb_constraints()
--   WHERE table_name = 'solutions' AND constraint_type = 'CHECK'
-- must contain every value of SOLUTION_KINDS
```

`duckdb_constraints()` exposes `constraint_type` (`CHECK`, `FOREIGN KEY`, `PRIMARY KEY`, `NOT NULL`,
`UNIQUE`) and `expression`, so the comparison is a metadata query, not SQL parsing.

**2. Three families of "type", kept in different files.**

| Family | Answers | Construct | Lives where | Example |
| --- | --- | --- | --- | --- |
| Value vocabulary | which values are legal | `Literal` + derived tuple | `converter/types.py` | `SolutionKind`, `SolutionQuality` |
| Boundary shape | which fields travel together across a layer | `TypedDict` / `Protocol` | `converter/core/contracts.py` | `ParsedSolution`, `SolutionPayload`, `WorkerResult` |
| Domain model | data + behaviour | `dataclass` | the module that owns it | `CordeauProblem` |

`types.py` mirrors `tsplib_parser/types.py` (package-level vocabulary module) and must stay a leaf: no
imports from the database, the CLI or the writers. `contracts.py` is the opposite — it is imported by
producers and consumers alike and changes per integration. Merging them produces a file every module
imports, which is how a vocabulary becomes unchangeable.

Not in `contracts.py`: the DB schema itself (SQL has its own type vocabulary; the bridge is `types.py` plus
the drift test), private intermediate shapes that never cross a boundary, and the problem taxonomy — that
one stays in `tsplib_parser/types.py` and must never be duplicated here (`M12`).

**3. Holmberger `.txt` instances: no parser exists, and the format is CVRPTW, not CVRP.**

Verified 2026-10-24: `Holmberger/RC1_6_1.txt` is not TSPLIB and has no reader anywhere in `src/` (the only
format island is `cordeau/`, with parser + converter + types). Structure:

```text
RC1_6_1
VEHICLE
NUMBER     CAPACITY
 150          200
CUSTOMER
CUST NO.  XCOORD.    YCOORD.    DEMAND   READY TIME  DUE DATE   SERVICE TIME
    0     150        150          0          0       1206          0
    1     125        168         27        867        897         10
```

Consequences: ingesting these 356 instances is **writing a parser**, not adding a file extension, and the
instances carry `READY TIME` / `DUE DATE` / `SERVICE TIME` — a CVRPTW problem, which the current schema
cannot hold. `_normalize_type_for_schema` maps `CVRPTW` to `CVRP`, so ingesting them today would store 356
instances with their time windows **silently dropped** (`CV9` item 2, `M12`) — the same silent loss this
milestone exists to remove.

Therefore A5 splits:

| Step | Content | Unblocks |
| --- | --- | --- |
| **A5a** | Scanner classifies `.sol` / `.opt.tour` as solutions (not problems) and stops poisoning batches | 82 tours + the 34 `.sol` whose instances are already ingested |
| **A5b** | Holmberger island (`holmberger_parser.py` + types, mirroring `cordeau/`) **plus** the columns CVRPTW needs (`time_windows DOUBLE[][]`, `service_times DOUBLE[]`) | the remaining 356 `.sol` files, without data loss |

Until A5b, those 356 solutions are stored as orphans and reported — honest, and reversible with one
`UPDATE` once the instances exist.

Deletion happens in A4, when the batch writer calls the new functions and the old ones have no reason to
exist; until then the tests added in A2 pin the new behaviour, so the old code is unused, not "in use
twice".

A2 corpus guard (**corrected 2026-10-24**): the original plan compared `parse_solution_file(path)` with
`FormatParser().parse_file(path)["tours"][0]["nodes"]`. That comparison cannot exist — `FormatParser` is a
_problem_ parser and never parsed solution files, so there was no second implementation to agree with.
What A2 does instead is assert the property both formats must satisfy, over the whole corpus:
`routes` is contiguous (`sorted(nodes) == list(range(len(nodes)))`), a `*.opt.tour` is exactly one route
covering every node, and every `.sol` carries a cost. This is a stronger claim than equality with a
parser that never read these files, and it is what the old code silently assumed.

### CV13 — The corpus ships every instance twice (found during A3, open)

Measured 2026-10-24 while grounding the discovery rules:

| Observation | Measurement |
| --- | --- |
| `datasets_raw/problems/**` and `datasets_raw/zips/all_problems/**` hold the same instances | 198 files, 198 byte-identical |
| tours are duplicated the same way | 82 files for 41 distinct tours (40 identical, `rd100` differs only by a `DIMENSION` line) |
| problem files on disk | 786, but only 588 distinct `(stem, suffix)` pairs |
| solution files on disk | 472, but only 468 reach a distinct instance |

Consequence for A4: `solutions.source_file` being `UNIQUE` stops the _same path_ twice but not the _same
solution_ twice under two paths, so each of the 41 problems would get two solution rows and every
"solutions per instance" aggregate would double count. The `checksum` column (added in A1) exists for
exactly this: A4 should dedupe on `(problem_id, checksum)` semantics -- store the first path, report the
duplicate as skipped rather than silently dropping it. Left open on purpose: it is a write-path decision,
and A3 only had to make sure discovery does not _hide_ the second copy (it returns both files).

Registering it also corrects an assumption in CV10: "one row per solution file" is not the same as "one
row per solution".
