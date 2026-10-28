"""Parse solution files (``*.opt.tour``, ``*.sol``) into :class:`ParsedSolution`.

This replaces ``DataTransformer.parse_solution_data`` (dead code, register item
**CV11**) with a parser that:

- reads **in memory** -- no temporary file is written to inject a missing
  ``DIMENSION`` line, which the old path needed only because it funnelled a tour
  through ``FormatParser`` (AGENTS §5.4). A tour file is a list of integers, not
  a TSPLIB problem;
- **raises** :class:`SolutionParseError` instead of returning ``None`` -- a
  malformed solution must never be indistinguishable from "no solution"
  (register item **S2**);
- normalises **each format against the array it indexes**, which is *not* one
  rule for both (measured 2026-10-24, correcting A2 via register item **CV14**):

| Format | File ids | Index into the problem's `coords`/`demands` |
| --- | --- | --- |
| ``*.sol`` (CVRPLIB) | customer ordinals, depot `0` never listed | ``index = id`` (the depot occupies index 0) |
| ``*.opt.tour`` (TSPLIB) | node numbers of a depot-free array | ``index = id - 1`` |

Evidence: recomputing each stated cost from the instance reproduces it only
under that frame -- ``vrp-XXL/Brussels1`` 501719.0 (nint), ``Vrp-Set-Li/Li_21``
16212.82548 (real), ``VRP-set-D/Loggi-n401-k23`` 336903.0 (explicit matrix), and
``tour/gr48.opt.tour`` 5046 (matrix, cycle). Under the wrong frame the same
computations are off by 17.9x, 0.5%, 224% and out of bounds respectively. A
contiguity sweep cannot see this defect: a uniform shift preserves contiguity.

Formats (measured 2026-10-23, see ``src/converter/TODO.md`` §CV10):

``*.opt.tour`` -- TSPLIB: optional ``COMMENT`` (sometimes carrying the cost),
optional ``DIMENSION``, then ``TOUR_SECTION`` with one cycle terminated by
``-1``.

``*.sol`` -- CVRPLIB: ``Route #N: <nodes>`` per vehicle (a route may wrap across
several physical lines) and a final ``Cost <value>`` line.

Linking a solution to a problem (**A3**) runs in two directions, and only one of
them can be ambiguous:

* forward -- :func:`candidate_solution_files` starts from a problem *path*, so
  the corpus layout itself decides (``X.vrp`` and ``X.sol`` are siblings;
  ``tsp/X.tsp`` and ``tour/X.opt.tour`` are cousins). Measured 2026-10-24:
  390/390 ``.sol`` files have a same-stem sibling, 82/82 tours sit in the
  ``tour`` directory next to their instance's directory.
* backward -- :func:`link_solution` starts from a solution *file* and sees only
  a stem, so it can face several stored problems with that name. It then
  returns :class:`Unlinked` instead of picking one (**CV10**).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from converter.core.contracts import ParsedSolution, ProblemRef
from converter.types import SolutionKind, UnlinkReason
from converter.utils.exceptions import ExtractionError

#: Suffix of a TSPLIB optimal-tour file.
TOUR_SUFFIX = ".tour"

#: Name a TSPLIB optimal tour carries in the corpus (``gr48.opt.tour``).
#: ``TOUR_SUFFIX`` is what the parser dispatches on, so a plain ``X.tour`` also
#: parses; discovery looks for ``.opt.tour`` because all 82 corpus tours use it.
OPT_TOUR_SUFFIX = ".opt.tour"

#: Suffix of a CVRPLIB solution file.
SOL_SUFFIX = ".sol"

#: ``Route #3: 12 84 91`` -- the header only. The body is accumulated line by
#: line because large XXL routes wrap across several physical lines, and a regex
#: over the whole text silently truncates a body at the first non-digit
#: (``Route #1: 1.0 2 3`` used to yield ``[0]``).
_ROUTE_HEADER_RE = re.compile(r"^\s*Route\s*#\s*(\d+)\s*:", re.IGNORECASE)

#: ``Cost 1234.5``; signed and scientific notation accepted because the old
#: ``([\d.]+)`` pattern silently failed on both.
_COST_RE = re.compile(r"^\s*Cost\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", re.MULTILINE | re.IGNORECASE)

#: The two cost shapes the corpus comments actually use: ``... gr666 (294358)``,
#: ``(Length 629)`` and ``Length 6110``. Bare numbers are not matched on purpose:
#: ``Optimum solution of bayg29`` carries a digit inside the name.
_COMMENT_COST_RE = re.compile(r"\(\s*(?:Length\s+)?(\d+(?:\.\d+)?)\s*\)|\bLength\s+(\d+(?:\.\d+)?)", re.IGNORECASE)

_DIMENSION_KEYWORD = "DIMENSION"
_TOUR_SECTION_KEYWORD = "TOUR_SECTION"
_FILE_TERMINATOR = "EOF"
_ENTRY_TERMINATOR = "-1"


class SolutionParseError(ExtractionError):
  """Raised when a solution file cannot be parsed.

  A solution is either parsed completely or reported as failed; there is no
  partial result and no ``None`` return.
  """


def _read_text(path: Path) -> str:
  """Read a solution file, falling back to latin-1 for non-UTF-8 bytes.

  The previous implementation passed an encoding name in the *error handler*
  slot (``errors="latin-1"``), which CPython resolves lazily: pure-ASCII files
  parsed and the first non-UTF-8 byte raised ``LookupError`` (register item
  **M9**). Decoding twice is the correct form of that fallback.

  An unreadable file is reported through the same exception as a malformed one:
  a solution that disappeared between the scan and the parse must not kill a
  batch with an error type nobody catches.
  """
  try:
    try:
      return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
      return path.read_text(encoding="latin-1")
  except OSError as exc:
    raise SolutionParseError(f"cannot read solution file: {exc}", problem_name=path.name) from exc


def _to_index(token: str, *, path: Path, kind: SolutionKind) -> int:
  """Convert one node id from the file to an index into the instance's arrays.

  The frame is **per format**, not shared: ``*.sol`` ids are customer ordinals
  over an array whose index 0 is the depot (``index = id``), while ``*.opt.tour``
  ids number a depot-free array (``index = id - 1``). Measured by recomputing the
  stated costs, see the module docstring.
  """
  try:
    node_id = int(token)
  except ValueError as exc:
    raise SolutionParseError(f"node id {token!r} is not an integer", problem_name=path.name) from exc
  if node_id == 0:
    raise SolutionParseError("node id 0 is the depot and is never listed", problem_name=path.name)
  if node_id < 0:
    raise SolutionParseError(f"negative node id {node_id}", problem_name=path.name)
  return node_id if kind == "SOL" else node_id - 1


def _cost_from_comment(comment: str) -> float | None:
  """Extract the cost a ``COMMENT`` line states, if it states one.

  Three shapes occur: ``(294358)``, ``(Length 629)`` and ``Length 6110``. Bare
  numbers are ignored -- ``Optimum solution of bayg29`` would otherwise report 29.
  """
  match = _COMMENT_COST_RE.search(comment)
  if not match:
    return None
  return float(match.group(1) or match.group(2))


def _parse_tour(path: Path) -> ParsedSolution:
  """Parse a TSPLIB ``*.opt.tour`` file into a single 0-based route."""
  comment = ""
  nodes: list[int] = []
  dimension: int | None = None
  in_section = False
  saw_section = False
  saw_terminator = False

  for raw_line in _read_text(path).splitlines():
    line = raw_line.strip()
    if not line:
      continue
    upper = line.upper()
    if upper.startswith(_FILE_TERMINATOR):
      break
    if not in_section:
      if saw_terminator and not upper.startswith(_TOUR_SECTION_KEYWORD):
        raise SolutionParseError("node data after the tour terminator", problem_name=path.name)
      if upper.startswith("COMMENT"):
        comment = line.split(":", 1)[1].strip() if ":" in line else ""
      elif upper.startswith(_DIMENSION_KEYWORD):
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        dimension = int(value) if value.isdigit() else None
      elif upper.startswith(_TOUR_SECTION_KEYWORD):
        if saw_section:
          raise SolutionParseError("a second TOUR_SECTION follows the first", problem_name=path.name)
        in_section = True
        saw_section = True
      continue
    for token in line.split():
      if token == _ENTRY_TERMINATOR:
        in_section = False
        saw_terminator = True
        break
      nodes.append(_to_index(token, path=path, kind="OPT_TOUR"))

  if not saw_section:
    raise SolutionParseError("no TOUR_SECTION found", problem_name=path.name)
  if not nodes:
    raise SolutionParseError("TOUR_SECTION is empty", problem_name=path.name)
  if len(set(nodes)) != len(nodes):
    raise SolutionParseError("a node is visited twice", problem_name=path.name)
  if dimension is not None and len(nodes) != dimension:
    raise SolutionParseError(
      f"the tour lists {len(nodes)} nodes but DIMENSION is {dimension}",
      problem_name=path.name,
    )

  return ParsedSolution(
    kind="OPT_TOUR",
    quality="proven_optimal",
    source_file=str(path),
    cost=_cost_from_comment(comment),
    routes=[nodes],
  )


def _parse_sol(path: Path) -> ParsedSolution:
  """Parse a CVRPLIB ``*.sol`` file into one 0-based route per vehicle."""
  text = _read_text(path)

  routes: list[list[int]] = []
  body: list[int] | None = None
  last_route_number = 0

  for raw_line in text.splitlines():
    line = raw_line.strip()
    if not line:
      continue
    if header := _ROUTE_HEADER_RE.match(line):
      route_number = int(header.group(1))
      if route_number <= last_route_number:
        raise SolutionParseError(f"route #{route_number} is out of order", problem_name=path.name)
      last_route_number = route_number
      body = []
      routes.append(body)
      line = line[header.end() :]
    if _COST_RE.match(line):
      body = None
      continue
    if body is None:
      # Text before the first route, or after the Cost line, is not route data.
      continue
    body.extend(_to_index(token, path=path, kind="SOL") for token in line.split())

  if not routes:
    raise SolutionParseError("no 'Route #N:' lines found", problem_name=path.name)
  if any(not route for route in routes):
    raise SolutionParseError("a route has no customers", problem_name=path.name)
  visited = [node for route in routes for node in route]
  if len(set(visited)) != len(visited):
    raise SolutionParseError("a customer is served twice", problem_name=path.name)
  if sorted(visited) != list(range(1, len(visited) + 1)):
    raise SolutionParseError(
      "the routes are not a complete 1..n customer set (index = id, depot 0 excluded)",
      problem_name=path.name,
    )

  cost_match = _COST_RE.search(text)
  return ParsedSolution(
    kind="SOL",
    quality="best_known",
    source_file=str(path),
    cost=float(cost_match.group(1)) if cost_match else None,
    routes=routes,
  )


def parse_solution_file(path: str | Path) -> ParsedSolution:
  """Parse a solution file, dispatching on its suffix.

  Parameters
  ----------
  path : str or Path
      ``*.opt.tour`` (TSPLIB single tour) or ``*.sol`` (CVRPLIB routes).

  Returns
  -------
  ParsedSolution
      Kind, quality claim, cost (``None`` when the file carries none) and
      0-based routes with the depot excluded.

  Raises
  ------
  SolutionParseError
      Unknown suffix, no routes, an empty section, or a node id that is not a
      positive integer.
  """
  solution_path = Path(path)
  suffix = solution_path.suffix.lower()

  if suffix == SOL_SUFFIX:
    return _parse_sol(solution_path)
  if suffix == TOUR_SUFFIX:
    return _parse_tour(solution_path)
  raise SolutionParseError(f"unsupported solution format {suffix!r}", problem_name=solution_path.name)


#: Directory, next to a problem's own directory, that holds the optimal tours.
#: A measured property of the TSPLIB distribution, not a guess: all 82 corpus
#: tours live in ``<family>/tour/X.opt.tour`` while their instance is
#: ``<family>/tsp/X.tsp``.
TOUR_DIR_NAME = "tour"

#: Instance suffixes whose solution can be a single cycle in ``tour/``.
#:
#: Measured 2026-10-24 over the whole corpus: the 82 tours belong to 64 ``.tsp``
#: and 18 ``.hcp`` instances (``alb1000``/``alb2000``/... ship **only** as
#: ``.hcp`` and still have tours), and ``att48``/``eil51`` exist as both ``.tsp``
#: and ``.vrp`` -- so the ``.vrp`` twin must be excluded or it would claim the
#: TSP tour, the silent wrong link **CV10** exists to prevent.
#:
#: ``.atsp`` and ``.sop`` are deliberately **absent**: no corpus evidence, and an
#: SOP answer is a precedence-constrained path rather than a single cycle. Adding
#: them without a fixture would be a rule that cannot fail (AGENTS §5.8).
TOUR_INSTANCE_SUFFIXES: frozenset[str] = frozenset({".tsp", ".hcp"})


@dataclass(frozen=True, slots=True)
class Linked:
  """A solution that belongs to exactly one stored problem."""

  problem_id: int


@dataclass(frozen=True, slots=True)
class Unlinked:
  """A solution that belongs to no problem, or to several.

  ``candidate_ids`` is empty for ``no_instance`` and holds every contender for
  ``ambiguous``, so the caller can name them in the warning instead of guessing
  (register item **CV10**).
  """

  reason: UnlinkReason
  candidate_ids: tuple[int, ...] = ()


#: Result of linking one solution file. Two named shapes instead of ``int | None``
#: because "no instance" and "several instances" need different reporting, and
#: ``None`` cannot carry that distinction (AGENTS §5.5).
LinkResult = Linked | Unlinked


def solution_stem(path: str | Path) -> str:
  """Return the instance name a solution file belongs to.

  ``gr48.opt.tour`` and ``gr48.sol`` both give ``gr48``. ``Path.stem`` alone
  would return ``gr48.opt`` for the first one, producing a stem that matches no
  problem. Comparison is case-insensitive in both steps, matching
  :func:`candidate_solution_files`.
  """
  name = Path(path).name
  if not name.lower().endswith(TOUR_SUFFIX):
    return Path(name).stem
  stem = name[: -len(TOUR_SUFFIX)]
  return stem[: -len(".opt")] if stem.lower().endswith(".opt") else stem


def candidate_solution_files(problem_path: str | Path) -> list[Path]:
  """Return the solution files that belong to ``problem_path`` by location.

  Two structural rules, both measured over the whole corpus on 2026-10-24:

  1. a sibling with the same stem and a ``.sol`` suffix -- 390/390 CVRPLIB
     solutions (Holmberger ``.txt`` and ``.vrp`` instances alike) sit next to
     their instance;
  2. ``<parent>/tour/<stem>.opt.tour`` for an instance whose suffix is in
     :data:`TOUR_INSTANCE_SUFFIXES` -- 82/82 TSPLIB tours, in both corpus trees.
  Rule 2 is restricted because a tour is a single cycle: ``att48.vrp`` and
  ``att48.tsp`` share a stem, and only the ``.tsp`` twin ships the tour.

  This direction cannot be ambiguous: the corpus layout already says which
  instance the file belongs to, which is why the forward link resolves the
  ``att48`` / ``eil51`` tours that the stem-based backward link must refuse.

  Only existing files are returned, in the order above. An empty list means the
  corpus ships no solution for this instance (``hcp`` and ``sop`` have none),
  not that the lookup failed.
  """
  problem = Path(problem_path)
  candidates = [problem.with_suffix(SOL_SUFFIX)]
  if problem.suffix.lower() in TOUR_INSTANCE_SUFFIXES:
    candidates.append(problem.parent.parent / TOUR_DIR_NAME / f"{problem.stem}{OPT_TOUR_SUFFIX}")
  return [candidate for candidate in candidates if candidate.is_file()]


def link_solution(
  parsed: ParsedSolution,
  problems_by_stem: Mapping[str, Sequence[ProblemRef]],
) -> LinkResult:
  """Attach a parsed solution to a stored problem, or explain why it cannot be.

  Parameters
  ----------
  parsed : ParsedSolution
      The solution to link; only ``source_file`` is read.
  problems_by_stem : Mapping[str, Sequence[ProblemRef]]
      Stored problems keyed by **lowercase** instance stem. Lowercase because the
      corpus mixes spellings (``kroD100.opt.tour`` ships with ``kroD100.tsp``)
      while the file header may spell the name differently, and a case mismatch
      would turn a real instance into a false orphan.

  Returns
  -------
  LinkResult
      :class:`Linked` when exactly one problem matches, otherwise
      :class:`Unlinked` with the reason -- ``no_instance`` (nothing to attach to)
      or ``ambiguous`` (two or more problems share the stem, **CV10**). The
      solution is never attached to a guess.
  """
  contenders = tuple(problems_by_stem.get(solution_stem(parsed["source_file"]).lower(), ()))
  if len(contenders) == 1:
    return Linked(problem_id=contenders[0]["id"])
  if not contenders:
    return Unlinked(reason="no_instance")
  return Unlinked(reason="ambiguous", candidate_ids=tuple(ref["id"] for ref in contenders))
