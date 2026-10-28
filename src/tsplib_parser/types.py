"""Core TSPLIB95 vocabularies shared across the package.

WHY
---
The problem-type vocabulary existed twice: ``validation.py`` kept its own
``known_types`` set while ``parser.py`` built labels of its own, and nothing tied
the two together, so producer and consumer could drift apart without a test
noticing (``PB4``/``PC8`` in ``TODO.md``). The same holds for the edge-weight
vocabularies and for the file-extension hints the type detection needs (``P4``).

WHAT
----
One module that answers, for the whole package:

- which problem types exist (:class:`ProblemType`);
- which spellings are accepted but normalize to a core type
  (:data:`PROBLEM_TYPE_ALIASES`);
- which ``TYPE`` values a file may declare (:data:`VALID_PROBLEM_TYPES`);
- which ``EDGE_WEIGHT_TYPE`` values exist (:data:`EDGE_WEIGHT_TYPES`, spec
  §1.1.6) — a coordinate type that is missing an implementation is a different
  failure from a value that is not TSPLIB95 at all;
- which extension hints at which type (:data:`EXTENSION_TYPE_HINTS`);
- the per-line grammar of every data section (:data:`SECTION_GRAMMARS`, spec
  §1.2): ``validation`` derives the coordinate dimensions it enforces from that
  table and the section tests check the raw file lines against it, so the spec
  fact of §1.2 is declared once and read by both (
  ``PC8``).

EXPECTED
--------
Pure data and two lookups: no parsing, no I/O, no import of the rest of the
package, so ``parser``, ``validation`` and, later, the problem-class registry can
all rely on it without introducing a cycle.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, NotRequired, TypedDict

__all__: list[str] = [
  "DISPLAY_DATA_DIMENSIONS",
  "DISPLAY_DATA_TYPES",
  "EDGE_DATA_FORMATS",
  "EDGE_WEIGHT_TYPES",
  "EXTENDED_PROBLEM_TYPES",
  "EXTENSION_TYPE_HINTS",
  "FUNCTIONAL_EDGE_WEIGHT_FORMATS",
  "MATRIX_EDGE_WEIGHT_FORMATS",
  "NODE_COORD_DIMENSIONS",
  "NODE_COORD_TYPES",
  "NO_DIAG_FORMAT_FALLBACK",
  "PROBLEM_TYPE_ALIASES",
  "SECTION_GRAMMARS",
  "STORABLE_PROBLEM_TYPES",
  "THREED_WEIGHT_TYPES",
  "TWOD_WEIGHT_TYPES",
  "VALID_PROBLEM_TYPES",
  "ColumnKind",
  "Metadata",
  "ParseResult",
  "ProblemData",
  "ProblemType",
  "SectionGrammar",
  "TourDict",
  "WeightSource",
  "normalize_problem_type",
]


class ProblemType(StrEnum):
  """Problem types of the core TSPLIB95 format.

  ``TOUR`` is not a problem statement but the recorded best route for some of
  them; it is kept in the vocabulary because the corpus ships 41 such files and
  the downstream schema needs a value for them.
  """

  TSP = "TSP"
  ATSP = "ATSP"
  SOP = "SOP"
  HCP = "HCP"
  CVRP = "CVRP"
  TOUR = "TOUR"


#: Spellings that are legal in a file header but normalize to a core type.
#: ``VRP`` is the umbrella spelling of TSPLIB95; this package models the
#: capacitated case, so a bare ``VRP`` is a ``CVRP``.
PROBLEM_TYPE_ALIASES: dict[str, ProblemType] = {
  "VRP": ProblemType.CVRP,
}

#: Every ``TYPE`` value a core TSPLIB95 file may declare, aliases included.
VALID_PROBLEM_TYPES: frozenset[str] = frozenset(
  {problem_type.value for problem_type in ProblemType} | set(PROBLEM_TYPE_ALIASES)
)

#: Extended problem ``TYPE`` vocabulary: the core TSPLIB95 types plus the problem
#: types the LKH-3 reference defines a *parseable* grammar for, normalized to
#: uppercase, plus the project-defined multi-depot family.
#:
#: Three deliberate departures from the reference's capability list:
#:
#: - the multi-depot family (``MDVRP``, ``MDVRPTW``) is ours. The reference
#:   defines ``MDMTSP`` (multiple depot, multiple travelling salesman) but no
#:   multi-depot vehicle-routing type, and the Cordeau front end can emit both
#:   spellings, so refusing them would make this parser unable to read a document
#:   it produced itself.
#: - ``TRPP`` is gone because no source defines it; the reference has ``TRP``.
#: - the coloured-TSP family (``CTSP``, ``CTSP-D``, ``GCTSP``, ``CCCTSP``,
#:   ``MSCTSP``, ``PCTSP``, ``CBTSP``, ``CBNTSP``) is not accepted, because every
#:   one of them needs ``CTSP_SET_SECTION`` and the only source we hold names that
#:   section without publishing its grammar. Accepting the ``TYPE`` would mean
#:   parsing the file and dropping the colouring, i.e. solving a different
#:   problem; validation rejects the ``TYPE`` instead.
EXTENDED_PROBLEM_TYPES: frozenset[str] = VALID_PROBLEM_TYPES | frozenset(
  {
    "1-PDTSP",
    "ACVRP",
    "ADCVRP",
    "BMTSP",
    "BWTSP",
    "CATSPP",
    "CCVRP",
    "CLUVRP",
    "CVRPTW",
    "DCVRP",
    "HPP",
    "K-TSP",
    "M-PDTSP",
    "M1-PDTSP",
    "MDMTSP",
    "MDVRP",
    "MDVRPTW",
    "MLP",
    "MTRP",
    "MTRPD",
    "MTSP",
    "O-K-TSP",
    "OP",
    "OVRP",
    "PC-TSP",
    "PDPTW",
    "PDTSP",
    "PDTSPF",
    "PDTSPL",
    "PTP",
    "PTSP",
    "RCTVRP",
    "RCTVRPTW",
    "SOFTCLUVRP",
    "STTSP",
    "TOP",
    "TRP",
    "TSPDL",
    "TSPPD",
    "TSPTW",
    "TSP_MD",
    "VRPB",
    "VRPBTW",
    "VRPMPD",
    "VRPMPDTW",
    "VRPSPD",
    "VRPSPDTW",
  }
)

#: Problem types that can be stored in the DuckDB problems hub table.
#: Excludes TOUR because solution files are not problem instances.
STORABLE_PROBLEM_TYPES: frozenset[str] = frozenset(t for t in EXTENDED_PROBLEM_TYPES if t != "TOUR")


def normalize_problem_type(raw_type: str | None) -> str | None:
  """Normalize a TSPLIB/LKH ``TYPE`` string (e.g. ``'TSP (M.~Hofmeister)'``, ``'VRP'``) to its canonical token.

  Extracts the leading token before any parenthetical comment, uppercases it,
  and maps aliases (``VRP`` -> ``CVRP``) via :data:`PROBLEM_TYPE_ALIASES`.
  If the leading token is not in :data:`EXTENDED_PROBLEM_TYPES`, returns the
  stripped raw string so validation can report the offending value verbatim.
  """
  if not raw_type or not isinstance(raw_type, str):
    return None
  stripped: str = raw_type.strip()
  if not stripped:
    return None
  base_token: str = stripped.split("(")[0].strip().split()[0].upper() if stripped.split("(")[0].strip() else ""
  if base_token in PROBLEM_TYPE_ALIASES:
    return PROBLEM_TYPE_ALIASES[base_token].value
  if base_token in EXTENDED_PROBLEM_TYPES:
    return base_token
  return stripped


#: File-extension hints used by type detection (decision ``P4``, step 1). The
#: extension never decides on its own: it is compared with the declared ``TYPE``
#: and a disagreement is logged (step 3).
EXTENSION_TYPE_HINTS: dict[str, ProblemType] = {
  ".tsp": ProblemType.TSP,
  ".atsp": ProblemType.ATSP,
  ".sop": ProblemType.SOP,
  ".hcp": ProblemType.HCP,
  ".vrp": ProblemType.CVRP,
  ".tour": ProblemType.TOUR,
}

#: Every ``EDGE_WEIGHT_TYPE`` value of TSPLIB95 §1.1.6. ``SPECIAL`` is in the
#: vocabulary even though no formula exists for it: a file may declare it, and
#: that is a supported-feature gap, not an unknown keyword.
EDGE_WEIGHT_TYPES: frozenset[str] = frozenset(
  {
    "EXPLICIT",
    "EUC_2D",
    "EUC_3D",
    "MAX_2D",
    "MAX_3D",
    "MAN_2D",
    "MAN_3D",
    "CEIL_2D",
    "GEO",
    "ATT",
    "XRAY1",
    "XRAY2",
    "SPECIAL",
  }
)

#: 2-D coordinate-based ``EDGE_WEIGHT_TYPE`` values (require 2-D coordinates).
TWOD_WEIGHT_TYPES: frozenset[str] = frozenset({"EUC_2D", "MAX_2D", "MAN_2D", "CEIL_2D", "GEO", "ATT"})

#: 3-D coordinate-based ``EDGE_WEIGHT_TYPE`` values (require 3-D coordinates).
THREED_WEIGHT_TYPES: frozenset[str] = frozenset({"EUC_3D", "MAX_3D", "MAN_3D", "XRAY1", "XRAY2"})

#: Legal ``NODE_COORD_TYPE`` values (§1.1.8) mapped to their required coordinate dimension.
NODE_COORD_TYPES: dict[str, int | None] = {
  "TWOD_COORDS": 2,
  "THREED_COORDS": 3,
  "NO_COORDS": None,
}

#: Legal ``DISPLAY_DATA_TYPE`` values (§1.1.10).
DISPLAY_DATA_TYPES: frozenset[str] = frozenset({"COORD_DISPLAY", "TWOD_DISPLAY", "NO_DISPLAY"})

#: Legal ``EDGE_DATA_FORMAT`` values (§1.1.9).
EDGE_DATA_FORMATS: frozenset[str] = frozenset({"EDGE_LIST", "ADJ_LIST"})

#: Matrix-backed ``EDGE_WEIGHT_FORMAT`` values (§1.1.7).
MATRIX_EDGE_WEIGHT_FORMATS: frozenset[str] = frozenset(
  {
    "FULL_MATRIX",
    "UPPER_ROW",
    "LOWER_ROW",
    "UPPER_DIAG_ROW",
    "LOWER_DIAG_ROW",
    "UPPER_COL",
    "LOWER_COL",
    "UPPER_DIAG_COL",
    "LOWER_DIAG_COL",
  }
)

#: Function-backed ``EDGE_WEIGHT_FORMAT`` values (§1.1.7).
FUNCTIONAL_EDGE_WEIGHT_FORMATS: frozenset[str] = frozenset({"FUNCTION"})

#: Mapping from diagonal-inclusive triangular formats to their no-diagonal
#: counterparts (used when a ``*_DIAG_*`` problem omits the 0-diagonal, e.g. ``M8``).
NO_DIAG_FORMAT_FALLBACK: dict[str, str] = {
  "LOWER_DIAG_ROW": "LOWER_ROW",
  "UPPER_DIAG_ROW": "UPPER_ROW",
  "LOWER_DIAG_COL": "LOWER_COL",
  "UPPER_DIAG_COL": "UPPER_COL",
}

#: Weight source classification emitted in ``metadata["weight_source"]``.
type WeightSource = Literal[
  "explicit_matrix",
  "explicit_function",
  "coordinate_based",
  "special_function",
  "edge_data",
  "unweighted",
  "unknown",
]


class TourDict(TypedDict):
  """One extracted 0-based tour route in ``ParseResult["tours"]``."""

  tour_id: int
  nodes: list[int]


class ProblemData(TypedDict):
  """Problem header and extended-section data in ``ParseResult["problem_data"]``.

  The ten core keys are emitted unconditionally by
  ``FormatParser._extract_problem_data`` (their values are ``None`` when the
  source file omits the keyword), so they are required and nullable.

  Everything else depends on the dispatched problem class (LKH-3 headers and
  sections) or on VRP preprocessing, and is therefore ``NotRequired``. Keys not
  declared here can still appear at runtime; the producer documents that gap.
  """

  # Core keys: always present, nullable values
  name: str | None
  type: str
  comment: str | None
  dimension: int | None
  capacity: int | None
  node_coord_type: str | None
  edge_weight_type: str | None
  display_data_type: str | None
  edge_weight_format: str | None
  edge_data_format: str | None

  # Explicit weight matrix (``Matrix``) or raw nested list when it cannot be built
  edge_weights: NotRequired[Any]

  # Extended (TSPLIB-extended, PB18) header fields. There is no depot count here:
  #: it is ``len(depots)`` of the payload, never a ``DEPOTS`` header.
  vehicles: NotRequired[int]
  periods: NotRequired[int]
  max_distance: NotRequired[float]
  service_time: NotRequired[float]
  capacity_vol: NotRequired[int]
  capacity_weight: NotRequired[int]
  salesmen: NotRequired[int]
  external_salesmen: NotRequired[int]
  scale: NotRequired[int]
  risk_threshold: NotRequired[int]
  grid_size: NotRequired[float]
  k: NotRequired[int]
  probability: NotRequired[float]

  # Extended LKH-3 sections: 0-based arrays (coordinate rows are lists of floats)
  time_windows: NotRequired[list[list[float]]]
  service_times: NotRequired[list[list[float]]]
  pickup_and_delivery: NotRequired[list[list[float]]]
  backhauls: NotRequired[list[int]]
  depot_capacities: NotRequired[list[int]]
  depot_durations: NotRequired[dict[int, float]]
  required_nodes: NotRequired[list[int]]

  # Preprocessed VRP metadata flags
  has_time_windows: NotRequired[bool]
  has_service_times: NotRequired[bool]
  has_pickup_delivery: NotRequired[bool]
  has_backhauls: NotRequired[bool]
  stripped_sections: NotRequired[list[str]]


class Metadata(TypedDict):
  """File and problem characteristic metadata in ``ParseResult["metadata"]``."""

  file_path: str
  file_name: str
  file_size: int
  has_coordinates: bool
  has_display_coords: NotRequired[bool]
  has_demands: bool
  has_depots: bool
  has_tours: bool
  has_edges: bool
  has_fixed_edges: bool
  is_symmetric: bool | None
  weight_source: str
  problem_source: str | None
  vrp_constraints: NotRequired[list[str]]
  num_vehicles: NotRequired[int]
  max_route_distance: NotRequired[float]
  service_time: NotRequired[float]


class ParseResult(TypedDict):
  """Typed contract for the dictionary returned by ``FormatParser.parse_file`` (P10 / PC1)."""

  problem_data: ProblemData
  coords: list[list[float]]
  display_coords: list[list[float]]
  demands: list[int]
  depots: list[int]
  edges: list[list[int]]
  fixed_edges: list[list[int]]
  tours: list[TourDict]
  metadata: Metadata


class ColumnKind(StrEnum):
  """Kind of one column inside a data-section line (spec §1.2)."""

  INTEGER = "integer"
  REAL = "real"
  #: One or more integers, the line length being open (``ADJ_LIST`` rows, a
  #: matrix row).
  INTEGERS = "integers"


@dataclass(frozen=True, slots=True)
class SectionGrammar:
  """Per-line grammar of one data section body, straight from spec §1.2.

  One entry per *variant*: a section whose shape depends on a companion keyword
  (``NODE_COORD_TYPE``, ``EDGE_DATA_FORMAT``, ``DISPLAY_DATA_TYPE``) has one
  entry per legal value of that keyword, with :attr:`selector` naming the keyword
  and :attr:`selector_value` the value it selects.
  """

  #: Section header line, e.g. ``NODE_COORD_SECTION``.
  keyword: str
  #: Column kinds of one body line, in order, node id first.
  columns: tuple[ColumnKind, ...]
  #: Companion keyword that selects this variant, if the section has variants.
  selector: str | None = None
  #: Value of :attr:`selector` that selects this variant.
  selector_value: str | None = None
  #: Number of ``-1`` terminator lines the spec prescribes for the section.
  terminator_lines: int = 0
  #: Key of the parse result this section feeds, when it maps onto one.
  result_key: str | None = None
  #: Anything a reader (or a test) must know that the columns do not say.
  note: str = ""


_INT = ColumnKind.INTEGER
_REAL = ColumnKind.REAL
_INTS = ColumnKind.INTEGERS

#: Every data section of TSPLIB95 §1.2, per variant. The declared columns are the
#: spec's, not the parser's: the parser re-bases node ids to 0-based and exposes
#: sections as lists, which is why the result contract is a separate artifact
#: (the ``ParseResult`` typed dict).
SECTION_GRAMMARS: tuple[SectionGrammar, ...] = (
  SectionGrammar(
    keyword="NODE_COORD_SECTION",
    columns=(_INT, _REAL, _REAL),
    selector="NODE_COORD_TYPE",
    selector_value="TWOD_COORDS",
    result_key="coords",
  ),
  SectionGrammar(
    keyword="NODE_COORD_SECTION",
    columns=(_INT, _REAL, _REAL, _REAL),
    selector="NODE_COORD_TYPE",
    selector_value="THREED_COORDS",
    result_key="coords",
    note="No corpus file declares THREED_COORDS; the XRAY instances carry three columns without it.",
  ),
  SectionGrammar(keyword="DEPOT_SECTION", columns=(_INT,), terminator_lines=1, result_key="depots"),
  SectionGrammar(
    keyword="DEMAND_SECTION",
    columns=(_INT, _INT),
    result_key="demands",
    note="Depot nodes occur here too, with demand 0 (spec §1.2.3).",
  ),
  SectionGrammar(
    keyword="EDGE_DATA_SECTION",
    columns=(_INT, _INT),
    selector="EDGE_DATA_FORMAT",
    selector_value="EDGE_LIST",
    terminator_lines=1,
    result_key="edges",
  ),
  SectionGrammar(
    keyword="EDGE_DATA_SECTION",
    columns=(_INT, _INTS),
    selector="EDGE_DATA_FORMAT",
    selector_value="ADJ_LIST",
    terminator_lines=2,
    result_key="edges",
    note="Only synthetic fixtures exercise this variant; all nine HCP corpus files are EDGE_LIST.",
  ),
  SectionGrammar(keyword="FIXED_EDGES_SECTION", columns=(_INT, _INT), terminator_lines=1, result_key="fixed_edges"),
  SectionGrammar(
    keyword="DISPLAY_DATA_SECTION",
    columns=(_INT, _REAL, _REAL),
    selector="DISPLAY_DATA_TYPE",
    selector_value="TWOD_DISPLAY",
    result_key="display_coords",
    note="Feeds the top-level display_coords key; the 2-D rule is enforced from this table (R2).",
  ),
  SectionGrammar(
    keyword="TOUR_SECTION",
    columns=(_INT,),
    terminator_lines=2,
    result_key="tours",
    note="One -1 per tour, an extra -1 for the section; real files end the last tour with -1 and then EOF.",
  ),
  SectionGrammar(
    keyword="EDGE_WEIGHT_SECTION",
    columns=(_INTS,),
    result_key="problem_data.edge_weights",
    note="Integers in the layout named by EDGE_WEIGHT_FORMAT; the length is implicit.",
  ),
)


def _coordinate_dimensions(keyword: str) -> frozenset[int]:
  """Coordinate dimensions the spec allows for ``keyword``, per :data:`SECTION_GRAMMARS`.

  One column of a coordinate row is the node id and the rest are the coordinates,
  so the rule follows from the declared columns. Deriving it keeps the spec fact
  in one place: adding a variant changes what ``validation`` accepts with no
  second edit (``PC8``).
  """
  return frozenset(len(grammar.columns) - 1 for grammar in SECTION_GRAMMARS if grammar.keyword == keyword)


#: Coordinate dimensions TSPLIB95 allows for ``NODE_COORD_SECTION`` — the two
#: ``NODE_COORD_TYPE`` variants of §1.2.1, i.e. ``{2, 3}``.
NODE_COORD_DIMENSIONS: frozenset[int] = _coordinate_dimensions("NODE_COORD_SECTION")

#: Display coordinates are 2-D only: ``TWOD_DISPLAY`` is the sole
#: ``DISPLAY_DATA_TYPE`` value that carries a section (§1.2.8).
DISPLAY_DATA_DIMENSIONS: frozenset[int] = _coordinate_dimensions("DISPLAY_DATA_SECTION")
