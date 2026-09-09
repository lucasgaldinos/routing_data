"""
Integration tests for the 'converter inspect' CLI command.

Test Coverage:
- inspect command help and option parsing
- Generic table enumeration (information_schema, no hardcoded names)
- Row counts, schema, and sample rows for --table
- --detail schema output for all tables
"""

from pathlib import Path

import duckdb
import pytest
from click.testing import CliRunner

from converter.cli.commands import cli


@pytest.fixture
def cli_runner() -> CliRunner:
  """
  WHAT: Create Click CLI runner
  WHY: Need runner to test CLI commands
  EXPECTED: CliRunner instance
  DATA: Click's test runner
  """
  return CliRunner()


@pytest.fixture
def inspect_db(tmp_path: Path) -> Path:
  """
  WHAT: Create a small temp DuckDB database for inspection tests
  WHY: Need a real database file for click.Path(exists=True)
  EXPECTED: Path to temp database with two tables
  DATA: problems (2 rows), nodes (1 row)
  """
  db_path = tmp_path / "routing.duckdb"
  conn = duckdb.connect(str(db_path))
  try:
    conn.execute("CREATE TABLE problems (id INTEGER, name VARCHAR)")
    conn.execute("INSERT INTO problems VALUES (1, 'gr17'), (2, 'berlin52')")
    conn.execute("CREATE TABLE nodes (id INTEGER, x DOUBLE, y DOUBLE)")
    conn.execute("INSERT INTO nodes VALUES (1, 0.0, 0.0)")
  finally:
    conn.close()
  return db_path


class TestInspectCommand:
  """Test 'converter inspect' command."""

  def test_inspect_help(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test inspect command help
    WHY: Should display help with all options
    EXPECTED: Exit code 0, options listed
    DATA: converter inspect --help
    """
    result = cli_runner.invoke(cli, ["inspect", "--help"])

    assert result.exit_code == 0
    assert "inspect" in result.output
    assert "--database" in result.output
    assert "--table" in result.output
    assert "--detail" in result.output

  def test_inspect_lists_tables(self, cli_runner: CliRunner, inspect_db: Path) -> None:
    """
    WHAT: Test inspect enumerates tables generically
    WHY: Should list tables with row counts
    EXPECTED: Exit code 0, both tables and row counts shown
    DATA: Temp database with problems + nodes
    """
    result = cli_runner.invoke(cli, ["inspect", "--database", str(inspect_db)])

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "problems" in result.output
    assert "nodes" in result.output
    assert "Rows: 2" in result.output

  def test_inspect_specific_table(self, cli_runner: CliRunner, inspect_db: Path) -> None:
    """
    WHAT: Test inspect with --table filter
    WHY: Should show schema and sample rows for one table
    EXPECTED: Exit code 0, schema + sample data present
    DATA: Temp database, --table problems
    """
    result = cli_runner.invoke(cli, ["inspect", "--database", str(inspect_db), "--table", "problems"])

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Schema" in result.output
    assert "Sample data" in result.output
    assert "gr17" in result.output

  def test_inspect_detail(self, cli_runner: CliRunner, inspect_db: Path) -> None:
    """
    WHAT: Test inspect --detail
    WHY: Should show schema for all tables
    EXPECTED: Exit code 0, schema sections for all tables
    DATA: Temp database, --detail
    """
    result = cli_runner.invoke(cli, ["inspect", "--database", str(inspect_db), "--detail"])

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Schema" in result.output
    assert "nodes" in result.output
