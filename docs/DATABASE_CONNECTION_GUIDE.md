---
title: Database Connection & Query Guide
description: >
  How to connect to and query the routing DuckDB database with python, the
  DuckDB CLI, and pandas, including database statistics, schema reference, and
  query examples.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Updated database and JSON paths to the datasets_processed/ layout.
related_files: []
tags: [guide/database, guide/query, guide/python, notes/database, analysis/schema, guide/sql, guide/etl, notes/usage, analysis/statistics, guide/cli]
---
# Database Connection & Query Guide

## Overview

The routing database (`datasets_processed/db/routing.duckdb`) contains **232 routing problems** with complete metadata, node coordinates, and distance matrices. This guide shows how to connect and query the data.

## Database Statistics

### Problem Distribution

| Type | Count | Dimension Range | Average Dim | Description |
| ------ | ------- | ----------------- | ------------- | ------------- |
| **TSP** | 113 | 14 - 85,900 | 2,658.84 | Traveling Salesman Problems |
| **CVRP** | 50 | 7 - 30,001 | 2,796.20 | Capacitated Vehicle Routing Problems |
| **SOP** | 41 | 9 - 380 | 95.49 | Sequential Ordering Problems |
| **ATSP** | 19 | 17 - 443 | 127.53 | Asymmetric TSP |
| **HCP** | 9 | 1,000 - 5,000 | 3,000.00 | Hamiltonian Cycle Problems |
| **TOTAL** | **232** | - | - | - |

### Storage Methods

| Type | Total | Explicit Matrices | Coordinate-Based | Notes |
| ------ | ------- | ------------------- | ------------------ | ------- |
| **ATSP** | 19 | 19 | 0 | All asymmetric, require explicit matrices |
| **CVRP** | 50 | 15 | 35 | Mixed: 15 EXPLICIT, 35 EUC_2D |
| **SOP** | 41 | 41 | 0 | All have explicit precedence matrices |
| **TSP** | 113 | 17 | 94 | Mostly coordinate-based (EUC_2D, GEO) |
| **HCP** | 9 | 0 | 0 | Use adjacency lists (no distance matrices) |
| **TOTAL** | **232** | **92** | **129** | 11 other (HCP, XRAY) |

### Edge Weight Types

| Edge Weight Type | Count | Storage Method |
| ------------------ | ------- | ---------------- |
| **EUC_2D** | 113 | Coordinates in `nodes` table |
| **EXPLICIT** | 92 | Matrices in `edge_weight_matrices` table |
| **GEO** | 10 | Coordinates in `nodes` table |
| **CEIL_2D** | 4 | Coordinates in `nodes` table |
| **ATT** | 2 | Coordinates in `nodes` table |
| **XRAY1/XRAY2** | 2 | Coordinates in `nodes` table |
| **NULL** | 9 | HCP problems (adjacency lists) |

### Matrix Formats

| Format | Count | Dimension Range | Avg Size | Description |
| -------- | ------- | ----------------- | ---------- | ------------- |
| **FULL_MATRIX** | 62 | 9 - 443 | 91.5 KB | Full n×n matrix |
| **LOWER_DIAG_ROW** | 12 | 6 - 561 | 115.5 KB | Lower triangle with diagonal |
| **LOWER_ROW** | 12 | 242 - 1,001 | 2,011.1 KB | Lower triangle without diagonal |
| **UPPER_DIAG_ROW** | 3 | 175 - 1,032 | 2,247.3 KB | Upper triangle with diagonal |
| **UPPER_ROW** | 3 | 29 - 180 | 66.2 KB | Upper triangle without diagonal |

**Total:** 92 explicit matrices storing 474,955 nodes

---

## Connection Methods

### Method 1: python with DuckDB

```python
import duckdb
import json

# Connect to database
db = duckdb.connect('datasets_processed/db/routing.duckdb')

# Query problems
result = db.execute("""
    SELECT name, type, dimension, edge_weight_type
    FROM problems
    WHERE type = 'TSP' AND dimension < 100
    ORDER BY dimension
""").fetchall()

for name, ptype, dim, ewt in result:
    print(f"{name}: {ptype} with {dim} nodes ({ewt})")

db.close()
```

### Method 2: DuckDB CLI

```bash
# Open database
duckdb datasets_processed/db/routing.duckdb

# List tables
SHOW TABLES;

# Query problems
SELECT type, COUNT(*) FROM problems GROUP BY type;

# Exit
.quit
```

### Method 3: python with Pandas

```python
import duckdb
import pandas as pd

db = duckdb.connect('datasets_processed/db/routing.duckdb')

# Load problems as DataFrame
df = db.execute("SELECT * FROM problems").df()
print(df.head())

# Load nodes for a specific problem
nodes_df = db.execute("""
    SELECT n.*
    FROM nodes n
    JOIN problems p ON p.id = n.problem_id
    WHERE p.name = 'berlin52'
""").df()

db.close()
```

---

## Schema Reference

### Tables

1. **`problems`** - Problem metadata (232 rows)
2. **`nodes`** - Node coordinates and demands (474,955 rows)
3. **`edge_weight_matrices`** - Explicit distance matrices (92 rows)

### Table: `problems`

| Column | Type | Description |
| -------- | ------ | ------------- |
| `id` | INTEGER | Primary key |
| `name` | VARCHAR | Problem name (e.g., "berlin52", "eil7") |
| `type` | VARCHAR | Problem type (TSP, CVRP, ATSP, SOP, HCP) |
| `dimension` | INTEGER | Number of nodes/cities |
| `edge_weight_type` | VARCHAR | Distance metric (EUC_2D, EXPLICIT, GEO, etc.) |
| `edge_weight_format` | VARCHAR | Matrix format (FULL_MATRIX, LOWER_ROW, etc.) |
| `capacity` | INTEGER | Vehicle capacity (VRP only) |
| `comment` | VARCHAR | Problem description |
| `file_path` | VARCHAR | Original file path |
| `checksum` | VARCHAR | SHA256 checksum |

### Table: `nodes`

| Column | Type | Description |
| -------- | ------ | ------------- |
| `id` | INTEGER | Primary key |
| `problem_id` | INTEGER | Foreign key to `problems.id` |
| `node_id` | INTEGER | Node number (0-based) |
| `x` | DOUBLE | X coordinate |
| `y` | DOUBLE | Y coordinate |
| `demand` | INTEGER | Node demand (VRP only) |

### Table: `edge_weight_matrices`

| Column | Type | Description |
| -------- | ------ | ------------- |
| `problem_id` | INTEGER | Foreign key to `problems.id` |
| `dimension` | INTEGER | **Actual matrix dimension** (may differ from problem dimension) |
| `matrix_format` | VARCHAR | Original TSPLIB format |
| `is_symmetric` | BOOLEAN | Whether matrix is symmetric |
| `matrix_json` | TEXT | Full matrix as JSON (2D array) |

**Important:** For VRP problems with customer-only matrices:

- `problems.dimension` = total nodes (depot + customers)
- `edge_weight_matrices.dimension` = customers only (dimension - 1)
- Example: `eil7` has `problems.dimension=7` but `matrix.dimension=6` (6×6 matrix)

---

## Query Examples

### 1. Get All TSP Problems with Coordinates

```sql
SELECT name, dimension, edge_weight_type
FROM problems
WHERE type = 'TSP'
  AND edge_weight_type IN ('EUC_2D', 'GEO', 'ATT')
ORDER BY dimension;
```

**Result:** 94 TSP problems with coordinate-based distances

### 2. Get Problem with Nodes

```sql
SELECT
    p.name,
    p.dimension,
    n.node_id,
    n.x,
    n.y
FROM problems p
JOIN nodes n ON p.id = n.problem_id
WHERE p.name = 'berlin52'
ORDER BY n.node_id
LIMIT 10;
```

**Output:**

```
name       | dimension | node_id | x      | y
-----------|-----------|---------|--------|--------
berlin52   | 52        | 0       | 565.0  | 575.0
berlin52   | 52        | 1       | 25.0   | 185.0
...
```

### 3. Get ATSP with Explicit Matrix

```sql
SELECT
    p.name,
    p.dimension as problem_dim,
    ew.dimension as matrix_dim,
    ew.matrix_format,
    LENGTH(ew.matrix_json) as matrix_size_bytes
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.type = 'ATSP'
ORDER BY p.dimension;
```

**Output:**

```
name   | problem_dim | matrix_dim | matrix_format | matrix_size_bytes
-------|-------------|------------|---------------|------------------
br17   | 17          | 17         | FULL_MATRIX   | 1,024
ft53   | 53          | 53         | FULL_MATRIX   | 11,449
...
```

### 4. Extract Distance Matrix as python Array

```python
import duckdb
import json

db = duckdb.connect('datasets_processed/db/routing.duckdb')

# Get matrix for br17
result = db.execute("""
    SELECT ew.matrix_json
    FROM edge_weight_matrices ew
    JOIN problems p ON p.id = ew.problem_id
    WHERE p.name = 'br17'
""").fetchone()

if result:
    matrix = json.loads(result[0])

    # Access distance from node 0 to node 5
    distance = matrix[0][5]
    print(f"Distance from node 0 to node 5: {distance}")

    # Get full row for node 0
    row_0 = matrix[0]
    print(f"Node 0 to all others: {row_0}")

db.close()
```

### 5. Get VRP Problems with Customer-Only Matrices

```sql
SELECT
    p.name,
    p.dimension as total_nodes,
    ew.dimension as customers_only,
    p.capacity
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.type = 'CVRP'
  AND ew.dimension = p.dimension - 1
ORDER BY p.dimension;
```

**Output:**

```
name  | total_nodes | customers_only | capacity
------|-------------|----------------|----------
eil7  | 7           | 6              | 3
eil13 | 13          | 12             | 4
eil31 | 31          | 30             | 6
```

### 6. Get SOP Problems (Sequential Ordering)

```sql
SELECT
    p.name,
    p.dimension,
    ew.is_symmetric,
    ew.matrix_format
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.type = 'SOP'
ORDER BY p.dimension
LIMIT 5;
```

### 7. Get HCP Problems (No Matrices)

```sql
SELECT
    p.name,
    p.dimension,
    COUNT(n.id) as node_count
FROM problems p
LEFT JOIN nodes n ON p.id = n.problem_id
WHERE p.type = 'HCP'
GROUP BY p.name, p.dimension
ORDER BY p.dimension;
```

**Note:** HCP problems use adjacency lists stored in the nodes table, not distance matrices.

### 8. Calculate Statistics by Problem Type

```sql
SELECT
    type,
    COUNT(*) as total_problems,
    MIN(dimension) as min_dim,
    MAX(dimension) as max_dim,
    ROUND(AVG(dimension), 2) as avg_dim,
    COUNT(DISTINCT CASE WHEN edge_weight_type = 'EXPLICIT' THEN id END) as with_matrices
FROM problems
GROUP BY type
ORDER BY type;
```

### 9. Find Problems by Dimension Range

```sql
SELECT name, type, dimension, edge_weight_type
FROM problems
WHERE dimension BETWEEN 100 AND 500
  AND type = 'TSP'
ORDER BY dimension;
```

### 10. Get Problem Summary with Nodes and Matrix Info

```sql
SELECT
    p.name,
    p.type,
    p.dimension,
    p.edge_weight_type,
    COUNT(DISTINCT n.id) as node_count,
    CASE
        WHEN ew.problem_id IS NOT NULL THEN 'Explicit Matrix'
        WHEN p.edge_weight_type IN ('EUC_2D', 'GEO', 'ATT') THEN 'Coordinates'
        ELSE 'Other'
    END as storage_method
FROM problems p
LEFT JOIN nodes n ON p.id = n.problem_id
LEFT JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.name = 'berlin52'
GROUP BY p.name, p.type, p.dimension, p.edge_weight_type, ew.problem_id;
```

---

## Distance Calculation Guide

### For Coordinate-Based Problems (EUC_2D, GEO, etc.)

Distances are **NOT stored** in the database. Compute them on-demand from node coordinates:

```python
import math

def euclidean_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Example: Get distance between two nodes in berlin52
import duckdb

db = duckdb.connect('datasets_processed/db/routing.duckdb')

nodes = db.execute("""
    SELECT node_id, x, y
    FROM nodes n
    JOIN problems p ON p.id = n.problem_id
    WHERE p.name = 'berlin52'
    ORDER BY node_id
""").fetchall()

# Distance from node 0 to node 1
n0 = nodes[0]  # (0, 565.0, 575.0)
n1 = nodes[1]  # (1, 25.0, 185.0)
dist = euclidean_distance(n0[1], n0[2], n1[1], n1[2])
print(f"Distance from node {n0[0]} to node {n1[0]}: {dist:.2f}")

db.close()
```

### For EXPLICIT Problems (ATSP, SOP, some CVRP)

Distances are **pre-stored** in `edge_weight_matrices.matrix_json`:

```python
import duckdb
import json

db = duckdb.connect('datasets_processed/db/routing.duckdb')

# Get matrix
result = db.execute("""
    SELECT matrix_json
    FROM edge_weight_matrices ew
    JOIN problems p ON p.id = ew.problem_id
    WHERE p.name = 'br17'
""").fetchone()

matrix = json.loads(result[0])

# Distance from node 0 to node 5
distance = matrix[0][5]
print(f"Distance from node 0 to node 5: {distance}")

db.close()
```

### For VRP Customer-Only Matrices

**Important:** Matrix indices are **customer indices**, not total node indices:

```python
# For eil7 (7 nodes total: 1 depot + 6 customers)
# Matrix is 6×6 (customers only)
# To get distance from customer 2 to customer 4:

result = db.execute("""
    SELECT matrix_json
    FROM edge_weight_matrices ew
    JOIN problems p ON p.id = ew.problem_id
    WHERE p.name = 'eil7'
""").fetchone()

matrix = json.loads(result[0])

# Customer indices are 0-based (0-5 for 6 customers)
# These correspond to nodes 1-6 in the problem (node 0 is depot)
customer_2_to_4 = matrix[2][4]  # Customer 2 → Customer 4
print(f"Distance: {customer_2_to_4}")
```

---

## Matrix Dimension Reference

### Understanding Matrix Dimensions

| Problem Type | `problems.dimension` | `edge_weight_matrices.dimension` | Notes |
| -------------- | --------------------- | ---------------------------------- | ------- |
| **TSP (EXPLICIT)** | n nodes | n×n matrix | Standard: dimension matches |
| **ATSP** | n nodes | n×n matrix | Always asymmetric |
| **SOP** | n nodes | n×n matrix | Dimension marker stripped during parsing |
| **CVRP (EXPLICIT)** | n nodes (depot + customers) | May be (n-1)×(n-1) | Customer-only matrices exclude depot |
| **CVRP (EUC_2D)** | n nodes | No matrix | Uses coordinates |
| **HCP** | n nodes | No matrix | Uses adjacency lists |

### VRP Matrix Special Case

For VRP problems with `EDGE_WEIGHT_FORMAT: EXPLICIT`:

```sql
-- Find VRP problems with customer-only matrices
SELECT
    p.name,
    p.dimension as total_nodes,
    ew.dimension as matrix_dimension,
    p.dimension - ew.dimension as difference
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.type = 'CVRP' AND p.edge_weight_type = 'EXPLICIT';
```

**Output:**

```
name  | total_nodes | matrix_dimension | difference
------|-------------|------------------|------------
eil7  | 7           | 6                | 1
eil13 | 13          | 12               | 1
eil31 | 31          | 30               | 1
```

When `difference = 1`, the matrix contains only customer-to-customer distances (depot excluded).

---

## JSON File Access

All problems are also exported as JSON files in `datasets_processed/json/`:

```bash
datasets_processed/json/
  ├── tsp/
  │   ├── berlin52.json
  │   ├── gr17.json
  │   └── ...
  ├── cvrp/
  │   ├── eil7.json
  │   └── ...
  ├── atsp/
  │   ├── br17.json
  │   └── ...
  ├── sop/
  │   └── ...
  └── hcp/
      └── ...
```

### JSON Structure

```json
{
  "metadata": {
    "name": "berlin52",
    "type": "TSP",
    "dimension": 52,
    "edge_weight_type": "EUC_2D",
    "comment": "52 locations in Berlin (Groetschel)"
  },
  "nodes": [
    {"id": 0, "x": 565.0, "y": 575.0},
    {"id": 1, "x": 25.0, "y": 185.0},
    ...
  ],
  "edge_weight_matrix": null  // Only present for EXPLICIT problems
}
```

---

## Verification Queries

### Check Database Integrity

```sql
-- Verify all problems have nodes
SELECT
    p.type,
    COUNT(DISTINCT p.id) as total_problems,
    COUNT(DISTINCT n.problem_id) as problems_with_nodes
FROM problems p
LEFT JOIN nodes n ON p.id = n.problem_id
GROUP BY p.type
ORDER BY p.type;
```

**Expected:** All problems should have nodes (232 = 232).

### Check Matrix Storage

```sql
-- Verify EXPLICIT problems have matrices
SELECT
    p.edge_weight_type,
    COUNT(DISTINCT p.id) as total,
    COUNT(DISTINCT ew.problem_id) as with_matrix
FROM problems p
LEFT JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.edge_weight_type = 'EXPLICIT'
GROUP BY p.edge_weight_type;
```

**Expected:** All 92 EXPLICIT problems should have matrices.

### Validate Matrix Dimensions

```sql
-- Check for matrix dimension mismatches
SELECT
    p.name,
    p.type,
    p.dimension as problem_dim,
    ew.dimension as matrix_dim,
    p.dimension - ew.dimension as diff
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.dimension != ew.dimension
ORDER BY diff DESC;
```

**Expected:** VRP customer-only matrices will show `diff=1`, others should be `diff=0`.

---

## Performance Tips

### 1. Use Indexes Efficiently

The database has indexes on:

- `problems.id` (primary key)
- `problems.name`
- `nodes.problem_id` (foreign key)
- `edge_weight_matrices.problem_id` (foreign key)

### 2. Limit Large Queries

```sql
-- Good: Limit results for large problems
SELECT * FROM nodes
WHERE problem_id = (SELECT id FROM problems WHERE name = 'pla85900')
LIMIT 1000;

-- Avoid: Loading entire 85,900-node problem at once
```

### 3. Use JSON Functions for Matrix Queries

```sql
-- DuckDB can query JSON directly
SELECT
    p.name,
    json_extract(ew.matrix_json, '$[0][5]') as dist_0_to_5
FROM problems p
JOIN edge_weight_matrices ew ON p.id = ew.problem_id
WHERE p.name = 'br17';
```

---

## Common Issues

### Issue 1: VRP Matrix Dimension Mismatch

**Problem:** VRP matrix dimension is 1 less than problem dimension.

**Solution:** This is **correct** for customer-only matrices. Use `ew.dimension` for matrix access, not `p.dimension`.

### Issue 2: HCP Problems Have No Matrix

**Problem:** Can't find distance matrix for HCP problems.

**Solution:** HCP problems use **adjacency lists**, not distance matrices. Check the nodes table for adjacency information.

### Issue 3: Large Matrix Memory Usage

**Problem:** Loading large matrices (e.g., rbg443 with 443×443 elements) uses too much memory.

**Solution:** Query specific matrix elements using JSON functions instead of loading the entire matrix.

---

## Summary

✅ **All 232 problems correctly identified**

- 19 ATSP, 50 CVRP, 9 HCP, 41 SOP, 113 TSP

✅ **All matrices correctly stored**

- 92 explicit matrices (19 ATSP + 15 CVRP + 41 SOP + 17 TSP)
- 129 coordinate-based problems (compute distances on-demand)
- 9 HCP problems (adjacency lists)

✅ **Data integrity verified**

- All 232 problems have nodes (474,955 total)
- VRP customer-only matrices correctly identified (dimension - 1)
- SOP dimension markers correctly stripped

✅ **Access methods available**

- DuckDB SQL queries
- python with DuckDB/Pandas
- JSON files for offline access

---

**Generated:** October 28, 2025
**Database:** `datasets_processed/db/routing.duckdb`
**Version:** 1.0
