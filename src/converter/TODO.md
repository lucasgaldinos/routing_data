# TODO — `converter`

_Open problems in `src/converter/**`. Parser-side findings live in [`../tsplib_parser/TODO.md`](../tsplib_parser/TODO.md)._

_Registered 2026-10-13 from the `tsplib_parser` review decisions (P2/P3 in that file)._

## Distance layer (`utils/cost.py`)

This module owns the TSPLIB coordinate-distance registry (`_COORD_DISTANCES`). The parser deliberately does **not** compute weights — it records the declared `EDGE_WEIGHT_TYPE`, and the arithmetic lives here (decision **P2**, revised 2026-10-14: a parseable problem is never rejected for a missing cost function).

### CV1 — Implement XRAY1/XRAY2 distances — **done 2026-10-14**

- **What:** `XRAY1` and `XRAY2` are in `_COORD_DISTANCES`, implemented from the distribution's own `DEQ`/`DUN` listings in `datasets_raw/zips/xray.problems` plus the spec's §2.7 `×100` rounding proposal.
- **Where:** `src/converter/utils/cost.py` (`_xray`, `_xray1`, `_xray2`); tests in [`tests/test_converter/test_cost.py`](../../tests/test_converter/test_cost.py).
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
- **Where:** `src/converter/utils/cost.py`; tests in [`tests/test_converter/test_cost.py`](../../tests/test_converter/test_cost.py) (`TestUnsupportedWeightTypes`, 7 tests).
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

### CV4 — Resolve Pre-Existing Schema Assertion Failures in Converter Tests
- **Problem**: 14 tests in `tests/converter/test_unit_transformer.py` and `tests/converter/test_integration_pipeline.py` fail because they assert against retired v1 schema structures (`insert_nodes`, `nodes` table layout) rather than the v2 DuckDB schema.
- **Action**: Update test fixtures and expectations to match the canonical v2 schema without weakening validation guarantees.

### CV5 — Lint and Import Cleanups in `src/converter/`
- **Problem**:
  - `src/converter/core/transformer.py:127`: Line length exceeds 120 columns (130 characters).
  - `src/converter/utils/parallel.py:3`: Runtime import of internal `_thread.LockType` outside a `TYPE_CHECKING` block, plus unsorted imports.
- **Action**: Format long comprehension across multiple lines; move `LockType` to `if TYPE_CHECKING:` block.

### CV6 — Expand Database Schema `CHECK` Constraint for Valid Problem Types
- **Problem**: `database/operations.py:105` defines `CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP'))`. This hard-fails and rolls back batches for:
  - 41 valid TSPLIB `TOUR` files in `datasets_raw/problems/`.
  - Extended LKH-3 benchmark problems (`CVRPTW`, `TSPTW`, `MDVRP`).
- **Action**: Align database `CHECK` constraints with `tsplib_parser.types.VALID_PROBLEM_TYPES` and `LKH_PROBLEM_TYPES`.

