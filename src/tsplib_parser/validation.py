"""Validation utilities for TSPLIB95 format parsing.

Provides two-stage validation for TSPLIB95 problems:
1. ``validate_problem_data``: Pre-extraction validation on the 1-based raw
   ``StandardProblem`` dictionary (keywords, vocabularies, section key
   bijections ``1..dimension``, coordinate dimensions, and cross-field
   invariants).
2. ``validate_parse_result``: Post-extraction validation on the 0-based
   ``ParseResult`` contract produced by ``FormatParser.parse_file`` (runtime
   types, 0-based index bounds ``0..dimension-1``, array lengths vs
   ``DIMENSION``, ``Matrix.size == dimension``, and metadata consistency).
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from . import matrix
from .fields import DemandsField, IndexedCoordinatesField
from .models import StandardProblem
from .types import (
  DISPLAY_DATA_TYPES,
  EDGE_DATA_FORMATS,
  EDGE_WEIGHT_TYPES,
  FUNCTIONAL_EDGE_WEIGHT_FORMATS,
  NODE_COORD_TYPES,
  THREED_WEIGHT_TYPES,
  TWOD_WEIGHT_TYPES,
  VALID_PROBLEM_TYPES,
  WeightSource,
  normalize_problem_type,
)

if TYPE_CHECKING:
  from tsplib_parser.fields import Field

#: Types whose distances come from the declared ``EDGE_WEIGHT_TYPE``, which is
#: therefore mandatory for them (spec §1.1.6). ``HCP`` carries its edges in
#: ``EDGE_DATA_SECTION`` and ``TOUR`` is a recorded solution: those are the only
#: corpus files without the keyword (9 and 41 of the 239).
WEIGHT_BEARING_TYPES: frozenset[str] = frozenset({"TSP", "ATSP", "SOP", "CVRP", "VRP"})

#: Valid ``metadata["weight_source"]`` values.
VALID_WEIGHT_SOURCES: frozenset[str] = frozenset(
  {"explicit_matrix", "explicit_function", "coordinate_based", "special_function", "unweighted"}
)

#: Expected top-level keys of ``ParseResult``.
PARSE_RESULT_KEYS: frozenset[str] = frozenset(
  {
    "problem_data",
    "coords",
    "display_coords",
    "demands",
    "depots",
    "edges",
    "fixed_edges",
    "tours",
    "metadata",
  }
)


def _is_int(value: Any) -> bool:
  """Return True when ``value`` is a true ``int`` (excluding ``bool``)."""
  return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
  """Return True when ``value`` is an ``int`` or ``float`` (excluding ``bool``)."""
  return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_dict(value: object) -> TypeGuard[dict[Any, Any]]:
  """Narrow ``value`` to a mapping of untyped keys to untyped values."""
  return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[Any]]:
  """Narrow ``value`` to a list of untyped items."""
  return isinstance(value, list)


def _is_number_row(value: object, min_len: int) -> bool:
  """Return True when ``value`` is a tuple/list holding at least ``min_len`` numbers."""
  if not isinstance(value, (tuple, list)):
    return False
  row: Sequence[object] = cast("Sequence[object]", value)
  return len(row) >= min_len and all(_is_number(x) for x in row)


def _is_int_list(value: object) -> bool:
  """Return True when ``value`` is a list of true ints (``bool`` excluded)."""
  if not isinstance(value, list):
    return False
  items: list[object] = cast("list[object]", value)
  return all(_is_int(x) for x in items)


def _is_int_pair(value: object) -> bool:
  """Return True when ``value`` is a 2-element tuple/list of true ints."""
  if not isinstance(value, (tuple, list)):
    return False
  pair: Sequence[object] = cast("Sequence[object]", value)
  return len(pair) == 2 and all(_is_int(x) for x in pair)


def _is_float_list(value: object, exact_len: int | None = None) -> bool:
  """Return True when ``value`` is a list of floats, optionally of ``exact_len``."""
  if not isinstance(value, list):
    return False
  items: list[object] = cast("list[object]", value)
  if exact_len is not None and len(items) != exact_len:
    return False
  return all(isinstance(x, float) for x in items)


def _format_node_list(nodes: list[Any], limit: int = 10) -> str:
  """Format a list of node keys with an ellipsis suffix when truncated."""
  shown: list[Any] = nodes[:limit]
  suffix: str = f" (and {len(nodes) - len(shown)} more)" if len(nodes) > len(shown) else ""
  return f"{shown}{suffix}"


def check_symmetry(
  problem_type: str | None,
  edge_weight_type: str | None,
  matrix_obj: matrix.Matrix | None = None,
) -> bool | None:
  """Determine whether a routing problem has symmetric distances (PB2 / P5).

  - Unweighted problems (``HCP``, ``TOUR`` without ``EDGE_WEIGHT_TYPE``): ``None``.
  - ``ATSP`` and ``SOP``: ``False`` (directed / precedence-constrained).
  - ``EXPLICIT`` matrix problems: verified directly across all ``(i, j)`` pairs
    in ``matrix_obj`` (``matrix_obj.value_at(i, j) == matrix_obj.value_at(j, i)``).
  - Coordinate-based problems: ``True``.
  """
  norm_type: str = normalize_problem_type(problem_type) or ""

  if norm_type in ("HCP", "TOUR") and not edge_weight_type:
    return None

  if norm_type in ("ATSP", "SOP"):
    return False

  if matrix_obj is not None:
    size: int = matrix_obj.size
    for i in range(size):
      for j in range(i + 1, size):
        if matrix_obj.value_at(i, j) != matrix_obj.value_at(j, i):
          return False
    return True

  return True


def identify_weight_source(
  edge_weight_type: str | None,
  edge_weight_format: str | None = None,
) -> WeightSource:
  """Identify how edge weights are determined from header keywords."""
  if edge_weight_type:
    if edge_weight_type == "EXPLICIT":
      if edge_weight_format in FUNCTIONAL_EDGE_WEIGHT_FORMATS:
        return "explicit_function"
      return "explicit_matrix"
    if edge_weight_type == "SPECIAL":
      return "special_function"
    if edge_weight_type in (TWOD_WEIGHT_TYPES | THREED_WEIGHT_TYPES):
      return "coordinate_based"
  return "unweighted"


def _validate_section_key_bijection(
  section: dict[Any, Any],
  section_name: str,
  dimension: int,
  errors: list[str],
) -> None:
  """Enforce that a 1-based section dict has exact keys ``1..dimension``."""
  missing: list[int] = [i for i in range(1, dimension + 1) if i not in section]
  if missing:
    errors.append(f"{section_name} is missing entries for node(s) {_format_node_list(missing)}")

  out_of_range: list[Any] = [k for k in section if not _is_int(k) or k < 1 or k > dimension]
  if out_of_range:
    errors.append(
      f"{section_name} contains out-of-range node key(s) {_format_node_list(out_of_range)} (expected 1..{dimension})"
    )


def validate_problem_data(
  data: dict[str, Any],
  problem_class: type[StandardProblem] = StandardProblem,
) -> list[str]:
  """Validate pre-extraction 1-based problem data structure and spec invariants.

  Consults ``problem_class`` for allowed problem ``TYPE`` values and declared
  section field dimensions (``R1``/``R2``), so subclasses such as
  :class:`LKHProblem` automatically validate their extended types and sections.

  Parameters
  ----------
  data : dict of str to any
      Problem data dictionary with keys like ``'name'``, ``'type'``,
      ``'dimension'``, etc., typically built from ``problem.as_name_dict()``.
  problem_class : type[StandardProblem], default StandardProblem
      Problem model class whose ``allowed_problem_types`` and ``fields_by_name``
      govern validation.

  Returns
  -------
  list of str
      List of validation error messages. Empty list means validation passed.
  """
  errors: list[str] = []
  allowed_types: frozenset[str] = getattr(problem_class, "allowed_problem_types", VALID_PROBLEM_TYPES)

  # 1. Required header fields
  name: Any = data.get("name")
  if not isinstance(name, str) or not name.strip():
    errors.append("Problem name is required")

  raw_type: Any = data.get("type") or data.get("problem_type")
  if not isinstance(raw_type, str) or not raw_type.strip():
    errors.append("Problem type is required")
    problem_type: str = ""
  else:
    problem_type = normalize_problem_type(raw_type) or ""
    if problem_type not in allowed_types:
      errors.append(f"Unknown problem type: {raw_type.strip().upper()}")

  dimension: Any = data.get("dimension")
  has_valid_dim: bool = _is_int(dimension) and dimension > 0
  if not has_valid_dim:
    errors.append("Dimension must be positive integer")

  # 2. Header keyword vocabularies
  edge_weight_type: str | None = data.get("edge_weight_type")
  if edge_weight_type is not None:
    edge_weight_type = str(edge_weight_type).strip().upper()
    if edge_weight_type not in EDGE_WEIGHT_TYPES:
      errors.append(f"Unknown EDGE_WEIGHT_TYPE: {edge_weight_type}")

  if problem_type in WEIGHT_BEARING_TYPES and not edge_weight_type:
    errors.append(f"{problem_type} requires EDGE_WEIGHT_TYPE")

  node_coord_type: str | None = data.get("node_coord_type")
  if node_coord_type is not None:
    node_coord_type = str(node_coord_type).strip().upper()
    if node_coord_type not in NODE_COORD_TYPES:
      errors.append(f"Unknown NODE_COORD_TYPE: {node_coord_type}")

  display_data_type: str | None = data.get("display_data_type")
  if display_data_type is not None:
    display_data_type = str(display_data_type).strip().upper()
    if display_data_type not in DISPLAY_DATA_TYPES:
      errors.append(f"Unknown DISPLAY_DATA_TYPE: {display_data_type}")

  edge_data_format: str | None = data.get("edge_data_format")
  if edge_data_format is not None:
    edge_data_format = str(edge_data_format).strip().upper()
    if edge_data_format not in EDGE_DATA_FORMATS:
      errors.append(f"Unknown EDGE_DATA_FORMAT: {edge_data_format}")

  edge_format: str | None = data.get("edge_weight_format")
  if edge_format is not None:
    edge_format = str(edge_format).strip().upper()

  # 3. EXPLICIT weight invariants
  if edge_weight_type == "EXPLICIT":
    if not edge_format:
      errors.append("EDGE_WEIGHT_TYPE EXPLICIT requires EDGE_WEIGHT_FORMAT")
    elif edge_format not in FUNCTIONAL_EDGE_WEIGHT_FORMATS and edge_format not in matrix.TYPES:
      errors.append(f"Unknown EDGE_WEIGHT_FORMAT: {edge_format}")
    if edge_format not in FUNCTIONAL_EDGE_WEIGHT_FORMATS and not data.get("edge_weights"):
      errors.append("EDGE_WEIGHT_TYPE EXPLICIT but EDGE_WEIGHT_SECTION produced no weights")
  elif edge_format is not None:
    if edge_format not in FUNCTIONAL_EDGE_WEIGHT_FORMATS and edge_format not in matrix.TYPES:
      errors.append(f"Unknown EDGE_WEIGHT_FORMAT: {edge_format}")

  # 4. Header-vs-section presence rules for NODE_COORD_SECTION and DISPLAY_DATA_SECTION
  if node_coord_type == "NO_COORDS" and data.get("node_coords"):
    errors.append("NODE_COORD_TYPE is NO_COORDS but NODE_COORD_SECTION is present")

  display_data: Any = data.get("display_data")
  if display_data_type == "NO_DISPLAY" and display_data:
    errors.append("DISPLAY_DATA_TYPE is NO_DISPLAY but DISPLAY_DATA_SECTION is present")
  elif display_data_type == "TWOD_DISPLAY" and not display_data:
    errors.append("DISPLAY_DATA_TYPE is TWOD_DISPLAY but DISPLAY_DATA_SECTION is missing")

  # 5. Field-driven validation for all IndexedCoordinatesField and DemandsField sections (R1 / R2)
  for field_name, field_obj in problem_class.fields_by_name.items():
    section_val: object = data.get(field_name)
    if not section_val:
      continue
    section_kw: str = field_obj.keyword

    if isinstance(field_obj, IndexedCoordinatesField):
      allowed_dims: set[int] = set(field_obj.dimensions) if field_obj.dimensions else {2, 3}
      min_len: int = min(allowed_dims)
      coordinates: dict[Any, Any] | None = section_val if _is_dict(section_val) else None
      if coordinates is None or not all(_is_number_row(row, min_len) for row in coordinates.values()):
        errors.append(f"{section_kw} contains invalid coordinates")
        continue

      if has_valid_dim:
        _validate_section_key_bijection(coordinates, section_kw, dimension, errors)

      dimensions: set[int] = {len(coord) for coord in coordinates.values()}
      if not dimensions <= allowed_dims:
        if section_kw == "NODE_COORD_SECTION":
          errors.append(
            f"NODE_COORD_SECTION has unsupported coordinate dimensions: {sorted(dimensions)}"
            f" (spec allows {sorted(allowed_dims)})"
          )
        else:
          errors.append(f"{section_kw} must have dimensions {sorted(allowed_dims)}, got {sorted(dimensions)}")
      elif len(dimensions) > 1:
        errors.append(f"{section_kw} mixes coordinate dimensions: {sorted(dimensions)}")
      elif section_kw == "NODE_COORD_SECTION":
        coord_dim: int = next(iter(dimensions))
        if node_coord_type == "TWOD_COORDS" and coord_dim != 2:
          errors.append(f"NODE_COORD_TYPE is TWOD_COORDS but NODE_COORD_SECTION has {coord_dim}-D coordinates")
        elif node_coord_type == "THREED_COORDS" and coord_dim != 3:
          errors.append(f"NODE_COORD_TYPE is THREED_COORDS but NODE_COORD_SECTION has {coord_dim}-D coordinates")
        if edge_weight_type in TWOD_WEIGHT_TYPES and coord_dim != 2:
          errors.append(f"EDGE_WEIGHT_TYPE {edge_weight_type} requires 2-D coordinates, got {coord_dim}-D")
        elif edge_weight_type in THREED_WEIGHT_TYPES and coord_dim != 3:
          errors.append(f"EDGE_WEIGHT_TYPE {edge_weight_type} requires 3-D coordinates, got {coord_dim}-D")

    elif isinstance(field_obj, DemandsField) and _is_dict(section_val) and has_valid_dim:
      _validate_section_key_bijection(section_val, section_kw, dimension, errors)
      if section_kw == "DEMAND_SECTION":
        bad_demands: list[Any] = [k for k, v in section_val.items() if not _is_int(v) or v < 0]
        if bad_demands:
          errors.append(
            f"DEMAND_SECTION has non-integer or negative demand at node(s) {_format_node_list(bad_demands)}"
          )

  # 6. CVRP / VRP validation (CAPACITY, DEMAND_SECTION, DEPOT_SECTION)
  capacity: Any = data.get("capacity")
  if capacity is not None and (not _is_int(capacity) or capacity <= 0):
    errors.append("CAPACITY must be a positive integer")

  demands: object = data.get("demands")
  depots: object = data.get("depots")

  if problem_type == "CVRP" and not demands:
    errors.append("CVRP/VRP problem requires a DEMAND_SECTION")

  if depots:
    depot_ids: list[Any] | None = depots if _is_list(depots) else None
    if depot_ids is None or not all(_is_int(d) for d in depot_ids):
      errors.append("DEPOT_SECTION must contain integer node IDs")
    elif has_valid_dim:
      out_of_range_depots: list[int] = [d for d in depot_ids if d < 1 or d > dimension]
      if out_of_range_depots:
        errors.append(
          f"DEPOT_SECTION contains out-of-range depot node(s) {_format_node_list(out_of_range_depots)} "
          f"(expected 1..{dimension})"
        )
      if _is_dict(demands):
        nonzero_depots: list[int] = [d for d in depot_ids if d in demands and demands[d] != 0]
        if nonzero_depots:
          errors.append(f"DEPOT_SECTION node(s) {_format_node_list(nonzero_depots)} must have demand 0")

  # 7. EDGE_DATA_SECTION and FIXED_EDGES_SECTION validation
  edge_data: Any = data.get("edge_data")
  if problem_type == "HCP" and not edge_data:
    errors.append("HCP problem requires EDGE_DATA_SECTION")

  for section_val, section_label in (
    (edge_data, "EDGE_DATA_SECTION"),
    (data.get("fixed_edges"), "FIXED_EDGES_SECTION"),
  ):
    if section_val:
      edge_items: list[Any] | None = section_val if _is_list(section_val) else None
      if edge_items is None:
        errors.append(f"{section_label} must be a list of edge pairs")
      else:
        for edge in edge_items:
          if not _is_int_pair(edge):
            errors.append(f"{section_label} contains malformed edge {edge!r}")
            break
          if has_valid_dim and (edge[0] < 1 or edge[0] > dimension or edge[1] < 1 or edge[1] > dimension):
            errors.append(f"{section_label} contains out-of-range edge {edge!r} (expected endpoints in 1..{dimension})")
            break

  # 8. TOUR_SECTION validation
  tours: object = data.get("tours")
  if problem_type == "TOUR" and not tours:
    errors.append("TOUR problem requires TOUR_SECTION")

  if tours:
    tour_groups: list[Any] | None = tours if _is_list(tours) else None
    if tour_groups is None:
      errors.append("TOUR_SECTION must be a list of tours")
    elif has_valid_dim:
      expected_nodes: set[int] = set(range(1, dimension + 1))
      for idx, tour in enumerate(tour_groups):
        if not _is_int_list(tour):
          errors.append(f"TOUR_SECTION tour {idx} contains non-integer node IDs")
          break
        if len(tour) != dimension:
          errors.append(f"TOUR_SECTION tour {idx} has length {len(tour)}, expected DIMENSION={dimension}")
        elif set(tour) != expected_nodes:
          errors.append(f"TOUR_SECTION tour {idx} is not a valid permutation of 1..{dimension}")

  return errors


def validate_parse_result(
  result: Mapping[str, Any],
  problem_class: type[StandardProblem] = StandardProblem,
) -> list[str]:
  """Validate post-extraction 0-based ``ParseResult`` contract and invariants.

  Verifies that ``FormatParser.parse_file`` produced:
  - The exact ``ParseResult`` key set (no legacy ``nodes`` key).
  - Canonical ``problem_data`` with positive ``dimension`` and a valid
    ``Matrix`` of size ``dimension`` when ``EXPLICIT`` matrix weights are used.
  - Strictly ``float`` elements in ``coords`` and ``display_coords``, with
    ``len == dimension`` when present.
  - Strictly ``int`` elements in ``demands``, ``depots``, ``edges``,
    ``fixed_edges``, and ``tours``, all 0-based in ``0..dimension - 1``.
  - ``metadata`` boolean flags, ``is_symmetric``, and ``weight_source``
    consistent with the extracted payload.

  Parameters
  ----------
  result : dict of str to any
      The dictionary returned by ``FormatParser.parse_file()``.
  problem_class : type[StandardProblem], default StandardProblem
      Problem model class whose ``allowed_problem_types`` govern type checking.

  Returns
  -------
  list of str
      List of validation error messages. Empty list means validation passed.
  """
  errors: list[str] = []

  if not isinstance(result, dict):
    return ["ParseResult must be a dictionary"]

  if "nodes" in result:
    errors.append("ParseResult must not contain retired v1 'nodes' key")

  missing_keys: frozenset[str] = PARSE_RESULT_KEYS - set(result.keys())
  if missing_keys:
    errors.append(f"ParseResult is missing required keys: {sorted(missing_keys)}")
    return errors

  problem_data: object = result["problem_data"]
  if not _is_dict(problem_data):
    errors.append("problem_data must be a dictionary")
    return errors

  dimension: Any = problem_data.get("dimension")
  if not _is_int(dimension) or dimension <= 0:
    errors.append(f"problem_data['dimension'] must be a positive int, got {dimension!r}")
    return errors

  allowed_types: frozenset[str] = getattr(problem_class, "allowed_problem_types", VALID_PROBLEM_TYPES)
  problem_type: Any = problem_data.get("type")
  if not isinstance(problem_type, str) or problem_type not in allowed_types or problem_type == "VRP":
    errors.append(f"problem_data['type'] must be a normalized TSPLIB type, got {problem_type!r}")

  # 1. Explicit matrix check
  ew_type: Any = problem_data.get("edge_weight_type")
  ew_format: Any = problem_data.get("edge_weight_format")
  mat: object = problem_data.get("edge_weights")
  if ew_type == "EXPLICIT" and ew_format not in FUNCTIONAL_EDGE_WEIGHT_FORMATS:
    if not isinstance(mat, matrix.Matrix):
      errors.append(f"EXPLICIT problem must have a Matrix in problem_data['edge_weights'], got {type(mat).__name__}")
    elif mat.size != dimension:
      errors.append(f"Explicit matrix size ({mat.size}) does not match DIMENSION ({dimension})")

  # 2. Coords check (0-based list[list[float]])
  node_coord_field: Field | None = problem_class.fields_by_name.get("node_coords")
  allowed_coord_dims: set[int] = (
    set(node_coord_field.dimensions)
    if isinstance(node_coord_field, IndexedCoordinatesField) and node_coord_field.dimensions
    else {2, 3}
  )
  raw_coords: object = result["coords"]
  coords: list[Any] | None = raw_coords if _is_list(raw_coords) else None
  if coords is None:
    errors.append("coords must be a list")
  elif len(coords) not in (0, dimension):
    errors.append(f"coords length ({len(coords)}) must be 0 or DIMENSION ({dimension})")
  elif coords:
    coord_dims: set[int] = set()
    for idx, row in enumerate(coords):
      if not _is_float_list(row):
        errors.append(f"coords[{idx}] must be a list[float], got {row!r}")
        break
      coord_dims.add(len(row))
    if coord_dims and (len(coord_dims) != 1 or not coord_dims <= allowed_coord_dims):
      errors.append(f"coords has invalid coordinate dimensions: {sorted(coord_dims)}")

  # 3. Display coords check (0-based list[list[float]])
  raw_display_coords: object = result["display_coords"]
  display_coords: list[Any] | None = raw_display_coords if _is_list(raw_display_coords) else None
  if display_coords is None:
    errors.append("display_coords must be a list")
  elif len(display_coords) not in (0, dimension):
    errors.append(f"display_coords length ({len(display_coords)}) must be 0 or DIMENSION ({dimension})")
  elif display_coords:
    for idx, row in enumerate(display_coords):
      if not _is_float_list(row, 2):
        errors.append(f"display_coords[{idx}] must be a 2-element list[float], got {row!r}")
        break

  # 4. Demands check (0-based list[int])
  raw_demands: object = result["demands"]
  demands: list[Any] | None = raw_demands if _is_list(raw_demands) else None
  if demands is None:
    errors.append("demands must be a list")
  elif len(demands) not in (0, dimension):
    errors.append(f"demands length ({len(demands)}) must be 0 or DIMENSION ({dimension})")
  elif demands:
    for idx, val in enumerate(demands):
      if not _is_int(val) or val < 0:
        errors.append(f"demands[{idx}] must be a non-negative int, got {val!r}")
        break

  # 5. Depots check (0-based list[int] in 0..dimension-1)
  raw_depots: object = result["depots"]
  depots: list[Any] | None = raw_depots if _is_list(raw_depots) else None
  if depots is None:
    errors.append("depots must be a list")
  else:
    for idx, d in enumerate(depots):
      if not _is_int(d) or d < 0 or d >= dimension:
        errors.append(f"depots[{idx}]={d!r} out of 0-based range 0..{dimension - 1}")
        break
      if demands is not None and len(demands) == dimension and demands[d] != 0:
        errors.append(f"depot node {d} must have 0 demand, got {demands[d]}")
        break

  # 6. Edges and fixed_edges check (0-based list[list[int]] in 0..dimension-1)
  for key in ("edges", "fixed_edges"):
    raw_edge_list: object = result[key]
    edge_list: list[Any] | None = raw_edge_list if _is_list(raw_edge_list) else None
    if edge_list is None:
      errors.append(f"{key} must be a list")
    else:
      for idx, edge in enumerate(edge_list):
        edge_pair: list[Any] | None = edge if _is_list(edge) else None
        if (
          edge_pair is None
          or len(edge_pair) != 2
          or not _is_int(edge_pair[0])
          or not _is_int(edge_pair[1])
          or edge_pair[0] < 0
          or edge_pair[0] >= dimension
          or edge_pair[1] < 0
          or edge_pair[1] >= dimension
        ):
          errors.append(f"{key}[{idx}]={edge!r} is not a valid 0-based edge in 0..{dimension - 1}")
          break

  # 7. Tours check (0-based TourDict list)
  raw_tours: object = result["tours"]
  tours: list[Any] | None = raw_tours if _is_list(raw_tours) else None
  if tours is None:
    errors.append("tours must be a list")
  else:
    expected_zero_based: set[int] = set(range(dimension))
    for idx, raw_tour in enumerate(tours):
      tour_entry: dict[Any, Any] | None = raw_tour if _is_dict(raw_tour) else None
      if tour_entry is None:
        errors.append(f"tours[{idx}] must be a TourDict")
        break
      if tour_entry.get("tour_id") != idx:
        errors.append(f"tours[{idx}]['tour_id'] must be {idx}, got {tour_entry.get('tour_id')!r}")
      raw_tour_nodes: object = tour_entry.get("nodes")
      tour_nodes: list[Any] | None = raw_tour_nodes if _is_list(raw_tour_nodes) else None
      if tour_nodes is None or not all(_is_int(n) for n in tour_nodes):
        errors.append(f"tours[{idx}]['nodes'] must be a list[int]")
        break
      if len(tour_nodes) != dimension or set(tour_nodes) != expected_zero_based:
        errors.append(f"tours[{idx}]['nodes'] is not a valid 0-based permutation of 0..{dimension - 1}")
        break

  # 8. Metadata consistency checks (using canonical check_symmetry & identify_weight_source)
  metadata: object = result["metadata"]
  if not _is_dict(metadata):
    errors.append("metadata must be a dictionary")
  else:
    flag_pairs: tuple[tuple[str, Any], ...] = (
      ("has_coordinates", coords),
      ("has_display_coords", display_coords),
      ("has_demands", demands),
      ("has_depots", depots),
      ("has_edges", result["edges"]),
      ("has_fixed_edges", result["fixed_edges"]),
      ("has_tours", tours),
    )
    for flag_name, collection in flag_pairs:
      expected_flag: bool = bool(collection)
      actual_flag: Any = metadata.get(flag_name)
      if actual_flag is not expected_flag:
        errors.append(f"metadata['{flag_name}'] is {actual_flag!r}, expected {expected_flag}")

    weight_source: Any = metadata.get("weight_source")
    if weight_source not in VALID_WEIGHT_SOURCES:
      errors.append(f"metadata['weight_source']={weight_source!r} not in {sorted(VALID_WEIGHT_SOURCES)}")

    expected_sym: bool | None = check_symmetry(
      problem_type=problem_type if isinstance(problem_type, str) else None,
      edge_weight_type=ew_type if isinstance(ew_type, str) else None,
      matrix_obj=mat if isinstance(mat, matrix.Matrix) else None,
    )
    is_sym: Any = metadata.get("is_symmetric")
    if is_sym != expected_sym:
      errors.append(f"metadata['is_symmetric'] for {problem_type} is {is_sym!r}, expected {expected_sym!r}")

  return errors


def validate_coordinates(coords: Sequence[Sequence[float]]) -> bool:
  """Validate coordinate data structure.

  Checks that coordinates are properly formatted tuples/lists with at least
  2 numeric values and that *all* coordinate components (2-D or 3-D) are
  numeric (excluding ``bool``). Allows empty coordinate lists.

  Parameters
  ----------
  coords : sequence of sequence of float
      List of coordinate tuples/lists, where each contains numeric values.

  Returns
  -------
  bool
      True if coordinates are valid or list is empty, False otherwise.
  """
  if not coords:
    return True

  return all(
    isinstance(coord, (tuple, list)) and len(coord) >= 2 and all(_is_number(x) for x in coord) for coord in coords
  )
