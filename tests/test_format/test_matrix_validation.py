"""Tests for matrix dimension validation.

WHAT: Test that Matrix classes validate element count matches expected size
WHY: Prevent data corruption from malformed TSPLIB files
HOW: Create matrices with incorrect element counts and verify ParseError

Author: AI Assistant
Date: 2025-10-27
"""

import pytest

from tsplib_parser.exceptions import ParseError
from tsplib_parser.matrix import (
  FullMatrix,
  LowerCol,
  LowerDiagCol,
  LowerDiagRow,
  LowerRow,
  UpperCol,
  UpperDiagRow,
  UpperRow,
)


class TestMatrixDimensionValidation:
  """Test matrix dimension validation for all formats."""

  def test_full_matrix_correct_size(self):
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

  def test_full_matrix_incorrect_size(self):
    """
    WHAT: Create FullMatrix with wrong number of elements
    WHY: Verify validation catches dimension mismatch
    EXPECTED: ParseError with descriptive message
    DATA: 3x3 matrix with only 8 elements (needs 9)
    """
    numbers = list(range(1, 9))  # Only 8 elements

    with pytest.raises(ParseError) as exc_info:
      FullMatrix(numbers, size=3)

    error_msg = str(exc_info.value)
    assert "FullMatrix" in error_msg
    assert "dimension 3" in error_msg
    assert "requires 9" in error_msg
    assert "got 8" in error_msg

  def test_lower_row_correct_size(self):
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

  def test_lower_row_incorrect_size(self):
    """
    WHAT: Create LowerRow with wrong number of elements
    WHY: Detect common error of providing full matrix to triangular
    EXPECTED: ParseError with correct size calculation
    DATA: 10x10 lower triangle needs 45, given only 40
    """
    numbers = list(range(40))  # Only 40 elements

    with pytest.raises(ParseError) as exc_info:
      LowerRow(numbers, size=10)

    error_msg = str(exc_info.value)
    assert "LowerRow" in error_msg
    assert "dimension 10" in error_msg
    assert "requires 45" in error_msg  # 10*9/2 = 45
    assert "got 40" in error_msg

  def test_lower_diag_row_correct_size(self):
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

  def test_upper_row_correct_size(self):
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

  def test_upper_diag_row_correct_size(self):
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

  def test_column_variants_same_size_requirements(self):
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

  def test_large_matrix_size_calculation(self):
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
    with pytest.raises(ParseError):
      FullMatrix(list(range(196248)), size=443)  # One short!

  def test_zero_dimension_edge_case(self):
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

  def test_dimension_one_edge_case(self):
    """
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

  def test_error_includes_matrix_type(self):
    """Verify error message identifies which matrix type failed."""
    with pytest.raises(ParseError) as exc_info:
      LowerDiagRow([1, 2, 3], size=3)

    assert "LowerDiagRow" in str(exc_info.value)

  def test_error_includes_expected_and_actual(self):
    """Verify error message shows both expected and actual counts."""
    with pytest.raises(ParseError) as exc_info:
      UpperRow([1, 2, 3, 4, 5], size=4)  # Needs 6, got 5

    error_msg = str(exc_info.value)
    assert "requires 6" in error_msg
    assert "got 5" in error_msg

  def test_error_includes_dimension(self):
    """Verify error message shows the dimension."""
    with pytest.raises(ParseError) as exc_info:
      FullMatrix([1, 2, 3], size=2)

    assert "dimension 2" in str(exc_info.value)
