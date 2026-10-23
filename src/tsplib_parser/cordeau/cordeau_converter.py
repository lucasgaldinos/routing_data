"""Converter from Cordeau format to TSPLIB95 format.

This module converts parsed Cordeau problems into TSPLIB95 format strings,
enabling them to be processed by the existing TSPLIB95 pipeline.
"""

import logging
from pathlib import Path

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

  def to_tsplib(
    self,
    problem: CordeauProblem,
    output_path: str | Path | None = None,
    as_lkh: bool = True,
  ) -> str:
    """Convert Cordeau problem to TSPLIB / LKH format.

    Parameters
    ----------
    problem : CordeauProblem
        Parsed Cordeau problem
    output_path : str | Path, optional
        If provided, write content to this file
    as_lkh : bool, default True
        If True, serialize lossless LKH-3 format (TYPE : MDVRP, VEHICLES, DEPOTS,
        DISTANCE, and extended sections for heterogeneous constraints).
        If False, serialize legacy TSPLIB95 single-depot CVRP surrogate format.

    Returns
    -------
    str
        Formatted problem content

    Raises
    ------
    ValueError
        If problem type is not supported for conversion
    """
    if problem.problem_type not in (2, 6):
      raise ValueError(
        f"Only MDVRP (type=2) and MDVRPTW (type=6) conversion is supported, "
        f"got type {problem.problem_type} ({problem.type_name})"
      )

    self.logger.debug(f"Converting {problem.name} from Cordeau to TSPLIB format (as_lkh={as_lkh})")

    lines: list[str] = []

    # Header section
    lines.extend(self._generate_header(problem, as_lkh=as_lkh))
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

    # Extended sections for heterogeneous constraints (LKH mode)
    if as_lkh:
      capacities: list[int] = [c.max_load for c in problem.depot_constraints]
      if len(set(capacities)) > 1:
        lines.append("DEPOT_CAPACITY_SECTION")
        for depot_num, c in enumerate(problem.depot_constraints, start=1):
          lines.append(f"{depot_num} {c.max_load}")

      durations: list[float] = [c.max_duration for c in problem.depot_constraints]
      if len(set(durations)) > 1:
        lines.append("DEPOT_DURATION_SECTION")
        for depot_num, c in enumerate(problem.depot_constraints, start=1):
          lines.append(f"{depot_num} {c.max_duration}")

      # Time windows and service times (MDVRPTW mode)
      if any(n.earliest_time is not None for n in problem.nodes):
        lines.append("TIME_WINDOW_SECTION")
        node_num = 1
        for depot in problem.depot_nodes:
          e = depot.earliest_time if depot.earliest_time is not None else 0.0
          latest = depot.latest_time if depot.latest_time is not None else 0.0
          lines.append(f"{node_num} {e} {latest}")
          node_num += 1
        for customer in problem.customer_nodes:
          e = customer.earliest_time if customer.earliest_time is not None else 0.0
          latest = customer.latest_time if customer.latest_time is not None else 0.0
          lines.append(f"{node_num} {e} {latest}")
          node_num += 1

        if any(n.service_duration > 0 for n in problem.nodes):
          lines.append("SERVICE_TIME_SECTION")
          node_num = 1
          for depot in problem.depot_nodes:
            lines.append(f"{node_num} {depot.service_duration}")
            node_num += 1
          for customer in problem.customer_nodes:
            lines.append(f"{node_num} {customer.service_duration}")
            node_num += 1

    # EOF marker
    lines.append("EOF")

    content: str = "\n".join(lines)

    if output_path:
      path = Path(output_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(content)
      self.logger.info(f"Wrote TSPLIB file: {output_path}")

    return content

  def to_tsplib95(self, problem: CordeauProblem, output_path: str | Path | None = None) -> str:
    """Convert Cordeau problem to legacy TSPLIB95 single-depot CVRP surrogate format."""
    return self.to_tsplib(problem, output_path=output_path, as_lkh=False)

  def _generate_header(self, problem: CordeauProblem, as_lkh: bool = True) -> list[str]:
    """Generate TSPLIB / LKH header section.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data
    as_lkh : bool, default True
        Whether to generate LKH-3 extended header

    Returns
    -------
    list[str]
        Header lines
    """
    capacities: list[int] = [c.max_load for c in problem.depot_constraints]
    max_durations: list[float] = [c.max_duration for c in problem.depot_constraints]

    comment_parts: list[str] = [
      f"Cordeau {problem.type_name} instance",
      f"{problem.num_vehicles} vehicles per depot ({problem.num_vehicles * problem.num_depots} total)",
      f"{problem.num_customers} customers",
      f"{problem.num_depots} depots",
    ]

    if max(max_durations) > 0:
      comment_parts.append(f"max_duration={max(max_durations)}")

    if len(set(capacities)) > 1:
      comment_parts.append(f"capacities={capacities}")
    if len(set(max_durations)) > 1 and max(max_durations) > 0:
      comment_parts.append(f"max_durations={max_durations}")

    comment: str = " | ".join(comment_parts)

    if as_lkh:
      header: list[str] = [
        f"NAME : {problem.name}",
        f"COMMENT : {comment}",
        f"TYPE : {problem.type_name}",
        f"DIMENSION : {problem.dimension}",
        "EDGE_WEIGHT_TYPE : EUC_2D",
        f"VEHICLES : {problem.num_vehicles * problem.num_depots}",
        f"DEPOTS : {problem.num_depots}",
      ]
      if len(set(capacities)) == 1:
        header.append(f"CAPACITY : {capacities[0]}")
      if len(set(max_durations)) == 1 and max_durations[0] > 0:
        header.append(f"DISTANCE : {max_durations[0]}")
      return header

    # Legacy TSPLIB95 CVRP surrogate mode
    legacy_header: list[str] = [
      f"NAME : {problem.name}",
      f"COMMENT : {comment}",
      "TYPE : CVRP",
      f"DIMENSION : {problem.dimension}",
      "EDGE_WEIGHT_TYPE : EUC_2D",
      f"CAPACITY : {max(capacities)}",
    ]
    return legacy_header

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
    lines: list[str] = []
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
    lines: list[str] = []
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
    lines: list[str] = []

    # List depot node numbers (now 1..num_depots after renumbering)
    for depot_num in range(1, problem.num_depots + 1):
      lines.append(f"{depot_num}")

    # Terminator
    lines.append("-1")

    return lines
