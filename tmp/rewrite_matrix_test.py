from pathlib import Path

path = Path("tests/tsplib_parser/test_unit_matrix_formats.py")
text = path.read_text()

start = text.index('  @pytest.mark.skip(\n    reason="BUG: Parser returns')
end = text.index("  def test_atsp_files_have_asymmetric_data(self):")

replacement = '''  def test_br17_atsp_full_matrix_matches_file(self, br17_path: Path) -> None:
    """WHAT: Parse br17.atsp and read the explicit matrix.
    WHY: The parser must expose a FullMatrix, not the removed v1 nested list.
    EXPECTED: 17x17 matrix whose first row and spot values equal the file.
    """
    parsed: dict[str, Any] = FormatParser().parse_file(str(br17_path))
    problem: dict[str, Any] = parsed["problem_data"]

    assert problem["name"] == "br17"
    assert problem["dimension"] == 17
    assert problem["edge_weight_format"] == "FULL_MATRIX"

    matrix = problem["edge_weights"]
    assert isinstance(matrix, FullMatrix)
    assert matrix.size == 17

    expected_row_zero: list[int] = [9999, 3, 5, 48, 48, 8, 8, 5, 5, 3, 3, 0, 3, 5, 8, 8, 5]
    assert [matrix[0, column] for column in range(17)] == expected_row_zero
    assert matrix[1, 0] == 3
    assert matrix[1, 9] == 0
    assert matrix[16, 16] == 9999

  @pytest.mark.requires_dataset
  def test_corpus_full_matrix_values_match_raw_sections(self, test_data_dir: Path) -> None:
    """WHAT: Compare every extracted FULL_MATRIX against its raw section.
    WHY: The old manual script sampled matrices; the parser contract is exact.
    EXPECTED: For every EXPLICIT + FULL_MATRIX corpus file, the matrix size and
      every flattened value equal the integers in EDGE_WEIGHT_SECTION.
    """
    corpus_files: list[Path] = sorted(test_data_dir.rglob("*.atsp")) + sorted(
      test_data_dir.rglob("*.tsp")
    )
    checked = 0

    for corpus_path in corpus_files:
      parsed: dict[str, Any] = FormatParser().parse_file(str(corpus_path))
      problem: dict[str, Any] = parsed["problem_data"]
      if problem["edge_weight_type"] != "EXPLICIT" or problem["edge_weight_format"] != "FULL_MATRIX":
        continue

      dimension: int = problem["dimension"]
      raw_values: list[int] = _read_full_matrix_section(corpus_path)
      matrix = problem["edge_weights"]

      assert isinstance(matrix, FullMatrix), f"{corpus_path.name} must expose a FullMatrix"
      assert matrix.size == dimension, f"{corpus_path.name}: size {matrix.size} != {dimension}"
      assert len(raw_values) == dimension * dimension, f"{corpus_path.name}: raw section size"
      assert matrix.numbers == raw_values, f"{corpus_path.name}: values differ from raw section"
      checked += 1

    assert checked > 0, "Corpus should contain EXPLICIT/FULL_MATRIX problems"

'''

text = text[:start] + replacement + text[end:]
text = text.rstrip() + '''


def _read_full_matrix_section(path: Path) -> list[int]:
  """Return the integers of a FULL_MATRIX EDGE_WEIGHT_SECTION, in file order."""
  lines: list[str] = path.read_text(encoding="utf-8", errors="replace").splitlines()
  start: int = next(
    index for index, line in enumerate(lines) if line.strip().startswith("EDGE_WEIGHT_SECTION")
  )

  values: list[int] = []
  for line in lines[start + 1 :]:
    stripped: str = line.strip()
    if not stripped:
      continue
    if any(character.isalpha() for character in stripped):
      break
    values.extend(int(token) for token in stripped.split())
  return values
'''
text = text.replace("  def br17_path(self):", "  def br17_path(self) -> Path:")
path.write_text(text)
