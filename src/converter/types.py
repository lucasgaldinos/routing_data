"""Value vocabularies for the converter.

This module is the single place where a closed set of allowed values is written
down: the ``Literal`` is the declaration, and the runtime tuple is derived from
it with ``typing.get_args`` so nothing can drift.

Three families of "type" live in three different places, deliberately:

- **value vocabulary** (which values are legal) -> here, ``converter/types.py``
- **boundary shape** (which fields travel together across a layer) ->
  ``converter/core/contracts.py``
- **domain model** (data + behaviour) -> the module that owns it

The problem taxonomy is *not* here: it belongs to ``tsplib_parser.types`` and
duplicating it is register item **M12**. This module therefore imports nothing
from the package, so it can be used by parsers, writers and the database layer
alike.

Naming mirrors ``tsplib_parser/types.py``: a package-level ``types`` module that
owns vocabularies.
"""

from typing import Literal, get_args

#: Source format of a solution file.
#:
#: - ``OPT_TOUR`` -- a TSPLIB ``*.opt.tour``: one cycle, no cost line.
#: - ``SOL`` -- a CVRPLIB ``*.sol``: several vehicle routes plus a ``Cost`` line.
#:
#: Hardcoded exactly once. Every consumer (parser dispatch, insert validation,
#: run summaries, the SQL ``CHECK``) reads it from here, and the schema contract
#: test compares the stored constraint against this tuple.
SolutionKind = Literal["OPT_TOUR", "SOL"]
SOLUTION_KINDS: tuple[SolutionKind, ...] = get_args(SolutionKind)

#: What the source claims about the solution's quality.
#:
#: A boolean ``is_optimal`` was rejected because it merged two different states:
#:
#: - ``proven_optimal`` -- the distribution ships the file as an optimal tour
#:   (TSPLIB ``*.opt.tour``) or marks the value as proven optimal (VRP-REP ``*``).
#: - ``best_known`` -- cheapest solution found so far, no proof (CVRPLIB ``*.sol``).
#: - ``unknown`` -- the source makes no claim at all.
SolutionQuality = Literal["proven_optimal", "best_known", "unknown"]
SOLUTION_QUALITIES: tuple[SolutionQuality, ...] = get_args(SolutionQuality)

#: Why a solution file could not be attached to a problem.
#:
#: - ``no_instance`` -- no stored problem carries that stem (its instance was
#:   never ingested, e.g. the 356 Holmberger ``.txt`` instances, or no instance
#:   exists for that name at all).
#: - ``ambiguous`` -- several stored problems share the stem, so any pick would be
#:   a guess (register item **CV10**). Measured 2026-10-24: three stems exist as
#:   both ``.tsp`` and ``.vrp`` (``att48``, ``eil51``, ``gil262``); two of them
#:   ship a tour, so two tour files (four paths, the corpus holds two identical
#:   trees) are ambiguous.
#:
#: The distinction matters for the run summary: ``no_instance`` shrinks by itself
#: once the missing parsers exist, ``ambiguous`` needs a human decision.
UnlinkReason = Literal["no_instance", "ambiguous"]
UNLINK_REASONS: tuple[UnlinkReason, ...] = get_args(UnlinkReason)
