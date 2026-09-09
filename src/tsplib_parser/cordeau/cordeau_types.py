"""Type definitions for Cordeau MDVRP format.

This module defines dataclasses representing the structure of Cordeau's
benchmark instances for Multi-Depot Vehicle Routing Problems.
"""

from dataclasses import dataclass


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
  """Complete Cordeau problem instance.

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
