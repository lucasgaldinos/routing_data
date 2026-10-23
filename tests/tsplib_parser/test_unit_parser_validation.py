"""Comprehensive problem validation and declared-vs-extracted consistency tests.

WHAT
----
Tests two-stage validation (`validate_problem_data` and `validate_parse_result`),
all newly hardened parser invariants (`PB2`, `PB4`, `PB12`, `PB13`, `M8`, `R6`),
and a corpus-wide declared-vs-extracted consistency check across all 239 files
in `datasets_raw/problems/**`.

WHY
---
Previously, tests checked individual functions or small fixtures, without
verifying across the entire problem corpus that every problem's declared headers
(`DIMENSION`, `TYPE`, `EDGE_WEIGHT_TYPE`, `EDGE_WEIGHT_FORMAT`, `CAPACITY`, etc.)
and raw sections match the runtime types, dimensions, and 0-based arrays
extracted by `FormatParser.parse_file()`.

EXPECTED
--------
- Every one of the 239 corpus files parses with zero pre- or post-extraction
  validation errors, and every extracted field, type, dimension, coordinate,
  demand, depot, edge, tour, and matrix matches what the raw file declares.
- Malformed or inconsistent problems fail loudly with `ValidationError` or
  `ParseError` naming the exact violation.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tsplib_parser.exceptions import ParseError, ValidationError
from tsplib_parser.fields import IntegerField, StringField
from tsplib_parser.matrix import Matrix
from tsplib_parser.models import (
  LKHProblem,
  StandardProblem,
  get_problem_class_for_type,
  register_problem_class,
)
from tsplib_parser.parser import FormatParser
from tsplib_parser.types import (
  THREED_WEIGHT_TYPES,
  TWOD_WEIGHT_TYPES,
  normalize_problem_type,
)
from tsplib_parser.validation import (
  validate_coordinates,
  validate_parse_result,
)

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult


def _write(tmp_path: Path, name: str, content: str) -> str:
  """Write ``content`` to ``tmp_path/name`` and return its path string."""
  target: Path = tmp_path / name
  target.write_text(content, encoding="utf-8")
  return str(target)


def _extract_raw_declarations(file_path: Path) -> dict[str, Any]:
  """Read raw headers and section presence directly from a TSPLIB file for oracle comparison."""
  try:
    text: str = file_path.read_text(encoding="utf-8")
  except UnicodeDecodeError:
    text = file_path.read_text(encoding="latin-1")

  headers: dict[str, str] = {}
  sections_present: set[str] = set()
  in_section: str | None = None

  for raw_line in text.splitlines():
    line: str = raw_line.strip()
    if not line or line.startswith("#"):
      continue
    if line == "EOF":
      in_section = None
      break
    if line.endswith("_SECTION"):
      in_section = line
      sections_present.add(line)
      continue
    if ":" in line:
      prefix: str = line.split(":", 1)[0].strip()
      is_kw: bool = (
        bool(prefix)
        and any(c.isalpha() for c in prefix)
        and all(c.isupper() or c.isdigit() or c == "_" for c in prefix)
      )
      if in_section is None or is_kw:
        in_section = None
        key, val = (p.strip() for p in line.split(":", 1))
        if key == "FIXED_EDGES":
          sections_present.add("FIXED_EDGES_SECTION")
        else:
          headers[key] = val

  return {
    "headers": headers,
    "sections": sections_present,
  }


class TestCorpusDeclaredVsExtractedConsistency:
  """Verify declared headers and sections vs extracted ParseResult across all 239 corpus files."""

  @pytest.mark.requires_dataset
  @pytest.mark.slow
  def test_all_corpus_files_match_declared_types_and_dimensions(self, test_data_dir: Path) -> None:
    """WHAT: Parse all 239 files in `datasets_raw/problems/**` and compare against raw declarations.

    WHY: Guarantees that for every problem in the benchmark corpus, what the file
    declares in its headers and sections matches the types, dimensions, and 0-based
    arrays extracted by `FormatParser.parse_file()`.

    EXPECTED: All 239 files parse with 0 failures and pass every declared-vs-extracted check.
    """
    corpus_files: list[Path] = sorted(
      p for p in test_data_dir.rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    assert len(corpus_files) == 239, f"Expected 239 corpus files, found {len(corpus_files)}"

    parser = FormatParser()

    for file_path in corpus_files:
      raw_info: dict[str, Any] = _extract_raw_declarations(file_path)
      raw_headers: dict[str, str] = raw_info["headers"]
      raw_sections: set[str] = raw_info["sections"]

      result: ParseResult = parser.parse_file(file_path)

      # 1. Post-extraction validator must pass with 0 errors
      assert validate_parse_result(result) == [], f"{file_path.name} failed post-extraction validation"
      assert "nodes" not in result, f"{file_path.name}: retired v1 'nodes' key must not be present"

      pdata: dict[str, Any] = result["problem_data"]
      meta: dict[str, Any] = result["metadata"]

      # 2. Declared header fields vs extracted problem_data
      assert pdata["name"] == raw_headers["NAME"], f"{file_path.name}: NAME mismatch"
      assert pdata["type"] == normalize_problem_type(raw_headers["TYPE"]), f"{file_path.name}: TYPE mismatch"

      declared_dim: int = int(raw_headers["DIMENSION"])
      assert pdata["dimension"] == declared_dim, f"{file_path.name}: DIMENSION mismatch"
      assert isinstance(pdata["dimension"], int), f"{file_path.name}: dimension must be int"

      if "CAPACITY" in raw_headers:
        assert pdata["capacity"] == int(raw_headers["CAPACITY"]), f"{file_path.name}: CAPACITY mismatch"
      else:
        assert pdata["capacity"] is None

      if "EDGE_WEIGHT_TYPE" in raw_headers:
        assert pdata["edge_weight_type"] == raw_headers["EDGE_WEIGHT_TYPE"]

      if "EDGE_WEIGHT_FORMAT" in raw_headers:
        assert pdata["edge_weight_format"] == raw_headers["EDGE_WEIGHT_FORMAT"]

      # 3. NODE_COORD_SECTION vs extracted coords
      coords: list[list[float]] = result["coords"]
      if "NODE_COORD_SECTION" in raw_sections:
        assert len(coords) == declared_dim, f"{file_path.name}: coords length != DIMENSION"
        assert meta["has_coordinates"] is True
        ew_type: str | None = pdata.get("edge_weight_type")
        if ew_type in TWOD_WEIGHT_TYPES:
          assert all(len(row) == 2 for row in coords), f"{file_path.name}: 2D weight type must have 2D coords"
        elif ew_type in THREED_WEIGHT_TYPES:
          assert all(len(row) == 3 for row in coords), f"{file_path.name}: 3D weight type must have 3D coords"
      else:
        assert coords == [], f"{file_path.name}: unexpected coords when NODE_COORD_SECTION absent"
        assert meta["has_coordinates"] is False

      # 4. DISPLAY_DATA_SECTION vs extracted display_coords (PB13)
      display_coords: list[list[float]] = result["display_coords"]
      if "DISPLAY_DATA_SECTION" in raw_sections:
        assert len(display_coords) == declared_dim, f"{file_path.name}: display_coords length != DIMENSION"
        assert meta["has_display_coords"] is True
        assert all(len(row) == 2 and all(isinstance(v, float) for v in row) for row in display_coords)
      else:
        assert display_coords == []
        assert meta["has_display_coords"] is False

      # 5. DEMAND_SECTION & DEPOT_SECTION vs extracted demands & depots
      demands: list[int] = result["demands"]
      depots: list[int] = result["depots"]
      if "DEMAND_SECTION" in raw_sections:
        assert len(demands) == declared_dim, f"{file_path.name}: demands length != DIMENSION"
        assert meta["has_demands"] is True
        assert all(isinstance(d, int) and d >= 0 for d in demands)
      else:
        assert demands == []
        assert meta["has_demands"] is False

      if "DEPOT_SECTION" in raw_sections:
        assert len(depots) >= 1
        assert meta["has_depots"] is True
        assert all(0 <= d < declared_dim for d in depots)
        assert all(demands[d] == 0 for d in depots), f"{file_path.name}: depot demand must be 0"
      else:
        assert depots == []
        assert meta["has_depots"] is False

      # 6. EDGE_DATA_SECTION & FIXED_EDGES_SECTION vs extracted edges & fixed_edges
      if "EDGE_DATA_SECTION" in raw_sections:
        assert len(result["edges"]) > 0
        assert meta["has_edges"] is True
      else:
        assert result["edges"] == []
        assert meta["has_edges"] is False

      if "FIXED_EDGES_SECTION" in raw_sections:
        assert len(result["fixed_edges"]) > 0
        assert meta["has_fixed_edges"] is True
      else:
        assert result["fixed_edges"] == []
        assert meta["has_fixed_edges"] is False

      # 7. TOUR_SECTION vs extracted tours
      if "TOUR_SECTION" in raw_sections:
        assert len(result["tours"]) >= 1
        assert meta["has_tours"] is True
        for tour in result["tours"]:
          assert len(tour["nodes"]) == declared_dim
          assert set(tour["nodes"]) == set(range(declared_dim))
      else:
        assert result["tours"] == []
        assert meta["has_tours"] is False

      # 8. EDGE_WEIGHT_SECTION vs extracted Matrix (including M8 eil7/eil13/eil31)
      if "EDGE_WEIGHT_SECTION" in raw_sections:
        mat: Any = pdata.get("edge_weights")
        assert isinstance(mat, Matrix), f"{file_path.name}: EDGE_WEIGHT_SECTION must yield Matrix"
        assert mat.size == declared_dim, f"{file_path.name}: Matrix.size ({mat.size}) != DIMENSION ({declared_dim})"


class TestPreAndPostExtractionValidationRules:
  """Unit tests for pre-extraction (`validate_problem_data`) and post-extraction (`validate_parse_result`)."""

  def test_out_of_order_node_coords_are_normalized_by_node_id(self, tmp_path: Path) -> None:
    """WHAT: `NODE_COORD_SECTION` listing nodes in order 3, 1, 2 instead of 1, 2, 3.

    WHY: `coords[i]` must always represent TSPLIB node `i + 1`, never the i-th line
    in file order.

    EXPECTED: `coords[0]` is node 1, `coords[1]` is node 2, `coords[2]` is node 3.
    """
    content = (
      "NAME: out_of_order\n"
      "TYPE: TSP\n"
      "DIMENSION: 3\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "NODE_COORD_SECTION\n"
      "3 30.0 300.0\n"
      "1 10.0 100.0\n"
      "2 20.0 200.0\n"
      "EOF\n"
    )
    path = _write(tmp_path, "out_of_order.tsp", content)
    result = FormatParser().parse_file(path)

    assert result["coords"] == [
      [10.0, 100.0],
      [20.0, 200.0],
      [30.0, 300.0],
    ]

  def test_out_of_range_node_coord_key_rejected(self, tmp_path: Path) -> None:
    """WHAT: `NODE_COORD_SECTION` with node IDs {1, 2, 4} for `DIMENSION: 3`.

    WHY: Even when `len(node_coords) == dimension`, keys outside `1..dimension`
    violate the 1-based node bijection.

    EXPECTED: `ValidationError` naming both the missing node `[3]` and out-of-range key `[4]`.
    """
    content = (
      "NAME: bad_keys\n"
      "TYPE: TSP\n"
      "DIMENSION: 3\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "NODE_COORD_SECTION\n"
      "1 0.0 0.0\n"
      "2 1.0 0.0\n"
      "4 0.0 1.0\n"
      "EOF\n"
    )
    path = _write(tmp_path, "bad_keys.tsp", content)
    with pytest.raises(ValidationError, match=r"NODE_COORD_SECTION is missing entries.*out-of-range"):
      FormatParser().parse_file(path)

  def test_coordinate_dimension_mismatch_with_weight_type_rejected(self, tmp_path: Path) -> None:
    """WHAT: `EDGE_WEIGHT_TYPE: EUC_2D` paired with 3-D coordinates in `NODE_COORD_SECTION`.

    WHY: 2-D distance metrics are only defined for 2-D coordinates (and 3-D metrics for 3-D).

    EXPECTED: `ValidationError` reporting that `EUC_2D` requires 2-D coordinates.
    """
    content = (
      "NAME: dim_mismatch\n"
      "TYPE: TSP\n"
      "DIMENSION: 2\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "NODE_COORD_SECTION\n"
      "1 0.0 0.0 0.0\n"
      "2 1.0 1.0 1.0\n"
      "EOF\n"
    )
    path = _write(tmp_path, "dim_mismatch.tsp", content)
    with pytest.raises(ValidationError, match="EDGE_WEIGHT_TYPE EUC_2D requires 2-D coordinates, got 3-D"):
      FormatParser().parse_file(path)

  def test_validate_coordinates_checks_third_dimension(self) -> None:
    """WHAT: 3-D coordinate tuple with a non-numeric `z` component.

    WHY: `validate_coordinates` previously checked only `coord[:2]`, letting a
    corrupted 3rd coordinate pass.

    EXPECTED: `validate_coordinates` returns `False`.
    """
    assert validate_coordinates([(0.0, 1.0, "bad_z")]) is False  # type: ignore[list-item]
    assert validate_coordinates([(0.0, 1.0, True)]) is False
    assert validate_coordinates([(0.0, 1.0, 2.5)]) is True

  def test_depot_with_nonzero_demand_rejected(self, tmp_path: Path) -> None:
    """WHAT: CVRP where the depot node carries non-zero demand.

    WHY: TSPLIB95 requires depot nodes to have demand 0.

    EXPECTED: `ValidationError` naming the depot node with non-zero demand.
    """
    content = (
      "NAME: bad_depot_demand\n"
      "TYPE: CVRP\n"
      "DIMENSION: 2\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "CAPACITY: 10\n"
      "NODE_COORD_SECTION\n"
      "1 0.0 0.0\n"
      "2 1.0 1.0\n"
      "DEMAND_SECTION\n"
      "1 5\n"
      "2 3\n"
      "DEPOT_SECTION\n"
      "1\n"
      "-1\n"
      "EOF\n"
    )
    path = _write(tmp_path, "bad_depot_demand.vrp", content)
    with pytest.raises(ValidationError, match=r"DEPOT_SECTION node\(s\) \[1\] must have demand 0"):
      FormatParser().parse_file(path)

  def test_tour_not_permutation_of_dimension_rejected(self, tmp_path: Path) -> None:
    """WHAT: `TOUR_SECTION` whose tour repeats node 1 instead of visiting node 3.

    WHY: A valid TSPLIB tour of dimension `n` must be a permutation of `1..n`.

    EXPECTED: `ValidationError` reporting that the tour is not a valid permutation.
    """
    content = (
      "NAME: bad_tour\n"
      "TYPE: TOUR\n"
      "DIMENSION: 3\n"
      "TOUR_SECTION\n"
      "1 2 1\n"
      "-1\n"
      "EOF\n"
    )
    path = _write(tmp_path, "bad_tour.tour", content)
    with pytest.raises(ValidationError, match=r"not a valid permutation of 1\.\.3"):
      FormatParser().parse_file(path)

  def test_edge_list_rejects_extra_tokens_and_honors_trailing_format(self, tmp_path: Path) -> None:
    """WHAT: `EDGE_LIST` line with 3 tokens (`1 2 3`), and `EDGE_DATA_FORMAT` after `EDGE_DATA_SECTION`.

    WHY: Fixes PB12 — `EDGE_LIST` must not silently ignore extra tokens on a line,
    and `EDGE_DATA_FORMAT` must be honored even when declared after `EDGE_DATA_SECTION`.

    EXPECTED: `ParseError` raised in both cases when the section violates the format.
    """
    extra_tokens_content = (
      "NAME: extra_edge_tokens\n"
      "TYPE: HCP\n"
      "DIMENSION: 3\n"
      "EDGE_DATA_FORMAT: EDGE_LIST\n"
      "EDGE_DATA_SECTION\n"
      "1 2 3\n"
      "-1\n"
      "EOF\n"
    )
    path1 = _write(tmp_path, "extra_tokens.hcp", extra_tokens_content)
    with pytest.raises(ParseError, match='EDGE_LIST: expected "<from> <to>"'):
      FormatParser().parse_file(path1)

    trailing_format_mismatch = (
      "NAME: trailing_fmt\n"
      "TYPE: HCP\n"
      "DIMENSION: 3\n"
      "EDGE_DATA_SECTION\n"
      "1: 2 3 -1\n"
      "-1\n"
      "EDGE_DATA_FORMAT: EDGE_LIST\n"
      "EOF\n"
    )
    path2 = _write(tmp_path, "trailing_fmt.hcp", trailing_format_mismatch)
    with pytest.raises(ParseError, match="EDGE_LIST"):
      FormatParser().parse_file(path2)

  def test_symmetry_check_inspects_explicit_matrix_values(self, tmp_path: Path) -> None:
    """WHAT: A `TYPE: TSP` problem with an asymmetric `FULL_MATRIX`, plus unweighted `HCP`/`TOUR`.

    WHY: Fixes PB2 and P5 — `_check_symmetry` previously returned `True` for every
    non-ATSP problem without checking matrix entries, and returned `True` for unweighted
    `HCP`/`TOUR` files.

    EXPECTED: `is_symmetric` is `False` for asymmetric `FULL_MATRIX` TSP, `True` for
    symmetric `FULL_MATRIX` TSP, and `None` for unweighted `HCP`/`TOUR`.
    """
    asym_tsp = (
      "NAME: asym_tsp\n"
      "TYPE: TSP\n"
      "DIMENSION: 3\n"
      "EDGE_WEIGHT_TYPE: EXPLICIT\n"
      "EDGE_WEIGHT_FORMAT: FULL_MATRIX\n"
      "EDGE_WEIGHT_SECTION\n"
      "0 10 20\n"
      "99 0 30\n"
      "20 30 0\n"
      "EOF\n"
    )
    path = _write(tmp_path, "asym.tsp", asym_tsp)
    result = FormatParser().parse_file(path)
    assert result["metadata"]["is_symmetric"] is False

    hcp_content = (
      "NAME: sym_hcp\n"
      "TYPE: HCP\n"
      "DIMENSION: 3\n"
      "EDGE_DATA_FORMAT: EDGE_LIST\n"
      "EDGE_DATA_SECTION\n"
      "1 2\n"
      "2 3\n"
      "3 1\n"
      "-1\n"
      "EOF\n"
    )
    hcp_path = _write(tmp_path, "sym.hcp", hcp_content)
    hcp_result = FormatParser().parse_file(hcp_path)
    assert hcp_result["metadata"]["is_symmetric"] is None
    assert hcp_result["metadata"]["weight_source"] == "unweighted"

  def test_problem_class_subclass_dispatch_extracts_extended_fields(self, tmp_path: Path) -> None:
    """WHAT: Subclass `StandardProblem` with LKH-style keywords (`VEHICLES`, `MTSP_OBJECTIVE`).

    WHY: Verifies R6 (`pylkh` pattern) — `FormatParser` accepts `problem_class` and
    `_extract_problem_data` dynamically extracts non-section fields from `fields_by_name`
    without modifying `FormatParser`.

    EXPECTED: Extended fields are parsed and surfaced in `result["problem_data"]`.
    """

    class CustomLKHProblem(StandardProblem):
      vehicles = IntegerField("VEHICLES")
      mtsp_objective = StringField("MTSP_OBJECTIVE")

    content = (
      "NAME: custom_lkh\n"
      "TYPE: TSP\n"
      "DIMENSION: 3\n"
      "VEHICLES: 2\n"
      "MTSP_OBJECTIVE: MINMAX\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "NODE_COORD_SECTION\n"
      "1 0.0 0.0\n"
      "2 1.0 0.0\n"
      "3 0.0 1.0\n"
      "EOF\n"
    )
    path = _write(tmp_path, "custom_lkh.tsp", content)
    result = FormatParser(problem_class=CustomLKHProblem).parse_file(path)

    assert result["problem_data"]["vehicles"] == 2
    assert result["problem_data"]["mtsp_objective"] == "MINMAX"
    assert result["coords"] == [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]

  def test_lkh_problem_parses_and_validates_extended_type_and_sections(self, tmp_path: Path) -> None:
    """WHAT: Parse a `TYPE: CVRPTW` problem with `TIME_WINDOW_SECTION` using `LKHProblem`.

    WHY: Verifies P6, R1, R2, and R6 — `StandardProblem` rejects `CVRPTW`, whereas
    `LKHProblem` accepts LKH-3 types, parses `TIME_WINDOW_SECTION` natively (without
    stripping it), and validates `TIME_WINDOW_SECTION` against `field.dimensions == 2`.

    EXPECTED: `StandardProblem` raises `ValidationError` on `TYPE: CVRPTW`;
    `LKHProblem` succeeds and extracts 0-based `time_windows`; a 3-column row in
    `TIME_WINDOW_SECTION` fails `R1`/`R2` field-dimension validation.
    """
    cvrptw_content = (
      "NAME: mini_cvrptw\n"
      "TYPE: CVRPTW\n"
      "DIMENSION: 3\n"
      "VEHICLES: 2\n"
      "CAPACITY: 100\n"
      "SERVICE_TIME: 5.5\n"
      "EDGE_WEIGHT_TYPE: EUC_2D\n"
      "NODE_COORD_SECTION\n"
      "1 0.0 0.0\n"
      "2 1.0 0.0\n"
      "3 0.0 1.0\n"
      "DEMAND_SECTION\n"
      "1 0\n"
      "2 10\n"
      "3 20\n"
      "TIME_WINDOW_SECTION\n"
      "1 0 100\n"
      "2 10 50\n"
      "3 20 80\n"
      "DEPOT_SECTION\n"
      "1\n"
      "-1\n"
      "EOF\n"
    )
    path = _write(tmp_path, "mini_cvrptw.vrp", cvrptw_content)

    # StandardProblem rejects CVRPTW as outside core TSPLIB95
    with pytest.raises(ValidationError, match="Unknown problem type: CVRPTW"):
      FormatParser(problem_class=StandardProblem).parse_file(path)

    # LKHProblem accepts CVRPTW and natively parses TIME_WINDOW_SECTION
    result = FormatParser(problem_class=LKHProblem).parse_file(path)
    assert result["problem_data"]["type"] == "CVRPTW"
    assert result["problem_data"]["vehicles"] == 2
    assert result["problem_data"]["service_time"] == 5.5
    assert "stripped_sections" not in result["problem_data"]
    assert result["problem_data"]["time_windows"] == [[0.0, 100.0], [10.0, 50.0], [20.0, 80.0]]

    # FormatParser() auto-dispatches to LKHProblem when problem_class is omitted
    auto_result = FormatParser().parse_file(path)
    assert auto_result["problem_data"]["type"] == "CVRPTW"
    assert auto_result["problem_data"]["time_windows"] == [[0.0, 100.0], [10.0, 50.0], [20.0, 80.0]]

    # R1/R2: 3-column TIME_WINDOW_SECTION row is rejected by field.dimensions=2
    bad_tw_content = cvrptw_content.replace("2 10 50\n", "2 10 50 99\n")
    bad_path = _write(tmp_path, "bad_cvrptw.vrp", bad_tw_content)
    with pytest.raises(ValidationError, match=r"TIME_WINDOW_SECTION must have dimensions \[2\]"):
      FormatParser(problem_class=LKHProblem).parse_file(bad_path)

  def test_problem_class_registry_auto_dispatch(self) -> None:
    """WHAT: Test get_problem_class_for_type and register_problem_class.

    WHY: Verifies declarative auto-dispatch for core, extended, and custom problem types.
    """
    assert get_problem_class_for_type("TSP") is StandardProblem
    assert get_problem_class_for_type("CVRP") is StandardProblem
    assert get_problem_class_for_type("CVRPTW") is LKHProblem
    assert get_problem_class_for_type("TSPTW") is LKHProblem
    assert get_problem_class_for_type(None) is StandardProblem
    assert get_problem_class_for_type("UNKNOWN_TYPE") is StandardProblem

    # Dynamic registration of a custom problem class
    class CustomProblem(StandardProblem):
      allowed_problem_types = frozenset({"CUSTOM_VRP"})

    register_problem_class(CustomProblem)
    assert get_problem_class_for_type("CUSTOM_VRP") is CustomProblem


