---
title: "Walkthrough: Tasks 4.1–4.3 — Setup + Database Rebuild"
task_id: "4.1–4.3"
description: >
  Executes Batch 4 of the Routing_data database rebuild: confirms pandas is
  declared, removes the stray submodule .venv, and runs the pinned rebuild from
  the repo root to produce the canonical db/routing.duckdb.
created: "2026-08-27"
author: "[[Lucas Galdino]]"
status: "in-review"
tags:
  - notes/5w2h
  - benchmark/etl
  - benchmark/database
  - analysis/duckdb
  - review/implementation-plan
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
---

# Walkthrough: Batch 4 — Setup + Database Rebuild

## Objective

Complete the database rebuild: (4.1) confirm pandas is declared in
`pyproject.toml` (no action needed), (4.2) delete the stray
`src/submodules/Routing_data/.venv`, and (4.3) run the pinned `process` command
from the repo root, copy the produced DB to `db/routing.duckdb`, and clear the
stale husk.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| `pyproject.toml` | [pyproject.toml L29](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/pyproject.toml#L29) | `"pandas>=2.3.3"` already declared (Task 4.1 → no-op) |
| stray venv | `src/submodules/Routing_data/.venv` | 171 MB, untracked (`git ls-files` empty), acquired during testing |
| `db/routing.duckdb` | [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb) | 12 KB empty husk before rebuild |
| CLI entry | [converter_cli.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/converter_cli.py) | Inserts its own `src` dir on `sys.path`; `process` writes to `<output>/db/routing.duckdb` |
| config.yaml | [config.yaml](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/config.yaml) | Default `database_path: ./datasets/db/routing.duckdb` (not used — `-o` overrides) |
| input | `datasets/problems/` | Contains atsp/, hcp/, sop/, tour/, tsp/, vrp/ |

---

## Impact Analysis

### Root Cause

The canonical `db/routing.duckdb` was an empty 12 KB husk. Batches 1–3 changed
the parser/transformer/worker/DB schema, so the DB had to be rebuilt from
`datasets/problems` using the local submodule source, then the freshly produced
DB installed at the canonical path.

### Design Decisions

| Component | Before | After | Rationale |
| --- | --- | --- | --- |
| Rebuild interpreter | bare `python` (global venv) | `uv run python` (root project env) | Global venv lacks `click` → `ModuleNotFoundError`; `uv run` resolves root env with all ETL deps |
| Source resolution | (installed git-main `routing-data`) | `PYTHONPATH=src/submodules/Routing_data/src` | Forces local submodule source; avoids git-main shadowing (per TODO) |
| Output dir | — | `/tmp/routing_rebuild` (cleaned first) | Isolated scratch; `--force` + clean dir guarantees no stale tables |
| Stale husk removal | — | `rm -f datasets_processed/db/routing.duckdb` (repo root) | Pinned command; repo-root path does not exist → no-op; submodule's git-tracked copy intentionally left alone |

### Failure / Correction Log

| Attempt / Event | Evidence Read | Correction / Decision | Outcome |
| --- | --- | --- | --- |
| `PYTHONPATH=… python converter_cli.py --help` | `ModuleNotFoundError: No module named 'click'` | Switch to pinned `uv run python` (root env has click/duckdb/pandas) | `--help` exits 0; REQ-2 import fixed (relative `from .models`) |
| Full rebuild | CLI logs | N/A | 198 processed, 0 failed; per-type counts match pinned expectations |

---

## Affected Files

### Setup (2 items)

1. `src/submodules/Routing_data/.venv` — deleted (`rm -rf`; untracked, 171 MB).
2. `pyproject.toml` — **unchanged** (pandas already declared; Task 4.1 no-op).

### Rebuild (1 file)

1. [db/routing.duckdb](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/db/routing.duckdb) — replaced 12 KB husk with the 21 MB rebuilt DB (copied from `/tmp/routing_rebuild/db/routing.duckdb`).

---

## Change Checklist

- [x] 1. Task 4.1 — pandas already declared; no installation work (no-op).
- [x] 2. Task 4.2 — stray `.venv` removed; repo-root `.venv` untouched.
- [x] 3. Task 4.3 — rebuild run; DB copied to `db/routing.duckdb`; stale husk `rm` run (no-op at repo root).
- [x] 4. Sanity query on the copied DB confirms 198 problems / 80 matrices / 43 solutions.

---

## Validation Evidence

| Check | Evidence | Result | Boundary / Follow-up |
| --- | --- | --- | --- |
| pandas declared | `pyproject.toml` L29 `"pandas>=2.3.3"` | pass | Task 4.1 needs no action |
| stray venv removed | `ls src/submodules/Routing_data` | pass — no `.venv` | repo-root/global venvs untouched |
| CLI imports (REQ-2) | `uv run … converter_cli.py --help` → exit 0 | pass | relative `from .models` confirmed |
| Rebuild | CLI: `Successful: 198`, `Failed: 0`, time 2.33s | pass | `db/routing.duckdb` 21 MB |
| DB populated | duckdb query: problems 198 (ATSP=19,CVRP=16,HCP=9,SOP=41,TSP=113), matrices 80, nodes 334813, solutions 43 | pass | full SQL assertion suite deferred to Batch 5 (reviewer) |
| stale husk | repo-root `datasets_processed/` absent; pinned `rm` no-op | pass | submodule `datasets_processed/db/routing.duckdb` is git-tracked → out of pinned scope |

---

## Deep Analysis

**Why `uv run` and not bare `python`:** the active shell environment is the uv
global venv, which does not have `click` installed. The pinned rebuild command
uses `uv run python` from the repo root, which binds the root project's virtual
environment (where `click`/`duckdb`/`pandas` are declared in the root
`pyproject.toml`). Using bare `python` would fail at import. This is exactly the
"main venv installed from git main" drift the plan warns about — hence
`PYTHONPATH=src/submodules/Routing_data/src` is mandatory so the local source is
imported, not the installed package.

**Husk reconciliation:** the plan's `rm -f datasets_processed/db/routing.duckdb`
is relative to the repo root, where `datasets_processed/` does not exist — the
command is a no-op by design. A separate, git-tracked
`src/submodules/Routing_data/datasets_processed/db/routing.duckdb` (48.5 MB)
exists inside the submodule; it is not a "stale empty husk" and is outside the
pinned scope, so it was left untouched. If cleanup of that tracked file is
desired it is a separate decision.

---

## Additional Findings

> [!NOTE]
> The output DB lives at `db/routing.duckdb` (canonical). The root
> `pyproject.toml` workspace `[tool.uv.workspace]` entry pointing to
> `data/Routing_data/vrp_database` remains stale (deferred) — `uv run` still
> resolved the root project env without issue.

---

## Review Notes

- Batch 5 (Task 5.1, reviewer) runs the full SQL assertion suite + spot-checks
  against the new `db/routing.duckdb`; not executed here (out of implementer scope).
- Confirm the `solutions` count (43) against the Batch-5 "all solutions linked"
  assertion — the CLI's tour sidecar discovery produced 43 rows this run.
