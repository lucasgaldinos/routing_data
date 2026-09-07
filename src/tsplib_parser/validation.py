"""Validation utilities for TSPLIB95 format parsing.

This module provides validation functions for problem data extracted from
TSPLIB95 files. Validates required fields, types, and structural integrity.
"""

from typing import Any, Sequence


def validate_problem_data(data: dict[str, Any]) -> list[str]:
    """Validate extracted problem data structure and required fields.

    Checks for presence of required fields (name, type, dimension) and validates
    their types and values. Also validates problem type against known TSPLIB95 types.

    Parameters
    ----------
    data : dict of str to any
        Problem data dictionary with keys like 'name', 'type', 'dimension', etc.
        Typically extracted from StandardProblem.as_name_dict() or parsed TSPLIB95 file.

    Returns
    -------
    list of str
        List of validation error messages. Empty list means validation passed.
        Each error is a human-readable string describing what failed.

    Examples
    --------
    >>> data = {'name': 'gr17', 'type': 'TSP', 'dimension': 17}
    >>> errors = validate_problem_data(data)
    >>> len(errors)
    0

    >>> bad_data = {'name': 'test', 'dimension': -1}
    >>> errors = validate_problem_data(bad_data)
    >>> 'Problem type is required' in errors
    True
    >>> 'Dimension must be positive integer' in errors
    True

    Notes
    -----
    Validation checks:
    - name field exists and is non-empty
    - type field exists and is non-empty
    - dimension is positive integer
    - type is one of: TSP, VRP, ATSP, HCP, SOP, TOUR
    """
    errors = []

    # Required fields validation
    if not data.get('name'):
        errors.append("Problem name is required")

    if not data.get('type'):
        errors.append("Problem type is required")

    # Dimension validation
    dimension = data.get('dimension')
    if not isinstance(dimension, int) or dimension <= 0:
        errors.append("Dimension must be positive integer")

    # Problem type validation
    problem_type = data.get('type', '').upper()
    known_types = {'TSP', 'VRP', 'ATSP', 'HCP', 'SOP', 'TOUR', 'CVRP'}
    if problem_type and problem_type not in known_types:
        errors.append(f"Unknown problem type: {problem_type}")

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

    >>> validate_coordinates([(0, 0), ('a', 'b')])  # Invalid - not numeric
    False
    """
    if not coords:
        return True  # Empty coordinates are valid

    return all(
        isinstance(coord, (tuple, list)) and
        len(coord) >= 2 and
        all(isinstance(x, (int, float)) for x in coord[:2])
        for coord in coords
    )
