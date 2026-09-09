"""Tests for Cordeau MDVRP format converter."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from converter.api import merge_v2_payload
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from tsplib_parser.cordeau import CordeauConverter, CordeauParseError, CordeauParser
from tsplib_parser.cordeau.cordeau_types import CordeauNode, CordeauProblem
from tsplib_parser.parser import FormatParser

# Test files specified by user
TEST_FILES: list[str] = ["p01", "p03", "p08", "pr05", "p23"]


@pytest.fixture
def cordeau_base_path() -> Path:
  """Base path for Cordeau MDVRP test files."""
  return Path("datasets_raw/umalaga/mdvrp/C-mdvrp")


@pytest.fixture
def cordeau_parser() -> CordeauParser:
  """Create Cordeau parser instance."""
  return CordeauParser(logger=logging.getLogger(name=__name__))


@pytest.fixture
def cordeau_converter() -> CordeauConverter:
  """Create Cordeau converter instance."""
  return CordeauConverter(logger=logging.getLogger(name=__name__))


@pytest.fixture
def format_parser() -> FormatParser:
  """Create TSPLIB95 format parser instance."""
  return FormatParser(logger=logging.getLogger(__name__))


@pytest.fixture
def temp_converted_dir(tmp_path: Path) -> Path:
  """Create temporary directory for converted files."""
  converted_dir: Path = tmp_path / "converted"
  converted_dir.mkdir()
  return converted_dir


class TestCordeauParser:
  """Test Cordeau format parsing."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  def test_parse_file(self, cordeau_base_path: Path, cordeau_parser: CordeauParser, filename: str) -> None:
    """Test parsing Cordeau file successfully."""
    file_path: Path = cordeau_base_path / filename

    problem: CordeauProblem = cordeau_parser.parse_file(file_path)

    # Basic validation
    assert problem is not None
    assert problem.problem_type == 2  # MDVRP
    assert problem.num_vehicles > 0
    assert problem.num_customers > 0
    assert problem.num_depots > 0
    assert len(problem.nodes) == problem.num_customers + problem.num_depots
    assert len(problem.depot_constraints) == problem.num_depots

  def test_parse_p01_specific(self, cordeau_base_path: Path, cordeau_parser: CordeauParser) -> None:
    """Test p01 specific values."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / "p01")

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

    with pytest.raises(expected_exception=CordeauParseError):
      cordeau_parser.parse_file(file_path=invalid_file)


class TestCordeauConverter:
  """Test Cordeau to TSPLIB95 conversion."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  def test_convert_to_tsplib95(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    filename: str,
  ) -> None:
    """Test conversion to TSPLIB95 format."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / filename)

    # Convert to TSPLIB95
    tsplib_content: str = cordeau_converter.to_tsplib95(problem)

    # Basic validation
    assert tsplib_content is not None
    assert "NAME" in tsplib_content
    assert "TYPE" in tsplib_content
    assert "DIMENSION" in tsplib_content
    assert "EDGE_WEIGHT_TYPE" in tsplib_content
    assert "CAPACITY" in tsplib_content
    assert "NODE_COORD_SECTION" in tsplib_content
    assert "DEMAND_SECTION" in tsplib_content
    assert "DEPOT_SECTION" in tsplib_content
    assert "EOF" in tsplib_content

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  def test_convert_with_output_file(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test conversion with file output."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(cordeau_base_path / filename)

    # Convert with output file
    output_path = temp_converted_dir / f"{filename}.vrp"
    tsplib_content = cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Check file was created
    assert output_path.exists()

    # Check file content matches returned content
    file_content: str = output_path.read_text()
    assert file_content == tsplib_content

  def test_convert_p01_specific(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
  ) -> None:
    """Test p01 specific conversion details."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / "p01")
    tsplib_content: str = cordeau_converter.to_tsplib95(problem)

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
    for line in lines[depot_section_start + 1 :]:
      line = line.strip()
      if not line or line == "EOF":
        break
      try:
        depot_entries.append(int(line))
      except ValueError:
        break

    # Last entry should be -1
    assert depot_entries[-1] == -1
    # Number of actual depot IDs should match num_depots
    assert len(depot_entries) - 1 == problem.num_depots


class TestCordeauIntegration:
  """Test integration with existing pipeline."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  def test_tsplib95_parser_accepts_converted(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test that converted TSPLIB95 can be parsed by existing parser."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / filename)

    # Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing TSPLIB95 parser
    parsed_data: dict[str, Any] = format_parser.parse_file(file_path=output_path)

    # Validate parsed data
    assert parsed_data is not None
    assert "problem_data" in parsed_data
    assert parsed_data["problem_data"]["name"] == filename
    assert parsed_data["problem_data"]["type"] == "CVRP"
    assert parsed_data["problem_data"]["dimension"] == problem.dimension
    # Capacity: use max capacity from depot constraints
    expected_capacity = max(c.max_load for c in problem.depot_constraints)
    assert parsed_data["problem_data"]["capacity"] == expected_capacity

  @pytest.mark.parametrize("filename", TEST_FILES)
  def test_transformer_processes_converted(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test that transformer can process converted problem."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(cordeau_base_path / filename)

    # Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing TSPLIB95 parser
    parsed_data: dict[str, Any] = format_parser.parse_file(output_path)

    # Transform
    transformer = DataTransformer(logger=logging.getLogger(__name__))
    transformed: dict[str, Any] = transformer.transform_problem(parsed_data)

    # Validate transformation
    assert transformed is not None
    assert "problem_data" in transformed
    assert "nodes" in transformed
    assert len(transformed["nodes"]) == problem.dimension
    assert transformed["problem_data"]["name"] == filename
    assert transformed["problem_data"]["type"] == "CVRP"
    assert transformed["problem_data"]["dimension"] == problem.dimension

  def test_full_pipeline_p01(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
  ) -> None:
    """Test full pipeline: Parse → Convert → Parse → Transform → DB (v2)."""
    filename = "p01"

    # Step 1: Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / filename)

    # Step 2: Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Step 3: Parse with existing TSPLIB95 parser
    parsed_data: dict[str, Any] = format_parser.parse_file(output_path)

    # Step 4: Transform (v2 array-column payload)
    transformer = DataTransformer(logger=logging.getLogger(__name__))
    transformed: dict[str, Any] = transformer.transform_problem(problem_data=parsed_data)

    # Step 5: Insert via the v2 write path. `insert_problem` consumes the
    # flat merged payload (hub + shared columns at top level), so flatten
    # the transformed result with the production `merge_v2_payload`, then
    # write hub + cvrp_problems in one transaction. The manager opens a
    # fresh duckdb connection per operation, so a `:memory:` db cannot
    # persist schema/data across calls — use a file-backed scratch db
    # (the repo DB-test convention).
    db_manager = DatabaseManager(
      db_path=str(temp_converted_dir / "pipeline.duckdb"),
      logger=logging.getLogger(__name__),
    )
    db_manager.insert_problem(problem_data=merge_v2_payload(data=transformed))

    # Step 6: Verify against the v2 shape — hub (name, type) + the
    # self-contained cvrp_problems row. v2 has no `vehicles` column, so it
    # is intentionally not asserted (Cordeau's m lives only in the COMMENT).
    row = db_manager.load(name=filename, type="CVRP")
    assert row["name"] == filename  # hub
    assert row["type"] == "CVRP"  # hub
    assert row["has_solution"] is False  # hub satellite flag
    assert row["dimension"] == problem.dimension  # cvrp_problems
    assert row["capacity"] == max(c.max_load for c in problem.depot_constraints)
    assert len(row["demands"]) == problem.dimension
    assert row["depots"] == transformed["depots"]
    assert len(row["depots"]) == problem.num_depots

  def test_json_output_p01(
    self,
    cordeau_base_path: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
  ) -> None:
    """Test JSON output generation (v2 flattened shape)."""
    filename = "p01"

    # Parse and convert
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_base_path / filename)
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing parser
    parsed_data: dict[str, Any] = format_parser.parse_file(file_path=output_path)

    # Transform
    transformer = DataTransformer(logger=logging.getLogger(__name__))
    transformed: dict[str, Any] = transformer.transform_problem(problem_data=parsed_data)

    # Write JSON. JSONWriter.organize_by_type defaults to True, so the file
    # lands under a type subdirectory: <out>/cvrp/p01.json.
    json_output_dir: Path = temp_converted_dir / "json"
    json_output_dir.mkdir()
    json_writer = JSONWriter(output_dir=json_output_dir, logger=logging.getLogger(__name__))
    json_writer.write_problem(data=transformed)

    # Verify JSON file created under the type subdirectory
    json_file: Path = json_output_dir / "cvrp" / f"{filename}.json"
    assert json_file.exists()

    # Verify JSON content against the v2 flattened shape: metadata sits
    # under the 'problem' key, with nodes/tours/metadata as siblings.

    with open(file=json_file) as f:
      json_data = json.load(fp=f)

    assert json_data["problem"]["name"] == filename
    assert json_data["problem"]["type"] == "CVRP"
    assert json_data["problem"]["dimension"] == problem.dimension
    assert json_data["problem"]["capacity"] == max(c.max_load for c in problem.depot_constraints)
