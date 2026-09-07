---
title: Contributing Guide
description: >
  Contributor onboarding and development workflow for the TSPLIB95 ETL Converter:
  setup, essential commands, parser extension, schema migration, testing, debugging,
  code quality, and deployment workflows.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Moved from the developer-workflow document in docs/development/ to
          docs/reference/CONTRIBUTING.md; fixed stale parser path
          (src/tsplib_parser/), removed phantom --config flag references,
          corrected test file name (test_full_pipeline.py), and reworded the
          schema migration section to reflect inline migrations in operations.py.
related_files: [] # markdown relative links, or [] if none
tags: [guide/contributing, guide/development, guide/etl, guide/cli, guide/testing, guide/database, guide/workflow, guide/architecture, guide/setup, notes/development, notes/contribution, notes/testing]
---
# Developer Workflow Guide - TSPLIB95 ETL System

## Development Environment Setup

### Quick Setup (3 steps)

```bash
# 1. Clone and setup
git clone https://github.com/lucasgaldinos/Routing_data.git
cd Routing_data

# 2. Install dependencies with uv (recommended)
uv sync

# 3. Verify installation
uv run converter --help
```

### Alternative Setup (pip)

```bash
# Using pip instead of uv
pip install -e .

# Verify installation
python -m converter.cli.commands --help
```

## Essential Commands

### Development Commands

```bash
# Run tests
uv run pytest                          # All tests
uv run pytest tests/test_full_pipeline.py  # Specific test
uv run pytest -v -s                   # Verbose output

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Type checking
uv run mypy src/

# Code formatting
uv run black src/ tests/
uv run isort src/ tests/

# Linting
uv run flake8 src/ tests/
```

### CLI Commands

```bash
# Basic processing
uv run converter process -i datasets_raw/problems -o datasets_processed/

# Development/debugging modes
uv run converter process --verbose --workers 1 --batch-size 10

# Process specific types only
uv run converter process --types TSP --types VRP

# Force reprocessing (ignore change detection)
uv run converter process --force
```

>[!note]
> The `process` command has no `--config` flag — pass options directly as flags (e.g. `--workers`, `--batch-size`, `--types`). `converter init` only writes a configuration template; the CLI does not read it.

### Database Operations

```bash
# Connect to database for inspection
duckdb datasets_processed/db/routing.duckdb

# Within DuckDB shell:
SHOW TABLES;
SELECT COUNT(*) FROM problems;
SELECT type, COUNT(*) FROM problems GROUP BY type;
DESCRIBE problems;
```

## Development Workflows

### 1. Adding New TSPLIB Format Support

**Pattern**: Extend the parser without breaking existing functionality

```bash
# 1. Create test file first
# example.xyz lives in datasets_raw/problems/new_format/
ls datasets_raw/problems/new_format/

# 2. Add parser test
cat > tests/test_new_format.py << 'EOF'
def test_new_format_parsing():
    parser = FormatParser(logger=setup_logging())
    data = parser.parse_file("datasets_raw/problems/new_format/example.xyz")

    assert data['problem_data']['type'] == 'XYZ'
    assert 'nodes' in data
EOF

# 3. Run failing test to confirm
uv run pytest tests/test_new_format.py -v

# 4. Implement parser extension in src/tsplib_parser/
# (Edit converter.py to handle new format)

# 5. Verify test passes
uv run pytest tests/test_new_format.py -v

# 6. Run full integration test
uv run pytest tests/test_full_pipeline.py
```

### 2. Performance Optimization Workflow

**Pattern**: Profile, optimize, validate

```bash
# 1. Create performance benchmark
cat > tests/benchmark_performance.py << 'EOF'
import time
from converter import process_directory

start = time.time()
results = process_directory("datasets_raw/small_subset", "temp_output")
duration = time.time() - start

print(f"Processed {results['total_files']} files in {duration:.2f}s")
print(f"Rate: {results['total_files']/duration:.1f} files/sec")
EOF

# 2. Run baseline benchmark
uv run python tests/benchmark_performance.py

# 3. Profile with memory monitoring
uv run python -m memory_profiler tests/benchmark_performance.py

# 4. Make optimization changes

# 5. Verify performance improvement
uv run python tests/benchmark_performance.py

# 6. Ensure tests still pass
uv run pytest
```

### 3. Database Schema Migration Workflow

**Pattern**: Version-controlled schema changes

```bash
# 1. Add the migration inline in operations.py
# There is no separate migrations/ folder — schema migrations are defined
# directly in src/converter/database/operations.py. Add the DDL there, e.g.:
#   ALTER TABLE problems ADD COLUMN processing_metadata JSON;
#   UPDATE problems SET processing_metadata = '{}';

# 2. Update DatabaseManager to handle migration
# (Edit operations.py to include the new DDL)

# 3. Test migration on copy of database
cp datasets_processed/db/routing.duckdb datasets_processed/db/routing_backup.duckdb
uv run python -c "
from src.converter.database.operations import DatabaseManager
db = DatabaseManager('datasets_processed/db/routing.duckdb')
print('Migration completed')
"

# 4. Verify schema change
duckdb datasets_processed/db/routing.duckdb << 'EOF'
DESCRIBE problems;
EOF

# 5. Update tests for new schema
# 6. Run full test suite
uv run pytest
```

## Testing Strategies

### Unit Testing Pattern

```python
# tests/test_component.py
import pytest
from unittest.mock import Mock, patch
from src.converter.core.transformer import DataTransformer

def test_index_conversion():
    """Test critical 1-based to 0-based conversion."""
    logger = Mock()
    transformer = DataTransformer(logger=logger)

    # Mock TSPLIB data (1-based)
    tsplib_data = {
        'problem_data': {'dimension': 3},
        'tours': [[1, 2, 3, 1]],  # 1-based tour
        'nodes': [
            {'node_id': 1, 'x': 0, 'y': 0},
            {'node_id': 2, 'x': 1, 'y': 1},
            {'node_id': 3, 'x': 2, 'y': 2}
        ]
    }

    result = transformer.transform_problem(tsplib_data)

    # Verify 0-based conversion
    assert result['tours'][0] == [0, 1, 2, 0]  # 0-based tour
    assert result['nodes'][0]['node_id'] == 0   # 0-based node IDs
```

### Integration Testing Pattern

```python
# tests/test_integration.py
def test_end_to_end_pipeline():
    """Test complete pipeline with real data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use real TSPLIB file
        test_file = "datasets_raw/problems/tsp/gr17.tsp"
        output_dir = Path(temp_dir) / "output"

        # Run complete pipeline
        results = process_directory(
            input_dir=Path(test_file).parent,
            output_dir=output_dir,
            workers=1  # Single-threaded for deterministic testing
        )

        # Verify outputs exist
        assert results['processed_files'] == 1
        assert (output_dir / "json" / "tsp" / "gr17.json").exists()

        # Verify database content
        db_path = output_dir / "db" / "routing.duckdb"
        conn = duckdb.connect(str(db_path))

        problems = conn.execute("SELECT name FROM problems").fetchall()
        assert problems[0][0] == "gr17"
```

### Data Quality Testing Pattern

```python
# tests/test_data_quality.py
def test_known_solution_validation():
    """Validate against known optimal solutions."""
    parser = FormatParser(logger=setup_logging())

    # Known problem with known solution
    data = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")

    # Verify problem characteristics
    assert data['problem_data']['dimension'] == 17
    assert data['problem_data']['edge_weight_type'] == 'EUC_2D'

    # If tour file exists, verify optimal value
    if 'tours' in data and data['tours']:
        # gr17 has known optimal value of 2085
        tour = data['tours'][0]
        # Calculate tour distance and compare to known optimal
```

## Debugging Workflows

### Debug Processing Issues

```bash
# 1. Enable verbose logging
export CONVERTER_LOG_LEVEL=DEBUG

# 2. Process single file with debugging
uv run python -c "
import logging
from src.tsplib_parser.parser import FormatParser
from src.converter.utils.logging import setup_logging

logger = setup_logging('DEBUG')
parser = FormatParser(logger=logger)

try:
    data = parser.parse_file('problematic_file.tsp')
    print('Parse successful')
except Exception as e:
    logger.exception('Parse failed')
"

# 3. Inspect intermediate data
uv run python -c "
data = parser.parse_file('file.tsp')
import json
print(json.dumps(data['problem_data'], indent=2))
"
```

### Debug Database Issues

```bash
# 1. Connect to database directly
duckdb datasets_processed/db/routing.duckdb

# 2. Check for data inconsistencies
SELECT p.name, p.dimension, COUNT(n.node_id) as actual_nodes
FROM problems p
LEFT JOIN nodes n ON p.id = n.problem_id
GROUP BY p.id, p.name, p.dimension
HAVING p.dimension != COUNT(n.node_id);

# 3. Check file tracking status
SELECT file_path, processing_status, error_message
FROM file_tracking
WHERE processing_status = 'failed';
```

### Debug Memory Issues

```bash
# 1. Monitor memory usage during processing
uv run python -m memory_profiler -c "
from converter import process_directory
process_directory('large_dataset/', 'output/', workers=1, batch_size=10)
"

# 2. Process with reduced batch sizes
uv run converter process --batch-size 10 --workers 1 --verbose

# 3. Check for memory leaks in long-running processes
uv run python -c "
import psutil
import os
process = psutil.Process(os.getpid())

# Monitor memory during processing
for i in range(100):
    # Process one file
    data = converter.parse_file(f'file_{i}.tsp')

    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f'File {i}: {memory_mb:.1f} MB')
"
```

## Code Quality Workflows

### Pre-commit Checks

```bash
# Set up pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Run tests
uv run pytest tests/ -q

# Check code formatting
uv run black --check src/ tests/

# Check imports
uv run isort --check-only src/ tests/

# Type checking
uv run mypy src/

echo "Pre-commit checks passed!"
EOF

chmod +x .git/hooks/pre-commit
```

### Code Review Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-vrp-support

# 2. Make changes with tests
# (Edit files, add tests)

# 3. Verify all tests pass
uv run pytest

# 4. Check integration with real data
uv run converter process -i datasets_raw/problems/vrp --types VRP --verbose

# 5. Commit with descriptive message
git add .
git commit -m "Add support for VRPTW format

- Extended FormatParser to handle time windows
- Added time_windows field to nodes table
- Updated transformer for time window normalization
- Added comprehensive tests with real VRPTW files

Fixes #123"

# 6. Create pull request
git push origin feature/new-vrp-support
```

## Performance Monitoring

### Regular Performance Checks

```bash
# 1. Automated performance regression test
cat > tests/test_performance_regression.py << 'EOF'
import time
import pytest
from converter import process_directory

@pytest.mark.performance
def test_processing_performance():
    """Ensure processing performance doesn't regress."""
    start = time.time()

    results = process_directory(
        "datasets_raw/problems/tsp/",  # Known dataset
        "temp_output/",
        workers=4
    )

    duration = time.time() - start
    files_per_second = results['processed_files'] / duration

    # Assert minimum performance threshold
    assert files_per_second >= 50, f"Performance regression: {files_per_second:.1f} files/sec"
EOF

# 2. Run performance tests
uv run pytest tests/test_performance_regression.py -v -m performance
```

### Database Performance Monitoring

```sql
-- Monitor query performance in DuckDB
EXPLAIN ANALYZE SELECT p.name, COUNT(n.node_id)
FROM problems p
JOIN nodes n ON p.id = n.problem_id
WHERE p.type = 'TSP' AND p.dimension > 100
GROUP BY p.id, p.name;

-- Check index usage
SHOW INDEX FROM problems;

-- Monitor database size growth
SELECT
  COUNT(*) as total_problems,
  SUM(dimension) as total_nodes,
  COUNT(CASE WHEN type = 'TSP' THEN 1 END) as tsp_count,
  COUNT(CASE WHEN type = 'VRP' THEN 1 END) as vrp_count
FROM problems;
```

## Configuration Management

### Environment-Specific Configurations

```bash
# Development configuration
cat > configs/dev_config.yaml << 'EOF'
input_path: "./datasets_raw/small_subset"  # Smaller dataset for dev
processing:
  batch_size: 10        # Smaller batches for debugging
  max_workers: 1        # Single-threaded for debugging
logging:
  level: "DEBUG"        # Verbose logging
  console: true
EOF

# Production configuration
cat > configs/prod_config.yaml << 'EOF'
input_path: "./datasets_raw/problems"
processing:
  batch_size: 200       # Larger batches for efficiency
  max_workers: 8        # Multi-threaded processing
logging:
  level: "INFO"         # Production logging
  file: "/var/log/converter.log"
EOF

# The CLI does not accept a --config flag; pass the equivalent settings as flags:
uv run converter process -i datasets_raw/problems --workers 8 --batch-size 200
```

## Deployment Workflows

### Package Building

```bash
# 1. Update version
sed -i 's/version = ".*"/version = "1.2.0"/' pyproject.toml

# 2. Build package
uv build

# 3. Test package installation
pip install dist/routing_data-1.2.0-py3-none-any.whl

# 4. Verify CLI works
converter --version
```

### Docker Deployment (if needed)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .

ENTRYPOINT ["converter"]
CMD ["process", "--help"]
```

```bash
# Build and test
docker build -t tsplib-converter .
docker run -v $(pwd)/datasets_raw:/data/input -v $(pwd)/output:/data/output \
  tsplib-converter process -i /data/input -o /data/output
```

This workflow guide provides the essential commands and patterns for productive development in the TSPLIB95 ETL System codebase.
