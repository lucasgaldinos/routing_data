"""Tests for matrix format conversion and equivalence.

WHAT: Verify that different matrix formats produce equivalent full matrices
WHY: Ensure conversion logic preserves distance values correctly
HOW: Test format duality, conversion to full matrix, and real TSPLIB data

This completes Task 8: Matrix Conversion Verification
- Tests conversion from triangular formats to full matrices
- Verifies row/column duality with same input data
- Uses br17.atsp as real-world baseline

Author: AI Assistant
Date: 2025-10-27
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tsplib_parser.exceptions import ParseError
from tsplib_parser.matrix import (
  TYPES,
  FullMatrix,
  LowerCol,
  LowerDiagCol,
  LowerDiagRow,
  LowerRow,
  UpperCol,
  UpperDiagCol,
  UpperDiagRow,
  UpperRow,
)
from tsplib_parser.parser import FormatParser

if TYPE_CHECKING:
  from tsplib_parser.types import ParseResult


class TestMatrixFormatEquivalence:
  """Test that different formats produce equivalent matrices."""

  def test_all_formats_create_valid_matrices(self) -> None:
    """
    WHAT: Test that all 9 matrix format classes are instantiable
    WHY: Verify TYPES dict maps to working classes
    EXPECTED: All format classes create valid matrix objects
    DATA: Appropriate element counts for each format
    """
    # Full matrix 4x4: 16 elements
    full = FullMatrix(list(range(16)), size=4)
    assert full.size == 4

    # Triangular with diagonal: 10 elements
    lower_diag = LowerDiagRow(list(range(10)), size=4)
    upper_diag = UpperDiagRow(list(range(10)), size=4)
    lower_diag_col = LowerDiagCol(list(range(10)), size=4)
    upper_diag_col = UpperDiagCol(list(range(10)), size=4)
    assert lower_diag.size == upper_diag.size == 4
    assert lower_diag_col.size == upper_diag_col.size == 4

    # Triangular without diagonal: 6 elements
    lower = LowerRow(list(range(6)), size=4)
    upper = UpperRow(list(range(6)), size=4)
    lower_col = LowerCol(list(range(6)), size=4)
    upper_col = UpperCol(list(range(6)), size=4)
    assert lower.size == upper.size == 4
    assert lower_col.size == upper_col.size == 4

  def test_lower_row_to_full_matrix_conversion(self) -> None:
    """
    WHAT: Verify LowerRow can reconstruct full symmetric matrix
    WHY: Test that triangular storage correctly expands to full matrix
    EXPECTED: All matrix positions accessible with correct values
    DATA: 4x4 symmetric matrix stored as lower triangle

    Full symmetric matrix:
      0  10  20  30
     10   0  21  31
     20  21   0  32
     30  31  32   0

    LowerRow storage (no diagonal): [10, 20,21, 30,31,32]
    """
    numbers: list[int] = [10, 20, 21, 30, 31, 32]
    matrix = LowerRow(numbers, size=4)

    # Reconstruct full matrix by accessing all positions
    full = []
    for i in range(4):
      row = []
      for j in range(4):
        row.append(matrix[i, j])
      full.append(row)

    # Verify full matrix
    expected: list[list[int]] = [[0, 10, 20, 30], [10, 0, 21, 31], [20, 21, 0, 32], [30, 31, 32, 0]]
    assert full == expected

  def test_upper_col_produces_same_matrix_as_lower_row(self) -> None:
    """
    WHAT: Verify UpperCol and LowerRow produce identical matrices
    WHY: Test column/row duality - these should be equivalent representations
    EXPECTED: matrix_upper_col[i,j] == matrix_lower_row[i,j] for all i,j
    DATA: Same numbers [10, 20, 21, 30, 31, 32]

    This is the KEY duality test mentioned in Task 8:
    "Verify row/column duality (UpperCol=LowerRow logic)"
    """
    numbers: list[int] = [10, 20, 21, 30, 31, 32]

    lower_row = LowerRow(numbers, size=4)
    upper_col = UpperCol(numbers, size=4)

    # Verify EVERY element matches
    for i in range(4):
      for j in range(4):
        assert lower_row[i, j] == upper_col[i, j], (
          f"Mismatch at [{i},{j}]: LowerRow={lower_row[i, j]}, UpperCol={upper_col[i, j]}"
        )

  def test_lower_col_produces_same_matrix_as_upper_row(self) -> None:
    """
    WHAT: Verify LowerCol and UpperRow produce identical matrices
    WHY: Test second column/row duality pair
    EXPECTED: matrix_lower_col[i,j] == matrix_upper_row[i,j] for all i,j
    DATA: Same numbers [1, 2, 3, 12, 13, 23]
    """
    numbers: list[int] = [1, 2, 3, 12, 13, 23]

    upper_row = UpperRow(numbers, size=4)
    lower_col = LowerCol(numbers, size=4)

    # Verify EVERY element matches
    for i in range(4):
      for j in range(4):
        assert upper_row[i, j] == lower_col[i, j], (
          f"Mismatch at [{i},{j}]: UpperRow={upper_row[i, j]}, LowerCol={lower_col[i, j]}"
        )

  def test_upper_diag_col_produces_same_matrix_as_lower_diag_row(self) -> None:
    """
    WHAT: Verify UpperDiagCol and LowerDiagRow produce identical matrices
    WHY: Test third column/row duality pair (with diagonal)
    EXPECTED: Matrices match element-wise
    DATA: [0, 10, 11, 20, 21, 22, 30, 31, 32, 33]
    """
    numbers: list[int] = [0, 10, 11, 20, 21, 22, 30, 31, 32, 33]

    lower_diag_row = LowerDiagRow(numbers, size=4)
    upper_diag_col = UpperDiagCol(numbers, size=4)

    for i in range(4):
      for j in range(4):
        assert lower_diag_row[i, j] == upper_diag_col[i, j], f"Mismatch at [{i},{j}]"

  def test_lower_diag_col_produces_same_matrix_as_upper_diag_row(self) -> None:
    """
    WHAT: Verify LowerDiagCol and UpperDiagRow produce identical matrices
    WHY: Test fourth column/row duality pair (with diagonal)
    EXPECTED: Matrices match element-wise
    DATA: [0, 1, 2, 3, 11, 12, 13, 22, 23, 33]
    """
    numbers: list[int] = [0, 1, 2, 3, 11, 12, 13, 22, 23, 33]

    upper_diag_row = UpperDiagRow(numbers, size=4)
    lower_diag_col = LowerDiagCol(numbers, size=4)

    for i in range(4):
      for j in range(4):
        assert upper_diag_row[i, j] == lower_diag_col[i, j], f"Mismatch at [{i},{j}]"

  def test_symmetric_matrix_lower_and_upper_formats_match(self) -> None:
    """
    WHAT: Verify that symmetric matrix produces same values from lower/upper formats
    WHY: For symmetric matrices, lower and upper triangles contain same info
    EXPECTED: LowerDiagRow and UpperDiagRow produce same full matrix
    DATA: Symmetric 3x3 matrix

    Symmetric matrix:
    5  1  2
    1  5  3
    2  3  5

    LowerDiagRow: [5, 1,5, 2,3,5]
    UpperDiagRow: [5,1,2, 5,3, 5]
    """
    lower_numbers: list[int] = [5, 1, 5, 2, 3, 5]
    upper_numbers: list[int] = [5, 1, 2, 5, 3, 5]

    lower = LowerDiagRow(lower_numbers, size=3)
    upper = UpperDiagRow(upper_numbers, size=3)

    # Both should produce same symmetric matrix
    for i in range(3):
      for j in range(3):
        assert lower[i, j] == upper[i, j], f"Symmetric matrix mismatch at [{i},{j}]"

  def test_asymmetric_matrix_lower_and_upper_formats_differ(self) -> None:
    """
    WHAT: Verify asymmetric matrices preserve different upper/lower values
    WHY: For asymmetric matrices (like ATSP), [i,j] != [j,i]
    EXPECTED: LowerDiagRow and UpperDiagRow produce different values
    DATA: Asymmetric 3x3 matrix

    Asymmetric matrix:
    0  10  20
    1   0  21
    2   3   0

    LowerDiagRow: [0, 1,0, 2,3,0]
    UpperDiagRow: [0,10,20, 0,21, 0]
    """
    lower_numbers: list[int] = [0, 1, 0, 2, 3, 0]
    upper_numbers: list[int] = [0, 10, 20, 0, 21, 0]

    lower = LowerDiagRow(lower_numbers, size=3)
    upper = UpperDiagRow(upper_numbers, size=3)

    # Diagonal should match
    for i in range(3):
      assert lower[i, i] == upper[i, i] == 0

    # Off-diagonal should differ
    assert lower[1, 0] == 1 and upper[1, 0] == 10  # different!
    assert lower[0, 1] == 1 and upper[0, 1] == 10  # lower uses symmetry

  def test_types_dict_completeness(self) -> None:
    """
    WHAT: Verify TYPES dict contains all 9 matrix format mappings
    WHY: Ensure parser can instantiate any EDGE_WEIGHT_FORMAT
    EXPECTED: All 9 format names map to correct classes
    DATA: TYPES dictionary
    """
    assert len(TYPES) == 9

    # Verify all expected formats are present
    expected_formats = {
      "FULL_MATRIX": FullMatrix,
      "UPPER_DIAG_ROW": UpperDiagRow,
      "UPPER_ROW": UpperRow,
      "LOWER_DIAG_ROW": LowerDiagRow,
      "LOWER_ROW": LowerRow,
      "UPPER_DIAG_COL": UpperDiagCol,
      "UPPER_COL": UpperCol,
      "LOWER_DIAG_COL": LowerDiagCol,
      "LOWER_COL": LowerCol,
    }

    for format_name, matrix_class in expected_formats.items():
      assert format_name in TYPES, f"Missing format: {format_name}"
      assert TYPES[format_name] == matrix_class


class TestRealTSPLIBData:
  """Test with real TSPLIB95 data from br17.atsp."""

  @pytest.fixture
  def br17_path(self, dataset_path: Callable[..., str]) -> Path:
    """Path to br17.atsp test file."""
    return Path(dataset_path("atsp", "br17.atsp"))

  @pytest.mark.requires_dataset
  def test_br17_atsp_full_matrix_matches_file(self, br17_path: Path) -> None:
    """WHAT: Parse br17.atsp and read the explicit matrix.
    WHY: The parser must expose a FullMatrix, not the removed v1 nested list.
    EXPECTED: 17x17 matrix whose first row and spot values equal the file.
    """
    parsed: ParseResult = FormatParser().parse_file(str(br17_path))
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
  @pytest.mark.slow
  def test_corpus_full_matrix_values_match_raw_sections(self, test_data_dir: Path) -> None:
    """WHAT: Compare every extracted FULL_MATRIX against its raw section.
    WHY: The old manual script sampled matrices; the parser contract is exact.
    EXPECTED: For every EXPLICIT + FULL_MATRIX corpus file, the matrix size and
      every flattened value equal the integers in EDGE_WEIGHT_SECTION.
    """
    corpus_files: list[Path] = sorted(test_data_dir.rglob("*.atsp")) + sorted(test_data_dir.rglob("*.tsp"))
    checked = 0

    for corpus_path in corpus_files:
      parsed: ParseResult = FormatParser().parse_file(str(corpus_path))
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

  @pytest.mark.requires_dataset
  def test_atsp_files_have_asymmetric_data(self, dataset_path: Callable[..., str]) -> None:
    """
    Verify ATSP files contain actually asymmetric distance matrices.

    WHAT: Check ALL pairs (i,j) where i<j for asymmetry in ATSP files
    WHY: ATSP = Asymmetric TSP, must have d[i][j] != d[j][i] for significant proportion of pairs
    EXPECTED: At least 10% of pairs should be asymmetric for each ATSP file
    TEST DATA: Multiple ATSP files (br17, ft53, ft70)

    PROPERTY: For ATSP file, ∃ significant proportion where matrix[i][j] != matrix[j][i]

    This replaces the severely flawed test that only checked 8.6% of pairs.
    Now we check ALL pairs with meaningful threshold.
    """
    parser = FormatParser()

    # Test MULTIPLE ATSP files, not just one
    atsp_files: list[tuple[str, int]] = [
      (dataset_path("atsp", "br17.atsp"), 17),
      (dataset_path("atsp", "ft53.atsp"), 53),
      (dataset_path("atsp", "ft70.atsp"), 70),
    ]

    checked = 0
    for file_path, expected_dim in atsp_files:
      # Skip if file doesn't exist
      if not Path(file_path).exists():
        pytest.skip(f"Test file not found: {file_path}")
        continue

      # Parse file and extract edge weight matrix
      parsed_data: ParseResult = parser.parse_file(file_path)
      problem_data = parsed_data["problem_data"]
      edge_weights = problem_data["edge_weights"]

      # Verify dimension
      assert edge_weights.size == expected_dim, (
        f"{file_path}: Expected dimension {expected_dim}, got {edge_weights.size}"
      )

      # Check ALL pairs (upper triangle only for efficiency)
      asymmetric_count = 0
      total_pairs = 0

      for i in range(edge_weights.size):
        for j in range(i + 1, edge_weights.size):  # j > i (upper triangle)
          total_pairs += 1
          # Check if symmetric: matrix[i,j] should equal matrix[j,i] for symmetric matrix
          if edge_weights[i, j] != edge_weights[j, i]:
            asymmetric_count += 1

      # Calculate asymmetry ratio
      asymmetry_ratio = asymmetric_count / total_pairs if total_pairs > 0 else 0

      # MEANINGFUL assertion with threshold
      # ATSP files should have at least 10% asymmetric pairs
      assert asymmetry_ratio >= 0.10, (
        f"{file_path}: Expected ≥10% asymmetric pairs, got {asymmetry_ratio:.1%} "
        f"({asymmetric_count}/{total_pairs} pairs)"
      )

      checked += 1

    assert checked == len(atsp_files), "Every ATSP baseline file must be checked"

  def test_matrix_conversion_preserves_all_values(self) -> None:
    """
    WHAT: Test that converting triangular to full matrix preserves all values
    WHY: Ensure no data loss in format conversion
    EXPECTED: Can reconstruct original full matrix from triangular storage
    DATA: Small 5x5 symmetric matrix

    Original full matrix:
    0   1   2   3   4
    1   0   5   6   7
    2   5   0   8   9
    3   6   8   0  10
    4   7   9  10   0

    This can be stored as LowerRow: [1, 2,5, 3,6,8, 4,7,9,10] (10 elements)
    Or as UpperRow: [1,2,3,4, 5,6,7, 8,9, 10] (10 elements)
    """
    # Create full matrix
    full_numbers = [0, 1, 2, 3, 4, 1, 0, 5, 6, 7, 2, 5, 0, 8, 9, 3, 6, 8, 0, 10, 4, 7, 9, 10, 0]
    full_matrix = FullMatrix(full_numbers, size=5)

    # Create equivalent lower triangle representation
    lower_numbers = [1, 2, 5, 3, 6, 8, 4, 7, 9, 10]
    lower_matrix = LowerRow(lower_numbers, size=5)

    # Verify ALL values match
    for i in range(5):
      for j in range(5):
        assert full_matrix[i, j] == lower_matrix[i, j], (
          f"Mismatch at [{i},{j}]: full={full_matrix[i, j]}, lower={lower_matrix[i, j]}"
        )


class TestMatrixConversionEdgeCases:
  """Test edge cases in matrix conversion."""

  def test_zero_dimension_matrix(self) -> None:
    """Test that 0x0 matrices work correctly."""
    matrix = FullMatrix([], size=0)
    assert matrix.size == 0
    assert len(matrix.numbers) == 0

  def test_large_matrix_dimension_443(self) -> None:
    """
    WHAT: Test that large matrix (rbg443.atsp dimension) can be created
    WHY: Verify formulas work for real TSPLIB problem sizes
    EXPECTED: Matrix created with correct element count
    DATA: 443x443 dimensions (from rbg443.atsp)
    """
    # Full matrix 443x443 needs 196,249 elements
    dimension = 443
    full_size = dimension * dimension
    assert full_size == 196249

    # Create matrix with dummy data
    numbers = [0] * full_size
    matrix = FullMatrix(numbers, size=dimension)
    assert matrix.size == dimension

    # Lower triangle with diagonal: 443*444/2 = 98,346
    lower_size = dimension * (dimension + 1) // 2
    assert lower_size == 98346

    lower_numbers = [0] * lower_size
    lower_matrix = LowerDiagRow(lower_numbers, size=dimension)
    assert lower_matrix.size == dimension


# ---------------------------------------------------------------------------
# Merged from test_format/test_matrix_validation.py on 2026-10-20; bodies unchanged.
# ---------------------------------------------------------------------------


class TestMatrixDimensionValidation:
  """Test matrix dimension validation for all formats."""

  def test_full_matrix_correct_size(self) -> None:
    """
    WHAT: Create FullMatrix with correct number of elements
    WHY: Verify validation allows correct data
    EXPECTED: Matrix created successfully
    DATA: 3x3 matrix needs 9 elements
    """
    numbers = list(range(1, 10))  # 9 elements
    matrix = FullMatrix(numbers, size=3)
    assert matrix.size == 3
    assert len(matrix.numbers) == 9

  def test_full_matrix_incorrect_size(self) -> None:
    """
    WHAT: Create FullMatrix with wrong number of elements
    WHY: Verify validation catches dimension mismatch
    EXPECTED: ParseError with descriptive message
    DATA: 3x3 matrix with only 8 elements (needs 9)
    """
    numbers = list(range(1, 9))  # Only 8 elements

    with pytest.raises(ParseError, match="requires 9 elements") as exc_info:
      FullMatrix(numbers, size=3)

    error_msg = str(exc_info.value)
    assert "FullMatrix" in error_msg
    assert "dimension 3" in error_msg
    assert "requires 9" in error_msg
    assert "got 8" in error_msg

  def test_lower_row_correct_size(self) -> None:
    """
    WHAT: Create LowerRow with correct number of elements
    WHY: Verify triangular matrix without diagonal validation
    EXPECTED: Matrix created successfully
    DATA: 4x4 lower triangle without diagonal needs 6 elements
    """
    # Lower triangle 4x4 without diagonal: 1 + 2 + 3 = 6
    numbers = [1, 2, 3, 4, 5, 6]
    matrix = LowerRow(numbers, size=4)
    assert matrix.size == 4
    assert len(matrix.numbers) == 6

  def test_lower_row_incorrect_size(self) -> None:
    """
    WHAT: Create LowerRow with wrong number of elements
    WHY: Detect common error of providing full matrix to triangular
    EXPECTED: ParseError with correct size calculation
    DATA: 10x10 lower triangle needs 45, given only 40
    """
    numbers = list(range(40))  # Only 40 elements

    with pytest.raises(ParseError, match="LowerRow with dimension 10") as exc_info:
      LowerRow(numbers, size=10)

    error_msg = str(exc_info.value)
    assert "LowerRow" in error_msg
    assert "dimension 10" in error_msg
    assert "requires 45" in error_msg  # 10*9/2 = 45
    assert "got 40" in error_msg

  def test_lower_diag_row_correct_size(self) -> None:
    """
    WHAT: Create LowerDiagRow with correct number of elements
    WHY: Verify triangular matrix with diagonal validation
    EXPECTED: Matrix created successfully
    DATA: 4x4 lower triangle with diagonal needs 10 elements
    """
    # Lower triangle 4x4 with diagonal: 1 + 2 + 3 + 4 = 10
    numbers = list(range(1, 11))
    matrix = LowerDiagRow(numbers, size=4)
    assert matrix.size == 4
    assert len(matrix.numbers) == 10

  def test_upper_row_correct_size(self) -> None:
    """
    WHAT: Create UpperRow with correct number of elements
    WHY: Verify upper triangle without diagonal validation
    EXPECTED: Matrix created successfully
    DATA: 5x5 upper triangle without diagonal needs 10 elements
    """
    # Upper triangle 5x5 without diagonal: 4 + 3 + 2 + 1 = 10
    numbers = list(range(10))
    matrix = UpperRow(numbers, size=5)
    assert matrix.size == 5
    assert len(matrix.numbers) == 10

  def test_upper_diag_row_correct_size(self) -> None:
    """
    WHAT: Create UpperDiagRow with correct number of elements
    WHY: Verify upper triangle with diagonal validation
    EXPECTED: Matrix created successfully
    DATA: 5x5 upper triangle with diagonal needs 15 elements
    """
    # Upper triangle 5x5 with diagonal: 5 + 4 + 3 + 2 + 1 = 15
    numbers = list(range(15))
    matrix = UpperDiagRow(numbers, size=5)
    assert matrix.size == 5
    assert len(matrix.numbers) == 15

  def test_column_variants_same_size_requirements(self) -> None:
    """
    WHAT: Verify column variants have same size as row variants
    WHY: Column formats just interpret data differently
    EXPECTED: Same element count requirements
    DATA: Various triangular matrices
    """
    # LowerCol = UpperRow logic (no diagonal)
    numbers_6 = list(range(6))
    matrix_lower_col = LowerCol(numbers_6, size=4)
    matrix_upper_row = UpperRow(numbers_6, size=4)
    assert len(matrix_lower_col.numbers) == len(matrix_upper_row.numbers)

    # UpperCol = LowerRow logic (no diagonal)
    matrix_upper_col = UpperCol(numbers_6, size=4)
    matrix_lower_row = LowerRow(numbers_6, size=4)
    assert len(matrix_upper_col.numbers) == len(matrix_lower_row.numbers)

    # LowerDiagCol = UpperDiagRow logic (with diagonal)
    numbers_10 = list(range(10))
    matrix_lower_diag_col = LowerDiagCol(numbers_10, size=4)
    matrix_upper_diag_row = UpperDiagRow(numbers_10, size=4)
    assert len(matrix_lower_diag_col.numbers) == len(matrix_upper_diag_row.numbers)

  def test_large_matrix_size_calculation(self) -> None:
    """
    WHAT: Test size calculation for large matrices
    WHY: Verify formula works for realistic TSPLIB problem sizes
    EXPECTED: Correct element count for 443-node problem
    DATA: rbg443.atsp dimension (from real TSPLIB file)
    """
    # Full matrix 443x443 should need 196,249 elements
    expected_full = 443 * 443
    assert expected_full == 196249

    # Lower triangle with diagonal: 443*444/2 = 98,346
    expected_lower_diag = 443 * 444 // 2
    assert expected_lower_diag == 98346

    # This would fail with wrong element count
    with pytest.raises(ParseError, match="requires 196249 elements"):
      FullMatrix(list(range(196248)), size=443)  # One short!

  def test_zero_dimension_edge_case(self) -> None:
    """
    WHAT: Test edge case of zero dimension
    WHY: Ensure validation handles degenerate cases
    EXPECTED: ParseError or successful empty matrix
    DATA: Empty matrix
    """
    # Zero dimension should need 0 elements
    numbers = []
    matrix = FullMatrix(numbers, size=0)
    assert matrix.size == 0
    assert len(matrix.numbers) == 0

  def test_dimension_one_edge_case(self) -> None:
    """s
    WHAT: Test edge case of 1x1 matrix
    WHY: Ensure formulas work for smallest valid matrix
    EXPECTED: Correct element counts
    DATA: Single-element matrix
    """
    # Full 1x1 needs 1 element
    matrix_full = FullMatrix([1], size=1)
    assert len(matrix_full.numbers) == 1

    # Lower diag 1x1 needs 1 element (just diagonal)
    matrix_lower_diag = LowerDiagRow([1], size=1)
    assert len(matrix_lower_diag.numbers) == 1

    # Lower row 1x1 needs 0 elements (no off-diagonal)
    matrix_lower = LowerRow([], size=1)
    assert len(matrix_lower.numbers) == 0


class TestMatrixValidationErrorMessages:
  """Test that validation error messages are helpful."""

  def test_error_includes_matrix_type(self) -> None:
    """Verify error message identifies which matrix type failed."""
    with pytest.raises(ParseError, match="LowerDiagRow") as exc_info:
      LowerDiagRow([1, 2, 3], size=3)

    assert "LowerDiagRow" in str(exc_info.value)

  def test_error_includes_expected_and_actual(self) -> None:
    """Verify error message shows both expected and actual counts."""
    with pytest.raises(ParseError, match="UpperRow with dimension 4") as exc_info:
      UpperRow([1, 2, 3, 4, 5], size=4)  # Needs 6, got 5

    error_msg = str(exc_info.value)
    assert "requires 6" in error_msg
    assert "got 5" in error_msg

  def test_error_includes_dimension(self) -> None:
    """Verify error message shows the dimension."""
    with pytest.raises(ParseError, match="dimension 2 requires 4") as exc_info:
      FullMatrix([1, 2, 3], size=2)

    assert "dimension 2" in str(exc_info.value)


def _read_full_matrix_section(path: Path) -> list[int]:
  """Return the integers of a FULL_MATRIX EDGE_WEIGHT_SECTION, in file order."""
  lines: list[str] = path.read_text(encoding="utf-8", errors="replace").splitlines()
  start: int = next(index for index, line in enumerate(lines) if line.strip().startswith("EDGE_WEIGHT_SECTION"))

  values: list[int] = []
  for line in lines[start + 1 :]:
    stripped: str = line.strip()
    if not stripped:
      continue
    if any(character.isalpha() for character in stripped):
      break
    values.extend(int(token) for token in stripped.split())
  return values
