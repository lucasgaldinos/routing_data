"""Tests for Cordeau MDVRP format converter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tsplib_parser.cordeau import CordeauConverter, CordeauParseError, CordeauParser
from tsplib_parser.cordeau.cordeau_types import CordeauProblem
from tsplib_parser.exceptions import FormatError
from tsplib_parser.models import ExtendedProblem, Problem

if TYPE_CHECKING:
  from pathlib import Path

  from tsplib_parser.cordeau.cordeau_types import CordeauNode

# Test files specified by user
TEST_FILES: list[str] = ["p01", "p03", "p08", "pr05", "p23"]


@pytest.fixture
def cordeau_parser() -> CordeauParser:
  """Create Cordeau parser instance."""
  return CordeauParser(logger=logging.getLogger(name=__name__))


@pytest.fixture
def cordeau_converter() -> CordeauConverter:
  """Create Cordeau converter instance."""
  return CordeauConverter(logger=logging.getLogger(name=__name__))


@pytest.fixture
def temp_converted_dir(tmp_path: Path) -> Path:
  """Create temporary directory for converted files."""
  converted_dir: Path = tmp_path / "converted"
  converted_dir.mkdir()
  return converted_dir


class TestCordeauParser:
  """Test Cordeau format parsing."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  @pytest.mark.requires_dataset
  def test_parse_file(self, cordeau_mdvrp_dir: Path, cordeau_parser: CordeauParser, filename: str) -> None:
    """Test parsing Cordeau file successfully."""
    file_path: Path = cordeau_mdvrp_dir / filename

    problem: CordeauProblem = cordeau_parser.parse_file(file_path)

    # Basic validation
    assert problem is not None
    assert problem.problem_type == 2  # MDVRP
    assert problem.num_vehicles > 0
    assert problem.num_customers > 0
    assert problem.num_depots > 0
    assert len(problem.nodes) == problem.num_customers + problem.num_depots
    assert len(problem.depot_constraints) == problem.num_depots

  @pytest.mark.requires_dataset
  def test_parse_p01_specific(self, cordeau_mdvrp_dir: Path, cordeau_parser: CordeauParser) -> None:
    """Test p01 specific values."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")

    # p01 is a well-known benchmark, verify key properties
    assert problem.num_vehicles == 4
    assert problem.num_customers == 50
    assert problem.num_depots == 4

    # Check customers have demands
    customers: list[CordeauNode] = problem.customer_nodes
    assert all(node.demand > 0 for node in customers)

    # Check depots have no demands
    depots: list[CordeauNode] = problem.depot_nodes
    assert all(node.demand == 0 for node in depots)
    assert all(node.is_depot for node in depots)

  def test_invalid_file(self, cordeau_parser: CordeauParser, tmp_path: Path) -> None:
    """Test parsing invalid file raises error."""
    invalid_file: Path = tmp_path / "invalid.txt"
    invalid_file.write_text(data="not a valid cordeau file\n")

    with pytest.raises(expected_exception=CordeauParseError, match="Header must have 4 values"):
      cordeau_parser.parse_file(file_path=invalid_file)

  def test_cordeau_parse_error_is_format_error(self) -> None:
    """Verify CordeauParseError is part of FormatError exception tree."""
    assert issubclass(CordeauParseError, FormatError)

  def test_line_count_mismatch_raises_error(self, cordeau_parser: CordeauParser, tmp_path: Path) -> None:
    """Verify files with missing or extra node lines raise CordeauParseError."""
    # Header says 1 vehicle, 2 customers, 1 depot -> expects 1 + 1 + 2 + 1 = 5 lines
    content = "2 1 2 1\n0 100\n1 10.0 20.0 0.0 5 1 1 1\n# Missing customer 2 and depot!\n"
    truncated: Path = tmp_path / "truncated.txt"
    truncated.write_text(content)
    with pytest.raises(expected_exception=CordeauParseError, match="Expected 5 non-empty lines"):
      cordeau_parser.parse_file(file_path=truncated)

  def test_invalid_time_windows_raises_error(self, cordeau_parser: CordeauParser, tmp_path: Path) -> None:
    """Verify invalid time windows in MDVRPTW raise CordeauParseError instead of being swallowed."""
    # type 6 is MDVRPTW
    content = "6 1 1 1\n0 100\n1 10.0 20.0 0.0 5 1 1 1 not_a_number 100.0\n2 0.0 0.0 0.0 0 1 1 1 0.0 1000.0\n"
    tw_file: Path = tmp_path / "bad_tw.txt"
    tw_file.write_text(content)
    with pytest.raises(expected_exception=CordeauParseError, match="invalid time window values"):
      cordeau_parser.parse_file(file_path=tw_file)

  @pytest.mark.requires_dataset
  def test_cordeau_problem_is_not_a_tsplib_problem(
    self, cordeau_mdvrp_dir: Path, cordeau_parser: CordeauParser
  ) -> None:
    """Verify CordeauProblem is a source record and to_extended() is its conversion boundary."""
    assert not issubclass(CordeauProblem, Problem)
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")
    assert isinstance(problem.to_extended(), ExtendedProblem)

  @pytest.mark.requires_dataset
  def test_cordeau_problem_as_dict(self, cordeau_mdvrp_dir: Path, cordeau_parser: CordeauParser) -> None:
    """Verify CordeauProblem.as_dict() produces normalized problem data."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")
    data: dict[str, Any] = problem.as_dict()
    assert data["name"] == "p01"
    assert data["type"] == "MDVRP"
    assert data["dimension"] == 54
    assert data["vehicles"] == 16  # 4 vehicles * 4 depots
    assert data["capacity"] == 80
    assert len(data["depots"]) == 4
    assert len(data["node_coords"]) == 54
    assert len(data["demands"]) == 54

  @pytest.mark.requires_dataset
  def test_cordeau_problem_to_extended(self, cordeau_mdvrp_dir: Path, cordeau_parser: CordeauParser) -> None:
    """Verify CordeauProblem.to_extended() creates a valid ExtendedProblem model."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")
    extended: ExtendedProblem = problem.to_extended()
    assert isinstance(extended, ExtendedProblem)
    assert extended.name == "p01"
    assert extended.problem_type == "MDVRP"
    assert extended.dimension == 54
    assert extended.vehicles == 16
    assert extended.capacity == 80
    assert extended.depots == [node.node_id for node in problem.depot_nodes]
    assert not hasattr(extended, "num_depots")


class TestCordeauConverter:
  """Test Cordeau to TSPLIB95 conversion."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  @pytest.mark.requires_dataset
  def test_convert_to_extended_tsplib(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    filename: str,
  ) -> None:
    """Verify the emitted document keeps the real type and every depot."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / filename)

    tsplib_content: str = cordeau_converter.to_tsplib(problem)

    # The instance's real type, never a single-depot CVRP surrogate.
    assert f"TYPE : {problem.type_name}" in tsplib_content
    assert "TYPE : CVRP" not in tsplib_content

    # Every depot survives, and the depot count is the section length.
    assert "DEPOT_SECTION" in tsplib_content
    depot_block: str = tsplib_content.split("DEPOT_SECTION", 1)[1].split("-1", 1)[0]
    depot_ids: list[str] = depot_block.split()
    assert len(depot_ids) == problem.num_depots
    assert depot_ids == [str(node.node_id) for node in problem.depot_nodes]

    assert "NAME" in tsplib_content
    assert "DIMENSION" in tsplib_content
    assert "EDGE_WEIGHT_TYPE" in tsplib_content
    assert "NODE_COORD_SECTION" in tsplib_content
    assert "DEMAND_SECTION" in tsplib_content
    assert "EOF" in tsplib_content

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  @pytest.mark.requires_dataset
  def test_convert_with_output_file(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test conversion with file output."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(cordeau_mdvrp_dir / filename)

    # Convert with output file
    output_path = temp_converted_dir / f"{filename}.vrp"
    tsplib_content: str = cordeau_converter.to_tsplib(problem, output_path=output_path)

    # Check file was created
    assert output_path.exists()

    # Check file content matches returned content
    file_content: str = output_path.read_text()
    assert file_content == tsplib_content

  @pytest.mark.requires_dataset
  def test_convert_p01_specific(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
  ) -> None:
    """Test p01 specific conversion details."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")
    tsplib_content: str = cordeau_converter.to_tsplib(problem)

    # Check dimension (customers + depots)
    assert f"DIMENSION : {problem.dimension}" in tsplib_content

    # Check depot section lists all depots
    lines: list[str] = tsplib_content.split("\n")
    depot_section_start: int | None = None
    for i, line in enumerate(iterable=lines):
      if line.strip() == "DEPOT_SECTION":
        depot_section_start = i
        break

    assert depot_section_start is not None

    # Count depot entries (should be num_depots + terminator -1)
    depot_entries: list[int] = []
    for raw_line in lines[depot_section_start + 1 :]:
      stripped: str = raw_line.strip()
      if not stripped or stripped == "EOF":
        break
      try:
        depot_entries.append(int(stripped))
      except ValueError:
        break

    # Last entry should be -1
    assert depot_entries[-1] == -1
    # The listed ids are the depots' own node numbers, not a renumbering
    assert depot_entries[:-1] == [node.node_id for node in problem.depot_nodes]

  @pytest.mark.requires_dataset
  def test_convert_to_tsplib_extended_lossless(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
  ) -> None:
    """Test lossless conversion to the TSPLIB-extended format."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / "p01")
    content: str = cordeau_converter.to_tsplib(problem=problem)

    assert "TYPE : MDVRP" in content
    assert "VEHICLES : 16" in content
    assert "CAPACITY : 80" in content
    # The depot count is derived from DEPOT_SECTION, so no DEPOTS header.
    assert "DEPOTS :" not in content

    # Verify ExtendedProblem parses it back losslessly
    parsed: ExtendedProblem = ExtendedProblem.parse(text=content)
    assert parsed.name == "p01"
    assert parsed.problem_type == "MDVRP"
    assert parsed.vehicles == 16
    assert parsed.capacity == 80
    assert parsed.depots == [node.node_id for node in problem.depot_nodes]

  def test_convert_heterogeneous_depot_sections(
    self,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    tmp_path: Path,
  ) -> None:
    """Test that heterogeneous depot constraints emit extended sections without data loss."""
    content = (
      "2 2 4 2\n"
      "100 120\n"
      "150 200\n"
      "1 10.0 20.0 5.0 10 1 1 1\n"
      "2 30.0 40.0 5.0 15 1 1 1\n"
      "3 50.0 60.0 5.0 20 1 1 1\n"
      "4 70.0 80.0 5.0 25 1 1 1\n"
      "5 0.0 0.0 0.0 0 1 1 1\n"
      "6 100.0 100.0 0.0 0 1 1 1\n"
    )
    raw_file: Path = tmp_path / "hetero.txt"
    raw_file.write_text(content)

    problem: CordeauProblem = cordeau_parser.parse_file(file_path=raw_file)
    content: str = cordeau_converter.to_tsplib(problem=problem)

    assert "DEPOT_CAPACITY_SECTION" in content
    assert "DEPOT_DURATION_SECTION" in content

    parsed: ExtendedProblem = ExtendedProblem.parse(text=content)
    assert parsed.problem_type == "MDVRP"
    assert parsed.depot_capacities == {1: 120, 2: 200}
    assert parsed.depot_durations == {1: 100.0, 2: 150.0}


def test_mdvrptw_round_trip_keeps_source_node_ids(
  tmp_path: Path,
  cordeau_parser: CordeauParser,
  cordeau_converter: CordeauConverter,
) -> None:
  """A type-6 instance converts to a document this parser reads back unchanged.

  Regression for two defects: ``MDVRPTW`` was absent from
  ``EXTENDED_PROBLEM_TYPES``, so the converter's own output raised
  ``ValidationError: Unknown problem type: MDVRPTW``; and
  ``TIME_WINDOW_SECTION``/``SERVICE_TIME_SECTION`` renumbered nodes 1..dimension
  with the depots first, while ``NODE_COORD_SECTION``/``DEMAND_SECTION`` kept the
  source ids (customers 1..n, depots n+1..n+t), so every customer window slid one
  node further back for each depot in the instance.
  """
  content = (
    "6 2 4 2\n"
    "100 120\n"
    "150 200\n"
    "1 10.0 20.0 5.0 10 1 1 1 0.0 50.0\n"
    "2 30.0 40.0 5.0 15 1 1 1 0.0 60.0\n"
    "3 50.0 60.0 5.0 20 1 1 1 0.0 70.0\n"
    "4 70.0 80.0 5.0 25 1 1 1 0.0 80.0\n"
    "5 0.0 0.0 0.0 0 0 0\n"
    "6 100.0 100.0 0.0 0 0 0\n"
  )
  raw_file: Path = tmp_path / "mdvrptw.txt"
  raw_file.write_text(content)

  problem: CordeauProblem = cordeau_parser.parse_file(file_path=raw_file)
  converted: str = cordeau_converter.to_tsplib(problem=problem)
  parsed: ExtendedProblem = ExtendedProblem.parse(text=converted)

  assert parsed.problem_type == "MDVRPTW"
  assert parsed.depots == [5, 6]
  # Each customer window must stay on its own source node id; the pre-fix output
  # put customer 1's window on node 3.
  assert parsed.time_windows[1] == [0.0, 50.0]
  assert parsed.time_windows[2] == [0.0, 60.0]
  assert parsed.time_windows[3] == [0.0, 70.0]
  assert parsed.time_windows[4] == [0.0, 80.0]
  # Depots carry no window in the source, so none is invented for them.
  assert 5 not in parsed.time_windows
  assert 6 not in parsed.time_windows
