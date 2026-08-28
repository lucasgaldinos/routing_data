---
title: Comprehensive Troubleshooting Guide
description: >
  Common issues, edge cases, and step-by-step resolutions for the TSPLIB95 ETL
  System: file processing, parsing, memory, database, and CLI problems.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Updated output and database paths to the datasets_processed/ layout.
related_files: []
tags: [guide/troubleshooting, notes/issues, guide/cli, guide/database, guide/etl, notes/debugging, analysis/errors, guide/setup, notes/edge-cases, guide/configuration]
---
# Comprehensive Troubleshooting Guide - TSPLIB95 ETL System

## Overview

This guide covers common issues, edge cases, and troubleshooting strategies for the TSPLIB95 ETL System. Each issue includes symptoms, root causes, and step-by-step resolution procedures.

## Troubleshooting Categories

### 1. 📁 File Processing Issues

#### Issue: "No files found to process"

**Symptoms:**

```bash
uv run converter process -i datasets_raw/problems -o datasets_processed/
# Output: Found 0 files to process
```

**Root Causes & Solutions:**

1. **Incorrect file patterns**

    ```bash
    # Check what files actually exist
    find datasets_raw/problems -name "*.tsp" -o -name "*.vrp" | head -10

    # If files have different extensions, update config
    uv run converter process -i datasets_raw/problems --types ALL
    ```

2. **Permission issues**

    ```bash
    # Check file permissions
    ls -la datasets_raw/problems/

    # Fix permissions if needed
    chmod -R +r datasets_raw/problems/
    ```

3. **Symbolic link issues**

    ```bash
    # Check for broken symlinks
    find datasets_raw/problems -type l -exec test ! -e {} \; -print

    # Remove broken symlinks
    find datasets_raw/problems -type l -exec test ! -e {} \; -delete
    ```

4. **Path case sensitivity (Linux/macOS)**

    ```bash
    # Check actual directory structure
    tree datasets_raw/ | head -20

    # Ensure correct case in paths
    uv run converter process -i "$(realpath datasets_raw/problems)" -o datasets_processed/
    ```

#### Issue: "File too large" errors

**Symptoms:**

```
ERROR: File size exceeds limit: huge_problem.tsp (1.2GB > 100MB limit)
```

**Solutions:**

**A. Increase file size limit**

```yaml
# config.yaml
validation:
  max_file_size_mb: 2048  # Increase to 2GB
```

**B. Process large files individually**

```bash
# Process with streaming for very large files
uv run converter process -i large_files/ -o output/ --batch-size 1 --workers 1
```

**C. Split large files (if possible)**

```python
# python script to split large TSPLIB files
def split_large_tsplib(file_path, max_nodes=10000):
    with open(file_path) as f:
        # Read header sections
        # Split COORD_SECTION into chunks
        # Write separate files with proper headers
        pass
```

#### Issue: Character encoding problems

**Symptoms:**

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 10
```

**Solutions:**

**A. Auto-detect encoding**

```bash
# Install chardet for encoding detection
pip install chardet

# Check file encoding
python -c "
import chardet
with open('problematic.tsp', 'rb') as f:
    encoding = chardet.detect(f.read())
    print(f'Detected encoding: {encoding}')
"
```

**B. Convert encoding**

```bash
# Convert to UTF-8 using iconv
iconv -f ISO-8859-1 -t UTF-8 problematic.tsp > converted.tsp

# Or using python
python -c "
import codecs
with codecs.open('problematic.tsp', 'r', 'latin1') as f:
    content = f.read()
with codecs.open('converted.tsp', 'w', 'utf-8') as f:
    f.write(content)
"
```

### 2. 📊 Parsing & Validation Issues

#### Issue: "Invalid TSPLIB format" errors

**Symptoms:**

```
ParsingError: Missing required section: NODE_COORD_SECTION in problem.tsp
```

**Diagnostic Steps:**

**A. Examine file structure**

```bash
# Check file format manually
head -50 problem.tsp

# Look for required sections
grep -n "SECTION\|SPECIFICATION" problem.tsp
```

**B. Validate against TSPLIB specification**

```python
# python validation script
def validate_tsplib_structure(file_path):
    required_fields = ['NAME', 'TYPE', 'DIMENSION']
    required_sections = {
        'TSP': ['NODE_COORD_SECTION'],
        'VRP': ['NODE_COORD_SECTION', 'DEMAND_SECTION'],
        'ATSP': ['EDGE_WEIGHT_SECTION']
    }

    with open(file_path) as f:
        content = f.read()

    # Check required fields
    for field in required_fields:
        if f"{field}:" not in content:
            print(f"Missing required field: {field}")

    # Check sections based on type
    # Implementation details...
```

**Solutions:**

**A. Relaxed parsing mode**

```python
# Enable relaxed parsing in code
parser = TSPLIBParser(logger=logger)
try:
    data = parser.parse_file(file_path)
except ParsingError:
    # Try with relaxed validation
    data = parser.parse_file(file_path, strict=False)
```

**B. Manual file repair**

```bash
# Add missing sections if data exists
echo "NODE_COORD_SECTION" >> problem.tsp
# Add coordinate data...
echo "EOF" >> problem.tsp
```

#### Issue: Dimension mismatch errors

**Symptoms:**

```
ValidationError: DIMENSION (500) doesn't match actual nodes (498)
```

**Solutions:**

**A. Auto-correct dimension**

```python
# Correction logic (implement in transformer)
def fix_dimension_mismatch(problem_data):
    declared_dim = problem_data.get('dimension', 0)
    actual_nodes = len(problem_data.get('nodes', []))

    if declared_dim != actual_nodes:
        logger.warning(f"Dimension mismatch: {declared_dim} vs {actual_nodes}")
        problem_data['dimension'] = actual_nodes
        problem_data['_dimension_corrected'] = True

    return problem_data
```

**B. Manual file correction**

```bash
# Count actual nodes
grep -c "^[0-9]" coords_section.txt

# Update DIMENSION field
sed -i 's/DIMENSION: 500/DIMENSION: 498/' problem.tsp
```

#### Issue: Invalid coordinate values

**Symptoms:**

```
ValidationError: Invalid coordinate: node 145 has NaN values (inf, -inf)
```

**Solutions:**

**A. Coordinate sanitization**

```python
def sanitize_coordinates(nodes):
    for node in nodes:
        # Handle NaN/infinity values
        if math.isnan(node['x']) or math.isinf(node['x']):
            node['x'] = 0.0  # or interpolate from neighbors
        if math.isnan(node['y']) or math.isinf(node['y']):
            node['y'] = 0.0
    return nodes
```

**B. Coordinate range validation**

```python
def validate_coordinate_ranges(nodes, problem_type='TSP'):
    bounds = {
        'TSP': {'x': (-1e6, 1e6), 'y': (-1e6, 1e6)},
        'GEO': {'x': (-180, 180), 'y': (-90, 90)}  # longitude, latitude
    }

    for node in nodes:
        x_min, x_max = bounds[problem_type]['x']
        y_min, y_max = bounds[problem_type]['y']

        if not (x_min <= node['x'] <= x_max):
            raise ValidationError(f"X coordinate out of range: {node['x']}")
```

### 3. 🔄 Transformation Issues

#### Issue: Index conversion problems

**Symptoms:**

```
IndexError: Node index 0 not found (expecting 1-based indexing)
```

**Diagnostic Steps:**

```python
# Check indexing pattern in original file
def analyze_indexing(file_path):
    with open(file_path) as f:
        content = f.read()

    # Look for node indices
    import re
    node_pattern = r'^(\d+)\s+[\d\.\-\s]+'
    matches = re.findall(node_pattern, content, re.MULTILINE)

    if matches:
        indices = [int(m) for m in matches[:10]]
        print(f"First 10 node indices: {indices}")

        if min(indices) == 0:
            print("0-based indexing detected")
        elif min(indices) == 1:
            print("1-based indexing detected")
        else:
            print(f"Non-standard indexing: starts at {min(indices)}")
```

**Solutions:**

**A. Smart index detection**

```python
def detect_and_convert_indices(problem_data):
    nodes = problem_data.get('nodes', [])
    if not nodes:
        return problem_data

    # Detect indexing scheme
    min_id = min(node['node_id'] for node in nodes)

    if min_id == 0:
        # Already 0-based, no conversion needed
        logger.info("0-based indexing detected, no conversion needed")
        return problem_data
    elif min_id == 1:
        # Convert 1-based to 0-based
        for node in nodes:
            node['node_id'] -= 1

        # Convert tours if present
        for tour in problem_data.get('tours', []):
            for i in range(len(tour)):
                tour[i] -= 1

        logger.info("Converted 1-based to 0-based indexing")
    else:
        # Non-standard indexing, create mapping
        id_mapping = {old_id: i for i, old_id in enumerate(sorted(set(node['node_id'] for node in nodes)))}

        for node in nodes:
            node['node_id'] = id_mapping[node['node_id']]

        logger.warning(f"Non-standard indexing converted, started at {min_id}")

    return problem_data
```

#### Issue: VRP-specific transformation errors

**Symptoms:**

```
ValidationError: VRP problem has no depots defined
```

**Solutions:**

**A. Default depot assignment**

```python
def ensure_vrp_depots(problem_data):
    if problem_data['type'] != 'VRP':
        return problem_data

    nodes = problem_data.get('nodes', [])
    depots = [n for n in nodes if n.get('is_depot', False)]

    if not depots:
        # Assign first node as depot
        if nodes:
            nodes[0]['is_depot'] = True
            logger.warning("No depots found, assigned first node as depot")
        else:
            raise ValidationError("VRP problem has no nodes")

    return problem_data
```

**B. Demand validation and normalization**

```python
def normalize_vrp_demands(problem_data):
    if problem_data['type'] != 'VRP':
        return problem_data

    nodes = problem_data.get('nodes', [])
    capacity = problem_data.get('capacity')

    for node in nodes:
        demand = node.get('demand', 0)

        # Handle negative demands
        if demand < 0:
            logger.warning(f"Negative demand {demand} for node {node['node_id']}, setting to 0")
            node['demand'] = 0

        # Check against capacity
        if capacity and demand > capacity:
            logger.warning(f"Demand {demand} exceeds capacity {capacity} for node {node['node_id']}")
            # Could scale down or flag as infeasible

    return problem_data
```

### 4. 💾 Database Issues

#### Issue: Database connection failures

**Symptoms:**

```
DatabaseError: Could not connect to database: datasets_processed/db/routing.duckdb
sqlite3.OperationalError: database is locked
```

**Solutions:**

**A. Check database locks**

```bash
# Check for processes using the database
lsof datasets_processed/db/routing.duckdb

# Kill processes if necessary (be careful!)
kill -9 <process_id>
```

**B. Database recovery**

```bash
# Backup existing database
cp datasets_processed/db/routing.duckdb datasets_processed/db/routing.duckdb.backup

# Test database integrity
duckdb datasets_processed/db/routing.duckdb "PRAGMA integrity_check;"

# If corrupted, restore from backup or rebuild
rm datasets_processed/db/routing.duckdb
uv run converter process --force -i datasets_raw/problems -o datasets_processed/
```

**C. Connection pool management**

```python
# Implement proper connection handling
class DatabaseManager:
    def __init__(self, db_path, max_connections=10):
        self.connection_pool = queue.Queue(maxsize=max_connections)

        # Pre-create connections
        for _ in range(max_connections):
            conn = duckdb.connect(db_path)
            self.connection_pool.put(conn)

    def get_connection(self, timeout=30):
        try:
            return self.connection_pool.get(timeout=timeout)
        except queue.Empty:
            raise DatabaseError("No database connections available")

    def return_connection(self, conn):
        self.connection_pool.put(conn)
```

#### Issue: Transaction deadlocks

**Symptoms:**

```
DatabaseError: Transaction deadlock detected
duckdb.Error: Constraint Error: Conflicting concurrent update
```

**Solutions:**

**A. Retry mechanism with exponential backoff**

```python
import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries):
        try:
            return func()
        except DatabaseError as e:
            if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"Deadlock detected, retrying in {delay:.2f}s (attempt {attempt + 1})")
                time.sleep(delay)
            else:
                raise
```

**B. Transaction scope optimization**

```python
def insert_problem_atomic(db_manager, problem_data):
    with db_manager.get_connection() as conn:
        try:
            conn.execute("BEGIN TRANSACTION")

            # Insert in specific order to avoid deadlocks
            problem_id = insert_problem_metadata(conn, problem_data['problem_data'])
            insert_nodes_batch(conn, problem_id, problem_data['nodes'])
            insert_edges_batch(conn, problem_id, problem_data.get('edges', []))
            insert_tours_batch(conn, problem_id, problem_data.get('tours', []))

            conn.execute("COMMIT")
            return problem_id
        except Exception as e:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Transaction failed: {e}")
```

### 5. 👥 Parallel Processing Issues

#### Issue: Worker process crashes

**Symptoms:**

```
ERROR: Worker process 3 crashed with exit code -11 (SIGSEGV)
Processing incomplete: 450/500 files completed
```

**Diagnostic Steps:**

**A. Check system resources**

```bash
# Monitor memory usage during processing
watch -n 1 'ps aux | grep converter | head -10'

# Check system limits
ulimit -a

# Monitor system messages
dmesg | tail -20
```

**B. Enable core dumps for debugging**

```bash
# Enable core dumps
ulimit -c unlimited

# Set core dump pattern
echo "/tmp/core.%e.%p" | sudo tee /proc/sys/kernel/core_pattern

# Run with debugging
uv run converter process --debug --workers 1 -i problematic_files/
```

**Solutions:**

**A. Memory limit enforcement**

```python
import psutil
import os

class WorkerMemoryMonitor:
    def __init__(self, max_memory_mb=2048):
        self.max_memory_mb = max_memory_mb
        self.process = psutil.Process()

    def check_memory_usage(self):
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        if memory_mb > self.max_memory_mb:
            logger.error(f"Memory limit exceeded: {memory_mb:.1f}MB > {self.max_memory_mb}MB")
            # Force garbage collection
            import gc
            gc.collect()

            # Check again after GC
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            if memory_mb > self.max_memory_mb * 1.1:  # 10% grace period
                raise MemoryError(f"Memory limit exceeded after GC: {memory_mb:.1f}MB")
```

**B. Graceful worker restart**

```python
def process_with_worker_restart(file_batch, worker_id):
    memory_monitor = WorkerMemoryMonitor()

    for i, file_path in enumerate(file_batch):
        try:
            # Check memory before processing each file
            memory_monitor.check_memory_usage()

            # Process file
            result = process_single_file(file_path)

            # Force GC every 10 files
            if i % 10 == 9:
                import gc
                gc.collect()

        except MemoryError:
            logger.warning(f"Worker {worker_id} restarting due to memory pressure")
            # Signal for worker restart
            return {'restart_needed': True, 'processed': i}
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            continue

    return {'completed': True, 'processed': len(file_batch)}
```

#### Issue: Load balancing problems

**Symptoms:**

```
Worker 1: 95% CPU usage, processing large files
Worker 2-4: 5% CPU usage, waiting for work
Processing rate: 2 files/sec (expected: 20 files/sec)
```

**Solutions:**

**A. File size-based batching**

```python
def create_balanced_batches(file_list, num_workers=4):
    # Get file sizes
    file_sizes = []
    for file_path in file_list:
        size = os.path.getsize(file_path)
        file_sizes.append((file_path, size))

    # Sort by size (largest first)
    file_sizes.sort(key=lambda x: x[1], reverse=True)

    # Create balanced batches using longest processing time algorithm
    batches = [[] for _ in range(num_workers)]
    batch_sizes = [0] * num_workers

    for file_path, size in file_sizes:
        # Assign to least loaded worker
        min_worker = min(range(num_workers), key=lambda i: batch_sizes[i])
        batches[min_worker].append(file_path)
        batch_sizes[min_worker] += size

    return batches
```

**B. Dynamic work stealing**

```python
import queue
import threading

class DynamicWorkQueue:
    def __init__(self, file_list):
        self.work_queue = queue.Queue()
        self.completed = queue.Queue()
        self.lock = threading.Lock()

        # Add all files to work queue
        for file_path in file_list:
            self.work_queue.put(file_path)

    def get_next_file(self, worker_id, timeout=1):
        try:
            return self.work_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def mark_completed(self, file_path, result):
        self.completed.put((file_path, result))
        self.work_queue.task_done()
```

### 6. 📤 Output Issues

#### Issue: JSON serialization errors

**Symptoms:**

```
TypeError: Object of type numpy.float64 is not JSON serializable
```

**Solutions:**

**A. Custom JSON encoder**

```python
import json
import numpy as np
from decimal import Decimal

class TSPLIBJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        return super().default(obj)

# Use custom encoder
json.dump(data, f, cls=TSPLIBJSONEncoder, indent=2)
```

**B. Data sanitization before JSON output**

```python
def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()  # Convert to python native type
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    else:
        return str(obj)  # Fallback to string representation
```

#### Issue: File system permissions for output

**Symptoms:**

```
PermissionError: [Errno 13] Permission denied: 'datasets_processed/json/tsp/gr17.json'
```

**Solutions:**

**A. Directory creation with proper permissions**

```python
def ensure_output_directory(output_path, mode=0o755):
    directory = os.path.dirname(output_path)

    try:
        os.makedirs(directory, mode=mode, exist_ok=True)
    except PermissionError:
        # Try to create in user's home directory instead
        home_dir = os.path.expanduser("~/converter_output")
        alternative_path = output_path.replace(directory, home_dir)

        logger.warning(f"Cannot write to {directory}, using {home_dir}")
        os.makedirs(os.path.dirname(alternative_path), mode=mode, exist_ok=True)

        return alternative_path

    return output_path
```

**B. Atomic file writing**

```python
import tempfile
import shutil

def write_json_atomic(data, output_path):
    # Write to temporary file first
    temp_fd, temp_path = tempfile.mkstemp(
        suffix='.json.tmp',
        dir=os.path.dirname(output_path)
    )

    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(data, f, cls=TSPLIBJSONEncoder, indent=2)

        # Atomic rename
        shutil.move(temp_path, output_path)

    except Exception:
        # Clean up temporary file on error
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise
```

## Edge Case Handling Strategies

### Extreme Dataset Characteristics

#### Single-node problems (dimension=1)

```python
def handle_single_node_problem(problem_data):
    if problem_data.get('dimension', 0) == 1:
        logger.info("Single-node problem detected")

        # Ensure minimal valid structure
        nodes = problem_data.setdefault('nodes', [])
        if not nodes:
            nodes.append({
                'node_id': 0,
                'x': 0.0,
                'y': 0.0,
                'demand': 0,
                'is_depot': True  # Single node is depot for VRP
            })

        # Tours for single node
        tours = problem_data.setdefault('tours', [])
        if not tours:
            tours.append([0, 0])  # Tour from node to itself

    return problem_data
```

#### Massive problems (dimension > 100,000)

```python
def handle_massive_problems(problem_data):
    dimension = problem_data.get('dimension', 0)

    if dimension > 100000:
        logger.warning(f"Large problem detected: {dimension} nodes")

        # Enable streaming mode
        problem_data['_streaming_mode'] = True

        # Disable edge precomputation
        problem_data['_skip_edges'] = True

        # Use batch processing for nodes
        problem_data['_batch_size'] = 1000

    return problem_data
```

#### Degenerate coordinate cases

```python
def handle_degenerate_coordinates(nodes):
    # Check if all nodes are at same location
    if len(nodes) > 1:
        first_node = nodes[0]
        all_same = all(
            abs(node['x'] - first_node['x']) < 1e-9 and
            abs(node['y'] - first_node['y']) < 1e-9
            for node in nodes[1:]
        )

        if all_same:
            logger.warning("All nodes at same location, adding small perturbations")

            # Add small random perturbations
            import random
            for i, node in enumerate(nodes[1:], 1):
                node['x'] += random.uniform(-0.1, 0.1)
                node['y'] += random.uniform(-0.1, 0.1)

    return nodes
```

## Performance Troubleshooting

### Memory Issues

#### Diagnosing memory leaks

```bash
# Monitor memory usage over time
while true; do
    ps aux | grep converter | awk '{print $6, $11}' | sort -n
    sleep 5
done

# Use memory profiler
pip install memory-profiler psutil
uv run python -m memory_profiler converter_script.py
```

#### Memory optimization

```python
# Force garbage collection between batches
import gc
import weakref

class MemoryOptimizedProcessor:
    def __init__(self):
        self.weak_refs = []

    def process_batch(self, files):
        for file_path in files:
            result = self.process_file(file_path)

            # Store weak reference for debugging
            self.weak_refs.append(weakref.ref(result))

            # Process result immediately
            self.output_result(result)

            # Clear reference
            del result

        # Force garbage collection after batch
        gc.collect()

        # Check for memory leaks
        active_refs = sum(1 for ref in self.weak_refs if ref() is not None)
        if active_refs > 100:
            logger.warning(f"Possible memory leak: {active_refs} objects still referenced")
```

### Performance Bottlenecks

#### I/O bottleneck identification

```python
import time
import contextlib

@contextlib.contextmanager
def timing_context(operation_name):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation_name} took {duration:.3f} seconds")

# Use in processing pipeline
def process_file_with_timing(file_path):
    with timing_context("File read"):
        content = read_file(file_path)

    with timing_context("Parsing"):
        parsed_data = parse_content(content)

    with timing_context("Database insert"):
        insert_to_database(parsed_data)
```

This comprehensive troubleshooting guide should help identify and resolve most issues that users might encounter with the TSPLIB95 ETL System.
