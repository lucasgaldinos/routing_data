---
title: "Knowledge: converter DB path resolution — database_path vs -o"
description: >
  How the converter resolves its DuckDB output path: the `process` command
  derives it from `-o/--output` as `<output>/db/routing.duckdb` and never reads
  `config.yaml`'s `database_path`; the canonical DB is `db/routing.duckdb`.
created: "2026-08-28"
author: "[[GitHub Copilot]]"
tags:
  - benchmark/etl
  - benchmark/database
  - analysis/duckdb
  - notes/routing-data
links:
  - "[plan-routing-schema-v2.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.md)"
  - "[walkthrough_2-3_2-4.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_2-3_2-4.md)"
---

# Knowledge: converter DB path resolution — `database_path` vs `-o`

## Objective

Explains how the TSPLIB converter chooses the DuckDB file it writes, so a future task never assumes `config.yaml`'s `database_path` controls the CLI. Covers the `process` command's path derivation, who actually reads `database_path`, and how to target the canonical `db/routing.duckdb`. It deliberately does NOT cover the schema v2 DDL or insert dispatch (see the schema-v2 plan Batches 1–2).

## How to Use This Knowledge

Apply when answering "where did `converter process` write the DB?", when wiring any config/env-driven DB path (e.g. Batch 8's config-driven consumer fix), or before changing defaults in `config.yaml` / `converter/config.py` / `converter/cli/commands.py`. It corrects a common misconception: editing `database_path` does NOT change what `converter process` does.

---

## 1. The `process` command builds its own DB path

`src/converter/cli/commands.py` — the `process` command:

```python
@click.option('--output', '-o', type=click.Path(),
              default='./datasets',
              help='Output directory for database (default: ./datasets)')
...
db_path = Path(output) / 'db' / 'routing.duckdb'
```

So `uv run converter process -i <dir>` with **no `-o`** writes to `./datasets/db/routing.duckdb` **relative to the process CWD** — not to `config.yaml`'s `database_path`. The same is true for the `converter_cli.py` shim and the `converter` console-script entry point: both route to the same `cli.commands.process`, so there is no difference in path resolution between "the entry point" and "the CLI shim".

| Invocation | DB written | Notes |
| --- | --- | --- |
| `converter process -i X` (no `-o`) | `./datasets/db/routing.duckdb` (CWD-relative) | stale-path failure class if CWD is the repo root |
| `converter process -i X -o <dir>` | `<dir>/db/routing.duckdb` | canonical reached when `<dir>` = submodule root |
| `-o /tmp/routing_rebuild_v2` (Batch 7) | `/tmp/routing_rebuild_v2/db/routing.duckdb` | scratch, then promoted in 7.2 |

## 2. Who actually reads `database_path`

`config.yaml`'s `database_path` is consumed only by `converter/config.py::load_config()` (default `"config.yaml"`), which returns a `ConverterConfig` dataclass. **No CLI command in `src/` calls `load_config`** — the value is documentation-grade today. It is written by `converter init` from the template embedded in `commands.py` (which still carried the stale `./datasets/db/routing.duckdb` default at the time of writing).

The stale default lived in three places:

| Location | Value before Task 2.4 | State |
| --- | --- | --- |
| `config.yaml` L15 | `./datasets/db/routing.duckdb` | fixed → `./db/routing.duckdb` (Task 2.4) |
| `src/converter/config.py` L21 (dataclass default) | `./datasets/db/routing.duckdb` | still stale (out of 2.4 scope) |
| `src/converter/cli/commands.py` L360 (`init` template) | `./datasets/db/routing.duckdb` | still stale (out of 2.4 scope) |

## 3. Path resolution is CWD-relative

`load_config()` reads `config.yaml` relative to CWD and resolves **no** relative paths inside it against the file's own directory. So a `database_path` of `./db/routing.duckdb` means `<CWD>/db/routing.duckdb` — the submodule's canonical DB only when the process CWD is the submodule root (or `-o` points there).

---

## References / Sources

- [commands.py `process`](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/cli/commands.py#L132) — `-o` option + `db_path = Path(output) / 'db' / 'routing.duckdb'`
- [config.py](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/src/converter/config.py) — `ConverterConfig.database_path` + `load_config()`
- [config.yaml](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/config.yaml) — canonical default + override comment (Task 2.4)
- [plan-routing-schema-v2.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routing-schema-v2.prompt.md) — Batch 7 rebuild/promote, Batch 8.2 config-driven repoint
