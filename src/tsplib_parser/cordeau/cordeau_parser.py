"""Parser for Cordeau MDVRP format files.

This module parses Cordeau benchmark instance files into structured Python objects.
"""

import logging
from pathlib import Path
from typing import Literal

from .cordeau_types import CordeauDepotConstraint, CordeauNode, CordeauProblem


class CordeauParseError(Exception):
  """Exception raised for Cordeau format parsing errors."""

  pass


class CordeauParser:
  """Parser for Cordeau MDVRP benchmark format.

  Parses files in the format described by Cordeau et al. (1997) for
  multi-depot vehicle routing problems.

  Attributes
  ----------
  logger : logging.Logger
      Logger instance for tracking parsing operations

  Examples
  --------
  >>> parser = CordeauParser()
  >>> problem = parser.parse_file("datasets_raw/umalaga/mdvrp/C-mdvrp/p01")
  >>> print(f"{problem.name}: {problem.num_customers} customers, {problem.num_depots} depots")
  p01: 50 customers, 4 depots
  """

  def __init__(self, logger: logging.Logger | None = None) -> None:
    """Initialize parser.

    Parameters
    ----------
    logger : logging.Logger, optional
        Logger for tracking operations
    """
    self.logger: logging.Logger = logger or logging.getLogger(__name__)

  def parse_file(self, file_path: str | Path) -> CordeauProblem:
    """Parse a Cordeau format file.

    Parameters
    ----------
    file_path : str
        Path to Cordeau format file

    Returns
    -------
    CordeauProblem
        Parsed problem data

    Raises
    ------
    CordeauParseError
        If file format is invalid
    FileNotFoundError
        If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
      raise FileNotFoundError(f"Cordeau file not found: {file_path}")

    self.logger.debug(f"Parsing Cordeau file: {file_path}")

    try:
      with open(path) as f:
        lines = [line.strip() for line in f if line.strip()]

      # Parse header
      header = self._parse_header(lines[0])
      problem_type, num_vehicles, num_customers, num_depots = header

      # Parse depot constraints
      constraints_end = 1 + num_depots
      depot_constraints = self._parse_depot_constraints(lines[1:constraints_end])

      # Parse nodes (customers + depots)
      nodes_start = constraints_end
      nodes_end = nodes_start + num_customers + num_depots
      nodes = self._parse_nodes(lines[nodes_start:nodes_end], num_customers, num_depots, problem_type)

      # Create problem instance
      problem = CordeauProblem(
        name=path.stem,
        problem_type=problem_type,
        num_vehicles=num_vehicles,
        num_customers=num_customers,
        num_depots=num_depots,
        depot_constraints=depot_constraints,
        nodes=nodes,
      )

      self.logger.info(
        f"Parsed {problem.name}: {problem.type_name} with "
        f"{problem.num_customers} customers, {problem.num_depots} depots, "
        f"{problem.num_vehicles} vehicles"
      )

      return problem

    except CordeauParseError:
      raise
    except Exception as e:
      raise CordeauParseError(f"Failed to parse Cordeau file {file_path}: {e!s}") from e

  def _parse_header(self, line: str) -> tuple[int, int, int, int]:
    """Parse header line: type m n t.

    Parameters
    ----------
    line : str
        Header line

    Returns
    -------
    tuple[int, int, int, int]
        (problem_type, num_vehicles, num_customers, num_depots)
    """
    parts = line.split()
    if len(parts) != 4:
      raise CordeauParseError(f"Header must have 4 values (type m n t), got {len(parts)}: {line}")

    try:
      problem_type = int(parts[0])
      num_vehicles = int(parts[1])
      num_customers = int(parts[2])
      num_depots = int(parts[3])
    except ValueError as e:
      raise CordeauParseError(f"Header values must be integers: {line}") from e

    if problem_type < 0 or problem_type > 7:
      raise CordeauParseError(f"Invalid problem type {problem_type}, must be 0-7")

    if num_vehicles <= 0 or num_customers <= 0 or num_depots <= 0:
      raise CordeauParseError(
        f"Vehicles, customers, and depots must be positive: m={num_vehicles}, n={num_customers}, t={num_depots}"
      )

    return problem_type, num_vehicles, num_customers, num_depots

  def _parse_depot_constraints(self, lines: list[str]) -> list[CordeauDepotConstraint]:
    """Parse depot constraint lines: D Q.

    Parameters
    ----------
    lines : List[str]
        Constraint lines (one per depot)

    Returns
    -------
    List[CordeauDepotConstraint]
        Parsed constraints
    """
    constraints = []

    for i, line in enumerate(lines, 1):
      parts: list[str] = line.split()
      if len(parts) != 2:
        raise CordeauParseError(f"Depot constraint line {i} must have 2 values (D Q), got {len(parts)}: {line}")

      try:
        max_duration = float(parts[0])
        max_load = int(parts[1])
      except ValueError as e:
        raise CordeauParseError(f"Depot constraint line {i} has invalid values: {line}") from e

      constraints.append(CordeauDepotConstraint(max_duration, max_load))

    return constraints

  def _parse_nodes(self, lines: list[str], num_customers: int, num_depots: int, problem_type: int) -> list[CordeauNode]:
    """Parse node lines.

    Format depends on problem type:
    - Basic (VRP, MDVRP): i x y d q f a list
    - With time windows (VRPTW, MDVRPTW): i x y d q f a list e l

    Parameters
    ----------
    lines : List[str]
        Node lines
    num_customers : int
        Number of customer nodes
    num_depots : int
        Number of depot nodes
    problem_type : int
        Problem type (0-7)

    Returns
    -------
    List[CordeauNode]
        Parsed nodes (customers first, then depots)
    """
    has_time_windows: bool = problem_type >= 4  # VRPTW variants
    nodes = []

    expected_nodes: int = num_customers + num_depots
    if len(lines) != expected_nodes:
      raise CordeauParseError(
        f"Expected {expected_nodes} node lines ({num_customers} customers + {num_depots} depots), got {len(lines)}"
      )

    for i, line in enumerate(lines, 1):
      is_depot: bool = i > num_customers
      node: CordeauNode = self._parse_node_line(line, i, is_depot, has_time_windows)
      nodes.append(node)

    return nodes

  def _parse_node_line(self, line: str, line_num: int, is_depot: bool, has_time_windows: bool) -> CordeauNode:
    """Parse a single node line.

    Parameters
    ----------
    line : str
        Node line
    line_num : int
        Line number for error messages
    is_depot : bool
        Whether this is a depot node
    has_time_windows : bool
        Whether problem has time windows

    Returns
    -------
    CordeauNode
        Parsed node
    """
    parts: list[str] = line.split()

    # Depot nodes have fewer fields (7): i x y d 0 0 0
    # Customer nodes vary by problem type:
    #   MDVRP (type=2): i x y d q f a list (8+)
    #   With time windows: + e l (10+)

    if is_depot:
      # Depots have: i x y d 0 0 0
      if len(parts) < 7:
        raise CordeauParseError(f"Depot line {line_num} has {len(parts)} fields, expected at least 7: {line}")

      try:
        node_id = int(parts[0])
        x = float(parts[1])
        y = float(parts[2])
        service_duration = float(parts[3])

        return CordeauNode(
          node_id=node_id,
          x=x,
          y=y,
          service_duration=service_duration,
          demand=0,  # Depots have 0 demand
          is_depot=True,
        )
      except (ValueError, IndexError) as e:
        raise CordeauParseError(f"Invalid depot node data at line {line_num}: {line}") from e

    # Customer nodes
    min_fields: Literal[10] | Literal[8] = 10 if has_time_windows else 8

    if len(parts) < min_fields:
      raise CordeauParseError(f"Node line {line_num} has {len(parts)} fields, expected at least {min_fields}: {line}")

    try:
      node_id = int(parts[0])
      x = float(parts[1])
      y = float(parts[2])
      service_duration = float(parts[3])
      demand = int(parts[4])
      frequency = int(parts[5])
      num_combinations = int(parts[6])

      # Parse visit combinations list
      # The next 'num_combinations' values (or specified in 'a' field)
      # For MDVRP (type=2), typically this is just placeholder values
      visit_combinations = []
      list_start = 7
      list_end: int = list_start + num_combinations

      for j in range(list_start, min(list_end, len(parts))):
        # Stop if we hit time window fields
        if has_time_windows and j >= len(parts) - 2:
          break
        try:
          visit_combinations.append(int(parts[j]))
        except ValueError:
          # Reached non-integer field, stop parsing combinations
          break

      # Parse time windows if present
      earliest_time = None
      latest_time = None
      if has_time_windows and len(parts) >= 2:
        try:
          earliest_time = float(parts[-2])
          latest_time = float(parts[-1])
        except (ValueError, IndexError):
          pass

    except (ValueError, IndexError) as e:
      raise CordeauParseError(f"Node line {line_num} has invalid format: {line}") from e

    return CordeauNode(
      node_id=node_id,
      x=x,
      y=y,
      service_duration=service_duration,
      demand=demand,
      frequency=frequency,
      num_combinations=num_combinations,
      visit_combinations=visit_combinations if visit_combinations else None,
      earliest_time=earliest_time,
      latest_time=latest_time,
      is_depot=is_depot,
    )
