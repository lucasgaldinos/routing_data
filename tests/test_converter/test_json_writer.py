"""
Tests for converter.output.json_writer.JSONWriter - JSON file output.

Tests the actual behavior of JSONWriter for creating JSON files with proper structure.
Based on verified system output.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from converter.core.transformer import DataTransformer
from converter.output.json_writer import JSONWriter
from tsplib_parser.parser import FormatParser


class TestJSONWriterBasic:
  """Test basic JSONWriter functionality."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  @pytest.fixture
  def sample_data(self):
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    return transformer.transform_problem(parsed)

  def test_writer_creates_output_directory(self, tmpdir):
    """
    WHAT: Test that JSONWriter creates output directory
    WHY: Directory should be created automatically if it doesn't exist
    EXPECTED: Directory exists after initialization
    DATA: Temp directory path
    """
    output_dir = Path(tmpdir) / "json_output"
    assert not output_dir.exists(), "Directory shouldn't exist yet"

    writer = JSONWriter(output_dir=str(output_dir))

    assert output_dir.exists(), "Directory should be created"
    assert output_dir.is_dir(), "Should be a directory"

  def test_write_problem_with_type_organization(self, tmpdir, sample_data):
    """
    WHAT: Test writing problem with type-based organization
    WHY: Files should be organized in subdirectories by problem type
    EXPECTED: File created at output_dir/tsp/gr17.json
    DATA: gr17.tsp (TSP type)
    """
    writer = JSONWriter(output_dir=tmpdir, pretty=True)

    path = writer.write_problem(sample_data, organize_by_type=True)

    # Verify path structure
    expected_path = Path(tmpdir) / "tsp" / "gr17.json"
    assert path == str(expected_path), f"Path should be {expected_path}"
    assert expected_path.exists(), "File should exist"

  def test_write_problem_without_type_organization(self, tmpdir, sample_data):
    """
    WHAT: Test writing problem without type organization
    WHY: Files should be created directly in output directory
    EXPECTED: File created at output_dir/gr17.json
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmpdir)

    path = writer.write_problem(sample_data, organize_by_type=False)

    # Verify path structure
    expected_path = Path(tmpdir) / "gr17.json"
    assert path == str(expected_path), f"Path should be {expected_path}"
    assert expected_path.exists(), "File should exist"

  def test_write_problem_creates_type_subdirectory(self, tmpdir, sample_data):
    """
    WHAT: Test that write_problem creates type subdirectory
    WHY: Should create tsp/ directory for TSP problems
    EXPECTED: tsp/ directory exists
    DATA: gr17.tsp (TSP type)
    """
    writer = JSONWriter(output_dir=tmpdir)

    writer.write_problem(sample_data, organize_by_type=True)

    type_dir = Path(tmpdir) / "tsp"
    assert type_dir.exists(), "Type subdirectory should be created"
    assert type_dir.is_dir(), "Should be a directory"


class TestJSONWriterContent:
  """Test JSON file content."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  @pytest.fixture
  def sample_data(self):
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    return transformer.transform_problem(parsed)

  def test_written_json_has_correct_structure(self, tmpdir, sample_data):
    """
    WHAT: Test that written JSON has correct structure
    WHY: JSON should have specific keys: problem, nodes, edges, tours, metadata
    EXPECTED: JSON contains all required keys (NO 'edges' field - Issue #4)
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmpdir)
    path = writer.write_problem(sample_data)

    with open(path) as f:
      json_data = json.load(f)

    required_keys = {"problem", "nodes", "tours", "metadata"}
    assert set(json_data.keys()) == required_keys, f"JSON should have keys: {required_keys}"

  def test_written_json_preserves_problem_data(self, tmpdir, sample_data):
    """
    WHAT: Test that JSON preserves problem data correctly
    WHY: Problem metadata should be intact
    EXPECTED: Problem name, type, dimension match source data
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmpdir)
    path = writer.write_problem(sample_data)

    with open(path) as f:
      json_data = json.load(f)

    assert json_data["problem"]["name"] == "gr17"
    assert json_data["problem"]["type"] == "TSP"
    assert json_data["problem"]["dimension"] == 17

  def test_written_json_preserves_nodes(self, tmpdir, sample_data):
    """
    WHAT: Test that JSON preserves node data
    WHY: Nodes should be written correctly
    EXPECTED: Node count and structure match source
    DATA: gr17.tsp - 17 nodes
    """
    writer = JSONWriter(output_dir=tmpdir)
    path = writer.write_problem(sample_data)

    with open(path) as f:
      json_data = json.load(f)

    assert len(json_data["nodes"]) == 17, "Should have 17 nodes"
    assert json_data["nodes"] == sample_data["nodes"], "Nodes should match source data"

  def test_pretty_printing_enabled(self, tmpdir, sample_data):
    """
    WHAT: Test that pretty printing works
    WHY: Pretty-printed JSON should be human-readable
    EXPECTED: File contains indentation and newlines
    DATA: gr17.tsp with pretty=True
    """
    writer = JSONWriter(output_dir=tmpdir, pretty=True)
    path = writer.write_problem(sample_data)

    with open(path) as f:
      content = f.read()

    # Pretty-printed JSON has indentation
    assert "  " in content, "Should have indentation (2 spaces)"
    assert content.count("\n") > 20, "Should have many newlines for readability"

  def test_pretty_printing_disabled(self, tmpdir, sample_data):
    """
    WHAT: Test that compact JSON works
    WHY: Compact JSON should be smaller
    EXPECTED: File has minimal whitespace
    DATA: gr17.tsp with pretty=False
    """
    writer = JSONWriter(output_dir=tmpdir, pretty=False)
    path = writer.write_problem(sample_data)

    with open(path) as f:
      content = f.read()

    # Compact JSON has minimal newlines
    # Note: Still has some newlines due to JSON structure
    assert content.count("\n") < 10, "Should have few newlines"


class TestJSONWriterBatch:
  """Test batch writing functionality."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  @pytest.fixture
  def batch_data(self):
    """Parse multiple problems for batch testing."""
    parser = FormatParser()
    transformer = DataTransformer()

    files = ["datasets_raw/problems/tsp/gr17.tsp", "datasets_raw/problems/tsp/berlin52.tsp"]

    data_list = []
    for file_path in files:
      parsed = parser.parse_file(file_path)
      transformed = transformer.transform_problem(parsed)
      data_list.append(transformed)

    return data_list

  def test_write_batch_creates_multiple_files(self, tmpdir, batch_data):
    """
    WHAT: Test that write_batch creates multiple JSON files
    WHY: Should write all problems in the list
    EXPECTED: Returns list of paths, all files exist
    DATA: gr17.tsp, berlin52.tsp
    """
    writer = JSONWriter(output_dir=tmpdir)

    paths = writer.write_batch(batch_data, organize_by_type=True)

    assert len(paths) == 2, "Should return 2 paths"

    for path in paths:
      assert Path(path).exists(), f"File should exist: {path}"

  def test_write_batch_organizes_by_type(self, tmpdir, batch_data):
    """
    WHAT: Test that write_batch organizes files by type
    WHY: Both TSP problems should be in tsp/ subdirectory
    EXPECTED: Both files in output_dir/tsp/
    DATA: gr17.tsp, berlin52.tsp (both TSP)
    """
    writer = JSONWriter(output_dir=tmpdir)

    paths = writer.write_batch(batch_data, organize_by_type=True)

    for path in paths:
      assert "/tsp/" in path, f"Path should contain /tsp/: {path}"

  def test_write_batch_returns_correct_filenames(self, tmpdir, batch_data):
    """
    WHAT: Test that write_batch returns correct filenames
    WHY: Filenames should match problem names
    EXPECTED: gr17.json and berlin52.json
    DATA: gr17.tsp, berlin52.tsp
    """
    writer = JSONWriter(output_dir=tmpdir)

    paths = writer.write_batch(batch_data)

    filenames = [Path(p).name for p in paths]
    assert "gr17.json" in filenames, "Should have gr17.json"
    assert "berlin52.json" in filenames, "Should have berlin52.json"


class TestJSONWriterUtility:
  """Test utility methods."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  def test_get_output_path_with_type_organization(self, tmpdir):
    """
    WHAT: Test get_output_path with type organization
    WHY: Should return path with type subdirectory
    EXPECTED: Returns output_dir/tsp/test.json
    DATA: problem_name='test', problem_type='TSP'
    """
    writer = JSONWriter(output_dir=tmpdir)

    path = writer.get_output_path("test", "TSP", organize_by_type=True)

    expected = str(Path(tmpdir) / "tsp" / "test.json")
    assert path == expected, f"Path should be {expected}"

  def test_get_output_path_without_type_organization(self, tmpdir):
    """
    WHAT: Test get_output_path without type organization
    WHY: Should return path directly in output_dir
    EXPECTED: Returns output_dir/test.json
    DATA: problem_name='test'
    """
    writer = JSONWriter(output_dir=tmpdir)

    path = writer.get_output_path("test", "TSP", organize_by_type=False)

    expected = str(Path(tmpdir) / "test.json")
    assert path == expected, f"Path should be {expected}"

  def test_get_output_path_lowercases_type(self, tmpdir):
    """
    WHAT: Test that get_output_path lowercases problem type
    WHY: Directory names should be lowercase
    EXPECTED: 'TSP' becomes 'tsp' in path
    DATA: problem_type='TSP'
    """
    writer = JSONWriter(output_dir=tmpdir)

    path = writer.get_output_path("test", "TSP", organize_by_type=True)

    assert "/tsp/" in path, "Type directory should be lowercase"
    assert "/TSP/" not in path, "Should not have uppercase type"


class TestJSONWriterEdgeCases:
  """Test edge cases and error handling."""

  @pytest.fixture
  def tmpdir(self):
    """Create temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

  def test_write_problem_with_missing_fields(self, tmpdir):
    """
    WHAT: Test writing problem with minimal data
    WHY: Should handle missing optional fields gracefully
    EXPECTED: Writes JSON with available data, uses 'unknown' for missing fields
    DATA: Minimal problem_data without name or type
    """
    writer = JSONWriter(output_dir=tmpdir)

    minimal_data = {
      "problem_data": {},  # Empty problem_data
      "nodes": [],
      "tours": [],
      "metadata": {},
    }

    path = writer.write_problem(minimal_data)

    # Should use 'unknown' for missing fields
    assert Path(path).exists(), "File should still be created"
    assert "unknown" in path.lower(), "Should use 'unknown' for missing name/type"

  def test_write_problem_overwrites_existing_file(self, tmpdir):
    """
    WHAT: Test that write_problem overwrites existing files
    WHY: Should update files on re-write
    EXPECTED: File content changes on second write
    DATA: Same problem written twice with different metadata
    """
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    data1 = transformer.transform_problem(parsed)

    writer = JSONWriter(output_dir=tmpdir)

    # First write
    path1 = writer.write_problem(data1)
    with open(path1) as f:
      content1 = f.read()

    # Modify data
    data2 = data1.copy()
    data2["metadata"]["test_flag"] = "modified"

    # Second write (same path)
    path2 = writer.write_problem(data2)
    with open(path2) as f:
      content2 = f.read()

    assert path1 == path2, "Paths should be the same"
    assert content1 != content2, "Content should be different"
    assert "modified" in content2, "Should contain modified metadata"
