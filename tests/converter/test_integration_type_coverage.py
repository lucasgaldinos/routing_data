"""Storability of every problem type the corpus declares.

WHAT
----
Drives one real corpus file per schema-admitted type through the worker and the
batch insert, then reads the rows back and compares values. Also pins what
happens to declared types the schema cannot hold: ``TOUR`` (refused outright)
and ``MDVRP`` (stored as ``CVRP``, identity lost).

WHY
---
The corpus declares ``TSP`` 226 times, ``TOUR`` 82, ``SOP`` 82, ``CVRP`` 56,
``ATSP`` 38, ``HCP`` 18. Because the batch is a single transaction, one refused
file removes every other problem from the run (CV9). "Which types can we store,
and what exactly survives" has to be an explicit, tested statement.

EXPECTED
--------
- Each admitted type inserts and reads back its own type, dimension and payload.
- ``TOUR`` is refused by ``_normalize_type_for_schema`` today; the target model
  (tour files are solutions of their instance) is tracked as CV9 and asserted as
  an xfail so an accidental fix turns the suite red.
- ``MDVRP`` keeps its identity in the hub in the target model; today it collapses
  to ``CVRP``, also asserted as an xfail.
"""

from pathlib import Path

import duckdb
import pytest

from converter.database.operations import DatabaseManager
from converter.utils.worker_functions import process_file_for_parallel

#: ``(declared type, corpus file, owned table, column compared to the worker payload)``.
#: Every entry compares a real payload array against the stored column, so a parser
#: regression (dropped demands, transposed adjacency) fails here instead of passing.
ADMITTED_SAMPLES: tuple[tuple[str, str, str, str], ...] = (
  ("TSP", "problems/tsp/att48.tsp", "tsp_problems", "coords"),
  ("CVRP", "problems/vrp/att48.vrp", "cvrp_problems", "demands"),
  ("HCP", "problems/hcp/alb1000.hcp", "hcp_problems", "adjacency"),
  ("SOP", "problems/sop/ESC07.sop", "sop_problems", "fixed_edges"),
)

#: Column name -> worker payload key that carries it.
PAYLOAD_KEY: dict[str, str] = {
  "coords": "coords",
  "demands": "demands",
  "adjacency": "edges",
  "fixed_edges": "fixed_edges",
}

#: Type table that owns each admitted type (mirrors ``_TYPE_TABLES``).
TYPE_TABLES: dict[str, str] = {
  "TSP": "tsp_problems",
  "ATSP": "atsp_problems",
  "CVRP": "cvrp_problems",
  "HCP": "hcp_problems",
  "SOP": "sop_problems",
}


def _worker_payload(datasets_root: Path, relative_path: str, tmp_path: Path) -> dict[str, object]:
  """Run the real worker for one corpus file and fail loudly if it did not parse."""
  payload = process_file_for_parallel(str(datasets_root / relative_path), output_dir=str(tmp_path))
  assert payload.get("success") is True, f"worker rejected {relative_path}: {payload.get('error')}"
  return payload


@pytest.mark.requires_dataset
@pytest.mark.parametrize(("problem_type", "relative_path", "table", "column"), ADMITTED_SAMPLES)
@pytest.mark.database
def test_admitted_type_round_trips(
  datasets_raw_dir: Path,
  tmp_path: Path,
  problem_type: str,
  relative_path: str,
  table: str,
  column: str,
) -> None:
  """WHAT: worker -> batch insert -> read back, for each admitted type.

  WHY: a type that parses but cannot be stored is a silent hole in the dataset, and
  a stored-but-truncated payload is worse than a missing row. Comparing the actual
  array column against the worker's own array is the only assertion that catches a
  parser regression (dropped demands, transposed adjacency, empty coords).

  EXPECTED: hub type, dimension, and the type table's array column all equal the
  worker payload; ``total_failed == 0``.
  """
  payload = _worker_payload(datasets_raw_dir, relative_path, tmp_path)
  problem_data = payload["problem_data"]
  assert isinstance(problem_data, dict)
  dimension = problem_data["dimension"]
  name = problem_data["name"]
  expected_array = payload[PAYLOAD_KEY[column]]
  # ``fixed_edges`` is genuinely empty for every SOP file in the corpus (41 of 41 omit
  # FIXED_EDGES_SECTION), so only require a non-empty array for the data-bearing columns.
  if column != "fixed_edges":
    assert expected_array, f"worker produced no {PAYLOAD_KEY[column]} for {relative_path}"

  db_path = tmp_path / f"{problem_type.lower()}.duckdb"
  manager = DatabaseManager(db_path=str(db_path))
  result = manager.insert_problems_batch([payload])

  assert result["total_inserted"] == 1, f"{problem_type} was not stored: {result['failed']}"
  assert result["total_failed"] == 0
  assert table == TYPE_TABLES[problem_type]
  with duckdb.connect(str(db_path), read_only=True) as conn:
    hub = conn.execute("SELECT name, type FROM problems").fetchall()
    # Names come from the closed constants above, never from input.
    stored = conn.execute(f"SELECT dimension, {column} FROM {table}").fetchall()  # noqa: S608
  assert hub == [(name, problem_type)]
  assert stored == [(dimension, expected_array)], f"{column} lost or altered for {problem_type}"


@pytest.mark.requires_dataset
@pytest.mark.database
def test_explicit_atsp_matrix_round_trips(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: the satellite row for an EXPLICIT matrix problem (``br17.atsp``).

  WHY: the matrix lives in ``edge_weight_matrices``, not on the type table, so the
  other round-trip test cannot see it. ``matrix`` is ``INTEGER[][]`` while the
  parser produces ``int | float``: only a value comparison reveals truncation.

  EXPECTED: a matrix row with the declared format and every cell equal to the
  parsed matrix cell.
  """
  payload = _worker_payload(datasets_raw_dir, "problems/atsp/br17.atsp", tmp_path)
  edge_weight_data = payload["edge_weight_data"]
  assert isinstance(edge_weight_data, dict)
  expected_matrix = edge_weight_data["matrix"]

  db_path = tmp_path / "atsp_matrix.duckdb"
  result = DatabaseManager(db_path=str(db_path)).insert_problems_batch([payload])
  assert result["total_inserted"] == 1, result["failed"]

  with duckdb.connect(str(db_path), read_only=True) as conn:
    stored = conn.execute("SELECT matrix_format, matrix FROM edge_weight_matrices").fetchall()
  assert len(stored) == 1
  matrix_format, stored_matrix = stored[0]
  assert matrix_format == "FULL_MATRIX"
  assert stored_matrix == expected_matrix, "matrix cells changed between parse and storage"


@pytest.mark.requires_dataset
@pytest.mark.database
def test_tour_file_is_refused_by_the_write_path(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: a ``TYPE : TOUR`` file, characterisation of current behaviour.

  WHY: 82 corpus files are ``*.opt.tour``. The schema has no home for them, and
  the refusal is what destroys a mixed batch (train of CV9 item 1).

  EXPECTED: the worker parses it (``type == 'TOUR'``) and the insert reports a
  ``DatabaseError`` instead of storing it. Target behaviour, pending the CV9
  modelling decision, is asserted in the xfail below.
  """
  payload = _worker_payload(datasets_raw_dir, "zips/all_problems/tour/alb1000.opt.tour", tmp_path)
  problem_data = payload["problem_data"]
  assert isinstance(problem_data, dict)
  assert problem_data["type"] == "TOUR"

  manager = DatabaseManager(db_path=str(tmp_path / "tour.duckdb"))
  result = manager.insert_problems_batch([payload])

  assert result["total_inserted"] == 0
  assert result["total_failed"] == 1
  assert "Unsupported problem type 'TOUR'" in result["failed"][0]["error"]


@pytest.mark.requires_dataset
@pytest.mark.xfail(
  strict=True,
  reason="CV9: a tour file is the solution of its instance; the schema has no solutions table yet.",
)
@pytest.mark.database
def test_tour_file_should_be_storable(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: target behaviour for ``*.opt.tour``.

  WHY: TSPLIB95 ships tours as ``<instance>.opt.tour`` (``docs/reference/tsplib95_format.md``
  §1.2.7 and the instance catalogue), and ``DataTransformer.find_solution_file``
  already resolves them that way — the database is the only layer that disagrees.

  EXPECTED: the tour is stored, not rejected.
  """
  payload = _worker_payload(datasets_raw_dir, "zips/all_problems/tour/alb1000.opt.tour", tmp_path)
  manager = DatabaseManager(db_path=str(tmp_path / "tour_target.duckdb"))
  result = manager.insert_problems_batch([payload])
  assert result["total_inserted"] == 1, result["failed"]


@pytest.mark.database
def test_extended_type_keeps_its_identity(tmp_path: Path) -> None:
  """WHAT: hub ``type`` for an extended LKH-3 problem.

  WHY: an MDVRP stored as ``CVRP`` is indistinguishable from a real CVRP, and its
  per-depot capacities/durations have no column to land in.

  EXPECTED: the declared type survives into the hub.
  """
  payload: dict[str, object] = {
    "success": True,
    "file_path": "synthetic/mdvrp-probe.vrp",
    "problem_data": {
      "name": "mdvrp-probe",
      "type": "MDVRP",
      "dimension": 4,
      "capacity": 80,
      "edge_weight_type": "EUC_2D",
      "vehicles": 4,
    },
    "transformed_data": {
      "problem_data": {
        "name": "mdvrp-probe",
        "type": "MDVRP",
        "dimension": 4,
        "capacity": 80,
        "edge_weight_type": "EUC_2D",
      },
      "coords": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
      "demands": [0, 0, 1, 1],
      "depots": [0, 1],
    },
    "coords": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
    "display_coords": [],
    "demands": [0, 0, 1, 1],
    "depots": [0, 1],
    "metadata": {},
    "edge_weight_data": None,
    "edges": None,
    "fixed_edges": None,
  }
  manager = DatabaseManager(db_path=str(tmp_path / "mdvrp.duckdb"))
  result = manager.insert_problems_batch([payload])
  assert result["total_inserted"] == 1, result["failed"]
  with duckdb.connect(str(tmp_path / "mdvrp.duckdb"), read_only=True) as conn:
    stored = conn.execute("SELECT type FROM problems WHERE name = 'mdvrp-probe'").fetchone()
  assert stored == ("MDVRP",)
