# `routing_data/src` architecture map

Read-only exploration. Python 3.12 in `.venv`; commands run with `uv run` and
`PYTHONPATH=src`. Line counts are `wc -l`. This is a map, not a review; registered
defects (PB1, PB12, PB13, PC1, PC6/D1, PP1, R6, PB14) are pointed at, not re-litigated.
Registers: `src/tsplib_parser/TODO.md`, `src/converter/TODO.md`, repo `TODO.md`.

Two packages under `src/`: **`tsplib_parser`** (standalone TSPLIB95 parser, 3.65 kLOC)
and **`converter`** (ETL: parse → transform → JSON/DuckDB, 4.29 kLOC).

---

## 1. Module inventory

### `src/tsplib_parser/**` (full)

| path | lines | purpose | public symbols | intra-repo imports |
|---|---|---|---|---|
| `tsplib_parser/__init__.py` | 73 | package facade; version `2.0.0` | re-exports `FormatError, ParseError, ValidationError, StandardProblem, validate_coordinates, validate_problem_data` | `.exceptions`, `.models`, `.validation` |
| `tsplib_parser/types.py` | 241 | pure vocabularies + spec grammar tables; no I/O | `ProblemType`(StrEnum), `PROBLEM_TYPE_ALIASES`, `VALID_PROBLEM_TYPES`, `EXTENSION_TYPE_HINTS`, `EDGE_WEIGHT_TYPES`, `ColumnKind`, `SectionGrammar`, `SECTION_GRAMMARS`, `NODE_COORD_DIMENSIONS`, `DISPLAY_DATA_DIMENSIONS` | none |
| `tsplib_parser/exceptions.py` | 129 | exception hierarchy | `FormatError`(base, `.wrap`/`.amend`), `ParseError(FormatError, ValueError)`, `ValidationError(FormatError)`, `UnsupportedFeatureError(FormatError)` | none |
| `tsplib_parser/matrix.py` | 363 | EXPLICIT weight-matrix classes + format registry | `Matrix`, `FullMatrix`, `HalfMatrix`, `UpperDiagRow`/`LowerDiagRow`, `UpperRow`/`LowerRow`, `UpperCol`/`LowerCol`, `UpperDiagCol`/`LowerDiagCol`, `TYPES`, `integer_sum` | `.exceptions` |
| `tsplib_parser/models.py` | 967 | field-based TSPLIB95 model (utilities+transformers+fields+model, one module — PP1) | `BiSep`, `Transformer`, `FuncT`, `NumberT`, `EdgeDataT`, `ContainerT`, `ListT`, `MapT`, `Field`, `TransformerField`, `StringField`, `IntegerField`, `IndexedCoordinatesField`, `DepotsField`, `DemandsField`, `MatrixField`, `EdgeListField`, `EdgeDataField`, `ToursField`, `FileMeta`, `Problem`, `_SectionAccumulator`, `StandardProblem` | `.exceptions`, `.matrix` |
| `tsplib_parser/parser.py` | 901 | high-level ETL entry point | `FormatParser` (`.parse_file`, `.validate_problem`, `.detect_special_distance_type`, 8 `_extract_*`) | `.exceptions`, `.models`, `.validation`, **`tsplib_parser.matrix`** (absolute — PP10) |
| `tsplib_parser/validation.py` | 203 | cross-field invariants over `as_name_dict()` | `validate_problem_data`, `validate_coordinates`, `FUNCTIONAL_EDGE_WEIGHT_FORMATS`, `WEIGHT_BEARING_TYPES` | `.matrix`, `.types` |
| `tsplib_parser/cordeau/__init__.py` | 18 | cordeau facade | re-exports the 5 cordeau names | `.cordeau_converter`, `.cordeau_parser`, `.cordeau_types` |
| `tsplib_parser/cordeau/cordeau_types.py` | 142 | dataclasses for Cordeau MDVRP | `CordeauDepotConstraint`, `CordeauNode`, `CordeauProblem` (`.type_name`, `.dimension`, `.customer_nodes`, `.depot_nodes`) | none (dataclasses) |
| `tsplib_parser/cordeau/cordeau_parser.py` | 324 | Cordeau text → dataclasses | `CordeauParser`, `CordeauParseError(Exception)` | `.cordeau_types` |
| `tsplib_parser/cordeau/cordeau_converter.py` | 246 | Cordeau dataclasses → TSPLIB95 text | `CordeauConverter` | `.cordeau_types` |

### `src/converter/**` (module granularity)

| path | lines | purpose | public symbols | intra-repo imports |
|---|---|---|---|---|
| `converter/__init__.py` | 42 | facade; re-exports the 5 `api` functions | `parse_file, to_json, to_database, process_directory, create_simple_converter` | `.api` |
| `converter/__main__.py` | 6 | `python -m converter` → `cli` | — | `.cli.commands` |
| `converter/api.py` | 301 | high-level API + schema-v2 payload builder | `SimpleConverter`, `merge_v2_payload`, module-level `parse_file/to_json/to_database/process_directory/create_simple_converter` | `tsplib_parser.parser`, `.core.transformer`, `.database.operations`, `.output.json_writer`, `.utils.logging` |
| `converter/config.py` | 68 | YAML config dataclass | `ConverterConfig`, `load_config`, `save_config` | none |
| `converter/cli/commands.py` | 586 | Click CLI | `cli` group + `process, validate, analyze, init, export-parquet, inspect` | `.core.scanner`, `.database.operations`, `.output.json_writer`, `.output.parquet_writer`, `.utils.logging`, `.utils.parallel`, `.utils.update`, `.utils.worker_functions` |
| `converter/core/scanner.py` | 172 | file discovery/batching by glob | `FileScanner` | none |
| `converter/core/transformer.py` | 552 | parse-result → storage shape; solution-file parsing | `DataTransformer` | **`tsplib_parser.matrix`**, (TYPE_CHECKING `tsplib_parser.parser`) |
| `converter/database/operations.py` | 907 | DuckDB schema v2 write/read | `DatabaseManager` | `.utils.exceptions` |
| `converter/output/json_writer.py` | 126 | per-type JSON files | `JSONWriter` | `.core.transformer` |
| `converter/output/parquet_writer.py` | 266 | DuckDB table → Parquet | `ParquetWriter`, `export_database_to_parquet` | none (duckdb) |
| `converter/output/__init__.py` | 6 | output facade | `JSONWriter`, `ParquetWriter`, `export_database_to_parquet` | `.json_writer`, `.parquet_writer` |
| `converter/utils/cost.py` | 287 | TSPLIB distance registry + route-cost | `compute_routes_cost`, `supported_weight_types` | **`tsplib_parser.exceptions`**, **`tsplib_parser.types`** |
| `converter/utils/exceptions.py` | 308 | converter error hierarchy | `ConverterError` → `ExtractionError, TransformError, DatabaseError, OutputError, NotFoundError` | none |
| `converter/utils/logging.py` | 43 | logger factory | `setup_logging` | none |
| `converter/utils/parallel.py` | 272 | process/thread pool runner | `ParallelProcessor` | none |
| `converter/utils/update.py` | 273 | incremental update / checksums | `UpdateManager` | none |
| `converter/utils/worker_functions.py` | 122 | picklable worker for `ProcessPoolExecutor` | `process_file_for_parallel`, `calculate_checksum` | `converter.core.transformer`, `tsplib_parser.parser` (function-local, lines 57-58) |

---

## 2. The parse pipeline, end to end

Entry: `FormatParser.parse_file(file_path, special_func=None) -> dict[str, Any]` (`parser.py:103`, annotation `parser.py:103-105`; `special_func` is dead — PB1).

Order of calls inside `parse_file` (`parser.py:157-205`):

1. `self._preprocess_vrp_file(file_path)` (`parser.py:158`; impl `parser.py:219`). Reads the file (utf-8, latin-1 fallback), scans lines; strips LKH-3 sections named in `_STRIPPED_SECTIONS` (`parser.py:20`), records them in `self._additional_vrp_fields["stripped_sections"]`; also handles `CAPACITY_VOL`/`CAPACITY_WEIGHT`/`DISTANCE`/multi-dimensional demand. Writes a temp `*.vrp` only if content changed. Returns original or temp path.
2. `open(processed_file).read()` → `text` (`parser.py:165-166`).
3. `problem: StandardProblem = StandardProblem.parse(text, special=special_func)` (`parser.py:167`). **This is where `StandardProblem` is hardcoded (R6).** The `special=`/`**options` is never read by the model (`models.py:670`, `**options` ignored — PB1). Temp file unlinked in `finally` (`parser.py:168-170`).
4. `self.validate_problem(problem)` (`parser.py:173`; impl `parser.py:822`). Calls `problem.as_name_dict()` (`models.py:654`), normalizes `problem_type→type`, then `validation.validate_problem_data(data)` (`validation.py:25`); adds a coordinate-count/dimension check (`parser.py:840-846`); raises `ValidationError` on any error.
5. Extraction methods, in order:
   - `demands, depots = self._extract_demands_depots(problem)` (`parser.py:176`, impl `parser.py:587`) → reads `problem.demands` (dict `{1-based id: int}`) and `problem.depots` (list) → result keys `demands` (length-`dimension` 0-based list, `[]` if no DEMAND_SECTION) and `depots` (sorted 0-based list).
   - `_extract_problem_data(problem)` (`parser.py:390`) → reads `as_name_dict()` + `problem.edge_weights` → result key `problem_data` (dict; 9 base keys + conditional `edge_weights` + VRP extension keys).
   - `_extract_nodes(problem)` (`parser.py:506`) → reads `node_coords, demands, depots, display_data` → result key `nodes` (empty `[]` when no `NODE_COORD_SECTION` — this is PB13's root: display data has nowhere to go).
   - `_extract_tours(problem)` (`parser.py:626`) → reads `tours` → result key `tours` (`[{tour_id, nodes:0-based}]`).
   - `_extract_metadata(problem, file_path)` (`parser.py:704`) → reads `problem` attrs + calls `_check_symmetry` (`parser.py:741`, PB2) and `_identify_weight_source` (`parser.py:777`) → result key `metadata` (9 keys).
   - `_extract_edges(problem)` (`parser.py:660`) → reads `edge_data` → result key `edges` (0-based pairs).
   - `_extract_fixed_edges(problem)` (`parser.py:682`) → reads `fixed_edges` → result key `fixed_edges`.
6. Result dict assembled at `parser.py:180-195`: `problem_data, nodes, tours, metadata, edges, fixed_edges, demands, depots` — all 8 keys always present. **Verified**: all 239 corpus files return exactly these 8 keys (see §7).

Conditional keys: `problem_data["edge_weights"]` only when `problem.edge_weights` truthy (`parser.py:436-441`); `problem_data` gains `capacity_vol/capacity_weight/max_distance/has_time_windows/…` only from VRP preprocessing; a `type` may be rewritten to a synthetic compound label (`MC-VRP`, `TW-VRP`, `PD-VRP`, …) at `parser.py:451-465`. `demands`/`depots` are `[]` when the section is absent.

### The transform/field layer (`models.py`)

- `BiSep` (`models.py:54`): in/out separator pair; `.from_value(None|str|(in,out))` normalizes; used to split/join section bodies.
- `Transformer` base (`models.py:115`): `parse(text)->T`. Subclasses: `FuncT` (apply a function, `models.py:129`), `NumberT` (int-then-float, `models.py:152`), `EdgeDataT` (edges, sniffs EDGE_LIST vs ADJ_LIST — PB12, `models.py:169`).
- `ContainerT` (`models.py:229`) + `ListT` (`models.py:308`) + `MapT` (`models.py:318`): split a section body by separator, enforce/remove a `-1` terminal, parse per item, aggregate errors with 1-based positions, enforce `size`, `pack` into list/dict.
- `Field` (`models.py:409`) → `TransformerField` (`models.py:436`, builds its transformer via `build_transformer`, PP3). Concrete fields: `StringField`(`:453`), `IntegerField`(`:461`), `IndexedCoordinatesField`(`:471`), `DepotsField`(`:491`), `DemandsField`(`:502`), `MatrixField`(`:514`), `EdgeListField`(`:525`), `EdgeDataField`(`:533`), `ToursField`(`:559`). Each maps one TSPLIB keyword → parsed value.
- `FileMeta` metaclass (`models.py:597`): walks the MRO and builds `fields_by_name` / `fields_by_keyword` from class attrs that are `Field` instances. **This is the sole section/keyword registration mechanism.**
- `Problem` (`models.py:621`): `__getattribute__` override returns a field's default when the value is absent (PP5); `as_dict`/`as_name_dict`/`as_keyword_dict` drop nothing but include defaults; base `parse` raises `NotImplementedError` (`models.py:670`).
- `_SectionAccumulator` (`models.py:723`): holds the current `*_SECTION` and its raw lines; `open/add/seed/close` (`:746/:752/:756/:760`); on `close` it parses the joined body through the registered field, sets the attribute, or appends `unsupported <SECTION>` (`:773`) / `invalid <SECTION>` (`:780`) to a shared error list.
- `StandardProblem` (`models.py:785`): declares the fields (`:787-808`) and implements `parse` (`models.py:810`, single pass over lines). Also `create_explicit_matrix()` (`models.py:904`), which reads `edge_weight_format/edge_weights/dimension/problem_type` and builds a `matrix.TYPES` object.

---

## 3. Data structures crossing boundaries (`matrix.py`)

- Base `Matrix` (`matrix.py:54`): `numbers` (flattened), `size`, `min_index`; `__getitem__`→`value_at` (`:106`) via `get_index` (abstract, `:138`); constructor validates element count against `_calculate_expected_size` (`:90`).
- `FullMatrix` (`:156`, `get_index=i*size+j`), `HalfMatrix` (`:170`; `has_diagonal`; `value_at` returns 0 on the unused diagonal and calls `_fix_indices`), then `UpperDiagRow`(`:223`), `LowerDiagRow`(`:252`), `UpperRow`(`:280`), `LowerRow`(`:298`), `UpperCol`(`:316`), `LowerCol`(`:325`), `UpperDiagCol`(`:334`), `LowerDiagCol`(`:343`). Column variants subclass the mirrored row classes (`UpperCol(LowerRow)` etc.).
- `matrix.TYPES` (`matrix.py:353`) maps the 9 `EDGE_WEIGHT_FORMAT` strings → classes (FULL_MATRIX, UPPER/LOWER × DIAG/ROW/COL). Confirmed 9 keys at runtime.
- Construction: `StandardProblem.create_explicit_matrix()` (`models.py:904`) flattens `edge_weights` and instantiates `TYPES[fmt]`; tolerates two deviations (leading DIMENSION marker; customer-only VRP matrix) else raises `ParseError`.
- Where it lands in the result: inside `Any` — `_extract_problem_data` puts the `Matrix` object into `result["problem_data"]["edge_weights"]` (`parser.py:437-441`). **Verified**: `gr17.tsp` → `LowerDiagRow` instance; `eil22.vrp` → no `edge_weights` key. Downstream, `DataTransformer._convert_edge_weights_to_matrix` (`transformer.py:~193`) turns it into a full `list[list]` under `edge_weight_matrix` and deletes the raw key (`transformer.py:88-96`).

---

## 4. Extension points and extension friction

**(a) New TSPLIB95 problem type.** Files/lines that must change:
1. `types.py` — add a `ProblemType` member (`types.py:44`); `VALID_PROBLEM_TYPES` (`types.py:86`) and `EXTENSION_TYPE_HINTS` (`types.py:92`) derive from it, so validation (`validation.py:99`) follows automatically.
2. `parser.py` — `_normalize_problem_type`'s `known_types` set (`parser.py:486`); the DB-facing label is emitted here.
3. `parser.py:12` (import) and `parser.py:167` (`StandardProblem.parse`) — **R6**: `FormatParser` hardcodes `StandardProblem`, so a new problem *class* cannot be dispatched to without editing the entry point.
4. `database/operations.py` — the hub `CHECK (type IN ('TSP','ATSP','CVRP','HCP','SOP'))` (`operations.py:101-110`), a new per-type table plus `_TYPE_INSERTERS` (`operations.py:243`) / `_TYPE_TABLES` (`operations.py:255`) entries and an `_insert_*`/read counterpart.
   What breaks first: the entry point can only ever produce a `StandardProblem`, so extension sections the new type needs either go unmodeled (dropped/erroring) or require a subclass that `parse_file` never picks; then `validation` rejects an unregistered type; then the DB `CHECK`/`_normalize_type_for_schema` (`operations.py:273`) rejects the label.

**(b) New data section.** Add a `Field` subclass in `models.py` (e.g. near `models.py:514-559`), attach it as an attribute on `StandardProblem` (`models.py:787-808`) — `FileMeta` (`models.py:597`) auto-registers it in `fields_by_keyword`. `StandardProblem.parse` opens any `line.endswith("_SECTION")` (`models.py:869`) and `_SectionAccumulator.close` (`models.py:760`) parses it; an unregistered section is reported (`models.py:773`). To surface it in the public result, add an `_extract_*` and a key in the result dict (`parser.py:180-195`) plus, if persisted, a schema column and transformer passthrough.

**(c) cordeau island.** `cordeau/*` does **not** plug into `FormatParser` dispatch: `CordeauParser.parse_file` (`cordeau_parser.py:47`) is a standalone pass over Cordeau's own `type m n t` header format, returning `CordeauProblem` dataclasses (`cordeau_types.py:76`); `CordeauConverter.to_tsplib95` (`cordeau_converter.py:51`) converts MDVRP (type 2 only, else `ValueError`) to a TSPLIB `CVRP` text that the normal pipeline then parses. Errors are signalled by `CordeauParseError(Exception)` (`cordeau_parser.py:20`) — **not** a `FormatError` subclass (PP6), so `except FormatError` callers miss it. `cordeau_types.CordeauProblem.__post_init__` (`cordeau_types.py:88`) also raises bare `ValueError`.

---

## 5. Tests and how they are written

`tests/` (7.24 kLOC) layout:
- `tests/conftest.py` (440) — shared fixtures: `test_data_dir` (→`datasets_raw/problems`, `conftest.py:13`), small/medium TSP, ATSP, VRP path maps, `gr17_tsp`, `temp_output_dir`, `in_memory_db` (imports `src.converter.database.operations`, `conftest.py:84`), `sample_problem_data`, `sample_nodes`, and ~15 string fixtures of malformed/edge-case TSPLIB content (`malformed_*`, `duplicate_*`, `function_weight_format_content`, `fixed_edges_keyword_content`, `comment_inside_sections_content`, `time_window_vrp_content`, `failing_preprocessed_vrp_content`, …).
- `tests/test_format/` (7 files) — the parser package. `test_format_parser.py` (FormatParser on real corpus files), `test_matrix_equivalence.py`, `test_matrix_validation.py`, `test_matrix_value_access.py` (the 9 matrix formats), `test_parser_contract.py` (PB3/5/6/7/8/9/10 behaviors), `test_parser_robustness.py` (malformed input must fail loudly), `test_section_grammars.py` (reads `SECTION_GRAMMARS` and checks raw corpus lines + parsed values).
- `tests/test_converter/` (8 files + `test_formats/`) — `test_converter_api.py`, `test_cost.py` (distance values incl. XRAY), `test_database.py`, `test_database_connection_leak.py`, `test_json_writer.py`, `test_json_writing_fixes.py`, `test_scanner.py`, `test_transformer.py`, `test_formats/test_cordeau.py`.
- `tests/test_integration/` — `test_cli.py`, `test_inspect.py`, `test_pipeline.py`.
- Top level: `test_edge_weights.py` (262) is a pytest file; `test_full_pipeline.py` (138) and `verify_database.py` (76) are **manual scripts** (`main()`/`__main__`) with no `test_*` functions — collected but empty. `test_full_pipeline.py` is **stale**: calls `db_manager.insert_problem_atomic(...)` and `transformed_data["nodes"]` (`test_full_pipeline.py:58-64`), the retired v1 API.

Corpus guardrail (239 files / 0 failures) exists **only as a manual script** documented in `src/tsplib_parser/TODO.md` §2, **not** as a pytest test (no test references 239 or rglobs the whole corpus; PC7). Fixtures referenced from corpus: `conftest.py` path maps and `test_section_grammars.py`'s `CASES` table.

Tests reaching into private state: `test_transformer.py:224,259` call `transformer._normalize_nodes`; `test_parser_contract.py:249,270` call the helper `self._route_temp_files_to(...)`; `test_matrix_equivalence.py:254` reads a local `_explicit_matrix` helper. Conventions: WHAT/WHY/HOW docstrings, dense parametrization; repo rule `.github/instructions/test.instructions.md` (comprehensive/value/boundary coverage; "DO NOT use `@pytest.mark.skip` with a comment explaining a bug").

Exact commands:
```bash
# parser format tests (the one green gate) — verified 102 passed, 1 skipped
PYTHONPATH=src uv run pytest tests/test_format -q
# converter + integration tests — verified 14 failed, 149 passed (pre-existing, TODO B2)
PYTHONPATH=src uv run pytest tests/test_converter tests/test_integration tests/test_edge_weights.py -q
# corpus gate (manual, from tsplib_parser/TODO.md §2)
PYTHONPATH=src uv run python - <<'EOF'
from pathlib import Path; from tsplib_parser.parser import FormatParser
p=FormatParser()
for f in sorted(x for x in Path("datasets_raw/problems").rglob("*") if x.is_file()): p.parse_file(f)
EOF
uv run ruff check src        # 4 errors; tests: 254 errors (PB14 subset)
PYTHONPATH=src uv run mypy src   # 54 errors in 6 files
```
`pytest.ini` sets `testpaths=tests`, verbose, strict-markers; `pyproject.toml` also declares pytest/mypy/ruff config (pytest warns it ignores the pyproject `[tool.pytest.ini_options]`). 1 skipped test: `test_matrix_equivalence.py:257` (stale reason — PP7/PB14).

---

## 6. Layering and dependencies

- Direction is one-way: **`converter` → `tsplib_parser`**. No `tsplib_parser` module imports `converter` (verified by import grep). Concretely: `converter/api.py:14` imports `tsplib_parser.parser`; `converter/core/transformer.py:11` imports `tsplib_parser.matrix`; `converter/utils/cost.py:29-30` imports `tsplib_parser.exceptions` + `tsplib_parser.types`; `converter/utils/worker_functions.py:57-58` (function-local) imports `tsplib_parser.parser`.
- Inside `tsplib_parser`: `types`/`exceptions` are leaves; `matrix`→`exceptions`; `models`→`exceptions,matrix`; `validation`→`matrix,types`; `parser`→`exceptions,models,validation,matrix`; `cordeau/*` import only within `cordeau`. `__init__.py` re-exports from `exceptions/models/validation` (not `parser`, to avoid import order issues — PP2 says no cycle actually exists).
- Cycles/violations: none found. Boundary/import-convention violations: `parser.py:9` uses an absolute self-import `from tsplib_parser.matrix import Matrix` while the rest are relative (PP10); `worker_functions.py` and `transformer.py` defer a `FormatParser` import to function scope / `TYPE_CHECKING`.
- `converter/utils/cost.py` sits **below** the parser in the layering but **reads the parser's vocabulary**: it imports `EDGE_WEIGHT_TYPES` (spec §1.1.6) and the exception types so the converter's distance registry and the parser agree on what a legal weight type is (TODO `CV2` explicitly justifies this as PC8's single-vocabulary rule). It has **no caller in `src/**`** (TODO `CV2`: "blast radius none yet").

---

## 7. Facts verified by running code, and what could not be verified

Verified (`.venv` = Python 3.12.13, pytest 9.1.1):
- `PYTHONPATH=src uv run pytest tests/test_format -q` → **102 passed, 1 skipped** in 0.68s (7 files, 103 collected). (TODO §1 still says "63 passed, 1 skipped" — stale.)
- Corpus through `FormatParser.parse_file` over `datasets_raw/problems/**`: **TOTAL_FILES=239, OK=239, FAIL=0**; by ext `.tsp 113, .sop 41, .tour 41, .atsp 19, .vrp 16, .hcp 9`. Every file returned exactly the 8 top-level keys `demands, depots, edges, fixed_edges, metadata, nodes, problem_data, tours`.
- Result shapes: `gr17.tsp` → `problem_data` has 10 keys incl. `edge_weights` (type `LowerDiagRow`, `isinstance(..., matrix.Matrix) is True`), `nodes=0`, `demands=0`; `eil22.vrp` → 9 `problem_data` keys, no `edge_weights`, `nodes=22, demands=22, depots=[0]`. `metadata` always the 9 documented keys. `matrix.TYPES` has 9 entries.
- `uv run ruff check src` → **4 errors**; `uv run ruff check tests` → **254 errors** (PB14 reports 34 in two matrix test files specifically). `PYTHONPATH=src uv run mypy src` → **54 errors in 6 files** (many `untyped-decorator` from Click in `cli/commands.py`).
- `PYTHONPATH=src uv run pytest tests/test_converter tests/test_integration tests/test_edge_weights.py -q` → **14 failed, 149 passed** (matches repo TODO blocker B2: cordeau integration, json_writer structure, json fixes, pipeline integration).

Could not verify / left as-is:
- The full 239-file corpus is not wired as a CI/test gate (PC7) — only a documented manual script; I ran it manually.
- The TODO registers' historical claims (e.g. `PB14` exact counts, `PP7` skip reason) were not separately re-derived beyond what ruff/pytest reported.
- `converter/utils/{parallel,update}.py`, `output/parquet_writer.py`, `cli/commands.py` bodies were read only at the signature/dispatch level, not line-by-line.
