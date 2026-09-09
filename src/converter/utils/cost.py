"""Solution-cost backfill: compute route length at ETL from the problem's weight data.

User decision (pinned 2026-08-28, plan Task 2.2): when a solution's cost is not
present in the source file (e.g. ``.opt.tour`` files without a length COMMENT),
compute the route length from the problem's weight data — the EXPLICIT
edge-weight matrix when available, otherwise the coordinates + EDGE_WEIGHT_TYPE
distance function. Problems without usable weight data (e.g. unweighted HCP
adjacency) keep a NULL ``solutions.cost``.

Distance semantics follow the TSPLIB95 spec and match the main repo's
``src/distances/pairwise.py`` so benchmark consumers see identical lengths:

- ``nint(x) = int(x + 0.5)`` (C ``nint``).
- GEO uses the spherical law of cosines with TSPLIB's ``R = 6378.388`` km and
  ``PI = 3.141592``; the result is ``int(d + 1.0)``.
- ATT uses the pseudo-Euclidean formula with the conditional ``+1``.
"""

import math
from collections.abc import Callable, Sequence
from typing import Any


def _nint(x: float) -> int:
  """Round to nearest integer (TSPLIB95 convention, C ``nint``)."""
  return int(x + 0.5)


def _euclidean_2d(a: Sequence[float], b: Sequence[float]) -> int:
  xd: float = a[0] - b[0]
  yd: float = a[1] - b[1]
  return _nint(math.sqrt(xd * xd + yd * yd))


def _euclidean_3d(a: Sequence[float], b: Sequence[float]) -> int:
  xd: float = a[0] - b[0]
  yd: float = a[1] - b[1]
  zd: float = a[2] - b[2]
  return _nint(math.sqrt(xd * xd + yd * yd + zd * zd))


def _ceiling_2d(a: Sequence[float], b: Sequence[float]) -> int:
  xd: float = a[0] - b[0]
  yd: float = a[1] - b[1]
  return math.ceil(math.sqrt(xd * xd + yd * yd))


def _manhattan_2d(a: Sequence[float], b: Sequence[float]) -> int:
  return _nint(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def _manhattan_3d(a: Sequence[float], b: Sequence[float]) -> int:
  return _nint(abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]))


def _maximum_2d(a: Sequence[float], b: Sequence[float]) -> int:
  return max(_nint(abs(a[0] - b[0])), _nint(abs(a[1] - b[1])))


def _maximum_3d(a: Sequence[float], b: Sequence[float]) -> int:
  return max(
    _nint(abs(a[0] - b[0])),
    _nint(abs(a[1] - b[1])),
    _nint(abs(a[2] - b[2])),
  )


def _to_radians_geo(coord_val: float) -> float:
  """Convert a TSPLIB95 DDD.MM geographic coordinate to radians."""
  deg: int = _nint(coord_val)
  minutes: float = coord_val - deg
  return 3.141592 * (deg + 5.0 * minutes / 3.0) / 180.0


def _geographical(a: Sequence[float], b: Sequence[float]) -> int:
  lat1: float = _to_radians_geo(a[0])
  lon1: float = _to_radians_geo(a[1])
  lat2: float = _to_radians_geo(b[0])
  lon2: float = _to_radians_geo(b[1])
  q1: float = math.cos(lon1 - lon2)
  q2: float = math.cos(lat1 - lat2)
  q3: float = math.cos(lat1 + lat2)
  acos_arg: float = 0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)
  acos_arg = max(-1.0, min(1.0, acos_arg))
  return int(6378.388 * math.acos(acos_arg) + 1.0)


def _att(a: Sequence[float], b: Sequence[float]) -> int:
  xd: float = a[0] - b[0]
  yd: float = a[1] - b[1]
  rij: float = math.sqrt((xd * xd + yd * yd) / 10.0)
  tij: int = _nint(rij)
  return tij + 1 if tij < rij else tij


#: Coordinate-based EDGE_WEIGHT_TYPE -> TSPLIB95 distance function.
_COORD_DISTANCES: dict[str, Callable[[Sequence[float], Sequence[float]], int]] = {
  "EUC_2D": _euclidean_2d,
  "EUC_3D": _euclidean_3d,
  "CEIL_2D": _ceiling_2d,
  "MAN_2D": _manhattan_2d,
  "MAN_3D": _manhattan_3d,
  "MAX_2D": _maximum_2d,
  "MAX_3D": _maximum_3d,
  "GEO": _geographical,
  "ATT": _att,
}


def _matrix_distance(matrix: Sequence[Sequence[Any]]) -> Callable[[int, int], int]:
  """Build a 0-based node-id edge-weight callable from an EXPLICIT matrix."""

  def _distance(i: int, j: int) -> int:
    return int(matrix[i][j])

  return _distance


def _coord_distance(
  coords: Sequence[Sequence[float]],
  fn: Callable[[Sequence[float], Sequence[float]], int],
) -> Callable[[int, int], int]:
  """Build a 0-based node-id edge-weight callable from coordinates + a distance fn."""

  def _distance(i: int, j: int) -> int:
    return fn(coords[i], coords[j])

  return _distance


def _route_length(route: Sequence[int], distance: Callable[[int, int], int]) -> float:
  """Length of one closed route under a 0-based edge-weight callable.

  TSPLIB tours are open in the file (the start node is not repeated), so the
  closing edge back to the start is part of the tour length; it is added
  unless the route already repeats its first node.
  """
  if len(route) < 2:
    return 0.0
  total: int = 0
  for i in range(len(route) - 1):
    total += distance(route[i], route[i + 1])
  if route[0] != route[-1]:
    total += distance(route[-1], route[0])
  return float(total)


def compute_routes_cost(
  routes: Sequence[Sequence[int]],
  *,
  matrix: Sequence[Sequence[Any]] | None = None,
  coords: Sequence[Sequence[float]] | None = None,
  edge_weight_type: str | None = None,
) -> float | None:
  """Compute the total cost of solution routes from the problem's weight data.

  Prefers the EXPLICIT ``matrix`` (rows/cols are 0-based node ids); falls
  back to ``coords`` + ``edge_weight_type`` for coordinate-based types.
  Returns ``None`` when no weight source is available or the type is
  unsupported — the caller then leaves ``solutions.cost`` NULL (e.g.
  unweighted HCP adjacency).
  """
  distance: Callable[[int, int], int] | None = None
  if matrix is not None:
    distance = _matrix_distance(matrix)
  elif coords is not None and edge_weight_type:
    fn: Callable[[Sequence[float], Sequence[float]], int] | None = _COORD_DISTANCES.get(str(edge_weight_type).upper())
    if fn is not None:
      distance = _coord_distance(coords, fn)
  if distance is None:
    return None
  return sum(_route_length(route, distance) for route in routes)
