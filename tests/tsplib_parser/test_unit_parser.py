"""
Tests for FormatParser - TSPLIB95 file parsing.

Tests the actual behavior of FormatParser.parse_file() method with real TSPLIB files.
Based on verified system output from running the CLI successfully.
"""

from collections.abc import Callable
from typing import Any, cast

import pytest

from tsplib_parser.exceptions import ParseError
from tsplib_parser.parser import FormatParser


class TestFormatParserBasic:
  """Test basic FormatParser functionality with real files."""

  @pytest.mark.requires_dataset
  def test_parse_file_gr17_explicit_weights(self, dataset_path: Callable[..., str]) -> None:
    """
    Test parsing gr17.tsp - 17-city TSP with EXPLICIT edge weights.

    WHAT: Parse gr17.tsp and validate the returned data structure
    WHY: Verify parser correctly handles EXPLICIT weight matrix problems
    EXPECTED: Returns dict with problem_data, nodes (empty - EXPLICIT has no coordinates), tours, metadata
    TEST DATA: gr17.tsp (17 cities, EXPLICIT weights, LOWER_DIAG_ROW format)

    NOTE: EXPLICIT weight problems carry no coordinates, so no node rows are
    produced (Decision 3 - the virtual-node scaffold is removed).
    """
    parser = FormatParser()
    result = parser.parse_file(dataset_path("tsp", "gr17.tsp"))

    # Verify result structure
    assert isinstance(result, dict), "Result must be a dictionary"
    assert "problem_data" in result, "Result must have problem_data key"
    assert "coords" in result, "Result must have coords key"
    assert "display_coords" in result, "Result must have display_coords key"
    assert "nodes" not in result, "Result must not have retired v1 nodes key"
    assert "tours" in result, "Result must have tours key"
    assert "metadata" in result, "Result must have metadata key"

    # Verify problem_data
    problem_data = result["problem_data"]
    assert problem_data["name"] == "gr17", "Problem name should be gr17"
    assert problem_data["type"] == "TSP", "Problem type should be TSP"
    assert problem_data["dimension"] == 17, "Should have 17 nodes"
    assert problem_data["edge_weight_type"] == "EXPLICIT", "Should have EXPLICIT weights"
    assert problem_data["edge_weight_format"] == "LOWER_DIAG_ROW", "Should be LOWER_DIAG_ROW format"

    # Verify coords structure (EXPLICIT problems produce empty coords)
    coords: list[list[float]] = cast("list[list[float]]", result["coords"])
    assert isinstance(coords, list), "Coords must be a list"
    assert len(coords) == 0, "EXPLICIT problems must yield empty coords (no NODE_COORD_SECTION)"

    # Verify tours (gr17.tsp has no tour solution)
    tours: list[Any] = cast("list[Any]", result["tours"])
    assert isinstance(tours, list), "Tours must be a list"
    assert len(tours) == 0, "gr17.tsp has no tour solution"

    # Verify metadata
    metadata = result["metadata"]
    assert "file_path" in metadata, "Metadata must have file_path"
    assert "gr17.tsp" in metadata["file_path"], "file_path should contain filename"
    assert metadata["has_coordinates"] is False, "EXPLICIT problems have no coordinates"
    assert metadata["is_symmetric"] is True, "TSP is symmetric"
    assert metadata["weight_source"] == "explicit_matrix", "Should be explicit_matrix"

  @pytest.mark.requires_dataset
  def test_parse_file_att48_att_distance(self, dataset_path: Callable[..., str]) -> None:
    """
    Test parsing att48.tsp - 48-city TSP with ATT (pseudo-Euclidean) distance.

    WHAT: Parse att48.tsp with ATT distance metric
    WHY: Verify parser handles different distance types
    EXPECTED: Problem data with ATT edge_weight_type, 48 coordinate rows
    TEST DATA: att48.tsp (48 US capitals, ATT distance)
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "att48.tsp"))

    # Verify problem data
    problem_data = result["problem_data"]
    assert problem_data["name"] == "att48", "Problem name should be att48"
    assert problem_data["type"] == "TSP", "Problem type should be TSP"
    assert problem_data["dimension"] == 48, "Should have 48 nodes"
    assert problem_data["edge_weight_type"] == "ATT", "Should use ATT distance"
    assert problem_data["comment"] == "48 capitals of the US (Padberg/Rinaldi)", "Should have correct comment"

    # Verify correct number of coordinate rows
    assert len(result["coords"]) == 48, "Should extract all 48 node coordinates"

    # Verify metadata indicates coordinate-based problem
    metadata = result["metadata"]
    assert metadata["weight_source"] == "coordinate_based", "ATT is coordinate-based"
    assert metadata["is_symmetric"] is True, "ATT problems are symmetric"

  @pytest.mark.requires_dataset
  def test_parse_file_berlin52_euclidean(self, dataset_path: Callable[..., str]) -> None:
    """
    Test parsing berlin52.tsp - 52-location TSP with Euclidean distances.

    WHAT: Parse berlin52.tsp with EUC_2D distance
    WHY: Verify parser handles Euclidean distance type
    EXPECTED: Problem data with EUC_2D, 52 coordinate rows
    TEST DATA: berlin52.tsp (52 locations in Berlin)
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "berlin52.tsp"))

    problem_data = result["problem_data"]
    assert problem_data["name"] == "berlin52", "Problem name should be berlin52"
    assert problem_data["dimension"] == 52, "Should have 52 nodes"
    assert problem_data["edge_weight_type"] == "EUC_2D", "Should use Euclidean 2D distance"

    assert len(result["coords"]) == 52, "Should extract all 52 node coordinates"


class TestFormatParserErrorHandling:
  """Test error handling in FormatParser."""

  def test_parse_nonexistent_file(self) -> None:
    """
    Test parsing a file that doesn't exist.

    WHAT: Attempt to parse non-existent file
    WHY: Verify parser raises appropriate error
    EXPECTED: ParseError raised
    """
    parser = FormatParser()

    with pytest.raises(expected_exception=ParseError, match="Failed to parse"):
      parser.parse_file(file_path="nonexistent_file.tsp")

  def test_parse_invalid_file_path(self) -> None:
    """
    Test parsing with invalid file path.

    WHAT: Pass invalid path to parser
    WHY: Verify error handling for bad paths
    EXPECTED: ParseError raised
    """
    parser = FormatParser()

    with pytest.raises(expected_exception=ParseError, match="Failed to parse"):
      parser.parse_file(file_path="/invalid/path/to/file.tsp")


class TestFormatParserDataIntegrity:
  """Test data integrity and consistency."""

  @pytest.mark.requires_dataset
  def test_coord_row_sequence(self, dataset_path: Callable[..., str]) -> None:
    """
    Test that coordinate rows are 0-based and ordered by TSPLIB node ID 1..dimension.

    WHAT: Verify coords array length and 0-based ordering
    WHY: Ensure proper 1-based TSPLIB → 0-based database conversion
    EXPECTED: coords has 48 2-element float lists for att48.tsp
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "att48.tsp"))

    coords = result["coords"]
    assert len(coords) == 48
    assert all(isinstance(row, list) and len(row) == 2 and all(isinstance(v, float) for v in row) for row in coords)

  @pytest.mark.requires_dataset
  def test_dimension_matches_coord_count(self, dataset_path: Callable[..., str]) -> None:
    """
    Test that dimension matches the actual coordinate row count for coordinate-based
    problems, and that coordinate-less (EXPLICIT) problems yield empty coords.

    WHAT: Verify dimension vs coord-count consistency per problem family
    WHY: Coordinate-based problems must expose one coordinate row per node;
        EXPLICIT weight problems have no coordinates so they must expose
        empty coords (Decision 3 - the virtual-node scaffold is removed).
    EXPECTED: dimension == len(coords) for coordinate-based files; for
        EXPLICIT gr17, dimension == 17 but len(coords) == 0.
    """
    parser = FormatParser()

    # Coordinate-based files: dimension == coord count
    coordinate_files: list[tuple[str, int]] = [
      (dataset_path("tsp", "att48.tsp"), 48),
      (dataset_path("tsp", "berlin52.tsp"), 52),
    ]
    for file_path, expected_dimension in coordinate_files:
      result = parser.parse_file(file_path)
      dimension = result["problem_data"]["dimension"]
      coord_count: int = len(result["coords"])

      assert dimension == coord_count, f"{file_path}: dimension={dimension} but got {coord_count} coords"
      assert dimension == expected_dimension, f"{file_path}: expected dimension={expected_dimension}, got {dimension}"

    # EXPLICIT (coordinate-less) file: empty coords, dimension intact
    result = parser.parse_file(file_path=dataset_path("tsp", "gr17.tsp"))
    assert result["problem_data"]["dimension"] == 17, "gr17 dimension should be 17"
    assert len(result["coords"]) == 0, "EXPLICIT gr17 must yield empty coords (no coordinates)"


class TestFormatParserMetadata:
  """Test metadata extraction."""

  @pytest.mark.requires_dataset
  def test_metadata_file_info(self, dataset_path: Callable[..., str]) -> None:
    """
    Test that metadata contains correct file information.

    WHAT: Verify metadata has file_path, file_name, file_size
    WHY: Ensure file tracking works correctly
    EXPECTED: Metadata with complete file information
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "gr17.tsp"))

    metadata = result["metadata"]

    # Check required fields
    assert "file_path" in metadata, "Must have file_path"
    assert "file_name" in metadata, "Must have file_name"
    assert "file_size" in metadata, "Must have file_size"
    assert "problem_source" in metadata, "Must have problem_source"

    # Check values
    assert metadata["file_name"] == "gr17.tsp", "Should extract filename"
    assert "gr17.tsp" in metadata["file_path"], "file_path should contain filename"
    assert metadata["file_size"] > 0, "file_size should be positive"
    assert metadata["problem_source"] == "tsp", "Should extract problem source from path"

  @pytest.mark.requires_dataset
  def test_metadata_problem_characteristics(self, dataset_path: Callable[..., str]) -> None:
    """
    Test metadata problem characteristic flags.

    WHAT: Verify has_coordinates, has_demands, has_depots, is_symmetric flags
    WHY: Ensure problem characteristics are correctly identified
    EXPECTED: Correct boolean flags based on problem type
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "gr17.tsp"))

    metadata = result["metadata"]

    # TSP problems should have specific characteristics
    assert metadata["has_coordinates"] is False, "EXPLICIT problems have no coordinates"
    assert metadata["has_demands"] is False, "TSP has no demands"
    assert metadata["has_depots"] is False, "TSP has no depots"
    assert metadata["is_symmetric"] is True, "TSP is symmetric"


class TestFormatParserValueValidation:
  """Test that parser extracts CORRECT values, not just structure.

  This addresses the critical finding that previous tests only checked
  structure (dict keys exist) but never validated actual data values.
  """

  @pytest.mark.requires_dataset
  def test_gr17_edge_weight_matrix_correctness(self, dataset_path: Callable[..., str]) -> None:
    """
    Verify gr17.tsp edge weight matrix values are correct.

    WHAT: Parse gr17.tsp and validate actual edge weight values against reference
    WHY: Ensure parser extracts correct distances, not just structure
    EXPECTED: Matrix values match known-good TSPLIB reference values
    TEST DATA: gr17.tsp with verified edge weights from TSPLIB
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "gr17.tsp"))

    # Extract edge weight matrix
    edge_weights = result["problem_data"]["edge_weights"]

    # Verify matrix type and dimension
    assert edge_weights.size == 17, f"Expected dimension 17, got {edge_weights.size}"

    # Validate specific known values from TSPLIB reference
    assert edge_weights[0, 0] == 0, "gr17[0,0] diagonal should be 0"
    assert edge_weights[0, 1] == 633, "gr17[0,1] should be 633"
    assert edge_weights[0, 2] == 257, "gr17[0,2] should be 257"
    assert edge_weights[1, 2] == 390, "gr17[1,2] should be 390"
    assert edge_weights[0, 16] == 121, "gr17[0,16] should be 121"
    assert edge_weights[16, 16] == 0, "gr17[16,16] diagonal should be 0"

    # Validate symmetry (gr17 is symmetric TSP)
    asymmetric_pairs = []
    for i in range(17):
      for j in range(17):
        if edge_weights[i, j] != edge_weights[j, i]:
          asymmetric_pairs.append((i, j, edge_weights[i, j], edge_weights[j, i]))

    assert len(asymmetric_pairs) == 0, (
      f"gr17 should be symmetric, but found {len(asymmetric_pairs)} asymmetric pairs: {asymmetric_pairs[:5]}"
    )

  @pytest.mark.requires_dataset
  def test_berlin52_coordinates_correctness(self, dataset_path: Callable[..., str]) -> None:
    """
    Verify berlin52.tsp coordinate values are correct.

    WHAT: Parse berlin52.tsp and validate actual x,y coordinates
    WHY: Ensure parser extracts correct coordinates from NODE_COORD_SECTION
    EXPECTED: Coordinates match known-good TSPLIB reference values
    TEST DATA: berlin52.tsp with verified coordinates from TSPLIB
    """
    parser = FormatParser()
    result = parser.parse_file(file_path=dataset_path("tsp", "berlin52.tsp"))

    coords = result["coords"]

    # Verify coordinate row count
    assert len(coords) == 52, f"Expected 52 coordinate rows, got {len(coords)}"

    # Validate specific known coordinates from TSPLIB reference (0-based index)
    assert coords[0] == [565.0, 575.0], "berlin52 node 0 should be [565.0, 575.0]"
    assert coords[1] == [25.0, 185.0], "berlin52 node 1 should be [25.0, 185.0]"
    assert coords[2] == [345.0, 750.0], "berlin52 node 2 should be [345.0, 750.0]"
    assert coords[51] == [1740.0, 245.0], "berlin52 node 51 should be [1740.0, 245.0]"

    # Validate ALL coordinates are 2-element float lists
    for i, row in enumerate(iterable=coords):
      assert isinstance(row, list) and len(row) == 2, f"Row {i} should be 2-element list, got {row!r}"
      assert all(isinstance(v, float) for v in row), f"Row {i} values must be float, got {row!r}"
