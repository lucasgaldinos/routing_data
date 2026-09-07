---
title: "Walkthrough: Task 2.7 — Mermaid ER diagram of schema v2"
task_id: "2.7"
description: >
  Renders the implemented schema v2 as a single reviewable Mermaid `erDiagram`
  knowledge-base artifact: hub `problems`, five per-type tables, and three
  satellites, with every FK edge traceable to a `REFERENCES` clause in
  `operations.py` and `solutions` visibly marked on-hold.
created: 2026-08-31
author:
  - "[[Lucas Galdino]]"
  - "[[GitHub Copilot]]"
status: "in-review"
tags:
  - notes/5w2h
  - analysis/er-diagram
  - analysis/schema-design
  - analysis/duckdb
  - notes/routing-data
links:
  - "[plan-routing-schema-v2.prompt.new.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.new.md)"
  - "[knowledge_schema-v2-er.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_schema-v2-er.md)"
---

# Walkthrough: Task 2.7 — Mermaid ER diagram of schema v2

## Objective

Produce a knowledge-base Mermaid `erDiagram` of the **implemented** schema v2
(source of truth: `operations.py` `_initialize_schema`): the thin `problems`
hub, the five self-contained per-type tables, and the three satellites — one
node per table, one relationship per FK, PKs annotated, and the `solutions`
satellite visibly marked frozen/on-hold. This file becomes the review artifact
for any future schema change.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| Source of truth (DDL) | [operations.py `_initialize_schema`](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/database/operations.py#L42) | 9 tables: hub (L56) + 5 type tables (L69–L126) + 3 satellites (L127–L158); sequences `problems_seq`/`file_tracking_seq`/`solutions_seq` |
| FK clauses | `operations.py` | every type table + `edge_weight_matrices` use `problem_id ... PRIMARY KEY REFERENCES problems(id)` (1:1); `solutions`/`file_tracking` use own `id` PK + `problem_id ... REFERENCES problems(id)` (1:N) |
| Plan decision pins | [plan-routing-schema-v2.prompt.new.md §Decisions](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.new.md) | Decision 1 (hub topology), Decision 2 (satellites), Decision 3 (array columns), Decision 11 (solutions parked) |
| Schema sketch | plan `Target schema v2 (DDL sketch)` | matches `operations.py`; `solutions` shown commented out in the sketch — included in diagram but flagged on-hold |

## Impact Analysis

### Design Decisions

| Decision point | Choice | Rationale |
| --- | --- | --- |
| Node granularity | one node per table (9 total) | matches the DoD "9 table nodes"; keeps the diagram legible |
| Cardinality | type tables + `edge_weight_matrices` = 1:1 (`problem_id` is PK); `solutions`/`file_tracking` = 1:N (own `id` PK, FK not unique) | derived directly from the DDL key declarations, not from the plan sketch |
| `solutions` treatment | included in the diagram but flagged `FROZEN` in the relationship label, legend, and §4 | it exists in the DDL but is parked (Decision 11 / 2026-08-30 ruling) |
| Array columns | shown as `double[][]`/`int[]`/`int[][]` attributes with decision notes | visualizes Decision 3 without a separate `nodes` table |
| Diagram type keyword | `erDiagram` + `direction TB` (not `erDiagram TD`) | `erDiagram` takes direction as a separate statement; the previous `erDiagram TD` first line was invalid syntax that rendered only by silent tolerance |
| Layout | top-to-bottom (`direction TB`) | user-selected (vscode_askQuestions) — hub on top, tables below |
| Attribute detail | full detail retained | user-selected — keep all columns as-is |
| Edge labels | simplified to short verbs `owns` / `has` | user-selected; decision context stays in §2 legend. `solutions` kept as `has (FROZEN)` to preserve the on-hold signal |
| Theme | minimal neutral light palette (`config:` YAML block) | user-selected ("neutral palette, do not exaggerate"); matches the GitHub-light rendering of the knowledge-base doc |
| Title | `title: Routing_data schema v2` in YAML frontmatter | user-selected — adds context when embedded/exported |

### Readability rework (2026-08-31)

Applied the user-selected options to the mermaid block:

- **First line fixed:** `erDiagram TD` → `erDiagram` + `direction TB` (a real syntax correction; per the Mermaid reference `erDiagram` declares direction via a separate `direction TB/LR` statement, not on the keyword line).
- **YAML frontmatter added:** `title: Routing_data schema v2` and a minimal `theme: base` neutral light palette (`primaryColor #f6f8fa`, `primaryTextColor #24292f`, `primaryBorderColor #d0d7de`, `lineColor #57606a`, `edgeLabelBackground #ffffff`, `nodeTextColor #24292f`, `background #ffffff`) — kept deliberately small per "do not exaggerate on customization".
- **Edge labels simplified:** `"problem_id (Decision N)"` → `"owns"` for the hub→type-table and hub→matrix edges, `"has"` for the hub→`file_tracking` edge, and `"has (FROZEN)"` for `solutions` (keeps the mandatory on-hold marking while staying short).
- **Attributes untouched:** full column detail retained per user choice.

### DoD Compliance

| Clause | Status | Evidence |
| --- | --- | --- |
| File exists with repo-standard frontmatter | ✅ | `knowledge_schema-v2-er.md` created with title/description/created/status/author/type/scope/modifications/related_files/tags |
| Diagram has 9 table nodes | ✅ | `problems`, `tsp_problems`, `atsp_problems`, `cvrp_problems`, `hcp_problems`, `sop_problems`, `edge_weight_matrices`, `solutions`, `file_tracking` |
| Every FK edge traceable to a `REFERENCES` clause | ✅ | 8 relationships; §3 table maps each to its `REFERENCES problems(id)` line in `operations.py` (L70/L83/L92/L107/L117/L128/L139/L152) |
| `solutions` visibly marked on-hold | ✅ | `has (FROZEN)` relationship label, legend row, and §4 on-hold note |

### Validation

- Initial render: extracted the Mermaid block with `mmdc` (mermaid-cli) to a PNG — exit 0, no parse errors, all 9 nodes and 8 edges present.
- **Post-rework re-validation:** re-extracted and re-rendered after the readability changes (title + config frontmatter, `direction TB`, simplified labels) — exit 0, no parse errors, all 9 nodes and 8 edges present. Temp files cleaned up afterward.

## Affected Files

| File | Change |
| --- | --- |
| [knowledge_schema-v2-er.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_schema-v2-er.md) | **New.** Knowledge-base ER diagram: frontmatter + `erDiagram` (9 nodes, 8 FK edges), decision legend (§2), FK traceability table (§3), on-hold surface note (§4), references. |

No source code changed — this is a documentation-only task.

## Checklist

- [x] Read authoritative DDL in `operations.py` `_initialize_schema`
- [x] Rendered all 9 tables with PK/FK annotations
- [x] Added 8 FK relationships, each traceable to a `REFERENCES` clause
- [x] Marked `solutions` frozen/on-hold
- [x] Added legend mapping edges → Decisions 1/2/3
- [x] Repo-standard frontmatter (title, description, created, status, author, type, scope, modifications, related_files, tags)
- [x] Validated diagram renders via `mmdc` (no syntax errors)
- [x] Created walkthrough and linked it from the knowledge file

## References

- Plan: [plan-routing-schema-v2.prompt.new.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.new.md)
- Knowledge: [knowledge_schema-v2-er.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_schema-v2-er.md)
