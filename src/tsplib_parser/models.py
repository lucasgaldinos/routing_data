"""
Core TSPLIB95 parsing models and field system.

This module contains the domain models (Problem, StandardProblem, LKHProblem)
and problem registry for TSPLIB95 and LKH-3 routing problems.
"""

import itertools
import logging
from typing import Any, Self, cast

from . import exceptions, matrix
from .fields import (
  DemandsField,
  DepotsField,
  DurationsField,
  EdgeDataField,
  EdgeListField,
  Field,
  IndexedCoordinatesField,
  IntegerField,
  MatrixField,
  NumberField,
  StringField,
  ToursField,
)
from .tokenization import _split_tsplib_text
from .types import LKH_PROBLEM_TYPES, NO_DIAG_FORMAT_FALLBACK, VALID_PROBLEM_TYPES

logger: logging.Logger = logging.getLogger(__name__)


class FileMeta(type):
  """Metaclass that builds field mappings for Problem classes."""

  # Class attributes that will be added to Problem classes
  fields_by_name: dict[str, Field]
  fields_by_keyword: dict[str, Field]

  def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type:
    cls = super().__new__(mcs, name, bases, attrs)

    # collect fields from this class and all parent classes
    fields: dict[str, Field] = {}
    for klass in reversed(cls.__mro__):
      for key, value in vars(klass).items():
        if isinstance(value, Field):
          fields[key] = value

    # build name/keyword mappings
    cls.fields_by_name = fields
    cls.fields_by_keyword = {f.keyword: f for f in fields.values()}

    return cls


class Problem(metaclass=FileMeta):
  """Base problem class."""

  # Attributes added by metaclass
  fields_by_name: dict[str, Field]
  fields_by_keyword: dict[str, Field]

  def __init__(self, **kwargs: Any) -> None:
    for name, value in kwargs.items():
      setattr(self, name, value)

  def as_dict(self, by_keyword: bool = False) -> dict[str, Any]:
    """Return the problem data as a dictionary."""
    data: dict[str, Any] = {}
    for name, field in self.__class__.fields_by_name.items():
      value = getattr(self, name)
      if name in self.__dict__ or value != field.get_default_value():
        key: str = field.keyword if by_keyword else name
        data[key] = value
    return data

  def as_name_dict(self) -> dict[str, Any]:
    """Return the problem data as a dictionary by field name."""
    return self.as_dict(by_keyword=False)

  def as_keyword_dict(self) -> dict[str, Any]:
    """Return the problem data as a dictionary by field keyword."""
    return self.as_dict(by_keyword=True)


class StandardProblem(Problem):
  """Standard TSPLIB95 problem with core fields."""

  allowed_problem_types: frozenset[str] = VALID_PROBLEM_TYPES

  # ``Field`` is a non-data descriptor: the populated value lives in the instance
  # ``__dict__`` and shadows the descriptor object. The declared attribute type is
  # therefore the parsed *value* type, not the ``Field`` type. ``cast`` is a runtime
  # no-op, so the class ``__dict__`` still holds the descriptor for ``FileMeta``
  # discovery, ``__set_name__`` and default handling.

  # Basic metadata fields
  name: str | None = cast("str | None", StringField("NAME"))
  comment: str | None = cast("str | None", StringField("COMMENT"))
  problem_type: str | None = cast("str | None", StringField("TYPE"))
  dimension: int = cast("int", IntegerField("DIMENSION"))
  capacity: int = cast("int", IntegerField("CAPACITY"))
  node_coord_type: str | None = cast("str | None", StringField("NODE_COORD_TYPE"))
  edge_weight_type: str | None = cast("str | None", StringField("EDGE_WEIGHT_TYPE"))
  display_data_type: str | None = cast("str | None", StringField("DISPLAY_DATA_TYPE"))
  edge_weight_format: str | None = cast("str | None", StringField("EDGE_WEIGHT_FORMAT"))
  edge_data_format: str | None = cast("str | None", StringField("EDGE_DATA_FORMAT"))

  # Section data fields
  node_coords = cast("dict[Any, Any]", IndexedCoordinatesField("NODE_COORD_SECTION", dimensions=(2, 3)))
  edge_data = cast("list[Any]", EdgeDataField("EDGE_DATA_SECTION"))
  edge_weights = cast("list[Any]", MatrixField("EDGE_WEIGHT_SECTION"))
  display_data = cast("dict[Any, Any]", IndexedCoordinatesField("DISPLAY_DATA_SECTION", dimensions=2))
  fixed_edges = cast("list[Any]", EdgeListField("FIXED_EDGES_SECTION"))
  depots = cast("list[Any]", DepotsField("DEPOT_SECTION"))
  demands = cast("dict[Any, Any]", DemandsField("DEMAND_SECTION"))
  tours = cast("list[Any]", ToursField("TOUR_SECTION"))

  @classmethod
  def parse(cls, text: str, **options: Any) -> Self:
    """Parse TSPLIB95 format text into a StandardProblem (or subclass).

    Executes in two decoupled steps:
    1. Split text into ``(raw_headers, raw_sections)`` via :func:`_split_tsplib_text`,
        ignoring blank lines and ``#`` comments everywhere.
    2. Parse all header keywords first, then parse all data sections second so
        every section has access to populated header attributes (such as
        ``EDGE_DATA_FORMAT`` and ``DIMENSION``) regardless of file ordering.

    Raises
    ------
    ParseError
        When any known keyword or section content is unparsable, or when a
        ``*_SECTION`` has no registered field on ``cls``.
    """
    problem = cls()
    errors: list[str] = []
    raw_headers, raw_sections = _split_tsplib_text(text, errors)

    for header_keyword, header_value in raw_headers:
      field: Field | None = cls.fields_by_keyword.get(header_keyword)
      if field is not None:
        try:
          parsed_value: Any = field.parse(header_value)
          if field.name:
            setattr(problem, field.name, parsed_value)
        except Exception as e:
          errors.append(f"invalid value for {header_keyword}: {e}")

    for section_keyword, section_body in raw_sections:
      sec_field: Field | None = cls.fields_by_keyword.get(section_keyword)
      if sec_field is None:
        errors.append(f"unsupported {section_keyword}: no field registered for its body")
        continue
      try:
        parsed_sec: Any = sec_field.parse_for_problem(section_body, problem)
        if sec_field.name:
          setattr(problem, sec_field.name, parsed_sec)
      except Exception as e:
        errors.append(f"invalid {section_keyword}: {e}")

    if errors:
      raise exceptions.ParseError("TSPLIB parse errors: " + "; ".join(errors))
    return problem

  def create_explicit_matrix(self) -> matrix.Matrix | None:
    """Convert edge_weights list[list] to a Matrix object for EXPLICIT problems.

    ``DIMENSION`` is authoritative (TSPLIB spec): the flattened weight list
    must match the element count implied by ``EDGE_WEIGHT_FORMAT`` and
    ``DIMENSION``. Two real-world deviations from the core format are
    accommodated, both detected by element count and validated against
    ``DIMENSION`` rather than guessed:

    1. Some SOPLIB-derived files prepend a leading integer equal to
        ``DIMENSION`` to the ``EDGE_WEIGHT_SECTION`` (a non-conforming marker
        that never appears in the spec).
    2. Some triangular-matrix files (e.g. ``eil7.vrp``, ``eil13.vrp``,
        ``eil31.vrp``) declare ``LOWER_DIAG_ROW`` (or another ``*_DIAG_*``
        format) with ``DIMENSION = n`` but omit the 0-diagonal, providing
        exactly ``n * (n - 1) // 2`` elements (the exact count for the
        corresponding no-diagonal ``n x n`` triangular format).

    Any other element count raises a ParseError instead of silently
    truncating or padding.

    Returns:
        Matrix object if edge_weight_format is set, None otherwise
    """
    fmt: str = getattr(self, "edge_weight_format", None) or ""
    weights_raw: Any = getattr(self, "edge_weights", None) or []
    if not fmt or not weights_raw:
      return None

    dimension: int = int(getattr(self, "dimension", 0) or 0)

    MatrixClass: type[matrix.Matrix] | None = matrix.TYPES.get(fmt)
    if not MatrixClass:
      return None

    weights: list[int | float] = list(itertools.chain(*weights_raw))
    expected: int = MatrixClass._calculate_expected_size(dimension)

    # Deviation 1: leading DIMENSION marker (SOPLIB-derived files). Detected
    # by count (exactly one extra element) AND value (equal to DIMENSION),
    # so a conforming matrix is never touched.
    if len(weights) == expected + 1 and weights and int(weights[0]) == dimension:
      logger.info(f"Dropping leading DIMENSION marker ({weights[0]}) from EDGE_WEIGHT_SECTION")
      weights = weights[1:]

    # Deviation 2: *_DIAG_* format declared, but the 0-diagonal was omitted
    # (exact element count for the corresponding no-diagonal n x n triangular format).
    if len(weights) != expected and fmt in NO_DIAG_FORMAT_FALLBACK:
      no_diag_fmt: str = NO_DIAG_FORMAT_FALLBACK[fmt]
      NoDiagClass: type[matrix.Matrix] = matrix.TYPES[no_diag_fmt]
      expected_no_diag: int = NoDiagClass._calculate_expected_size(dimension)
      if len(weights) == expected_no_diag:
        logger.warning(
          f"{fmt} declared with DIMENSION={dimension} (expected {expected} elements), "
          f"but EDGE_WEIGHT_SECTION has {len(weights)} elements (matching {no_diag_fmt} with omitted diagonal); "
          f"interpreting as {dimension}x{dimension} {no_diag_fmt} matrix"
        )
        MatrixClass = NoDiagClass
        expected = expected_no_diag

    if len(weights) != expected:
      raise exceptions.ParseError(
        f"{fmt} matrix with dimension {dimension} requires {expected} "
        f"elements, but EDGE_WEIGHT_SECTION contains {len(weights)}"
      )

    return MatrixClass(weights, dimension, min_index=0)


class LKHProblem(StandardProblem):
  """Extended LKH-3 routing problem model (proto implementation, P6 / R6).

  Inherits all core TSPLIB95 fields and parsing behavior from
  :class:`StandardProblem` and extends :attr:`allowed_problem_types` to the
  LKH-3 vocabulary (``CVRPTW``, ``TSPTW``, ``PDPTW``, ``MDVRP``, ``VRPB``,
  ``MTSP``, etc.) while registering LKH-3 header and section descriptors via
  :class:`FileMeta`.
  """

  allowed_problem_types: frozenset[str] = LKH_PROBLEM_TYPES

  # Extended LKH-3 header fields
  vehicles: int = cast("int", IntegerField("VEHICLES"))
  max_distance: int | float = cast("int | float", NumberField("DISTANCE"))
  service_time: int | float = cast("int | float", NumberField("SERVICE_TIME"))
  capacity_vol: int = cast("int", IntegerField("CAPACITY_VOL"))
  capacity_weight: int = cast("int", IntegerField("CAPACITY_WEIGHT"))
  num_depots: int = cast("int", IntegerField("DEPOTS"))
  periods: int = cast("int", IntegerField("PERIODS"))

  # Extended LKH-3 section fields
  time_windows = cast("dict[Any, Any]", IndexedCoordinatesField("TIME_WINDOW_SECTION", dimensions=2))
  service_times = cast("dict[Any, Any]", IndexedCoordinatesField("SERVICE_TIME_SECTION", dimensions=1))
  backhauls = cast("dict[Any, Any]", DemandsField("BACKHAUL_SECTION"))
  pickup_and_delivery = cast(
    "dict[Any, Any]", IndexedCoordinatesField("PICKUP_AND_DELIVERY_SECTION", dimensions=(3, 5, 6))
  )
  depot_capacities = cast("dict[Any, Any]", DemandsField("DEPOT_CAPACITY_SECTION"))
  depot_durations = cast("dict[Any, Any]", DurationsField("DEPOT_DURATION_SECTION"))


#: Global registry mapping problem type names to their registered problem model classes.
PROBLEM_REGISTRY: dict[str, type[StandardProblem]] = {}


def register_problem_class(
  cls: type[StandardProblem],
  types: frozenset[str] | set[str] | tuple[str, ...] | None = None,
) -> type[StandardProblem]:
  """Register a StandardProblem subclass for one or more problem types.

  Parameters
  ----------
  cls : type[StandardProblem]
      The problem model class to register.
  types : collection of str, optional
      Specific problem type strings to register for this class. If None,
      registers all types in ``cls.allowed_problem_types``.

  Returns
  -------
  type[StandardProblem]
      The registered class (enables use as a class decorator).
  """
  target_types: frozenset[str] | set[str] | tuple[str, ...] | Any | tuple[()] = (
    types if types is not None else getattr(cls, "allowed_problem_types", ())
  )
  for problem_type in target_types:
    PROBLEM_REGISTRY[problem_type] = cls
  return cls


def get_problem_class_for_type(problem_type: str | None) -> type[StandardProblem]:
  """Resolve the problem class registered for ``problem_type``.

  Defaults to :class:`StandardProblem` when ``problem_type`` is None or
  unrecognized in the registry.
  """
  if not problem_type:
    return StandardProblem
  return PROBLEM_REGISTRY.get(problem_type, StandardProblem)


# Register base TSPLIB95 core types with StandardProblem
register_problem_class(StandardProblem, VALID_PROBLEM_TYPES)

# Register extended LKH-3 types with LKHProblem
register_problem_class(LKHProblem, LKH_PROBLEM_TYPES - VALID_PROBLEM_TYPES)


__all__: list[str] = [
  "PROBLEM_REGISTRY",
  "FileMeta",
  "LKHProblem",
  "Problem",
  "StandardProblem",
  "get_problem_class_for_type",
  "register_problem_class",
]
