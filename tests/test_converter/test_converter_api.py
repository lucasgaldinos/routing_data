"""
Tests for converter.api.SimpleConverter - High-level API for TSPLIB parsing and conversion.

Tests the actual behavior of SimpleConverter which integrates FormatParser with DataTransformer.
Based on verified system output.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from converter.api import SimpleConverter
from tsplib_parser.exceptions import ParseError


class TestSimpleConverterParsing:
  """Test SimpleConverter.parse_file() method."""

  @pytest.fixture
  def converter(self) -> SimpleConverter:
    """Create SimpleConverter instance for testing."""
    return SimpleConverter()

  def test_parse_file_returns_expected_structure(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test that parse_file returns correct v2 data structure
    WHY: SimpleConverter (schema v2) should return the array-column payload: hub
        + per-type keys (problem_data) with NO v1 ``nodes`` list
    EXPECTED: Returns dict with problem_data/tours/metadata/coords/display_coords/
        demands/depots/edges/fixed_edges keys; gr17.tsp is EXPLICIT so it also
        carries edge_weight_matrix and coords stays None
    DATA: gr17.tsp
    """
    result = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")

    # Verify top-level keys
    assert isinstance(result, dict), "Should return dictionary"
    # Schema-v2 array-column key set (gr17 is EXPLICIT, so edge_weight_matrix
    # is present and coords/display_coords remain None).
    expected_keys: set[str] = {
      "problem_data",
      "tours",
      "metadata",
      "coords",
      "display_coords",
      "demands",
      "depots",
      "edges",
      "fixed_edges",
      "edge_weight_matrix",
    }
    assert set(result.keys()) == expected_keys, f"v1 'nodes' must be gone; keys: {set(result.keys())}"
    # Assert the hub and array columns carry the expected types
    assert isinstance(result["problem_data"], dict)
    assert isinstance(result["tours"], list)
    assert isinstance(result["metadata"], dict)
    assert result["coords"] is None, "EXPLICIT problem has no coords array column"
    assert result["display_coords"] is None
    assert result["demands"] == []
    assert result["depots"] == []

  def test_parse_file_problem_data_structure(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test problem_data structure from parse_file
    WHY: Problem data should contain all metadata fields plus file info
    EXPECTED: Contains name, type, dimension, edge_weight_type, file_path, file_size, etc.
    DATA: gr17.tsp - EXPLICIT, 17 nodes
    """
    result = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    problem_data = result["problem_data"]

    # Verify essential fields
    assert problem_data["name"] == "gr17"
    assert problem_data["type"] == "TSP"
    assert problem_data["dimension"] == 17
    assert problem_data["edge_weight_type"] == "EXPLICIT"

    # Verify file metadata added by transformer
    assert "file_path" in problem_data
    assert "file_size" in problem_data
    assert isinstance(problem_data["file_size"], int)

  def test_parse_file_array_columns_structure(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test the v2 node-data representation from parse_file (gr17, EXPLICIT)
    WHY: Schema v2 carries node data as array columns, not a ``nodes`` row-list
    EXPECTED: gr17.tsp (EXPLICIT, 17x17 matrix) has coords=None (distance data
        lives in edge_weight_matrix), demands/depots empty, and a 17x17 matrix
    DATA: gr17.tsp - EXPLICIT, dimension 17
    """
    result = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")

    assert "nodes" not in result, "v1 'nodes' top-level key must be gone"

    # EXPLICIT problem: coords / display_coords are not present for gr17,
    # the full distance data is the 17x17 edge_weight_matrix.
    assert result["coords"] is None
    assert result["display_coords"] is None
    assert result["demands"] == []
    assert result["depots"] == []

    matrix = result["edge_weight_matrix"]
    assert isinstance(matrix, list), "edge_weight_matrix should be a 2D list"
    assert len(matrix) == 17, "gr17 matrix is 17x17"
    assert all(len(row) == 17 for row in matrix)
    # Diagonal is zero for a valid distance matrix
    assert matrix[0][0] == 0

  def test_parse_file_metadata_structure(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test metadata structure from parse_file
    WHY: Metadata should contain file info and problem characteristics
    EXPECTED: Contains file_path, file_name, has_coordinates, is_symmetric, weight_source, etc.
    DATA: gr17.tsp
    """
    result = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    metadata = result["metadata"]
    # Verify metadata fields
    assert "file_path" in metadata
    assert "file_name" in metadata
    assert "file_size" in metadata
    assert "has_coordinates" in metadata
    assert "has_demands" in metadata
    assert "has_depots" in metadata
    assert "is_symmetric" in metadata
    assert "weight_source" in metadata

    # Verify values for gr17.tsp
    assert metadata["file_name"] == "gr17.tsp"
    assert metadata["has_coordinates"] is False  # EXPLICIT matrix
    assert metadata["has_demands"] is False  # TSP has no demands
    assert metadata["has_depots"] is False  # TSP has no depots

  def test_parse_file_with_coordinate_problem(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test parsing coordinate-based problem
    WHY: Verify SimpleConverter handles EUC_2D problems correctly under v2
    EXPECTED: Returns coords array column (52 rows), edge_weight_type='EUC_2D',
        and no edge_weight_matrix (distances computed on demand)
    DATA: berlin52.tsp - EUC_2D, 52 nodes
    """
    result = converter.parse_file("datasets_raw/problems/tsp/berlin52.tsp")

    assert result["problem_data"]["name"] == "berlin52"
    assert result["problem_data"]["type"] == "TSP"
    assert result["problem_data"]["dimension"] == 52
    assert result["problem_data"]["edge_weight_type"] == "EUC_2D"
    assert "nodes" not in result, "v1 'nodes' top-level key must be gone"
    # EUC_2D problem: coords array column holds the 52 node coordinates
    coords = result["coords"]
    assert coords is not None
    assert len(coords) == 52, "Should have 52 coordinate rows"
    assert all(len(row) == 2 for row in coords)
    # Coordinate problems compute distances on demand; no matrix row stored
    assert "edge_weight_matrix" not in result


class TestSimpleConverterErrorHandling:
  """Test SimpleConverter error handling."""

  @pytest.fixture
  def converter(self) -> SimpleConverter:
    """Create SimpleConverter instance for testing."""
    return SimpleConverter()

  def test_parse_nonexistent_file_raises_error(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test that parsing nonexistent file raises ParseError
    WHY: Should handle file not found gracefully
    EXPECTED: Raises ParseError with descriptive message
    DATA: nonexistent.tsp (file does not exist)
    """
    with pytest.raises(ParseError) as exc_info:
      converter.parse_file("nonexistent.tsp")

    assert "nonexistent.tsp" in str(exc_info.value)
    assert "No such file or directory" in str(exc_info.value)

  def test_parse_invalid_path_raises_error(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test that parsing with invalid path raises ParseError
    WHY: Should validate file path
    EXPECTED: Raises ParseError for invalid paths
    DATA: /invalid/path/file.tsp
    """
    with pytest.raises(ParseError):
      converter.parse_file("/invalid/path/file.tsp")


class TestSimpleConverterJSONConversion:
  """Test SimpleConverter.to_json() and to_json_format() methods."""

  @pytest.fixture
  def converter(self) -> SimpleConverter:
    """Create SimpleConverter instance for testing."""
    return SimpleConverter()

  @pytest.fixture
  def sample_data(self, converter: SimpleConverter) -> dict[str, Any]:
    """Parse sample data for JSON conversion tests."""
    return converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")

  def test_to_json_format_structure(self, converter: SimpleConverter, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test to_json_format() transformation (schema v2)
    WHY: Should convert to JSON-friendly format with the v2 key set
    EXPECTED: Returns dict with 'problem', 'tours', 'metadata' plus the forwarded
        array-column keys (coords/display_coords/demands/depots/edges/
        fixed_edges); no v1 'nodes' key
    DATA: gr17.tsp parsed data
    """
    json_format = converter.transformer.to_json_format(sample_data)

    # Verify structure
    assert isinstance(json_format, dict)
    required_keys = {
      "problem",
      "tours",
      "metadata",
      "coords",
      "display_coords",
      "demands",
      "depots",
      "edges",
      "fixed_edges",
    }
    assert set(json_format.keys()) == required_keys
    assert "nodes" not in json_format, "no v1 'nodes' list in v2 json output"

    # Verify types
    assert isinstance(json_format["problem"], dict)
    assert isinstance(json_format["tours"], list)
    assert isinstance(json_format["metadata"], dict)

  def test_to_json_format_preserves_data(self, converter: SimpleConverter, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that to_json_format preserves essential data
    WHY: Transformation should not lose information
    EXPECTED: Problem name, dimension, and the explicit matrix survive (gr17)
    DATA: gr17.tsp
    """
    json_format = converter.transformer.to_json_format(sample_data)

    assert json_format["problem"]["name"] == "gr17"
    assert json_format["problem"]["dimension"] == 17
    # gr17 is EXPLICIT: coords stays None in the JSON output
    assert json_format["coords"] is None
    assert json_format["demands"] == []
    assert json_format["depots"] == []

  def test_to_json_writes_valid_file(self, converter: SimpleConverter, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test to_json() writes valid JSON file
    WHY: Should create readable JSON file
    EXPECTED: Creates JSON file that can be parsed back (v2 key set)
    DATA: gr17.tsp -> temp JSON file
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      output_path = Path(tmpdir) / "test_output.json"

      # Write JSON
      converter.to_json(sample_data, str(output_path))

      # Verify file exists
      assert output_path.exists(), "JSON file should be created"

      # Verify valid JSON
      with open(output_path) as f:
        loaded_data = json.load(f)

      assert loaded_data["problem"]["name"] == "gr17"
      assert loaded_data["problem"]["dimension"] == 17
      assert "nodes" not in loaded_data, "no v1 'nodes' key in written json"
      assert loaded_data["coords"] is None
      assert loaded_data["demands"] == []
      assert loaded_data["depots"] == []

  def test_to_json_creates_output_directory(self, converter: SimpleConverter, sample_data: dict[str, Any]) -> None:
    """
    WHAT: Test that to_json() creates output directory if needed
    WHY: Should handle missing directories automatically
    EXPECTED: Creates nested directories and writes file
    DATA: gr17.tsp -> nested/path/output.json
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      output_path = Path(tmpdir) / "nested" / "path" / "output.json"

      # Write JSON (directory doesn't exist yet)
      converter.to_json(sample_data, str(output_path))

      # Verify directory and file created
      assert output_path.parent.exists(), "Parent directory should be created"
      assert output_path.exists(), "JSON file should be created"


class TestSimpleConverterIntegration:
  """Test SimpleConverter end-to-end integration."""

  @pytest.fixture
  def converter(self) -> SimpleConverter:
    """Create SimpleConverter instance for testing."""
    return SimpleConverter()

  def test_parse_transform_json_pipeline(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test complete parse → transform → JSON pipeline
    WHY: Verify SimpleConverter integrates all components correctly
    EXPECTED: Parse file, transform data, write JSON successfully
    DATA: gr17.tsp → parse → transform → JSON
    """
    # Parse
    data = converter.parse_file("datasets_raw/problems/tsp/gr17.tsp")

    # Write to temporary file (to_json internally re-applies to_json_format)
    with tempfile.TemporaryDirectory() as tmpdir:
      output_path = Path(tmpdir) / "output.json"
      converter.to_json(data, str(output_path))

      # Verify
      assert output_path.exists()
      with open(output_path) as f:
        loaded = json.load(f)

      assert loaded["problem"]["name"] == "gr17"
      assert loaded["problem"]["type"] == "TSP"
      assert "nodes" not in loaded, "no v1 'nodes' key in pipeline output"
      assert loaded["coords"] is None, "gr17 is EXPLICIT: coords stays None"
      assert loaded["demands"] == []
      assert loaded["depots"] == []

  def test_consistency_across_multiple_files(self, converter: SimpleConverter) -> None:
    """
    WHAT: Test that SimpleConverter handles multiple files consistently
    WHY: Should produce consistent v2 output structure for different problems
    EXPECTED: All files return the same hub/type-table/array-column keys (only
        the EXPLICIT-vs-coordinate satellite differs)
    DATA: gr17.tsp (EXPLICIT), berlin52.tsp (EUC_2D)
    """
    files = ["datasets_raw/problems/tsp/gr17.tsp", "datasets_raw/problems/tsp/berlin52.tsp"]

    results = [converter.parse_file(f) for f in files]

    # Shared v2 key set across both problems (no v1 ``nodes``).
    shared_keys = {
      "problem_data",
      "tours",
      "metadata",
      "coords",
      "display_coords",
      "demands",
      "depots",
      "edges",
      "fixed_edges",
    }
    for result in results:
      assert "nodes" not in result
      assert shared_keys <= set(result.keys())
      assert isinstance(result["problem_data"], dict)
      assert isinstance(result["tours"], list)
      assert isinstance(result["metadata"], dict)

    # gr17 (EXPLICIT) carries a matrix row; berlin52 (coordinate) carries coords.
    gr17, berlin52 = results
    assert "edge_weight_matrix" in gr17 and gr17["edge_weight_matrix"] is not None
    assert "edge_weight_matrix" not in berlin52
    assert gr17["coords"] is None
    assert berlin52["coords"] is not None and len(berlin52["coords"]) == 52

    # Hub dimension is consistent regardless of the array-column carrier
    assert gr17["problem_data"]["dimension"] == 17
    assert berlin52["problem_data"]["dimension"] == 52
