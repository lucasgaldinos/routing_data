# TODO

_Active implementation plan - routing_data parser hardening (tsplib_parser) + ETL visibility._

> Registered 2026-09-09 from the stepwise Q&A. Execution follows the `stepwise-explain-and-fix`
> protocol: one change at a time -> business-rule-first ELI5 -> askQuestions gate -> verify ->
> pause -> summary. Mermaid README (Task 5.2) is deliberately the LAST task.

## Current status

- [x] Review complete: 239-file corpus parses cleanly; `test_unit_parser_validation.py` = 100% green.
- [x] Batch 1 - `models.py` micro-cleanups (1.1 - 1.6 completed)
- [x] Batch 2 - `StandardProblem.parse` structural simplification & decomposition into `tokenization.py`, `fields.py`, `transformers.py`
- [ ] Batch 3 - ETL failure visibility (converter / CLI)
- [ ] Batch 4 - naming collision (`DataTransformer` -> `ProblemNormalizer`)
- [x] Batch 5 - docs: `src/tsplib_parser/README.md` with mermaid diagrams, updated TODOs, test layout conventions

## Decisions pinned

| # | Decision | Why |
| --- | --- | --- |
| D1 | Keep `FileMeta` metaclass | `__init_subclass__` never runs for `Problem` itself -> fields declared on the base class would silently never register. |
| D2 | No `@dataclass` / `ABC` | Fields are descriptors; a bare `Transformer()` is a deliberate no-op child; model-layer `parse` is already a classmethod. |
| D3 | No numpy in the parser | Text->number is already C `int()`; no gain at this data scale. |
| D4 | Cordeau stays an island | Separate grammar, own parser/converter; untouched. |
| D5 | Keep both `FuncT(int)` and `NumberT()` | Different strictness; used by different fields. |
| D6 | Task 4.1 = **option A**: class-only rename `DataTransformer` -> `ProblemNormalizer` | Smallest ripple; keeps `models.Transformer` upstream-faithful. |
| D7 | Batch 1 items 1.5 / 1.6 | Completed. |
| D8 | Subtractive LSP fix for `Problem.parse()` | Removed `parse()` on base `Problem`; parsing belongs to `StandardProblem` and `FormatParser`. |
| D9 | `Field.__get__` descriptor | Implemented non-data descriptor protocol, eliminating `Problem.__getattribute__` interception. |

## Non-goals / out of scope

- 14 pre-existing converter/integration failures (v1-schema assertions in `tests/converter/`) - not caused by parser refactoring; handled in converter batch.
- Removing the metaclass, adopting `@dataclass` or `ABC` - rejected (D1/D2).
- numpy in the parser - rejected (D3).

## Tasks

### Batch 1 - `models.py` micro-cleanups — **COMPLETED**

- [x] **Task 1.1 - `create_explicit_matrix` header cleanup**
- [x] **Task 1.2 - `FuncT.parse`: narrow the exception clause**
- [x] **Task 1.3 - `NumberT.parse` error parity with `FuncT`**
- [x] **Task 1.4 - `ContainerT.parse`: use the `enumerate` index**
- [x] **Task 1.5 - Dedupe terminal-stripping block (`_split_items`)**
- [x] **Task 1.6 - `BiSep.from_value` classmethod**

### Batch 2 - `StandardProblem.parse` structural simplification — **COMPLETED**

- [x] **Task 2.1 - Single-pass decoupled splitting (`_split_tsplib_text`) and module decomposition into `tokenization.py`, `fields.py`, `transformers.py`, and `models.py`**

### Batch 3 - ETL failure visibility

- [ ] **Task 3.1 - Trace `process_files_parallel()` result consumption**

  + **What:** Trace where the stats dict (`successful`/`failed`/`errors`) returned by
    `ParallelProcessor.process_files_parallel()` is consumed in the CLI / `core` pipeline.
  + **Why:** Workers log and record failures, but if the caller never surfaces the `errors` list
    or exits non-zero, a failed batch looks silent ("no errored batches shown").
  + **Where:** `src/converter/core/`, CLI entry points.
  + **How much:** Low (investigation only).
  + **DoD:** A written trace stating whether/where failures surface. No code change yet.

- [ ] **Task 3.2 - (conditional on 3.1) Surface failures loudly**

  + **What:** Make the CLI print the error summary and exit non-zero when any batch failed.
  + **Why:** Failures must be visible at the process boundary, not buried in a returned dict.
  + **How much:** Low.
  + **DoD:** Running the pipeline against one deliberately broken file produces a visible,
    non-zero failure.

### Batch 4 - naming collision (option A locked, D6)

- [ ] **Task 4.1 - Rename converter class `DataTransformer` -> `ProblemNormalizer` (class only)**

  + **What:** Rename the class in `src/converter/core/transformer.py`; update all references and
    imports; keep the module filename.
  + **Why:** `models.Transformer` (format parser) vs `converter ... transformer.py::DataTransformer`
    (ETL reshape) name collision is confusing; class-only rename is the smallest ripple.
  + **Where:** `src/converter/core/transformer.py` + referencing modules/tests.
  + **How much:** Low/Medium.
  + **DoD:** Zero old-name references in `src/` and `tests/`; converter suite behaves as before
    (excluding the 14 pre-existing v1 failures).

### Batch 5 - documentation — **COMPLETED**

- [x] **Task 5.1 - Comment near `FileMeta`**
- [x] **Task 5.2 - `src/tsplib_parser/README.md` with 3-layer architecture and mermaid diagrams**

## Verification commands

```bash
uv run python -m pytest tests/test_format -q        # 63 passed / 1 skipped
~/.local/bin/ruff check src/tsplib_parser            # changed files
uv run converter process -i datasets_raw/problems -o <tmp>   # corpus run when a task touches parsing
```

## Deferred / parked

- Full corpus regression-harness automation.
- Anything new that surfaces during the walk - propose it, don't assume it.

| ID | Severity | Problem | Type | Where | Cause / Why | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | Blocker | Rerun on existing DB silently no-ops: duplicate key → batch rollback, stale row kept, exit 0, JSON rewritten anyway → DB/JSON diverge | Data integrity / workflow | `operations.py:292` (`_insert_hub`), UNIQUE `:109`, batch `:434-519`, caller `commands.py:161`, update branch `commands.py:120-135` | Plain `INSERT`, no upsert; constraint error swallowed → rollback; CLI prints success + exit 0 | Root: S3 non-idempotent writes; update path; G6 false-confidence test |
| B2 | Blocker | All 4 CI gates red: 14 tests fail, 256 ruff, black reformats everything, 16 mypy | Process / verification | `tests/**`, `pyproject.toml:75`, `ci.yml`, `src/**` | v2 schema landed in `src` only, tests still assert v1 `nodes`/`insert_nodes`; black hardcodes 4-space vs project 2-space → gate can never pass; mypy errors unfixed | S1 half-landed migration; m21 dual config/formatter |
| B3 | Blocker | One bad row kills whole batch; payload without `problem_data` vanishes uncounted (returns 0/0) | Failure isolation / data integrity | `operations.py:434-570`, silent skip `:473` | One transaction per batch, no per-row savepoint; skip path logs nothing, counts nothing | Same root as B1; M12 (`TOUR` poisons batch) |
| M1 | Major | `analyze` crashes on any DB with HCP/SOP; `--type TOUR` guaranteed to fail | Correctness / CLI | `commands.py:313`, `:264`; `operations.py:830-831`, `:281-287` | `None` formatted with `:<15` (NULL `edge_weight_type` emitted as `CAST(NULL AS VARCHAR)`); `TOUR` offered in `Choice` but schema guard raises | M12 taxonomy drift |
| M2 | Major | JSON output: path traversal via file `NAME`, silent overwrite, thread race, JSON/DB key divergence | Security / data integrity | `json_writer.py:64,122`; `validation.py:70-71`; `commands.py:170-185`; `operations.py:573-583` | `NAME` only checked non-empty → `lucas_galdino` escapes output dir; duplicate `NAME` overwrites; concurrent threads same path; DB disambiguates by stem, JSON doesn't | Validation gap; key-policy split vs DB |
| M3 | Major | Float edge weights silently rounded to int (`1.5` → `2`) | Data integrity | `operations.py:191`; `models.py:161-176`; `transformer.py:186` | Schema `INTEGER[][]` vs parser `int \| float`; stored/read-back truncation verified | — |
| M4 | Major | Failed matrix conversion still stores problem, minus distances | Silent failure / data integrity | `transformer.py:85-98` vs `api.py:203-206` | Warn + `None` instead of re-raise; contradicts own comment "stores an unreadable problem" | S2 lenient storage |
| M5 | Major | VRP preprocessed temp files orphaned on every parse failure | Resource leak | `parser.py:142-146` (unlink on success only), temp created `:366-375` | No `try/finally`; correct pattern exists in `transformer.py` tour path — **fixed 2026-10-14** (PB3, see `src/tsplib_parser/TODO.md` §9) | G1 no tests |
| M6 | Major | `special_func` documented, accepted, dropped; `UnsupportedFeatureError` never raised | Dead feature / API lie | `parser.py:83-142`, `:790`; `models.py:831` | `StandardProblem.parse(text, **options)` never reads options; no dispatch | **Revised 2026-10-14 (P2):** XRAY parses and needs no `special_func`; the parser must record the declared weight type (parser-side, Phase C) and the converter raises `UnsupportedFeatureError` for `SPECIAL` without a callable — done (`CV2` in `src/converter/TODO.md`) |
| M7 | Major | `is_symmetric` guessed from format names, can be false | Data integrity | `parser.py:727-753` | Only `ATSP` + 4 formats return `False`; asymmetric `FULL_MATRIX` TSP recorded symmetric; `TYPE : ATSP (author)` bypasses string check | — |
| M8 | Major | CVRP customer-only matrices get fabricated zeroed depot row | Data integrity | `transformer.py:238-262` | Deliberate decision #5; `0.0` is not a distance → garbage depot legs | Accepted compromise, unmarked |
| M9 | Major | `errors="latin-1"` is not a codec error handler → tour files silently dropped | Silent failure / correctness | `transformer.py:423` | `LookupError: unknown error handler` → broad except → `None` → tour absent | G2 untested path |
| M10 | Major | `SimpleConverter.to_json(data, "problem.json")` crashes | Correctness / public API | `api.py:65` | `os.makedirs(os.path.dirname(...))` → `makedirs("")` → `FileNotFoundError` | — |
| M11 | Major | `converter validate` validates nothing | UX / docs | `commands.py:228-258`; `verify_database.py` | Body prints stats; docstring promises schema/integrity checks; command can never fail | Real checks exist but unwired (G8) |
| M12 | Major | Problem-type taxonomy copied 5+ times, already drifted | Architecture / SSOT | `operations.py:105,200-206,212-218,281-287`; `validation.py:88`; `scanner.py:150-157`; `commands.py:264`; `__init__.py:8-14` | No single enum/registry; `TOUR` accepted by CLI/docs, rejected by schema | Root for B3 (`TOUR`) + M1 |
| m1 | Minor | `--batch-size` no-op | CLI / UX | `parallel.py:44`; `commands.py:140` | Stored, never read; scanner batching never triggers | — |
| m2 | Minor | `--workers 0` crashes | Correctness | `commands.py:138-146` | No validation; `ProcessPoolExecutor(0)` ValueError | — |
| m3 | Minor | Docstring sells connection pooling / backpressure / memory limit — none enforced | Docs / behavior | `parallel.py:22-31`, `:148-157` | `memory_limit_mb` unused; sequential mode still pays executor indirection | — |
| m4 | Minor | Dead-API archipelago (~800 lines uncalled) | Maintainability | `cost.py:148`; `transformer.py:339-552,280-333`; `config.py`; `update.py:37,138,223,249`; `parallel.py:240,255`; `parquet_writer.py:131-168`; `conftest.py:76-84` | Written + documented, never wired; stale v1 asserts | S4 feature sprawl |
| m5 | Minor | Public validator crashes instead of returning errors | Correctness | `validation.py:81` | `.upper()` on `None`/non-str → `AttributeError` | — |
| m6 | Minor | `if "VRP" in t` substring match | Correctness | `operations.py:285` | `"VRPTSP"`-style types silently land in `cvrp_problems` | M12 |
| m7 | Minor | `load()` normalizes type, `load_matrix()` doesn't | API inconsistency | `operations.py:637-658` vs `:660-685` | `"VRP"` lookups fail in one path | M12 |
| m8 | Minor | `.sol` parse maps depot `0` → node `-1` silently; cost regex misses negatives/scientific notation | Data integrity | `transformer.py:496-529` | `([\d.]+)` pattern; depot mapping undocumented | G2 |
| m9 | Minor | Two policies for display coords; sparse `node_id`s misalign silently | Data integrity | `transformer.py:148-160` vs `:122-146`; `validation.py` | `_build_display_coords` compresses missing entries; validation checks counts only | — |
| m10 | Minor | Scanner order = filesystem order; no dedupe; `stat()` races deletion | Reproducibility / workflow | `scanner.py:63,110,138-141` | Unsorted `rglob`; `problem_id` differs per machine | — |
| m11 | Minor | CLI heuristically re-scans `cvrplib` sibling; root containing `cvrplib`/`all_problems` double-lists files | Workflow | `commands.py:99-111` | String-match MDVRP filter + extra scan root → duplicate input | Feeds B1/B3 rollback |
| m12 | Minor | `config.yaml` write-only | Config | `commands.py:329-373`; `load_config` 0 callers | `init` emits, nothing reads; `database_path` ignored; `log_file` never wired | S4 |
| m13 | Minor | Version drift ×4 | Docs / API | `pyproject.toml` 0.1.0; `converter.__version__` 1.0.0; `tsplib_parser.__version__` 2.0.0; `commands.py:22` "0.1.0" | Hardcoded `version_option` | S5 |
| m14 | Minor | Stale examples/docstrings (`nodes` key, `nodes.parquet`, "Step 5" w/o Step 4, unused `output_dir`) | Docs | `api.py:262-268`; `parquet_writer` docstring; `worker_functions.py:70`; `cordeau_parser.py:249` | Retired v1 shapes still documented | S1 |
| m15 | Minor | Parser nits: `# EXPLAIN:` in parse loop; `self.func.__name__` AttributeError for `partial`; `MapT` dup keys last-wins; extra `EDGE_LIST` tokens ignored; `#` lines in sections hard-fail | Correctness / robustness | `models.py:860,142,832-905` | — | — |
| m16 | Minor | Cordeau: time-window errors swallowed; extra node lines sliced away; MDVRP flattened to `CVRP`, per-depot `Q`/`D` dropped | Data integrity | `cordeau_parser.py:306-307,69-87`; `cordeau_converter.py:123,151` | RESOLVED: FormatError inheritance, CordeauProblem(Problem), to_tsplib lossless LKH mode with DEPOT_CAPACITY/DEPOT_DURATION sections | Closed |
| m17 | Minor | f-string SQL in Parquet export (`COPY` interpolation, template+`replace`) | Security (bounded) | `parquet_writer.py:112-114,150-152,219` | Low exploitability (CLI validates), but contradicts parameterized discipline | — |
| m18 | Minor | `_calculate_checksum` returns `""` on error — indistinguishable from "changed" | Failure point | `update.py:126-131` | Transient read failure → reprocess loop | Feeds B1 |
| m19 | Minor | `update_file_tracking` reimplements upsert (TOCTOU window) | Workflow / correctness | `operations.py:713-760` vs upsert at `:609` | Check-then-insert duplicates logic | — |
| m20 | Minor | Unused runtime deps: `pandas` 0 imports, `ruff` as runtime dep, `pyyaml` reachable only via dead config | Dependencies | `pyproject.toml:20-31` | Liability with no consumer | m4, m12 |
| m21 | Minor | Dual pytest config; black vs ruff-format contradiction | Tooling | `pytest.ini` vs dead `[tool.pytest.ini_options]`; `pyproject.toml:75` | `pytest.ini` wins; two formatters, one infeasible | Root for B2 |
| m22 | Minor | Whole-corpus results held in memory before single batch insert | Performance / memory | `worker_functions.py:70-90`; `parallel.py:122,181`; `commands.py:151-161` | Matrices pickled + retained; peak ≈ Σ matrix sizes | Interacts with B1/B3 fix |
| n1 | Nit | Stale "circular imports" rationale | Docs | `tsplib_parser/__init__.py:64-66` | No cycle exists; `parser.py` never imports package `__init__` | — |
| n2 | Nit | 308-line exceptions module, 44% covered, ~200 lines docstring | Docs | `converter/utils/exceptions.py` | Docstring cosplay for 6 classes | m4 |
| n3 | Nit | 2-space/120-col style vs CI black defaults | Style / tooling | repo-wide | Pick one universe | m21 |
| n4 | Nit | Commit message `some changes, don't even know` | Process | git `0e04050` | Reviewability of history | — |
| n5 | Nit | Reviewer bookmark comment left in hot path | Maintainability | `models.py:860` | Question answered 20 lines later | — |
| S1 | Systemic | Migration half-landed: v2 in `src`, absent in tests/docs/CLI | Root cause | `src` vs `tests/**`, docstrings, `commands.py:264` | Generates B2, B3 (`TOUR`), M1, m14 | — |
| S2 | Systemic | Two error philosophies colliding: strict parser vs lenient storage | Root cause | `models.py:831-905` vs `transformer.py`, `commands.py` | Garbage in, success reported | — |
| S3 | Systemic | Non-idempotent writes vs re-run-centric operations | Root cause | only upsert = `operations.py:609`; rest insert-only | Contradicts `--force`/incremental model | B1, B3 |
| S4 | Systemic | Feature sprawl ahead of wiring | Root cause | `cost.py`, solution ingestion, backup, progress, config, `special_func` | Dead code that looks alive; docs describe intended behavior | m4, M6, M11 |
| S5 | Systemic | SSOT violations | Root cause | type ×5, version ×4, pytest config ×2, formatter ×2, DB path ×2 | Drift is already fact, not a risk | M12, m13, m21, B2 |
| G1 | Gap | VRP preprocessing entirely untested (UTF-8→latin-1 fallback, section skips, multi-dim demands, `CAPACITY_VOL/WEIGHT`, temp files) | Coverage | `parser.py:233-373` | 0 tests; proven leak M5 | M5 |
| G2 | Gap | Solution discovery / `.opt.tour` / `.sol` / cost extraction: 0 tests, 0 callers | Coverage | `transformer.py:339-552` | Contains broken latin-1 path | M9, m4, m8 |
| G3 | Gap | `cost.py` and `config.py` 0% covered | Coverage | `cost.py`, `config.py` | Dead modules | m4, m12 |
| G4 | Gap | `parquet_writer` 16%; `export-parquet` and `init` commands untested | Coverage | `parquet_writer.py`; `commands.py:433-481,329-373` | — | m17 |
| G5 | Gap | `update.py` modified-file branch, backup, candidate scan untested | Coverage | `update.py:86-106,149-170,260-273` | Exactly the branch B1 breaks | B1, m18 |
| G6 | Gap | Force/re-insert path test asserts log substring, not DB state | Coverage | `tests/test_integration/test_cli.py:181-201`; `operations.py:665-681` | False confidence; test that would have caught B1 | B1 |
| G7 | Gap | No tests for: duplicate/name-collision JSON, `NAME` traversal, concurrent writes, `analyze` NULL `edge_weight_type`, `--types TOUR`, rollback accounting, `WORKERS=0` | Coverage | `tests/**` | — | M1, M2, B3, m2 |
| G8 | Gap | `in_memory_db` fixture unused + broken; `verify_database.py` not collected; `validate` a stub | Coverage | `tests/conftest.py:76-84`; `verify_database.py`; `commands.py:228` | Open-per-call `:memory:` = fresh empty DB each time | M11 |
| F1 | Fixed | `FuncT` identity lambda incompatible with `T` (mypy strict) | Type safety | `models.py:131` | `func or (lambda x: x)` returns `str` vs `T`; fixed with `cast("Callable[[str], T]", ...)` + `cast` import | Resolved |
| F2 | Fixed | `requires-python = ">=3.10"` vs PEP 695 syntax (3.12+ only) | Tooling / metadata | `pyproject.toml:10` (+classifier `:21`); `ci.yml:14`; `README.md:27,63`; `docs/README.md:125`; `docs/guides/USER_GUIDE.md:78`; `docs/reference/CONTRIBUTING.md:535` | Metadata claimed 3.10/3.11 support; file can't parse there; bumped to `>=3.12` + CI matrix/docs ripples | Resolved |
