---
title: "Walkthrough: Tasks 2.3–2.4 — Venv hygiene: sys.path hack + config.yaml default"
task_id: "2.3–2.4"
description: >
  Retires the converter_cli.py sys.path hack (redundant under the editable
  install) and points config.yaml's database_path default at the canonical
  db/routing.duckdb, documenting the -o override the CLI actually uses.
created: "2026-08-28"
author: "[[GitHub Copilot]]"
status: "in-review"
tags:
  - notes/5w2h
  - benchmark/etl
  - notes/routing-data
  - analysis/duckdb
links:
  - "[plan-routing-schema-v2.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.md)"
  - "[knowledge_converter-db-path-resolution.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_converter-db-path-resolution.md)"
---

# Walkthrough: Tasks 2.3–2.4 — Venv hygiene: sys.path hack + config.yaml default

## Objective

- **2.3** — Remove the `sys.path.insert(0, .../src)` hack from `converter_cli.py` (L13); the editable install + `converter` entry point make it redundant.
- **2.4** — Replace config.yaml's stale `database_path: "./datasets/db/routing.duckdb"` default (a nonexistent directory) with the canonical `db/routing.duckdb`, and document the override, because `converter process` does not read `database_path`.

## Context: Code ↔ Documentation ↔ Data Correlation

| Artifact | Location | Relevant Observation |
| --- | --- | --- |
| CLI shim | [converter_cli.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/converter_cli.py) | L13 `sys.path.insert(0, .../src)` — the cargo-culted hack (removed) |
| Console entry | [pyproject.toml L48–49](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/pyproject.toml#L48) | `[project.scripts] converter = "converter.cli.commands:cli"` — canonical entry point |
| Config default | [config.yaml L15](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/config.yaml#L15) | stale `./datasets/db/routing.duckdb` (dir does not exist) → canonical `./db/routing.duckdb` |
| CLI path derivation | [commands.py L132/L136](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/cli/commands.py#L132) | `-o` default `./datasets`; `db_path = Path(output)/'db'/'routing.duckdb'` — ignores `database_path` |
| Config loader | [config.py L21/L37](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/config.py#L21) | `ConverterConfig.database_path` default; `load_config()` reads yaml; nothing in `src/` calls it for the CLI |
| Canonical DB | `db/routing.duckdb` (main repo root, 21 MB; submodule `db/` created by Batch 7.2) | plan's canonical path (Task 7.2) |
| Sibling script | [convert_vrp.py L13](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/convert_vrp.py#L13) | identical `sys.path.insert` hack; uses `converter.api.process_directory` (Task 2.1 fate) |

---

## Impact Analysis

### Root Cause

- **2.3** — `converter_cli.py:13` injected its own `src/` dir onto `sys.path`. After Decision 8 (editable path source `routing-data = { path = ... }`), the `converter` entry point and the shim both resolve `converter` through the editable install, so the hack is dead weight — and it is what made the old walkthrough believe PYTHONPATH was "mandatory".
- **2.4** — config.yaml's default `./datasets/db/routing.duckdb` points at a directory that does not exist. A default that silently resolves to the wrong DB is the same failure class as the stale 48.5 MB husk (Decision 9). Worse, the default is misleading: `converter process` never reads it.

### Design Decisions

| Component | Before | After | Rationale |
| --- | --- | --- | --- |
| `converter_cli.py` | `import sys`, `import os`, `sys.path.insert(0, .../src)` (L9–14) | plain `from converter.cli.commands import cli` | editable install resolves the package; no path surgery needed |
| `config.yaml` `database_path` | `./datasets/db/routing.duckdb` | `./db/routing.duckdb` + override comment | canonical name; documents that `process` uses `-o`, not this value |
| override documentation | none | config comment block (Task 2.4) | DoD alternative (B): `-o <submodule-root>` targets canonical DB |

### Failure / Correction Log

| Attempt / Event | Evidence Read | Correction / Decision | Outcome |
| --- | --- | --- | --- |
| (none) — no failed attempts; baseline DoD verified before editing | `uv run converter --help` exit 0; `import cli` exit 0 (pre-edit) | N/A | baseline matches plan (PYTHONPATH redundancy proof) |

---

## Affected Files

### python (1 file)

1. [converter_cli.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/converter_cli.py#L9) — removed `import sys`, `import os`, the `# Add src to path` comment, and the `sys.path.insert(...)` line (L9–14 → L9).

### YAML (1 file)

1. [config.yaml](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/config.yaml#L15) — `database_path: "./db/routing.duckdb"` + 13-line comment documenting that `process` derives its DB path from `-o` and how to target the canonical DB.

### Not touched (scope boundary, reported)

- `convert_vrp.py` L13 — identical `sys.path.insert` hack, but its `converter.api` dependency is governed by **Task 2.1** (retire vs rewrite `api.py`); out of 2.3's `Where`.
- `tests/**` (11 files) — `sys.path.insert(0, .../src)` test import shims; out of 2.3 scope (Task 6.3 migrates `from src.converter` imports).
- `src/converter/config.py` L21 and `src/converter/cli/commands.py` L360 — carry the same stale `database_path` default (dataclass + `init` template); out of 2.4's `Where` (config.yaml only).

## Change Checklist

- [x] 1. `converter_cli.py` — sys.path hack removed; `uv run converter --help` exits 0
- [x] 2. `converter_cli.py` — `uv run python -c "from converter.cli.commands import cli"` exits 0
- [x] 3. `converter_cli.py` — shim runs directly: `uv run python .../converter_cli.py --help` exits 0
- [x] 4. `config.yaml` — `database_path` → canonical `./db/routing.duckdb`; `load_config()` returns it
- [x] 5. `config.yaml` — override documented (comment); `process --help` confirms `-o` default `./datasets`
- [x] 6. Grep — remaining `sys.path` manipulation classified and reported

## Validation Evidence

| Check | Evidence | Result | Boundary / Follow-up |
| --- | --- | --- | --- |
| `uv run converter --help` | exit 0, usage header printed | ✅ pass | baseline also exit 0 (pre-edit) — no regression |
| `uv run python -c "from converter.cli.commands import cli"` | `OK cli`, exit 0 | ✅ pass | import resolution via editable install |
| shim direct run `converter_cli.py --help` | exit 0 | ✅ pass | proves the shim needs no `sys.path` surgery |
| grep `sys.path` (excl `.venv`) | 12 hits: 11 × `tests/**` + 1 × `convert_vrp.py` L13 | ✅ converter_cli.py clean | tests → Task 6.3; convert_vrp.py → Task 2.1 boundary (reviewer decision) |
| `load_config('config.yaml').database_path` | `'./db/routing.duckdb'` | ✅ pass | value read correctly from YAML |
| `converter process --help` | `-o, --output PATH ... default: ./datasets` | ✅ pass | proves DB path is `-o`-driven, not `database_path`-driven |
| `converter process` without `-o` → canonical DB (DoD alt A) | NOT executed — unreachable via config edit | n/a | `process` ignores `database_path` (commands.py L136); DoD alt (B) taken instead |
| YAML parse / lint | config.yaml: no errors; converter_cli.py: pre-existing "missing stubs" Pylance notes on unchanged import | ✅ | stub warnings are not new (editable pkg ships no py.typed) |

---

## Deep Analysis

**Why the DoD alternative (A) is unreachable from config.yaml.** Task 2.4's DoD
offers two alternatives: `converter process` without `-o` targets the canonical
DB (file-tracking row), **or** the override is documented in config comments.
`process` computes `db_path = Path(output) / 'db' / 'routing.duckdb'` with
`output` defaulting to `./datasets` (commands.py L132/L136); it never calls
`load_config`. Therefore no edit to `config.yaml` alone can change what a
flag-less run writes — the documented-override alternative (B) is the only
correct outcome, and that is what was delivered. The doc comment records the
actual mechanism (`-o <submodule-root>` → `<submodule-root>/db/routing.duckdb`,
which is the canonical path) so Batch 7/8 implementers are not misled.

**Why the "no sys.path manipulation remains in the repo" clause is scoped.**
The DoD's hygiene clause, read literally against the whole submodule, cannot be
satisfied by Task 2.3 alone: `convert_vrp.py` (sibling entry script importing
`converter.api.process_directory`) and 11 `tests/**` files still carry
`sys.path.insert`. Both are explicitly owned elsewhere — `convert_vrp.py`'s fate
is decided by Task 2.1 (retire vs rewrite `api.py`), and the test shims are
Task 6.3's sweep target. Per the task's `Where` (converter_cli.py L13 only) and
the "do not touch anything else" constraint, this was reported rather than
silently "fixed" by scope creep. The production entry-point surface (the
`converter` console script and its shim) is now free of sys.path manipulation,
which is what the plan's mental model ("converter_cli.py:13 already does...")
refers to. The reviewer should confirm whether the hygiene clause should extend
to `convert_vrp.py` (recommend folding into Task 2.1) — see Review Notes.

**Incidental findings (out of scope).** The stale `database_path` default
persists in `src/converter/config.py` L21 (dataclass default) and
`src/converter/cli/commands.py` L360 (`converter init` template). Both produce
the same misleading `./datasets/db/routing.duckdb`. Recommend a follow-up
(could fold into Task 6.2's config consolidation or a one-line task).

For the full resolution model, see
[knowledge_converter-db-path-resolution.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/knowledge-base/knowledge_converter-db-path-resolution.md).

---

## Additional Findings

> [!NOTE]
> The `.venv/` tree also contains `sys.path` usage, but it is vendored
> third-party (numpy/pandas/psutil) and `activate_this.py` — excluded from the
> grep by design; it is not repo source.

---

## Review Notes

- **Task 2.3 DoD** — functional clauses pass (both commands exit 0; shim runs
  directly). The "no `sys.path` manipulation remains in the repo" clause is met
  for the task's `Where` (converter_cli.py). Remaining hits: `convert_vrp.py` L13
  (recommend folding into Task 2.1's api.py retirement) and `tests/**` (Task 6.3).
  Please confirm that boundary reading.
- **Task 2.4 DoD** — alternative (B) taken (override documented in config
  comments). The `-o`-driven path derivation was verified via `--help` + source.
  `converter process` was intentionally **not** run: it would write
  `./datasets/db/routing.duckdb` (creating files outside the task's footprint)
  and would hit Task 1.5's still-broken `get_problem_stats` at the end of the run.
