---
title: Architecture Decisions
description: >
  Decision log for the TSPLIB95 ETL Converter. Records the accepted architecture
  decisions (standalone parser, hybrid matrix storage, 0-based indexing, DuckDB),
  the matrix implementation facts, corrections to earlier reviews, accepted
  tradeoffs, and the still-open items. Merged from the earlier design-analysis
  and matrix-review reference documents.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Created by merging the two earlier reference documents (design-analysis
          and matrix-review) into a single decision-log document. Dropped
          actor-critic narrative, effort estimates, and checklists.
related_files: [] # markdown relative links, or [] if none
tags: [analysis/architecture, notes/decision-log, analysis/matrix, analysis/database, analysis/parser, analysis/design, analysis/tradeoffs, analysis/validation, notes/architecture, review/matrix, review/design, analysis/storage]
---

# Architecture Decisions

This document is the decision log for the TSPLIB95 ETL Converter. It records what
was decided, why, and the consequences — plus the matrix implementation facts and
the accepted tradeoffs. It replaces the earlier design-analysis and matrix-review
documents.

## Architecture Decision Log

### D1 — Standalone parser implementation (not vendored tsplib95)

- **Decision**: The parsing layer in `src/tsplib_parser/` is our own implementation,
  written against the TSPLIB95 format specification and using the `tsplib95` library
  only as a design reference. It is **not** vendored code and **not** a dependency.
- **Context**: An earlier review wrongly framed the project as "vendored tsplib95
  code". The Field-based parsing system mirrors tsplib95's keyword structure but is
  our own codebase, built for ETL pipeline requirements (parse-only, no rendering).
- **Consequence**: The parser must be maintained and typed in-house. The public API
  (`FormatParser`) is clean; the legacy Field system carries type-safety debt (see
  Open Items).

### D2 — No edges table; `edge_weight_matrices` as hot/cold hybrid storage

- **Decision**: There is **no edges table**. Coordinate-based problems
  (`EUC_2D`, `GEO`, `ATT`, …) store node coordinates in `nodes` and compute
  distances on demand; EXPLICIT problems store the full n×n matrix as JSON in the
  separate `edge_weight_matrices` table.
- **Context**: A row-per-edge table would cause an O(n²) explosion — e.g. rbg443
  would need 196,249 rows. Keeping matrices separate from the `problems` table
  prevents buffer-pool pollution and keeps metadata queries light.
- **Consequence**: Matrix reads require a join, but it is a PK–PK one-to-one join
  and highly optimized.

### D3 — 1-based (TSPLIB) to 0-based (database) index conversion

- **Decision**: All node IDs are converted from TSPLIB95's 1-based indexing to
  0-based indexing during transformation.
- **Context**: TSPLIB95 is 1-based; the python/numpy ecosystem is 0-based.
- **Consequence**: Correct for analysis, but every node/edge operation must be
  tested with both indexing systems.

### D4 — Parse-only pipeline (no rendering)

- **Decision**: The converter parses and stores; it does not implement rendering,
  graph generation, or problem-solvability validation.
- **Context**: The target use case is batch ETL, not interactive single-file
  exploration. Edge iteration, distance queries, and solvability checks are
  analytical features outside the ETL scope.
- **Consequence**: Smaller, focused codebase; analytical features are deferred (see
  Open Items).

### D5 — DuckDB as the embedded analytical store

- **Decision**: Use DuckDB for storage, with dual JSON + Parquet output.
- **Context**: DuckDB is embeddable, analytical, and well suited to querying routing
  problem metadata and matrices.
- **Consequence**: Less ecosystem support than PostgreSQL (no server, limited ALTER),
  but no deployment overhead for the research pipeline.

### D6 — SHA-256 change detection in `file_tracking`

- **Decision**: `file_tracking` stores checksums and last-processed timestamps to
  enable incremental processing.
- **Context**: The dataset changes between runs; reprocessing everything is slow.
- **Consequence**: Only changed/new files are processed unless `--force` is used.

### D7 — `FormatParser` returns structured dicts

- **Decision**: The public parsing API returns plain dicts rather than Problem
  objects.
- **Context**: Dicts are serializable (JSON), batch-insertable, and avoid keeping
  parsed objects in memory.
- **Consequence**: Easy transformation/validation before insert; no object graph to
  manage.

### D8 — Schema evolution via idempotent DDL / drop-and-recreate (DuckDB)

- **Decision**: Schema changes are applied as idempotent DDL
  (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) in
  `src/converter/database/operations.py`; structural changes use drop-and-recreate
  of the affected table instead of FK UPDATE migrations.
- **Context**: There is no `migrations/` folder. DuckDB's ALTER support is limited,
  so in-place FK-level UPDATE migrations are not relied upon.
- **Consequence**: Migrations are inline in `operations.py` and must be written
  idempotently; destructive changes require a rebuild of the affected table.

### D9 — `solutions.routes` as `int[][]` for all problem types

- **Decision**: Solutions store routes as a 2D integer array, supporting single
  routes (TSP, ATSP, HCP, SOP) and multiple routes (VRP).
- **Context**: One structure must represent every routing solution shape.
- **Consequence**: No per-type solution tables are needed.

## Matrix Implementation Facts

`src/tsplib_parser/matrix.py` implements **9/9 TSPLIB95 matrix formats** (100%):

```python
TYPES = {
    'FULL_MATRIX': FullMatrix,           # complete n×n matrix
    'UPPER_DIAG_ROW': UpperDiagRow,      # upper triangle, row-wise, with diagonal
    'UPPER_ROW': UpperRow,               # upper triangle, row-wise, no diagonal
    'LOWER_DIAG_ROW': LowerDiagRow,      # lower triangle, row-wise, with diagonal
    'LOWER_ROW': LowerRow,               # lower triangle, row-wise, no diagonal
    'UPPER_DIAG_COL': UpperDiagCol,      # upper triangle, column-wise, with diagonal
    'UPPER_COL': UpperCol,               # upper triangle, column-wise, no diagonal
    'LOWER_DIAG_COL': LowerDiagCol,      # lower triangle, column-wise, with diagonal
    'LOWER_COL': LowerCol,               # lower triangle, column-wise, no diagonal
}
```

(`FUNCTION` is not a matrix format — it means weights come from coordinates or a
function, so no matrix class is needed.)

### Index formulas (O(1) element access)

```python
# Full matrix (row-major):           i * size + j
# Lower triangle (row-wise):         integer_sum(i) + j
# Upper triangle (row-wise):         integer_sum(n, n - i) + (j - i)
```

Triangular numbers are memoized via `_int_sum`, so repeated queries are O(1).

### Row/column duality

Column variants reuse the row variants by swapping indices
(`HalfMatrix._fix_indices`): `UpperCol` inherits `LowerRow`, `LowerCol` inherits
`UpperRow`, `UpperDiagCol` inherits `LowerDiagRow`, `LowerDiagCol` inherits
`UpperDiagRow`. This duality is mathematically sound and matches the reference
implementation.

### Dimension validation — status: CLOSED

An earlier review flagged "no validation that `len(numbers)` matches the expected
size". That gap has been closed: `Matrix.__init__` now computes the expected size
and raises `ParseError` on mismatch, e.g. a `LOWER_ROW` matrix with `dimension=10`
must have exactly 45 elements.

## Accepted Tradeoffs

- **DROP/RECREATE vs FK UPDATE (DuckDB)**: structural schema changes drop and
  recreate the affected table rather than relying on FK-level UPDATE migrations,
  because DuckDB's ALTER support is limited. Cost: destructive rebuilds; benefit:
  reliable, idempotent schema application.
- **Hybrid storage**: explicit matrices stored as full JSON arrays (converted from
  any of the 9 input formats). Cost: JSON blobs are larger than raw triangular
  storage; benefit: uniform query surface and simple export.
- **`rbg443` note**: the largest matrix in the dataset is rbg443.atsp — 443 nodes,
  196,249 entries, ~770 KB JSON. This is the canonical case that justifies the
  separate `edge_weight_matrices` table and rules out a row-per-edge design.
- **No per-edge rows**: edge weights are never stored one row per edge; dense
  graphs would make the database unusable.

## Open Items

- **Tour index conversion verification**: whether `.tour` files convert node IDs
  1-based → 0-based is still unverified (potential data-corruption risk; flagged
  HIGH in earlier review).
- **Type-safety debt**: the legacy Field system in `src/tsplib_parser/` still
  carries a large number of static-analysis (Pylance) errors; `FormatParser` (the
  public API) is clean.
- **Test coverage**: 63% is below the 80%+ production target; column-format matrix
  classes and edge cases remain thinly tested.
- **On-demand distance queries**: for coordinate-based problems there is no
  convenient way to query d(i,j) without reading all nodes — a candidate for a
  future helper.
