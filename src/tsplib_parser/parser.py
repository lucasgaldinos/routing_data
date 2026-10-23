"""TSPLIB95 parser integration for ETL converter."""

import logging
from pathlib import Path
from typing import Any, cast

from .exceptions import FormatError, ParseError, ValidationError
from .fields import DemandsField, IndexedCoordinatesField
from .matrix import Matrix
from .models import (
  StandardProblem,
  get_problem_class_for_type,
)
from .types import (
  Metadata,
  ParseResult,
  ProblemData,
  TourDict,
  WeightSource,
  normalize_problem_type,
)
from .validation import (
  check_symmetry,
  identify_weight_source,
  validate_parse_result,
  validate_problem_data,
)

#: DUE_DATE_SECTION: due date for service
_STRIPPED_SECTIONS: dict[str, str] = {
  "TIME_WINDOW_SECTION": "has_time_windows",
  "PICKUP_AND_DELIVERY_SECTION": "has_pickup_delivery",
  "PICKUP_SECTION": "has_pickup_delivery",
  "SERVICE_TIME_SECTION": "has_service_times",
  "BACKHAUL_SECTION": "has_backhauls",
  "DELIVERY_SECTION": "",
  "PICKUP_DELIVERY_SECTION": "",
  "STANDTIME_SECTION": "",
  "READY_TIME_SECTION": "",
  "DUE_DATE_SECTION": "",
}

#: Extended VRP/LKH-3 header lines (``"VEHICLES : 16"``). ``_preprocess_vrp_file``
#: strips them only when the target problem class does not register the keyword,
#: mirroring the ``*_SECTION`` handling in ``_STRIPPED_SECTIONS``. Stripping a
#: registered header would downgrade the typed field to a raw string
#: (``vehicles`` becoming ``"16"``) and drop the model's own key (``num_depots``).
_VRP_HEADER_FIELDS: tuple[str, ...] = (
  "SERVICE_TIME",
  "TIME_WINDOW",
  "PICKUP_DELIVERY",
  "VEHICLES",
  "DEPOTS",
  "PERIODS",
)


def _extract_header_type(content: str) -> str | None:
  """Peek at the leading header lines to extract the declared problem TYPE."""
  for raw_line in content.splitlines():
    line: str = raw_line.strip()
    if line.startswith("TYPE"):
      parts: list[str] = line.split(":", 1)
      if len(parts) == 2:
        return normalize_problem_type(parts[1])
    elif line.endswith("_SECTION") or line == "EOF":
      break
  return None


class FormatParser:
  """TSPLIB95 file parser with complete extraction, normalization, and validation.

  Parses TSPLIB95-format routing problems (TSP, CVRP, ATSP, HCP, SOP, TOUR)
  and extended subclasses (such as :class:`LKHProblem`), extracting structured
  schema-v2 array columns with 0-based indices and two-stage validation
  (pre-extraction 1-based spec checks and post-extraction 0-based contract checks).
  """

  def __init__(
    self,
    logger: logging.Logger | None = None,
    problem_class: type[StandardProblem] | None = None,
  ) -> None:
    """Initialize TSPLIB parser.

    Parameters
    ----------
    logger : logging.Logger, optional
        Logger instance for tracking parsing operations.
    problem_class : type[StandardProblem], optional
        Problem model class used to parse files. If None (default),
        automatically dispatches to the registered class for the file's
        declared ``TYPE`` header via :func:`get_problem_class_for_type`.
    """
    self.logger: logging.Logger = logger or logging.getLogger(name=__name__)
    self.problem_class: type[StandardProblem] | None = problem_class
    self._additional_vrp_fields: dict[str, Any] = {}

  def parse_file(
    self,
    file_path: str | Path,
    problem_class: type[StandardProblem] | None = None,
  ) -> ParseResult:
    """Parse TSPLIB file and return complete normalized schema-v2 data structure.

    Parameters
    ----------
    file_path : str or Path
        Path to TSPLIB file to parse.
    problem_class : type[StandardProblem], optional
        Override ``self.problem_class`` (or automatic registry dispatch)
        for this specific parse call.

    Returns
    -------
    ParseResult
        Normalized payload with keys:
        - ``problem_data`` : dict - Header metadata and ``edge_weights`` Matrix
        - ``coords`` : list[list[float]] - 0-based node coordinates
        - ``display_coords`` : list[list[float]] - 0-based display coordinates
        - ``demands`` : list[int] - 0-based node demands
        - ``depots`` : list[int] - 0-based depot node indices
        - ``edges`` : list[list[int]] - 0-based graph edges
        - ``fixed_edges`` : list[list[int]] - 0-based fixed edges
        - ``tours`` : list[TourDict] - 0-based solution tours
        - ``metadata`` : dict - File, symmetry, and section presence metadata

    Raises
    ------
    ParseError
        If file reading or syntax parsing fails.
    ValidationError
        If pre-extraction or post-extraction validation fails.
    """
    self._additional_vrp_fields = {}
    cls_to_use: type[StandardProblem] | None = problem_class or self.problem_class

    try:
      try:
        with open(file=file_path, encoding="utf-8") as f:
          raw_content: str = f.read()
      except UnicodeDecodeError:
        with open(file=file_path, encoding="latin-1") as f:
          raw_content = f.read()

      if cls_to_use is None:
        declared_type: str | None = _extract_header_type(raw_content)
        cls_to_use = get_problem_class_for_type(declared_type)

      text, additional_fields = self._preprocess_vrp_file(
        file_path=file_path,
        problem_class=cls_to_use,
        content=raw_content,
      )
      self._additional_vrp_fields = additional_fields
      problem: StandardProblem = cls_to_use.parse(text)

      # Convert once and share between Stage 1 validation and extraction
      raw_data: dict[str, Any] = problem.as_name_dict()

      # Stage 1: Pre-extraction 1-based spec validation
      self.validate_problem(problem, raw_data=raw_data)

      # Extract 0-based schema-v2 components
      problem_data: ProblemData = self._extract_problem_data(problem, raw_data=raw_data)
      coords: list[list[float]] = self._extract_coords(problem)
      display_coords: list[list[float]] = self._extract_display_coords(problem)
      demands, depots = self._extract_demands_depots(problem)
      edges: list[list[int]] = self._extract_edges(problem)
      fixed_edges: list[list[int]] = self._extract_fixed_edges(problem)
      tours: list[TourDict] = self._extract_tours(problem)
      metadata: Metadata = self._extract_metadata(
        problem=problem,
        file_path=file_path,
        problem_data=problem_data,
        coords=coords,
        display_coords=display_coords,
        demands=demands,
        depots=depots,
        edges=edges,
        fixed_edges=fixed_edges,
        tours=tours,
      )

      result: ParseResult = {
        "problem_data": problem_data,
        "coords": coords,
        "display_coords": display_coords,
        "demands": demands,
        "depots": depots,
        "edges": edges,
        "fixed_edges": fixed_edges,
        "tours": tours,
        "metadata": metadata,
      }

      # Stage 2: Post-extraction 0-based contract validation
      post_errors: list[str] = validate_parse_result(result, problem_class=cls_to_use)
      if post_errors:
        raise ValidationError(f"Post-extraction validation errors: {'; '.join(post_errors)}")

      problem_type: Any = problem_data.get("type")
      dimension: int = int(problem_data.get("dimension", 0) or 0)
      if not coords and dimension > 0:
        self.logger.info(msg=f"Successfully parsed {file_path}: {problem_type} dim={dimension} (no node coords)")
      else:
        self.logger.info(msg=f"Successfully parsed {file_path}: {problem_type} with {len(coords)} coords")
      return result

    except FormatError:
      raise
    except Exception as e:
      raise ParseError(f"Failed to parse {file_path}: {e}") from e

  def _preprocess_vrp_file(
    self,
    file_path: str | Path,
    problem_class: type[StandardProblem] = StandardProblem,
    content: str | None = None,
  ) -> tuple[str, dict[str, Any]]:
    """Preprocess VRP file in-memory to handle extended LKH-3 / VRP variants not registered on ``problem_class``.

    Returns
    -------
    tuple[str, dict[str, Any]]
        The preprocessed file content string and any extracted additional fields.
    """
    if content is None:
      try:
        with open(file=file_path, encoding="utf-8") as f:
          content = f.read()
      except UnicodeDecodeError:
        with open(file=file_path, encoding="latin-1") as f:
          content = f.read()

    original_content: str = content
    additional_fields: dict[str, Any] = {}

    lines: list[str] = content.split("\n")
    processed_lines: list[str] = []
    i: int = 0

    in_demand_section: bool = False
    stripped_sections: list[str] = []

    # Headers the target class can parse as typed fields must reach the parser
    # untouched; only the leftovers of extended specs may be stripped here.
    registered_keywords: frozenset[str] = frozenset(problem_class.fields_by_keyword)
    unregistered_headers: frozenset[str] = frozenset(_VRP_HEADER_FIELDS).difference(registered_keywords)

    while i < len(lines):
      line: str = lines[i].strip()

      if line == "DEMAND_SECTION":
        in_demand_section = True
        processed_lines.append(line)
      elif line.endswith("_SECTION") or line == "EOF":
        in_demand_section = False

        flag: str | None = _STRIPPED_SECTIONS.get(line)
        if flag is not None and line not in problem_class.fields_by_keyword:
          if flag:
            additional_fields[flag] = True
          stripped_sections.append(line)
          j: int = i + 1
          while j < len(lines) and not lines[j].strip().endswith("_SECTION") and lines[j].strip() != "EOF":
            j += 1
          i = j - 1
        else:
          processed_lines.append(line)
      elif in_demand_section and line:
        parts: list[str] = line.split()
        if len(parts) >= 3:
          node_id: str = parts[0]
          weight_demand: str = parts[1]
          volume_demand: str = parts[2] if len(parts) > 2 else "0"

          if "volume_demands" not in additional_fields:
            additional_fields["volume_demands"] = {}
          additional_fields["volume_demands"][int(node_id)] = int(volume_demand)

          processed_lines.append(f"{node_id} {weight_demand}")
        else:
          processed_lines.append(line)

      elif line.startswith("CAPACITY :"):
        capacity_match: list[str] = line.split(":", 1)
        if len(capacity_match) == 2:
          processed_lines.append(f"CAPACITY : {capacity_match[1].strip()}")

          j = i + 1
          while j < len(lines):
            next_line: str = lines[j].strip()
            if next_line.startswith("CAPACITY_VOL :"):
              vol_value: str = next_line.split(":", 1)[1].strip()
              additional_fields["capacity_vol"] = int(vol_value)
              j += 1
            elif next_line.startswith("CAPACITY_WEIGHT :"):
              weight_value: str = next_line.split(":", 1)[1].strip()
              additional_fields["capacity_weight"] = int(weight_value)
              j += 1
            elif next_line.startswith(("NODE_COORD_SECTION", "DEMAND_SECTION", "DEPOT_SECTION", "EOF")):
              break
            elif next_line and ":" in next_line and not next_line.startswith("CAPACITY"):
              break
            else:
              j += 1
          i = j - 1

      elif line.startswith("DISTANCE :") and "DISTANCE" not in registered_keywords:
        distance_value: str = line.split(":", 1)[1].strip()
        additional_fields["max_distance"] = float(distance_value)

      elif any(line.startswith(f"{field} :") for field in unregistered_headers):
        field_name: str = line.split(":")[0].strip().lower()
        field_value: str = line.split(":", 1)[1].strip()
        additional_fields[field_name] = field_value

      else:
        processed_lines.append(line)

      i += 1

    if stripped_sections:
      additional_fields["stripped_sections"] = stripped_sections
    self._additional_vrp_fields = additional_fields

    if additional_fields:
      processed_content: str = "\n".join(processed_lines)
      if processed_content != original_content:
        self.logger.debug(
          f"Preprocessed VRP file {file_path} in-memory (additional fields: {list(additional_fields.keys())})"
        )
        return processed_content, additional_fields

    return original_content, additional_fields

  def _extract_problem_data(
    self,
    problem: StandardProblem,
    raw_data: dict[str, Any] | None = None,
  ) -> ProblemData:
    """Extract problem header metadata, extended subclass sections, and explicit weight matrix.

    Iterates dynamically over fields declared on ``problem``'s class so
    ``StandardProblem`` subclasses (such as :class:`LKHProblem`) automatically
    surface their header and extended section fields without modifying
    ``FormatParser``. Preserves normalized TSPLIB ``type`` (never overwriting
    it with ``MC-VRP``/``TW-VRP`` compound strings).

    Returns
    -------
    ProblemData
        The declared core keys are checked against :class:`ProblemData` at
        construction. Extended LKH-3 sections and VRP-preprocessing fields are
        dynamic (``result[field_name] = ...`` with a runtime key), so they are
        collected separately and merged into the same payload.
    """
    data: dict[str, Any] = raw_data if raw_data is not None else problem.as_name_dict()

    raw_type: str = str(data.get("problem_type", "") or "")
    normalized_type: str = self._normalize_problem_type(raw_type) or ""
    dimension: int = int(data.get("dimension", 0) or 0)

    result: ProblemData = {
      "name": data.get("name"),
      "type": normalized_type,
      "comment": data.get("comment"),
      "dimension": data.get("dimension"),
      "capacity": data.get("capacity"),
      "edge_weight_type": data.get("edge_weight_type"),
      "edge_weight_format": data.get("edge_weight_format"),
      "node_coord_type": data.get("node_coord_type"),
      "display_data_type": data.get("display_data_type"),
      "edge_data_format": data.get("edge_data_format"),
    }
    #: Keys that only exist for some problem classes (extended LKH-3 headers and
    #: sections) or that come from VRP preprocessing; ``ProblemData`` declares the
    #: known ones as ``NotRequired`` and cannot express the rest.
    extras: dict[str, Any] = {}

    core_section_names: frozenset[str] = frozenset(StandardProblem.fields_by_name.keys())

    # Dynamically include additional header and extended section fields from subclasses (e.g. LKHProblem)
    for field_name, field_obj in problem.__class__.fields_by_name.items():
      if field_name == "problem_type" or field_name in result or field_name in extras or field_name not in data:
        continue
      if field_obj.keyword.endswith("_SECTION"):
        if field_name in core_section_names:
          continue
        sec_val: object = data[field_name]
        if isinstance(field_obj, IndexedCoordinatesField) and isinstance(sec_val, dict) and dimension > 0:
          coord_rows: dict[int, list[float]] = cast("dict[int, list[float]]", sec_val)
          extras[field_name] = [[float(c) for c in coord_rows[i + 1]] for i in range(dimension)]
        elif isinstance(field_obj, DemandsField) and isinstance(sec_val, dict) and dimension > 0:
          demand_rows: dict[int, int] = cast("dict[int, int]", sec_val)
          extras[field_name] = [int(demand_rows[i + 1]) for i in range(dimension)]
        else:
          extras[field_name] = sec_val
      else:
        extras[field_name] = data[field_name]

    # Attach explicit Matrix object when EDGE_WEIGHT_SECTION is present
    if getattr(problem, "edge_weights", None):
      matrix_obj: Matrix | None = problem.create_explicit_matrix()
      extras["edge_weights"] = matrix_obj if matrix_obj is not None else problem.edge_weights

    # Merge VRP extension flags/fields without mutating the canonical TSPLIB type (PB4)
    for field_name, field_value in self._additional_vrp_fields.items():
      if field_name not in result and field_name not in extras:
        extras[field_name] = field_value

    return cast("ProblemData", {**result, **extras})

  def _normalize_problem_type(self, raw_type: str | None) -> str | None:
    """Normalize problem type strings to canonical TSPLIB95/LKH-3 types."""
    return normalize_problem_type(raw_type)

  def _extract_coords(self, problem: StandardProblem) -> list[list[float]]:
    """Extract 0-based ``coords`` array (``list[list[float]]``) from ``NODE_COORD_SECTION``.

    Index ``i`` corresponds to 1-based TSPLIB node ``i + 1``.
    Returns ``[]`` when ``NODE_COORD_SECTION`` is absent.
    """
    node_coords: dict[int, list[float]] | None = getattr(problem, "node_coords", None)
    if not node_coords:
      return []
    dimension: int = int(getattr(problem, "dimension", 0) or 0)
    return [[float(c) for c in node_coords[i + 1]] for i in range(dimension)]

  def _extract_display_coords(self, problem: StandardProblem) -> list[list[float]]:
    """Extract 0-based ``display_coords`` array (``list[list[float]]``) from ``DISPLAY_DATA_SECTION``.

    Index ``i`` corresponds to 1-based TSPLIB node ``i + 1``.
    Returns ``[]`` when ``DISPLAY_DATA_SECTION`` is absent.
    """
    display_data: dict[int, list[float]] | None = getattr(problem, "display_data", None)
    if not display_data:
      return []
    dimension: int = int(getattr(problem, "dimension", 0) or 0)
    return [[float(c) for c in display_data[i + 1]] for i in range(dimension)]

  def _extract_demands_depots(self, problem: StandardProblem) -> tuple[list[int], list[int]]:
    """Extract 0-based ``demands`` and ``depots`` arrays from ``DEMAND_SECTION`` and ``DEPOT_SECTION``."""
    dimension: int = int(getattr(problem, "dimension", 0) or 0)

    demands_raw: dict[int, int] | None = getattr(problem, "demands", None)
    if demands_raw:
      demands: list[int] = [int(demands_raw[i + 1]) for i in range(dimension)]
    else:
      demands = []

    depots_raw: list[Any] | int | None = getattr(problem, "depots", None)
    if isinstance(depots_raw, list):
      depots: list[int] = sorted(int(d) - 1 for d in depots_raw)
    elif depots_raw is not None:
      depots = [int(depots_raw) - 1]
    else:
      depots = []
    return demands, depots

  def _extract_tours(self, problem: StandardProblem) -> list[TourDict]:
    """Extract solution tours with 0-based node indices."""
    tours: list[TourDict] = []

    tour_data: Any = getattr(problem, "tours", None)
    if tour_data:
      for idx, tour in enumerate(tour_data):
        tour_nodes: list[int] = [int(node) - 1 for node in tour if node != -1]
        tours.append({"tour_id": idx, "nodes": tour_nodes})

    return tours

  def _extract_edges(self, problem: StandardProblem) -> list[list[int]]:
    """Extract graph edges from ``EDGE_DATA_SECTION`` as 0-based ``[from, to]`` pairs."""
    raw_edges: list[list[int]] | None = getattr(problem, "edge_data", None)
    if not raw_edges:
      return []
    return [[int(u) - 1, int(v) - 1] for u, v in raw_edges]

  def _extract_fixed_edges(self, problem: StandardProblem) -> list[list[int]]:
    """Extract fixed edges from ``FIXED_EDGES_SECTION`` as 0-based ``[from, to]`` pairs."""
    raw_edges: list[list[int]] | None = getattr(problem, "fixed_edges", None)
    if not raw_edges:
      return []
    return [[int(u) - 1, int(v) - 1] for u, v in raw_edges]

  def _extract_metadata(
    self,
    problem: StandardProblem,
    file_path: str | Path,
    problem_data: ProblemData | None = None,
    coords: list[list[float]] | None = None,
    display_coords: list[list[float]] | None = None,
    demands: list[int] | None = None,
    depots: list[int] | None = None,
    edges: list[list[int]] | None = None,
    fixed_edges: list[list[int]] | None = None,
    tours: list[TourDict] | None = None,
  ) -> Metadata:
    """Extract file, symmetry, weight source, and section-presence metadata."""
    file_path_obj = Path(file_path)
    matrix_obj: Matrix | None = None
    edge_weights_val: Any = problem_data.get("edge_weights") if problem_data else None
    if isinstance(edge_weights_val, Matrix):
      matrix_obj = edge_weights_val

    has_coords: bool = bool(coords) if coords is not None else bool(getattr(problem, "node_coords", None))
    has_disp: bool = (
      bool(display_coords) if display_coords is not None else bool(getattr(problem, "display_data", None))
    )
    has_dem: bool = bool(demands) if demands is not None else bool(getattr(problem, "demands", None))
    has_dep: bool = bool(depots) if depots is not None else bool(getattr(problem, "depots", None))
    has_edg: bool = bool(edges) if edges is not None else bool(getattr(problem, "edge_data", None))
    has_fix: bool = bool(fixed_edges) if fixed_edges is not None else bool(getattr(problem, "fixed_edges", None))
    has_trs: bool = bool(tours) if tours is not None else bool(getattr(problem, "tours", None))

    return {
      "file_path": str(file_path),
      "file_size": file_path_obj.stat().st_size if file_path_obj.exists() else 0,
      "file_name": file_path_obj.name,
      "problem_source": file_path_obj.parent.name,
      "has_coordinates": has_coords,
      "has_display_coords": has_disp,
      "has_demands": has_dem,
      "has_depots": has_dep,
      "has_edges": has_edg,
      "has_fixed_edges": has_fix,
      "has_tours": has_trs,
      "is_symmetric": self._check_symmetry(problem, matrix_obj=matrix_obj),
      "weight_source": self._identify_weight_source(problem),
    }

  def _check_symmetry(self, problem: StandardProblem, matrix_obj: Matrix | None = None) -> bool | None:
    """Delegate symmetry check to :func:`tsplib_parser.validation.check_symmetry`."""
    if matrix_obj is None and getattr(problem, "edge_weights", None):
      matrix_obj = problem.create_explicit_matrix()
    return check_symmetry(
      problem_type=getattr(problem, "problem_type", None),
      edge_weight_type=getattr(problem, "edge_weight_type", None),
      matrix_obj=matrix_obj,
    )

  def _identify_weight_source(self, problem: StandardProblem) -> WeightSource:
    """Delegate weight-source identification to :func:`tsplib_parser.validation.identify_weight_source`."""
    return identify_weight_source(
      edge_weight_type=getattr(problem, "edge_weight_type", None),
      edge_weight_format=getattr(problem, "edge_weight_format", None),
    )

  def validate_problem(
    self,
    problem: StandardProblem,
    raw_data: dict[str, Any] | None = None,
  ) -> None:
    """Validate pre-extraction 1-based problem structure and spec invariants."""
    if not isinstance(problem, StandardProblem):
      raise ValidationError("Not a valid StandardProblem")

    data: dict[str, Any] = (raw_data if raw_data is not None else problem.as_name_dict()).copy()
    if "problem_type" in data:
      data["type"] = self._normalize_problem_type(raw_type=data["problem_type"])
      del data["problem_type"]
    errors: list[str] = validate_problem_data(data=data, problem_class=problem.__class__)

    if errors:
      raise ValidationError(f"Validation errors: {'; '.join(errors)}")
