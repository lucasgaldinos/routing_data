"""Tests for database connection / transaction management on the v2 write path (Issue #6)."""

from pathlib import Path

import duckdb
import pytest

from converter.database.operations import DatabaseManager
from converter.utils.logging import setup_logging


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
    problem_id = db_manager.insert_problem(problem_data)

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

  def test_insert_problem_rollback_on_invalid_data(self, temp_output_dir: str) -> None:
    """Test the v2 transaction rolls back when a type-row insert fails."""
    db_path = Path(temp_output_dir) / "test_rollback.duckdb"
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
    with pytest.raises(duckdb.ConstraintException):
      db_manager.insert_problem(invalid_problem_data)

    # Both the hub row and the type-table row must have rolled back
    with duckdb.connect(str(db_path)) as conn:
      problem_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      tsp_count = conn.execute("SELECT COUNT(*) FROM tsp_problems").fetchone()[0]

      assert problem_count == 0, "Hub row should have rolled back"
      assert tsp_count == 0, "Type-table row should have rolled back"

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
    with pytest.raises(duckdb.ConstraintException):
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

    successful = [r for r in results if r is not None]
    assert len(successful) == 10

    # Verify the database has exactly the 10 committed rows and is still usable
    with duckdb.connect(str(db_path)) as conn:
      problem_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
      assert problem_count == 10
      conn.execute("SELECT * FROM problems")

  def test_edge_weight_insertion_with_transaction(self, temp_output_dir: str) -> None:
    """Test the v2 edge_weight_matrices INTEGER[][] insert rides the same transaction."""
    db_path = Path(temp_output_dir) / "test_edge_weights.duckdb"
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
      result = conn.execute(
        "SELECT matrix, matrix_format, is_symmetric FROM edge_weight_matrices WHERE problem_id = ?",
        [problem_id],
      ).fetchone()

      assert result is not None
      stored_matrix = result[0]
      # DuckDB materializes the nested array as nested sequences; compare shape
      assert [list(row) for row in stored_matrix] == [[0, 10, 15], [20, 0, 25], [30, 35, 0]]
      assert result[1] == "FULL_MATRIX"
      assert result[2] is False
