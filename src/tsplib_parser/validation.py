"""Validation utilities for TSPLIB95 format parsing.

This module provides validation functions for problem data extracted from
TSPLIB95 files. Validates required fields, types, and structural integrity.
"""

from collections.abc import Sequence
from typing import Any

from . import matrix


def validate_problem_data(data: dict[str, Any]) -> list[str]:
  """Validate extracted problem data structure and required fields.

  Checks for presence of required fields (name, type, dimension), validates
  their types and values, and enforces the structural cross-field invariants:

  - ``EDGE_WEIGHT_TYPE: EXPLICIT`` requires an interpretable
    ``EDGE_WEIGHT_FORMAT`` and a non-empty ``EDGE_WEIGHT_SECTION`` (exact
    cardinality vs ``DIMENSION`` is enforced when the matrix is built, see
    ``StandardProblem.create_explicit_matrix``).
  - ``CVRP``/``VRP`` requires a ``DEMAND_SECTION`` whose entries cover every
    node ``1..dimension`` (depots included, per the spec).
  - ``NODE_COORD_SECTION`` / ``DISPLAY_DATA_SECTION`` entries must be numeric
    and at least 2-D when the section is present.

  Parameters
  ----------
  data : dict of str to any
      Problem data dictionary with keys like 'name', 'type', 'dimension', etc.
      Typically extracted from StandardProblem.as_name_dict() or parsed
      TSPLIB95 file.

  Returns
  -------
  list of str
      List of validation error messages. Empty list means validation passed.
      Each error is a human-readable string describing what failed.

  Examples
  --------
  >>> data = {"name": "gr17", "type": "TSP", "dimension": 17}
  >>> errors = validate_problem_data(data)
  >>> len(errors)
  0

  >>> bad_data = {"name": "test", "dimension": -1}
  >>> errors = validate_problem_data(bad_data)
  >>> "Problem type is required" in errors
  True
  >>> "Dimension must be positive integer" in errors
  True

  Notes
  -----
  Validation checks:
  - name field exists and is non-empty
  - type field exists and is non-empty
  - dimension is positive integer
  - type is one of: TSP, VRP, ATSP, HCP, SOP, TOUR, CVRP
  - EXPLICIT weight problems carry a parseable weight section
  - CVRP/VRP demand sections cover every node 1..dimension
  - coordinates are numeric with at least two dimensions
  """
  errors: list[str] = []

  # Required fields validation
  if not data.get("name"):
    errors.append("Problem name is required")

  if not data.get("type"):
    errors.append("Problem type is required")

  # Dimension validation
  dimension = data.get("dimension")
  if not isinstance(dimension, int) or dimension <= 0:
    errors.append("Dimension must be positive integer")

  # Problem type validation
  problem_type = data.get("type", "").upper()
  known_types = {"TSP", "VRP", "ATSP", "HCP", "SOP", "TOUR", "CVRP"}
  if problem_type and problem_type not in known_types:
    errors.append(f"Unknown problem type: {problem_type}")

  # Structural invariants ---------------------------------------------------
  # EXPLICIT weights: an EDGE_WEIGHT_SECTION must have produced data and the
  # declared format must be one the matrix layer can interpret.
  if data.get("edge_weight_type") == "EXPLICIT":
    edge_format = data.get("edge_weight_format")
    if not edge_format:
      errors.append("EDGE_WEIGHT_TYPE EXPLICIT requires EDGE_WEIGHT_FORMAT")
    elif edge_format not in matrix.TYPES:
      errors.append(f"Unknown EDGE_WEIGHT_FORMAT: {edge_format}")
    if not data.get("edge_weights"):
      errors.append("EDGE_WEIGHT_TYPE EXPLICIT but EDGE_WEIGHT_SECTION produced no weights")

  # CVRP/VRP demands: every node 1..dimension (depots included) needs an entry.
  if problem_type in ("CVRP", "VRP"):
    demands = data.get("demands")
    if not demands:
      errors.append("CVRP/VRP problem requires a DEMAND_SECTION")
    elif isinstance(dimension, int) and dimension > 0:
      missing = [i for i in range(1, dimension + 1) if i not in demands]
      if missing:
        shown = missing[:10]
        suffix = f" (and {len(missing) - len(shown)} more)" if len(missing) > len(shown) else ""
        errors.append(f"DEMAND_SECTION is missing entries for node(s) {shown}{suffix}")

  # Coordinates must be numeric and at least 2-D when present.
  node_coords = data.get("node_coords")
  if node_coords and not validate_coordinates(node_coords.values()):
    errors.append("NODE_COORD_SECTION contains invalid coordinates")
  display_data = data.get("display_data")
  if display_data and not validate_coordinates(display_data.values()):
    errors.append("DISPLAY_DATA_SECTION contains invalid coordinates")

  return errors


def validate_coordinates(coords: Sequence[tuple[float, ...]]) -> bool:
  """Validate coordinate data structure.

  Checks that coordinates are properly formatted tuples/lists with at least
  2 numeric values (x, y). Allows empty coordinate lists.

  Parameters
  ----------
  coords : sequence of tuple of float
      List of coordinate tuples, where each tuple contains at least (x, y) values.

  Returns
  -------
  bool
      True if coordinates are valid or list is empty, False otherwise.

  Examples
  --------
  >>> validate_coordinates([(0, 0), (1, 1), (2, 2)])
  True

  >>> validate_coordinates([])  # Empty is valid
  True

  >>> validate_coordinates([(0, 0), (1,)])  # Invalid - not enough values
  False

  >>> validate_coordinates([(0, 0), ("a", "b")])  # Invalid - not numeric
  False
  """
  if not coords:
    return True  # Empty coordinates are valid

  return all(
    isinstance(coord, (tuple, list)) and len(coord) >= 2 and all(isinstance(x, (int, float)) for x in coord[:2])
    for coord in coords
  )
