---
title: Parquet Export Guide
description: >
  How to export DuckDB tables to Apache Parquet with the converter CLI and
  Python API: codec choices, integration with pandas/polars/DuckDB, and
  performance notes.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Updated database and output paths to the datasets_processed/ layout
          and repointed the archive output example.
related_files: []
tags: [guide/export, guide/parquet, guide/database, guide/cli, analysis/performance, guide/etl, notes/data-formats, analysis/storage, guide/python, benchmark/performance, analysis/benchmarking]
---
# Parquet Export Guide

## Overview

The TSPLIB95 ETL Converter supports exporting database tables to **Apache Parquet** format - a columnar storage format optimized for analytical queries and machine learning workflows.

## Why Parquet?

### Advantages

| Feature | Benefit |
| --------- | --------- |
| **Columnar Storage** | Efficient compression and fast column-based queries |
| **Schema Preservation** | Maintains data types and metadata |
| **Compression** | 20-70% smaller than JSON (default: Snappy) |
| **Interoperability** | Works with pandas, polars, DuckDB, Spark, Arrow |
| **Fast I/O** | Optimized for batch reads and analytical workloads |

### Compression Comparison

Based on 113 TSP problems dataset:

| Format | Size | Compression Ratio | Best For |
| -------- | ------ | ------------------- | ---------- |
| **JSON** (raw) | 8.14 MB | 1.0x (baseline) | Human-readable, web APIs |
| **Parquet** (snappy) | 6.27 MB | 0.77x (23% smaller) | General purpose, balanced speed/size |
| **Parquet** (gzip) | ~5.5 MB | 0.68x (32% smaller) | Network transfer, storage optimization |
| **Parquet** (zstd) | ~4.5 MB | 0.55x (45% smaller) | Long-term archival, maximum compression |
| **Parquet** (uncompressed) | ~9.2 MB | 1.13x (13% larger) | Maximum read speed, already compressed storage |

## Usage

### CLI Export

```bash
# Export all tables to Parquet (default: snappy compression)
uv run converter export-parquet

# Specify database and output directory
uv run converter export-parquet \
  -d datasets_processed/db/routing.duckdb \
  -o datasets_processed/parquet

# Export specific tables only
uv run converter export-parquet \
  -t problems \
  -t nodes \
  -o exports/

# Use different compression codec
uv run converter export-parquet -c zstd  # Maximum compression
uv run converter export-parquet -c gzip  # Good compression
uv run converter export-parquet -c uncompressed  # Fastest reads

# Disable info display (faster for scripting)
uv run converter export-parquet --no-info
```

### python API

```python
from converter.output.parquet_writer import ParquetWriter, export_database_to_parquet

# Quick export (all tables)
files = export_database_to_parquet(
    db_path="datasets_processed/db/routing.duckdb",
    output_dir="datasets_processed/parquet",
    compression="snappy"
)

# Advanced usage
writer = ParquetWriter(
    output_dir="datasets_processed/parquet",
    compression="zstd"  # Maximum compression
)

# Export all tables
files = writer.export_from_database(
    db_path="datasets_processed/db/routing.duckdb"
)

# Export specific tables
files = writer.export_from_database(
    db_path="datasets_processed/db/routing.duckdb",
    tables=["problems", "nodes"]
)

# Export single table with custom filename
output_file = writer.export_table(
    db_path="datasets_processed/db/routing.duckdb",
    table_name="problems",
    output_filename="tsp_problems.parquet"
)

# Get Parquet file metadata
info = writer.get_parquet_info("datasets_processed/parquet/problems.parquet")
print(f"Rows: {info['row_count']}, Columns: {info['column_count']}")
print(f"Size: {info['size_mb']} MB, Compression: {info['compression']}")
```

## Reading Parquet Files

### Using Pandas

```python
import pandas as pd

# Read single table
problems_df = pd.read_parquet('datasets_processed/parquet/problems.parquet')

# Read specific columns (columnar advantage!)
problems_df = pd.read_parquet(
    'datasets_processed/parquet/problems.parquet',
    columns=['name', 'type', 'dimension']
)

# Filter while reading (predicate pushdown)
problems_df = pd.read_parquet(
    'datasets_processed/parquet/problems.parquet',
    filters=[('type', '=', 'TSP'), ('dimension', '<', 200)]
)
```

### Using Polars (Faster for Large Data)

```python
import polars as pl

# Read entire table (lazy evaluation)
problems_lf = pl.scan_parquet('datasets_processed/parquet/problems.parquet')

# Filter and select
result = (
    problems_lf
    .filter(pl.col('type') == 'TSP')
    .filter(pl.col('dimension') < 200)
    .select(['name', 'dimension', 'edge_weight_type'])
    .collect()
)

# Eager read
problems_df = pl.read_parquet('datasets_processed/parquet/problems.parquet')
```

### Using DuckDB (Zero-Copy, Most Efficient)

```python
import duckdb

# Query Parquet directly (no loading!)
conn = duckdb.connect(':memory:')

result = conn.execute("""
    SELECT name, type, dimension
    FROM 'datasets_processed/parquet/problems.parquet'
    WHERE type = 'TSP' AND dimension BETWEEN 100 AND 200
    ORDER BY dimension
""").fetchall()

# Convert to DataFrame
df = conn.execute("""
    SELECT * FROM 'datasets_processed/parquet/problems.parquet'
""").df()

# Join multiple Parquet files
result = conn.execute("""
    SELECT p.name, p.dimension, COUNT(n.node_id) as node_count
    FROM 'datasets_processed/parquet/problems.parquet' p
    LEFT JOIN 'datasets_processed/parquet/nodes.parquet' n
        ON p.id = n.problem_id
    GROUP BY p.name, p.dimension
""").df()
```

### Using PyArrow

```python
import pyarrow.parquet as pq

# Read Parquet file
table = pq.read_table('datasets_processed/parquet/problems.parquet')

# Convert to pandas
df = table.to_pandas()

# Read with column selection
table = pq.read_table(
    'datasets_processed/parquet/problems.parquet',
    columns=['name', 'type', 'dimension']
)

# Read metadata only
metadata = pq.read_metadata('datasets_processed/parquet/problems.parquet')
print(f"Rows: {metadata.num_rows}")
print(f"Columns: {metadata.num_columns}")
```

## Use Cases

### Data Science & Machine Learning

```python
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Load routing problem features
problems = pd.read_parquet('datasets_processed/parquet/problems.parquet')
nodes = pd.read_parquet('datasets_processed/parquet/nodes.parquet')

# Feature engineering
features = problems[['dimension', 'edge_weight_type']].copy()
features['node_density'] = features['dimension'] / 100  # Normalize

# Train/test split
X_train, X_test = train_test_split(features, test_size=0.2)
```

### Analytics & Reporting

```python
import duckdb
import matplotlib.pyplot as plt

conn = duckdb.connect(':memory:')

# Aggregate statistics
stats = conn.execute("""
    SELECT type,
           COUNT(*) as count,
           AVG(dimension) as avg_dim,
           MAX(dimension) as max_dim
    FROM 'datasets_processed/parquet/problems.parquet'
    GROUP BY type
""").df()

# Visualization
stats.plot.bar(x='type', y='count', title='Problems by Type')
plt.show()
```

### Distributed Processing (Spark)

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("TSPLIB").getOrCreate()

# Read Parquet (distributed)
problems_df = spark.read.parquet('datasets_processed/parquet/problems.parquet')

# Query with Spark SQL
problems_df.createOrReplaceTempView("problems")
result = spark.sql("""
    SELECT type, COUNT(*) as count
    FROM problems
    GROUP BY type
""")
```

## Performance Tips

### 1. Column Selection

```python
# ❌ Bad: Read all columns
df = pd.read_parquet('nodes.parquet')  # Reads all 10 columns

# ✅ Good: Read only needed columns
df = pd.read_parquet('nodes.parquet', columns=['problem_id', 'x', 'y'])
```

### 2. Predicate Pushdown

```python
# ❌ Bad: Filter after loading
df = pd.read_parquet('problems.parquet')
filtered = df[df['type'] == 'TSP']

# ✅ Good: Filter during read (predicate pushdown)
filtered = pd.read_parquet(
    'problems.parquet',
    filters=[('type', '=', 'TSP')]
)
```

### 3. Lazy Evaluation (Polars)

```python
import polars as pl

# ❌ Eager: Loads everything
df = pl.read_parquet('problems.parquet')
result = df.filter(pl.col('dimension') < 100)

# ✅ Lazy: Optimized query plan
result = (
    pl.scan_parquet('problems.parquet')
    .filter(pl.col('dimension') < 100)
    .select(['name', 'dimension'])
    .collect()  # Execute only when needed
)
```

### 4. Zero-Copy with DuckDB

```python
import duckdb

# ❌ Slower: Load to python then query
df = pd.read_parquet('problems.parquet')
result = df[df['dimension'] < 100]

# ✅ Fastest: Query Parquet directly (no python copy)
conn = duckdb.connect(':memory:')
result = conn.execute("""
    SELECT * FROM 'problems.parquet' WHERE dimension < 100
""").df()
```

## Compression Guide

### When to Use Each Codec

| Codec | Compression Ratio | Speed | Best For |
| ------- | ------------------ | ------- | ---------- |
| **snappy** (default) | ~0.77x | ⚡⚡⚡ Fast | General purpose, interactive analysis |
| **gzip** | ~0.68x | ⚡⚡ Moderate | Network transfer, cloud storage |
| **zstd** | ~0.55x | ⚡ Slower | Long-term archival, maximum space savings |
| **uncompressed** | 1.13x | ⚡⚡⚡⚡ Fastest | Already compressed storage (e.g., S3), maximum read speed |

### Example: Maximum Compression

```bash
# For archival or cloud storage
uv run converter export-parquet -c zstd -o datasets_processed/parquet/

# Result: ~4.5 MB (vs 8.14 MB JSON, 45% savings)
```

## Integration Examples

### Jupyter Notebook

```python
# notebook.ipynb
import pandas as pd
import duckdb

# Quick load
problems = pd.read_parquet('datasets_processed/parquet/problems.parquet')

# Display
problems.head()

# SQL queries
conn = duckdb.connect(':memory:')
conn.execute("""
    SELECT * FROM 'datasets_processed/parquet/problems.parquet'
    WHERE type = 'TSP'
""").df()
```

### Streamlit Dashboard

```python
# dashboard.py
import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_parquet('datasets_processed/parquet/problems.parquet')

df = load_data()
st.dataframe(df)
st.bar_chart(df.groupby('type').size())
```

### FastAPI Endpoint

```python
from fastapi import FastAPI
import pandas as pd

app = FastAPI()

problems_df = pd.read_parquet('datasets_processed/parquet/problems.parquet')

@app.get("/problems/{problem_type}")
def get_problems(problem_type: str):
    filtered = problems_df[problems_df['type'] == problem_type]
    return filtered.to_dict(orient='records')
```

## Troubleshooting

### File Not Found

```python
# Error: FileNotFoundError: datasets_processed/parquet/problems.parquet

# Solution 1: Export first
from converter.output.parquet_writer import export_database_to_parquet
export_database_to_parquet('datasets_processed/db/routing.duckdb')

# Solution 2: Check path
from pathlib import Path
print(Path('datasets_processed/parquet').exists())  # Should be True
```

### Large Memory Usage

```python
# Problem: Reading 300K+ nodes exhausts memory

# Solution 1: Use DuckDB (zero-copy)
import duckdb
conn = duckdb.connect(':memory:')
result = conn.execute("""
    SELECT * FROM 'nodes.parquet' LIMIT 1000
""").df()

# Solution 2: Use Polars lazy evaluation
import polars as pl
result = (
    pl.scan_parquet('nodes.parquet')
    .head(1000)
    .collect()
)

# Solution 3: Read in chunks (pandas)
import pandas as pd
for chunk in pd.read_parquet('nodes.parquet', chunksize=10000):
    process(chunk)  # Process each chunk separately
```

### Incompatible Schemas

```python
# Problem: TypeError: struct<...> is not supported

# Solution: Flatten nested structures before export
# (Already handled in our converter - matrices stored as JSON strings)

# If needed, convert JSON columns:
import json
df['matrix'] = df['matrix_json'].apply(json.loads)
```

## Best Practices

1. **✅ Use Parquet for analytics**: Columnar format optimized for aggregations
2. **✅ Filter during read**: Use `filters` parameter (predicate pushdown)
3. **✅ Select only needed columns**: Reduces I/O and memory
4. **✅ Use DuckDB for queries**: Zero-copy, most efficient
5. **✅ Choose compression wisely**: `snappy` (default) for speed, `zstd` for space
6. **❌ Don't use for transactional writes**: Parquet is append-only
7. **❌ Don't edit in-place**: Export new version if schema changes

## Further Reading

- [Apache Parquet Documentation](https://parquet.apache.org/docs/)
- [DuckDB Parquet Support](https://duckdb.org/docs/data/parquet)
- [Pandas Parquet I/O](https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html)
- [Polars Parquet Guide](https://pola-rs.github.io/polars/py-polars/html/reference/io.html#parquet)

---

**Need help?** See [Troubleshooting Guide](TROUBLESHOOTING.md) or [open an issue](https://github.com/your-repo/issues).
