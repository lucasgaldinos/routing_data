"""Boundary shapes for the converter.

A *contract* is a shape that crosses a layer: producer -> consumer, function ->
database, worker -> parent process. Every field here is named and fixed, so the
two sides of a boundary cannot disagree about what is being passed.

This is not a second ``types`` module (see ``converter/types.py``): the
vocabularies live there, the shapes live here. The split exists because the two
change for different reasons -- a new allowed value is a rare domain decision,
while a new contract field follows an integration -- and because a single module
imported by everything becomes impossible to change.

Only ``TypedDict`` declarations belong here. No logic, no defaults beyond what a
``NotRequired`` marker states, no database access.
"""

from typing import TypedDict

from converter.types import SolutionKind, SolutionQuality


class ProblemRef(TypedDict):
  """One stored problem, as the linker needs to see it.

  A projection of a ``problems`` row, not the row itself: the linker only needs
  the identity, the name, and the type (the parenthetical in an ambiguity
  warning). ``name`` and ``type`` are what the two ``att48`` rows disagree on,
  which is the whole reason the link is refused instead of guessed.
  """

  id: int
  name: str
  type: str


class ParsedSolution(TypedDict):
  """A solution file as its own parser can describe it.

  Everything here is knowable from the file alone. Deliberately excludes the
  problem link: only the linker can resolve which instance a solution belongs
  to, and a ``problem_id: None`` placeholder here would lie about which layer
  fills it (that is what :class:`SolutionPayload` is for).
  """

  kind: SolutionKind
  quality: SolutionQuality
  source_file: str
  cost: float | None
  routes: list[list[int]]


class SolutionPayload(ParsedSolution):
  """A parsed solution plus the problem it was linked to.

  ``problem_id`` is ``None`` when the link is unknowable -- the instance was
  never ingested, or its stem matches several instances (register item **CV10**,
  e.g. ``att48.tsp`` and ``att48.vrp``). An unattached row is stored as-is and
  reported; it is never attached to a guess.
  """

  problem_id: int | None
