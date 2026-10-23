"""Integration tests for the converter pipeline components.

WHAT: Compose the scanner, parser/transformer, JSON writer and database writer.
WHY: Each component has unit tests; these cases prove the v2 array-column
     payload survives every component boundary without losing values.
EXPECTED: The payload keeps its declared dimension and values through JSON and
     DuckDB, and the removed v1 ``nodes`` key never reappears.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from converter.api import merge_v2_payload
from converter.core.scanner import FileScanner
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult


@pytest.fixture
def transformed_gr17(tsp_dir: Path) -> dict[str, Any]:
  """Parse and transform gr17.tsp (17 nodes, EXPLICIT LOWER_DIAG_ROW)."""
  parsed: ParseResult = FormatParser().parse_file(str(tsp_dir / "gr17.tsp"))
  return DataTransformer().transform_problem(parsed)


class TestScannerIntegration:
  """FileScanner behavior against the real corpus directory."""

  @pytest.mark.requires_dataset
  def test_scanner_finds_test_files(self, tsp_dir: Path) -> None:
    """WHAT: Scan the TSP directory. WHY: discovery must see corpus files.
    EXPECTED: gr17.tsp is found and every match is a .tsp file.
    """
    files: list[str] = FileScanner().scan_files(str(tsp_dir), patterns=["*.tsp"])

    assert files, "Scanner should find at least one .tsp file"
    assert "gr17.tsp" in {Path(file_path).name for file_path in files}
    assert all(Path(file_path).suffix == ".tsp" for file_path in files)

  @pytest.mark.requires_dataset
  def test_scanner_batching_integration(self, tsp_dir: Path) -> None:
    """WHAT: Scan with batch_size=2. WHY: batch consumers need metadata intact.
    EXPECTED: Non-empty batches whose entries carry path, name and type.
    """
    batches: list[list[dict[str, Any]]] = list(
      FileScanner(batch_size=2).scan_directory(str(tsp_dir), patterns=["*.tsp"])
    )

    assert batches, "Should produce at least one batch"
    for batch in batches:
      for file_info in batch:
        assert {"file_path", "file_name", "problem_type"} <= set(file_info)
        assert file_info["problem_type"] == "TSP"


class TestParserTransformerIntegration:
  """Parser output consumed by the v2 transformer."""

  @pytest.mark.requires_dataset
  def test_parse_and_transform_gr17(self, transformed_gr17: dict[str, Any]) -> None:
    """WHAT: Parse then transform gr17.tsp. WHY: v2 emits array columns.
    EXPECTED: No ``nodes`` key; a 17x17 matrix with the file's declared values.
    """
    assert "nodes" not in transformed_gr17, "v1 nodes key must not return"

    problem: dict[str, Any] = transformed_gr17["problem_data"]
    assert problem["name"] == "gr17"
    assert problem["dimension"] == 17

    matrix: list[list[int]] = transformed_gr17["edge_weight_matrix"]
    assert len(matrix) == 17
    assert all(len(row) == 17 for row in matrix)
    assert matrix[0][0] == 0
    assert matrix[0][1] == 633
    assert matrix[1][0] == 633


class TestJSONWriterIntegration:
  """Transformed payload consumed by the JSON writer."""

  @pytest.mark.requires_dataset
  def test_write_transformed_data_to_json(self, tsp_dir: Path, tmp_path: Path) -> None:
    """WHAT: Write berlin52 to JSON. WHY: JSON must match the v2 shape.
    EXPECTED: Exact top-level key set, 52 coordinates preserved verbatim.
    """
    parsed: ParseResult = FormatParser().parse_file(str(tsp_dir / "berlin52.tsp"))
    transformed: dict[str, Any] = DataTransformer().transform_problem(parsed)

    writer = JSONWriter(output_dir=str(tmp_path))
    json_path: str = writer.write_problem(transformed, organize_by_type=False)

    assert Path(json_path).exists()
    json_data: dict[str, Any] = json.loads(Path(json_path).read_text(encoding="utf-8"))

    assert set(json_data) == {
      "problem",
      "coords",
      "demands",
      "depots",
      "display_coords",
      "edges",
      "fixed_edges",
      "metadata",
      "tours",
    }
    assert json_data["problem"]["name"] == "berlin52"
    assert json_data["problem"]["type"] == "TSP"
    assert json_data["problem"]["dimension"] == 52
    assert len(json_data["coords"]) == 52
    assert json_data["coords"] == transformed["coords"]
    assert json_data["metadata"]["file_name"] == "berlin52.tsp"

  @pytest.mark.requires_dataset
  def test_batch_write_multiple_files(self, tsp_dir: Path, tmp_path: Path) -> None:
    """WHAT: Write the first three TSP files. WHY: batch output must not drop.
    EXPECTED: One existing JSON file per input file, no swallowed errors.
    """
    files: list[str] = FileScanner().scan_files(str(tsp_dir), patterns=["*.tsp"])[:3]
    assert files, "Corpus should contain .tsp files"

    writer = JSONWriter(output_dir=str(tmp_path))
    for file_path in files:
      parsed: ParseResult = FormatParser().parse_file(file_path)
      transformed: dict[str, Any] = DataTransformer().transform_problem(parsed)
      json_path: str = writer.write_problem(transformed, organize_by_type=True)
      assert Path(json_path).exists()

    written: list[Path] = sorted(tmp_path.rglob("*.json"))
    assert len(written) == len(files)


class TestDatabaseIntegration:
  """Transformed payload consumed by the v2 database writer."""

  @pytest.mark.requires_dataset
  @pytest.mark.database
  def test_write_transformed_data_to_database(self, transformed_gr17: dict[str, Any], tmp_path: Path) -> None:
    """WHAT: Insert the merged v2 payload. WHY: DB reads must see the same values.
    EXPECTED: Loaded row matches the transformed problem; one problem in stats.
    """
    db_path: Path = tmp_path / "test.duckdb"
    db = DatabaseManager(str(db_path))

    problem_id: int = db.insert_problem(merge_v2_payload(transformed_gr17))
    assert problem_id > 0

    row: dict[str, Any] = db.load(name="gr17", type="TSP")
    assert row["name"] == "gr17"
    assert row["type"] == "TSP"
    assert row["dimension"] == 17
    assert row["edge_weight_type"] == "EXPLICIT"

    stats: dict[str, Any] = db.get_problem_stats()
    assert stats["total_problems"] == 1
