---
title: "TSPLIB95 ETL Converter — User Guide"
description: >
  End-user documentation for the TSPLIB95 ETL converter: installation, CLI
  usage, Python API, database access, and pointers to the dedicated guides.
created: 2025-10-28
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Trimmed duplicated troubleshooting and database-query sections to
          links, removed the phantom --config flag, corrected DB paths to
          datasets_processed/, and fixed stale Python API imports.
related_files:
  - [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
  - [DATABASE_CONNECTION_GUIDE.md](../DATABASE_CONNECTION_GUIDE.md)
  - [PARQUET_EXPORT.md](./PARQUET_EXPORT.md)
  - [CONTRIBUTING.md](../reference/CONTRIBUTING.md)
tags:
  - guide/usage
  - guide/cli
  - guide/python-api
  - guide/database
  - guide/installation
  - guide/quickstart
  - guide/troubleshooting
  - analysis/etl
  - notes/converter
  - review/documentation
---
# TSPLIB95 ETL System - User Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Basic Usage](#basic-usage)
4. [Advanced Usage](#advanced-usage)
5. [CLI Reference](#cli-reference)
6. [python API](#python-api)
7. [Database Queries](#database-queries)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

Get started in 3 simple steps:

```bash
# 1. Install the package
pip install -e .

# 2. Initialize configuration
python -m converter.cli.commands init

# 3. Process TSPLIB files
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --parallel
```

>[!tip]: the installed entry point is equivalent — `converter process -i ... -o ...`.

That's it! You now have:

- A DuckDB database at `datasets_processed/db/routing.duckdb`
- JSON files organized by type in `datasets_processed/json/`
- File tracking for incremental updates

---

## Installation

### Prerequisites

- python ≥ 3.11
- 2GB+ RAM (for processing large files)
- 1GB+ disk space (for database and JSON output)

### Install from Source

```bash
# Clone repository
git clone https://github.com/lucasgaldinos/Routing_data.git
cd Routing_data

# Install with dependencies
pip install -e .

# Verify installation
python -c "from converter.cli.commands import cli; print('✓ Installation successful')"
```

### Install Development Dependencies

For testing and development:

```bash
pip install -e ".[dev]"
```

---

## Basic Usage

### 1. Initialize Configuration

Create a configuration file with default settings:

```bash
python -m converter.cli.commands init --output config.yaml
```

This creates `config.yaml`:

```yaml
input_path: ./datasets_raw/problems
file_patterns:
- '*.tsp'
- '*.vrp'
- '*.atsp'
- '*.hcp'
- '*.sop'
- '*.tour'
json_output_path: ./datasets_processed/json
database_path: ./datasets_processed/db/routing.duckdb
batch_size: 100
max_workers: 4
memory_limit_mb: 2048
log_level: INFO
log_file: ./logs/converter.log
```

**Customize settings:**

```bash
# Edit config.yaml
nano config.yaml

# Modify settings as needed:
# - max_workers: 8  (for faster processing on powerful machines)
# - log_level: DEBUG  (for troubleshooting)
# - batch_size: 50  (for lower memory usage)
```

### 2. Process TSPLIB Files

#### Process All Files

```bash
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/
```

**What happens:**

1. Scans `datasets_raw/problems` recursively
2. Finds all TSPLIB files (*.tsp,*.vrp, etc.)
3. Parses each file to extract metadata, nodes, and edge-weight matrices
4. Stores in DuckDB at `datasets_processed/db/routing.duckdb`
5. Writes JSON to `datasets_processed/json/{tsp,vrp,atsp}/`
6. Tracks files with SHA256 checksums

#### Process Specific Types

```bash
# Only TSP files
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --types tsp

# Multiple types
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --types tsp --types vrp
```

#### Parallel Processing

```bash
# Use 4 workers (default)
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --parallel

# Use 8 workers (for faster processing)
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --parallel \
  --workers 8
```

#### Sequential Processing

For debugging or low-memory systems:

```bash
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --no-parallel
```

### 3. Validate Database

Check database integrity:

```bash
python -m converter.cli.commands validate \
  --database datasets_processed/db/routing.duckdb
```

**Output:**

```text
✓ Database connection successful
✓ All required tables exist
✓ All sequences exist
✓ Foreign key constraints valid
✓ Database validation passed
```

### 4. Analyze Data

#### View Statistics (Table Format)

```bash
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --format table
```

**Output:**

```text
Problem Statistics:
┌──────┬────────┬───────────┬───────────┐
│ Type │ Count  │ Avg Dim   │ Max Dim   │
├──────┼────────┼───────────┼───────────┤
│ TSP  │ 113    │ 1204.5    │ 13509     │
│ VRP  │ 45     │ 342.8     │ 1001      │
│ ATSP │ 28     │ 156.3     │ 443       │
└──────┴────────┴───────────┴───────────┘
```

#### View Statistics (JSON Format)

```bash
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --format json > stats.json
```

#### Filter by Type

```bash
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --type TSP \
  --limit 20
```

---

## Advanced Usage

### Incremental Updates

The system automatically detects changed files:

```bash
# First run: processes all files
python -m converter.cli.commands process -i datasets_raw/problems -o datasets_processed/

# Modify a file
echo "COMMENT : Updated" >> datasets_raw/problems/tsp/gr17.tsp

# Second run: only processes changed file
python -m converter.cli.commands process -i datasets_raw/problems -o datasets_processed/
```

**Output:**

```text
INFO - Checking for changed files...
INFO - Processing modified file: datasets_raw/problems/tsp/gr17.tsp
INFO - Skipping 112 unchanged files
```

### Force Reprocessing

Skip change detection and process all files:

```bash
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --force
```

### Custom Batch Size

Adjust memory usage:

```bash
# Lower batch size for limited memory
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --batch-size 50

# Higher batch size for better performance
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --batch-size 200
```

### Custom Worker Count

```bash
# Single worker (sequential)
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --workers 1

# Maximum parallelization (for powerful systems)
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --workers 16
```

### Configuration File (Template Only)

The CLI has **no `--config` flag**. `converter init -o config.yaml` generates
a settings template for reference; pass values through CLI flags:

```bash
python -m converter.cli.commands process \
  -i ./my_data \
  -o ./output/ \
  --workers 8 \
  --batch-size 50
```

---

## CLI Reference

### `init` Command

Generate a configuration file.

```bash
python -m converter.cli.commands init [OPTIONS]
```

**Options:**

- `--output, -o PATH` - Output path for config file (default: config.yaml)

**Example:**

```bash
python -m converter.cli.commands init -o my_config.yaml
```

### `process` Command

Run the ETL pipeline.

```bash
python -m converter.cli.commands process [OPTIONS]
```

**Options:**

- `--input, -i PATH` - Input directory containing TSPLIB files
- `--output, -o PATH` - Output directory for JSON and database
- `--parallel / --no-parallel` - Enable/disable parallel processing (default: enabled)
- `--batch-size INT` - Batch size for processing (default: 100)
- `--workers INT` - Number of parallel workers (default: 4)
- `--types TEXT` - Problem types to process (can be specified multiple times)
- `--force / --no-force` - Force reprocessing of existing files (default: disabled)

**Examples:**

```bash
# Basic usage
python -m converter.cli.commands process -i data/ -o output/

# Parallel with 8 workers
python -m converter.cli.commands process -i data/ -o output/ --workers 8

# Only TSP and VRP files
python -m converter.cli.commands process -i data/ -o output/ --types tsp --types vrp

# Force reprocessing
python -m converter.cli.commands process -i data/ -o output/ --force
```

### `validate` Command

Validate database integrity.

```bash
python -m converter.cli.commands validate [OPTIONS]
```

**Options:**

- `--database, -d PATH` - Path to DuckDB database file

**Examples:**

```bash
# Validate the processed database
python -m converter.cli.commands validate --database datasets_processed/db/routing.duckdb
```

### `analyze` Command

Generate statistics and analyze data.

```bash
python -m converter.cli.commands analyze [OPTIONS]
```

**Options:**

- `--database, -d PATH` - Path to DuckDB database file
- `--format [table|json]` - Output format (default: table)
- `--type TEXT` - Filter by problem type
- `--limit INT` - Limit number of results (default: 100)

**Examples:**

```bash
# Table format
python -m converter.cli.commands analyze --database datasets_processed/db/routing.duckdb

# JSON format
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --format json

# Filter by type
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --type TSP \
  --limit 50

# Save to file
python -m converter.cli.commands analyze \
  --database datasets_processed/db/routing.duckdb \
  --format json > analysis.json
```

---

## python API

Use the converter programmatically in your python code.

### Basic Parsing

```python
from converter.api import parse_file

# Parse a file (returns transformed data: problem_data, nodes, ...)
result = parse_file('datasets_raw/problems/tsp/berlin52.tsp')

# Access data
print(f"Problem: {result['problem_data']['name']}")
print(f"Dimension: {result['problem_data']['dimension']}")
print(f"Nodes: {len(result['nodes'])}")
```

### Complete Pipeline

```python
from converter.core.scanner import FileScanner
from tsplib_parser.parser import FormatParser
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from converter.utils.logging import setup_logging

# Initialize components
logger = setup_logging("INFO")
scanner = FileScanner(logger=logger)
parser = FormatParser(logger=logger)
transformer = DataTransformer(logger=logger)
db_manager = DatabaseManager("output.duckdb", logger=logger)
json_writer = JSONWriter("output_json/", logger=logger)

# Scan for files
files = scanner.scan_files('datasets_raw/problems/tsp', patterns=['*.tsp'])
print(f"Found {len(files)} files")

# Process each file
for file_path in files[:5]:  # First 5 files
    # Parse
    problem_data = parser.parse_file(file_path)

    # Transform
    transformed = transformer.transform_problem(problem_data)

    # Store in database
    problem_id = db_manager.insert_problem(transformed['problem_data'])
    if transformed['nodes']:
        db_manager.insert_nodes(problem_id, transformed['nodes'])
    if transformed.get('edge_weight_data'):
        db_manager.insert_edge_weights(problem_id, transformed['edge_weight_data'])

    # Write JSON
    json_writer.write_problem(transformed)

    print(f"✓ Processed {transformed['problem_data']['name']}")
```

### Parallel Processing

```python
from converter.utils.parallel import ParallelProcessor
from tsplib_parser.parser import FormatParser
from converter.utils.logging import setup_logging

logger = setup_logging("INFO")
parser = FormatParser(logger=logger)
processor = ParallelProcessor(max_workers=4, logger=logger)

# Define processing function
def process_file(file_path):
    result = parser.parse_file(file_path)
    return result['problem_data']['name']

# Process files in parallel
files = ['file1.tsp', 'file2.tsp', 'file3.tsp']
results = processor.process_files_parallel(files, process_file)

print(f"Successful: {results['successful']}")
print(f"Failed: {results['failed']}")
print(f"Time: {results['processing_time']:.2f}s")
```

### Update Detection

```python
from converter.utils.update import UpdateManager
from converter.database.operations import DatabaseManager
from converter.utils.logging import setup_logging

logger = setup_logging("INFO")
db_manager = DatabaseManager("routing.duckdb", logger)
update_manager = UpdateManager(db_manager, logger)

# Check if file needs processing
file_path = 'datasets_raw/problems/tsp/berlin52.tsp'
change_info = update_manager.detect_changes(file_path)

if change_info['needs_update']:
    print(f"File needs update: {change_info['change_type']}")
else:
    print("File unchanged, skipping")
```

---

## Database Queries

The canonical connection and query reference lives in
[DATABASE_CONNECTION_GUIDE.md](../DATABASE_CONNECTION_GUIDE.md): schema
details, storage methods, validation queries, and performance tips.

```python
import duckdb

conn = duckdb.connect('datasets_processed/db/routing.duckdb')
result = conn.execute('SELECT COUNT(*) FROM problems').fetchone()
print(f"Total problems: {result[0]}")
conn.close()
```

---

## Troubleshooting

See the dedicated [Troubleshooting Guide](./TROUBLESHOOTING.md) for the full
symptom → root-cause → resolution reference (file processing, parsing,
database, memory, and performance).

The two most common issues:

1. **`ModuleNotFoundError: No module named 'converter'`** — install in
   editable mode: `pip install -e .`
2. **Database lock (`Could not set lock on file`)** — close other
   connections, then remove the stale `.wal` file if needed.

---

## Best Practices

### 1. Always Use Incremental Updates

```bash
# First run
python -m converter.cli.commands process -i data/ -o output/

# Subsequent runs (only processes changed files)
python -m converter.cli.commands process -i data/ -o output/
```

### 2. Validate After Processing

```bash
python -m converter.cli.commands process -i data/ -o output/
python -m converter.cli.commands validate --database output/db/routing.duckdb
```

### 3. Backup Database Regularly

```bash
# Create backup
cp datasets_processed/db/routing.duckdb datasets_processed/db/routing_backup_$(date +%Y%m%d).duckdb

# Or export to SQL
duckdb datasets_processed/db/routing.duckdb -c "EXPORT DATABASE 'backup/';"
```

### 4. Monitor Log Files

```bash
# Tail log file during processing
tail -f logs/converter.log

# Check for errors
grep "ERROR" logs/converter.log
```

### 5. Pass Settings via CLI Flags

The CLI takes no `--config` flag; pass settings explicitly:

```bash
python -m converter.cli.commands process \
  -i datasets_raw/problems \
  -o datasets_processed/ \
  --workers 8 \
  --batch-size 150
```

---

## Getting Help

### Check Documentation

- Contributing Guide: `../reference/CONTRIBUTING.md`
- Architecture Decisions: `../reference/ARCHITECTURE_DECISIONS.md`
- TSPLIB95 Format Spec: `../reference/tsplib95_format.md`
- Database Guide: `../DATABASE_CONNECTION_GUIDE.md`

### Run Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific modules
python -m pytest tests/test_converter -v

# Integration tests
python -m pytest tests/test_integration -v
```

### Command Help

```bash
# General help
python -m converter.cli.commands --help

# Command-specific help
python -m converter.cli.commands process --help
python -m converter.cli.commands validate --help
python -m converter.cli.commands analyze --help
```

---

## Next Steps

Now that you know how to use the system:

1. **Process Your Data**: Run the pipeline on your TSPLIB files
2. **Explore the Database**: Use SQL queries to analyze problems
3. **Integrate**: Use the python API in your own code
4. **Optimize**: Tune workers and batch size for your system
5. **Extend**: Add custom processing or analysis functions

Happy routing! 🚀
