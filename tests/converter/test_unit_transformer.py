"""
Tests for converter.core.transformer.DataTransformer - Data transformation logic.

Tests the actual behavior of DataTransformer which normalizes and enriches parsed data.
Based on verified system output.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from converter.core.transformer import DataTransformer
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult


class TestDataTransformerBasic:
  """Test basic DataTransformer functionality."""

  @pytest.fixture
  def transformer(self) -> DataTransformer:
    """Create DataTransformer instance."""
    return DataTransformer()

  @pytest.fixture
  def parsed_data(self, dataset_path: Callable[..., str]) -> "ParseResult":
    """Parse sample data for transformation tests."""
    parser = FormatParser()
    return parser.parse_file(dataset_path("tsp", "gr17.tsp"))

  @pytest.mark.requires_dataset
  def test_transform_problem_returns_expected_keys(
    self, transformer: DataTransformer, parsed_data: "ParseResult"
  ) -> None:
    """
    WHAT: Test that transform_problem returns the schema-v2 payload keys
    WHY: Schema v2 (Decision 3) drops the v1 ``nodes`` row-list; node data is
        carried as array columns. gr17.tsp is EXPLICIT so it also carries the
        edge_weight_matrix (and coords/display_coords stay None).
    EXPECTED: Returns dict with the exact v2 key set, no ``nodes`` key
    DATA: gr17.tsp parsed data
    """
    result: dict[str, Any] = transformer.transform_problem(parsed_data)

    # gr17 (EXPLICIT TSP) → edge_weight_matrix present, no ``nodes`` key.
    expected_keys: set[str] = {
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

  @pytest.mark.requires_dataset
  def test_transform_problem_enriches_problem_data(
    self, transformer: DataTransformer, parsed_data: "ParseResult"
  ) -> None:
    """
    WHAT: Test that transform_problem enriches problem_data with file info
    WHY: Should add file_path and file_size from metadata to problem_data
    EXPECTED: problem_data contains file_path and file_size
    DATA: gr17.tsp
    """
    result: dict[str, Any] = transformer.transform_problem(parsed_data)
    problem_data = result["problem_data"]

    assert "file_path" in problem_data, "Should add file_path to problem_data"
    assert "file_size" in problem_data, "Should add file_size to problem_data"
    assert isinstance(problem_data["file_size"], int)

  @pytest.mark.requires_dataset
  def test_transform_problem_emits_array_columns_not_nodes(
    self, transformer: DataTransformer, dataset_path: Callable[..., str]
  ) -> None:
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
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "berlin52.tsp"))
    result: dict[str, Any] = transformer.transform_problem(parsed)

    assert "nodes" not in result, "v1 'nodes' key must be gone"
    dimension = result["problem_data"]["dimension"]
    assert dimension == 52
    # coords is the observable per-node surface for a coordinate problem;
    # display_coords stays None unless the format needs display normalization.
    assert result["coords"] is not None
    assert len(result["coords"]) == dimension
    if result["display_coords"] is not None:
      assert len(result["display_coords"]) == dimension

  @pytest.mark.requires_dataset
  def test_transform_problem_preserves_node_count(
    self, transformer: DataTransformer, dataset_path: Callable[..., str]
  ) -> None:
    """
    WHAT: Test that transformation preserves node count
    WHY: Normalization should not add or remove nodes; the count surfaces as
        the length of the coords / display_coords array columns (v2)
    EXPECTED: coords/display_coords length equals both the parsed coord count and dimension
    DATA: berlin52.tsp - 52 nodes
    """
    parser = FormatParser()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "berlin52.tsp"))
    input_count: int = len(parsed["coords"])
    assert input_count == 52

    result: dict[str, Any] = transformer.transform_problem(parsed)
    output_count: int = len(result["coords"]) if result["coords"] is not None else 0

    assert output_count == input_count, "Node count should be preserved"
    assert output_count == result["problem_data"]["dimension"]

  @pytest.mark.requires_dataset
  def test_transform_problem_with_file_info(self, transformer: DataTransformer, parsed_data: "ParseResult") -> None:
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
  def transformer(self) -> DataTransformer:
    """Create DataTransformer instance."""
    return DataTransformer()

  @pytest.fixture
  def transformed_data(self, transformer: DataTransformer, dataset_path: Callable[..., str]) -> dict[str, Any]:
    """Get transformed data for JSON format tests."""
    parser = FormatParser()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))
    return transformer.transform_problem(parsed)

  def test_to_json_format_renames_problem_data(
    self, transformer: DataTransformer, transformed_data: dict[str, Any]
  ) -> None:
    """
    WHAT: Test that to_json_format renames 'problem_data' to 'problem'
    WHY: JSON format uses shorter key name
    EXPECTED: Returns dict with 'problem' key instead of 'problem_data'
    DATA: gr17.tsp transformed data
    """
    json_format: dict[str, Any] = transformer.to_json_format(transformed_data)

    assert "problem" in json_format, "Should have 'problem' key"
    assert "problem_data" not in json_format, "Should not have 'problem_data' key"
    assert json_format["problem"] == transformed_data["problem_data"]

  def test_to_json_format_preserves_data_tours_metadata(
    self, transformer: DataTransformer, transformed_data: dict[str, Any]
  ) -> None:
    """
    WHAT: Test that to_json_format preserves the v2 payload
    WHY: Schema v2 has no ``nodes`` list; JSON must forward problem, the array
        columns, tours and metadata unchanged
    EXPECTED: problem == problem_data; tours/metadata identical; array-column keys
        (coords/display_coords/demands/depots/edges/fixed_edges) forwarded; no ``nodes``
    DATA: gr17.tsp
    """
    json_format: dict[str, Any] = transformer.to_json_format(transformed_data)

    assert "nodes" not in json_format, "no v1 'nodes' key in v2 JSON output"
    assert json_format["problem"] == transformed_data["problem_data"]
    assert json_format["tours"] == transformed_data["tours"]
    assert json_format["metadata"] == transformed_data["metadata"]
    for key in ("coords", "display_coords", "demands", "depots", "edges", "fixed_edges"):
      assert json_format[key] == transformed_data[key]

  def test_to_json_format_returns_expected_keys(
    self,
    transformer: DataTransformer,
    transformed_data: dict[str, Any]
  ) -> None:
    """
    WHAT: Test that to_json_format returns the v2 key set
    WHY: JSON format has a specific v2 key structure: problem (renamed from
        problem_data), tours, metadata plus the forwarded array-column keys.
    EXPECTED: Returns dict with the exact v2 key set, no ``nodes`` key
    DATA: gr17.tsp
    """
    json_format = transformer.to_json_format(transformed_data)

    expected_keys: set[str] = {
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


class TestDataTransformerCoordAndMatrixHandling:
  """Test schema-v2 coordinate and explicit matrix transformation."""

  @pytest.fixture
  def transformer(self) -> DataTransformer:
    """Create DataTransformer instance."""
    return DataTransformer()

  def test_explicit_problem_with_display_coords_preserves_display_coords(self, transformer: DataTransformer) -> None:
    """
    WHAT: Transform an EXPLICIT problem that has display_coords but no node coords
    WHY: Fixes PB13 — display coordinates must be preserved even when coords is None
    EXPECTED: coords is None, display_coords is preserved verbatim, edge_weight_matrix is n x n
    """
    synthetic_parsed: ParseResult = {
      "problem_data": {
        "name": "synthetic_display_only",
        "type": "TSP",
        "comment": None,
        "dimension": 3,
        "capacity": None,
        "node_coord_type": None,
        "edge_weight_type": "EXPLICIT",
        "edge_weight_format": "FULL_MATRIX",
        "display_data_type": None,
        "edge_data_format": None,
        "edge_weights": [[0, 5, 9], [5, 0, 4], [9, 4, 0]],
      },
      "coords": [],
      "display_coords": [[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]],
      "demands": [],
      "depots": [],
      "tours": [],
      "edges": [],
      "fixed_edges": [],
      "metadata": {
        "file_path": "",
        "file_name": "synthetic_display_only.tsp",
        "file_size": 0,
        "problem_source": None,
        "has_coordinates": False,
        "has_display_coords": True,
        "has_demands": False,
        "has_depots": False,
        "has_tours": False,
        "has_edges": False,
        "has_fixed_edges": False,
        "is_symmetric": True,
        "weight_source": "explicit_matrix",
      },
    }
    transformed: dict[str, Any] = transformer.transform_problem(synthetic_parsed)

    assert transformed["coords"] is None
    assert transformed["display_coords"] == [[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]]
    assert transformed["edge_weight_matrix"] == [[0, 5, 9], [5, 0, 4], [9, 4, 0]]

  def test_omitted_diagonal_matrix_preserves_depot_distances(self, transformer: DataTransformer) -> None:
    """
    WHAT: Transform a CVRP whose LOWER_ROW matrix omits the 0-diagonal (n*(n-1)//2 entries)
    WHY: Fixes M8 — previously misidentified omitted-diagonal triangular matrices as (n-1)-node
         customer-only matrices and zero-padded the depot row/column
    EXPECTED: Full n x n symmetric matrix with 0 diagonal and intact row/col 0 depot distances
    """
    # For n=4, LOWER_ROW has 4*3//2 = 6 entries:
    # row 1: [10], row 2: [20, 30], row 3: [40, 50, 60]
    synthetic_parsed: ParseResult = {
      "problem_data": {
        "name": "synthetic_lower_row_cvrp",
        "type": "CVRP",
        "comment": None,
        "dimension": 4,
        "capacity": 100,
        "node_coord_type": None,
        "edge_weight_type": "EXPLICIT",
        "edge_weight_format": "LOWER_ROW",
        "display_data_type": None,
        "edge_data_format": None,
        "edge_weights": [[10], [20, 30], [40, 50, 60]],
      },
      "coords": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
      "display_coords": [],
      "demands": [0, 10, 20, 30],
      "depots": [0],
      "tours": [],
      "edges": [],
      "fixed_edges": [],
      "metadata": {
        "file_path": "",
        "file_name": "synthetic_lower_row_cvrp.vrp",
        "file_size": 0,
        "problem_source": None,
        "has_coordinates": True,
        "has_display_coords": False,
        "has_demands": True,
        "has_depots": True,
        "has_tours": False,
        "has_edges": False,
        "has_fixed_edges": False,
        "is_symmetric": True,
        "weight_source": "explicit_matrix",
      },
    }
    transformed: dict[str, Any] = transformer.transform_problem(synthetic_parsed)
    mat = transformed["edge_weight_matrix"]

    assert mat == [
      [0, 10, 20, 40],
      [10, 0, 30, 50],
      [20, 30, 0, 60],
      [40, 50, 60, 0],
    ]


class TestDataTransformerIntegration:
  """Test DataTransformer with real parsed data."""

  @pytest.fixture
  def transformer(self) -> DataTransformer:
    """Create DataTransformer instance."""
    return DataTransformer()

  @pytest.mark.requires_dataset
  def test_full_transformation_pipeline(self, transformer: DataTransformer, dataset_path: Callable[..., str]) -> None:
    """
    WHAT: Test complete transformation pipeline with real data
    WHY: Verify transformer works end-to-end
    EXPECTED: Parse → transform → JSON format → validate all work together
    DATA: gr17.tsp
    """
    # Parse
    parser = FormatParser()
    parsed: ParseResult = parser.parse_file(dataset_path("tsp", "gr17.tsp"))

    # Transform
    transformed: dict[str, Any] = transformer.transform_problem(parsed)

    # Validate
    errors: list[str] = transformer.validate_transformation(transformed)
    assert errors == [], f"Transformed data should be valid, errors: {errors}"

    # Convert to JSON format
    json_format: dict[str, Any] = transformer.to_json_format(transformed)

    # Verify JSON format (no v1 ``nodes`` key; dimension preserved on hub)
    assert "nodes" not in json_format, "no v1 'nodes' key in v2 JSON output"
    assert json_format["problem"]["name"] == "gr17"
    assert json_format["problem"]["type"] == "TSP"
    assert json_format["problem"]["dimension"] == 17
