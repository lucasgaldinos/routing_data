"""Converter from Cordeau format to TSPLIB-extended format.

This module converts parsed Cordeau problems into the TSPLIB-extended dialect,
enabling them to be processed by the existing parser pipeline.

The emitted document always states the instance's real type (``MDVRP`` or
``MDVRPTW``) and always keeps its depots in ``DEPOT_SECTION``. There is no
single-depot ``CVRP`` surrogate: flattening several depots into one and
reducing heterogeneous capacities to their maximum changes the problem.
"""

import logging
from pathlib import Path

from .cordeau_types import CordeauNode, CordeauProblem


class CordeauConverter:
  """Converter from Cordeau MDVRP format to the TSPLIB-extended dialect.

  Converts Cordeau benchmark instances to a TSPLIB-extended document that keeps
  the real problem type and every depot.

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
  >>> tsplib_content = converter.to_tsplib(problem)
  >>> # Optionally write to file
  >>> converter.to_tsplib(problem, output_path="p01.vrp")
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
  ) -> str:
    """Convert a Cordeau problem to the TSPLIB-extended dialect.

    Parameters
    ----------
    problem : CordeauProblem
        Parsed Cordeau problem
    output_path : str | Path, optional
        If provided, write content to this file

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

    self.logger.debug(f"Converting {problem.name} from Cordeau to TSPLIB-extended format")

    lines: list[str] = []

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

    # Extended sections: emitted when the instance's constraints are heterogeneous,
    # because a single ``CAPACITY``/``DISTANCE`` header cannot carry them.
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

    # Time windows and service times (MDVRPTW mode). Both sections must address
    # nodes by the ids NODE_COORD_SECTION and DEMAND_SECTION just used (the
    # source's own customer-then-depot numbering). An earlier version renumbered
    # the nodes 1..dimension with the depots first, which shifted every customer
    # window by one node per depot.
    #
    # Rows are emitted only for nodes the source actually constrains: a node
    # absent from TIME_WINDOW_SECTION means "no window", whereas `0 <latest>`
    # would be a window this file never stated.
    windowed: list[CordeauNode] = [n for n in problem.nodes if n.earliest_time is not None]
    if windowed:
      lines.append("TIME_WINDOW_SECTION")
      for node in windowed:
        e = node.earliest_time if node.earliest_time is not None else 0.0
        latest = node.latest_time if node.latest_time is not None else 0.0
        lines.append(f"{node.node_id} {e} {latest}")

      # Kept inside the window branch because the Cordeau->ParseResult path only
      # carries service durations for time-windowed instances; emitting the
      # section for a plain MDVRP would state what that path drops.
      if any(n.service_duration > 0 for n in problem.nodes):
        lines.append("SERVICE_TIME_SECTION")
        for node in [*problem.customer_nodes, *problem.depot_nodes]:
          lines.append(f"{node.node_id} {node.service_duration}")

    # EOF marker
    lines.append("EOF")

    content: str = "\n".join(lines)

    if output_path:
      path = Path(output_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(content)
      self.logger.info(f"Wrote TSPLIB file: {output_path}")

    return content

  def _generate_header(self, problem: CordeauProblem) -> list[str]:
    """Generate the TSPLIB-extended header.

    The header states the instance's real type (``MDVRP`` or ``MDVRPTW``) and
    every depot stays in ``DEPOT_SECTION``. A single-depot ``CVRP`` surrogate
    is not offered: it dropped the depots and flattened heterogeneous depot
    capacities into one number, so the emitted file described a different
    problem.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

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

    header: list[str] = [
      f"NAME : {problem.name}",
      f"COMMENT : {comment}",
      f"TYPE : {problem.type_name}",
      f"DIMENSION : {problem.dimension}",
      "EDGE_WEIGHT_TYPE : EUC_2D",
      f"VEHICLES : {problem.num_vehicles * problem.num_depots}",
    ]
    if len(set(capacities)) == 1:
      header.append(f"CAPACITY : {capacities[0]}")
    if len(set(max_durations)) == 1 and max_durations[0] > 0:
      header.append(f"DISTANCE : {max_durations[0]}")
    return header

  def _generate_node_coords(self, problem: CordeauProblem) -> list[str]:
    """Generate NODE_COORD_SECTION in the source's own node numbering.

    Customers first (nodes ``1..n``) and depots last (nodes ``n+1..n+t``), which
    is the order the Cordeau file itself uses. Renumbering to put the depots first
    would make the emitted nodes disagree with the source ids, so a solution file
    that names customer ``44`` would no longer name node ``44`` here.

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

    for customer in problem.customer_nodes:
      lines.append(f"{customer.node_id} {customer.x} {customer.y}")

    for depot in problem.depot_nodes:
      lines.append(f"{depot.node_id} {depot.x} {depot.y}")

    return lines

  def _generate_demands(self, problem: CordeauProblem) -> list[str]:
    """Generate DEMAND_SECTION in the source's own node numbering.

    Depots have demand 0 and keep their source ids, so the section stays aligned
    with ``NODE_COORD_SECTION``.

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

    for customer in problem.customer_nodes:
      lines.append(f"{customer.node_id} {customer.demand}")

    for depot in problem.depot_nodes:
      lines.append(f"{depot.node_id} 0")

    return lines

  def _generate_depot_section(self, problem: CordeauProblem) -> list[str]:
    """Generate DEPOT_SECTION with the depots' original node numbers.

    The depots keep their source ids (``n+1..n+t``), so the section is the map
    from *depot number* (position in this list, 1-based) to *node id*.

    Parameters
    ----------
    problem : CordeauProblem
        Problem data

    Returns
    -------
    list[str]
        Depot section lines
    """
    lines: list[str] = [f"{depot.node_id}" for depot in problem.depot_nodes]
    lines.append("-1")

    return lines
