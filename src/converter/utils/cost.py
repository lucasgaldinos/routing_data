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
- XRAY1/XRAY2 use the crystallography distance (TSPLIB95 §2.7, the ``DEQ`` and
  ``DUN`` routines distributed in ``xray.problems``): the three motor
  coordinates are compared axis by axis, the x-difference wrapped at 360°,
  each difference divided by its motor speed, and the largest scaled
  difference multiplied by 100 and rounded. XRAY1 assumes equal speeds
  (``1.00, 1.0, 1.00``); XRAY2 uses ``1.25, 1.5, 1.15``.
"""

import math
from collections.abc import Callable, Sequence
from typing import Any

from tsplib_parser.exceptions import FormatError, UnsupportedFeatureError
from tsplib_parser.types import EDGE_WEIGHT_TYPES


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


def _xray(a: Sequence[float], b: Sequence[float], *, sx: float, sy: float, sz: float) -> int:
  """Crystallography distance with per-axis motor speeds (TSPLIB95 §2.7).

  The three coordinates are the positions of three motors; the x-axis is an
  angle, so its difference wraps at 360°. Each axis difference is scaled by its
  motor speed and the largest scaled difference decides the distance, which the
  spec multiplies by 100 to stay integral.
  """
  phi: float = abs(a[0] - b[0])
  dist_phi: float = min(phi, abs(phi - 360.0))
  dist_chi: float = abs(a[1] - b[1])
  dist_two_theta: float = abs(a[2] - b[2])
  cost: float = max(dist_phi / sx, dist_chi / sy, dist_two_theta / sz)
  return _nint(100.0 * cost)


def _xray1(a: Sequence[float], b: Sequence[float]) -> int:
  """``EDGE_WEIGHT_TYPE: XRAY1`` — motors at equal speed (``DEQ`` routine)."""
  return _xray(a, b, sx=1.00, sy=1.0, sz=1.00)


def _xray2(a: Sequence[float], b: Sequence[float]) -> int:
  """``EDGE_WEIGHT_TYPE: XRAY2`` — motors at different speeds (``DUN`` routine)."""
  return _xray(a, b, sx=1.25, sy=1.5, sz=1.15)


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
  "XRAY1": _xray1,
  "XRAY2": _xray2,
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


def supported_weight_types() -> frozenset[str]:
  """``EDGE_WEIGHT_TYPE`` values this module can turn into distances.

  Every coordinate type of the TSPLIB95 vocabulary except ``SPECIAL`` — which
  has no formula (the caller must supply one) — plus ``EXPLICIT``, whose
  distances come from the matrix argument rather than from this registry. Lets a
  caller record "no cost function exists" without provoking an exception.
  """
  return frozenset(_COORD_DISTANCES) | {"EXPLICIT"}


def _coordinate_function(
  edge_weight_type: str,
  special: Callable[[Sequence[float], Sequence[float]], int] | None,
) -> Callable[[Sequence[float], Sequence[float]], int] | None:
  """Distance function for one coordinate-based ``EDGE_WEIGHT_TYPE``.

  Returns ``None`` for the one type whose weights do not come from this
  registry: ``EXPLICIT``, whose entries arrive in the matrix argument.

  Raises
  ------
  UnsupportedFeatureError
      ``SPECIAL`` without a callable, or a TSPLIB95 weight type with no
      implementation in the registry.
  FormatError
      Not a TSPLIB95 weight type at all (typo, garbage) — never a ``KeyError``.
  """
  key: str = edge_weight_type.upper()
  registered: Callable[[Sequence[float], Sequence[float]], int] | None = _COORD_DISTANCES.get(key)
  if registered is not None:
    return registered
  if key == "SPECIAL":
    if special is None:
      raise UnsupportedFeatureError("EDGE_WEIGHT_TYPE SPECIAL requires a supplied distance function")
    return special
  if key == "EXPLICIT":
    return None
  if key in EDGE_WEIGHT_TYPES:
    # Keep this branch: it is unreachable today only because every type of the
    # vocabulary is either registered above or handled here, and the vocabulary
    # is the spec's, growing independently of this registry. P2 requires the gap
    # to be reported — as a legal-but-unimplemented type, not as a malformed
    # file and not as the "no weight source" ``None``.
    raise UnsupportedFeatureError(f"EDGE_WEIGHT_TYPE {key} has no implementation in the distance registry")
  raise FormatError(f"Unknown EDGE_WEIGHT_TYPE: {key}")


def compute_routes_cost(
  routes: Sequence[Sequence[int]],
  *,
  matrix: Sequence[Sequence[Any]] | None = None,
  coords: Sequence[Sequence[float]] | None = None,
  edge_weight_type: str | None = None,
  special: Callable[[Sequence[float], Sequence[float]], int] | None = None,
) -> float | None:
  """Compute the total cost of solution routes from the problem's weight data.

  Prefers the EXPLICIT ``matrix`` (rows/cols are 0-based node ids); otherwise
  builds a distance callable from ``coords`` + ``edge_weight_type``. Returns
  ``None`` only when there is no weight source at all — no matrix, no
  coordinates, or ``EXPLICIT`` without its matrix (an unweighted problem such as
  HCP adjacency). A *known* weight type with no implementation is a failure, not
  a silent ``None``: see Raises.

  ``special`` is used only when the file declares ``EDGE_WEIGHT_TYPE: SPECIAL``,
  the one type whose formula TSPLIB95 does not define. Supplying it next to any
  other type is a caller mistake and raises, rather than being ignored the way
  the removed ``special_func`` parameter was (``PB1``).

  ``None`` means "no weight source at all", and has four causes: no matrix and no
  coordinates; ``EXPLICIT`` without its matrix; coordinates without an
  ``edge_weight_type`` (a file that is broken per §1.1.6 — reported by
  ``validate_problem_data``, not here); and a type whose distances do not exist
  at all (``HCP`` carries edges, ``TOUR`` is a recorded solution).

  Raises
  ------
  ValueError
      ``special`` supplied for a file that does not declare ``SPECIAL``.
  UnsupportedFeatureError
      The file declares ``SPECIAL`` without a supplied ``special`` callable, or
      a TSPLIB95 weight type that has no implementation here.
  FormatError
      ``edge_weight_type`` is not a TSPLIB95 weight type at all (typo, garbage)
      — never a bare ``KeyError``.
  """
  distance: Callable[[int, int], int] | None = None
  if special is not None and (edge_weight_type is None or edge_weight_type.upper() != "SPECIAL"):
    # A caller/config error, not a data error: whoever passed the callable and
    # whoever declared the weight type disagree, and the callable would otherwise
    # vanish without a trace.
    raise ValueError(f"special= is only used by EDGE_WEIGHT_TYPE SPECIAL; the declared type is {edge_weight_type!r}.")
  if matrix is not None:
    distance = _matrix_distance(matrix)
  elif coords is not None and edge_weight_type:
    function: Callable[[Sequence[float], Sequence[float]], int] | None = _coordinate_function(edge_weight_type, special)
    if function is not None:
      distance = _coord_distance(coords, function)

  if distance is None:
    return None
  return sum(_route_length(route, distance) for route in routes)
