# TODO — `tsplib_parser`

_Open problems in `src/tsplib_parser/**` only: what is broken, what breaks this repo's own patterns, and what breaks general best practice. Converter-side items (ETL, database, CLI, JSON writer) are tracked in [`../../TODO.md`](../../TODO.md); distance computation and `SPECIAL` dispatch are tracked in [`../converter/TODO.md`](../converter/TODO.md). Both are out of scope here._

_Last reviewed: 2026-10-14 — package re-read, 239-file corpus run, broken-class pass implemented and verified (`tests/test_format`)._

---

## 1. Blocker scope — where B1–B3 from `../../TODO.md:185-189` land

| Blocker | Lands in `tsplib_parser`? | Why / parser-side involvement | How verified |
| --- | --- | --- | --- |
| **B1** — rerun on an existing DB silently no-ops (duplicate key → batch rollback, stale row kept, exit 0) | **No** — owned by `src/converter/database/operations.py` (`_insert_hub` + batch insert) | The parser never writes anything and is deterministic. It does, however, pass the file's `NAME` through verbatim, so two distinct files sharing a `NAME` produce the same hub key. Parser output can _feed_ the collision; it does not cause it. | Converter side not re-verified here (out of scope). Parser side: parsing the corpus twice gives identical results. |
| **B2** — all four CI gates red | **Mostly no** — the 14 failing tests, 256 ruff errors and 16 mypy errors live in `tests/**` and `src/converter/**`. **One slice is here:** the skipped test `tests/test_format/test_matrix_equivalence.py:257` (stale reason: "needs `_create_explicit_matrix()`", which now exists). Also the documented run command in `../../TODO.md` (`uv run python -m pytest tests/test_format -q`) fails locally unless `PYTHONPATH=src` is set or the package is installed. | `tests/test_format` is the one gate that is actually green: **63 passed, 1 skipped**. | Ran the suite. |
| **B3** — one bad row kills the whole batch; payloads without `problem_data` vanish uncounted | **No** — owned by the batch transaction in `operations.py`. **But the parser supplies a concrete trigger:** it emits problem `TYPE` values the downstream schema rejects — `TOUR` (41 of the 239 corpus files) and the concatenated VRP-variant labels `MC-VRP` / `TW-VRP` / `PD-VRP` / `MCTW-VRP`, etc. (see **PB4**). Any such row poisons a batch. | 41 TOUR + 16 CVRP files in the corpus; the type guard in `operations.py:281-287` rejects `TOUR`. | Corpus run + code read. |

**Conclusion.** No blocker actually _lives_ in `tsplib_parser`. B1 and B3 are converter-owned; B2 touches this package only through one stale skipped test and one stale run command. The parser's real contribution to that failure chain is the **problem-type vocabulary it emits** — values that are neither in the TSPLIB95 spec nor in its own validation set (PB4), which is what pushes a rerun into B1/B3 territory.

---

## 2. What was verified (evidence, not assertion)

```bash
# unit gate for this package
uv run pytest tests/test_format -q     # 63 passed, 1 skipped (before the contract tests)

# full corpus through the public entry point (FormatParser.parse_file)
PYTHONPATH=src uv run python - <<'EOF'
from pathlib import Path
from tsplib_parser.parser import FormatParser
parser = FormatParser()
for f in sorted(p for p in Path("datasets_raw/problems").rglob("*") if p.is_file()):
    parser.parse_file(f)
EOF
```

```text
TOTAL_FILES = 239      FAIL_COUNT = 0
.tsp  113 → TSP        .sop 41 → SOP        .tour 41 → TOUR
.atsp  19 → ATSP       .vrp 16 → CVRP       .hcp   9 → HCP
EDGE_WEIGHT_TYPE: EUC_2D 91 | EXPLICIT 80 | GEO 10 | CEIL_2D 4 | ATT 2 | XRAY1 1 | XRAY2 1 | SPECIAL 0
```

**"Parses without raising" is not "parses correctly."** Outstanding gaps:

- Only matrices have numeric equivalence and value-access tests. No tests assert parsed coordinate or metadata values for TSP/SOP/HCP/ATSP/TOUR.
- Some emitted metadata is unreliable (e.g. `is_symmetric`, see **PB2**).
- Full 239-file corpus run is not yet automated as a CI regression gate (**PC7**).

### 2.1 Reference-implementation deep dive (2026-10-13)

Evidence from `rhgrant10/tsplib95` (v0.7.1, Apache-2.0) and `ben-hudson/pylkh` (v2.0.0, DBAD — study only):

| Question | `rhgrant10/tsplib95` | `ben-hudson/pylkh` |
| --- | --- | --- |
| TYPE handling | Kept verbatim as string; no registry or normalization | Inherits string; adds fields via thin `LKHProblem(StandardProblem)` subclass |
| `SPECIAL` | Supported via caller callback `special=`, single dispatch in `_create_wfunc` | None |
| XRAY1/XRAY2 | Implemented in pure python (`distances.xray` with speed parameters `sx, sy, sz`); Fortran `deq.f`/`duneq.f` are archival only | None |
| Distance dispatch | Dict registry `distances.TYPES` + `partial` variants; `matrix.TYPES` for EXPLICIT | Extends `distances.TYPES` |
| Symmetry | Declared, not measured: `not is_full_matrix() and not is_special()` | Inherits |
| Extension as type signal | No | No |
| Errors / bulk behavior | Raises `TsplibError` hierarchy; CLI continues per file | Bare `NoToursException`, `assert`, `warnings.warn` |

**XRAY1/XRAY2 implementation note:** the converter implements the formula (pure python 3-D `DEQ`/`DUN`: axis differences, x wrapped at 360°, per-axis motor speeds `1.25/1.5/1.15` for XRAY2, `×100` rounding). Verified 2026-10-14 against a compiled `gfortran` oracle of the distribution's own routines — see [`../converter/TODO.md`](../converter/TODO.md) (`CV1`, done). The parser records the declared weight type and never rejects a parseable problem for a missing cost function (**P2** revised).

---

## 3. Broken — does not work, or works while being silently wrong

_Status: All PB items are FIXED and verified against the 239-file corpus and unit contract suites._

| ID | Status | Problem | Where | Why it matters | Resolution |
| --- | --- | --- | --- | --- | --- |
| **PB1** | **FIXED** | `special_func` is accepted and then dropped. | `parser.py`, `cost.py` | Silent wrong data. | Removed dead parameter; converter dispatches via `cost.py` (`CV1`/`CV2`). |
| **PB2** | **FIXED** | `is_symmetric` is guessed from format names instead of measured. | `validation.py`, `parser.py` | Asymmetric matrices incorrectly flagged. | Measured for EXPLICIT matrices; tri-state `bool \| None`; type-normalized. |
| **PB3** | **FIXED** | The VRP preprocessing temp file leaks on every failure. | `parser.py` | Resource leak. | Replaced disk temp files with pure in-memory stream processing (`Task C1`). |
| **PB4** | **FIXED** | Problem-type vocabulary drifts (`MC-VRP`). | `types.py`, `parser.py` | Triggered B3 batch rollbacks. | Single source of truth in `types.py`; base `TYPE` emitted; extended types via `LKHProblem`. |
| **PB5** | **FIXED** | `#` comment inside data section hard-fails file. | `tokenization.py` | Robustness gap. | `_split_tsplib_text` skips comments and blank lines everywhere. |
| **PB6** | **FIXED** | Legacy base `Problem.parse()` LSP violation / leniency trap. | `models.py` | Silent data loss; LSP violation. | Removed `parse()` from `Problem` (Option 1). Parsing belongs to `StandardProblem`/`FormatParser`. |
| **PB7** | **FIXED** | `FuncT.parse` error raises `AttributeError` on callables without `__name__`. | `transformers.py` | Masks real errors. | Uses `getattr(func, "__name__", type(func).__name__)`. |
| **PB8** | **FIXED** | `MapT` silently overwrites duplicate keys. | `transformers.py` | Silent row dropping. | Duplicates detected, counted, and raised as `ParseError`. |
| **PB9** | **FIXED** | Decorative no-op validation hooks. | `fields.py`, `validation.py` | False confidence. | Removed no-op `validate()` hooks; unified in `validate_problem_data`. |
| **PB10** | **FIXED** | Spec-compliant `EDGE_WEIGHT_FORMAT : FUNCTION` rejected. | `validation.py` | Rejects valid files. | Accepted and handled; no matrix section required. |
| **PB11** | **FIXED** | Unhandled sections dropped silently. | `parser.py`, `models.py` | Section loss. | Stripped sections recorded in `stripped_sections`; extended sections registered in `LKHProblem`. |
| **PB12** | **FIXED** | `EDGE_DATA_FORMAT` ignored; colon-less `ADJ_LIST` dropped. | `transformers.py`, `fields.py` | Data loss on graph problems. | `EdgeDataT` and `EdgeDataField` honor declared format and sniff colon-less ADJ_LIST. |
| **PB13** | **FIXED** | `DISPLAY_DATA_SECTION` dropped for coordinate-less files. | `parser.py` | Dropped display data. | Extracted into parsed dictionary and validated. |
| **PB14** | **FIXED** | Pre-existing ruff debt in test modules. | `tests/tsplib_parser/` | Dilutes lint signals. | Formatted, type-annotated, 100% ruff-clean. |

---

## 4. Pattern Issues Register

| ID | Status | Problem | Where | Why it matters | Resolution / Action |
| --- | --- | --- | --- | --- | --- |
| **PP1** | **FIXED** | `models.py` is a ~1,034-line grab-bag. | `models.py` | Monolithic coupling. | Decomposed into `transformers.py`, `fields.py`, `tokenization.py`, `models.py`. |
| **PP2** | **FIXED** | Stale package documentation. | `__init__.py` | Misleads users about imports. | Re-exported `FormatParser` cleanly from `__init__.py` with accurate docstrings. |
| **PP3** | **OPEN** | `TransformerField.__init__` calls `self.__class__.build_transformer()`. | `fields.py:64` | Subclass classmethod called in base `__init__`. | Convert to cached lazy property on `TransformerField`. |
| **PP4** | **OPEN** | `Field.__init__(keyword, **options)` with `setattr` fan-out. | `fields.py:31` | Silent typos in options. | Declare explicit constructor arguments. |
| **PP5** | **FIXED** | `Problem.__getattribute__` intercepts every attribute access. | `models.py` | Sits on hot path. | Implemented non-data descriptor `Field.__get__`; removed `__getattribute__`. |
| **PP6** | **FIXED** | Cordeau island bypasses exception contract and flattens MDVRP. | `cordeau/` | Bypasses `FormatError` and loses per-depot capacities. | `CordeauParseError(FormatError)`, `CordeauProblem(Problem)`, lossless `to_tsplib(as_lkh=True)` with `DEPOT_CAPACITY_SECTION` and `DEPOT_DURATION_SECTION`. |
| **PP7** | **FIXED** | Stale skip in matrix equivalence test. | `tests/tsplib_parser/` | Hides test coverage. | Un-skipped and verified green. |
| **PP8** | **FIXED** | Reviewer bookmark comment left in parse loop. | `models.py` | Noise in code. | Deleted. |
| **PP9** | **FIXED** | Private `_TemporaryFileWrapper` import. | `parser.py` | Private stdlib import. | Deleted; tempfiles eliminated. |
| **PP10** | **FIXED** | Absolute import `from tsplib_parser.matrix import Matrix`. | `parser.py` | Breaks relative import convention. | Replaced with relative import. |

---

## 5. Practice & Code Quality Register

| ID | Status | Problem | Where | Why it matters | Resolution / Action |
| --- | --- | --- | --- | --- | --- |
| **PC1** | **OPEN** | Parse result is untyped `dict[str, Any]`. | `parser.py:83` | Consumers re-guess keys. | Introduce `TypedDict` (`ParseResult`, `ProblemData`, `Node`). |
| **PC2** | **OPEN** | Descriptor typing at boundary leaks `Any`. | `fields.py` | Static typing incomplete. | Type descriptor protocol with overloads (`instance: None -> Self`). |
| **PC3** | **FIXED** | Broad `except Exception` collapses bugs and data errors. | `transformers.py` | Masks genuine bugs. | Narrowed to `(ValueError, TypeError)`. |
| **PC4** | **OPEN** | Module-global mutable cache `_INT_SUM_MEMO`. | `matrix.py:18` | Unbounded growth. | Use `functools.lru_cache` or explicit reset helper. |
| **PC5** | **FIXED** | Missing `__all__` in modules. | Package-wide | Unclear public API. | Explicit `__all__` defined across all modules. |
| **PC6** | **FIXED** | `detect_special_distance_type` substring sniffing. | `parser.py` | False positives on comments. | Replaced with declared keyword parsing. |
| **PC7** | **FIXED** | Untested behavior / missing corpus gate. | `tests/tsplib_parser/` | Silent regression risk. | 239-file sweep automated in `test_unit_parser_validation.py`. |
| **PC8** | **FIXED** | Magic-string vocabularies duplicated across modules. | `types.py` | Inconsistency and drift. | Centralized in `types.py`. |
| **PC9** | **OPEN** | Dangling documentation links in knowledge base. | `docs/**` | Broken documentation links. | Repoint to new modules and `src/tsplib_parser/README.md`. |
| **PC10** | **FIXED** | `SECTION_GRAMMARS` only half-consumed. | `types.py`, `validation.py` | Spec duplication. | Validator derives dimension invariants from `SECTION_GRAMMARS`. |
| **PC11** | **OPEN** | Inconsistent finding register row shapes across TODOs. | Repository-wide | Hard to cross-reference. | Standardize table schema across all TODO documents. |

---

## 6. Execution plan

_Re-planned 2026-10-14, after the broken-class pass. Supersedes the previous flat list, which still had the finished PB3 in it and did not know about R1–R6, P10 or P11._

**Guardrail for every phase:** the corpus stays green — 239 files, 0 failures through `FormatParser.parse_file`, plus `tests/test_format` passing. Anything that turns a corpus file from pass into fail needs an explicit decision first.

> **P2 vs P11 — resolved 2026-10-14.** Evidence that made the conflict visible: [`datasets_raw/problems`](../../datasets_raw/problems) holds **2 XRAY files** (`XRAY1 1 | XRAY2 1`) and **0 `SPECIAL`** files, and all 239 parse today — so “raise per file” for XRAY would have broken the gate, while P11 puts those files in scope. Decision (**P2** revised): every problem whose structure parses is parsed; the cost function lives in the converter, and until it exists it is tracked and linked from the parse result. Only structurally unparsable files raise (**P1**).

### Phase A — foundations (no behavior change)

1. Add `types.py`: a core `ProblemType` vocabulary (`TSP`, `ATSP`, `SOP`, `HCP`, `CVRP`, `TOUR`), the accepted-but-normalized aliases, the extension→type hints, and the `EDGE_WEIGHT_*` vocabularies — one source of truth for parser, validator and database (fixes **PC8**, feeds **PB4** and **P4**). **Done 2026-10-15** for `ProblemType`, the aliases, the extension hints and `EDGE_WEIGHT_TYPES`; the validator now reads `VALID_PROBLEM_TYPES` instead of its own set.
2. Declare the per-line grammar of every data section (`SECTION_GRAMMARS`, spec §1.2) and derive the section type/value tests from it (`tests/test_format/test_section_grammars.py`). **Done 2026-10-15** — it found **PB12** and **PB13**. The table now also has a production reader: `validation.py` derives `NODE_COORD_DIMENSIONS` and `DISPLAY_DATA_DIMENSIONS` from it instead of hardcoding `{2, 3}`, so the spec fact of §1.2 is declared once and read by the validator _and_ the tests (`EXTENSION_TYPE_HINTS` stays unconsumed until **P4** is implemented — staged, not dead).
3. Adopt the parse-result contract (**P10**): `ParseResult` / `ProblemData` / `Node` / `Metadata` `TypedDict`s in the signature (**PC1**).
4. Logging contract (**P7**): module logger only; every record carries the file path and the location inside the file; no file handler inside the library.
5. **PC10** — decide the section-grammar table's role: (a) parser consumes `columns`/`terminator_lines` as a strict section check, or (b) the table stays the spec of record and the validator grows into it. Prerequisite for either: the corpus gate as a test (**PC7**), because (a) can reject files that parse today.

### Phase B — core parsing correctness (scope per P11)

1. **R6** — `FormatParser` dispatches to a problem class instead of hardcoding `StandardProblem`; prerequisite for **P6** and for every non-core format.
2. **R2** — the coordinate rule reads the field's declared `dimensions` again, so `display_data` is 2-D-only and a new field declares its own shape (**R1** keeps the declaration as the field's own contract). **Partly done 2026-10-15:** the 2-D-only display rule is back and both rules now read the allowed dimensions from `types.SECTION_GRAMMARS` (`DISPLAY_DATA_DIMENSIONS` = `{2}`, `NODE_COORD_DIMENSIONS` = `{2, 3}`) rather than a hardcoded literal. What is _not_ done is reading the `Field` descriptor's own `dimensions` declaration — the spec fact is single-sourced in the grammar table instead, which is what **PC8** asks for.
3. **PB2 + P5** — symmetry: type-first defaults, measured for `FULL_MATRIX`, tri-state `is_symmetric: bool | None`, `TYPE` normalized before comparison (**P4** step 4).

### Phase C — vocabulary and fail-fast

1. **PB4** — emit the base `TYPE` plus variant metadata fields; stop emitting invented compound labels (`MC-VRP`…) that trigger B3 batch rollbacks; one validated vocabulary (**PC8**).
2. **PB1 + P3 + PC6** — remove the dead `special_func` parameter; record the declared weight type and, when the cost function is not implemented (`XRAY1`, `XRAY2`, `SPECIAL`), track and link it instead of fabricating a `weight_source` label with no distances behind it; replace the substring sniff with the parsed `EDGE_WEIGHT_TYPE` (**P2** as revised).

### Phase D — structure (behavior-preserving)

1. **PP1** — split `models.py` (~940 lines) into `utils` / `transformers` / `fields` / `models`; then **R5** — extract the four responsibilities of `StandardProblem.parse` into per-kind handlers; while inside the file: **PP3**, **PP4**, **PP5**, **PP8**, **PC5** (`__all__`).
2. **PP2** — correct the `__init__.py` documentation; **PC9** — repoint the dangling knowledge-base links; **PP9/PP10** — import hygiene in `parser.py`.

### Phase E — verification

 1. **PC7** — corpus gate as a test/marker, boundary cases, parsed coordinate/metadata value assertions; **PP7** — un-skip the matrix equivalence test.

**Outside this package, in dependency order:** [`CV1`/`CV2`](../converter/TODO.md) (XRAY distance functions, `SPECIAL` dispatch) and the repo-wide ETL/DB blockers B1/B3 in [`../../TODO.md`](../../TODO.md). Cordeau stays isolated (**PP6**, decision D4).

---

## 7. Decisions and policy (recorded 2026-10-13)

**Policy:** Files that cannot be parsed correctly must **raise** (`UnsupportedFeatureError` / `ParseError`). Bulk execution must **continue** with remaining files. No silent drops, no silent defaults, no fabricated values.

| # | Decision | Detail | Status |
| --- | --- | --- | --- |
| **P1** | Raise and continue | Parser raises per file; caller isolates failures and continues bulk run. | Accepted |
| **P2** | XRAY1/XRAY2, and any weight type whose cost function is not implemented | **Parsed, never rejected.** The parser records the declared `EDGE_WEIGHT_TYPE` and leaves the arithmetic to the converter ([`CV1`](../converter/TODO.md)); while a cost function does not exist yet it is _tracked and linked_ from the parse result instead of silently producing no distances or failing the file. | **Revised (user, 2026-10-14)** — the earlier “raise per file” text was wrong |
| **P3** | SPECIAL | Parser removes dead `special_func` parameter and raises `UnsupportedFeatureError`. Dispatch hook implemented in converter ([`CV2`](../converter/TODO.md)). | Accepted |
| **P4** | TYPE detection | Four steps: (1) file extension as hint; (2) regex on `TYPE` value matched against allowed keywords; (3) log TYPE/extension disagreements; (4) `FULL_MATRIX` symmetry comparison as final check. | Accepted |
| **P5** | Symmetry | Type-first: ATSP/SOP asymmetric, TSP/HCP/CVRP symmetric; compute explicitly for `FULL_MATRIX`; triangular formats symmetric by construction; log mismatches to console and file (**P7**). | Accepted |
| **P6** | Type vocabulary / LKH-3 | Keep base TSPLIB `TYPE` + separate variant metadata fields. `StandardProblem` stays core TSPLIB95; future LKH-3 formats use a thin subclass (similar to `pylkh`), not separate classes per family. | Accepted |
| **P7** | Logging | Warnings and errors carry the file path and the location inside it. Decided 2026-10-14: the **library only emits records** (module logger); the **CLI owns the run log** at `log/run-<timestamp>.log` plus the console handler, and never aborts a bulk run. | Accepted (CLI side pending) |
| **P8** | Reference implementations | Study `rhgrant10/tsplib95` and `ben-hudson/pylkh` for design patterns, but implement cleanly from TSPLIB95 spec (respect licensing). | Done (§2.1) |
| **P9** | Implementation order | Broken-class items first (PB3, PB5–PB11 — done 2026-10-14), then re-plan the remainder (foundations `types.py`, type detection, symmetry, converter). | Accepted |
| **P10** | Parse-result contract | Adopt a `TypedDict` (`ParseResult`, `ProblemData`, `Node`, `Metadata`) over a frozen dataclass: the payload crosses a process boundary as a plain dict and every consumer indexes it. | Accepted (user 2026-10-14; implemented in Phase A) |
| **P11** | Scope and dispatch | Current scope is the core TSPLIB95 problems in [`datasets_raw/problems`](../../datasets_raw/problems). `StandardProblem` models core TSPLIB95 only and must **raise** for extended sections — correct behavior, not a defect. `FormatParser.parse_file` must not be hardcoded to `StandardProblem`: it dispatches to a problem class, so an extended format is added by adding a class, not by editing the entry point. The strip-and-record path stays for the problem types that are not implemented yet. | Accepted (user, 2026-10-14) |

---

## 8. Related files

- Converter distance layer — XRAY1/XRAY2 implementation (`CV1`) and `SPECIAL` dispatch (`CV2`): [`../converter/TODO.md`](../converter/TODO.md)
- Architecture blueprint — module map, parse pipeline, measured result contract, extension guide, layer rules: [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) (written 2026-10-15 by an architect subagent from a codebase-explorer map at `tmp/src_exploration_report.md`)
- Repository-wide ETL work (database, CLI, JSON writer): [`../../TODO.md`](../../TODO.md)
- Parser contract tests for the 2026-10-14 pass: [`tests/test_format/test_parser_contract.py`](../../tests/test_format/test_parser_contract.py)
- Repo testing standards (folder convention): [`.github/instructions/testing_instructions.instructions.md`](../../.github/instructions/testing_instructions.instructions.md)

---

## 9. Implementation log

### 2026-10-14 — broken-class pass (PB3, PB5–PB11)

| Item | Change | Where |
| --- | --- | --- |
| **PB3** | The temporary preprocessed file is removed in `finally`, so a failed parse cannot leak it (previously the unlink ran on the success path only). | `parser.py` (`parse_file`) |
| **PB5** | Blank lines and `#` comments are skipped everywhere, including inside data sections, so a comment can never reach a field parser. | `models.py` (`StandardProblem.parse`) |
| **PB6** | The lenient duplicate parser on the base class is gone; `Problem.parse` now raises `NotImplementedError` and points at `StandardProblem.parse`. | `models.py` |
| **PB7** | `FuncT.parse` falls back to `type(func).__name__` when the callable has no `__name__` (`functools.partial`, callable instances). | `models.py` |
| **PB8** | `MapT` reports a duplicate key as a parsing error instead of silently overwriting the earlier row. | `models.py` |
| **PB9** | Removed the decorative validation hooks (`Transformer.validate`, `Field.validate`, `TransformerField.validate`, `IndexedCoordinatesField.validate`). The one real rule they carried — node coordinates are 2-D or 3-D and must not mix dimensions — moved into `validate_problem_data`, a path that actually runs. Leftovers: **R1**, **R2**. | `models.py`, `validation.py` |
| **PB10** | `EDGE_WEIGHT_FORMAT : FUNCTION` is accepted (no matrix section expected); a `FUNCTION` format no longer requires `edge_weights`. | `validation.py` |
| **PB11** | An unregistered `*_SECTION` is reported as an error instead of being dropped, and the VRP preprocessor now uses one declarative table (`_STRIPPED_SECTIONS`) that records every stripped section in `stripped_sections` and covers the real LKH-3 names (`PICKUP_AND_DELIVERY_SECTION`, `BACKHAUL_SECTION`). | `models.py`, `parser.py` |

Drive-by (typing only, no behavior change): `parser.py`'s partially-unknown diagnostics were cleared with `result: dict[str, Any]`, `constraints: list[str]`, and parameterized `depots_raw: list[Any] | int | None`.

**Runtime verification (2026-10-14):**

```bash
uv run pytest tests/test_format -q   # 81 passed, 1 skipped (before the contract tests)
```

```text
TOTAL_FILES = 239      FAIL_COUNT = 0
.tsp 113 → TSP   .sop 41 → SOP   .tour 41 → TOUR   .atsp 19 → ATSP   .vrp 16 → CVRP   .hcp 9 → HCP
```

**Environment note.** `uv run pytest` resolves `pytest` from the environment; when the first full-suite run was attempted it was not installed in `.venv`, so the system `/usr/bin/pytest` was used — the system python 3.13, whose `duckdb` import fails, which is why a full-suite run looked impossible. With pytest in the venv (2026-10-15):

```bash
uv run pytest tests -q      # 14 failed, 214 passed, 1 skipped
uv run pytest tests/test_format -q   # 102 passed, 1 skipped
```

All 14 failures are pre-existing and converter-side (json writer, cordeau, integration). Proof they do not come from this pass: extracting the `HEAD` parser with `git archive HEAD src/tsplib_parser` and running `tests/test_integration/test_pipeline.py` against it reproduces the same 5 failures.

**Tests added for this pass** — [`tests/test_format/test_parser_contract.py`](../../tests/test_format/test_parser_contract.py) (18 tests, fixtures added to [`tests/conftest.py`](../../tests/conftest.py)):

| Item | Test class | Contract asserted |
| --- | --- | --- |
| PB3 | `TestTemporaryFileIsolation` | the temp file is gone on the success path **and** on the failure path |
| PB5 | `TestCommentsInsideSections` | `#` comments before and inside sections are ignored, every coordinate intact |
| PB6 | `TestLegacyParserRemoved` | `Problem.parse` raises `NotImplementedError`; `StandardProblem.parse` unchanged |
| PB7 | `TestCallableWithoutName` | the error names `partial` instead of raising `AttributeError` |
| PB8 | `TestDuplicateKeysRejected` | a duplicate key in `DEMAND_SECTION` / `NODE_COORD_SECTION` rejects the file |
| PB9 | `TestCoordinateDimensionValidation` | mixed and 4-D coordinates reported; consistent 3-D accepted |
| PB10 | `TestFunctionEdgeWeightFormat` | synthetic `GEO`+`FUNCTION`, `EXPLICIT`+`FUNCTION` without a matrix, and both corpus files (`burma14`, `gr431`) |
| PB11 | `TestUnknownSectionReporting`, `TestStrippedSectionRecording` | an unregistered section raises; a stripped section is recorded in `stripped_sections` |

Writing the tests corrected two assumptions about the implemented behavior: `BACKHAUL_SECTION` (and `PICKUP_AND_DELIVERY_SECTION`) **are** in `_STRIPPED_SECTIONS`, so they are stripped-and-recorded rather than raised on — the raise is exercised with `REQUIRED_NODES_SECTION`; and because preprocessing runs first, the "unregistered section" error only fires for sections the preprocessor does not know.

**Still open inside this scope:** the PB11 remainder (full LKH-3 section support instead of strip-and-record, which belongs to the **P6** subclass work) and the stale skip in `tests/test_format/test_matrix_equivalence.py:257` (**PP7**).

### 2026-10-15 — code-quality pass (review findings acted on)

Requested review (`code-review-and-quality`, adversarial mode) of the XRAY cost functions, the section grammar and both test modules. Verdict: approve with nits — the XRAY port was checked against the in-repo `deq.f`/`duneq.f` reference and is faithful, the canonical-tour test is a justified golden lock (externally established by the compiled oracle, recorded in [`../converter/TODO.md`](../converter/TODO.md)), and the test files duplicate nothing of substance.

| Finding | Action taken | Where |
| --- | --- | --- |
| `SECTION_GRAMMARS` had no production reader, while `validation.py` kept its own `{2, 3}` — the very duplication (**PC8**) the table exists to kill. | `NODE_COORD_DIMENSIONS` / `DISPLAY_DATA_DIMENSIONS` are now derived from the table and used by the validator; the display rule (**R2**) is enforced again. | `types.py`, `validation.py` |
| The "legal type, no implementation" branch in the converter's distance lookup is unreachable today; a reviewer read it as dead code propped up by a private-dict test. | **Kept, deliberately**, with an in-code comment: the vocabulary is the spec's and grows independently of the registry, so the branch is the **P2** contract (report the gap; never a silent `None`, never a malformed-file error). The registry patch in the test is the only seam that reaches it today. | `../converter/utils/cost.py` (CV2) |
| `special=` was silently ignored when the declared type was not `SPECIAL` — the same shape as the removed `special_func` (**PB1**). | Now raises `ValueError`: a caller/config mismatch, distinct from `UnsupportedFeatureError` (a data limitation), and covered by a new test. | `../converter/utils/cost.py`, `tests/test_converter/test_cost.py` |
| The four causes of a `None` cost were undocumented; a coordinates-without-`EDGE_WEIGHT_TYPE` file would have returned `None` like an unweighted problem. | All four causes are documented; the fourth is a broken file, so `validate_problem_data` now reports it (`TSP requires EDGE_WEIGHT_TYPE`, enforced for TSP/ATSP/SOP/CVRP only — 0 of the 239 corpus files are affected; HCP and TOUR legitimately omit the keyword, 9 + 41 files). | `../converter/utils/cost.py`, `validation.py` |
| Test nits: a `WHAT` naming a file the test does not read, a variant covered by a file that never selects it, a body helper whose docstring claimed comment handling it did not do, and a matrix assertion weaker than its own rationale. | All four fixed: the display test states it uses a fixture, `THREED_COORDS` gets a synthetic fixture (no corpus file declares `NODE_COORD_TYPE`), `_section_body` skips `#` lines, and the matrix test compares the whole `matrix.numbers` stream. | `tests/test_format/test_section_grammars.py` |
| Pre-existing lint debt surfaced by a directory-wide check. | Registered as **PB14**. | `tests/test_format/test_matrix_*.py` |

**Verification after this pass:**

```bash
uv run pytest tests/test_format tests/test_converter/test_cost.py -q   # 118 passed, 1 skipped
uv run pytest tests -q                                                # 14 failed, 251 passed, 1 skipped (same 14 pre-existing)
uv run --with ruff ruff check <touched files>                          # clean
uv run --with mypy mypy types.py validation.py cost.py                 # clean
```

```text
TOTAL_FILES = 239      FAIL_COUNT = 0
```

### 2026-10-15 — architecture pass (explorer + architect subagents)

**What the earlier review actually covered** (asked explicitly, so it is on the record): the adversarial `code-review-and-quality` pass read exactly four artifacts — `src/converter/utils/cost.py` (XRAY pair functions, `_coordinate_function`, `supported_weight_types`, the `special=` contract), `src/tsplib_parser/types.py` (vocabularies + `SECTION_GRAMMARS`), `tests/test_converter/test_cost.py` (15 tests) and `tests/test_format/test_section_grammars.py` (21 tests) — across correctness, readability, architecture placement, dead code and over-engineering. It did **not** read `parser.py`, `models.py`, the converter ETL or the DB schema, and it did not run the suite (its verdict was approve-with-nits; every finding was answered in the previous log entry).

This pass adds a different kind of evidence: subagents mapped the whole tree and the parse pipeline.

| Step | Output |
| --- | --- |
| `codebase-explorer` subagent (read-only, `explore` skill) | Full map at `tmp/src_exploration_report.md` — module inventory, parse chain, matrix family, extension friction, test layout, layer rules. |
| Architect subagent (`architecture-blueprint-generator` skill), fed that report | [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) (384 lines, 9 sections, 2 rendered mermaid diagrams: module dependency flowchart + `parse_file` sequence). Linked from `docs/README.md`. |

Things the architecture pass settled with evidence:

- **The result contract, measured in the debugger** rather than read off the annotation: always the same 8 top-level keys, input-dependent `problem_data`, matrix objects inside `Any` (`PC1`, updated above).
- **`SECTION_GRAMMARS` is half-consumed** — registered as **PC10** with the two exits; the decision is now a Phase A item rather than an unexplained artifact.
- **A dead `pass` removed** in `validation.py`'s EXPLICIT/`FUNCTION` path: the branch `elif edge_format in FUNCTIONAL_EDGE_WEIGHT_FORMATS: pass` could never decide anything because the following `if` re-tests the same membership. Behaviour identical, one branch fewer.
- **Two converter-side findings were reproduced independently** with line references and are already registered upstream, so nothing new was filed: `operations.py:105` `CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP'))` rejects `TOUR` (41 corpus files) — that is **M12**; and `cli/commands.py:28` calls `setup_logging(level=log_level)` with no `log_file`, so the run log `log/run-<timestamp>.log` promised by **P7** does not exist — that is **m12** ("`log_file` never wired").
- **The architect corrected 10 line references and two descriptions** in the explorer's map (e.g. `as_name_dict` emits only non-default keys, `models.py:661`; `CordeauParseError` is at `cordeau_parser.py:13`), and found that `docs/diagrams/converter-architecture.md` documents a superseded layout (`converter/core/parser.py`, `database/schema.py` — neither exists). Not fixed: out of scope for a documentation pass, and the blueprint states the contradiction instead.

**Doc conventions followed:** the blueprint uses the frontmatter shape already in `docs/README.md` (`title`/`description`/`created`/`modifications`/`related_files`/`tags`), relative links, and mermaid code fences.

### 2026-10-14 — review follow-ups (open)

_Post-implementation review, with the owner's verdict (2026-10-14). R1–R2 are what this pass left behind; R3–R4 are behaviors the pass made visible; R5–R6 are pre-existing structure and coupling._

| # | Finding | Where | Verdict / next step |
| --- | --- | --- | --- |
| **R1** | After the field-level `validate` hooks were removed, the declared `dimensions` argument (`IndexedCoordinatesField("NODE_COORD_SECTION", dimensions=(2, 3))`, `dimensions=2` for display data) is no longer consulted by any enforcement path. | `models.py:476-482`, `models.py:801`, `models.py:804` | _Not dead code._ The declaration is the field's own description of the shape it accepts and the hook for future problem types and for upgradeability; it stays. The gap is that enforcement stopped consulting it. |
| **R2** | The rule that replaced `IndexedCoordinatesField.validate` hardcodes `{2, 3}` for `node_coords` and drops the `display_data` check, while the removed hook compared every value against the field's declared `dimensions`. | `validation.py:121-134` | Make enforcement read the declared `dimensions` again, so `display_data` is 2-D only and a new field declares its own shape — without restoring a hook that nothing calls. |
| **R3** | `StandardProblem.parse` raises `unsupported TIME_WINDOW_SECTION` for an extended section, while `FormatParser.parse_file` strips that same section before parsing. | `models.py` (`_SectionAccumulator.close`) vs `parser.py` (`_preprocess_vrp_file`) | Raising is **correct**: `StandardProblem` models core TSPLIB95 only. Keep it. The asymmetry belongs to the preprocessor, not to the model. |
| **R4** | `_STRIPPED_SECTIONS` is VRP/LKH-3 policy inside the core parser, applied to every file; no file in [`datasets_raw/problems`](../../datasets_raw/problems) uses those sections. | `parser.py:11-28` | The record is kept deliberately: it exists for the problem types that are not implemented yet. What has to change is the coupling in **R6**, not the table. |
| **R5** | `StandardProblem.parse` is ~90 lines with four responsibilities: keyword lines, section header/EOF open-close, the non-standard `FIXED_EDGES :` inline form, and error aggregation. | `models.py:811-898` | Extract per-kind handlers as part of the **PP1** split of `models.py` (split first, then extract), not as another patch on an already-large file. |
| **R6** | `FormatParser.parse_file` is hardcoded to `StandardProblem` (module import plus a direct call), so the entry point cannot route a file to another problem class. | `parser.py:9`, `parser.py:165` | Required before any LKH-3 work: `FormatParser` dispatches to a problem class (registry/`ProblemType` in the foundations phase) instead of naming `StandardProblem`. |

### 2026-10-15 — vocabulary and section grammars

| Item | Change | Where |
| --- | --- | --- |
| Phase A / PC8 | `types.py` now also holds `EDGE_WEIGHT_TYPES` (spec §1.1.6, all 13 values) and `SECTION_GRAMMARS` (spec §1.2, one entry per variant with its column kinds, selector keyword, terminator count and result key). `validation.py` reads the shared `VALID_PROBLEM_TYPES` instead of its own set. | `types.py`, `validation.py` |
| PC7 | `tests/test_format/test_section_grammars.py` — 21 tests derived from `SECTION_GRAMMARS`: a completeness test (a new grammar without a case fails), a per-variant raw-line check (column kinds + terminators), and per-section value tests that compare the parsed result with the file's own rows for `NODE_COORD_SECTION` (2-D and 3-D), `DEPOT_SECTION`, `DEMAND_SECTION` (including the depot-demand-0 rule), `EDGE_DATA_SECTION` (both layouts), `FIXED_EDGES_SECTION`, `DISPLAY_DATA_SECTION`, `TOUR_SECTION` and `EDGE_WEIGHT_SECTION` (matrix tokens in row-major order — the lines are wrapped, not rows). | `tests/test_format/test_section_grammars.py` |

**Corpus facts established while writing those tests** (they belong to the tests, not to folklore): no corpus file declares `THREED_COORDS` — the XRAY instances carry three columns without it; all nine HCP files are `EDGE_LIST`, so `ADJ_LIST` exists only in the spec (and in synthetic fixtures); no corpus file has both `NODE_COORD_SECTION` and `DISPLAY_DATA_SECTION`; explicit matrices are wrapped at an arbitrary line width, so `dimension²` tokens, not `dimension` lines, is the invariant.

**Guardrail after this pass:** corpus 239 files / 0 failures, `tests/test_format` green (102 passed, 1 skipped), `tests/test_converter/test_cost.py` green (15 passed), ruff and mypy clean on the touched files.

### 2026-10-21 — decomposition and descriptor protocol (PP1, PP5, PB6, R6)

| Item | Change | Where |
| --- | --- | --- |
| **PP1** | `models.py` decomposed into 4 cohesive single-responsibility modules: `transformers.py` (388 lines), `fields.py` (241 lines), `tokenization.py` (99 lines), and `models.py` (314 lines). Zero backward-compatibility re-export shims; call sites and tests import directly from target modules. | `src/tsplib_parser/` |
| **PP5** | `Field` implements Python's standard non-data descriptor protocol (`__get__`). Deleted `Problem.__getattribute__` interception from the hot path; unset attributes return defaults via the descriptor, while assigned attributes resolve via `__dict__` with zero lookup overhead. | `fields.py`, `models.py` |
| **PB6 / LSP** | Removed `Problem.parse()` entirely (Option 1). `Problem` is an abstract entity model, not a syntax parser; TSPLIB parsing is owned by `StandardProblem.parse` and `FormatParser`. | `models.py`, `test_unit_parser_contract.py` |
| **R6 / Registry** | Declarative problem registry (`PROBLEM_REGISTRY`, `register_problem_class`, `get_problem_class_for_type`). `FormatParser.parse_file` auto-dispatches to registered model classes (`StandardProblem`, `LKHProblem`) based on declared `TYPE`. | `models.py`, `parser.py` |

