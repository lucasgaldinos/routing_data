---
title: Getting Started — TSPLIB95 ETL System
description: >
  Quick-start guide for the TSPLIB95 ETL System: installation, first processing
  run, querying the database, JSON access, configuration notes, and
  troubleshooting basics.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Repointed the API/architecture links, removed the phantom --config
          flag usage, and updated output/database paths to the
          datasets_processed/ layout.
related_files:
  - "[User Guide](./USER_GUIDE.md)"
  - "[Architecture Decisions](../reference/ARCHITECTURE_DECISIONS.md)"
  - "[Troubleshooting](./TROUBLESHOOTING.md)"
tags: [guide/setup, guide/quickstart, guide/cli, guide/database, guide/etl, notes/overview, guide/troubleshooting, guide/configuration, analysis/design, notes/usage, guide/json]
---
# Getting Started - TSPLIB95 ETL System

## Quick Start (3 Steps)

### 1. Install

```bash
# Clone repository
git clone https://github.com/lucasgaldinos/Routing_data.git
cd Routing_data

# Install with uv (recommended)
uv sync

# Verify installation
uv run converter --help
```

### 2. Process Files

```bash
# Basic processing - converts all TSPLIB files to JSON + database
uv run converter process \
  --input datasets_raw/problems \
  --output datasets/

# With parallel processing (faster)
uv run converter process -i datasets_raw/problems -o datasets_processed/ --workers 8
```

### 3. Use Results

**Query Database:**

```bash
duckdb datasets_processed/db/routing.duckdb
```

```sql
-- View available problems
SELECT name, type, dimension FROM problems LIMIT 10;

-- Find large TSP instances
SELECT name, dimension FROM problems
WHERE type = 'TSP' AND dimension > 1000;

-- Analyze problem distribution
SELECT type, COUNT(*), AVG(dimension) as avg_size
FROM problems GROUP BY type;
```

**Access JSON Files:**

```bash
# Problems organized by type
ls datasets_processed/json/tsp/     # TSP problems
ls datasets_processed/json/vrp/     # VRP problems

# View single problem
cat datasets_processed/json/tsp/gr17.json
```

**Use python API:**

```python
import converter

# Parse single file
data = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")
print(f"Problem: {data['problem_data']['name']} ({data['problem_data']['dimension']} nodes)")

# Convert to JSON
converter.to_json(data, "my_problem.json")

# Store in database
converter.to_database(data, "my_routing.duckdb")
```

## What You Get

After processing, you'll have:

### Structured Database (DuckDB)

- **problems**: Metadata for each routing problem
- **nodes**: Coordinates, demands, depot information
- **edges**: Precomputed weights (for explicit problems)
- **tours**: Solution tours (if available)
- **file_tracking**: Change detection for updates

### Clean JSON Files

Organized by problem type with flattened structure:

```json
{
  "problem": {"name": "gr17", "type": "TSP", "dimension": 17},
  "nodes": [{"node_id": 0, "x": 38.24, "y": 20.42}],
  "solution": {"tour": [0, 1, 2, ...], "distance": 2085}
}
```

## Common Use Cases

### Batch Process Large Collections

```bash
# Process only specific types
uv run converter process --types TSP --types VRP -i large_collection/ -o results/

# Skip unchanged files (incremental updates)
uv run converter process -i datasets_raw/problems -o datasets_processed/  # Automatic

# Force reprocess everything
uv run converter process --force -i datasets_raw/problems -o datasets_processed/
```

### Analyze Problem Collections

```sql
-- Problem size distribution
SELECT
  CASE
    WHEN dimension < 100 THEN 'Small (<100)'
    WHEN dimension < 1000 THEN 'Medium (100-1000)'
    ELSE 'Large (>1000)'
  END as size_category,
  COUNT(*) as count
FROM problems
GROUP BY size_category;

-- Geographic problems vs others
SELECT
  CASE
    WHEN edge_weight_type IN ('EUC_2D', 'GEO') THEN 'Geographic'
    WHEN edge_weight_type = 'EXPLICIT' THEN 'Matrix-based'
    ELSE 'Other'
  END as problem_category,
  COUNT(*) as count
FROM problems
GROUP BY problem_category;

-- VRP problems with capacity constraints
SELECT name, dimension, capacity
FROM problems
WHERE type = 'VRP' AND capacity IS NOT NULL
ORDER BY dimension;
```

### Data Export for Analysis

```python
import pandas as pd
import duckdb

# Connect to database
conn = duckdb.connect("datasets_processed/db/routing.duckdb")

# Export problems to DataFrame
problems_df = conn.execute("""
    SELECT name, type, dimension, edge_weight_type, capacity
    FROM problems
    WHERE dimension BETWEEN 50 AND 500
""").df()

# Export nodes with coordinates
nodes_df = conn.execute("""
    SELECT p.name, n.node_id, n.x, n.y, n.demand, n.is_depot
    FROM problems p
    JOIN nodes n ON p.id = n.problem_id
    WHERE p.name = 'gr17'
""").df()

# Save to CSV for external analysis
problems_df.to_csv("problems_analysis.csv", index=False)
```

## Configuration

### Custom Configuration

```yaml
# config.yaml
input_path: "./my_tsplib_files"
processing:
  batch_size: 50        # Smaller for memory-constrained systems
  max_workers: 2        # Reduce for slower systems
  memory_limit_mb: 1024 # Adjust based on available RAM

output:
  json_output_path: "./results/json"
  database_path: "./results/routing.duckdb"

logging:
  level: "DEBUG"        # For troubleshooting
  console: true
```

```bash
# Generate a configuration template for reference, then edit it
uv run converter init -o config.yaml
nano config.yaml

# The CLI does not read config.yaml — pass the same values via flags:
uv run converter process -i ./my_tsplib_files --batch-size 50 --workers 2
```

### Environment Variables

```bash
# Override config with environment variables
export CONVERTER_INPUT_PATH="/data/tsplib"
export CONVERTER_MAX_WORKERS=16
export CONVERTER_LOG_LEVEL="DEBUG"

uv run converter process -o results/
```

## Troubleshooting

### Common Issues

**"No files found"**

- Check input path exists and contains .tsp, .vrp, .atsp, .hcp, .sop, or .tour files
- Verify file permissions

**"Memory errors during processing"**

```bash
# Reduce batch size and workers
uv run converter process --batch-size 10 --workers 1 -i datasets_raw/problems -o datasets_processed/
```

**"Database locked"**

- Only one process can write to DuckDB at a time
- Stop other converter processes or use different output paths

**"Parsing errors"**

```bash
# Enable verbose logging to see details
uv run converter process --verbose -i problematic_file/ -o debug_output/
```

### Getting Help

**Check logs:**

```bash
# View recent processing logs
tail -f logs/converter.log

# Search for errors
grep "ERROR" logs/converter.log
```

**Test with small dataset:**

```bash
# Process single file for debugging
uv run python -c "
import converter
data = converter.parse_file('datasets_raw/problems/tsp/gr17.tsp')
print('Success:', data['problem_data']['name'])
"
```

**Database inspection:**

```sql
-- Check processing status
SELECT processing_status, COUNT(*)
FROM file_tracking
GROUP BY processing_status;

-- Find failed files
SELECT file_path, error_message
FROM file_tracking
WHERE processing_status = 'failed';
```

## Next Steps

1. **Read [User Guide](USER_GUIDE.md)** for comprehensive usage documentation
2. **Read [API Reference](USER_GUIDE.md)** for programmatic usage
3. **Read [Architecture Guide](../reference/ARCHITECTURE_DECISIONS.md)** to understand system design

## Support

- **Issues**: [GitHub Issues](https://github.com/lucasgaldinos/Routing_data/issues)
- **Documentation**: `docs/` directory
- **Examples**: `tests/` directory for usage patterns
