"""
Tests for converter.database.operations.DatabaseManager - DuckDB database operations.

Tests the actual behavior of DatabaseManager for storing and querying TSPLIB data.
Based on verified system output with temporary databases.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from converter.api import merge_v2_payload
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.utils.exceptions import DatabaseError
from tsplib_parser.parser import FormatParser


class TestDatabaseManagerInitialization:
  """Test DatabaseManager initialization and schema creation."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for database."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  def test_creates_database_file(self, tmpdir):
    """
    WHAT: Test that DatabaseManager creates database file
    WHY: Database file should be created on initialization
    EXPECTED: Database file exists after initialization
    DATA: Temp directory path
    """
    db_path = Path(tmpdir) / "test.duckdb"
    assert not db_path.exists(), "Database shouldn't exist yet"

    db = DatabaseManager(str(db_path))

    assert db_path.exists(), "Database file should be created"

  def test_creates_database_directory(self, tmpdir):
    """
    WHAT: Test that DatabaseManager creates parent directories
    WHY: Should create directories if they don't exist
    EXPECTED: Nested directories are created
    DATA: Nested path like tmpdir/db/data/test.duckdb
    """
    db_path = Path(tmpdir) / "db" / "data" / "test.duckdb"
    assert not db_path.parent.exists(), "Parent directory shouldn't exist"

    db = DatabaseManager(str(db_path))

    assert db_path.parent.exists(), "Parent directories should be created"
    assert db_path.exists(), "Database file should be created"

  def test_initializes_schema(self, tmpdir):
    """
    WHAT: Test that DatabaseManager initializes the schema-v2 tables
    WHY: Schema (hub, type tables, satellites) should be created automatically
    EXPECTED: hub + 5 type tables + satellites exist; `nodes` table is gone
    DATA: Fresh database
    """
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Verify tables exist by querying
    import duckdb

    with duckdb.connect(str(db_path)) as conn:
      tables = conn.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main'
            """).fetchall()

      table_names = [t[0] for t in tables]
      # Hub + 5 per-type tables + 2 satellites (Decision 1/2)
      assert "problems" in table_names
      assert "tsp_problems" in table_names
      assert "atsp_problems" in table_names
      assert "cvrp_problems" in table_names
      assert "hcp_problems" in table_names
      assert "sop_problems" in table_names
      assert "edge_weight_matrices" in table_names
      assert "file_tracking" in table_names
      # The v1 `nodes` row-table is dropped (Decision 3)
      assert "nodes" not in table_names, "v1 nodes table should not exist"


class TestDatabaseManagerInsert:
  """Test DatabaseManager insert operations."""

  @pytest.fixture
  def db(self):
    """Create temporary database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db
    shutil.rmtree(tmpdir)

  @pytest.fixture
  def sample_data(self):
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    return transformer.transform_problem(parsed)

  def test_insert_problem_returns_id(self, db, sample_data):
    """
    WHAT: Test that insert_problem returns problem ID
    WHY: Should return auto-generated ID for reference
    EXPECTED: Returns integer ID (likely 1 for first insert)
    DATA: gr17.tsp problem data
    """
    problem_id = db.insert_problem(sample_data["problem_data"])

    assert isinstance(problem_id, int), "Should return integer ID"
    assert problem_id >= 1, "ID should be positive"

  def test_insert_problem_increments_id(self, db):
    """
    WHAT: Test that insert_problem increments ID for each insert
    WHY: Each problem should get unique sequential ID
    EXPECTED: Second insert returns ID greater than first
    DATA: Two different problems
    """
    parser = FormatParser()
    transformer = DataTransformer()

    # Insert first problem
    parsed1 = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    data1 = transformer.transform_problem(parsed1)
    id1 = db.insert_problem(data1["problem_data"])

    # Insert second problem
    parsed2 = parser.parse_file("datasets_raw/problems/tsp/berlin52.tsp")
    data2 = transformer.transform_problem(parsed2)
    id2 = db.insert_problem(data2["problem_data"])

    assert id2 > id1, "Second ID should be greater than first"

  def test_array_columns_store_vertex_data(self, db):
    """
    WHAT: Schema-v2 round-trip of the per-type array columns (Decision 3)
    WHY: The v1 ``insert_nodes`` row-table is deleted (Task 1.2); vertex data
        is now stored as array columns. Verify a coordinate problem's coords
        round-trips with length == dimension.
    EXPECTED: load() returns a coords array of length == dimension
    DATA: berlin52.tsp (EUC_2D, 52 nodes) via merge_v2_payload
    """
    parsed = FormatParser().parse_file("datasets_raw/problems/tsp/berlin52.tsp")
    transformed = DataTransformer().transform_problem(parsed)

    problem_id = db.insert_problem(merge_v2_payload(transformed))
    loaded = db.load(name="berlin52", type="TSP")

    assert isinstance(problem_id, int)
    assert loaded["dimension"] == 52
    assert loaded["coords"] is not None
    assert len(loaded["coords"]) == 52, "coords array length should match dimension"

  def test_empty_array_column_roundtrip(self, db):
    """
    WHAT: Empty/EXPLICIT problem stores NULL coords without error
    WHY: The v1 ``insert_nodes`` empty-list path is gone; EXPLICIT problems
        have no coordinate nodes, so coords stays NULL (matrix holds data).
    EXPECTED: No exception; load() returns coords None and dimension intact
    DATA: gr17.tsp (EXPLICIT TSP) via merge_v2_payload
    """
    parsed = FormatParser().parse_file("datasets_raw/problems/tsp/gr17.tsp")
    transformed = DataTransformer().transform_problem(parsed)

    problem_id = db.insert_problem(merge_v2_payload(transformed))
    loaded = db.load(name="gr17", type="TSP")

    assert isinstance(problem_id, int)
    assert loaded["dimension"] == 17
    assert loaded["coords"] is None, "EXPLICIT problem has no coordinate rows"

  def test_insert_preserves_problem_data(self, db, sample_data):
    """
    WHAT: Test that inserted problem data is preserved correctly
    WHY: Database should store exact values
    EXPECTED: Query returns same name, type, dimension
    DATA: gr17.tsp
    """
    problem_id = db.insert_problem(sample_data["problem_data"])

    # Query back
    problems = db.query_problems(problem_type="TSP")
    assert len(problems) == 1, "Should find inserted problem"

    problem = problems[0]
    assert problem["name"] == "gr17"
    assert problem["type"] == "TSP"
    assert problem["dimension"] == 17


class TestDatabaseManagerQuery:
  """Test DatabaseManager query operations."""

  @pytest.fixture
  def db_with_data(self):
    """Create database with sample data (v2 write path)."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert sample problems via the v2 single-transaction dispatch
    # (hub + type-table row in one insert_problem(merge_v2_payload(...))).
    parser = FormatParser()
    transformer = DataTransformer()

    files = ["datasets_raw/problems/tsp/gr17.tsp", "datasets_raw/problems/tsp/berlin52.tsp"]

    for file_path in files:
      parsed = parser.parse_file(file_path)
      transformed = transformer.transform_problem(parsed)
      db.insert_problem(merge_v2_payload(transformed))

    yield db
    shutil.rmtree(tmpdir)

  def test_query_problems_all(self, db_with_data):
    """
    WHAT: Test querying all problems without filters
    WHY: Should return all inserted problems
    EXPECTED: Returns 2 problems
    DATA: gr17.tsp, berlin52.tsp
    """
    problems = db_with_data.query_problems()

    assert len(problems) == 2, "Should return all problems"

  def test_query_problems_by_type(self, db_with_data):
    """
    WHAT: Test querying problems filtered by type
    WHY: Should filter by problem type
    EXPECTED: Returns only TSP problems
    DATA: TSP problems
    """
    problems = db_with_data.query_problems(problem_type="TSP")

    assert len(problems) == 2, "Should return TSP problems"
    assert all(p["type"] == "TSP" for p in problems)

  def test_query_problems_by_dimension_range(self, db_with_data):
    """
    WHAT: Test querying problems by dimension range
    WHY: Should filter by min/max dimension
    EXPECTED: Returns problems within range
    DATA: gr17 (17 nodes), berlin52 (52 nodes)
    """
    # Query for problems with dimension <= 20
    problems = db_with_data.query_problems(max_dimension=20)

    assert len(problems) == 1, "Should return only gr17"
    assert problems[0]["name"] == "gr17"
    assert problems[0]["dimension"] == 17

    # Query for problems with dimension >= 50
    problems = db_with_data.query_problems(min_dimension=50)

    assert len(problems) == 1, "Should return only berlin52"
    assert problems[0]["name"] == "berlin52"
    assert problems[0]["dimension"] == 52

  def test_query_problems_respects_limit(self, db_with_data):
    """
    WHAT: Test that query_problems respects limit parameter
    WHY: Should limit number of results
    EXPECTED: Returns at most limit number of results
    DATA: 2 problems, limit=1
    """
    problems = db_with_data.query_problems(limit=1)

    assert len(problems) == 1, "Should respect limit"


class TestDatabaseManagerStats:
  """Test DatabaseManager statistics methods."""

  @pytest.fixture
  def db_with_data(self):
    """Create database with sample data (v2 write path)."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert sample problems via the v2 single-transaction dispatch
    parser = FormatParser()
    transformer = DataTransformer()

    files = ["datasets_raw/problems/tsp/gr17.tsp", "datasets_raw/problems/tsp/berlin52.tsp"]

    for file_path in files:
      parsed = parser.parse_file(file_path)
      transformed = transformer.transform_problem(parsed)
      db.insert_problem(merge_v2_payload(transformed))

    yield db
    shutil.rmtree(tmpdir)

  def test_get_problem_stats_total_count(self, db_with_data):
    """
    WHAT: Test get_problem_stats returns total count
    WHY: Should count all problems in database
    EXPECTED: total_problems = 2
    DATA: 2 TSP problems
    """
    stats = db_with_data.get_problem_stats()

    assert "total_problems" in stats
    assert stats["total_problems"] == 2, "Should count all problems"

  def test_get_problem_stats_by_type(self, db_with_data):
    """
    WHAT: Test get_problem_stats groups by type
    WHY: Should provide breakdown by problem type
    EXPECTED: Returns counts and averages per type
    DATA: 2 TSP problems
    """
    stats = db_with_data.get_problem_stats()

    assert "by_type" in stats
    by_type = stats["by_type"]

    assert len(by_type) == 1, "Should have 1 type (TSP)"
    tsp_stats = by_type[0]
    assert tsp_stats["type"] == "TSP"
    assert tsp_stats["count"] == 2
    assert tsp_stats["avg_dimension"] == 34.5  # (17 + 52) / 2
    assert tsp_stats["max_dimension"] == 52


class TestDatabaseManagerExport:
  """Test DatabaseManager export functionality."""

  @pytest.fixture
  def db_with_data(self):
    """Create database with one EXPLICIT problem (v2 write path)."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert one problem (gr17, EXPLICIT) via merge_v2_payload so the
    # type-table row (dimension, coords=None) round-trips.
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    transformed = transformer.transform_problem(parsed)

    problem_id = db.insert_problem(merge_v2_payload(transformed))

    yield db, problem_id
    shutil.rmtree(tmpdir)

  def test_export_problem_returns_complete_data(self, db_with_data):
    """
    WHAT: Test that export_problem returns the full schema-v2 row
    WHY: export_problem(problem_id) should return the joined hub + type-table row
    EXPECTED: Returns dict with hub/type keys (name, type, dimension); no v1 'nodes'
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported = db.export_problem(problem_id)

    assert "name" in exported
    assert "type" in exported
    assert "dimension" in exported
    assert "id" in exported
    assert exported["id"] == problem_id
    assert "nodes" not in exported, "schema v2 has no nodes key (Decision 3)"

  def test_export_problem_preserves_problem_data(self, db_with_data):
    """
    WHAT: Test that exported problem data matches original
    WHY: Export should preserve all metadata at the top level
    EXPECTED: name, type, dimension match original
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported = db.export_problem(problem_id)

    assert exported["name"] == "gr17"
    assert exported["type"] == "TSP"
    assert exported["dimension"] == 17

  def test_export_problem_preserves_array_columns(self, db_with_data):
    """
    WHAT: Test that exported vertex data (array columns) is preserved
    WHY: Schema v2 stores vertex data as array columns, not a v1 ``nodes`` list
    EXPECTED: gr17 (EXPLICIT) keeps coords None with the key present
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported = db.export_problem(problem_id)

    assert "nodes" not in exported, "no v1 nodes list"
    assert "coords" in exported
    assert exported["coords"] is None, "EXPLICIT problem has no coordinate rows"
    assert exported["dimension"] == 17
    assert exported["edge_weight_type"] == "EXPLICIT"

  def test_export_problem_nonexistent_raises_error(self, db_with_data):
    """
    WHAT: Test that export_problem raises DatabaseError for a nonexistent id
    WHY: Should validate problem exists (export_problem raises DatabaseError)
    EXPECTED: Raises DatabaseError
    DATA: problem_id=9999 (doesn't exist)
    """
    db, _ = db_with_data

    with pytest.raises(DatabaseError) as exc_info:
      db.export_problem(9999)

    assert "9999" in str(exc_info.value)
    assert "not found" in str(exc_info.value).lower()


class TestDatabaseManagerFileTracking:
  """Test DatabaseManager file tracking functionality."""

  @pytest.fixture
  def db(self):
    """Create temporary database."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db
    shutil.rmtree(tmpdir)

  def test_track_file_stores_info(self, db):
    """
    WHAT: Test that update_file_tracking stores file information
    WHY: Should record file path, problem_id, checksum, size, timestamp
    EXPECTED: get_file_info returns stored data
    DATA: Sample problem + file tracking info
    """
    from datetime import datetime

    # First insert a problem to satisfy foreign key constraint
    problem_data = {
      "name": "test_problem",
      "type": "TSP",
      "comment": "Test",
      "dimension": 5,
      "edge_weight_type": "EUC_2D",
    }
    problem_id = db.insert_problem(problem_data)

    tracking_info = {
      "file_path": "/path/to/problem.tsp",
      "problem_id": problem_id,
      "checksum": "abc123",
      "file_size": 1024,
      "last_processed": datetime.now(),
    }

    db.update_file_tracking(tracking_info)

    # Retrieve
    info = db.get_file_info("/path/to/problem.tsp")

    assert info is not None, "Should retrieve file info"
    assert info["problem_id"] == 1
    assert info["checksum"] == "abc123"
    assert info["file_size"] == 1024

  def test_get_file_info_nonexistent_returns_none(self, db):
    """
    WHAT: Test that get_file_info returns None for nonexistent file
    WHY: Should handle missing files gracefully
    EXPECTED: Returns None
    DATA: Nonexistent file path
    """
    info = db.get_file_info("/nonexistent/file.tsp")

    assert info is None, "Should return None for nonexistent file"


class TestDatabaseManagerIntegration:
  """Test DatabaseManager with complete workflows."""

  @pytest.fixture
  def db(self):
    """Create temporary database."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db
    shutil.rmtree(tmpdir)

  def test_full_workflow_parse_insert_query(self, db):
    """
    WHAT: Test complete workflow: parse → insert → query (schema v2)
    WHY: Verify end-to-end database operations work with the v2 write path
    EXPECTED: Can parse, insert via merge_v2_payload, and retrieve data
    DATA: gr17.tsp
    """
    # Parse and transform
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    transformed = transformer.transform_problem(parsed)

    # Insert (single-transaction dispatch; no v1 insert_nodes / nodes table)
    problem_id = db.insert_problem(merge_v2_payload(transformed))

    # Query
    problems = db.query_problems(problem_type="TSP")
    assert len(problems) == 1

    # Export - returns the flat v2 joined row (no 'problem'/'nodes' nesting)
    exported = db.export_problem(problem_id)
    assert exported["id"] == problem_id
    assert exported["name"] == "gr17"
    assert exported["type"] == "TSP"
    assert exported["dimension"] == 17
    assert "nodes" not in exported, "schema v2 has no nodes key"

    # Stats
    stats = db.get_problem_stats()
    assert stats["total_problems"] == 1
