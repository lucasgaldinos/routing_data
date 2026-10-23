"""Data transformation for TSPLIB converter."""

from __future__ import annotations

import itertools
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from tsplib_parser import matrix

if TYPE_CHECKING:
  from tsplib_parser.parser import FormatParser
  from tsplib_parser.types import ParseResult, ProblemData, TourDict


class DataTransformer:
  """
  Data transformation for TSPLIB converter.

  Features:
  - Normalize data for database/JSON storage
  - Format conversion and validation
  - Metadata enrichment
  - Index normalization (1-based to 0-based)
  """

  def __init__(self, logger: logging.Logger | None = None) -> None:
    """
    Initialize transformer.

    Args:
        logger: Optional logger instance
    """
    self.logger: logging.Logger = logger or logging.getLogger(__name__)

  def transform_problem(self, problem_data: ParseResult, file_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Transform parsed problem data for storage.

    Args:
        problem_data: Parsed problem data from parser
        file_info: Optional file metadata

    Returns:
        Transformed data ready for storage
    """
    problem_meta: dict[str, Any] = dict(problem_data["problem_data"])
    tours: list[TourDict] = problem_data["tours"]
    metadata: dict[str, Any] = dict(problem_data["metadata"])

    if file_info:
      metadata.update(
        {
          "scanned_file_path": file_info.get("file_path"),
          "scanned_file_size": file_info.get("file_size"),
          "detected_type": file_info.get("problem_type"),
        }
      )

    coords_raw: list[list[float]] = problem_data["coords"]
    display_coords_raw: list[list[float]] = problem_data["display_coords"]
    coords: list[list[float]] | None = [list(row) for row in coords_raw] if coords_raw else None
    display_coords: list[list[float]] | None = [list(row) for row in display_coords_raw] if display_coords_raw else None
    demands: list[int] = problem_data["demands"]
    depots: list[int] = problem_data["depots"]

    # Process edge weights if present (EXPLICIT problems)
    edge_weight_matrix: list[list[float]] | None = None
    if problem_meta.get("edge_weights"):
      try:
        edge_weight_matrix = self._convert_edge_weights_to_matrix(
          edge_weights=problem_meta["edge_weights"],
          edge_weight_format=cast("str", problem_meta.get("edge_weight_format")),
          dimension=cast("int", problem_meta.get("dimension")),
        )
        self.logger.info(f"Converted edge weights to {len(edge_weight_matrix)}x{len(edge_weight_matrix[0])} matrix")
      except Exception as e:
        self.logger.warning(msg=f"Failed to convert edge weights: {e}")
        import traceback

        self.logger.debug(msg=traceback.format_exc())
        edge_weight_matrix = None

      del problem_meta["edge_weights"]

    edges: list[list[int]] = problem_data["edges"]
    fixed_edges: list[list[int]] = problem_data["fixed_edges"]

    result: dict[str, Any] = {
      "problem_data": self._enrich_problem_data(problem_meta, metadata),
      "tours": tours,
      "metadata": metadata,
      "edges": edges,
      "fixed_edges": fixed_edges,
      "coords": coords,
      "display_coords": display_coords,
      "demands": demands,
      "depots": depots,
    }

    if edge_weight_matrix is not None:
      result["edge_weight_matrix"] = edge_weight_matrix

    return result

  def _convert_edge_weights_to_matrix(
    self,
    edge_weights: matrix.Matrix | list[list[float]],
    edge_weight_format: str,
    dimension: int,
  ) -> list[list[float]]:
    """Convert edge weights to full 2D matrix.

    Args:
        edge_weights: Matrix object or list[list[float]] from parser
        edge_weight_format: Matrix format (FULL_MATRIX, LOWER_DIAG_ROW, etc.)
        dimension: Problem dimension (number of nodes)

    Returns:
        Full 2D matrix as list of lists (dimension x dimension)
    """
    if isinstance(edge_weights, matrix.Matrix):
      matrix_size: int = edge_weights.size
      matrix_2d: list[list[int | float]] = [
        [edge_weights.value_at(i, j) for j in range(matrix_size)] for i in range(matrix_size)
      ]
      self.logger.debug(
        f"Extracted matrix from Matrix object: format={edge_weight_format}, "
        f"problem_dimension={dimension}, matrix_size={matrix_size}"
      )
      return matrix_2d

    weights: list[Any] = list(itertools.chain(*edge_weights))

    self.logger.debug(
      msg=f"Converting edge weights: format={edge_weight_format}, dimension={dimension}, total_weights={len(weights)}"
    )

    if edge_weight_format not in matrix.TYPES:
      raise ValueError(f"Unsupported edge weight format: {edge_weight_format}. Supported: {list(matrix.TYPES.keys())}")

    MatrixClass = matrix.TYPES[edge_weight_format]
    m = MatrixClass(weights, dimension, min_index=0)
    matrix_2d = [[m.value_at(i, j) for j in range(dimension)] for i in range(dimension)]

    self.logger.debug(f"Successfully converted to {dimension}x{dimension} matrix")
    return matrix_2d

  def _enrich_problem_data(self, problem_meta: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich problem metadata with additional information.

    Args:
        problem_meta: Basic problem metadata
        metadata: File and processing metadata

    Returns:
        Enriched problem metadata
    """
    enriched: dict[str, Any] = problem_meta.copy()

    if "file_path" in metadata:
      enriched["file_path"] = metadata["file_path"]
    if "file_size" in metadata:
      enriched["file_size"] = metadata["file_size"]

    return enriched

  def to_json_format(self, data: dict[str, Any]) -> dict[str, Any]:
    """
    Convert data to flattened JSON format.

    Args:
        data: Transformed problem data

    Returns:
        Data in JSON-friendly format
    """
    json_data: dict[str, Any] = {
      "problem": data.get("problem_data", {}),
      "tours": data.get("tours", []),
      "metadata": data.get("metadata", {}),
    }

    for key in ("coords", "display_coords", "demands", "depots", "edges", "fixed_edges"):
      if key in data:
        json_data[key] = data[key]

    return json_data

  def validate_transformation(self, data: dict[str, Any]) -> list[str]:
    """
    Validate transformed data.

    Args:
        data: Transformed data

    Returns:
        list of validation error messages (empty if valid)
    """
    errors: list[str] = []

    problem_data = data.get("problem_data", {})
    required_fields: dict[str, str] = {
      "name": "Problem name is required",
      "type": "Problem type is required",
      "dimension": "Problem dimension is required",
    }
    errors.extend(msg for field, msg in required_fields.items() if not problem_data.get(field))

    dimension = problem_data.get("dimension")
    if isinstance(dimension, int) and dimension > 0:
      coords = data.get("coords")
      if coords is not None and len(coords) != dimension:
        errors.append(f"coords length ({len(coords)}) does not match dimension ({dimension})")
      display_coords = data.get("display_coords")
      if display_coords is not None and len(display_coords) != dimension:
        errors.append(f"display_coords length ({len(display_coords)}) does not match dimension ({dimension})")

    return errors

  def find_solution_file(self, problem_file_path: str) -> str | None:
    """
    Find associated solution file (.opt.tour or .sol) for a problem file.

    Args:
        problem_file_path: Path to problem file

    Returns:
        Path to solution file if found, None otherwise
    """
    problem_path = Path(problem_file_path)
    problem_stem = problem_path.stem

    # Check for .opt.tour file (priority for TSP)
    # Structure: datasets_raw/zips/all_problems/{tsp,vrp,atsp}/file.tsp
    #            datasets_raw/zips/all_problems/tour/file.opt.tour
    parent_dir = problem_path.parent.parent  # all_problems directory
    tour_dir = parent_dir / "tour"
    tour_file = tour_dir / f"{problem_stem}.opt.tour"

    if tour_file.exists():
      self.logger.info(f"Found .opt.tour solution: {tour_file}")
      return str(tour_file)

    # Check for .sol file (VRP multi-route solutions)
    # Structure: datasets_raw/cvrplib/VRP-set-XXX/file.vrp
    #            datasets_raw/cvrplib/VRP-set-XXX/file.sol
    sol_file = problem_path.with_suffix(".sol")
    if sol_file.exists():
      self.logger.info(f"Found .sol solution: {sol_file}")
      return str(sol_file)

    return None

  def parse_solution_data(
    self, solution_file_path: str, parser: FormatParser, problem_dimension: int | None = None
  ) -> dict[str, Any] | None:
    """
    Parse solution file (.opt.tour or .sol) and extract solution data.

    Args:
        solution_file_path: Path to solution file
        parser: FormatParser instance
        problem_dimension: Dimension of the linked problem, forwarded to
            tour parsing to pre-inject a missing DIMENSION line
            (Decision #6).

    Returns:
        dictionary with solution data (routes as list of lists) or None if parsing fails
    """
    solution_path = Path(solution_file_path)

    # Check file extension to determine format
    if solution_path.suffix == ".sol":
      return self._parse_sol_file(sol_file_path=solution_file_path)
    elif solution_path.suffix == ".tour":
      return self._parse_tour_file(
        tour_file_path=solution_file_path, parser=parser, problem_dimension=problem_dimension
      )
    else:
      self.logger.warning(msg=f"Unknown solution format: {solution_path.suffix}")
      return None

  def _parse_tour_file(
    self, tour_file_path: str, parser: FormatParser, problem_dimension: int | None = None
  ) -> dict[str, Any] | None:
    """
    Parse .opt.tour file (TSPLIB single-tour format).

    Args:
        tour_file_path: Path to .opt.tour file
        parser: FormatParser instance
        problem_dimension: Dimension of the linked problem, used to
            pre-inject a DIMENSION line when the tour file lacks one
            (Decision #6, e.g. rd100.opt.tour).

    Returns:
        dictionary with routes (as [[tour]]) or None
    """
    try:
      # Decision #6: if the tour file lacks a DIMENSION line, pre-inject
      # the linked problem's dimension and parse from a temp file. Keeps
      # parser.parse_file/validate_problem behavior unchanged.
      tour_path = Path(tour_file_path)
      raw_text: str = tour_path.read_text(encoding="utf-8", errors="latin-1")
      has_dimension: re.Match[str] | None = re.search(pattern=r"^\s*DIMENSION\s*:", string=raw_text, flags=re.MULTILINE)
      parse_target: str = tour_file_path
      temp_path: str | None = None
      if not has_dimension and problem_dimension is not None:
        import tempfile

        injected_text: str = f"DIMENSION : {problem_dimension}\n{raw_text}"
        tmp: Any = tempfile.NamedTemporaryFile(mode="w", suffix=".tour", delete=False, encoding="utf-8")
        tmp.write(injected_text)
        tmp.close()
        temp_path = str(tmp.name)
        parse_target = temp_path
        self.logger.debug(msg=f"Pre-injected DIMENSION : {problem_dimension} into {tour_file_path}")

      try:
        # Parse TOUR file using format parser
        tour_data = parser.parse_file(parse_target)
      finally:
        if temp_path:
          Path(temp_path).unlink(missing_ok=True)

      # Extract solution information
      problem_data: ProblemData = tour_data["problem_data"]
      tours: list[TourDict] = tour_data["tours"]

      if not tours:
        self.logger.warning(f"No tours found in {tour_file_path}")
        return None

      # Extract cost from comment if available
      comment: str = problem_data.get("comment") or ""
      cost: float | None = self._extract_cost_from_comment(comment)

      # Get first tour - tours is list of dicts with 'tour_id' and 'nodes'.
      # `validate_parse_result` guarantees each entry is a TourDict.
      first_tour: TourDict = tours[0]
      tour_nodes: list[int] = first_tour["nodes"]

      # Note: parser.parse_file() already returns 0-based node indices
      # (see _extract_tours in parser.py), so no re-conversion is needed here.
      # Wrap single tour in list to match multi-route format: [[tour]]
      routes: list[Any] = [tour_nodes] if tour_nodes else []

      solution_data: dict[str, Any] = {
        "name": problem_data.get("name"),
        "type": problem_data.get("type"),
        "cost": cost,
        "routes": routes,
      }

      self.logger.info(msg=f"Parsed .opt.tour: {len(tour_nodes)} nodes, cost={cost}")
      return solution_data

    except Exception as e:
      self.logger.error(msg=f"Failed to parse .opt.tour file {tour_file_path}: {e}")
      return None

  def _parse_sol_file(self, sol_file_path: str) -> dict[str, Any] | None:
    """
    Parse .sol file (CVRPLIB multi-route format).

    Format:
        Route #1: node1 node2 node3 ...
        Route #2: node4 node5 node6 ...
        ...
        Cost value

    Args:
        sol_file_path: Path to .sol file

    Returns:
        dictionary with routes (as [[route1], [route2], ...]) or None
    """
    try:
      with open(sol_file_path) as f:
        content: str = f.read()

      # Extract all routes using regex
      route_pattern = r"Route #\d+:\s*([\d\s]+)"
      route_matches = re.findall(route_pattern, content)

      if not route_matches:
        self.logger.warning(f"No routes found in {sol_file_path}")
        return None

      # Parse each route (convert space-separated nodes to list of ints)
      # CRITICAL: Convert from 1-based to 0-based indexing
      routes: list[list[int]] = []
      for route_str in route_matches:
        nodes: list[int] = [int(n) - 1 for n in route_str.split()]  # Subtract 1 for 0-based indexing
        routes.append(nodes)

      # Extract cost
      cost = None
      cost_match: re.Match[str] | None = re.search(r"Cost\s+([\d.]+)", content)
      if cost_match:
        cost = float(cost_match.group(1))

      solution_data: dict[str, Any] = {
        "name": Path(sol_file_path).stem,
        "type": "VRP",
        "cost": cost,
        "routes": routes,
      }

      total_nodes: int = sum(len(route) for route in routes)
      self.logger.info(f"Parsed .sol: {len(routes)} routes, {total_nodes} nodes, cost={cost}")
      return solution_data

    except Exception as e:
      self.logger.error(f"Failed to parse .sol file {sol_file_path}: {e}")
      return None

  def _extract_cost_from_comment(self, comment: str) -> float | None:
    """
    Extract cost from TOUR comment field.

    Args:
        comment: Comment string (e.g., "Optimal solution of gr666 (294358)")

    Returns:
        Extracted cost or None
    """
    if not comment:
      return None

    # Match pattern: "...(number)"
    match = re.search(r"\((\d+(?:\.\d+)?)\)", comment)
    if match:
      try:
        return float(match.group(1))
      except ValueError:
        return None

    return None
