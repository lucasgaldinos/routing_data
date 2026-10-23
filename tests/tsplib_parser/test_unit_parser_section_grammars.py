"""Type and value checks for every DATA section of TSPLIB95 (spec §1.2).

WHAT
----
The per-line grammar of each data section is declared once, in
``SECTION_GRAMMARS`` (`src/tsplib_parser/types.py`), straight from the spec: how
many columns a line has, which of them are integers or reals, which companion
keyword selects the variant, and how many ``-1`` terminator lines the section
takes. These tests read that table and, for every declared variant, check the
*raw* file lines against it and then check that the parsed result carries
exactly the numbers those lines contain.

WHY
---
Only matrices had value-level tests. ``DEPOT_SECTION``, ``TOUR_SECTION`` and
``DISPLAY_DATA_SECTION`` had none at all, so a parse that dropped a row, let a
``-1`` reach the result, or turned an integer into a float would have gone
unnoticed. The spec grammar is the oracle: it says what a section may contain,
and the corpus supplies a real file for every variant except ``ADJ_LIST`` and
``THREED_COORDS`` — no corpus file declares ``NODE_COORD_TYPE`` at all.

EXPECTED
--------
- Every entry of ``SECTION_GRAMMARS`` has a case here (the completeness test
  fails when the table grows without one).
- Each body line matches the declared column kinds, and the declared terminators
  are present.
- The parsed values equal the raw rows, re-based to the documented 0-based
  result contract, with no ``-1`` sentinel in the output.
"""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

from tsplib_parser.parser import FormatParser
from tsplib_parser.types import SECTION_GRAMMARS, ColumnKind, SectionGrammar

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult

#: One real corpus file per declared variant, keyed by (keyword, selector value).
#: Paths are relative to the corpus root (`test_data_dir`). The THREED_COORDS entry
#: feeds the value test only: `xray14012_1.tsp` carries three columns *without*
#: declaring `NODE_COORD_TYPE`, so the raw-grammar test uses the synthetic
#: fixture below rather than a file that never selects that variant.
CASES: dict[tuple[str, str | None], str] = {
  ("NODE_COORD_SECTION", "TWOD_COORDS"): "tsp/u1817.tsp",
  ("NODE_COORD_SECTION", "THREED_COORDS"): "tsp/xray14012_1.tsp",
  ("DEPOT_SECTION", None): "vrp/eil22.vrp",
  ("DEMAND_SECTION", None): "vrp/eil22.vrp",
  ("EDGE_DATA_SECTION", "EDGE_LIST"): "hcp/alb1000.hcp",
  ("FIXED_EDGES_SECTION", None): "tsp/linhp318.tsp",
  ("DISPLAY_DATA_SECTION", "TWOD_DISPLAY"): "tsp/bayg29.tsp",
  ("TOUR_SECTION", None): "tour/kroD100.opt.tour",
  ("EDGE_WEIGHT_SECTION", None): "atsp/ftv64.atsp",
}

#: Variants with no corpus instance, exercised from a synthetic file: all nine
#: HCP files use EDGE_LIST (so ADJ_LIST exists only in the spec) and no corpus
#: file declares NODE_COORD_TYPE (so THREED_COORDS is never selected in practice).
#: The parser recognises the ``node: neighbours -1`` spelling; the spec's
#: colon-less form is tracked as PB12 in the package TODO and is not asserted here.
SYNTHETIC: dict[tuple[str, str | None], str] = {
  ("NODE_COORD_SECTION", "THREED_COORDS"): (
    "NAME: threed_coords_fixture\n"
    "TYPE: TSP\n"
    "DIMENSION: 3\n"
    "NODE_COORD_TYPE: THREED_COORDS\n"
    "EDGE_WEIGHT_TYPE: EUC_3D\n"
    "NODE_COORD_SECTION\n"
    "1 0.0 0.0 0.0\n"
    "2 1.0 0.0 0.0\n"
    "3 0.0 1.0 2.0\n"
    "EOF\n"
  ),
  ("EDGE_DATA_SECTION", "ADJ_LIST"): (
    "NAME: adj_list_fixture\n"
    "TYPE: HCP\n"
    "DIMENSION: 4\n"
    "EDGE_DATA_FORMAT: ADJ_LIST\n"
    "EDGE_DATA_SECTION\n"
    "1: 2 3 -1\n"
    "2: 1 -1\n"
    "3: 1 -1\n"
    "-1\n"
    "EOF\n"
  ),
}


def _variant_id(grammar: SectionGrammar) -> str:
  """Readable test id for one declared variant."""
  return f"{grammar.keyword.lower().removesuffix('_section')}-{grammar.selector_value or 'default'}"


def _is_integer(token: str) -> bool:
  return token.lstrip("+-").isdigit()


def _is_real(token: str) -> bool:
  try:
    float(token)
  except ValueError:
    return False
  return True


def _is_header(line: str) -> bool:
  """True for a section header, ``EOF``, or a ``KEYWORD: value`` line.

  A data row may itself contain a colon (``ADJ_LIST`` writes ``1: 2 3 -1``), so
  the colon only marks a header when the part before it is a TSPLIB keyword.
  """
  if line == "EOF" or line.endswith("_SECTION"):
    return True
  if ":" not in line:
    return False
  prefix: str = line.split(":", 1)[0].strip()
  if not prefix or not any(c.isalpha() for c in prefix):
    return False
  return all(c.isupper() or c.isdigit() or c == "_" for c in prefix)


def _section_body(path: Path, keyword: str) -> list[str]:
  """Body lines of ``keyword`` in ``path``: headers, comments and EOF excluded."""
  lines: list[str] = [line.strip() for line in path.read_text().splitlines()]
  start: int = lines.index(keyword)
  body: list[str] = []
  for line in lines[start + 1 :]:
    if line.startswith("#"):
      continue
    if not line or _is_header(line):
      break
    body.append(line)
  return body


def _data_lines(body: list[str]) -> list[str]:
  """Body without its trailing ``-1`` terminator lines."""
  return [line for line in body if line != "-1"]


def _trailing_terminators(body: list[str]) -> int:
  count = 0
  for line in reversed(body):
    if line != "-1":
      break
    count += 1
  return count


def _assert_columns(line: str, columns: tuple[ColumnKind, ...]) -> None:
  """Assert one body line matches the declared column kinds, in order."""
  # The ADJ_LIST spelling this parser recognises closes the source node with a
  # colon (``1: 2 3 -1``). The spec writes no colon (PB12), and a colon is
  # punctuation rather than a column kind, so it is stripped before the check.
  tokens: list[str] = [token.rstrip(":") for token in line.split()]
  pairs: list[tuple[str, ColumnKind]]
  if columns and columns[-1] is ColumnKind.INTEGERS:
    assert len(tokens) >= len(columns), f"{line!r} needs at least {len(columns)} columns, got {len(tokens)}"
    pairs = list(zip(tokens[: len(columns) - 1], columns[: len(columns) - 1], strict=True))
    pairs += [(token, ColumnKind.INTEGER) for token in tokens[len(columns) - 1 :]]
  else:
    assert len(tokens) == len(columns), f"{line!r} must have {len(columns)} columns, got {len(tokens)}"
    pairs = list(zip(tokens, columns, strict=True))

  for token, kind in pairs:
    if kind is ColumnKind.REAL:
      assert _is_real(token), f"column {token!r} must be a real in {line!r}"
    else:
      assert _is_integer(token), f"column {token!r} must be an integer in {line!r}"


def _parse_corpus(test_data_dir: Path, filename: str) -> "ParseResult":
  """Parse one corpus file through the public entry point."""
  return FormatParser().parse_file(str(test_data_dir / filename))


def test_every_declared_variant_has_a_case() -> None:
  """WHAT: the grammar table against the cases declared in this file.

  WHY: a new section grammar without a test would silently shrink the coverage
  this file exists to provide.

  EXPECTED: every variant names a corpus file or a synthetic one.
  """
  missing: list[tuple[str, str | None]] = [
    (grammar.keyword, grammar.selector_value)
    for grammar in SECTION_GRAMMARS
    if (grammar.keyword, grammar.selector_value) not in CASES
    and (grammar.keyword, grammar.selector_value) not in SYNTHETIC
  ]

  assert missing == [], f"no case declared for: {missing}"


@pytest.mark.parametrize("grammar", SECTION_GRAMMARS, ids=_variant_id)
@pytest.mark.requires_dataset
def test_section_lines_follow_the_declared_grammar(
  grammar: SectionGrammar, test_data_dir: Path, tmp_path: Path
) -> None:
  """WHAT: the raw lines of every declared section variant.

  WHY: the parser must be fed the shape the spec defines; a row with the wrong
  column count or with a real where an integer belongs is a malformed file, and
  the terminators are part of the section, not of the data.

  EXPECTED: every data line matches the declared column kinds, and the section
  carries its declared number of ``-1`` terminators (real files may end the last
  one with ``EOF`` instead, as the ``.tour`` corpus shows).
  """
  key: tuple[str, str | None] = (grammar.keyword, grammar.selector_value)
  if key in SYNTHETIC:
    path: Path = tmp_path / "synthetic_fixture.tsp"
    path.write_text(SYNTHETIC[key])
  else:
    assert key in CASES, f"{key} has no case and no synthetic content"
    path = test_data_dir / CASES[key]

  body: list[str] = _section_body(path, grammar.keyword)
  assert body, f"{grammar.keyword} in {path.name} must not be empty"

  for line in _data_lines(body):
    _assert_columns(line, grammar.columns)

  terminators: int = _trailing_terminators(body)
  if grammar.terminator_lines:
    ends_with_eof: bool = path.read_text().splitlines()[-1].strip() == "EOF"
    assert terminators >= grammar.terminator_lines or (terminators >= 1 and ends_with_eof), (
      f"{grammar.keyword}: expected {grammar.terminator_lines} '-1' terminator line(s), found {terminators}"
    )
  else:
    assert terminators == 0, f"{grammar.keyword} takes no terminator, found {terminators}"


class TestNodeCoordinates:
  """`NODE_COORD_SECTION` — `<int> <real> <real>` (2-D) or one more for 3-D."""

  @pytest.mark.requires_dataset
  def test_two_dimensional_coordinates_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: `u1817.tsp`, a 2-D instance.

    WHY: the coordinate values are what every distance in the pipeline is built
    from, and the file's node numbering is 1-based while the result is 0-based.

    EXPECTED: every result coordinate row equals its file row, indexed at node_id - 1.
    """
    body: list[str] = _section_body(test_data_dir / CASES[("NODE_COORD_SECTION", "TWOD_COORDS")], "NODE_COORD_SECTION")
    coords: list[list[float]] = _parse_corpus(test_data_dir, CASES[("NODE_COORD_SECTION", "TWOD_COORDS")])["coords"]

    assert len(coords) == len(body), "one result coordinate row per file row"
    for index, (line, coord) in enumerate(zip(body, coords, strict=True)):
      node_id, x, y = line.split()
      assert int(node_id) == index + 1, "the file numbers nodes from 1"
      assert coord == [float(x), float(y)], "a 2-D instance has [x, y] float coordinates"

  @pytest.mark.requires_dataset
  def test_three_dimensional_coordinates_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: `xray14012_1.tsp`, whose rows carry three coordinates.

    WHY: this is the only corpus shape with a third column, and 3-D support is
    what makes the XRAY instances parseable at all.

    EXPECTED: every result coordinate row equals its file row, indexed at node_id - 1.
    """
    filename: str = CASES[("NODE_COORD_SECTION", "THREED_COORDS")]
    body: list[str] = _section_body(test_data_dir / filename, "NODE_COORD_SECTION")
    coords: list[list[float]] = _parse_corpus(test_data_dir, filename)["coords"]

    assert len(coords) == len(body) == 14_012
    for index, (line, coord) in enumerate(zip(body, coords, strict=True)):
      node_id, x, y, z = line.split()
      assert int(node_id) - 1 == index
      assert coord == [float(x), float(y), float(z)]


class TestDepotAndDemandSections:
  """`DEPOT_SECTION` and `DEMAND_SECTION` of a CVRP (`eil22.vrp`)."""

  @pytest.mark.requires_dataset
  def test_depots_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: the single depot of `eil22.vrp`, listed as node 1 and terminated by -1.

    WHY: the depot decides which demand row must be zero, and the terminator must
    never reach the result as a node id.

    EXPECTED: the file's node ids minus one, and no -1 in the result.
    """
    body: list[str] = _section_body(test_data_dir / CASES[("DEPOT_SECTION", None)], "DEPOT_SECTION")
    depots = _parse_corpus(test_data_dir, CASES[("DEPOT_SECTION", None)])["depots"]

    assert depots == [int(line) - 1 for line in _data_lines(body)]
    assert -1 not in depots

  @pytest.mark.requires_dataset
  def test_demands_match_the_file_and_the_depot_demand_is_zero(self, test_data_dir: Path) -> None:
    """WHAT: every `DEMAND_SECTION` row of `eil22.vrp`.

    WHY: the spec requires the depot rows to be listed with demand 0; a parser
    that skipped them would still produce a plausible list, only shifted.

    EXPECTED: `demands[node - 1]` equals the file's demand for every row, and the
    depot's demand is 0.
    """
    filename: str = CASES[("DEMAND_SECTION", None)]
    body: list[str] = _section_body(test_data_dir / filename, "DEMAND_SECTION")
    rows: list[list[str]] = [line.split() for line in body]

    result: ParseResult = _parse_corpus(test_data_dir, filename)
    demands = result["demands"]
    depots = result["depots"]

    assert len(demands) == result["problem_data"]["dimension"]
    for node_id, demand in rows:
      assert demands[int(node_id) - 1] == int(demand)
    assert all(demands[depot] == 0 for depot in depots), "the depot nodes must carry demand 0"


class TestEdgeDataSections:
  """`EDGE_DATA_SECTION` in both formats of the spec."""

  @pytest.mark.requires_dataset
  def test_edge_list_pairs_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: `alb1000.hcp`, an `EDGE_LIST` instance.

    WHY: the pairs are re-based in the result, so an off-by-one or a lost final
    pair is invisible without comparing against the file.

    EXPECTED: exactly the file's pairs, minus one per endpoint.
    """
    filename: str = CASES[("EDGE_DATA_SECTION", "EDGE_LIST")]
    body: list[str] = _section_body(test_data_dir / filename, "EDGE_DATA_SECTION")
    edges = _parse_corpus(test_data_dir, filename)["edges"]

    assert edges == [[int(u) - 1, int(v) - 1] for u, v in (line.split() for line in _data_lines(body))]
    assert all(-1 not in edge for edge in edges)

  def test_adjacency_list_pairs_match_the_fixture(self, tmp_path: Path) -> None:
    """WHAT: an ``ADJ_LIST`` section in both colon-separated and spec colon-less forms.

    WHY: each line names a node and its neighbours, closed by ``-1``, and the
    whole list is closed by another ``-1``; both sentinels must be consumed.

    EXPECTED: one edge per (node, neighbour) pair, 0-based and sorted.
    """
    path: Path = tmp_path / "adj_list.hcp"
    path.write_text(SYNTHETIC[("EDGE_DATA_SECTION", "ADJ_LIST")])

    result: ParseResult = FormatParser().parse_file(str(path))
    assert sorted(result["edges"]) == [[0, 1], [0, 2], [1, 0], [2, 0]]

    # Also verify TSPLIB95 §1.2.4 colon-less ADJ_LIST form (PB12)
    colonless_path: Path = tmp_path / "adj_list_spec.hcp"
    colonless_path.write_text(
      "NAME: adj_list_spec\n"
      "TYPE: HCP\n"
      "DIMENSION: 4\n"
      "EDGE_DATA_FORMAT: ADJ_LIST\n"
      "EDGE_DATA_SECTION\n"
      "1 2 3 -1\n"
      "2 1 -1\n"
      "3 1 -1\n"
      "-1\n"
      "EOF\n"
    )
    colonless_result: ParseResult = FormatParser().parse_file(str(colonless_path))
    assert sorted(colonless_result["edges"]) == [[0, 1], [0, 2], [1, 0], [2, 0]]


class TestFixedEdgesSection:
  """`FIXED_EDGES_SECTION` — pairs the solution must contain."""

  @pytest.mark.requires_dataset
  def test_fixed_edges_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: `linhp318.tsp`, the one corpus file carrying this section.

    WHY: these edges are constraints, not weights; losing one changes which
    solutions the downstream problem describes.

    EXPECTED: exactly the file's pairs, minus one per endpoint.
    """
    filename: str = CASES[("FIXED_EDGES_SECTION", None)]
    body: list[str] = _section_body(test_data_dir / filename, "FIXED_EDGES_SECTION")
    fixed_edges = _parse_corpus(test_data_dir, filename)["fixed_edges"]

    assert fixed_edges == [[int(u) - 1, int(v) - 1] for u, v in (line.split() for line in _data_lines(body))]
    assert all(-1 not in edge for edge in fixed_edges)


class TestDisplayDataSection:
  """`DISPLAY_DATA_SECTION` — 2-D coordinates for plotting only."""

  WITH_COORDS: ClassVar[str] = (
    "NAME: display_fixture\n"
    "TYPE: TSP\n"
    "DIMENSION: 3\n"
    "EDGE_WEIGHT_TYPE: EUC_2D\n"
    "NODE_COORD_SECTION\n"
    "1 0.0 0.0\n"
    "2 10.0 0.0\n"
    "3 0.0 10.0\n"
    "DISPLAY_DATA_TYPE: TWOD_DISPLAY\n"
    "DISPLAY_DATA_SECTION\n"
    "1 1150.0 1760.0\n"
    "2 630.0 1660.0\n"
    "3 40.0 2090.0\n"
    "EOF\n"
  )

  @pytest.mark.requires_dataset
  def test_display_coordinates_match_corpus_file(self, test_data_dir: Path) -> None:
    """WHAT: `bayg29.tsp`, which carries `DISPLAY_DATA_SECTION` without `NODE_COORD_SECTION` (PB13).

    WHY: explicit-weight problems with display coordinates must expose `display_coords`
    even when `coords` is empty.

    EXPECTED: `display_coords` equals the 29 rows in `bayg29.tsp` and `coords` is empty.
    """
    filename: str = CASES[("DISPLAY_DATA_SECTION", "TWOD_DISPLAY")]
    body: list[str] = _section_body(test_data_dir / filename, "DISPLAY_DATA_SECTION")
    result: ParseResult = _parse_corpus(test_data_dir, filename)

    assert result["coords"] == []
    display_coords: list[list[float]] = result["display_coords"]
    assert len(display_coords) == len(body) == 29
    for index, (line, dcoord) in enumerate(zip(body, display_coords, strict=True)):
      node_id, x, y = line.split()
      assert int(node_id) - 1 == index
      assert dcoord == [float(x), float(y)]

  def test_display_coordinates_match_the_fixture(self, tmp_path: Path) -> None:
    """WHAT: a synthetic fixture carrying both `NODE_COORD_SECTION` and `DISPLAY_DATA_SECTION`.

    WHY: display coordinates are independent of node coordinates; dropping or
    swapping the two sets would otherwise go unnoticed.

    EXPECTED: `display_coords` and `coords` both equal their respective sections.
    """
    path: Path = tmp_path / "display_fixture.tsp"
    path.write_text(self.WITH_COORDS)

    result: ParseResult = FormatParser().parse_file(str(path))
    coords: list[list[float]] = result["coords"]
    display_coords: list[list[float]] = result["display_coords"]
    body: list[str] = _section_body(path, "DISPLAY_DATA_SECTION")

    assert len(body) == len(coords) == len(display_coords) == 3
    for index, (line, dcoord) in enumerate(zip(body, display_coords, strict=True)):
      node_id, x, y = line.split()
      assert int(node_id) - 1 == index
      assert dcoord == [float(x), float(y)]

    assert coords[0] == [0.0, 0.0]
    assert display_coords[0] != coords[0], "display data must not overwrite node coordinates"


class TestTourSection:
  """`TOUR_SECTION` — one or more tours, each closed by -1."""

  @pytest.mark.requires_dataset
  def test_tour_nodes_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: `kroD100.opt.tour`, a single optimal tour of 100 nodes.

    WHY: the tour drives every solution-cost computation, and the file mixes the
    tour's own terminator with the section's.

    EXPECTED: one tour, its nodes equal to the file's sequence minus one, no
    sentinel left.
    """
    filename: str = CASES[("TOUR_SECTION", None)]
    body: list[str] = _section_body(test_data_dir / filename, "TOUR_SECTION")
    tours = _parse_corpus(test_data_dir, filename)["tours"]

    expected_nodes: list[int] = [int(line) - 1 for line in _data_lines(body)]

    assert len(tours) == 1
    assert tours[0]["tour_id"] == 0
    assert tours[0]["nodes"] == expected_nodes
    assert len(expected_nodes) == 100, "kroD100's optimal tour visits 100 nodes"
    assert -1 not in tours[0]["nodes"]


class TestEdgeWeightSection:
  """`EDGE_WEIGHT_SECTION` — the explicit matrix."""

  @pytest.mark.requires_dataset
  def test_matrix_values_match_the_file(self, test_data_dir: Path) -> None:
    """WHAT: the explicit matrix of `ftv64.atsp` (`FULL_MATRIX`).

    WHY: matrices are the one section with existing value tests, but none of them
    compares against the file's own numbers, which is what catches a shifted row
    or a mis-ordered entry. The lines are *not* rows: TSPLIB wraps a matrix at an
    arbitrary width, so the token stream is what must match, in row-major order.

    EXPECTED: the matrix equals the file's token stream exactly, in row-major order.
    """
    filename: str = CASES[("EDGE_WEIGHT_SECTION", None)]
    body: list[str] = _section_body(test_data_dir / filename, "EDGE_WEIGHT_SECTION")
    result: ParseResult = _parse_corpus(test_data_dir, filename)

    matrix = result["problem_data"]["edge_weights"]
    dimension = result["problem_data"]["dimension"]
    values: list[int] = [int(token) for line in body for token in line.split()]

    assert len(values) == dimension * dimension, "a FULL_MATRIX has dimension² entries"
    # The whole stream in row-major order: sampled cells cannot catch a row that
    # shifts further down the matrix.
    assert matrix.numbers == values
