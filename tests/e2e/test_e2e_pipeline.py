"""End-to-end test: scan -> parse -> transform -> JSON + DuckDB.

WHAT: Run the production chain over a controlled two-file directory.
WHY: Unit and integration tests cover each edge; only this test proves the
     whole chain works together on the v2 payload.
EXPECTED: Two problems persisted in DuckDB and two JSON files on disk, with
     matching names, dimensions and coordinate counts.
"""

import json
import shutil
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


@pytest.mark.requires_dataset
@pytest.mark.database
def test_full_pipeline_scan_parse_transform_write(tmp_path: Path, test_data_dir: Path) -> None:
  """WHAT: Copy two corpus files, then run scanner -> parser -> transformer ->
  JSON writer -> database. WHY: the v2 payload must survive the whole chain.
  EXPECTED: One JSON file and one database row per input, same values.
  """
  source_dir: Path = test_data_dir / "tsp"
  input_dir: Path = tmp_path / "input"
  input_dir.mkdir()
  for name in ("gr17.tsp", "berlin52.tsp"):
    shutil.copy(source_dir / name, input_dir / name)

  json_dir: Path = tmp_path / "json"
  json_dir.mkdir()
  db_path: Path = tmp_path / "pipeline.duckdb"

  scanner = FileScanner()
  parser = FormatParser()
  transformer = DataTransformer()
  writer = JSONWriter(output_dir=str(json_dir))
  db = DatabaseManager(str(db_path))

  files: list[str] = scanner.scan_files(str(input_dir), patterns=["*.tsp"])
  assert len(files) == 2

  for file_path in files:
    parsed: ParseResult = parser.parse_file(file_path)
    transformed: dict[str, Any] = transformer.transform_problem(parsed)
    json_path: str = writer.write_problem(transformed, organize_by_type=True)
    assert Path(json_path).exists()
    db.insert_problem(merge_v2_payload(transformed))

  stats: dict[str, Any] = db.get_problem_stats()
  assert stats["total_problems"] == 2
  assert {entry["type"] for entry in stats["by_type"]} == {"TSP"}

  json_files: list[Path] = sorted(json_dir.rglob("*.json"))
  assert [path.name for path in json_files] == ["berlin52.json", "gr17.json"]

  berlin: dict[str, Any] = json.loads(
    (json_dir / "tsp" / "berlin52.json").read_text(encoding="utf-8")
  )
  assert berlin["problem"]["name"] == "berlin52"
  assert berlin["problem"]["dimension"] == 52
  assert len(berlin["coords"]) == 52

  row: dict[str, Any] = db.load(name="berlin52", type="TSP")
  assert row["dimension"] == 52
  assert row["edge_weight_type"] == "EUC_2D"
