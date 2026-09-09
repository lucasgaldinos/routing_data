"""
Tests for converter.core.transformer.DataTransformer - Data transformation logic.

Tests the actual behavior of DataTransformer which normalizes and enriches parsed data.
Based on verified system output.
"""

from typing import Any

import pytest

from converter.core.transformer import DataTransformer
from tsplib_parser.parser import FormatParser


class TestDataTransformerBasic:
  """Test basic DataTransformer functionality."""

  @pytest.fixture
  def transformer(self) -> DataTransformer:
    """Create DataTransformer instance."""
    return DataTransformer()

  @pytest.fixture
  def parsed_data(self) -> dict[str, Any]:
    """Parse sample data for transformation tests."""
    parser = FormatParser()
    return parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")

  def test_transform_problem_returns_expected_keys(
    self, transformer: DataTransformer, parsed_data: dict[str, Any]
  ) -> None:
    """
    WHAT: Test that transform_problem returns the schema-v2 payload keys
    WHY: Schema v2 (Decision 3) drops the v1 ``nodes`` row-list; node data is
        carried as array columns. gr17.tsp is EXPLICIT so it also carries the
        edge_weight_matrix (and coords/display_coords stay None).
    EXPECTED: Returns dict with the exact v2 key set, no ``nodes`` key
    DATA: gr17.tsp parsed data
    """
    result = transformer.transform_problem(parsed_data)

    # gr17 (EXPLICIT TSP) → edge_weight_matrix present, no ``nodes`` key.
    expected_keys = {
      "problem_data",
      "tours",
      "metadata",
      "edges",
      "fixed_edges",
      "coords",
      "display_coords",
      "demands",
      "depots",
      "edge_weight_matrix",
    }
    assert set(result.keys()) == expected_keys
    assert "nodes" not in result, "v1 'nodes' key must be gone"

  def test_transform_problem_enriches_problem_data(self, transformer, parsed_data):
    """
    WHAT: Test that transform_problem enriches problem_data with file info
    WHY: Should add file_path and file_size from metadata to problem_data
    EXPECTED: problem_data contains file_path and file_size
    DATA: gr17.tsp
    """
    result = transformer.transform_problem(parsed_data)
    problem_data = result["problem_data"]

    assert "file_path" in problem_data, "Should add file_path to problem_data"
    assert "file_size" in problem_data, "Should add file_size to problem_data"
    assert isinstance(problem_data["file_size"], int)

  def test_transform_problem_emits_array_columns_not_nodes(self, transformer):
    """
    WHAT: Test that transform_problem surfaces normalized node data as array columns
    WHY: Schema v2 (Decision 3) drops the v1 ``nodes`` row-list; per-node data is
        carried as coords / display_coords / demands / depots. Per-node field
        normalization itself is covered by TestDataTransformerNodeNormalization.
    EXPECTED: A coordinate problem yields coords/display_coords of length == dimension;
        the ``nodes`` top-level key is absent
    DATA: berlin52.tsp (EUC_2D, 52 nodes)
    """
    parser = FormatParser()
    parsed = parser.parse_file("datasets_raw/problems/tsp/berlin52.tsp")
    result = transformer.transform_problem(parsed)

    assert "nodes" not in result, "v1 'nodes' key must be gone"
    dimension = result["problem_data"]["dimension"]
    assert dimension == 52
    # coords is the observable per-node surface for a coordinate problem;
    # display_coords stays None unless the format needs display normalization.
    assert result["coords"] is not None
    assert len(result["coords"]) == dimension
    if result["display_coords"] is not None:
      assert len(result["display_coords"]) == dimension

  def test_transform_problem_preserves_node_count(self, transformer):
    """
    WHAT: Test that transformation preserves node count
    WHY: Normalization should not add or remove nodes; the count now surfaces as
        the length of the coords / display_coords array columns (v2)
    EXPECTED: coords/display_coords length equals both the parsed node count and dimension
    DATA: berlin52.tsp - 52 nodes
    """
    parser = FormatParser()
    parsed = parser.parse_file("datasets_raw/problems/tsp/berlin52.tsp")
    input_count = len(parsed["nodes"])
    assert input_count == 52

    result = transformer.transform_problem(parsed)
    output_count = len(result["coords"]) if result["coords"] is not None else 0

    assert output_count == input_count, "Node count should be preserved"
    assert output_count == result["problem_data"]["dimension"]

  def test_transform_problem_with_file_info(self, transformer, parsed_data):
    """
    WHAT: Test transform_problem with additional file_info parameter
    WHY: Should merge file_info into metadata
    EXPECTED: Metadata contains scanned_file_path, scanned_file_size, detected_type
    DATA: gr17.tsp with custom file_info
    """
    file_info = {"file_path": "/custom/path/problem.tsp", "file_size": 12345, "problem_type": "TSP"}

    result = transformer.transform_problem(parsed_data, file_info=file_info)
    metadata = result["metadata"]

    assert metadata["scanned_file_path"] == "/custom/path/problem.tsp"
    assert metadata["scanned_file_size"] == 12345
    assert metadata["detected_type"] == "TSP"


class TestDataTransformerJSONFormat:
  """Test DataTransformer.to_json_format() method."""

  @pytest.fixture
  def transformer(self):
    """Create DataTransformer instance."""
    return DataTransformer()

  @pytest.fixture
  def transformed_data(self, transformer):
    """Get transformed data for JSON format tests."""
    parser = FormatParser()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")
    return transformer.transform_problem(parsed)

  def test_to_json_format_renames_problem_data(self, transformer, transformed_data):
    """
    WHAT: Test that to_json_format renames 'problem_data' to 'problem'
    WHY: JSON format uses shorter key name
    EXPECTED: Returns dict with 'problem' key instead of 'problem_data'
    DATA: gr17.tsp transformed data
    """
    json_format = transformer.to_json_format(transformed_data)

    assert "problem" in json_format, "Should have 'problem' key"
    assert "problem_data" not in json_format, "Should not have 'problem_data' key"
    assert json_format["problem"] == transformed_data["problem_data"]

  def test_to_json_format_preserves_data_tours_metadata(self, transformer, transformed_data):
    """
    WHAT: Test that to_json_format preserves the v2 payload
    WHY: Schema v2 has no ``nodes`` list; JSON must forward problem, the array
        columns, tours and metadata unchanged
    EXPECTED: problem == problem_data; tours/metadata identical; array-column keys
        (coords/display_coords/demands/depots/edges/fixed_edges) forwarded; no ``nodes``
    DATA: gr17.tsp
    """
    json_format = transformer.to_json_format(transformed_data)

    assert "nodes" not in json_format, "no v1 'nodes' key in v2 JSON output"
    assert json_format["problem"] == transformed_data["problem_data"]
    assert json_format["tours"] == transformed_data["tours"]
    assert json_format["metadata"] == transformed_data["metadata"]
    # Array-column payload is forwarded unchanged when present
    for key in ("coords", "display_coords", "demands", "depots", "edges", "fixed_edges"):
      assert json_format[key] == transformed_data[key]

  def test_to_json_format_returns_expected_keys(self, transformer, transformed_data):
    """
    WHAT: Test that to_json_format returns the v2 key set
    WHY: JSON format has a specific v2 key structure: problem (renamed from
        problem_data), tours, metadata plus the forwarded array-column keys.
        gr17 is EXPLICIT so it carries all array-column keys, but NOT the
        edge_weight_matrix (that matrix is not forwarded to JSON output).
    EXPECTED: Returns dict with the exact v2 key set, no ``nodes`` key
    DATA: gr17.tsp
    """
    json_format = transformer.to_json_format(transformed_data)

    expected_keys = {
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
    assert set(json_format.keys()) == expected_keys
    assert "nodes" not in json_format


class TestDataTransformerNodeNormalization:
  """Test node normalization logic."""

  @pytest.fixture
  def transformer(self):
    """Create DataTransformer instance."""
    return DataTransformer()

  def test_normalize_nodes_adds_missing_fields(self, transformer):
    """
    WHAT: Test that _normalize_nodes adds missing fields with defaults
    WHY: Ensures all nodes have complete structure
    EXPECTED: Nodes with missing fields get default values (0, False, None)
    DATA: Minimal nodes with only node_id
    """
    minimal_nodes = [{"node_id": 0}, {"node_id": 1}]

    normalized = transformer._normalize_nodes(minimal_nodes)

    for node in normalized:
      assert "x" in node
      assert "y" in node
      assert "z" in node
      assert "demand" in node
      assert "is_depot" in node
      assert "display_x" in node
      assert "display_y" in node

      # Check defaults
      assert node["demand"] == 0, "Missing demand should default to 0"
      assert node["is_depot"] is False, "Missing is_depot should default to False"

  def test_normalize_nodes_preserves_existing_values(self, transformer):
    """
    WHAT: Test that _normalize_nodes preserves existing field values
    WHY: Should not overwrite valid data
    EXPECTED: Existing values remain unchanged
    DATA: Nodes with all fields populated
    """
    complete_nodes = [
      {
        "node_id": 0,
        "x": 10.5,
        "y": 20.3,
        "z": None,
        "demand": 15,
        "is_depot": True,
        "display_x": 11.0,
        "display_y": 21.0,
      }
    ]

    normalized = transformer._normalize_nodes(complete_nodes)
    node = normalized[0]

    assert node["node_id"] == 0
    assert node["x"] == 10.5
    assert node["y"] == 20.3
    assert node["demand"] == 15
    assert node["is_depot"] is True
    assert node["display_x"] == 11.0
    assert node["display_y"] == 21.0


class TestDataTransformerIntegration:
  """Test DataTransformer with real parsed data."""

  @pytest.fixture
  def transformer(self):
    """Create DataTransformer instance."""
    return DataTransformer()

  def test_full_transformation_pipeline(self, transformer):
    """
    WHAT: Test complete transformation pipeline with real data
    WHY: Verify transformer works end-to-end
    EXPECTED: Parse → transform → JSON format → validate all work together
    DATA: gr17.tsp
    """
    # Parse
    parser = FormatParser()
    parsed = parser.parse_file("datasets_raw/problems/tsp/gr17.tsp")

    # Transform
    transformed = transformer.transform_problem(parsed)

    # Validate
    errors = transformer.validate_transformation(transformed)
    assert errors == [], f"Transformed data should be valid, errors: {errors}"

    # Convert to JSON format
    json_format = transformer.to_json_format(transformed)

    # Verify JSON format (no v1 ``nodes`` key; dimension preserved on hub)
    assert "nodes" not in json_format, "no v1 'nodes' key in v2 JSON output"
    assert json_format["problem"]["name"] == "gr17"
    assert json_format["problem"]["type"] == "TSP"
    assert json_format["problem"]["dimension"] == 17
