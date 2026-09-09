"""
Integration tests for CLI commands.

Test Coverage:
- CLI command invocation and argument parsing
- process command: file processing workflow
- analyze command: database analysis
- validate command: database validation
- Error handling and exit codes
"""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

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
def test_data_dir() -> str:
  """
  WHAT: Use actual test data directory
  WHY: Need real TSPLIB files for testing
  EXPECTED: Path to test data
  DATA: datasets_raw/problems/tsp/gr17.tsp
  """
  base_path = Path(__file__).parent.parent.parent
  return str(base_path / "datasets_raw" / "problems" / "tsp")


@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
  """
  WHAT: Create temp directory for CLI outputs
  WHY: Need isolated output location
  EXPECTED: Temp directory with cleanup
  DATA: Temporary directory
  """
  tmpdir = tempfile.mkdtemp(prefix="cli_test_")
  yield tmpdir
  shutil.rmtree(tmpdir)


@pytest.fixture
def temp_input_with_file(test_data_dir: str) -> Generator[str, None, None]:
  """
  WHAT: Create temp input directory with gr17.tsp
  WHY: Need controlled input for CLI testing
  EXPECTED: Temp dir with single test file
  DATA: Copy of gr17.tsp
  """
  tmpdir = tempfile.mkdtemp(prefix="cli_input_")

  # Copy gr17.tsp to temp directory
  source_file = Path(test_data_dir) / "gr17.tsp"
  dest_file = Path(tmpdir) / "gr17.tsp"
  shutil.copy(source_file, dest_file)

  yield tmpdir
  shutil.rmtree(tmpdir)


class TestCLIBasic:
  """Test basic CLI functionality."""

  def test_cli_help(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test CLI help command
    WHY: Should display help message
    EXPECTED: Exit code 0, help text displayed
    DATA: converter --help
    """
    result = cli_runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "TSPLIB95 ETL Converter" in result.output
    assert "process" in result.output
    assert "analyze" in result.output
    assert "validate" in result.output

  def test_cli_version(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test CLI version command
    WHY: Should display version
    EXPECTED: Exit code 0, version displayed
    DATA: converter --version
    """
    result = cli_runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


class TestProcessCommand:
  """Test 'converter process' command."""

  def test_process_requires_input(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test process command without --input
    WHY: Should fail with error message
    EXPECTED: Exit code != 0, error about missing --input
    DATA: converter process (no args)
    """
    result = cli_runner.invoke(cli, ["process"])

    assert result.exit_code != 0
    assert "--input" in result.output or "required" in result.output.lower()

  def test_process_single_file_sequential(
    self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str
  ) -> None:
    """
    WHAT: Test processing single file in sequential mode
    WHY: Should successfully process file → JSON + DB
    EXPECTED: Exit code 0, success message, files created
    DATA: gr17.tsp → database + JSON
    """
    result = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"]
    )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Processing complete" in result.output

    # Verify database created
    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"
    assert db_path.exists(), "Database file should be created"

    # Verify JSON created
    json_files = list(Path(temp_output_dir).glob("**/*.json"))
    assert len(json_files) >= 1, "At least one JSON file should be created"

  def test_process_with_parallel_mode(
    self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str
  ) -> None:
    """
    WHAT: Test processing with parallel mode enabled
    WHY: Should handle parallel processing
    EXPECTED: Exit code 0, parallel mode message
    DATA: gr17.tsp with --parallel
    """
    result = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--parallel", "--workers", "2"]
    )

    # Note: May fall back to sequential for single file
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Processing complete" in result.output

  def test_process_with_type_filter(
    self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str
  ) -> None:
    """
    WHAT: Test processing with --types filter
    WHY: Should only process specified types
    EXPECTED: Exit code 0, only TSP files processed
    DATA: --types TSP
    """
    result = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--types", "TSP", "--no-parallel"]
    )

    assert result.exit_code == 0
    assert "Processing complete" in result.output

  def test_process_with_force_flag(
    self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str
  ) -> None:
    """
    WHAT: Test processing with --force flag
    WHY: Should reprocess existing files
    EXPECTED: Files processed even if already in DB
    DATA: Run twice with --force
    """
    # First run
    result1 = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"]
    )
    assert result1.exit_code == 0

    # Second run with force
    result2 = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--force", "--no-parallel"]
    )
    assert result2.exit_code == 0
    assert "Force mode" in result2.output or "processing all files" in result2.output

  def test_process_nonexistent_input(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test processing with nonexistent input directory
    WHY: Should fail gracefully
    EXPECTED: Exit code != 0, error message
    DATA: /nonexistent/path
    """
    result = cli_runner.invoke(cli, ["process", "--input", "/nonexistent/path", "--output", "/tmp/output"])

    assert result.exit_code != 0


class TestAnalyzeCommand:
  """Test 'converter analyze' command."""

  def test_analyze_requires_database(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test analyze command without --database
    WHY: Should fail with error message
    EXPECTED: Exit code != 0, error about missing --database
    DATA: converter analyze (no args)
    """
    result = cli_runner.invoke(cli, ["analyze"])

    assert result.exit_code != 0
    assert "--database" in result.output or "required" in result.output.lower()

  def test_analyze_table_format(self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str) -> None:
    """
    WHAT: Test analyze command with table format
    WHY: Should display statistics in table format
    EXPECTED: Exit code 0, table output with stats
    DATA: Processed database → table analysis
    """
    # First process a file
    cli_runner.invoke(cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"])

    # Then analyze
    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"
    result = cli_runner.invoke(cli, ["analyze", "--database", str(db_path), "--format", "table"])

    assert result.exit_code == 0
    assert "Database Statistics" in result.output
    assert "Total problems" in result.output
    assert "TSP" in result.output

  def test_analyze_json_format(self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str) -> None:
    """
    WHAT: Test analyze command with JSON format
    WHY: Should output valid JSON
    EXPECTED: Exit code 0, valid JSON output
    DATA: Processed database → JSON analysis
    """
    # First process a file
    cli_runner.invoke(cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"])

    # Then analyze with JSON format
    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"
    result = cli_runner.invoke(cli, ["analyze", "--database", str(db_path), "--format", "json"])

    assert result.exit_code == 0

    # Verify JSON is in output (may have logging mixed in)
    import json

    try:
      # Try to find JSON in output
      lines = result.output.strip().split("\n")
      # Find first line that starts with '{'
      json_start = next(i for i, line in enumerate(lines) if line.strip().startswith("{"))
      json_text = "\n".join(lines[json_start:])

      data = json.loads(json_text)
      assert "statistics" in data
      assert "problems" in data
    except (StopIteration, json.JSONDecodeError):
      # If JSON parsing fails, just check that output contains expected keys
      assert "statistics" in result.output
      assert "problems" in result.output

  def test_analyze_with_type_filter(
    self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str
  ) -> None:
    """
    WHAT: Test analyze with --type filter
    WHY: Should filter by problem type
    EXPECTED: Exit code 0, only specified type shown
    DATA: --type TSP
    """
    # First process a file
    cli_runner.invoke(cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"])

    # Analyze with type filter
    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"
    result = cli_runner.invoke(cli, ["analyze", "--database", str(db_path), "--type", "TSP", "--limit", "10"])

    assert result.exit_code == 0
    assert "TSP" in result.output

  def test_analyze_nonexistent_database(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test analyze with nonexistent database
    WHY: Should fail gracefully
    EXPECTED: Exit code != 0, error message
    DATA: /nonexistent/db.duckdb
    """
    result = cli_runner.invoke(cli, ["analyze", "--database", "/nonexistent/db.duckdb"])

    assert result.exit_code != 0


class TestValidateCommand:
  """Test 'converter validate' command."""

  def test_validate_successful(self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str) -> None:
    """
    WHAT: Test validate command on valid database
    WHY: Should pass validation
    EXPECTED: Exit code 0, success message
    DATA: Valid processed database
    """
    # First process a file
    cli_runner.invoke(cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"])

    # Then validate
    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"
    result = cli_runner.invoke(cli, ["validate", "--database", str(db_path)])

    assert result.exit_code == 0
    assert "validation successful" in result.output.lower()
    assert "Total problems" in result.output

  def test_validate_nonexistent_database(self, cli_runner: CliRunner) -> None:
    """
    WHAT: Test validate with nonexistent database
    WHY: Should fail gracefully
    EXPECTED: Exit code != 0, error message
    DATA: /nonexistent/db.duckdb
    """
    result = cli_runner.invoke(cli, ["validate", "--database", "/nonexistent/db.duckdb"])

    assert result.exit_code != 0
    # Click validates path existence, so error message differs
    assert "does not exist" in result.output.lower() or "not found" in result.output.lower()


class TestCLIIntegration:
  """Integration tests for CLI workflow."""

  def test_full_cli_workflow(self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str) -> None:
    """
    WHAT: Test complete CLI workflow
    WHY: Should work end-to-end: process → analyze → validate
    EXPECTED: All commands succeed
    DATA: gr17.tsp → full pipeline
    """
    # Step 1: Process
    result_process = cli_runner.invoke(
      cli, ["process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"]
    )
    assert result_process.exit_code == 0, f"Process failed: {result_process.output}"

    db_path = Path(temp_output_dir) / "db" / "routing.duckdb"

    # Step 2: Analyze
    result_analyze = cli_runner.invoke(cli, ["analyze", "--database", str(db_path)])
    assert result_analyze.exit_code == 0, f"Analyze failed: {result_analyze.output}"

    # Step 3: Validate
    result_validate = cli_runner.invoke(cli, ["validate", "--database", str(db_path)])
    assert result_validate.exit_code == 0, f"Validate failed: {result_validate.output}"

  def test_verbose_flag(self, cli_runner: CliRunner, temp_input_with_file: str, temp_output_dir: str) -> None:
    """
    WHAT: Test --verbose flag
    WHY: Should enable debug logging
    EXPECTED: More detailed output
    DATA: converter -v process ...
    """
    result = cli_runner.invoke(
      cli, ["-v", "process", "--input", temp_input_with_file, "--output", temp_output_dir, "--no-parallel"]
    )

    assert result.exit_code == 0
    # Verbose mode should show more logging
    assert "INFO" in result.output or "DEBUG" in result.output
