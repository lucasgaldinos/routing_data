"""Converter from Cordeau format to TSPLIB95 format.

This module converts parsed Cordeau problems into TSPLIB95 format strings,
enabling them to be processed by the existing TSPLIB95 pipeline.
"""

import logging
from pathlib import Path
from typing import LiteralString

from .cordeau_types import CordeauProblem


class CordeauConverter:
  """Converter from Cordeau MDVRP format to TSPLIB95 format.

  Converts Cordeau benchmark instances to TSPLIB95 VRP format with
  multiple depots support.

  Attributes
  ----------
  logger : logging.Logger
      Logger instance for tracking conversion operations

  Examples
  --------
  >>> from .cordeau_parser import CordeauParser
  >>> parser = CordeauParser()
  >>> converter = CordeauConverter()
  >>> problem = parser.parse_file("p01")
  >>> tsplib_content = converter.to_tsplib95(problem)
  >>> # Optionally write to file
  >>> converter.to_tsplib95(problem, output_path="p01.vrp")
  """

  def __init__(self, logger: logging.Logger | None = None) -> None:
    """Initialize converter.

    Parameters
    ----------
    logger : logging.Logger, optional
        Logger for tracking operations
    """
    self.logger: logging.Logger = logger or logging.getLogger(__name__)

  def to_tsplib95(self, problem: CordeauProblem, output_path: str | Path | None = None) -> str:
    """Convert Cordeau problem to TSPLIB95 format.

    Parameters
    ----------
    problem : CordeauProblem
        Parsed Cordeau problem
    output_path : str, optional
        If provided, write TSPLIB95 content to this file

    Returns
    -------
    str
        TSPLIB95 formatted content

    Raises
    ------
    ValueError
        If problem type is not supported for conversion
    """
    # Validate problem type
    if problem.problem_type != 2:
      raise ValueError(
        f"Only MDVRP (type=2) conversion is currently supported, got type {problem.problem_type} ({problem.type_name})"
      )

    self.logger.debug(f"Converting {problem.name} from Cordeau to TSPLIB95 format")

    # Build TSPLIB95 content
    lines = []

    # Header section
    lines.extend(self._generate_header(problem))
    lines.append("")

    # Node coordinates section
    lines.append("NODE_COORD_SECTION")
    lines.extend(self._generate_node_coords(problem))

    # Demand section
    lines.append("DEMAND_SECTION")
    lines.extend(self._generate_demands(problem))

    # Depot section
    lines.append("DEPOT_SECTION")
    lines.extend(self._generate_depot_section(problem))

    # EOF marker
    lines.append("EOF")

    # Join into single string
    content: LiteralString = "\n".join(lines)

    # Write to file if requested
    if output_path:
      path = Path(output_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(content)
      self.logger.info(f"Wrote TSPLIB95 file: {output_path}")

    return content

  def _generate_header(self, problem: CordeauProblem) -> list[str]:
    """Generate TSPLIB95 header section.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

    Returns
    -------
    list[str]
        Header lines
    """
    # Get capacity (use first depot's capacity, or max if they differ)
    capacities = [c.max_load for c in problem.depot_constraints]
    capacity = max(capacities)

    # Get max duration (use first depot's, or max if they differ)
    max_durations = [c.max_duration for c in problem.depot_constraints]
    max_duration = max(max_durations)

    # Build comment with problem metadata
    comment_parts = [
      f"Cordeau {problem.type_name} instance",
      f"{problem.num_vehicles} vehicles",
      f"{problem.num_customers} customers",
      f"{problem.num_depots} depots",
    ]

    if max_duration > 0:
      comment_parts.append(f"max_duration={max_duration}")

    # Note: Different capacities/durations per depot if they vary
    if len(set(capacities)) > 1:
      comment_parts.append(f"capacities={capacities}")
    if len(set(max_durations)) > 1 and max_duration > 0:
      comment_parts.append(f"max_durations={max_durations}")

    comment = " | ".join(comment_parts)

    header = [
      f"NAME : {problem.name}",
      f"COMMENT : {comment}",
      "TYPE : CVRP",
      f"DIMENSION : {problem.dimension}",
      "EDGE_WEIGHT_TYPE : EUC_2D",
      f"CAPACITY : {capacity}",
    ]

    return header

  def _generate_node_coords(self, problem: CordeauProblem) -> list[str]:
    """Generate NODE_COORD_SECTION.

    In TSPLIB95, depots should come first, then customers.
    Original Cordeau has customers first, depots last.

    Node numbering: 1..num_depots (depots), (num_depots+1)..dimension (customers)

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

    Returns
    -------
    list[str]
        Node coordinate lines
    """
    lines = []
    node_num = 1

    # First: depot nodes (renumber from 1)
    for depot in problem.depot_nodes:
      lines.append(f"{node_num} {depot.x} {depot.y}")
      node_num += 1

    # Then: customer nodes (continue numbering)
    for customer in problem.customer_nodes:
      lines.append(f"{node_num} {customer.x} {customer.y}")
      node_num += 1

    return lines

  def _generate_demands(self, problem: CordeauProblem) -> list[str]:
    """Generate DEMAND_SECTION.

    Depots have demand 0, customers have their original demands.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

    Returns
    -------
    list[str]
        Demand lines
    """
    lines = []
    node_num = 1

    # First: depot nodes (demand = 0)
    for _ in problem.depot_nodes:
      lines.append(f"{node_num} 0")
      node_num += 1

    # Then: customer nodes (original demands)
    for customer in problem.customer_nodes:
      lines.append(f"{node_num} {customer.demand}")
      node_num += 1

    return lines

  def _generate_depot_section(self, problem: CordeauProblem) -> list[str]:
    """Generate DEPOT_SECTION.

    Lists all depot node numbers (1..num_depots), terminated by -1.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

    Returns
    -------
    list[str]
        Depot section lines
    """
    lines = []

    # List depot node numbers (now 1..num_depots after renumbering)
    for depot_num in range(1, problem.num_depots + 1):
      lines.append(f"{depot_num}")

    # Terminator
    lines.append("-1")

    return lines
