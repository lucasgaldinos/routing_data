"""
Tests for converter.database.operations.DatabaseManager - DuckDB database operations.

Tests the actual behavior of DatabaseManager for storing and querying TSPLIB data.
Based on verified system output with temporary databases.
"""

from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pytest

from converter.api import merge_v2_payload
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.utils.exceptions import DatabaseError
from converter.utils.logging import setup_logging
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult


class TestDatabaseManagerInitialization:
  """Test DatabaseManager initialization and schema creation."""

  @pytest.mark.database
  def test_creates_database_file(self, tmp_path: Path) -> None:
    """
    WHAT: Test that DatabaseManager creates database file
    WHY: Database file should be created on initialization
    EXPECTED: Database file exists after initialization
    DATA: Temp directory path
    """
    db_path: Path = Path(tmp_path) / "test.duckdb"
    assert not db_path.exists(), "Database shouldn't exist yet"

    DatabaseManager(str(db_path))

    assert db_path.exists(), "Database file should be created"

  @pytest.mark.database
  def test_creates_database_directory(self, tmp_path: Path) -> None:
    """
    WHAT: Test that DatabaseManager creates parent directories
    WHY: Should create directories if they don't exist
    EXPECTED: Nested directories are created
    DATA: Nested path like tmp_path/db/data/test.duckdb
    """
    db_path = Path(tmp_path) / "db" / "data" / "test.duckdb"
    assert not db_path.parent.exists(), "Parent directory shouldn't exist"

    DatabaseManager(str(db_path))

    assert db_path.parent.exists(), "Parent directories should be created"
    assert db_path.exists(), "Database file should be created"

  @pytest.mark.database
  def test_initializes_schema(self, tmp_path: Path) -> None:
    """
    WHAT: Test that DatabaseManager initializes the schema-v2 tables
    WHY: Schema (hub, type tables, satellites) should be created automatically
    EXPECTED: hub + 5 type tables + satellites exist; `nodes` table is gone
    DATA: Fresh database
    """
    db_path: Path = Path(tmp_path) / "test.duckdb"
    DatabaseManager(str(db_path))

    # Verify tables exist by querying
    import duckdb

    with duckdb.connect(str(db_path)) as conn:
      tables: list[tuple[Any, ...]] = conn.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main'
            """).fetchall()

      table_names: list[Any] = [t[0] for t in tables]
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
  def db(self, tmp_path: Path) -> Generator[DatabaseManager, Any, None]:
    """Create temporary database for testing."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db

  @pytest.fixture
  def sample_data(self, dataset_path: Callable[..., str]) -> dict[str, Any]:
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    return transformer.transform_problem(parsed)

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_insert_problem_returns_id(self, db: DatabaseManager, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that insert_problem returns problem ID
    WHY: Should return auto-generated ID for reference
    EXPECTED: Returns integer ID (likely 1 for first insert)
    DATA: gr17.tsp problem data
    """
    problem_id: int = db.insert_problem(sample_data["problem_data"])

    assert isinstance(problem_id, int), "Should return integer ID"
    assert problem_id >= 1, "ID should be positive"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_insert_problem_increments_id(self, db: DatabaseManager, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Test that insert_problem increments ID for each insert
    WHY: Each problem should get unique sequential ID
    EXPECTED: Second insert returns ID greater than first
    DATA: Two different problems
    """
    parser = FormatParser()
    transformer = DataTransformer()

    # Insert first problem
    parsed1: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    data1: dict[str, Any] = transformer.transform_problem(parsed1)
    id1 = db.insert_problem(data1["problem_data"])

    # Insert second problem
    parsed2: ParseResult = parser.parse_file(dataset_path("tsp", "berlin52.tsp"))
    data2: dict[str, Any] = transformer.transform_problem(parsed2)
    id2: int = db.insert_problem(data2["problem_data"])

    assert id2 > id1, "Second ID should be greater than first"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_array_columns_store_vertex_data(self, db: DatabaseManager, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Schema-v2 round-trip of the per-type array columns (Decision 3)
    WHY: The v1 ``insert_nodes`` row-table is deleted (Task 1.2); vertex data
        is now stored as array columns. Verify a coordinate problem's coords
        round-trips with length == dimension.
    EXPECTED: load() returns a coords array of length == dimension
    DATA: berlin52.tsp (EUC_2D, 52 nodes) via merge_v2_payload
    """
    parsed: ParseResult = FormatParser().parse_file(dataset_path("tsp", "berlin52.tsp"))
    transformed: dict[str, Any] = DataTransformer().transform_problem(parsed)

    problem_id: int = db.insert_problem(merge_v2_payload(transformed))
    loaded: dict[str, Any] = db.load(name="berlin52", type="TSP")

    assert isinstance(problem_id, int)
    assert loaded["dimension"] == 52
    assert loaded["coords"] is not None
    assert len(loaded["coords"]) == 52, "coords array length should match dimension"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_empty_array_column_roundtrip(self, db: DatabaseManager, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Empty/EXPLICIT problem stores NULL coords without error
    WHY: The v1 ``insert_nodes`` empty-list path is gone; EXPLICIT problems
        have no coordinate nodes, so coords stays NULL (matrix holds data).
    EXPECTED: No exception; load() returns coords None and dimension intact
    DATA: gr17.tsp (EXPLICIT TSP) via merge_v2_payload
    """
    parsed: ParseResult = FormatParser().parse_file(dataset_path("tsp", "gr17.tsp"))
    transformed: dict[str, Any] = DataTransformer().transform_problem(parsed)

    problem_id: int = db.insert_problem(merge_v2_payload(transformed))
    loaded: dict[str, Any] = db.load(name="gr17", type="TSP")

    assert isinstance(problem_id, int)
    assert loaded["dimension"] == 17
    assert loaded["coords"] is None, "EXPLICIT problem has no coordinate rows"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_insert_preserves_problem_data(self, db: DatabaseManager, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that inserted problem data is preserved correctly
    WHY: Database should store exact values
    EXPECTED: Query returns same name, type, dimension
    DATA: gr17.tsp
    """
    db.insert_problem(sample_data["problem_data"])

    # Query back
    problems: list[dict[str, Any]] = db.query_problems(problem_type="TSP")
    assert len(problems) == 1, "Should find inserted problem"

    problem: dict[str, Any] = problems[0]
    assert problem["name"] == "gr17"
    assert problem["type"] == "TSP"
    assert problem["dimension"] == 17


class TestDatabaseManagerQuery:
  """Test DatabaseManager query operations."""

  @pytest.fixture
  def db_with_data(self, tmp_path: Path, dataset_path: Callable[..., str]) -> Generator[DatabaseManager, Any, None]:
    """Create database with sample data (v2 write path)."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert sample problems via the v2 single-transaction dispatch
    # (hub + type-table row in one insert_problem(merge_v2_payload(...))).
    parser = FormatParser()
    transformer = DataTransformer()

    files: list[str] = [dataset_path("tsp", "gr17.tsp"), dataset_path("tsp", "berlin52.tsp")]

    for file_path in files:
      parsed: ParseResult = parser.parse_file(file_path)
      transformed: dict[str, Any] = transformer.transform_problem(parsed)
      db.insert_problem(merge_v2_payload(transformed))

    yield db

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_query_problems_all(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test querying all problems without filters
    WHY: Should return all inserted problems
    EXPECTED: Returns 2 problems
    DATA: gr17.tsp, berlin52.tsp
    """
    problems: list[dict[str, Any]] = db_with_data.query_problems()

    assert len(problems) == 2, "Should return all problems"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_query_problems_by_type(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test querying problems filtered by type
    WHY: Should filter by problem type
    EXPECTED: Returns only TSP problems
    DATA: TSP problems
    """
    problems: list[dict[str, Any]] = db_with_data.query_problems(problem_type="TSP")

    assert len(problems) == 2, "Should return TSP problems"
    assert all(p["type"] == "TSP" for p in problems)

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_query_problems_by_dimension_range(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test querying problems by dimension range
    WHY: Should filter by min/max dimension
    EXPECTED: Returns problems within range
    DATA: gr17 (17 nodes), berlin52 (52 nodes)
    """
    # Query for problems with dimension <= 20
    problems: list[dict[str, Any]] = db_with_data.query_problems(max_dimension=20)

    assert len(problems) == 1, "Should return only gr17"
    assert problems[0]["name"] == "gr17"
    assert problems[0]["dimension"] == 17

    # Query for problems with dimension >= 50
    problems = db_with_data.query_problems(min_dimension=50)

    assert len(problems) == 1, "Should return only berlin52"
    assert problems[0]["name"] == "berlin52"
    assert problems[0]["dimension"] == 52

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_query_problems_respects_limit(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test that query_problems respects limit parameter
    WHY: Should limit number of results
    EXPECTED: Returns at most limit number of results
    DATA: 2 problems, limit=1
    """
    problems: list[dict[str, Any]] = db_with_data.query_problems(limit=1)

    assert len(problems) == 1, "Should respect limit"


class TestDatabaseManagerStats:
  """Test DatabaseManager statistics methods."""

  @pytest.fixture
  def db_with_data(self, tmp_path: Path, dataset_path: Callable[..., str]) -> Generator[DatabaseManager, Any, None]:
    """Create database with sample data (v2 write path)."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert sample problems via the v2 single-transaction dispatch
    parser = FormatParser()
    transformer = DataTransformer()

    files: list[str] = [dataset_path("tsp", "gr17.tsp"), dataset_path("tsp", "berlin52.tsp")]

    for file_path in files:
      parsed: ParseResult = parser.parse_file(file_path)
      transformed: dict[str, Any] = transformer.transform_problem(parsed)
      db.insert_problem(merge_v2_payload(transformed))

    yield db

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_get_problem_stats_total_count(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test get_problem_stats returns total count
    WHY: Should count all problems in database
    EXPECTED: total_problems = 2
    DATA: 2 TSP problems
    """
    stats: dict[str, Any] = db_with_data.get_problem_stats()

    assert "total_problems" in stats
    assert stats["total_problems"] == 2, "Should count all problems"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_get_problem_stats_by_type(self, db_with_data: DatabaseManager) -> None:
    """
    WHAT: Test get_problem_stats groups by type
    WHY: Should provide breakdown by problem type
    EXPECTED: Returns counts and averages per type
    DATA: 2 TSP problems
    """
    stats: dict[str, Any] = db_with_data.get_problem_stats()

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
  def db_with_data(
    self, tmp_path: Path, dataset_path: Callable[..., str]
  ) -> Generator[tuple[DatabaseManager, int], Any, None]:
    """Create database with one EXPLICIT problem (v2 write path)."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))

    # Insert one problem (gr17, EXPLICIT) via merge_v2_payload so the
    # type-table row (dimension, coords=None) round-trips.
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    transformed: dict[str, Any] = transformer.transform_problem(parsed)

    problem_id: int = db.insert_problem(merge_v2_payload(transformed))

    yield db, problem_id

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_export_problem_returns_complete_data(self, db_with_data: tuple[DatabaseManager, int]) -> None:
    """
    WHAT: Test that export_problem returns the full schema-v2 row
    WHY: export_problem(problem_id) should return the joined hub + type-table row
    EXPECTED: Returns dict with hub/type keys (name, type, dimension); no v1 'nodes'
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported: dict[str, Any] = db.export_problem(problem_id)

    assert "name" in exported
    assert "type" in exported
    assert "dimension" in exported
    assert "id" in exported
    assert exported["id"] == problem_id
    assert "nodes" not in exported, "schema v2 has no nodes key (Decision 3)"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_export_problem_preserves_problem_data(self, db_with_data: tuple[DatabaseManager, int]) -> None:
    """
    WHAT: Test that exported problem data matches original
    WHY: Export should preserve all metadata at the top level
    EXPECTED: name, type, dimension match original
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported: dict[str, Any] = db.export_problem(problem_id)

    assert exported["name"] == "gr17"
    assert exported["type"] == "TSP"
    assert exported["dimension"] == 17

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_export_problem_preserves_array_columns(self, db_with_data: tuple[DatabaseManager, int]) -> None:
    """
    WHAT: Test that exported vertex data (array columns) is preserved
    WHY: Schema v2 stores vertex data as array columns, not a v1 ``nodes`` list
    EXPECTED: gr17 (EXPLICIT) keeps coords None with the key present
    DATA: gr17.tsp
    """
    db, problem_id = db_with_data

    exported: dict[str, Any] = db.export_problem(problem_id)

    assert "nodes" not in exported, "no v1 nodes list"
    assert "coords" in exported
    assert exported["coords"] is None, "EXPLICIT problem has no coordinate rows"
    assert exported["dimension"] == 17
    assert exported["edge_weight_type"] == "EXPLICIT"

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_export_problem_nonexistent_raises_error(self, db_with_data: tuple[DatabaseManager, int]) -> None:
    """
    WHAT: Test that export_problem raises DatabaseError for a nonexistent id
    WHY: Should validate problem exists (export_problem raises DatabaseError)
    EXPECTED: Raises DatabaseError
    DATA: problem_id=9999 (doesn't exist)
    """
    db, _ = db_with_data

    with pytest.raises(expected_exception=DatabaseError, match="9999") as exc_info:
      db.export_problem(9999)

    assert "9999" in str(exc_info.value)
    assert "not found" in str(exc_info.value).lower()


class TestDatabaseManagerFileTracking:
  """Test DatabaseManager file tracking functionality."""

  @pytest.fixture
  def db(self, tmp_path: Path) -> Generator[DatabaseManager, Any, None]:
    """Create temporary database."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db

  @pytest.mark.database
  def test_track_file_stores_info(self, db: DatabaseManager) -> None:
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
    problem_id: int = db.insert_problem(problem_data)

    tracking_info = {
      "file_path": "/path/to/problem.tsp",
      "problem_id": problem_id,
      "checksum": "abc123",
      "file_size": 1024,
      "last_processed": datetime.now(),
    }

    db.update_file_tracking(tracking_info)

    # Retrieve
    info: dict[str, Any] | None = db.get_file_info("/path/to/problem.tsp")

    assert info is not None, "Should retrieve file info"
    assert info["problem_id"] == 1
    assert info["checksum"] == "abc123"
    assert info["file_size"] == 1024

  @pytest.mark.database
  def test_get_file_info_nonexistent_returns_none(self, db: DatabaseManager) -> None:
    """
    WHAT: Test that get_file_info returns None for nonexistent file
    WHY: Should handle missing files gracefully
    EXPECTED: Returns None
    DATA: Nonexistent file path
    """
    info: dict[str, Any] | None = db.get_file_info("/nonexistent/file.tsp")

    assert info is None, "Should return None for nonexistent file"


class TestDatabaseManagerIntegration:
  """Test DatabaseManager with complete workflows."""

  @pytest.fixture
  def db(self, tmp_path: Path) -> Generator[DatabaseManager, Any, None]:
    """Create temporary database."""
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))
    yield db

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_full_workflow_parse_insert_query(self, db: DatabaseManager, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Test complete workflow: parse → insert → query (schema v2)
    WHY: Verify end-to-end database operations work with the v2 write path
    EXPECTED: Can parse, insert via merge_v2_payload, and retrieve data
    DATA: gr17.tsp
    """
    # Parse and transform
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    transformed: dict[str, Any] = transformer.transform_problem(parsed)

    # Insert (single-transaction dispatch; no v1 insert_nodes / nodes table)
    problem_id: int = db.insert_problem(merge_v2_payload(transformed))

    # Query
    problems: list[dict[str, Any]] = db.query_problems(problem_type="TSP")
    assert len(problems) == 1

    # Export - returns the flat v2 joined row (no 'problem'/'nodes' nesting)
    exported: dict[str, Any] = db.export_problem(problem_id)
    assert exported["id"] == problem_id
    assert exported["name"] == "gr17"
    assert exported["type"] == "TSP"
    assert exported["dimension"] == 17
    assert "nodes" not in exported, "schema v2 has no nodes key"

    # Stats
    stats: dict[str, Any] = db.get_problem_stats()
    assert stats["total_problems"] == 1


# ---------------------------------------------------------------------------
# Merged from test_converter/test_database_connection_leak.py on 2026-10-20; bodies unchanged.
# ---------------------------------------------------------------------------


def _table_names(db_path: Path) -> set[str]:
  """Return the set of table names in the database's main schema."""
  with duckdb.connect(str(db_path)) as conn:
    tables = conn.execute(
      """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
        """
    ).fetchall()
  return {t[0] for t in tables}


class TestConnectionLeakFix:
  """Test suite for connection / transaction management in the v2 ``insert_problem`` dispatch."""

  @pytest.mark.database
  @pytest.mark.regression
  def test_insert_problem_success(self, temp_output_dir: str) -> None:
    """Test the v2 single-transaction insert completes and commits hub + type row."""
    db_path = Path(temp_output_dir) / "test_success.duckdb"
    db_manager = DatabaseManager(str(db_path), logger=setup_logging())

    problem_data = {
      "name": "test_problem",
      "type": "TSP",
      "comment": "Test problem",
      "dimension": 3,
      "edge_weight_type": "EUC_2D",
      "edge_weight_format": None,
      "coords": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
    }

    # v2 insert_problem(merged_payload) opens one BEGIN/COMMIT transaction
    problem_id: int = db_manager.insert_problem(problem_data)

    assert problem_id is not None
    assert problem_id > 0

    # Verify the hub + type-table rows committed; the v1 ``nodes`` table is gone
    with duckdb.connect(str(db_path)) as conn:
      problem_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      tsp_count = conn.execute("SELECT COUNT(*) FROM tsp_problems").fetchone()[0]
      dimension = conn.execute("SELECT dimension FROM tsp_problems WHERE problem_id = ?", [problem_id]).fetchone()[0]

      assert problem_count == 1
      assert tsp_count == 1
      assert dimension == 3
    assert "nodes" not in _table_names(db_path), "v1 nodes row-table is gone in schema v2"

  @pytest.mark.database
  @pytest.mark.regression
  def test_insert_problem_rollback_on_invalid_data(self, temp_output_dir: str) -> None:
    """Test the v2 transaction rolls back when a type-row insert fails."""
    db_path: Path = Path(temp_output_dir) / "test_rollback.duckdb"
    db_manager = DatabaseManager(str(db_path), logger=setup_logging())

    # Invalid problem data (dimension None violates tsp_problems NOT NULL)
    invalid_problem_data = {
      "name": "invalid_problem",
      "type": "TSP",
      "comment": "Should fail",
      "dimension": None,
      "edge_weight_type": "EUC_2D",
      "edge_weight_format": None,
    }

    # insert_problem(merge_v2_payload) re-raises the underlying duckdb error
    # (dimension None violates tsp_problems NOT NULL).
    with pytest.raises(duckdb.ConstraintException, match="Constraint Error"):
      db_manager.insert_problem(invalid_problem_data)

    # Both the hub row and the type-table row must have rolled back
    with duckdb.connect(str(db_path)) as conn:
      problem_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      tsp_count = conn.execute("SELECT COUNT(*) FROM tsp_problems").fetchone()[0]

      assert problem_count == 0, "Hub row should have rolled back"
      assert tsp_count == 0, "Type-table row should have rolled back"

  @pytest.mark.database
  @pytest.mark.regression
  def test_connection_cleanup_after_failure(self, temp_output_dir: str) -> None:
    """Verify the database stays usable (no leaked connection) after a failed insert."""
    db_path = Path(temp_output_dir) / "test_cleanup.duckdb"
    db_manager = DatabaseManager(str(db_path), logger=setup_logging())

    # Create a valid problem first
    valid_problem_data = {
      "name": "valid_problem",
      "type": "TSP",
      "dimension": 2,
      "edge_weight_type": "EUC_2D",
    }

    db_manager.insert_problem(valid_problem_data)

    # Now try an invalid insert - should fail but not leak a connection
    invalid_problem_data = {
      "name": "invalid",
      "type": "TSP",
      "dimension": None,  # Violates tsp_problems NOT NULL
    }

    # dimension None violates tsp_problems NOT NULL -> insert_problem re-raises
    # the duckdb error after rolling back its transaction (no leaked connection).
    with pytest.raises(duckdb.ConstraintException, match="Constraint Error"):
      db_manager.insert_problem(invalid_problem_data)

    # Database should still be accessible and writable (no leaked lock)
    with duckdb.connect(str(db_path)) as conn:
      result = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      assert result == 1, "Only the valid problem should remain"

      # Try writing again - should succeed if connection was closed cleanly.
      # Delete child rows first (v2 type table + satellites reference the hub
      # via FK), then the hub row.
      conn.execute("DELETE FROM tsp_problems WHERE problem_id = 1")
      conn.execute("DELETE FROM file_tracking WHERE problem_id = 1")
      conn.execute("DELETE FROM problems WHERE name = 'valid_problem'")
      result = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      assert result == 0

  @pytest.mark.database
  @pytest.mark.regression
  def test_parallel_inserts_no_connection_leak(self, temp_output_dir: str) -> None:
    """Test parallel v2 inserts against a file-backed db don't leak connections."""
    from concurrent.futures import ThreadPoolExecutor

    db_path = Path(temp_output_dir) / "test_parallel.duckdb"
    # ONE shared manager is created up-front (schema DDL runs once). The worker
    # threads all call db_manager.insert_problem(...), which opens a FRESH
    # connection per call. Deliberately NOT constructing a DatabaseManager per
    # thread/request: that re-runs the schema DDL concurrently and triggers a
    # DuckDB "catalog write-write conflict" (verified live).
    db_manager = DatabaseManager(str(db_path), logger=setup_logging())

    def insert_problem(index: int) -> int | None:
      """Insert a TSP problem through the shared manager; even indices succeed."""
      problem_data = {
        "name": f"problem_{index}",
        "type": "TSP",
        "dimension": index if index % 2 == 0 else None,  # Even succeed, odd fail
        "edge_weight_type": "EUC_2D",
      }
      try:
        return db_manager.insert_problem(problem_data)
      except Exception:
        return None

    # Run 20 inserts in parallel (10 succeed, 10 fail)
    with ThreadPoolExecutor(max_workers=4) as executor:
      results = list(executor.map(insert_problem, range(20)))

    successful: list[int] = [r for r in results if r is not None]
    assert len(successful) == 10

    # Verify the database has exactly the 10 committed rows and is still usable
    with duckdb.connect(str(db_path)) as conn:
      problem_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      assert problem_count == 10
      conn.execute("SELECT * FROM problems")

  @pytest.mark.database
  @pytest.mark.regression
  def test_edge_weight_insertion_with_transaction(self, temp_output_dir: str) -> None:
    """Test the v2 edge_weight_matrices INTEGER[][] insert rides the same transaction."""
    db_path: Path = Path(temp_output_dir) / "test_edge_weights.duckdb"
    db_manager = DatabaseManager(str(db_path), logger=setup_logging())

    problem_data = {
      "name": "br17",
      "type": "ATSP",
      "dimension": 3,
      "edge_weight_type": "EXPLICIT",
      "edge_weight_format": "FULL_MATRIX",
      # _insert_batch_satellites consumes keys matrix/matrix_format/is_symmetric
      # and stores the matrix as INTEGER[][], NOT a matrix_json text column.
      "edge_weight_data": {
        "matrix": [[0, 10, 15], [20, 0, 25], [30, 35, 0]],
        "matrix_format": "FULL_MATRIX",
        "is_symmetric": False,
      },
    }

    # Insert with edge weights (INTEGER[][] matrix stored in the same txn)
    problem_id = db_manager.insert_problem(problem_data)

    assert problem_id is not None
    assert problem_id > 0

    # Verify the matrix row committed as INTEGER[][] (no matrix_json column)
    with duckdb.connect(str(db_path)) as conn:
      result: tuple[Any, ...] | None = conn.execute(
        "SELECT matrix, matrix_format, is_symmetric FROM edge_weight_matrices WHERE problem_id = ?",
        [problem_id],
      ).fetchone()

      assert result is not None
      stored_matrix = result[0]
      # DuckDB materializes the nested array as nested sequences; compare shape
      assert [list(row) for row in stored_matrix] == [[0, 10, 15], [20, 0, 25], [30, 35, 0]]
      assert result[1] == "FULL_MATRIX"
      assert result[2] is False
