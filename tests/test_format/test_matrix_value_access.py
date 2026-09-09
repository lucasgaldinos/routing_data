"""Tests for matrix value access correctness.

WHAT: Verify that Matrix.__getitem__ returns correct values for all 9 formats
WHY: Ensure matrix indexing logic (get_index, _fix_indices) works correctly
HOW: Create matrices with known values and verify specific element access

This addresses Task 8: Matrix Conversion Verification
- Tests all 9 EDGE_WEIGHT_FORMAT types
- Uses 4x4 test matrix with distinct values to catch indexing bugs
- Verifies diagonal handling and symmetry logic

Author: AI Assistant
Date: 2025-10-27
"""

import pytest

from tsplib_parser.matrix import (
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


class TestMatrixValueAccess:
  """Test that matrix value access returns correct elements.

  Test Matrix (4x4) - using distinct values to catch indexing errors:

    col:  0   1   2   3
  row 0:  0   1   2   3
  row 1: 10  11  12  13
  row 2: 20  21  22  23
  row 3: 30  31  32  33

  Each format stores a subset of these values.
  """

  def test_full_matrix_value_access(self) -> None:
    """
    WHAT: Test FullMatrix returns correct values for all positions
    WHY: Verify row-major indexing (index = i*size + j)
    EXPECTED: All 16 values accessible correctly
    DATA: 4x4 full matrix [0,1,2,3,10,11,12,13,20,21,22,23,30,31,32,33]
    """
    numbers: list[int] = [0, 1, 2, 3, 10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33]
    matrix = FullMatrix(numbers, size=4)

    # Test diagonal
    assert matrix[0, 0] == 0
    assert matrix[1, 1] == 11
    assert matrix[2, 2] == 22
    assert matrix[3, 3] == 33

    # Test upper triangle
    assert matrix[0, 1] == 1
    assert matrix[0, 3] == 3
    assert matrix[1, 2] == 12
    assert matrix[2, 3] == 23

    # Test lower triangle
    assert matrix[1, 0] == 10
    assert matrix[2, 0] == 20
    assert matrix[2, 1] == 21
    assert matrix[3, 2] == 32

  def test_lower_diag_row_value_access(self) -> None:
    """
    WHAT: Test LowerDiagRow returns correct values for lower triangle + diagonal
    WHY: Verify lower triangle indexing with diagonal included
    EXPECTED: Diagonal and lower accessible, upper returns symmetric values
    DATA: [0, 10,11, 20,21,22, 30,31,32,33] (10 elements)

    Layout:
    0
    10 11
    20 21 22
    30 31 32 33
    """
    numbers = [
      0,  # row 0: diagonal
      10,
      11,  # row 1: lower + diagonal
      20,
      21,
      22,  # row 2: lower + diagonal
      30,
      31,
      32,
      33,  # row 3: lower + diagonal
    ]
    matrix = LowerDiagRow(numbers, size=4)

    # Test diagonal
    assert matrix[0, 0] == 0
    assert matrix[1, 1] == 11
    assert matrix[2, 2] == 22
    assert matrix[3, 3] == 33

    # Test lower triangle
    assert matrix[1, 0] == 10
    assert matrix[2, 0] == 20
    assert matrix[2, 1] == 21
    assert matrix[3, 0] == 30
    assert matrix[3, 2] == 32

    # Test upper triangle (should return symmetric lower values)
    assert matrix[0, 1] == 10  # symmetric to [1,0]
    assert matrix[0, 2] == 20  # symmetric to [2,0]
    assert matrix[1, 2] == 21  # symmetric to [2,1]

  def test_lower_row_value_access(self) -> None:
    """
    WHAT: Test LowerRow returns correct values for lower triangle without diagonal
    WHY: Verify lower triangle indexing with diagonal excluded (returns 0)
    EXPECTED: Lower triangle accessible, diagonal returns 0, upper symmetric
    DATA: [10, 20,21, 30,31,32] (6 elements)

    Layout:
    _
    10 _
    20 21 _
    30 31 32 _
    """
    numbers: list[int] = [
      10,  # row 1: [10]
      20,
      21,  # row 2: [20, 21]
      30,
      31,
      32,  # row 3: [30, 31, 32]
    ]
    matrix = LowerRow(numbers, size=4)

    # Test diagonal (should return 0 for non-diagonal format)
    assert matrix[0, 0] == 0
    assert matrix[1, 1] == 0
    assert matrix[2, 2] == 0
    assert matrix[3, 3] == 0

    # Test lower triangle
    assert matrix[1, 0] == 10
    assert matrix[2, 0] == 20
    assert matrix[2, 1] == 21
    assert matrix[3, 0] == 30
    assert matrix[3, 1] == 31
    assert matrix[3, 2] == 32

    # Test upper triangle (symmetric)
    assert matrix[0, 1] == 10
    assert matrix[0, 2] == 20
    assert matrix[1, 3] == 31

  def test_upper_diag_row_value_access(self) -> None:
    """
    WHAT: Test UpperDiagRow returns correct values for upper triangle + diagonal
    WHY: Verify upper triangle indexing with diagonal included
    EXPECTED: Diagonal and upper accessible, lower returns symmetric values
    DATA: [0,1,2,3, 11,12,13, 22,23, 33] (10 elements)

    Layout:
    0  1  2  3
       11 12 13
          22 23
             33
    """
    numbers = [
      0,
      1,
      2,
      3,  # row 0: diagonal + upper
      11,
      12,
      13,  # row 1: diagonal + upper
      22,
      23,  # row 2: diagonal + upper
      33,  # row 3: diagonal
    ]
    matrix = UpperDiagRow(numbers, size=4)

    # Test diagonal
    assert matrix[0, 0] == 0
    assert matrix[1, 1] == 11
    assert matrix[2, 2] == 22
    assert matrix[3, 3] == 33

    # Test upper triangle
    assert matrix[0, 1] == 1
    assert matrix[0, 2] == 2
    assert matrix[0, 3] == 3
    assert matrix[1, 2] == 12
    assert matrix[1, 3] == 13
    assert matrix[2, 3] == 23

    # Test lower triangle (should return symmetric upper values)
    assert matrix[1, 0] == 1  # symmetric to [0,1]
    assert matrix[2, 0] == 2  # symmetric to [0,2]
    assert matrix[3, 1] == 13  # symmetric to [1,3]

  def test_upper_row_value_access(self) -> None:
    """
    WHAT: Test UpperRow returns correct values for upper triangle without diagonal
    WHY: Verify upper triangle indexing with diagonal excluded (returns 0)
    EXPECTED: Upper triangle accessible, diagonal returns 0, lower symmetric
    DATA: [1,2,3, 12,13, 23] (6 elements)

    Layout:
    _  1  2  3
       _ 12 13
          _ 23
            _
    """
    numbers = [
      1,
      2,
      3,  # row 0: [1, 2, 3]
      12,
      13,  # row 1: [12, 13]
      23,  # row 2: [23]
    ]
    matrix = UpperRow(numbers, size=4)

    # Test diagonal (should return 0)
    assert matrix[0, 0] == 0
    assert matrix[1, 1] == 0
    assert matrix[2, 2] == 0
    assert matrix[3, 3] == 0

    # Test upper triangle
    assert matrix[0, 1] == 1
    assert matrix[0, 2] == 2
    assert matrix[0, 3] == 3
    assert matrix[1, 2] == 12
    assert matrix[1, 3] == 13
    assert matrix[2, 3] == 23

    # Test lower triangle (symmetric)
    assert matrix[1, 0] == 1
    assert matrix[2, 0] == 2
    assert matrix[3, 2] == 23

  def test_upper_col_equals_lower_row_logic(self) -> None:
    """
    WHAT: Test that UpperCol uses same logic as LowerRow (column/row duality)
    WHY: UpperCol inherits from LowerRow - verify this produces correct results
    EXPECTED: Same values accessible, representing column-wise storage
    DATA: Same as LowerRow test

    NOTE: UpperCol reads data column-wise, but the indexing produces
    the same matrix as LowerRow read row-wise (just transposed input order)
    """
    numbers = [10, 20, 21, 30, 31, 32]
    matrix = UpperCol(numbers, size=4)

    # Should behave identically to LowerRow
    assert matrix[0, 0] == 0  # diagonal
    assert matrix[1, 0] == 10
    assert matrix[2, 1] == 21
    assert matrix[3, 2] == 32

  def test_lower_col_equals_upper_row_logic(self) -> None:
    """
    WHAT: Test that LowerCol uses same logic as UpperRow (column/row duality)
    WHY: LowerCol inherits from UpperRow - verify this produces correct results
    EXPECTED: Same values accessible, representing column-wise storage
    DATA: Same as UpperRow test
    """
    numbers = [1, 2, 3, 12, 13, 23]
    matrix = LowerCol(numbers, size=4)

    # Should behave identically to UpperRow
    assert matrix[0, 0] == 0  # diagonal
    assert matrix[0, 1] == 1
    assert matrix[1, 2] == 12
    assert matrix[2, 3] == 23

  def test_upper_diag_col_equals_lower_diag_row_logic(self) -> None:
    """
    WHAT: Test that UpperDiagCol uses same logic as LowerDiagRow
    WHY: UpperDiagCol inherits from LowerDiagRow - verify duality
    EXPECTED: Same values accessible
    DATA: Same as LowerDiagRow test
    """
    numbers = [0, 10, 11, 20, 21, 22, 30, 31, 32, 33]
    matrix = UpperDiagCol(numbers, size=4)

    # Should behave identically to LowerDiagRow
    assert matrix[0, 0] == 0
    assert matrix[1, 0] == 10
    assert matrix[2, 2] == 22
    assert matrix[3, 2] == 32

  def test_lower_diag_col_equals_upper_diag_row_logic(self) -> None:
    """
    WHAT: Test that LowerDiagCol uses same logic as UpperDiagRow
    WHY: LowerDiagCol inherits from UpperDiagRow - verify duality
    EXPECTED: Same values accessible
    DATA: Same as UpperDiagRow test
    """
    numbers = [0, 1, 2, 3, 11, 12, 13, 22, 23, 33]
    matrix = LowerDiagCol(numbers, size=4)

    # Should behave identically to UpperDiagRow
    assert matrix[0, 0] == 0
    assert matrix[0, 1] == 1
    assert matrix[1, 2] == 12
    assert matrix[2, 3] == 23


class TestMatrixBoundaryConditions:
  """Test edge cases and boundary conditions."""

  def test_matrix_1x1(self) -> None:
    """Test 1x1 matrix (smallest valid matrix)."""
    # FullMatrix 1x1
    matrix = FullMatrix([42], size=1)
    assert matrix[0, 0] == 42

    # LowerDiagRow 1x1 (just diagonal)
    matrix = LowerDiagRow([42], size=1)
    assert matrix[0, 0] == 42

    # LowerRow 1x1 (no elements, diagonal excluded)
    matrix = LowerRow([], size=1)
    assert matrix[0, 0] == 0  # diagonal not included

  def test_matrix_index_bounds(self) -> None:
    """Test that out-of-bounds access raises IndexError."""
    numbers = [0, 1, 2, 3, 10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33]
    matrix = FullMatrix(numbers, size=4)

    # Valid access
    assert matrix[0, 0] == 0
    assert matrix[3, 3] == 33

    # Out of bounds should raise IndexError
    with pytest.raises(IndexError):
      _ = matrix[4, 0]

    with pytest.raises(IndexError):
      _ = matrix[0, 4]

    with pytest.raises(IndexError):
      _ = matrix[-1, 0]  # negative indices not allowed

  def test_get_index_formulas(self) -> None:
    """
    WHAT: Verify get_index() formulas return correct linear indices
    WHY: Ensure mathematical formulas for triangular matrices are correct
    EXPECTED: Correct indices for all formats
    DATA: Small 3x3 and 4x4 matrices
    """
    # FullMatrix: index = i*size + j
    matrix = FullMatrix([0] * 16, size=4)
    assert matrix.get_index(0, 0) == 0
    assert matrix.get_index(0, 3) == 3
    assert matrix.get_index(1, 0) == 4
    assert matrix.get_index(3, 3) == 15

    # LowerDiagRow: index = integer_sum(i) + j
    # Row 0: 0
    # Row 1: 1, 2
    # Row 2: 3, 4, 5
    # Row 3: 6, 7, 8, 9
    matrix = LowerDiagRow([0] * 10, size=4)
    assert matrix.get_index(0, 0) == 0  # integer_sum(0) + 0 = 0
    assert matrix.get_index(1, 0) == 1  # integer_sum(1) + 0 = 1
    assert matrix.get_index(1, 1) == 2  # integer_sum(1) + 1 = 2
    assert matrix.get_index(2, 0) == 3  # integer_sum(2) + 0 = 3
    assert matrix.get_index(3, 3) == 9  # integer_sum(3) + 3 = 6+3 = 9

    # UpperDiagRow: more complex formula
    matrix = UpperDiagRow([0] * 10, size=4)
    assert matrix.get_index(0, 0) == 0
    assert matrix.get_index(0, 1) == 1
    assert matrix.get_index(1, 1) == 4
    assert matrix.get_index(2, 2) == 7
