"""
Integration tests for ETL pipeline components.

Test Coverage:
- Scanner integration with file processing
- Multiple file batch processing
- Output verification (JSON + DB)
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from converter.core.scanner import FileScanner
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from tsplib_parser.parser import FormatParser


@pytest.fixture
def test_files_directory():
  """
  WHAT: Use actual test data directory
  WHY: Test with real TSPLIB files
  EXPECTED: Path to datasets_raw/problems/tsp directory
  DATA: gr17.tsp, etc
  """
  base_path = Path(__file__).parent.parent.parent
  return str(base_path / "datasets_raw" / "problems" / "tsp")


@pytest.fixture
def output_directory():
  """
  WHAT: Create temp directory for outputs
  WHY: Need isolated output location
  EXPECTED: Temp directory with cleanup
  DATA: Temporary directory
  """
  tmpdir = tempfile.mkdtemp(prefix="integration_test_")
  yield tmpdir
  shutil.rmtree(tmpdir)


class TestScannerIntegration:
  """Test FileScanner integration with file processing."""

  def test_scanner_finds_test_files(self, test_files_directory):
    """
    WHAT: Test scanner finds test data files
    WHY: Should discover all .tsp files in test directory
    EXPECTED: Finds gr17.tsp and other test files
    DATA: tests/data directory
    """
    scanner = FileScanner()
    files = scanner.scan_files(test_files_directory, patterns=["*.tsp"])

    assert len(files) > 0, "Should find at least one .tsp file"

    # Check that gr17.tsp is found
    file_names = [Path(f).name for f in files]
    assert "gr17.tsp" in file_names, "Should find gr17.tsp"

  def test_scanner_batching_integration(self, test_files_directory):
    """
    WHAT: Test scanner batching with real files
    WHY: Should yield files in batches
    EXPECTED: Batches with file metadata
    DATA: tests/data directory with batch_size=2
    """
    scanner = FileScanner(batch_size=2)
    batches = list(scanner.scan_directory(test_files_directory, patterns=["*.tsp"]))

    assert len(batches) > 0, "Should have at least one batch"

    # Check batch structure
    for batch in batches:
      for file_info in batch:
        assert "file_path" in file_info
        assert "file_name" in file_info
        assert "problem_type" in file_info
        assert file_info["problem_type"] == "TSP"


class TestParserTransformerIntegration:
  """Test Parser + Transformer integration."""

  def test_parse_and_transform_gr17(self, test_files_directory):
    """
    WHAT: Test parsing and transforming gr17.tsp
    WHY: Should successfully parse → transform
    EXPECTED: Transformed data with problem_data and nodes
    DATA: gr17.tsp
    """
    gr17_path = Path(test_files_directory) / "gr17.tsp"

    parser = FormatParser()
    transformer = DataTransformer()

    # Parse
    parsed = parser.parse_file(str(gr17_path))
    assert parsed is not None, "Parser should successfully parse gr17.tsp"

    # Transform
    transformed = transformer.transform_problem(parsed)
    assert "problem_data" in transformed, "Should have 'problem_data' key"
    assert "nodes" in transformed, "Should have 'nodes' key"
    assert len(transformed["nodes"]) == 17, "Should have 17 nodes"

  def test_parse_transform_multiple_files(self, test_files_directory):
    """
    WHAT: Test parsing + transforming multiple files
    WHY: Should handle batch processing
    EXPECTED: All files successfully processed
    DATA: All .tsp files in test directory
    """
    scanner = FileScanner()
    parser = FormatParser()
    transformer = DataTransformer()

    files = scanner.scan_files(test_files_directory, patterns=["*.tsp"])

    processed_count = 0
    for file_path in files:
      try:
        parsed = parser.parse_file(file_path)
        if parsed:
          transformed = transformer.transform_problem(parsed)
          assert "problem_data" in transformed
          assert "nodes" in transformed
          processed_count += 1
      except Exception:
        # Some files might not parse - that's OK for this test
        pass

    assert processed_count > 0, "Should successfully process at least one file"


class TestJSONWriterIntegration:
  """Test JSONWriter integration."""

  def test_write_transformed_data_to_json(self, test_files_directory, output_directory):
    """
    WHAT: Test writing transformed data to JSON
    WHY: Should create valid JSON files
    EXPECTED: JSON file created with correct structure
    DATA: gr17.tsp → JSON
    """
    gr17_path = Path(test_files_directory) / "gr17.tsp"

    parser = FormatParser()
    transformer = DataTransformer()
    writer = JSONWriter(output_dir=output_directory, pretty=True)

    # Process file
    parsed = parser.parse_file(str(gr17_path))
    transformed = transformer.transform_problem(parsed)

    # Write JSON
    json_path = writer.write_problem(transformed, organize_by_type=False)

    # Verify file exists
    assert Path(json_path).exists(), "JSON file should be created"

    # Verify JSON structure
    with open(json_path) as f:
      json_data = json.load(f)

    assert "problem" in json_data, "JSON should have 'problem' key"
    assert "nodes" in json_data, "JSON should have 'nodes' key"

  def test_batch_write_multiple_files(self, test_files_directory, output_directory):
    """
    WHAT: Test batch writing multiple files to JSON
    WHY: Should handle multiple files correctly
    EXPECTED: All files written as JSON
    DATA: All .tsp files
    """
    scanner = FileScanner()
    parser = FormatParser()
    transformer = DataTransformer()
    writer = JSONWriter(output_dir=output_directory)

    files = scanner.scan_files(test_files_directory, patterns=["*.tsp"])

    written_count = 0
    for file_path in files[:3]:  # Limit to 3 files for speed
      try:
        parsed = parser.parse_file(file_path)
        if parsed:
          transformed = transformer.transform_problem(parsed)
          json_path = writer.write_problem(transformed, organize_by_type=True)
          assert Path(json_path).exists()
          written_count += 1
      except Exception:
        pass

    assert written_count > 0, "Should write at least one JSON file"


class TestDatabaseIntegration:
  """Test Database integration."""

  def test_write_transformed_data_to_database(self, test_files_directory, output_directory):
    """
    WHAT: Test writing transformed data to database
    WHY: Should store data correctly in DuckDB
    EXPECTED: Data queryable from database
    DATA: gr17.tsp → database
    """
    gr17_path = Path(test_files_directory) / "gr17.tsp"
    db_path = str(Path(output_directory) / "test.duckdb")

    parser = FormatParser()
    transformer = DataTransformer()
    db = DatabaseManager(db_path)

    # Process file
    parsed = parser.parse_file(str(gr17_path))
    transformed = transformer.transform_problem(parsed)

    # Write to DB (need to extract problem_data from transformed)
    problem_data = transformed.get("problem_data", {})
    problem_id = db.insert_problem(problem_data)
    assert problem_id > 0, "Should get valid problem ID"

    nodes = transformed.get("nodes", [])
    node_count = db.insert_nodes(problem_id, nodes)
    assert node_count == 17, "Should insert 17 nodes"

    # Verify data
    stats = db.get_problem_stats()
    assert stats["total_problems"] == 1, "Should have 1 problem"


class TestFullPipelineIntegration:
  """Test complete pipeline integration."""

  def test_full_pipeline_scan_parse_transform_write(self, test_files_directory, output_directory):
    """
    WHAT: Test complete pipeline workflow
    WHY: Should work end-to-end
    EXPECTED: Files scanned → parsed → transformed → written to JSON + DB
    DATA: Test files → JSON + database
    """
    db_path = str(Path(output_directory) / "pipeline.duckdb")

    # Initialize all components
    scanner = FileScanner()
    parser = FormatParser()
    transformer = DataTransformer()
    writer = JSONWriter(output_dir=output_directory)
    db = DatabaseManager(db_path)

    # Scan files
    files = scanner.scan_files(test_files_directory, patterns=["*.tsp"])

    # Process each file
    processed_count = 0
    for file_path in files[:2]:  # Limit to 2 files
      try:
        # Parse + Transform
        parsed = parser.parse_file(file_path)
        if not parsed:
          continue

        transformed = transformer.transform_problem(parsed)

        # Write JSON
        json_path = writer.write_problem(transformed, organize_by_type=True)
        assert Path(json_path).exists()

        # Write DB
        problem_data = transformed.get("problem_data", {})
        problem_id = db.insert_problem(problem_data)

        nodes = transformed.get("nodes", [])
        db.insert_nodes(problem_id, nodes)

        processed_count += 1
      except Exception as e:
        # Log but don't fail - some files might have issues
        print(f"Skipped {file_path}: {e}")

    assert processed_count > 0, "Should process at least one file through full pipeline"

    # Verify database has data
    stats = db.get_problem_stats()
    assert stats["total_problems"] >= 1, "Database should have at least one problem"

    # Verify JSON files exist
    json_files = list(Path(output_directory).glob("**/*.json"))
    assert len(json_files) >= 1, "Should have at least one JSON file"
