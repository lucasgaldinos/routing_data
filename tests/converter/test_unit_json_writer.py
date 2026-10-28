"""
Tests for converter.output.json_writer.JSONWriter - JSON file output.

Tests the actual behavior of JSONWriter for creating JSON files with proper structure.
Based on verified system output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from converter.api import SimpleConverter
from converter.core.transformer import DataTransformer
from converter.output.json_writer import JSONWriter
from converter.utils.logging import setup_logging
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from collections.abc import Callable
  from logging import Logger

  from tsplib_parser.types import ParseResult


class TestJSONWriterBasic:
  """Test basic JSONWriter functionality."""

  @pytest.fixture
  def sample_data(self, dataset_path: Callable[..., str]) -> dict[str, Any]:
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    return transformer.transform_problem(parsed)

  def test_writer_creates_output_directory(self, tmp_path: Path) -> None:
    """
    WHAT: Test that JSONWriter creates output directory
    WHY: Directory should be created automatically if it doesn't exist
    EXPECTED: Directory exists after initialization
    DATA: Temp directory path
    """
    output_dir: Path = Path(tmp_path) / "json_output"
    assert not output_dir.exists(), "Directory shouldn't exist yet"

    JSONWriter(output_dir=str(output_dir))

    assert output_dir.exists(), "Directory should be created"
    assert output_dir.is_dir(), "Should be a directory"

  @pytest.mark.requires_dataset
  def test_write_problem_with_type_organization(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test writing problem with type-based organization
    WHY: Files should be organized in subdirectories by problem type
    EXPECTED: File created at output_dir/tsp/gr17.json
    DATA: gr17.tsp (TSP type)
    """
    writer = JSONWriter(output_dir=tmp_path, pretty=True)

    path = writer.write_problem(sample_data, organize_by_type=True)

    # Verify path structure
    expected_path: Path = Path(tmp_path) / "tsp" / "gr17.json"
    assert path == str(expected_path), f"Path should be {expected_path}"
    assert expected_path.exists(), "File should exist"

  @pytest.mark.requires_dataset
  def test_write_problem_without_type_organization(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test writing problem without type organization
    WHY: Files should be created directly in output directory
    EXPECTED: File created at output_dir/gr17.json
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmp_path)

    path: str = writer.write_problem(sample_data, organize_by_type=False)

    # Verify path structure
    expected_path: Path = Path(tmp_path) / "gr17.json"
    assert path == str(expected_path), f"Path should be {expected_path}"
    assert expected_path.exists(), "File should exist"

  @pytest.mark.requires_dataset
  def test_write_problem_prevents_path_traversal(self, tmp_path: Path, sample_data: dict[str, Any]) -> None:
    """WHAT: Test that write_problem prevents path traversal via problem name (regression for M2).

    WHY: Unsanitized names like '../../escaped' could escape output_dir.
    EXPECTED: File remains safely contained within output directory.
    """
    writer = JSONWriter(output_dir=str(tmp_path))
    malicious_data = dict(sample_data)
    malicious_data["problem_data"] = dict(sample_data["problem_data"])
    malicious_data["problem_data"]["name"] = "../../traversal_attack"

    written_path = Path(writer.write_problem(malicious_data, organize_by_type=True))
    assert written_path.resolve().is_relative_to(tmp_path.resolve())
    assert written_path.name == "traversal_attack.json"

  @pytest.mark.requires_dataset
  def test_write_problem_creates_type_subdirectory(self, tmp_path: Path, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that write_problem creates type subdirectory
    WHY: Should create tsp/ directory for TSP problems
    EXPECTED: tsp/ directory exists
    DATA: gr17.tsp (TSP type)
    """
    writer = JSONWriter(output_dir=tmp_path)

    writer.write_problem(sample_data, organize_by_type=True)

    type_dir: Path = Path(tmp_path) / "tsp"
    assert type_dir.exists(), "Type subdirectory should be created"
    assert type_dir.is_dir(), "Should be a directory"


class TestJSONWriterContent:
  """Test JSON file content."""

  @pytest.fixture
  def sample_data(self, dataset_path: Callable[..., str]) -> dict[str, Any]:
    """Parse and transform sample data."""
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    return transformer.transform_problem(parsed)

  @pytest.mark.requires_dataset
  def test_written_json_has_correct_structure(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that written JSON has the v2 top-level shape.
    WHY: The writer emits one key per array column plus problem, tours and metadata.
    EXPECTED: Exact v2 key set, with values carried from the transformed payload.
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmp_path)
    path: str = writer.write_problem(sample_data)

    with open(path) as f:
      json_data: dict[str, Any] = json.load(f)

    expected_keys: set[str] = {
      "problem",
      "coords",
      "demands",
      "depots",
      "display_coords",
      "edges",
      "fixed_edges",
      "metadata",
      "tours",
      "edge_weight_matrix",
    }
    assert set(json_data) == expected_keys
    assert json_data["problem"]["name"] == "gr17"
    assert json_data["problem"]["type"] == "TSP"
    assert json_data["problem"]["dimension"] == 17
    assert json_data["coords"] is None, "gr17 is EXPLICIT and has no coordinates"
    assert json_data["tours"] == sample_data["tours"] == []

  @pytest.mark.requires_dataset
  def test_written_json_preserves_problem_data(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that JSON preserves problem data correctly
    WHY: Problem metadata should be intact
    EXPECTED: Problem name, type, dimension match source data
    DATA: gr17.tsp
    """
    writer = JSONWriter(output_dir=tmp_path)
    path: str = writer.write_problem(sample_data)

    with open(path) as f:
      json_data = json.load(f)

    assert json_data["problem"]["name"] == "gr17"
    assert json_data["problem"]["type"] == "TSP"
    assert json_data["problem"]["dimension"] == 17

  @pytest.mark.requires_dataset
  def test_written_json_preserves_coords(self, tmp_path: Path, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Test that JSON preserves coordinate data
    WHY: Coordinates should be written correctly in Schema v2 format
    EXPECTED: Coordinate count and structure match source
    DATA: berlin52.tsp - 52 nodes
    """
    parser = FormatParser()
    transformer = DataTransformer()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "berlin52.tsp"))
    coord_data: dict[str, Any] = transformer.transform_problem(parsed)

    writer = JSONWriter(output_dir=tmp_path)
    path: str = writer.write_problem(coord_data)

    with open(path) as f:
      json_data = json.load(f)

    assert len(json_data["coords"]) == 52, "Should have 52 coordinates"
    assert json_data["coords"] == coord_data["coords"], "Coords should match source data"

  @pytest.mark.requires_dataset
  def test_pretty_printing_enabled(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that pretty printing works
    WHY: Pretty-printed JSON should be human-readable
    EXPECTED: File contains indentation and newlines
    DATA: gr17.tsp with pretty=True
    """
    writer = JSONWriter(output_dir=tmp_path, pretty=True)
    path: str = writer.write_problem(sample_data)

    with open(path) as f:
      content: str = f.read()

    # Pretty-printed JSON has indentation
    assert "  " in content, "Should have indentation (2 spaces)"
    assert content.count("\n") > 20, "Should have many newlines for readability"

  @pytest.mark.requires_dataset
  def test_pretty_printing_disabled(self, tmp_path: str, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that compact JSON works
    WHY: Compact JSON should be smaller
    EXPECTED: File has minimal whitespace
    DATA: gr17.tsp with pretty=False
    """
    writer = JSONWriter(output_dir=tmp_path, pretty=False)
    path: str = writer.write_problem(sample_data)

    with open(path) as f:
      content: str = f.read()

    # Compact JSON has minimal newlines
    # Note: Still has some newlines due to JSON structure
    assert content.count("\n") < 10, "Should have few newlines"


class TestJSONWriterBatch:
  """Test batch writing functionality."""

  @pytest.fixture
  def batch_data(self, dataset_path: Callable[..., str]) -> list[dict[str, Any]]:
    """Parse multiple problems for batch testing."""
    parser = FormatParser()
    transformer = DataTransformer()

    files: list[str] = [dataset_path("tsp", "gr17.tsp"), dataset_path("tsp", "berlin52.tsp")]

    data_list = []
    for file_path in files:
      parsed: ParseResult = parser.parse_file(file_path)
      transformed: dict[str, Any] = transformer.transform_problem(parsed)
      data_list.append(transformed)

    return data_list

  @pytest.mark.requires_dataset
  def test_write_batch_creates_multiple_files(self, tmp_path: str, batch_data: list[dict[str, Any]]) -> None:
    """
    WHAT: Test that write_batch creates multiple JSON files
    WHY: Should write all problems in the list
    EXPECTED: Returns list of paths, all files exist
    DATA: gr17.tsp, berlin52.tsp
    """
    writer = JSONWriter(output_dir=tmp_path)

    paths: list[str] = writer.write_batch(batch_data, organize_by_type=True)

    assert len(paths) == 2, "Should return 2 paths"

    for path in paths:
      assert Path(path).exists(), f"File should exist: {path}"

  @pytest.mark.requires_dataset
  def test_write_batch_organizes_by_type(self, tmp_path: str, batch_data: list[dict[str, Any]]) -> None:
    """
    WHAT: Test that write_batch organizes files by type
    WHY: Both TSP problems should be in tsp/ subdirectory
    EXPECTED: Both files in output_dir/tsp/
    DATA: gr17.tsp, berlin52.tsp (both TSP)
    """
    writer = JSONWriter(output_dir=tmp_path)

    paths: list[str] = writer.write_batch(batch_data, organize_by_type=True)

    for path in paths:
      assert "/tsp/" in path, f"Path should contain /tsp/: {path}"

  @pytest.mark.requires_dataset
  def test_write_batch_returns_correct_filenames(self, tmp_path: str, batch_data: list[dict[str, Any]]) -> None:
    """
    WHAT: Test that write_batch returns correct filenames
    WHY: Filenames should match problem names
    EXPECTED: gr17.json and berlin52.json
    DATA: gr17.tsp, berlin52.tsp
    """
    writer = JSONWriter(output_dir=tmp_path)

    paths: list[str] = writer.write_batch(batch_data)

    filenames: list[str] = [Path(p).name for p in paths]
    assert "gr17.json" in filenames, "Should have gr17.json"
    assert "berlin52.json" in filenames, "Should have berlin52.json"


class TestJSONWriterUtility:
  """Test utility methods."""

  def test_get_output_path_with_type_organization(self, tmp_path: Path) -> None:
    """
    WHAT: Test get_output_path with type organization
    WHY: Should return path with type subdirectory
    EXPECTED: Returns output_dir/tsp/test.json
    DATA: problem_name='test', problem_type='TSP'
    """
    writer = JSONWriter(output_dir=tmp_path)

    path: str = writer.get_output_path("test", "TSP", organize_by_type=True)

    expected = str(Path(tmp_path) / "tsp" / "test.json")
    assert path == expected, f"Path should be {expected}"

  def test_get_output_path_without_type_organization(self, tmp_path: Path) -> None:
    """
    WHAT: Test get_output_path without type organization
    WHY: Should return path directly in output_dir
    EXPECTED: Returns output_dir/test.json
    DATA: problem_name='test'
    """
    writer = JSONWriter(output_dir=tmp_path)

    path: str = writer.get_output_path("test", "TSP", organize_by_type=False)

    expected = str(Path(tmp_path) / "test.json")
    assert path == expected, f"Path should be {expected}"

  def test_get_output_path_lowercases_type(self, tmp_path: Path) -> None:
    """
    WHAT: Test that get_output_path lowercases problem type
    WHY: Directory names should be lowercase
    EXPECTED: 'TSP' becomes 'tsp' in path
    DATA: problem_type='TSP'
    """
    writer = JSONWriter(output_dir=tmp_path)

    path = writer.get_output_path("test", "TSP", organize_by_type=True)

    assert "/tsp/" in path, "Type directory should be lowercase"
    assert "/TSP/" not in path, "Should not have uppercase type"


class TestJSONWriterEdgeCases:
  """Test edge cases and error handling."""

  def test_write_problem_with_missing_fields(self, tmp_path: Path) -> None:
    """
    WHAT: Test writing problem with minimal data
    WHY: Should handle missing optional fields gracefully
    EXPECTED: Writes JSON with available data, uses 'unknown' for missing fields
    DATA: Minimal problem_data without name or type
    """
    writer = JSONWriter(output_dir=tmp_path)

    minimal_data: dict[str, Any] = {
      "problem_data": {},  # Empty problem_data
      "coords": [],
      "tours": [],
      "metadata": {},
    }

    path = writer.write_problem(minimal_data)

    # Should use 'unknown' for missing fields
    assert Path(path).exists(), "File should still be created"
    assert "unknown" in path.lower(), "Should use 'unknown' for missing name/type"

  @pytest.mark.requires_dataset
  def test_write_problem_overwrites_existing_file(self, tmp_path: Path, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Test that write_problem overwrites existing files
    WHY: Should update files on re-write
    EXPECTED: File content changes on second write
    DATA: Same problem written twice with different metadata
    """
    parser = FormatParser()
    transformer = DataTransformer()
    parsed = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    data1 = transformer.transform_problem(parsed)

    writer = JSONWriter(output_dir=tmp_path)

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


# ---------------------------------------------------------------------------
# Merged from test_converter/test_json_writing_fixes.py on 2026-10-20; bodies unchanged.
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data() -> dict[str, Any]:
  """Sample transformed problem data."""
  return {
    "problem_data": {"name": "test_problem", "type": "TSP", "dimension": 3, "edge_weight_type": "EUC_2D"},
    "coords": [
      [0.0, 0.0],
      [1.0, 1.0],
      [2.0, 2.0],
    ],
    "tours": [],
    "metadata": {"file_path": "test.tsp", "file_size": 100},
  }


class TestRemoveDeadEdgesField:
  """Test Issue #4: Remove 'edges' field from JSONWriter output."""

  @pytest.mark.requires_dataset
  @pytest.mark.regression
  def test_json_writer_no_edges_field(self, sample_data: dict[str, Any], tmp_path: Path) -> None:
    """
    WHAT: Verify JSONWriter does NOT include 'edges' field
    WHY: Issue #4 - 'edges' field is always empty, database has no edges table
    EXPECTED: JSON output should NOT contain 'edges' key
    """
    logger: Logger = setup_logging()
    json_writer = JSONWriter(str(tmp_path), logger=logger)

    # Write problem
    output_path = json_writer.write_problem(sample_data, organize_by_type=False)

    # Read back and verify
    with open(output_path) as f:
      json_data = json.load(f)

    # Should NOT have edges field
    assert "edges" not in json_data, "JSONWriter should not include 'edges' field"

    # Should have other expected fields
    assert "problem" in json_data
    assert "coords" in json_data
    assert "tours" in json_data
    assert "metadata" in json_data


class TestJSONWritingDeduplication:
  """Test Issue #3: Remove duplication between api.py and JSONWriter."""

  @pytest.mark.requires_dataset
  @pytest.mark.regression
  def test_api_to_json_no_edges(self, sample_data: dict[str, Any], tmp_path: Path) -> None:
    """
    WHAT: Verify api.to_json() does NOT include 'edges' field
    WHY: Issue #3 - api.py should use same structure as JSONWriter
    EXPECTED: JSON output should NOT contain 'edges' key
    """
    logger = setup_logging()
    converter = SimpleConverter(logger=logger)

    output_file = tmp_path / "test_output.json"
    converter.to_json(sample_data, str(output_file))

    # Read back and verify
    with open(output_file) as f:
      json_data = json.load(f)

    # Should NOT have edges field
    assert "edges" not in json_data, "api.to_json() should not include 'edges' field"

  @pytest.mark.requires_dataset
  @pytest.mark.regression
  def test_api_and_writer_produce_identical_output(self, sample_data: dict[str, Any], tmp_path: Path) -> None:
    """
    WHAT: Verify api.to_json() and JSONWriter produce identical output
    WHY: Issue #3 - eliminate duplication by using same code path
    EXPECTED: Identical JSON structure and content
    """
    logger: Logger = setup_logging()
    converter = SimpleConverter(logger=logger)
    json_writer = JSONWriter(str(tmp_path / "writer"), logger=logger)

    # Generate output from api.to_json()
    api_output_file = tmp_path / "api" / "test_problem.json"
    api_output_file.parent.mkdir(parents=True, exist_ok=True)
    converter.to_json(sample_data, str(api_output_file))

    # Generate output from JSONWriter
    writer_output = json_writer.write_problem(sample_data, organize_by_type=False)

    # Read both
    with open(api_output_file) as f:
      api_data = json.load(f)

    with open(writer_output) as f:
      writer_data = json.load(f)

    # Should be identical
    assert api_data == writer_data, "api.to_json() and JSONWriter should produce identical output"

  @pytest.mark.regression
  def test_both_methods_handle_empty_lists(self, tmp_path: Path) -> None:
    """
    WHAT: Verify both methods handle empty coords/tours correctly
    WHY: Edge case testing for consistency
    EXPECTED: Empty lists, not null values
    """
    logger = setup_logging()
    converter = SimpleConverter(logger=logger)
    json_writer = JSONWriter(str(tmp_path / "writer"), logger=logger)

    minimal_data = {
      "problem_data": {"name": "minimal", "type": "TSP", "dimension": 0},
      "coords": [],
      "tours": [],
      "metadata": {},
    }

    # Test api.to_json()
    api_file = tmp_path / "api_minimal.json"
    converter.to_json(minimal_data, str(api_file))

    with open(api_file) as f:
      api_data = json.load(f)

    assert api_data["coords"] == []
    assert api_data["tours"] == []

    # Test JSONWriter
    writer_file = json_writer.write_problem(minimal_data, organize_by_type=False)

    with open(writer_file) as f:
      writer_data = json.load(f)

    assert writer_data["coords"] == []
    assert writer_data["tours"] == []

    # Should match
    assert api_data == writer_data
