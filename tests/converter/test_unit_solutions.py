"""Solution parsing (``*.opt.tour``, ``*.sol``) and linking to a problem.

WHAT
----
Covers the two solution grammars shipped with the benchmark corpus, the
normalisation rule they share (0-based node indices, depot excluded, one route
for a tour and N routes for a ``.sol``), the failure modes that used to be
silent, and the two directions of the problem link: file discovery from a
problem path (:func:`candidate_solution_files`) and stem matching from a
solution file (:func:`link_solution`). Two corpus-wide tests assert the
invariants that make the single normalisation rule safe: every corpus file
numbers nodes from 1, never lists the depot, and returns a contiguous 0..n-1
index set.

WHY
---
``DataTransformer.parse_solution_data`` had zero callers, returned ``None`` on
every failure (so "malformed" looked like "no solution", register item S2), and
carried an encoding-handler bug (**M9**) plus a temp-file workaround that only
existed because it routed tours through ``FormatParser``. The replacement must
fail loudly, never touch the disk for parsing, and be provably complete over the
corpus before the write path depends on it (**A2** of the CV10 plan).

The link needs the same treatment: ``find_solution_file`` knew two hardcoded
layouts and returned the first hit, so a stem matching two instances silently
produced a wrong link. The replacement returns every candidate path (forward)
or refuses (backward), and never picks for the user (**CV10**).

EXPECTED
--------
- Both formats parse with the right ``kind``/``quality`` and 0-based routes.
- ``Cost`` accepts signed and scientific notation.
- Every malformed input raises ``SolutionParseError``; none returns ``None``.
- All 82 tours and all 390 ``.sol`` files in the corpus satisfy the contiguity
  invariant, which is what makes ``index = id - 1`` a single rule.
- Discovery finds a solution for every corpus instance that ships one, and
  linking reports ``no_instance``/``ambiguous`` instead of guessing.
"""

import math
from pathlib import Path

import pytest

from converter.core.contracts import ParsedSolution, ProblemRef
from converter.core.solutions import (
  TOUR_INSTANCE_SUFFIXES,
  Linked,
  SolutionParseError,
  Unlinked,
  candidate_solution_files,
  link_solution,
  parse_solution_file,
  solution_stem,
)
from tsplib_parser.parser import FormatParser

#: gr48.opt.tour carries its cost inside the COMMENT, as
#: ``COMMENT : Optimal solution for gr48 (5046)``.
TOUR_WITH_COMMENT_COST = "zips/all_problems/tour/gr48.opt.tour"

#: alb1000.opt.tour has no COMMENT at all, so there is no cost to recover.
TOUR_WITHOUT_COST = "zips/all_problems/tour/alb1000.opt.tour"

#: A wrapped XXL solution: routes run over several physical lines.
SOL_WRAPPED_ROUTES = "cvrplib/vrp-XXL/Leuven2.sol"


def _write(tmp_path: Path, name: str, content: str) -> Path:
  """Write ``content`` to ``tmp_path/name`` and return the path."""
  target = tmp_path / name
  target.write_text(content, encoding="utf-8")
  return target


@pytest.mark.requires_dataset
def test_opt_tour_parses_single_route_with_comment_cost(datasets_raw_dir: Path) -> None:
  """WHAT: a TSPLIB tour that declares its cost in the COMMENT.

  WHY: ``.opt.tour`` has no ``Cost`` line; the cost lives in the comment text, and
  this file proves the round trip keeps it.

  EXPECTED: kind ``OPT_TOUR``, quality ``proven_optimal``, cost 5046.0, one route
  covering 48 nodes as indices 0..47.
  """
  parsed = parse_solution_file(datasets_raw_dir / TOUR_WITH_COMMENT_COST)

  assert parsed["kind"] == "OPT_TOUR"
  assert parsed["quality"] == "proven_optimal"
  assert parsed["cost"] == 5046.0
  assert len(parsed["routes"]) == 1
  route = parsed["routes"][0]
  assert len(route) == 48
  assert sorted(route) == list(range(48))


@pytest.mark.requires_dataset
def test_opt_tour_without_comment_has_no_cost(datasets_raw_dir: Path) -> None:
  """WHAT: a tour file with no COMMENT line.

  WHY: absence of a cost must be represented as ``None``, not as 0.0 — a zero cost
  would be a wrong answer, not a missing one.

  EXPECTED: ``cost is None`` and the route still covers every node exactly once.
  """
  parsed = parse_solution_file(datasets_raw_dir / TOUR_WITHOUT_COST)

  assert parsed["cost"] is None
  route = parsed["routes"][0]
  assert len(route) == 1000
  assert sorted(route) == list(range(1000))


@pytest.mark.requires_dataset
def test_sol_parses_many_routes_and_cost(datasets_raw_dir: Path) -> None:
  """WHAT: an XXL CVRPLIB solution whose routes wrap across physical lines.

  WHY: the route body is not one line, so a line-oriented parser would truncate
  every vehicle route; the corpus contains files with 46 to 684 routes.

  EXPECTED: kind ``SOL``, quality ``best_known``, a cost, several routes, and every
  node visited exactly once.
  """
  parsed = parse_solution_file(datasets_raw_dir / SOL_WRAPPED_ROUTES)

  assert parsed["kind"] == "SOL"
  assert parsed["quality"] == "best_known"
  assert parsed["cost"] is not None
  assert len(parsed["routes"]) > 1
  visited = [node for route in parsed["routes"] for node in route]
  assert len(visited) == len(set(visited))
  assert sorted(visited) == list(range(1, len(visited) + 1))


def test_cost_accepts_signed_and_scientific_notation(tmp_path: Path) -> None:
  """WHAT: ``Cost -1.5e3`` and ``Cost 2500.75`` in two synthetic solutions.

  WHY: the previous ``([\\d.]+)`` pattern silently returned ``None`` for both, so a
  negative or exponential cost would have been stored as "no cost".

  EXPECTED: -1500.0 and 2500.75.
  """
  negative = _write(tmp_path, "neg.sol", "Route #1: 1 2 3\nCost -1.5e3\n")
  decimal = _write(tmp_path, "dec.sol", "Route #1: 1 2 3\nCost 2500.75\n")

  assert parse_solution_file(negative)["cost"] == -1500.0
  assert parse_solution_file(decimal)["cost"] == 2500.75


def test_tour_section_missing_raises(tmp_path: Path) -> None:
  """WHAT: a ``.tour`` file with a header but no TOUR_SECTION.

  WHY: a header-only tour is a malformed file; returning ``None`` made it look
  like an instance without a solution (S2).

  EXPECTED: ``SolutionParseError`` naming the missing section.
  """
  path = _write(tmp_path, "broken.opt.tour", "NAME : broken\nTYPE : TOUR\nEOF\n")

  with pytest.raises(SolutionParseError, match="TOUR_SECTION"):
    parse_solution_file(path)


def test_tour_section_empty_raises(tmp_path: Path) -> None:
  """WHAT: a TOUR_SECTION with no nodes.

  WHY: an empty cycle is not a solution; storing it would create a row whose
  ``routes`` claim nothing was visited.

  EXPECTED: ``SolutionParseError``.
  """
  path = _write(tmp_path, "empty.opt.tour", "TYPE : TOUR\nTOUR_SECTION\n-1\nEOF\n")

  with pytest.raises(SolutionParseError, match="empty"):
    parse_solution_file(path)


def test_sol_without_routes_raises(tmp_path: Path) -> None:
  """WHAT: a ``.sol`` file whose body has no ``Route #N:`` line.

  WHY: a cost with no routes is not a usable solution.

  EXPECTED: ``SolutionParseError`` naming the missing routes.
  """
  path = _write(tmp_path, "noroutes.sol", "Cost 100\n")

  with pytest.raises(SolutionParseError, match="Route"):
    parse_solution_file(path)


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
  """WHAT: a file that is neither ``.tour`` nor ``.sol``.

  WHY: silently skipping unknown formats is how files vanish from a corpus.

  EXPECTED: ``SolutionParseError`` naming the suffix.
  """
  path = _write(tmp_path, "solution.txt", "Route #1: 1 2 3\n")

  with pytest.raises(SolutionParseError, match=r"\.txt"):
    parse_solution_file(path)


def test_zero_indexed_node_is_rejected(tmp_path: Path) -> None:
  """WHAT: a solution that lists node 0.

  WHY: measured over all 472 corpus files, node numbering starts at 1 and the
  depot is never listed (CV10). A 0 therefore means the file uses a different
  convention, and shifting it silently would misalign the whole route.

  EXPECTED: ``SolutionParseError`` explaining that the depot is never listed.
  """
  path = _write(tmp_path, "zero.sol", "Route #1: 0 1 2\nCost 10\n")

  with pytest.raises(SolutionParseError, match="depot"):
    parse_solution_file(path)


def test_non_utf8_bytes_fall_back_to_latin1(tmp_path: Path) -> None:
  """WHAT: a tour whose COMMENT holds a latin-1 byte (``é`` as 0xE9).

  WHY: **M9** — the old reader passed ``errors="latin-1"``, an encoding name in the
  error-handler slot; CPython resolves that lazily, so the first non-UTF-8 byte
  raised ``LookupError`` and the broad ``except`` turned the solution into ``None``.

  EXPECTED: the file parses and the route is intact.
  """
  content = b"NAME : caf\xe9\nTYPE : TOUR\nCOMMENT : optimal for caf\xe9\nTOUR_SECTION\n1\n3\n-1\nEOF\n"
  path = tmp_path / "latin1.opt.tour"
  path.write_bytes(content)

  parsed = parse_solution_file(path)

  assert parsed["kind"] == "OPT_TOUR"
  assert parsed["routes"] == [[0, 2]]


def test_tour_terminator_closes_the_cycle(tmp_path: Path) -> None:
  """WHAT: a tour whose ``-1`` terminator is followed by ``EOF``.

  WHY: the terminator must end the node list without swallowing the trailer or
  leaking into the route as a bogus index.

  EXPECTED: exactly the nodes before ``-1``, in file order, shifted to 0-based.
  """
  path = _write(tmp_path, "t.opt.tour", "TYPE : TOUR\nTOUR_SECTION\n2 4 6 -1\nEOF\n")

  assert parse_solution_file(path)["routes"] == [[1, 3, 5]]


def test_second_tour_section_raises(tmp_path: Path) -> None:
  """WHAT: a tour file carrying two ``TOUR_SECTION`` blocks.

  WHY: the first implementation merged both cycles into one route when the second
  header appeared after the terminator, and silently dropped the second cycle
  when they were separated by ``-1`` only. Either way a wrong tour was stored.

  EXPECTED: ``SolutionParseError``, never a merged route.
  """
  two_headers = _write(tmp_path, "a.opt.tour", "TYPE : TOUR\nTOUR_SECTION\n1 2 -1\nTOUR_SECTION\n3 4 -1\nEOF\n")
  two_cycles = _write(tmp_path, "b.opt.tour", "TYPE : TOUR\nTOUR_SECTION\n1 2 -1\n3 4 -1\nEOF\n")

  with pytest.raises(SolutionParseError, match="second TOUR_SECTION"):
    parse_solution_file(two_headers)
  with pytest.raises(SolutionParseError, match="after the tour terminator"):
    parse_solution_file(two_cycles)


def test_tour_dimension_mismatch_raises(tmp_path: Path) -> None:
  """WHAT: a tour that lists fewer nodes than its own ``DIMENSION`` line declares.

  WHY: 81 of the 82 corpus tours declare ``DIMENSION``, so the parser can check
  completeness itself; a 47-node tour of a 48-node instance used to be accepted.

  EXPECTED: ``SolutionParseError`` naming both counts.
  """
  path = _write(tmp_path, "short.opt.tour", "DIMENSION : 5\nTOUR_SECTION\n1 2 3 -1\nEOF\n")

  with pytest.raises(SolutionParseError, match="DIMENSION is 5"):
    parse_solution_file(path)


def test_non_integer_token_in_a_route_raises(tmp_path: Path) -> None:
  """WHAT: ``Route #1: 1.0 2 3`` and ``Route #1: 1 -2 3``.

  WHY: the first implementation captured only ``[\\d\\s]+``, so a body was silently
  truncated at the first non-digit and ``1.0 2 3`` became the route ``[0]``.

  EXPECTED: ``SolutionParseError`` for both.
  """
  decimal = _write(tmp_path, "dec.sol", "Route #1: 1.0 2 3\nCost 10\n")
  negative = _write(tmp_path, "neg.sol", "Route #1: 1 -2 3\nCost 10\n")

  with pytest.raises(SolutionParseError, match="not an integer"):
    parse_solution_file(decimal)
  with pytest.raises(SolutionParseError, match="negative node id"):
    parse_solution_file(negative)


def test_duplicate_customer_raises(tmp_path: Path) -> None:
  """WHAT: a ``.sol`` that serves customer 2 twice and never visits 3.

  WHY: the completeness rule is executable, not just a corpus observation; a
  route that misses a customer is not a solution of that instance.

  EXPECTED: ``SolutionParseError``.
  """
  path = _write(tmp_path, "dup.sol", "Route #1: 1 2 2\nCost 10\n")

  with pytest.raises(SolutionParseError, match="served twice"):
    parse_solution_file(path)


def test_missing_solution_file_raises_parse_error(tmp_path: Path) -> None:
  """WHAT: a path that no longer exists (deleted between scan and parse).

  WHY: a batch that catches ``SolutionParseError`` must not die because the file
  system raised ``FileNotFoundError`` instead.

  EXPECTED: ``SolutionParseError`` wrapping the OS error.
  """
  with pytest.raises(SolutionParseError, match="cannot read"):
    parse_solution_file(tmp_path / "gone.sol")


@pytest.mark.parametrize("name", ["GR48.OPT.TOUR", "gr48.Opt.Tour"])
def test_solution_stem_is_case_insensitive(name: str) -> None:
  """WHAT: an uppercase spelling of the tour suffix.

  WHY: discovery lowercases the suffix but the first stem implementation stripped
  ``.opt`` case-sensitively, so ``GR48.OPT.TOUR`` yielded ``GR48.OPT`` -- one
  uppercase file away from orphaning every tour.

  EXPECTED: the bare instance name.
  """
  assert solution_stem(name) == name[: -len(".opt.tour")]


@pytest.mark.requires_dataset
def test_every_corpus_tour_is_one_complete_cycle(datasets_raw_dir: Path) -> None:
  """WHAT: all 82 ``*.opt.tour`` files in the corpus.

  WHY: this is the evidence for the single normalisation rule — if any tour
  repeated a node, skipped one, or listed the depot, ``index = id - 1`` would be
  wrong for that file and the "one rule for both formats" decision would collapse.

  EXPECTED: one route per file, nodes unique and contiguous from 0.
  """
  tours = sorted(datasets_raw_dir.rglob("*.opt.tour"))
  assert len(tours) == 82

  for path in tours:
    parsed = parse_solution_file(path)
    assert parsed["kind"] == "OPT_TOUR"
    assert parsed["quality"] == "proven_optimal"
    assert len(parsed["routes"]) == 1, f"{path.name}: a tour must be one cycle"
    route = parsed["routes"][0]
    assert sorted(route) == list(range(len(route))), f"{path.name}: route is not a complete 0-based cycle"


@pytest.mark.requires_dataset
def test_every_corpus_solution_is_contiguous_and_costs(datasets_raw_dir: Path) -> None:
  """WHAT: all 390 ``*.sol`` files in the corpus.

  WHY: the same evidence for the multi-route side: every customer is visited
  exactly once across all vehicle routes, and every file states a cost.

  EXPECTED: unique contiguous 1..n node set per file and a non-null cost.
  """
  solutions = sorted(datasets_raw_dir.rglob("*.sol"))
  assert len(solutions) == 390

  for path in solutions:
    parsed = parse_solution_file(path)
    assert parsed["kind"] == "SOL"
    assert parsed["quality"] == "best_known"
    assert parsed["cost"] is not None, f"{path.name}: no cost line"
    visited = [node for route in parsed["routes"] for node in route]
    assert len(visited) == len(set(visited)), f"{path.name}: a customer is served twice"
    assert sorted(visited) == list(range(1, len(visited) + 1)), (
      f"{path.name}: not a complete 1..n customer set (index = id, depot 0 excluded)"
    )


# --------------------------------------------------------------------------- #
# Index frame: the only test that can tell the two formats' rules apart
# --------------------------------------------------------------------------- #


def _stated_cost(datasets_raw_dir: Path, instance: str, solution: str, *, rounded: bool) -> tuple[float, float | None]:
  """Recompute the solution's cost from its instance, in the parser's index frame.

  The oracle closes every route through the depot (index 0) and uses the
  instance's own distances: the explicit matrix when the instance is
  ``EXPLICIT``, otherwise Euclidean with or without ``nint`` rounding. This is
  the check that a contiguity sweep cannot make: a uniform index shift preserves
  contiguity, so only recomputing the cost can see the frame.
  """
  problem = FormatParser().parse_file(str(datasets_raw_dir / instance))
  matrix = problem["problem_data"].get("edge_weights")
  coords = problem["coords"]

  def distance(a: int, b: int) -> float:
    if matrix is not None:
      return float(matrix.value_at(a, b))
    value = math.dist(coords[a], coords[b])
    return round(value) if rounded else value

  parsed = parse_solution_file(datasets_raw_dir / solution)
  total = 0.0
  for route in parsed["routes"]:
    stops = [0, *route, 0]
    total += sum(distance(stops[i], stops[i + 1]) for i in range(len(stops) - 1))
  return total, parsed["cost"]


@pytest.mark.requires_dataset
@pytest.mark.parametrize(
  ("instance", "solution", "rounded"),
  [
    ("cvrplib/vrp-XXL/Brussels1.vrp", "cvrplib/vrp-XXL/Brussels1.sol", True),
    ("cvrplib/vrp-XXL/Antwerp1.vrp", "cvrplib/vrp-XXL/Antwerp1.sol", True),
    ("cvrplib/Vrp-Set-Li/Li_21.vrp", "cvrplib/Vrp-Set-Li/Li_21.sol", False),
    ("cvrplib/Vrp-Set-Li/Li_22.vrp", "cvrplib/Vrp-Set-Li/Li_22.sol", False),
    ("cvrplib/VRP-set-D/Loggi-n401-k23.vrp", "cvrplib/VRP-set-D/Loggi-n401-k23.sol", False),
    ("cvrplib/VRP-set-D/Loggi-n1001-k31.vrp", "cvrplib/VRP-set-D/Loggi-n1001-k31.sol", False),
  ],
)
def test_sol_routes_index_the_instance_arrays(
  datasets_raw_dir: Path, instance: str, solution: str, rounded: bool
) -> None:
  """WHAT: a ``.sol`` route read as indices into the instance's own node arrays.

  WHY: **CV14** — the first A2 implementation subtracted 1 from every id for both
  formats. For ``.sol`` the id *is* the array index (the depot occupies index 0),
  so every CVRP solution was stored one node off: ``demands[route[i]]`` read the
  previous customer and the published cost was 17.9x too large on ``Brussels1``.
  The contiguity sweep could not see it, because a uniform shift keeps the set
  contiguous; recomputing the stated cost can.

  EXPECTED: the recomputed length equals the file's ``Cost`` (matrix, ``nint`` or
  real Euclidean, whichever the family uses).
  """
  total, stated = _stated_cost(datasets_raw_dir, instance, solution, rounded=rounded)

  assert stated is not None
  assert total == pytest.approx(stated, rel=1e-6)


@pytest.mark.requires_dataset
def test_tour_routes_index_a_depot_free_array(datasets_raw_dir: Path) -> None:
  """WHAT: a ``.opt.tour`` route read as indices into a depot-free node array.

  WHY: the tour frame is ``index = id - 1``, the opposite of ``.sol``. gr48 ships
  an explicit matrix and states 5046 in its COMMENT, so the frame is checkable
  without assuming a distance convention: the other frame is out of bounds.

  EXPECTED: the closed cycle over gr48's matrix equals 5046.
  """
  total, stated = _stated_cost(
    datasets_raw_dir,
    "zips/all_problems/tsp/gr48.tsp",
    "zips/all_problems/tour/gr48.opt.tour",
    rounded=False,
  )

  assert stated == 5046.0
  assert total == pytest.approx(5046.0)


@pytest.mark.requires_dataset
@pytest.mark.parametrize(
  ("tour", "expected"),
  [
    ("zips/all_problems/tour/ch130.opt.tour", 6110.0),
    ("zips/all_problems/tour/ch150.opt.tour", 6528.0),
    ("zips/all_problems/tour/eil101.opt.tour", 629.0),
  ],
)
def test_tour_cost_shapes_present_in_the_corpus(datasets_raw_dir: Path, tour: str, expected: float) -> None:
  """WHAT: the comment shapes ``Length 6110`` and ``(Length 629)``.

  WHY: a regex that only accepted ``(294358)`` silently reported ``cost=None`` for
  these corpus files, which A4 would have published as "no cost".

  EXPECTED: the stated length, not ``None``.
  """
  parsed = parse_solution_file(datasets_raw_dir / tour)

  assert parsed["cost"] == expected


# --------------------------------------------------------------------------- #
# Linking: discovery from a problem path (forward) and stem matching (backward)
# --------------------------------------------------------------------------- #


def _instance_tree(tmp_path: Path) -> Path:
  """Build a miniature corpus that reproduces the two measured layouts.

  ``<root>/problems/tsp/a.tsp`` with its tour at ``<root>/problems/tour/``, and
  ``<root>/cvrplib/set/b.vrp`` with a sibling ``b.sol`` -- the exact two rules
  ``candidate_solution_files`` relies on.
  """
  root = tmp_path / "corpus"
  (root / "problems" / "tsp").mkdir(parents=True)
  (root / "problems" / "tour").mkdir(parents=True)
  (root / "problems" / "vrp").mkdir(parents=True)
  (root / "cvrplib" / "set").mkdir(parents=True)

  (root / "problems" / "tsp" / "a.tsp").write_text("NAME : a\n", encoding="utf-8")
  (root / "problems" / "tour" / "a.opt.tour").write_text("TOUR_SECTION\n0\n-1\nEOF\n", encoding="utf-8")
  (root / "problems" / "vrp" / "a.vrp").write_text("NAME : a\n", encoding="utf-8")
  (root / "cvrplib" / "set" / "b.vrp").write_text("NAME : b\n", encoding="utf-8")
  (root / "cvrplib" / "set" / "b.sol").write_text("Route #1: 1 2\nCost 3\n", encoding="utf-8")
  return root


@pytest.mark.parametrize(
  ("name", "expected"),
  [
    ("gr48.opt.tour", "gr48"),
    ("gr48.tour", "gr48"),
    ("Leuven2.sol", "Leuven2"),
    ("kroD100.opt.tour", "kroD100"),
  ],
)
def test_solution_stem_strips_the_solution_suffix(name: str, expected: str) -> None:
  """WHAT: the instance name recovered from a solution filename.

  WHY: ``Path.stem`` returns ``gr48.opt`` for ``gr48.opt.tour``, a name no
  problem has, so every tour would become an orphan.

  EXPECTED: ``.opt.tour``, ``.tour`` and ``.sol`` all reduce to the instance name.
  """
  assert solution_stem(name) == expected


def test_discovery_finds_the_sibling_solution(tmp_path: Path) -> None:
  """WHAT: rule 1, the ``X.vrp`` / ``X.sol`` sibling pair.

  WHY: 390/390 corpus ``.sol`` files sit next to their instance, so a sibling is
  the whole rule; no directory guessing is needed.

  EXPECTED: exactly the sibling ``.sol``.
  """
  root = _instance_tree(tmp_path)
  assert candidate_solution_files(root / "cvrplib" / "set" / "b.vrp") == [root / "cvrplib" / "set" / "b.sol"]


def test_discovery_finds_the_tour_in_the_sibling_directory(tmp_path: Path) -> None:
  """WHAT: rule 2, ``tsp/X.tsp`` -> ``tour/X.opt.tour``.

  WHY: 82/82 corpus tours live in the ``tour`` directory next to their instance's
  family directory, and the corpus names them ``*.opt.tour`` (not ``*.tour``).

  EXPECTED: exactly the tour, even though no ``a.sol`` exists.
  """
  root = _instance_tree(tmp_path)
  assert candidate_solution_files(root / "problems" / "tsp" / "a.tsp") == [root / "problems" / "tour" / "a.opt.tour"]


def test_discovery_does_not_give_a_tour_to_the_route_instance(tmp_path: Path) -> None:
  """WHAT: the ``a.vrp`` twin of an instance that also ships a tour.

  WHY: **CV10** -- ``att48`` and ``eil51`` exist as both ``.tsp`` and ``.vrp``,
  and the tour belongs to the ``.tsp`` twin. A tour is a single cycle, so it is
  not a solution of the capacitated instance; handing it over would be a silent
  wrong link, the exact failure the old ``find_solution_file`` produced.

  EXPECTED: no candidates for ``a.vrp`` while ``a.tsp`` still gets the tour.
  """
  root = _instance_tree(tmp_path)
  assert candidate_solution_files(root / "problems" / "vrp" / "a.vrp") == []
  assert candidate_solution_files(root / "problems" / "tsp" / "a.tsp") == [root / "problems" / "tour" / "a.opt.tour"]


def test_discovery_returns_both_when_the_corpus_ships_both(tmp_path: Path) -> None:
  """WHAT: an instance with a sibling ``.sol`` *and* a tour.

  WHY: both files exist, so both are real solutions of that instance. Choosing
  one here would hide a data problem; the caller stores both.

  EXPECTED: the sibling first (path rule), the tour second.
  """
  root = _instance_tree(tmp_path)
  (root / "problems" / "tsp" / "a.sol").write_text("Route #1: 1\nCost 1\n", encoding="utf-8")

  assert candidate_solution_files(root / "problems" / "tsp" / "a.tsp") == [
    root / "problems" / "tsp" / "a.sol",
    root / "problems" / "tour" / "a.opt.tour",
  ]


def test_discovery_returns_nothing_when_the_corpus_ships_no_solution(tmp_path: Path) -> None:
  """WHAT: an instance with no solution anywhere.

  WHY: an empty list must mean "none exists", not "the lookup broke" -- ``hcp``
  and ``sop`` instances have no solutions at all in the corpus.

  EXPECTED: an empty list.
  """
  root = _instance_tree(tmp_path)
  (root / "problems" / "tsp" / "c.tsp").write_text("NAME : c\n", encoding="utf-8")

  assert candidate_solution_files(root / "problems" / "tsp" / "c.tsp") == []


def _solution(source_file: str) -> ParsedSolution:
  """Build a minimal parsed solution for link tests (only ``source_file`` matters)."""
  return ParsedSolution(kind="SOL", quality="best_known", source_file=source_file, cost=1.0, routes=[[0]])


def test_link_attaches_the_single_matching_problem() -> None:
  """WHAT: one stored problem carries the solution's stem.

  EXPECTED: :class:`Linked` with that id.
  """
  result = link_solution(_solution("b.sol"), {"b": [ProblemRef(id=7, name="b", type="CVRP")]})

  assert isinstance(result, Linked)
  assert result.problem_id == 7


def test_link_reports_a_missing_instance() -> None:
  """WHAT: no stored problem carries the stem.

  WHY: 356 of the 390 ``.sol`` files belong to Holmberger/Solomon ``.txt``
  instances the scanner does not ingest yet, so this is the *common* case and it
  must be reported, not hidden behind ``None``.

  EXPECTED: :class:`Unlinked` with reason ``no_instance`` and no candidates.
  """
  result = link_solution(_solution("RC1_6_1.sol"), {})

  assert isinstance(result, Unlinked)
  assert result.reason == "no_instance"
  assert result.candidate_ids == ()


def test_link_refuses_an_ambiguous_stem() -> None:
  """WHAT: two stored problems share the stem -- the ``att48`` case.

  WHY: **CV10** -- the corpus ships ``att48.tsp`` and ``att48.vrp``, so a tour
  cannot be attributed without a guess. Returning either id would silently corrupt
  every downstream "solutions per type" aggregate.

  EXPECTED: :class:`Unlinked` with reason ``ambiguous`` and both ids, so the
  warning can name them.
  """
  refs = [ProblemRef(id=12, name="att48", type="CVRP"), ProblemRef(id=47, name="att48", type="TSP")]

  result = link_solution(_solution("att48.opt.tour"), {"att48": refs})

  assert isinstance(result, Unlinked)
  assert result.reason == "ambiguous"
  assert result.candidate_ids == (12, 47)


def test_link_matches_the_stem_case_insensitively() -> None:
  """WHAT: ``kroD100.opt.tour`` against a stored ``krod100`` key.

  WHY: the corpus mixes spellings; a case-sensitive lookup would turn a real
  instance into a false orphan.

  EXPECTED: :class:`Linked` to the stored id.
  """
  result = link_solution(
    _solution("/somewhere/kroD100.opt.tour"),
    {"krod100": [ProblemRef(id=3, name="kroD100", type="TSP")]},
  )

  assert isinstance(result, Linked)
  assert result.problem_id == 3


@pytest.mark.requires_dataset
def test_every_corpus_solution_is_discoverable_from_its_instance(datasets_raw_dir: Path) -> None:
  """WHAT: all 390 ``.sol`` files, reached from their instance's path.

  WHY: this is the completeness evidence for rule 1. If one solution could not be
  found from its own instance, the forward link (the precise direction) would be
  silently lossy.

  EXPECTED: for every ``.sol``, the sibling instance exists and discovers it.
  """
  solutions = sorted(datasets_raw_dir.rglob("*.sol"))
  assert len(solutions) == 390

  for path in solutions:
    instance = path.with_suffix(".vrp")
    if not instance.is_file():
      instance = path.with_suffix(".txt")
    assert instance.is_file(), f"{path.name}: no sibling instance"
    assert path in candidate_solution_files(instance), f"{path.name}: not discovered from {instance.name}"


@pytest.mark.requires_dataset
def test_every_corpus_tour_is_discoverable_from_exactly_one_instance(datasets_raw_dir: Path) -> None:
  """WHAT: all 82 tours, reached from their instance's path.

  WHY: rule 2 plus the ``TOUR_INSTANCE_SUFFIXES`` restriction. Measured before
  writing it: ``alb1000`` ships only as ``.hcp`` (so ``.hcp`` must be included),
  while ``att48``/``eil51`` ship as ``.tsp`` **and** ``.vrp`` (so ``.vrp`` must be
  excluded). Both directions of that set are exercised by the corpus.

  EXPECTED: exactly one instance per tour discovers it, and no route instance
  (``.vrp``/``.txt``) ever discovers a tour.
  """
  tours = sorted(datasets_raw_dir.rglob("*.opt.tour"))
  assert len(tours) == 82

  for tour in tours:
    family = tour.parent.parent
    stem = solution_stem(tour)
    instances = [
      instance
      for directory in ("tsp", "atsp", "sop", "hcp", "vrp")
      for suffix in (".tsp", ".atsp", ".sop", ".hcp", ".vrp", ".txt")
      if (instance := family / directory / f"{stem}{suffix}").is_file()
    ]
    owners = [instance for instance in instances if tour in candidate_solution_files(instance)]
    assert len(owners) == 1, f"{tour.name}: expected one owning instance, got {[str(o) for o in owners]}"
    assert owners[0].suffix.lower() in TOUR_INSTANCE_SUFFIXES, (
      f"{tour.name}: a single-cycle tour was claimed by {owners[0].name}"
    )
