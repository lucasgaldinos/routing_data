---
title: The parser pipeline
description: >
  Parsing versus validation versus storage, the walk through parse_file, the four mechanisms that decide what a file is, the dead detector and the SPECIAL gap, where the VRP extras live, and the open design questions (graphing, CLI, parallelism, DB round-trip, distances). Repo-specific companion to the python-logic series.
created: 2026-10-06
type: guide
scope: repo
status: draft
author:
  - Lucas Galdino
  - GitHub Copilot
modifications:
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Placeholder created so cross-file links resolve while the file is written in a later turn.
  - date_modified: 2026-10-07
    modifications:
      - description: >
          First real version. Rewrote §1.4, §6.1 and §6.2 of PARSER-DETAILS.MD as a pipeline narrative: three layers, the parse_file walk, the four type mechanisms, dead-code findings with their real consequences, the VRP extras as parser-object state, and the review's open design questions folded in where they belong.
related_files:
  - [PARSER-DETAILS.MD](../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [parser.py](../../../src/tsplib_parser/parser.py)
  - [validation.py](../../../src/tsplib_parser/validation.py)
  - [models.md](./models.md)
  - [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md)
tags:
  - guide/parser-pipeline
  - guide/tsplib-parser
  - guide/etl
  - guide/open-questions
---

# The parser pipeline

## What this file is

Everything between a file on disk and a JSON payload: which layer does what, what decides a file's type, where the non-standard VRP data actually lives, and which findings from the code review are still open. The package core is [models.md](./models.md); the per-call mechanics are [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md).

## Three layers, not two

The quoted `parser.py:808-888` range holds `validate_problem` ([`parser.py:808`](../../../src/tsplib_parser/parser.py#L808), ending at 852) and the start of `detect_special_distance_type` ([`parser.py:854`](../../../src/tsplib_parser/parser.py#L854)). They belong to three distinct layers:

- [`StandardProblem.parse`](../../../src/tsplib_parser/models.py#L832-L920) is **syntax**: does this text look like TSPLIB95? Keyword to field, section to body.
- [`validation.py`](../../../src/tsplib_parser/validation.py) is **semantics**: does the data agree with itself? `DIMENSION` against coordinate count, `DEMAND_SECTION` covering every node, `EXPLICIT` requiring a weight format and non-empty weights.
- [`FormatParser.validate_problem`](../../../src/tsplib_parser/parser.py#L808) is the **bridge**: it normalizes the declared type, hands a plain dict to `validate_problem_data` ([`validation.py:13`](../../../src/tsplib_parser/validation.py#L13), called from [`parser.py:841`](../../../src/tsplib_parser/parser.py#L841)), then adds the one check needing the live object — coordinate count against `DIMENSION`.

The split pays off three ways: text can be parsed without being required to be valid; a dict already in the database can be validated without reparsing text; and `validation.py` stays pure functions over dictionaries, with no dependency on `Problem` or `Field`.

## The walk through parse_file

```text
FormatParser.parse_file(path)                                  parser.py:82
  1. _preprocess_vrp_file(path)      may write a temp file, strips VRP extensions
  2. open(...).read()                text
  3. StandardProblem.parse(text, ...)  the four steps of the parse loop
  4. validate_problem(problem)       may raise
  5. _extract_*                      plain dict result
```

Everything runs before the caller regains control, so a returned problem is never half-built — the per-step detail is in [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md).

## What decides what a file is: four mechanisms

None of them is `detect_special_distance_type` — the dead detector participates in nothing.

**Type normalization**, `_normalize_problem_type` (`parser.py`): the raw `TYPE` string is cut at the first `(` and upper-cased, then checked against `{"TSP", "ATSP", "CVRP", "VRP", "HCP", "SOP", "TOUR"}`. `TSP (M.~HOFMEISTER)` normalizes to `TSP`; anything outside the set passes through unchanged, with no error.

**Validation**, [`validation.py:82`](../../../src/tsplib_parser/validation.py#L82): the same seven types; an unknown one appends `Unknown problem type: <x>` to the error list.

**VRP variant reclassification**, in `_extract_problem_data` (`parser.py` 436-453), overrides the declared type:

| Field present in `_additional_vrp_fields` | Emitted type |
| --- | --- |
| `capacity_vol` | `MC-VRP` |
| `has_time_windows` | `TW-VRP` |
| `has_pickup_delivery` | `PD-VRP` |
| several of them | labels joined without separators: `MCTW-VRP`, `MCPD-VRP`, `MCTWPD-VRP` |
| only `max_distance` | nothing changes — stored in its own field, never alters the type |

The helper's docstring advertises `D-VRP`, which is never emitted, and the `else` branch that would emit `CVRP` is unreachable — it sits inside a guard requiring at least one marker field. Stale docstring plus dead fallback.

**Edge weight source**, [`_identify_weight_source`](../../../src/tsplib_parser/parser.py#L763):

| `EDGE_WEIGHT_TYPE` | Result |
| --- | --- |
| `EXPLICIT` | `explicit_matrix` |
| `SPECIAL` | `special_function` |
| `EUC_2D`, `EUC_3D`, `MAX_2D`, `MAX_3D`, `MAN_2D`, `MAN_3D`, `CEIL_2D`, `GEO`, `ATT`, `XRAY1`, `XRAY2` | `coordinate_based` |
| anything else, or missing | `unknown` |

## Dead code, and the gap behind it

Which helpers in the quoted range are live:

| Symbol | Defined at | Called from | Status |
| --- | --- | --- | --- |
| `validate_problem` | `parser.py:808` | `parser.py:149`, inside `parse_file` | live |
| `_check_symmetry` | `parser.py:727` | `parser.py:723`, inside `_extract_metadata` | live |
| `_identify_weight_source` | `parser.py:763` | `parser.py:724`, inside `_extract_metadata` | live |
| `detect_special_distance_type` | `parser.py:854` | nothing outside its own docstring | dead |
| `validate_problem_data` | `validation.py:13` | `parser.py:841` | live |
| `validate_coordinates` | `validation.py:121` | `validation.py:112` and `115`, plus re-exports at `__init__.py:51` and `67-68` | live |

Exactly one function is dead — and the gap it implies is the real finding: SPECIAL is a label, never behaviour. `parse_file` builds `StandardProblem.parse(text, special=special_func)` at `parser.py:142`, `parse` accepts `**options` and never reads it, and `_identify_weight_source` still labels the problem `weight_source: "special_function"`. [`UnsupportedFeatureError`](../../../src/tsplib_parser/exceptions.py#L114) documents "SPECIAL distance types without custom function", but nothing raises it. A SPECIAL file therefore parses cleanly, carries no distances, claims a special function in its metadata, and raises no error anywhere.

Two smaller weaknesses in the same neighbourhood:

- `_check_symmetry` can only return `False` for `ATSP`; the symmetric branch and the fallthrough both return `True`, so `is_symmetric` is effectively shorthand for "not ATSP" — weaker than its docstring suggests.
- The dead detector reads the whole file as text and tests `"EDGE_WEIGHT_TYPE" in content and "SPECIAL" in content`, never the keyword's actual value. A `COMMENT` mentioning SPECIAL would satisfy it. Worth knowing before it is ever wired up.

## Where the VRP extras live

The extras (`capacity_vol`, `capacity_weight`, `max_distance`, `has_time_windows`, `has_pickup_delivery`, `volume_demands`, ...) are neither fields nor problem attributes — they are state on the **parser object**:

```text
FormatParser.parse_file(path)
  1. _preprocess_vrp_file(path)
       reads the raw lines; recognises CAPACITY_VOL / DISTANCE / TIME_WINDOW_SECTION / PICKUP_SECTION ...
       stores them in self._additional_vrp_fields      parser.py:357
       writes a temp file WITHOUT those lines
  2. StandardProblem.parse(text)    ← parses the stripped temp file
  3. _extract_problem_data(problem)
       merges self._additional_vrp_fields back into the result dict  parser.py:434
       and may rewrite result["type"] to MC-VRP / TW-VRP / PD-VRP
```

Three consequences explain the behaviour:

- **Not fields.** No `Field`, no `fields_by_name` entry, no keyword registered — the lines are removed before `StandardProblem.parse` ever sees them, so `FileMeta` is not involved.
- **Not on the problem object.** `problem.capacity_vol` does not exist; the value reaches you only through the returned dict (`result[field_name]`, `parser.py:434`). The "data lives on the instance" rule of [models.md](./models.md) still holds — these values were never problem attributes to begin with.
- **Per-call state on a shared object.** `SimpleConverter.__init__` builds one `FormatParser` and reuses it (`converter/api.py:35`); each `parse_file` call replaces `self._additional_vrp_fields` (`parser.py:357`). Fine for a single sequential run; two threads sharing one converter would race. One caveat: the assignment sits near the end of `_preprocess_vrp_file`, so a failure during the scan leaves the previous call's dict in place — harmless today only because that call raises before anything merges it. A per-call return value would remove the question.

## Reshaping, not reparsing

Three components sit at three levels, and only the middle one sees the file format:

```text
file on disk
   ↓  FormatParser.parse_file          file-level: preprocess, read, validate, extract
plain dict  {'problem_data', 'nodes', 'tours', 'metadata', 'demands', 'depots', 'edges'}
   ↓  DataTransformer.transform_problem  storage-level: reshape into the schema v2 columns
storage/JSON payload
```

| Component | Input | Output | Job |
| --- | --- | --- | --- |
| `StandardProblem.parse` (`models.py:832`) | text | a `StandardProblem` | the only reader of the keyword/section format |
| `FormatParser.parse_file` (`parser.py:82`) | a path | a plain dict | preprocessing, the call to `parse`, `validate_problem`, then `_extract_*` |
| `DataTransformer.transform_problem` (`converter/core/transformer.py:37`) | that dict | the storage payload | array columns, edge-weight expansion, metadata enrichment |

The file format is parsed **once**. What happens more than once is *reshaping*, and it is worth naming rather than denying:

- `_extract_nodes` (`parser.py:494`) normalizes nodes to 0-based ids with `demand` and `is_depot`; `_normalize_nodes` (`converter/core/transformer.py:160`) normalizes the same keys again with `.get(...)` defaults. Two passes over the same shape; the second only ever sees dicts the first built.
- `_extract_problem_data` puts a `matrix.Matrix` under `problem_data["edge_weights"]` when `create_explicit_matrix()` succeeds, and the raw list of lists otherwise; `_convert_edge_weights_to_matrix` turns either into a list of lists before `del problem_meta["edge_weights"]` (`converter/core/transformer.py:96`) removes the key. That `del` runs after the conversion's `try`, so it also runs when the conversion failed and the matrix column ended up `None`.

Neither is a re-parse; both are consequences of the parser returning a pythonic object and the transformer needing a storage-shaped one.

## Open design questions

Folded in from the review that produced this series; each is a decision to make, not a finding:

| Question | Current state | Direction |
| --- | --- | --- |
| Graphing for a parsed problem without a full DB | no graph module exists; distances are labeled, not computed | fail fast if the distance type does not match, rather than assuming Euclidean; a model-side shortcut next to the DB-side default is reasonable |
| Helper CLI to identify problem specs before conversion | `converter_cli.py` exists; the review command only inspected `zips/` | add a spec-inspection helper covering the whole raw tree |
| Distance dispatch ownership | the parser only labels (`_identify_weight_source`); lengths are computed at the converter layer (`cost.py`) | decide between wiring `special`/dispatch into a distance module or deleting the parameter until that module exists — the current "advertised, accepted, ignored" state should not stay |
| Matrices and lengths | `create_explicit_matrix` on `StandardProblem` (`models.py:922`); coordinate distances live at the converter layer — `src/converter/utils/cost.py` implements the TSPLIB set (`_COORD_DISTANCES`) and mirrors `src/distances/pairwise.py` in the sibling `gpu_accelerated_clean` repo (`distances/matrix.py`, `pairwise.py`) | reuse the existing implementations, not rewrite; keep the numpy variants as the benchmark-side source |
| Parallel converter runs | scheduling lives in the converter driver; failures are not surfaced (open task) | surface per-file failures in the driver |
| Recreate a problem from the DB | EXPLICIT matrices are stored, so edges/weights are reconstructible; no `render()` exists | DB-first: LKH-style emission would be a later, separate consumer of the same model — add a writer module when a consumer exists |
| `DepotsField` terminal fix | `_split_items` strips only if present; depot sections without `-1` can raise | option 1 now (strip-only-if-present, path unreachable today) — adopt option 3 (tolerate `-1`-less sections) only when a real file forces it |

Which types actually reach the processed output: `datasets_processed/json` contains exactly five folders — `atsp`, `cvrp`, `hcp`, `sop`, `tsp`. The raw tree additionally has `tour/` and `vrp/`, so those are either not converted or land under other names, even though both are in the known-type sets.

## Connections

### Links out

- [models.md](./models.md) — the package core this pipeline wraps, and the matrix builder.
- [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md) — the per-call flow of `StandardProblem.parse`.
- [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md) — the tolerant/strict halves of the parser are summarized there.
- [descriptors-fields.md](../../studies/python-logic/theoretical/descriptors-fields.md) — the field objects each keyword routes to.
- [README.md](../../studies/python-logic/README.md) — the series map of content.

### Backlinks

Files that link here:

- [models.md](./models.md) — "the parser around this package".
- [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md) — "the parser that wraps this factory" and the `special=` parameter.
- [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md) — the strict-half audit for parser.py.
