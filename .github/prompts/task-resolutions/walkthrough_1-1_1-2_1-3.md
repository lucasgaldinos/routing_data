---
title: "Walkthrough: Tasks 1.1–1.3 — Parser Extraction of EDGE_LIST/ADJ_LIST and FIXED_EDGES"
task_id: "1.1-1.2-1.3"
description: >
  Batch 1 of the Routing_data database rebuild: added raw-text extraction of
  EDGE_DATA_SECTION (EDGE_LIST and ADJ_LIST) and FIXED_EDGES_SECTION into the
  FormatParser, and exposed them as top-level `edges`/`fixed_edges` keys on the
  parse_file result.
created: "2026-08-27"
author:
  - "[[Lucas Galdino]]"
status: "in-review"
tags: [guide/parser, algorithm/tsplib, algorithm/hcp, notes/routing-data, analysis/duckdb, benchmark/etl]
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
---

# Walkthrough: Tasks 1.1–1.3 — Parser Extraction (EDGE_LIST/ADJ_LIST + FIXED_EDGES)

## Objective

Extract HCP graph data (`EDGE_DATA_SECTION` in `EDGE_LIST`/`ADJ_LIST` formats) and
fixed edges (`FIXED_EDGES_SECTION`) in `FormatParser`, and expose both as top-level
keys of the `parse_file` result so the transformer/worker/insert chain reads them
uniformly (Decision #4). All edits confined to `parser.py`; `models.py` untouched.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| Parser | [parser.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py) | `parse_file` loads raw `text`; `StandardProblem.parse(text)` has no `FIXED_EDGES` field and its `EdgeDataField` expects weighted triples — unusable for HCP. |
| Models (read-only) | [models.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/models.py) | `edge_data_format = StringField('EDGE_DATA_FORMAT')` (L638); `EdgeDataField` (L452) parses weighted triples via `MapT(key=edge, value=int)`. |
| Decision pin | [plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md) | Decisions #1 (raw-text fixed edges), #3 (EDGE_LIST/ADJ_LIST parse), #4 (top-level keys). |
| Data | `datasets/problems/hcp/*.hcp` (9 files) | All declare `EDGE_DATA_FORMAT : EDGE_LIST`; `EDGE_DATA_SECTION` terminated by `-1`, then `EOF`. |
| Data | `datasets/problems/tsp/linhp318.tsp` | Declares `FIXED_EDGES_SECTION` `1 214` then `-1`. |
| Data | `datasets/problems/hcp/alb4000.hcp` | Non-standard `FIXED_EDGES :` keyword header after the edge list (must not bleed into `edges`). |

## Impact Analysis / Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Extraction approach | Raw-text scan of `text` (already loaded in `parse_file`) | `StandardProblem` drops unknown sections and `EdgeDataField` expects weighted triples; raw-text keeps `models.py` untouched (Decision #1/#3). |
| Shared section helper | New `_section_content(text, section_name)` | Deduplicates the "collect lines up to next `*_SECTION`/EOF" logic across edges and fixed-edges. |
| Section boundary robustness | `_section_content` also stops at all-uppercase keyword headers (e.g. `FIXED_EDGES :`) | `alb4000.hcp` places `FIXED_EDGES :` immediately after the edge list; without this, its 2 fixed edges would bleed into `edges`. ADJ_LIST data lines (`5: 1 2`) are excluded because their label is numeric (no alpha char). |
| ADJ_LIST expansion | `from: to1 to2 … -1` → `(from, toi)` pairs, skipping `-1` tokens | TSPLIB ADJ_LIST expands each adjacency list into per-neighbor edges; the trailing `-1` (per list and whole section) is ignored. |
| 0-based normalization | `int(token) - 1` | TSPLIB is 1-based; database uses 0-based (consistent with `_extract_nodes`). |
| Top-level exposure | `result['edges']` / `result['fixed_edges']` | Decision #4 pins top-level keys, matching the existing `edge_weight_data`/`solution_data` pattern. |
| `edge_data_format` source | `getattr(problem, 'edge_data_format', None) or 'EDGE_LIST'` | Read from the parsed `EDGE_DATA_FORMAT` header; default to `EDGE_LIST` when absent (as pinned). |

## Failure / Correction Log

| Attempt | Evidence | Correction |
| --- | --- | --- |
| Initial `_section_content` stopped only at `*_SECTION`/EOF | `alb4000.hcp` returned 7999 edges vs 7997 data lines; a `FIXED_EDGES :` keyword header was being treated as a data line (skipped by int-parse, but its 2 edges bled into `edges`) | Added a keyword-header stop: a colon-containing line whose label is all-uppercase/digit/underscore with at least one letter breaks the section. Verified `alb4000` → 7997 edges, `fixed_edges == []`. |

## Affected Files (Detailed)

### python — `src/tsplib_parser/parser.py`

1. [parser.py L602](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L602) — new `_section_content(text, section_name)` helper (collects raw section lines; stops at EOF, next `*_SECTION`, or all-uppercase keyword header).
2. [parser.py L647](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L647) — new `_extract_edges(text, edge_data_format)` parsing `EDGE_DATA_SECTION` for `EDGE_LIST` (one pair/line) and `ADJ_LIST` (`from: to…` expansion), 0-based.
3. [parser.py L706](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L706) — new `_extract_fixed_edges(text)` parsing `FIXED_EDGES_SECTION` … `-1` into 0-based pairs; returns `[]` when absent.
4. [parser.py L156-166](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/tsplib_parser/parser.py#L156) — `parse_file` builds `result` with `edges`/`fixed_edges` initialized to `[]`, then sets them from the helpers (deriving `edge_data_format` from `problem.edge_data_format`, default `EDGE_LIST`).

No other files changed. `models.py`, `validation.py`, `exceptions.py` untouched.

## Change Checklist

- [x] 1.1 — `_extract_edges` parses `EDGE_LIST` (one `[from,to]` per line) and `ADJ_LIST` (`from: to1 to2 …` expanded), 0-based.
- [x] 1.2 — `_extract_fixed_edges` parses `FIXED_EDGES_SECTION` … `-1` into 0-based pairs; returns `[]` when absent.
- [x] 1.3 — `parse_file` returns top-level `edges` and `fixed_edges` keys (siblings of `problem_data`/`nodes`/`tours`/`metadata`).
- [x] `edge_data_format` derived from parsed metadata (`problem.edge_data_format`), default `EDGE_LIST`.
- [x] `models.py.StandardProblem` NOT modified.

## Validation Evidence

Run with `PYTHONPATH=src/submodules/Routing_data/src`:

```text
alb1000 edges: 1998 sample0: [999, 592]
alb4000 edges: 7997
alb4000 has fixed_edges: []
linhp318 fixed_edges: [[0, 213]]
berlin52 edges: [] fixed_edges: []
ADJ_LIST parse: [[0, 1], [0, 2], [1, 0], [1, 2], [2, 0], [2, 1]]
```

- `alb1000` → 1998 edge pairs (`~2000`, matches `awk` count), all 0-based and `>= 0`.
- `alb4000` → full 7997-edge EDGE_LIST without error; non-standard `FIXED_EDGES :` header correctly excluded from `edges`.
- `linhp318.tsp` → `fixed_edges == [[0, 213]]` (from `1 214`).
- File with no section (e.g. `berlin52.tsp`) → `fixed_edges == []` and `edges == []`.
- Synthetic `ADJ_LIST` fixture expands `from: to…` into 0-based `(from,toi)` pairs.
- `get_errors` on `parser.py` → **No errors found** (pre-existing `StringField`-vs-`Literal` warnings in untouched methods are resolved after the dict typing became concrete).

Known boundary: `FIXED_EDGES_SECTION` is the only fixed-edge header captured (per Task 1.2); the non-standard `FIXED_EDGES :` header in `alb4000.hcp` is deliberately not captured (out of scope for this task).

## Deep Analysis

### Why raw-text extraction and not `EdgeDataField`

`models.py.EdgeDataField` (L452) is a `MapT(key=edge, value=int)` where each `edge` is a `ListT(value=int, size=2)` — i.e. it expects **weighted triples** `from to weight`, not bare `from to` pairs. HCP `EDGE_LIST` lines are `from to` (no weight), so reusing it would misparse. Moreover, `StandardProblem` has no `FIXED_EDGES_SECTION` field at all, and its `parse` loop silently drops unknown sections. Raw-text scanning in the parser is therefore the minimal, localized change that keeps `models.py` a read-only reference.

### ADJ_LIST expansion semantics

Per TSPLIB, an ADJ_LIST section is a list of `from: to1 to2 … -1` lines, with the whole section terminated by an extra `-1`. Each line expands to `(from, toi)` for every neighbor `toi`. The `-1` tokens (per-list and final) are skipped. This yields one directed edge per neighbor, which is the natural representation for the adjacency column.

### Robustness: keyword-header termination

`_section_content` stops at EOF, the next `*_SECTION`, or a line like `FIXED_EDGES :` (all-uppercase keyword + optional colon). The colon check requires at least one alphabetic character in the label, so numeric ADJ_LIST labels (`5: 1 2`) are never mistaken for headers. This is what keeps `alb4000.hcp`'s trailing `FIXED_EDGES :` block out of the `edges` result.

## Review Notes

- The `result` dict initializes `edges`/`fixed_edges` to `[]` so that any code path that inspects keys before/without extraction is stable, then overwrites with real values.
- The `edge_data_format` derivation falls back to `EDGE_LIST` when the header is absent, matching Decision #3's "all 9 .hcp files declare EDGE_LIST" fact and the task's "default to EDGE_LIST if absent".
