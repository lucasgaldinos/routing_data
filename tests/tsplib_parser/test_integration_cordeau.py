"""Integration tests for the Cordeau MDVRP adapter.

WHAT: Drive the Cordeau parse -> convert -> parse -> transform -> DB/JSON chain.
WHY: The adapter is only useful if the rest of the pipeline accepts its output.
EXPECTED: Converted problems parse, transform, persist, and serialize as v2 data.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest

from converter.api import merge_v2_payload
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from tsplib_parser.cordeau import CordeauConverter, CordeauParser
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from pathlib import Path

  from tsplib_parser.cordeau.cordeau_types import CordeauProblem
  from tsplib_parser.types import ParseResult, ProblemData

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
def format_parser() -> FormatParser:
  """Create TSPLIB95 format parser instance."""
  return FormatParser(logger=logging.getLogger(__name__))


@pytest.fixture
def temp_converted_dir(tmp_path: Path) -> Path:
  """Create temporary directory for converted files."""
  converted_dir: Path = tmp_path / "converted"
  converted_dir.mkdir()
  return converted_dir


class TestCordeauIntegration:
  """Test integration with existing pipeline."""

  @pytest.mark.parametrize(argnames="filename", argvalues=TEST_FILES)
  @pytest.mark.requires_dataset
  def test_tsplib95_parser_accepts_converted(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test that converted TSPLIB95 can be parsed by existing parser."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / filename)

    # Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing TSPLIB95 parser
    parsed_data: ParseResult = format_parser.parse_file(file_path=output_path)

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
  @pytest.mark.requires_dataset
  def test_parse_result_matches_converted_file(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Verify ``to_parse_result()`` agrees with the LKH file the converter writes."""
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / filename)
    expected: ParseResult = problem.to_parse_result(file_path=cordeau_mdvrp_dir / filename)

    output_path: Path = temp_converted_dir / f"{filename}.lkh.vrp"
    cordeau_converter.to_tsplib(problem=problem, output_path=output_path, as_lkh=True)
    reparsed: ParseResult = format_parser.parse_file(file_path=output_path)

    # 0-based arrays must agree element by element (depots first, as the file orders them)
    assert expected["coords"] == reparsed["coords"]
    assert expected["demands"] == reparsed["demands"]
    assert expected["depots"] == reparsed["depots"]

    # Data-carrying fields must agree. ``comment`` is generated prose, not data.
    expected_pd: ProblemData = expected["problem_data"]
    reparsed_pd: ProblemData = reparsed["problem_data"]
    assert reparsed_pd["name"] == expected_pd["name"]
    assert reparsed_pd["type"] == expected_pd["type"]
    assert reparsed_pd["dimension"] == expected_pd["dimension"]
    assert reparsed_pd["capacity"] == expected_pd["capacity"]
    assert reparsed_pd["edge_weight_type"] == expected_pd["edge_weight_type"]
    assert reparsed_pd.get("vehicles") == expected_pd.get("vehicles")
    assert reparsed_pd.get("num_depots") == expected_pd.get("num_depots")
    assert reparsed_pd.get("max_distance") == expected_pd.get("max_distance")
    assert reparsed_pd.get("depot_capacities") == expected_pd.get("depot_capacities")
    assert reparsed_pd.get("depot_durations") == expected_pd.get("depot_durations")
    assert reparsed_pd.get("time_windows") == expected_pd.get("time_windows")
    assert reparsed_pd.get("service_times") == expected_pd.get("service_times")

  @pytest.mark.parametrize("filename", TEST_FILES)
  @pytest.mark.requires_dataset
  def test_transformer_processes_converted(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
    filename: str,
  ) -> None:
    """Test that transformer can process converted problem."""
    # Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(cordeau_mdvrp_dir / filename)

    # Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing TSPLIB95 parser
    parsed_data: ParseResult = format_parser.parse_file(output_path)

    # Transform
    transformer = DataTransformer(logger=logging.getLogger(__name__))
    transformed: dict[str, Any] = transformer.transform_problem(parsed_data)

    # Validate transformation
    assert transformed is not None
    assert "problem_data" in transformed
    assert "coords" in transformed
    assert len(transformed["coords"]) == problem.dimension
    assert transformed["problem_data"]["name"] == filename
    assert transformed["problem_data"]["type"] == "CVRP"
    assert transformed["problem_data"]["dimension"] == problem.dimension

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_full_pipeline_p01(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
  ) -> None:
    """Test full pipeline: Parse → Convert → Parse → Transform → DB (v2)."""
    filename = "p01"

    # Step 1: Parse Cordeau file
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / filename)

    # Step 2: Convert to TSPLIB95 file
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Step 3: Parse with existing TSPLIB95 parser
    parsed_data: ParseResult = format_parser.parse_file(output_path)

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

  @pytest.mark.requires_dataset
  def test_json_output_p01(
    self,
    cordeau_mdvrp_dir: Path,
    cordeau_parser: CordeauParser,
    cordeau_converter: CordeauConverter,
    format_parser: FormatParser,
    temp_converted_dir: Path,
  ) -> None:
    """Test JSON output generation (v2 flattened shape)."""
    filename = "p01"

    # Parse and convert
    problem: CordeauProblem = cordeau_parser.parse_file(file_path=cordeau_mdvrp_dir / filename)
    output_path: Path = temp_converted_dir / f"{filename}.vrp"
    cordeau_converter.to_tsplib95(problem, output_path=output_path)

    # Parse with existing parser
    parsed_data: ParseResult = format_parser.parse_file(file_path=output_path)

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
