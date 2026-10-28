"""Schema contract for the v2 DuckDB topology.

WHAT
----
Pins the tables, columns and column types the converter writes into, the
``problems.type`` CHECK constraint, and the ``UNIQUE (name, type)`` key.

WHY
---
Three consumers depend on this shape: ``analyze`` / ``analyze --type``, the
parquet export (one ``COPY`` per table, so the parquet artifact set *is* the
table set), and every downstream query. A moved column or a widened type is a
breaking change to what users download, so the schema may only change together
with this snapshot.

EXPECTED
--------
- Exactly nine tables, with the documented columns in ordinal order.
- The CHECK admits the five v2 types and refuses ``TOUR`` and the extended
  LKH-3 types (evidence: CV9 in ``src/converter/TODO.md``).
- The hub refuses a duplicate ``(name, type)`` pair.
- The ``solutions`` vocabulary CHECKs agree with ``converter.types`` — the
  single place those values are written down (CV12).
"""

import re
from pathlib import Path

import duckdb
import pytest

from converter.database.operations import DatabaseManager
from converter.types import SOLUTION_KINDS, SOLUTION_QUALITIES

#: ``(column_name, data_type, is_nullable)`` per table, in ordinal order. Changing
#: a row here is a schema change, and a schema change is a change to the parquet
#: contract. Nullability is part of the contract: relaxing ``NOT NULL`` on
#: ``demands``/``depots``/``adjacency`` would let empty payloads through silently.
EXPECTED_SCHEMA: dict[str, list[tuple[str, str, str]]] = {
  "problems": [
    ("id", "INTEGER", "NO"),
    ("name", "VARCHAR", "NO"),
    ("type", "VARCHAR", "NO"),
    ("has_solution", "BOOLEAN", "NO"),
    ("created_at", "TIMESTAMP", "YES"),
    ("updated_at", "TIMESTAMP", "YES"),
  ],
  "tsp_problems": [
    ("problem_id", "INTEGER", "NO"),
    ("dimension", "INTEGER", "NO"),
    ("comment", "VARCHAR", "YES"),
    ("edge_weight_type", "VARCHAR", "NO"),
    ("edge_weight_format", "VARCHAR", "YES"),
    ("tsplib_name", "VARCHAR", "YES"),
    ("coords", "DOUBLE[][]", "YES"),
    ("display_coords", "DOUBLE[][]", "YES"),
  ],
  "atsp_problems": [
    ("problem_id", "INTEGER", "NO"),
    ("dimension", "INTEGER", "NO"),
    ("comment", "VARCHAR", "YES"),
    ("tsplib_name", "VARCHAR", "YES"),
  ],
  "cvrp_problems": [
    ("problem_id", "INTEGER", "NO"),
    ("dimension", "INTEGER", "NO"),
    ("capacity", "INTEGER", "NO"),
    ("comment", "VARCHAR", "YES"),
    ("edge_weight_type", "VARCHAR", "NO"),
    ("edge_weight_format", "VARCHAR", "YES"),
    ("tsplib_name", "VARCHAR", "YES"),
    ("coords", "DOUBLE[][]", "YES"),
    ("demands", "INTEGER[]", "NO"),
    ("depots", "INTEGER[]", "NO"),
  ],
  "hcp_problems": [
    ("problem_id", "INTEGER", "NO"),
    ("dimension", "INTEGER", "NO"),
    ("adjacency", "INTEGER[][]", "NO"),
    ("comment", "VARCHAR", "YES"),
    ("tsplib_name", "VARCHAR", "YES"),
  ],
  "sop_problems": [
    ("problem_id", "INTEGER", "NO"),
    ("dimension", "INTEGER", "NO"),
    ("fixed_edges", "INTEGER[][]", "YES"),
    ("comment", "VARCHAR", "YES"),
    ("tsplib_name", "VARCHAR", "YES"),
  ],
  "edge_weight_matrices": [
    ("problem_id", "INTEGER", "NO"),
    ("matrix_format", "VARCHAR", "NO"),
    ("is_symmetric", "BOOLEAN", "NO"),
    ("matrix", "INTEGER[][]", "NO"),
  ],
  "file_tracking": [
    ("id", "INTEGER", "NO"),
    ("file_path", "VARCHAR", "NO"),
    ("problem_id", "INTEGER", "YES"),
    ("checksum", "VARCHAR", "YES"),
    ("last_processed", "TIMESTAMP", "YES"),
    ("file_size", "BIGINT", "YES"),
  ],
  "solutions": [
    ("id", "INTEGER", "NO"),
    ("problem_id", "INTEGER", "YES"),
    ("kind", "VARCHAR", "NO"),
    ("quality", "VARCHAR", "NO"),
    ("source_file", "VARCHAR", "NO"),
    ("checksum", "VARCHAR", "YES"),
    ("cost", "DOUBLE", "YES"),
    ("routes", "INTEGER[][]", "NO"),
    ("created_at", "TIMESTAMP", "YES"),
  ],
}

#: Types the hub CHECK accepts (TSPLIB95 and TSPLIB-extended storable problem types).
SCHEMA_ADMITTED_TYPES: tuple[str, ...] = (
  "TSP",
  "ATSP",
  "CVRP",
  "HCP",
  "SOP",
  "MDVRP",
  "CVRPTW",
  "TSPTW",
  "PDPTW",
  "OVRP",
  "MTSP",
)

#: Types the parser or caller may declare but the schema refuses (solutions or unsupported types).
SCHEMA_REFUSED_TYPES: tuple[str, ...] = ("TOUR", "CTSP", "INVALID_TYPE", "UNKNOWN")


@pytest.fixture
def schema_db(tmp_path: Path) -> Path:
  """Create an empty v2 database and return its path."""
  path = tmp_path / "schema_contract.duckdb"
  DatabaseManager(db_path=str(path))
  return path


def _columns_by_table(db_path: Path) -> dict[str, list[tuple[str, str, str]]]:
  """Return ``{table: [(column, type, is_nullable), ...]}`` for the main schema."""
  with duckdb.connect(str(db_path), read_only=True) as conn:
    rows = conn.execute(
      "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns "
      "WHERE table_schema = 'main' ORDER BY table_name, ordinal_position"
    ).fetchall()
  grouped: dict[str, list[tuple[str, str, str]]] = {}
  for table, column, data_type, is_nullable in rows:
    grouped.setdefault(table, []).append((column, data_type, is_nullable))
  return grouped


@pytest.mark.database
def test_schema_topology_matches_contract(schema_db: Path) -> None:
  """WHAT: the full column list of every table, in ordinal order.

  WHY: the parquet export copies each table verbatim, so this snapshot is the
  published artifact contract.

  EXPECTED: exactly the eight tables below, column for column, type for type, and
  nullability for nullability.
  """
  assert _columns_by_table(schema_db) == EXPECTED_SCHEMA


@pytest.mark.parametrize("problem_type", SCHEMA_ADMITTED_TYPES)
@pytest.mark.database
def test_admitted_types_are_storable(schema_db: Path, problem_type: str) -> None:
  """WHAT: each admitted type passes the hub CHECK.

  WHY: these five are the types the write path can dispatch (``_TYPE_INSERTERS``).

  EXPECTED: the row lands and reads back with the same type.
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute("INSERT INTO problems (name, type) VALUES (?, ?)", [f"probe-{problem_type}", problem_type])
    stored = conn.execute("SELECT type FROM problems WHERE name = ?", [f"probe-{problem_type}"]).fetchone()
  assert stored == (problem_type,)


@pytest.mark.parametrize("problem_type", SCHEMA_REFUSED_TYPES)
@pytest.mark.database
def test_refused_types_violate_the_check(schema_db: Path, problem_type: str) -> None:
  """WHAT: declared-but-refused types hit the hub CHECK.

  WHY: ``TOUR`` (82 corpus files) and the LKH-3 extended types are declared by
  the parser but cannot be stored; today that failure aborts the whole batch.

  EXPECTED: ``ConstraintException``, naming the CHECK constraint.
  """
  with duckdb.connect(str(schema_db)) as conn, pytest.raises(duckdb.ConstraintException, match="CHECK"):
    conn.execute("INSERT INTO problems (name, type) VALUES (?, ?)", [f"probe-{problem_type}", problem_type])


@pytest.mark.database
def test_duplicate_name_and_type_is_refused(schema_db: Path) -> None:
  """WHAT: the hub key is ``(name, type)``, not ``name``.

  WHY: cross-type twins exist in the corpus (``att48`` as TSP and as CVRP), so the
  key must allow them while refusing true duplicates.

  EXPECTED: the second identical insert raises; the same name under a different
  type succeeds.
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute("INSERT INTO problems (name, type) VALUES ('att48', 'TSP')")
    conn.execute("INSERT INTO problems (name, type) VALUES ('att48', 'CVRP')")
    with pytest.raises(duckdb.ConstraintException):
      conn.execute("INSERT INTO problems (name, type) VALUES ('att48', 'TSP')")
    rows = conn.execute("SELECT type FROM problems WHERE name = 'att48' ORDER BY type").fetchall()
  assert rows == [("CVRP",), ("TSP",)]


@pytest.fixture
def seeded_problem(schema_db: Path) -> int:
  """Insert one problem and return its id, so solutions have an instance to link to."""
  with duckdb.connect(str(schema_db)) as conn:
    row = conn.execute("INSERT INTO problems (name, type) VALUES ('gr48', 'TSP') RETURNING id").fetchone()
  assert row is not None
  return int(row[0])


@pytest.mark.database
def test_tour_solution_links_to_its_instance(schema_db: Path, seeded_problem: int) -> None:
  """WHAT: a ``*.opt.tour`` stored against the instance it solves.

  WHY: this is the point of the satellite — today `has_solution` is never set and the
  82 tour files have nowhere to go. A tour is one route, stored in the same column as
  a multi-route ``.sol`` so both formats share one shape.

  EXPECTED: one row, `routes` of length 1, `quality = proven_optimal`, `cost` NULL
  (the file carries no cost).
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute(
      "INSERT INTO solutions (problem_id, kind, quality, source_file, routes) "
      "VALUES (?, 'OPT_TOUR', 'proven_optimal', 'gr48.opt.tour', [[0, 1, 2]])",
      [seeded_problem],
    )
    stored = conn.execute("SELECT problem_id, kind, quality, routes, cost FROM solutions").fetchall()

  assert stored == [(seeded_problem, "OPT_TOUR", "proven_optimal", [[0, 1, 2]], None)]


@pytest.mark.database
def test_multi_route_solution_keeps_every_route_in_order(schema_db: Path, seeded_problem: int) -> None:
  """WHAT: a CVRPLIB ``*.sol`` with several routes and a cost.

  WHY: route order and per-route node order are the solution's identity; a set-like
  storage would lose which vehicle serves which sequence.

  EXPECTED: all routes preserved in file order, `quality = best_known`, cost stored.
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute(
      "INSERT INTO solutions (problem_id, kind, quality, source_file, cost, routes) "
      "VALUES (?, 'SOL', 'best_known', 'Leuven2.sol', 477277.0, [[0, 5], [3, 1, 2], [4]])",
      [seeded_problem],
    )
    stored = conn.execute("SELECT routes, cost, quality FROM solutions").fetchall()

  assert stored == [([[0, 5], [3, 1, 2], [4]], 477277.0, "best_known")]


@pytest.mark.database
def test_solution_may_be_an_orphan(schema_db: Path) -> None:
  """WHAT: a solution whose instance is unknown.

  WHY: 356 of 390 `.sol` files point at instances that were never ingested, and an
  undecidable stem lands here too (CV10). The row must still be storable.

  EXPECTED: `problem_id` NULL, routes preserved.
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute(
      "INSERT INTO solutions (kind, quality, source_file, routes) "
      "VALUES ('SOL', 'best_known', 'Leuven2.sol', [[1, 2], [3]])"
    )
    stored = conn.execute("SELECT problem_id, routes FROM solutions").fetchall()

  assert stored == [(None, [[1, 2], [3]])]


@pytest.mark.database
def test_solution_requires_routes(schema_db: Path) -> None:
  """WHAT: `routes` is NOT NULL — a solution without a solution is refused.

  WHY: the column is the payload; an empty row would make every aggregate count a
  solution that does not exist. An *empty list* stays legal (a degenerate solution).

  EXPECTED: omitting `routes` raises, `routes = []` is accepted.
  """
  with duckdb.connect(str(schema_db)) as conn:
    with pytest.raises(duckdb.ConstraintException):
      conn.execute("INSERT INTO solutions (kind, quality, source_file) VALUES ('SOL', 'best_known', 'empty.sol')")
    conn.execute(
      "INSERT INTO solutions (kind, quality, source_file, routes) VALUES ('SOL', 'best_known', 'empty2.sol', [])"
    )
    assert conn.execute("SELECT COUNT(*) FROM solutions").fetchone() == (1,)


@pytest.mark.parametrize("kind", ["FOO", "tour", ""])
@pytest.mark.database
def test_solution_kind_is_constrained(schema_db: Path, kind: str) -> None:
  """WHAT: the `kind` domain (source format).

  WHY: `kind` is provenance; a free-form value makes every grouping unreliable.

  EXPECTED: anything outside ``SOLUTION_KINDS`` is refused.
  """
  assert kind not in SOLUTION_KINDS
  with duckdb.connect(str(schema_db)) as conn, pytest.raises(duckdb.ConstraintException):
    conn.execute(
      "INSERT INTO solutions (kind, quality, source_file, routes) VALUES (?, 'unknown', 'x.tour', [[0]])",
      [kind],
    )


@pytest.mark.parametrize("quality", ["optimal", "BEST_KNOWN", ""])
@pytest.mark.database
def test_solution_quality_is_constrained(schema_db: Path, quality: str) -> None:
  """WHAT: the `quality` domain.

  WHY: quality answers "can I treat this as ground truth?" — the distinction between a
  proven optimum and a best-known value (VRP-REP marks the former with '*') is lost if
  the column accepts arbitrary text.

  EXPECTED: anything outside ``SOLUTION_QUALITIES`` is refused, all three admitted.
  """
  assert quality not in SOLUTION_QUALITIES
  with duckdb.connect(str(schema_db)) as conn:
    with pytest.raises(duckdb.ConstraintException):
      conn.execute(
        "INSERT INTO solutions (kind, quality, source_file, routes) VALUES ('SOL', ?, 'q.sol', [[0]])",
        [quality],
      )
    for index, admitted in enumerate(SOLUTION_QUALITIES):
      conn.execute(
        "INSERT INTO solutions (kind, quality, source_file, routes) VALUES ('SOL', ?, ?, [[0]])",
        [admitted, f"ok{index}.sol"],
      )
    assert conn.execute("SELECT COUNT(*) FROM solutions").fetchone() == (3,)


@pytest.mark.database
def test_solution_source_file_is_unique(schema_db: Path) -> None:
  """WHAT: one row per solution file.

  WHY: the same file stored twice would double-count a solution in every aggregate.
  (Consequence, recorded as CV10: when a stem matches two instances the program
  cannot tell which one the solution belongs to, so the row is stored as an orphan
  rather than duplicated.)

  EXPECTED: the second insert of the same `source_file` raises and the count stays 1.
  """
  with duckdb.connect(str(schema_db)) as conn:
    conn.execute(
      "INSERT INTO solutions (kind, quality, source_file, routes) "
      "VALUES ('OPT_TOUR', 'proven_optimal', 'gr48.opt.tour', [[0]])"
    )
    with pytest.raises(duckdb.ConstraintException):
      conn.execute(
        "INSERT INTO solutions (kind, quality, source_file, routes) "
        "VALUES ('OPT_TOUR', 'proven_optimal', 'gr48.opt.tour', [[1]])"
      )
    assert conn.execute("SELECT COUNT(*) FROM solutions").fetchone() == (1,)


def _check_values(schema_db: Path, column: str) -> set[str]:
  """Return the literals the ``column`` CHECK admits, read back from DuckDB.

  ``duckdb_constraints()`` exposes ``constraint_type`` and ``expression``, so the
  stored domain can be compared with the Python vocabulary instead of re-reading
  the DDL string.
  """
  with duckdb.connect(str(schema_db), read_only=True) as conn:
    rows = conn.execute(
      "SELECT expression FROM duckdb_constraints() WHERE table_name = 'solutions' AND constraint_type = 'CHECK'"
    ).fetchall()
  pattern = re.compile(rf"\b{column}\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
  for (expression,) in rows:
    if expression and (match := pattern.search(expression)):
      return set(re.findall(r"'([^']*)'", match.group(1)))
  return set()


@pytest.mark.database
def test_solution_vocabularies_match_the_database(schema_db: Path) -> None:
  """WHAT: the ``kind`` and ``quality`` domains as stored in the database.

  WHY: **CV12** — the vocabulary is written once, in ``converter/types.py``, while
  the constraint is a static DDL string. Without this guard the two can drift and
  the database would reject a value the code considers legal (or admit one it
  does not).

  EXPECTED: each stored domain equals the tuple derived from the ``Literal``.
  """
  assert _check_values(schema_db, "kind") == set(SOLUTION_KINDS)
  assert _check_values(schema_db, "quality") == set(SOLUTION_QUALITIES)
  assert len(SOLUTION_KINDS) == 2
  assert len(SOLUTION_QUALITIES) == 3
