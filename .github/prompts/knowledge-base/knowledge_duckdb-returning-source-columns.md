---
title: "Knowledge: DuckDB INSERT…RETURNING source-column limitations and the temp_id mapping fallback"
description: >
  Documents the DuckDB 1.5.5 behavior where INSERT…SELECT…RETURNING can only
  reference columns that appear in the INSERT target (source columns are not
  referenceable unless they are also inserted), and the reliable row-order
  fallback for building a temp_id → real_id mapping in bulk ETL inserts.
created: 2026-08-27
author:
  - "[[Lucas Galdino]]"
tags: [analysis/duckdb, guide/database, benchmark/etl, notes/routing-data]
links:
  - "[plan-routingDatabaseRebuild.prompt.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/plan-routingDatabaseRebuild.prompt.md)"
  - "[walkthrough_3-1_3-2_3-3_3-4_3-5.md](file:///home/lucas_galdino/chimera/gpu_accelerated_clean/src/submodules/Routing_data/.github/prompts/task-resolutions/walkthrough_3-1_3-2_3-3_3-4_3-5.md)"
---

# DuckDB INSERT…RETURNING source columns + temp_id mapping fallback

## Objective

Explain two closely related DuckDB behaviors that matter when bulk-inserting
rows whose generated ids must be mapped back to an in-memory source key
(`temp_id`): (1) what `RETURNING` can and cannot reference, and (2) the safe
fallback for capturing the mapping by source row order. Verified against
DuckDB 1.5.5 (2026-08).

## 1. What `RETURNING` can reference in `INSERT … SELECT`

Given:

```sql
INSERT INTO problems (name, type, comment)
SELECT name, type, comment FROM problems_temp
RETURNING id, problems_temp.temp_id   -- ❌ fails
```

`RETURNING` can reference:

- columns of the **target** table (`problems.id`), and
- columns **produced by the INSERT's SELECT output** (i.e. columns that are
  actually inserted into a target column).

It **cannot** reference a source-table column that is not also selected into a
target column. Observed error:

```text
BinderException: Binder Error: Referenced column "temp_id" not found in FROM clause!
Candidate bindings: "type", "comment", "name"   -- only the SELECT-output columns
```

Qualifying the source table does not help:

```text
BinderException: Binder Error: Referenced table "problems_temp" not found!
```

The candidate bindings are exactly the INSERT output columns. So the intended
"return source columns" pattern requires `temp_id` to be part of the INSERT
target — which is usually undesirable (you don't want to persist a batch ordinal).

### Also rejected: the subquery form

The pattern `CREATE TABLE … AS SELECT … FROM (INSERT … RETURNING …) p` fails in
1.5.5 with:

```text
ParserException: Parser Error: syntax error at or near "INTO"
```

`INSERT` is not valid as a subquery source in this version.

## 2. The reliable fallback: RETURNING id zipped to temp_id by row order

When the source is a **single registered DataFrame / temp table** scanned in a
**single process** with no `ORDER BY` or parallel distribution, DuckDB emits
`RETURNING id` rows in the same order as the source rows. So:

```python
returned_ids = conn.execute("""
    INSERT INTO problems (name, type, comment)
    SELECT name, type, comment FROM problems_temp
    RETURNING id
""").fetchall()
ids = [row[0] for row in returned_ids]
mapping = dict(zip([pr['temp_id'] for pr in all_problems], ids))
```

Because `all_problems` is built in `temp_id` order and `problems_temp` is created
from it without reordering, `ids[i]` is the real id of the row whose `temp_id ==
i + 1`. Verified output: `returned ids: [1, 2, 3, 4]` → `mapping {1:1, 2:2, 3:3,
4:4}`.

> [!WARNING]
> This row-order assumption is only safe for a single-threaded scan of an
> in-process temp table / registered DataFrame. If the source could be
> reordered (parallel scan, external table, explicit sort), you must instead
> capture the mapping by inserting a real (temporary) source key column into a
> scratch table and joining on it.

## 3. Registering the mapping for downstream joins

The python-built mapping can be registered as a DataFrame and joined to other
registered DataFrames (verified in DuckDB 1.5.5):

```python
conn.register('problem_id_mapping', pd.DataFrame([
    {'temp_id': t, 'real_id': r} for t, r in mapping.items()
]))
conn.execute("""
    INSERT INTO nodes (problem_id, node_id)
    SELECT m.real_id, n.node_id
    FROM nodes_temp n JOIN problem_id_mapping m ON n.temp_problem_id = m.temp_id
""")
```

Joining two `conn.register`'d DataFrames works normally.

## 4. pandas → array columns (`INTEGER[][]`)

A pandas column of python nested lists (with `None` for non-graph rows) converts
transparently to `INTEGER[][]` / `LIST(LIST(INTEGER))` on INSERT. Float-typed
values in the nested lists are cast to `INTEGER` automatically (verified:
`[[0.0, 10.0], [10.0, 0.0]]` stored as `[[0, 10], [10, 0]]`). Mixed
`None`-and-lists columns work as long as the non-null values are homogeneous
nested lists.

## References / Sources

- Verified empirically against DuckDB 1.5.5 in sandbox scripts during Batch 3 of
  the Routing_data database rebuild (2026-08-27).
- Decision #10 of the rebuild plan pins `INSERT…RETURNING temp_id`; the row-order
  fallback is the documented, accepted alternative when the installed DuckDB
  rejects source-column RETURNING.
