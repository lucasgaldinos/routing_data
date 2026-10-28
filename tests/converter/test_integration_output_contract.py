"""What the JSON and parquet artifacts actually contain.

WHAT
----
Pins the JSON document shape for a coordinate instance and for an EXPLICIT
(matrix) instance, and pins the parquet export as one file per database table
with row counts equal to the table contents.

WHY
---
These are the two artifacts users take away. The parquet set is produced by
``COPY <table> TO … (FORMAT PARQUET)``, so it inherits every schema decision; the
JSON document is produced by ``DataTransformer.to_json_format``, which copies a
fixed key list. Recent measurement (CV9) showed the JSON path drops
``edge_weight_matrix`` entirely, making an EXPLICIT instance unusable in JSON.

EXPECTED
--------
- JSON top-level keys are exactly the documented set, with real values behind
  them (dimension matches the coordinate count).
- Parquet exports all eight tables, and each file's row count equals the table's.
- The EXPLICIT JSON case is an ``xfail(strict=True)``: the matrix must be present
  in the target model, and an accidental fix turns the suite red.
"""

import json
from pathlib import Path
from typing import cast

import duckdb
import pytest

from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from converter.output.parquet_writer import ParquetWriter
from converter.utils.worker_functions import process_file_for_parallel

#: Key set produced by ``to_json_format`` for every problem.
EXPECTED_JSON_KEYS: frozenset[str] = frozenset(
  {"problem", "tours", "metadata", "coords", "display_coords", "demands", "depots", "edges", "fixed_edges"}
)

#: Tables the parquet exporter publishes, one file each.
EXPECTED_PARQUET_TABLES: frozenset[str] = frozenset(
  {
    "problems",
    "tsp_problems",
    "atsp_problems",
    "cvrp_problems",
    "hcp_problems",
    "sop_problems",
    "edge_weight_matrices",
    "solutions",
    "file_tracking",
  }
)


def _write_json(payload: dict[str, object], output_dir: Path) -> dict[str, object]:
  """Write the worker payload as JSON and return the parsed document."""
  transformed = payload["transformed_data"]
  assert isinstance(transformed, dict)
  path = JSONWriter(output_dir=output_dir).write_problem(transformed)
  # ``json.loads`` is typed ``Any``; the document written by ``JSONWriter`` is a JSON object.
  return cast("dict[str, object]", json.loads(Path(path).read_text(encoding="utf-8")))


@pytest.mark.requires_dataset
@pytest.mark.database
def test_json_shape_for_coordinate_instance(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: the JSON document for an EUC_2D TSP instance (``att48.tsp``).

  WHY: consumers query these keys directly; a key rename or drop is a breaking
  change, and the values must line up with the header.

  EXPECTED: exactly ``EXPECTED_JSON_KEYS``, with ``problem.dimension == 48`` and
  48 coordinate rows.
  """
  payload = process_file_for_parallel(str(datasets_raw_dir / "problems/tsp/att48.tsp"), output_dir=str(tmp_path))
  assert payload.get("success") is True

  document = _write_json(payload, tmp_path / "json_tsp")

  assert set(document) == EXPECTED_JSON_KEYS
  problem = document["problem"]
  assert isinstance(problem, dict)
  assert problem["name"] == "att48"
  assert problem["type"] == "TSP"
  assert problem["dimension"] == 48
  coords = document["coords"]
  assert isinstance(coords, list)
  assert len(coords) == 48
  assert all(len(row) == 2 and all(isinstance(value, float) for value in row) for row in coords)


@pytest.mark.requires_dataset
@pytest.mark.database
def test_json_carries_the_explicit_matrix(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: JSON document for an EXPLICIT instance (``br17.atsp``).

  WHY: without the matrix an EXPLICIT problem's JSON holds no distances at all;
  the parsed payload has it, the writer drops it.

  EXPECTED: the document carries the 17x17 matrix that the transformer produced.
  """
  payload = process_file_for_parallel(str(datasets_raw_dir / "problems/atsp/br17.atsp"), output_dir=str(tmp_path))
  assert payload.get("success") is True
  transformed = payload["transformed_data"]
  assert isinstance(transformed, dict)
  assert "edge_weight_matrix" in transformed

  document = _write_json(payload, tmp_path / "json_atsp")

  assert "edge_weight_matrix" in document


@pytest.mark.requires_dataset
@pytest.mark.database
def test_parquet_export_is_one_file_per_table(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: the parquet export of a database holding two problems.

  WHY: the parquet artifact set is the schema, one file per table; a missing or
  extra file breaks every downstream loader.

  EXPECTED: exactly ``EXPECTED_PARQUET_TABLES`` files, and each file's row count
  equals its table's row count (so no table is exported empty by accident).
  """
  db_path = tmp_path / "export.duckdb"
  manager = DatabaseManager(db_path=str(db_path))
  payloads = [
    process_file_for_parallel(str(datasets_raw_dir / relative), output_dir=str(tmp_path))
    for relative in ("problems/tsp/att48.tsp", "problems/atsp/br17.atsp")
  ]
  assert all(payload.get("success") is True for payload in payloads)
  insert = manager.insert_problems_batch(payloads)
  assert insert["total_inserted"] == 2, insert["failed"]

  files = ParquetWriter(output_dir=str(tmp_path / "parquet")).export_from_database(db_path=str(db_path))

  assert set(files) == EXPECTED_PARQUET_TABLES
  with duckdb.connect(str(db_path), read_only=True) as conn:
    for table, parquet_path in files.items():
      # Table name comes from the closed EXPECTED_PARQUET_TABLES set; the path is a tmp_path artifact.
      expected = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
      exported = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()  # noqa: S608
      assert exported == expected, f"{table}: exported {exported} rows, table holds {expected}"
  with duckdb.connect(str(db_path), read_only=True) as conn:
    assert conn.execute("SELECT COUNT(*) FROM problems").fetchone() == (2,)
    assert conn.execute("SELECT COUNT(*) FROM edge_weight_matrices").fetchone() == (1,)


@pytest.mark.requires_dataset
@pytest.mark.database
def test_json_and_database_agree_on_identity(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: the same payload through both artifacts.

  WHY: JSON and DuckDB are two views of one problem; if they disagree on name or
  dimension, a user joining them silently mismatches rows.

  EXPECTED: identical name and dimension on both sides.
  """
  payload = process_file_for_parallel(str(datasets_raw_dir / "problems/tsp/att48.tsp"), output_dir=str(tmp_path))
  assert payload.get("success") is True

  db_path = tmp_path / "parity.duckdb"
  DatabaseManager(db_path=str(db_path)).insert_problems_batch([payload])
  document = _write_json(payload, tmp_path / "json_parity")
  problem = document["problem"]
  assert isinstance(problem, dict)

  with duckdb.connect(str(db_path), read_only=True) as conn:
    row = conn.execute(
      "SELECT p.name, t.dimension FROM problems p JOIN tsp_problems t ON t.problem_id = p.id"
    ).fetchone()

  assert row == (problem["name"], problem["dimension"])
