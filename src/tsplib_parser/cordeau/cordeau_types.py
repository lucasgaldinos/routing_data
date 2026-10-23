"""Type definitions for Cordeau MDVRP format.

This module defines dataclasses representing the structure of Cordeau's
benchmark instances for Multi-Depot Vehicle Routing Problems.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from ..models import LKHProblem
  from ..types import Metadata, ParseResult, ProblemData


@dataclass
class CordeauDepotConstraint:
  """Depot or vehicle type constraints.

  Attributes
  ----------
  max_duration : float
      Maximum route duration (D in Cordeau format)
  max_load : int
      Maximum vehicle capacity (Q in Cordeau format)
  """

  max_duration: float
  max_load: int


@dataclass
class CordeauNode:
  """Node in Cordeau problem (customer or depot).

  Attributes
  ----------
  node_id : int
      Original node number from file (1-based)
  x : float
      X coordinate
  y : float
      Y coordinate
  service_duration : float
      Service time at node (d in Cordeau format)
  demand : int
      Demand quantity (q in Cordeau format)
  frequency : int, optional
      Visit frequency for PVRP (f in Cordeau format)
  num_combinations : int, optional
      Number of visit combinations for PVRP (a in Cordeau format)
  visit_combinations : List[int], optional
      List of visit combination codes for PVRP
  earliest_time : float, optional
      Earliest service time for VRPTW (e in Cordeau format)
  latest_time : float, optional
      Latest service time for VRPTW (l in Cordeau format)
  is_depot : bool
      Whether this node is a depot
  """

  node_id: int
  x: float
  y: float
  service_duration: float
  demand: int
  frequency: int | None = None
  num_combinations: int | None = None
  visit_combinations: list[int] | None = None
  earliest_time: float | None = None
  latest_time: float | None = None
  is_depot: bool = False


@dataclass
class CordeauProblem:
  """Complete Cordeau problem instance (source-format record, not a TSPLIB model).

  Cordeau files are positional (``type m n t``), not keyword-driven TSPLIB, so this
  class intentionally does not implement :class:`tsplib_parser.models.Problem`: it has
  no ``Field`` descriptors, no ``parse()``, and no ``Problem(**kwargs)`` constructor.
  :meth:`to_lkh` is the conversion boundary that yields a TSPLIB-side ``LKHProblem``.

  Section values are 1-based (``node_id`` is the file's node number). The 0-based
  payload contract lives in :class:`tsplib_parser.types.ParseResult`.

  Attributes
  ----------
  name : str
      Problem name (filename without extension)
  problem_type : int
      Cordeau problem type (0-7):
      0=VRP, 1=PVRP, 2=MDVRP, 3=SDVRP,
      4=VRPTW, 5=PVRPTW, 6=MDVRPTW, 7=SDVRPTW
  num_vehicles : int
      Number of vehicles (m in Cordeau format)
  num_customers : int
      Number of customers (n in Cordeau format)
  num_depots : int
      Number of depots/days/vehicle types (t in Cordeau format)
  depot_constraints : List[CordeauDepotConstraint]
      Constraints for each depot/vehicle type (t items)
  nodes : List[CordeauNode]
      All nodes: first n are customers, last t are depots
  """

  name: str
  problem_type: int
  num_vehicles: int
  num_customers: int
  num_depots: int
  depot_constraints: list[CordeauDepotConstraint]
  nodes: list[CordeauNode]

  def __post_init__(self) -> None:
    """Validate problem structure."""
    expected_nodes = self.num_customers + self.num_depots
    if len(self.nodes) != expected_nodes:
      raise ValueError(
        f"Expected {expected_nodes} nodes "
        f"({self.num_customers} customers + {self.num_depots} depots), "
        f"got {len(self.nodes)}"
      )

    if len(self.depot_constraints) != self.num_depots:
      raise ValueError(f"Expected {self.num_depots} depot constraints, got {len(self.depot_constraints)}")

  @property
  def type_name(self) -> str:
    """Get human-readable problem type name."""
    type_names: dict[int, str] = {
      0: "VRP",
      1: "PVRP",
      2: "MDVRP",
      3: "SDVRP",
      4: "VRPTW",
      5: "PVRPTW",
      6: "MDVRPTW",
      7: "SDVRPTW",
    }
    return type_names.get(self.problem_type, f"UNKNOWN({self.problem_type})")

  @property
  def dimension(self) -> int:
    """Total number of nodes (customers + depots)."""
    return self.num_customers + self.num_depots

  @property
  def customer_nodes(self) -> list[CordeauNode]:
    """Get customer nodes only."""
    return [n for n in self.nodes if not n.is_depot]

  @property
  def depot_nodes(self) -> list[CordeauNode]:
    """Get depot nodes only."""
    return [n for n in self.nodes if n.is_depot]

  def as_dict(self, by_keyword: bool = False) -> dict[str, Any]:
    """Return the problem data as a normalized dictionary."""
    name_key = "NAME" if by_keyword else "name"
    type_key = "TYPE" if by_keyword else "type"
    dim_key = "DIMENSION" if by_keyword else "dimension"
    coord_key = "NODE_COORD_SECTION" if by_keyword else "node_coords"
    demand_key = "DEMAND_SECTION" if by_keyword else "demands"
    depot_key = "DEPOT_SECTION" if by_keyword else "depots"
    veh_key = "VEHICLES" if by_keyword else "vehicles"
    dist_key = "DISTANCE" if by_keyword else "max_distance"

    total_vehicles: int = self.num_vehicles * self.num_depots

    data: dict[str, Any] = {
      name_key: self.name,
      type_key: self.type_name,
      dim_key: self.dimension,
      coord_key: {n.node_id: (n.x, n.y) for n in self.nodes},
      demand_key: {n.node_id: n.demand for n in self.nodes},
      depot_key: [n.node_id for n in self.depot_nodes],
      veh_key: total_vehicles,
      "num_depots": self.num_depots,
      "num_customers": self.num_customers,
      "depot_constraints": [
        {"max_duration": c.max_duration, "max_load": c.max_load} for c in self.depot_constraints
      ],
    }

    capacities: set[int] = {c.max_load for c in self.depot_constraints}
    if len(capacities) == 1:
      cap_key = "CAPACITY" if by_keyword else "capacity"
      data[cap_key] = self.depot_constraints[0].max_load

    durations: set[float] = {c.max_duration for c in self.depot_constraints}
    if len(durations) == 1 and self.depot_constraints[0].max_duration > 0:
      data[dist_key] = self.depot_constraints[0].max_duration

    time_windows: dict[int, tuple[float, float]] = {
      n.node_id: (n.earliest_time, n.latest_time)
      for n in self.nodes
      if n.earliest_time is not None and n.latest_time is not None
    }
    if time_windows:
      tw_key = "TIME_WINDOW_SECTION" if by_keyword else "time_windows"
      srv_key = "SERVICE_TIME_SECTION" if by_keyword else "service_times"
      data[tw_key] = time_windows
      data[srv_key] = {n.node_id: (n.service_duration,) for n in self.nodes}

    return data

  def to_parse_result(self, file_path: str | Path | None = None) -> "ParseResult":
    """Convert this problem to the 0-based ``ParseResult`` payload contract.

    Node order matches the TSPLIB file that :meth:`CordeauConverter.to_tsplib`
    writes: depots first (indices ``0..num_depots - 1``), customers after. The
    arrays are 0-based, unlike :meth:`as_dict`, which keeps the source file's
    1-based Cordeau order.

    Parameters
    ----------
    file_path : str or Path, optional
        Source path used to fill ``metadata``. When omitted, the metadata falls
        back to the problem name and a zero file size.

    Returns
    -------
    ParseResult
        Payload with ``coords``, ``demands``, ``depots``, ``problem_data`` and
        ``metadata`` filled; graph and tour fields are empty.
    """
    nodes: list[CordeauNode] = [*self.depot_nodes, *self.customer_nodes]
    capacities: set[int] = {constraint.max_load for constraint in self.depot_constraints}
    durations: set[float] = {constraint.max_duration for constraint in self.depot_constraints}

    problem_data: ProblemData = {
      "name": self.name,
      "type": self.type_name,
      "comment": None,
      "dimension": self.dimension,
      "capacity": self.depot_constraints[0].max_load if len(capacities) == 1 else None,
      "node_coord_type": None,
      "edge_weight_type": "EUC_2D",
      "edge_weight_format": None,
      "display_data_type": None,
      "edge_data_format": None,
      "vehicles": self.num_vehicles * self.num_depots,
      "num_depots": self.num_depots,
    }

    # Mirror the sections ``CordeauConverter.to_tsplib(as_lkh=True)`` emits.
    if len(capacities) > 1:
      problem_data["depot_capacities"] = [constraint.max_load for constraint in self.depot_constraints]
    if len(durations) > 1:
      problem_data["depot_durations"] = {
        index: constraint.max_duration for index, constraint in enumerate(self.depot_constraints, start=1)
      }
    if len(durations) == 1 and self.depot_constraints[0].max_duration > 0:
      problem_data["max_distance"] = self.depot_constraints[0].max_duration
    if any(node.earliest_time is not None for node in nodes):
      problem_data["time_windows"] = [
        [
          node.earliest_time if node.earliest_time is not None else 0.0,
          node.latest_time if node.latest_time is not None else 0.0,
        ]
        for node in nodes
      ]
      if any(node.service_duration > 0 for node in nodes):
        problem_data["service_times"] = [[node.service_duration] for node in nodes]

    path: Path | None = Path(file_path) if file_path is not None else None
    metadata: Metadata = {
      "file_path": str(path) if path is not None else "",
      "file_name": path.name if path is not None else self.name,
      "file_size": path.stat().st_size if path is not None and path.exists() else 0,
      "problem_source": path.parent.name if path is not None else None,
      "has_coordinates": True,
      "has_display_coords": False,
      "has_demands": bool(nodes),
      "has_depots": self.num_depots > 0,
      "has_tours": False,
      "has_edges": False,
      "has_fixed_edges": False,
      "is_symmetric": True,
      "weight_source": "coordinate_based",
    }

    return {
      "problem_data": problem_data,
      "coords": [[node.x, node.y] for node in nodes],
      "display_coords": [],
      "demands": [node.demand for node in nodes],
      "depots": list(range(self.num_depots)),
      "edges": [],
      "fixed_edges": [],
      "tours": [],
      "metadata": metadata,
    }

  def to_lkh(self) -> "LKHProblem":
    """Convert this CordeauProblem to an in-memory LKHProblem model."""
    from ..models import LKHProblem

    lkh = LKHProblem()
    lkh.name = self.name
    lkh.problem_type = self.type_name
    lkh.dimension = self.dimension
    lkh.edge_weight_type = "EUC_2D"
    lkh.vehicles = self.num_vehicles * self.num_depots
    lkh.num_depots = self.num_depots

    capacities: set[int] = {c.max_load for c in self.depot_constraints}
    if len(capacities) == 1:
      lkh.capacity = self.depot_constraints[0].max_load

    durations: set[float] = {c.max_duration for c in self.depot_constraints}
    if len(durations) == 1 and self.depot_constraints[0].max_duration > 0:
      lkh.max_distance = self.depot_constraints[0].max_duration

    lkh.node_coords = {n.node_id: (n.x, n.y) for n in self.nodes}
    lkh.demands = {n.node_id: n.demand for n in self.nodes}
    lkh.depots = [n.node_id for n in self.depot_nodes]

    time_windows: dict[int, tuple[float, float]] = {
      n.node_id: (n.earliest_time, n.latest_time)
      for n in self.nodes
      if n.earliest_time is not None and n.latest_time is not None
    }
    if time_windows:
      lkh.time_windows = time_windows
      lkh.service_times = {n.node_id: (n.service_duration,) for n in self.nodes}

    return lkh
