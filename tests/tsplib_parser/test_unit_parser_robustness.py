"""Robustness tests: malformed input must fail loudly, never silently drop data.

WHAT
----
Feeds section-level corruptions (a poisoned line inside DEMAND_SECTION,
NODE_COORD_SECTION, EDGE_WEIGHT_SECTION, EDGE_DATA_SECTION) and structural
violations (missing DIMENSION, CVRP without full demand coverage, EXPLICIT
without weights) through FormatParser.parse_file, plus regressions for two
real-world format variants (tab-separated coordinates and the ``FIXED_EDGES :``
keyword form).

WHY
---
The parser previously logged such failures at debug level and returned a
"successful" result with the affected data silently missing — a single bad
cell erased an entire 17x17 ATSP matrix, one garbage line emptied all 21
demands. Silent data loss is the worst failure mode for an ETL.

EXPECTED
--------
- ParseError for unparsable known-section content (whole file rejected).
- ValidationError for cross-field structural violations.
- The documented exception contract holds: ValidationError surfaces as
  ValidationError, never laundered into ParseError.
- Valid files and the real-world format variants still parse correctly.
"""

from pathlib import Path

import pytest

from tsplib_parser.exceptions import ParseError, ValidationError
from tsplib_parser.parser import FormatParser


def _write(tmp_path: Path, name: str, content: str) -> str:
  """Write ``content`` to ``tmp_path/name`` and return the path string."""
  target = tmp_path / name
  target.write_text(content)
  return str(target)


class TestSectionCorruptionRaises:
  """A poisoned line inside a known data section rejects the whole file."""

  @pytest.mark.parametrize(
    "filename,fixture_name,expected_type",
    [
      ("bad.vrp", "malformed_demand_content", ParseError),
      ("bad.tsp", "malformed_tsp_content", ParseError),
      ("bad.atsp", "malformed_matrix_content", ParseError),
      ("bad.hcp", "malformed_edge_data_content", ParseError),
    ],
    ids=["demand-section", "coord-section", "weight-matrix", "edge-data"],
  )
  def test_poisoned_section_rejects_file(
    self,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    filename: str,
    fixture_name: str,
    expected_type: type[Exception],
  ) -> None:
    """WHAT: one poisoned line inside each known data section.

    WHY: these were previously swallowed at logger.debug, returning success
    with the section silently empty.

    EXPECTED: FormatParser.parse_file raises the documented error; no partial
    result is returned.
    """
    content = request.getfixturevalue(fixture_name)
    path = _write(tmp_path, filename, content)
    with pytest.raises(expected_type, match=r"parse errors|invalid .*_SECTION"):
      FormatParser().parse_file(path)

  @pytest.mark.requires_dataset
  def test_control_valid_file_parses(self, test_data_dir: Path) -> None:
    """Control: the loud path must not reject healthy files."""
    parser = FormatParser()
    result = parser.parse_file(test_data_dir / "tsp" / "berlin52.tsp")
    assert result["problem_data"]["dimension"] == 52
    assert len(result["coords"]) == 52


class TestExceptionContract:
  """ValidationError must surface under its own type, per the API contract."""

  def test_missing_dimension_raises_validation_error(self, tmp_path: Path, missing_dimension_content: str) -> None:
    """WHAT: file omits the mandatory DIMENSION keyword.

    WHY: parse_file's docstring promises ValidationError for structurally
    invalid data; a broad ``except Exception`` previously rewrote it into a
    generic ParseError, so callers catching ValidationError never fired.

    EXPECTED: ValidationError, not ParseError.
    """
    path = _write(tmp_path, "nodim.tsp", missing_dimension_content)
    with pytest.raises(ValidationError, match="Dimension must be positive integer"):
      FormatParser().parse_file(path)


class TestStructuralValidation:
  """Cross-field invariants enforced by validate_problem_data."""

  def test_cvrp_missing_demand_entry_rejected(self, tmp_path: Path) -> None:
    """WHAT: a CVRP whose DEMAND_SECTION drops the entry for node 3.

    WHY: demands are the core payload of a CVRP; a section that no longer
    covers every node 1..dimension is corrupt.

    EXPECTED: ValidationError naming the missing node.
    """
    clean = """NAME: clean_cvrp
TYPE: CVRP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EUC_2D
CAPACITY: 10
NODE_COORD_SECTION
1 0 0
2 1 0
3 0 1
DEMAND_SECTION
1 0
2 3
3 5
DEPOT_SECTION
1
-1
EOF
"""
    # Drop the demand entry for node 3, leaving nodes 1..2 covered.
    path = _write(tmp_path, "partial.vrp", clean.replace("3 5\n", "", 1))
    with pytest.raises(ValidationError, match="DEMAND_SECTION is missing entries"):
      FormatParser().parse_file(path)

  def test_explicit_without_weights_rejected(self, tmp_path: Path, explicit_without_weights_content: str) -> None:
    """WHAT: file declares EDGE_WEIGHT_TYPE EXPLICIT but no EDGE_WEIGHT_SECTION.

    WHY: an explicit-weight problem with no weight data is unusable and must
    not reach the database weightless.

    EXPECTED: ValidationError.
    """
    path = _write(tmp_path, "noweights.atsp", explicit_without_weights_content)
    with pytest.raises(ValidationError, match="EDGE_WEIGHT_SECTION produced no weights"):
      FormatParser().parse_file(path)


class TestRealWorldVariants:
  """Regressions surfaced by making failures loud: format variants the parser
  previously mishandled (or silently dropped)."""

  def test_tab_separated_coordinates_parse(self, tmp_path: Path, tab_separated_coords_content: str) -> None:
    """WHAT: NODE_COORD_SECTION columns separated by tabs.

    WHY: kv splitting used a literal-space separator, so tab-separated files
    failed; pa561.tsp's DISPLAY_DATA_SECTION (561 rows) was silently lost.

    EXPECTED: all 3 coordinates parsed correctly regardless of whitespace.
    """
    path = _write(tmp_path, "tab.tsp", tab_separated_coords_content)
    result = FormatParser().parse_file(path)
    assert result["coords"] == [
      [0.0, 0.0],
      [1.0, 0.0],
      [0.0, 1.0],
    ]

  def test_fixed_edges_keyword_form_parses(self, tmp_path: Path, fixed_edges_keyword_content: str) -> None:
    """WHAT: HCP declaring fixed edges via ``FIXED_EDGES :`` (alb4000-style).

    WHY: the keyword terminates EDGE_DATA_SECTION without a *_SECTION boundary
    and its pairs were previously dropped or misparsed.

    EXPECTED: edges intact and fixed_edges parsed, both 0-based.
    """
    path = _write(tmp_path, "alb_style.hcp", fixed_edges_keyword_content)
    result = FormatParser().parse_file(path)
    assert result["edges"] == [[0, 1], [1, 2], [2, 3], [3, 0]]
    assert result["fixed_edges"] == [[0, 1], [2, 3]]

  def test_adj_list_edge_data_sniffing(self, tmp_path: Path) -> None:
    """WHAT: EDGE_DATA_SECTION in ADJ_LIST layout is sniffed from content.

    WHY: edge parsing must not depend on EDGE_DATA_FORMAT keyword ordering,
    and no file in datasets_raw/problems exercises the ADJ_LIST path.

    EXPECTED: adjacency rows expand to 0-based ``[from, to]`` pairs.
    """
    content = (
      "NAME: adj\nTYPE: HCP\nDIMENSION: 3\nEDGE_DATA_FORMAT: ADJ_LIST\nEDGE_DATA_SECTION\n"
      "1: 2 3 -1\n2: 1 -1\n3: 1 -1\n-1\nEOF\n"
    )
    path = _write(tmp_path, "adj.hcp", content)
    result = FormatParser().parse_file(path)
    assert sorted(result["edges"]) == [[0, 1], [0, 2], [1, 0], [2, 0]]

  def test_adj_list_poisoned_neighbor_raises(self, tmp_path: Path) -> None:
    """WHAT: ADJ_LIST row with a non-integer neighbor node.

    WHY: adjacency data corruption must fail loudly, not drop the row.

    EXPECTED: ParseError naming the ADJ_LIST row.
    """
    content = (
      "NAME: adjbad\nTYPE: HCP\nDIMENSION: 3\nEDGE_DATA_FORMAT: ADJ_LIST\nEDGE_DATA_SECTION\n"
      "1: 2 3 -1\n2: 1 QQQ -1\n-1\nEOF\n"
    )
    path = _write(tmp_path, "adjbad.hcp", content)
    with pytest.raises(ParseError, match="ADJ_LIST"):
      FormatParser().parse_file(path)

  @pytest.mark.requires_dataset
  def test_tab_separated_display_data(self, test_data_dir: Path) -> None:
    """WHAT: pa561.tsp's tab-separated DISPLAY_DATA_SECTION end-to-end.

    WHY: pa561's display section (561 rows) was silently dropped both by
    literal-space splitting and by the retired v1 _extract_nodes (PB13).

    EXPECTED: all 561 display rows parse into result['display_coords'] with float [x, y] values.
    """
    real = test_data_dir / "tsp" / "pa561.tsp"
    result = FormatParser().parse_file(str(real))

    assert result["problem_data"]["dimension"] == 561
    assert result["coords"] == []
    assert len(result["display_coords"]) == 561
    assert result["metadata"]["has_display_coords"] is True
    assert all(len(row) == 2 and all(isinstance(v, float) for v in row) for row in result["display_coords"])

  def test_registered_lkh_headers_keep_typed_values(self, tmp_path: Path) -> None:
    """WHAT: MDVRP payload carrying ``VEHICLES :`` and ``DEPOTS :`` headers.

    WHY: ``_preprocess_vrp_file`` stripped every extended header before the
    problem class could parse it and re-added it as a raw string, so
    ``vehicles`` came back as ``"16"``, ``num_depots`` was never set, and a
    stray lowercased ``depots`` key appeared in ``problem_data``. Only headers
    the class does not register may be stripped.

    EXPECTED: ``vehicles``/``num_depots`` are ints and no ``depots`` key leaks.
    """
    content = (
      "NAME : mini-mdvrp\nTYPE : MDVRP\nDIMENSION : 5\nEDGE_WEIGHT_TYPE : EUC_2D\n"
      "VEHICLES : 16\nDEPOTS : 2\nCAPACITY : 80\n"
      "NODE_COORD_SECTION\n1 0.0 0.0\n2 10.0 0.0\n3 1.0 1.0\n4 2.0 2.0\n5 3.0 3.0\n"
      "DEMAND_SECTION\n1 0\n2 0\n3 10\n4 20\n5 30\n"
      "DEPOT_SECTION\n1\n2\n-1\nEOF\n"
    )
    payload = FormatParser().parse_file(_write(tmp_path, "mini-mdvrp.vrp", content))["problem_data"]

    assert payload["vehicles"] == 16
    assert isinstance(payload["vehicles"], int)
    assert payload.get("num_depots") == 2
    assert "depots" not in payload
