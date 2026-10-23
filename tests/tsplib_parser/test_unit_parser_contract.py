"""Parser behavior contracts hardened by the 2026-10-14 broken-class pass.

WHAT
----
Unit tests for `tsplib_parser` behaviors that used to be silent, lenient, or
spec-violating:

- PB3 temporary-file isolation around VRP preprocessing
- PB5 `#` comments inside data sections
- PB6 the removed lenient base-class parser
- PB7 error messages for callables without `__name__`
- PB8 duplicate section keys
- PB9 coordinate-dimension validation (relocated into `validate_problem_data`)
- PB10 the spec-legal `EDGE_WEIGHT_FORMAT: FUNCTION`
- PB11 unregistered sections reported, stripped sections recorded

WHY
---
Every one of these cases previously either dropped data silently or rejected
legal input, and none of them had a test. They are behavioral contracts of the
parser library, so they live next to the other parser tests in
`tests/tsplib_parser/` rather than in a separate tree.

EXPECTED
--------
- Values are asserted, not just shapes.
- Illegal input raises the documented exception with a message that names the
  offending construct.
- Legal input parses with every value intact.
"""

import functools
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tsplib_parser.exceptions import ParseError
from tsplib_parser.fields import IntegerField
from tsplib_parser.models import Problem, StandardProblem
from tsplib_parser.parser import FormatParser
from tsplib_parser.transformers import FuncT
from tsplib_parser.validation import validate_problem_data


def _write(tmp_path: Path, name: str, content: str) -> str:
  """Write ``content`` to ``tmp_path/name`` and return the path as a string."""
  target = tmp_path / name
  target.write_text(content)
  return str(target)


class TestCommentsInsideSections:
  """PB5: a `#` comment must be ignored everywhere, never fed to a field."""

  def test_comments_are_ignored_before_and_inside_sections(
    self, tmp_path: Path, comment_inside_sections_content: str
  ) -> None:
    """WHAT: `#` comments before the keywords and inside NODE_COORD_SECTION.

    WHY: only blank lines were skipped, so a comment inside a section reached
    the field parser and rejected the whole file.

    EXPECTED: the file parses and every coordinate value is intact.
    """
    path = _write(tmp_path, "commented.tsp", comment_inside_sections_content)
    result = FormatParser().parse_file(path)

    assert result["problem_data"]["name"] == "commented", "the comment before NAME must not be read as data"
    assert result["problem_data"]["dimension"] == 3, "DIMENSION must survive a comment inside the section"
    assert result["coords"] == [
      [0.0, 0.0],
      [10.0, 0.0],
      [0.0, 20.0],
    ], "every coordinate row must be parsed as float coordinates in 0-based order"


class TestDuplicateKeysRejected:
  """PB8: a repeated key in a section is corruption, not last-wins."""

  @pytest.mark.parametrize(
    ("filename", "fixture_name", "section"),
    [
      ("dup.vrp", "duplicate_demand_content", "DEMAND_SECTION"),
      ("dup.tsp", "duplicate_coords_content", "NODE_COORD_SECTION"),
    ],
    ids=["demand-section", "coord-section"],
  )
  def test_duplicate_key_rejects_file(
    self,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    filename: str,
    fixture_name: str,
    section: str,
  ) -> None:
    """WHAT: a section listing the same node id twice.

    WHY: the second row overwrote the first without a word, while every other
    malformed item already failed the file.

    EXPECTED: ParseError naming the duplicate key; no partial result returned.
    """
    content: str = request.getfixturevalue(fixture_name)
    path = _write(tmp_path, filename, content)

    with pytest.raises(ParseError, match=rf"invalid {section}: parsing errors: duplicate key"):
      FormatParser().parse_file(path)


class TestFunctionEdgeWeightFormat:
  """PB10: `EDGE_WEIGHT_FORMAT: FUNCTION` is spec-legal (TSPLIB95 1.1.7)."""

  def test_function_format_with_geo_parses(self, tmp_path: Path, function_weight_format_content: str) -> None:
    """WHAT: a GEO problem declaring `EDGE_WEIGHT_FORMAT: FUNCTION`.

    WHY: the validator rejected `FUNCTION` as an unknown format, failing legal
    input.

    EXPECTED: parses with the format and the coordinates preserved.
    """
    path = _write(tmp_path, "function.tsp", function_weight_format_content)
    result = FormatParser().parse_file(path)

    assert result["problem_data"]["edge_weight_format"] == "FUNCTION", "the declared format must be kept verbatim"
    assert result["problem_data"]["edge_weight_type"] == "GEO"
    assert result["coords"] == [
      [48.23, 10.53],
      [49.10, 11.20],
      [50.0, 12.0],
    ], "a FUNCTION format must not discard the coordinates"

  @pytest.mark.parametrize(("name", "dimension"), [("burma14", 14), ("gr431", 431)])
  @pytest.mark.requires_dataset
  def test_corpus_function_files_parse(self, test_data_dir: Path, name: str, dimension: int) -> None:
    """WHAT: the two corpus files declaring `EDGE_WEIGHT_FORMAT: FUNCTION`.

    WHY: they are the real-world instances of the format, so the fix is verified
    against data, not only against a synthetic fixture.

    EXPECTED: each parses with its declared dimension and one coordinate row per node.
    """
    result = FormatParser().parse_file(str(test_data_dir / "tsp" / f"{name}.tsp"))

    assert result["problem_data"]["edge_weight_format"] == "FUNCTION"
    assert result["problem_data"]["dimension"] == dimension, f"{name} declares DIMENSION {dimension}"
    assert len(result["coords"]) == dimension, f"{name} must yield one coordinate row per dimension"

  def test_explicit_function_needs_no_matrix(self, tmp_path: Path, explicit_function_format_content: str) -> None:
    """WHAT: `EXPLICIT` + `FUNCTION` with no EDGE_WEIGHT_SECTION.

    WHY: a `FUNCTION` format means the weights come from the declared distance
    function, so demanding a weight section rejects legal input.

    EXPECTED: parses, and no fabricated weight matrix is attached.
    """
    path = _write(tmp_path, "explicit_function.tsp", explicit_function_format_content)
    result = FormatParser().parse_file(path)

    assert result["problem_data"]["edge_weight_format"] == "FUNCTION"
    assert "edge_weights" not in result["problem_data"], "a FUNCTION format carries no matrix to attach"


class TestUnknownSectionReporting:
  """PB11: an unmodelled section is an error; unknown keywords stay tolerated."""

  def test_unregistered_section_rejects_file(self, tmp_path: Path, unregistered_section_content: str) -> None:
    """WHAT: a file carrying `REQUIRED_NODES_SECTION`, which no field models.

    WHY: the section accumulator discarded unregistered sections silently, so
    their payload vanished without a trace. Sections the preprocessor knows how
    to strip (such as `BACKHAUL_SECTION`) are recorded instead — see
    `TestStrippedSectionRecording`.

    EXPECTED: ParseError naming the unsupported section.
    """
    path = _write(tmp_path, "unregistered_section.tsp", unregistered_section_content)

    with pytest.raises(ParseError, match=r"unsupported REQUIRED_NODES_SECTION"):
      FormatParser().parse_file(path)

  def test_unknown_keyword_extension_still_tolerated(
    self, tmp_path: Path, unknown_keyword_extension_content: str
  ) -> None:
    """WHAT: an unknown non-section keyword (`MY_EXTENSION : ...`).

    WHY: the spec allows keyword extensions, so reporting unknown sections must
    not turn every extension into a failure.

    EXPECTED: parses, with the known values intact.
    """
    path = _write(tmp_path, "keyword_extension.tsp", unknown_keyword_extension_content)
    result = FormatParser().parse_file(path)

    assert result["problem_data"]["name"] == "keyword_extension"
    assert result["problem_data"]["dimension"] == 3, "an unknown keyword must not disturb DIMENSION"
    assert len(result["coords"]) == 3, "an unknown keyword must not swallow coordinate rows"


class TestStrippedSectionRecording:
  """PB11: stripping an extended section is recorded, never silent."""

  def test_time_window_section_is_recorded(self, tmp_path: Path, time_window_vrp_content: str) -> None:
    """WHAT: CVRP carrying a `TIME_WINDOW_SECTION`.

    WHY: the section is removed so `StandardProblem` stays core-only; the removal
    has to be visible in the result instead of silent, and the canonical TSPLIB
    type must remain `CVRP` (PB4).

    EXPECTED: the flag is set, the section is listed as stripped, type remains
    `CVRP`, and the core CVRP values are intact.
    """
    path = _write(tmp_path, "tw.vrp", time_window_vrp_content)
    result = FormatParser().parse_file(path)

    assert result["problem_data"]["type"] == "CVRP", "canonical type must remain CVRP (PB4)"
    assert result["problem_data"]["has_time_windows"] is True, "the stripped section must still set the flag"
    assert result["problem_data"]["stripped_sections"] == ["TIME_WINDOW_SECTION"], "the removal must be recorded"
    assert result["problem_data"]["dimension"] == 3
    assert result["demands"] == [0, 3, 5], "stripping one section must not disturb the CVRP demands"


class TestTemporaryFileIsolation:
  """PB3: the VRP preprocessor must not leak its temporary file."""

  @staticmethod
  def _route_temp_files_to(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Send `tempfile` output into `tmp_path`, where a leak is observable.

    A throwaway file is created and removed to prove the redirection actually
    took effect, so the leak checks below cannot pass vacuously.
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    probe_fd, probe_name = tempfile.mkstemp(suffix=".probe")
    os.close(probe_fd)
    probe = Path(probe_name)
    try:
      assert probe.parent == tmp_path, "tempfile must be redirected, or a leak would go unseen"
    finally:
      probe.unlink()

  def test_temp_file_removed_on_success(
    self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, time_window_vrp_content: str
  ) -> None:
    """WHAT: a preprocessing run that parses successfully.

    WHY: the temporary file used to be removed only on the success path, so the
    failure path (below) leaked; both paths must clean up.

    EXPECTED: preprocessing happened and no file was left behind.
    """
    self._route_temp_files_to(monkeypatch, tmp_path)
    path = _write(tmp_path, "tw_ok.vrp", time_window_vrp_content)
    before = set(tmp_path.iterdir())

    result = FormatParser().parse_file(path)

    assert result["problem_data"]["has_time_windows"] is True, "this input must trigger preprocessing"
    assert tempfile.gettempdir() == str(tmp_path), "the temp redirect must be active or a leak goes unseen"
    assert set(tmp_path.iterdir()) == before, "the temporary file must be removed on the success path"

  def test_temp_file_removed_when_parse_fails(
    self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing_preprocessed_vrp_content: str
  ) -> None:
    """WHAT: a preprocessing run whose parse then fails.

    WHY: this was the leaking path — every failed parse left a `*.vrp` behind in
    TMPDIR. The input is the same shape as the success case above, which asserts
    that this content does trigger preprocessing.

    EXPECTED: ParseError raised and no file left behind.
    """
    self._route_temp_files_to(monkeypatch, tmp_path)
    path = _write(tmp_path, "tw_bad.vrp", failing_preprocessed_vrp_content)
    before = set(tmp_path.iterdir())

    with pytest.raises(ParseError, match="invalid DEMAND_SECTION"):
      FormatParser().parse_file(path)

    assert tempfile.gettempdir() == str(tmp_path), "the temp redirect must be active or a leak goes unseen"
    assert set(tmp_path.iterdir()) == before, "the temporary file must be removed on the failure path too"


class TestLegacyParserRemoved:
  """PB6: the base class no longer offers a second, lenient parser."""

  def test_problem_has_no_parse_method(self) -> None:
    """WHAT: checking Problem has no parse method.

    WHY: Problem is an abstract metadata model, not a syntax parser.
    LSP requires that Problem does not advertise a parser it cannot fulfill.
    The real TSPLIB95 format parser is StandardProblem.parse.

    EXPECTED: Problem has no parse attribute.
    """
    assert not hasattr(Problem, "parse"), "Problem must not advertise a parse() method; use StandardProblem.parse"

  def test_standard_problem_parse_still_works(self) -> None:
    """WHAT: the strict parser after the cleanup.

    WHY: removing the duplicate must not disturb the real parse path.

    EXPECTED: values are parsed as before (read through `as_name_dict`, since the
    class attributes are `Field` descriptors, not the parsed values).
    """
    data: dict[str, Any] = StandardProblem.parse(
      "NAME: ok\nTYPE: TSP\nDIMENSION: 2\nEDGE_WEIGHT_TYPE: EUC_2D\n"
    ).as_name_dict()

    assert data["name"] == "ok"
    assert data["dimension"] == 2, "the strict parser must still convert DIMENSION to an int"
    assert data["edge_weight_type"] == "EUC_2D"


class TestCallableWithoutName:
  """PB7: the FuncT error path must not itself raise."""

  def test_partial_reports_its_type_instead_of_crashing(self) -> None:
    """WHAT: a `functools.partial` that fails on the input text.

    WHY: the handler read `func.__name__`; partials have none, so it raised
    AttributeError and hid the actual conversion failure.

    EXPECTED: ParseError naming the callable type, with the conversion reason.
    """
    transformer: FuncT[int] = FuncT(func=functools.partial(int, base=2))

    with pytest.raises(ParseError, match=r"could not apply partial to zz"):
      transformer.parse("zz")


class TestCoordinateDimensionValidation:
  """PB9: the coordinate rule runs in `validate_problem_data`, not a dead hook."""

  def test_mixed_dimensions_are_reported(self) -> None:
    """WHAT: rows mixing 2-D and 3-D coordinates.

    WHY: the rule used to live in an unreachable field hook; mixed dimensions in
    one section silently misalign downstream array columns.

    EXPECTED: one error naming the mixed dimensions.
    """
    errors: list[str] = validate_problem_data(
      {
        "name": "mixed",
        "type": "TSP",
        "dimension": 2,
        "edge_weight_type": "EUC_2D",
        "node_coords": {1: (0.0, 0.0), 2: (1.0, 0.0, 2.0)},
      }
    )

    assert "NODE_COORD_SECTION mixes coordinate dimensions: [2, 3]" in errors, (
      f"mixed 2-D/3-D rows must be reported, got: {errors}"
    )

  def test_unsupported_dimensions_are_reported(self) -> None:
    """WHAT: 4-D coordinates, which TSPLIB95 does not define.

    WHY: only 2-D and 3-D are legal (`NODE_COORD_TYPE`), so a 4-D row must fail
    loudly rather than be carried into the database.

    EXPECTED: one error naming the unsupported dimensions.
    """
    errors: list[str] = validate_problem_data(
      {
        "name": "fourd",
        "type": "TSP",
        "dimension": 1,
        "edge_weight_type": "EUC_2D",
        "node_coords": {1: (0.0, 0.0, 0.0, 0.0)},
      }
    )

    assert "NODE_COORD_SECTION has unsupported coordinate dimensions: [4] (spec allows [2, 3])" in errors, (
      f"a 4-D row must be reported, got: {errors}"
    )

  def test_consistent_3d_coordinates_pass(self) -> None:
    """WHAT: a legitimately 3-D coordinate section.

    WHY: the new rule must not reject valid 3-D problems.

    EXPECTED: no coordinate-dimension error is produced.
    """
    errors: list[str] = validate_problem_data(
      {
        "name": "threed",
        "type": "TSP",
        "dimension": 2,
        "edge_weight_type": "EUC_3D",
        "node_coords": {1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0)},
      }
    )

    assert not [error for error in errors if "coordinate dimensions" in error], (
      f"consistent 3-D coordinates must pass, got: {errors}"
    )


class TestFieldDescriptorProtocol:
  """PP5: Field implements standard descriptor protocol without Problem.__getattribute__ interception."""

  def test_unset_field_returns_default_value(self) -> None:
    problem = StandardProblem()
    assert problem.dimension == 0
    assert problem.capacity == 0
    assert problem.demands == {}

  def test_set_field_returns_instance_value(self) -> None:
    problem = StandardProblem(dimension=42)
    assert problem.dimension == 42

  def test_class_access_returns_field_descriptor(self) -> None:
    assert isinstance(StandardProblem.dimension, IntegerField)

  def test_unknown_attribute_raises_attribute_error(self) -> None:
    problem = StandardProblem()
    with pytest.raises(AttributeError):
      _ = problem.non_existent_attribute
