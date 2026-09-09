"""Matrix classes for TSPLIB95 EDGE_WEIGHT_SECTION parsing.

Provides matrix representations for different EDGE_WEIGHT_FORMAT types:
- FULL_MATRIX: Complete nxn matrix
- LOWER_DIAG_ROW: Lower triangle with diagonal
- LOWER_ROW: Lower triangle without diagonal
- UPPER_DIAG_ROW: Upper triangle with diagonal
- UPPER_ROW: Upper triangle without diagonal
- Column variants: LOWER_COL, UPPER_COL, LOWER_DIAG_COL, UPPER_DIAG_COL

"""

from collections.abc import Sequence

from . import exceptions

_INT_SUM_MEMO: dict[int, int] = {}


def _int_sum(n: int, memo: dict[int, int] = _INT_SUM_MEMO) -> int:
  """Compute sum of integers from 0 to n (triangular number).

  Uses memoization for performance.

  Args:
      n: Upper bound for sum
      memo: Memoization cache

  Returns:
      Sum 0 + 1 + 2 + ... + n
  """
  if n not in memo:
    s = n * (n + 1) // 2
    memo[n] = s
  return memo[n]


def integer_sum(n: int, m: int | None = None) -> int:
  """Compute sum of integers from 0 to n, optionally minus sum from 0 to m.

  Args:
      n: Upper bound for sum
      m: Optional lower bound to subtract

  Returns:
      Sum 0..n or (0..n) - (0..m)
  """
  s = _int_sum(n)
  if m:
    s -= _int_sum(m)
  return s


class Matrix:
  """A square matrix created from a list of numbers.

  Elements are accessible using matrix notation. Negative indexing is not
  allowed.

  Args:
      numbers: The elements of the matrix (flattened list)
      size: The width (also height) of the matrix
      min_index: The minimum index (default 0)

  Raises:
      ParseError: If the number of elements doesn't match the expected size
  """

  def __init__(self, numbers: Sequence[int | float], size: int, min_index: int = 0) -> None:
    """Initialize matrix from flattened list of numbers.

    Validates that the number of elements matches the expected size
    for this matrix format before storing.
    """
    # Validate dimension matches expected size
    expected_size = self._calculate_expected_size(size)
    actual_size = len(numbers)

    if actual_size != expected_size:
      matrix_type = self.__class__.__name__
      raise exceptions.ParseError(
        f"{matrix_type} with dimension {size} requires {expected_size} elements, but got {actual_size}"
      )

    self.numbers = list(numbers)
    self.size = size
    self.min_index = min_index

  @classmethod
  def _calculate_expected_size(cls, dimension: int) -> int:
    """Calculate the expected number of elements for this matrix format.

    Args:
        dimension: The matrix dimension (n for nxn matrix)

    Returns:
        Expected number of elements in the flattened matrix
    """
    # Default for base Matrix class (should be overridden by subclasses)
    return dimension * dimension

  def __getitem__(self, key: tuple[int, int]) -> int | float:
    """Get element at [i, j]."""
    return self.value_at(*key)

  def value_at(self, i: int, j: int) -> int | float:
    """Get the element at row i and column j.

    Args:
        i: Row index
        j: Column index

    Returns:
        Value of element at (i,j)

    Raises:
        IndexError: If (i,j) is out of bounds
    """
    i -= self.min_index
    j -= self.min_index
    if not self.is_valid_row_column(i, j):
      raise IndexError(f"({i}, {j}) is out of bounds")
    index = self.get_index(i, j)
    return self.numbers[index]

  def is_valid_row_column(self, i: int, j: int) -> bool:
    """Return True if (i,j) is a row and column within the matrix.

    Args:
        i: Row index
        j: Column index

    Returns:
        Whether (i,j) is within the bounds of the matrix
    """
    return 0 <= i < self.size and 0 <= j < self.size

  def get_index(self, i: int, j: int) -> int:
    """Return the linear index for the element at (i,j).

    Must be implemented by subclasses.

    Args:
        i: Row index
        j: Column index

    Returns:
        Linear index for element (i,j)

    Raises:
        NotImplementedError: If not implemented by subclass
    """
    raise NotImplementedError()


class FullMatrix(Matrix):
  """A complete square matrix.

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  def get_index(self, i: int, j: int) -> int:
    """Return linear index for full matrix (row-major order)."""
    return i * self.size + j


class HalfMatrix(Matrix):
  """A triangular half-matrix.

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  #: True if the half-matrix includes the diagonal
  has_diagonal: bool = True

  @classmethod
  def _calculate_expected_size(cls, dimension: int) -> int:
    """Calculate expected size for triangular matrix.

    Args:
        dimension: The matrix dimension

    Returns:
        For diagonal included: n(n+1)/2
        For diagonal excluded: n(n-1)/2
    """
    if cls.has_diagonal:
      return dimension * (dimension + 1) // 2
    else:
      return dimension * (dimension - 1) // 2

  def value_at(self, i: int, j: int) -> int | float:
    """Get element, returning 0 for diagonal if not included."""
    if i == j and not self.has_diagonal:
      return 0
    i, j = self._fix_indices(i, j)
    return super().value_at(i, j)

  def _fix_indices(self, i: int, j: int) -> tuple[int, int]:
    """Fix indices to ensure they reference the correct triangle.

    Must be implemented by subclasses.

    Args:
        i: Row index
        j: Column index

    Returns:
        Fixed (i, j) tuple

    Raises:
        NotImplementedError: If not implemented by subclass
    """
    raise NotImplementedError()


class UpperDiagRow(HalfMatrix):
  """Upper-triangular matrix that includes the diagonal.

  Format example (3x3):
  1 2 3
    4 5
      6

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  has_diagonal = True

  def _fix_indices(self, i: int, j: int) -> tuple[int, int]:
    """Swap indices if accessing lower triangle (symmetry)."""
    i, j = (j, i) if i > j else (i, j)
    if not self.has_diagonal:
      j -= 1
    return i, j

  def get_index(self, i: int, j: int) -> int:
    """Return linear index for upper triangle row-wise storage."""
    n = self.size - int(not self.has_diagonal)
    return integer_sum(n, n - i) + (j - i)


class LowerDiagRow(HalfMatrix):
  """Lower-triangular matrix that includes the diagonal.

  Format example (3x3):
  1
  2 3
  4 5 6

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  has_diagonal = True

  def _fix_indices(self, i: int, j: int) -> tuple[int, int]:
    """Swap indices if accessing upper triangle (symmetry)."""
    i, j = (j, i) if i < j else (i, j)
    if not self.has_diagonal:
      i -= 1
    return i, j

  def get_index(self, i: int, j: int) -> int:
    """Return linear index for lower triangle row-wise storage."""
    return integer_sum(i) + j


class UpperRow(UpperDiagRow):
  """Upper-triangular matrix that does not include the diagonal.

  Format example (4x4):
  _ 1 2 3
    _ 4 5
      _ 6
        _

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  has_diagonal = False


class LowerRow(LowerDiagRow):
  """Lower-triangular matrix that does not include the diagonal.

  Format example (4x4):
  _
  1 _
  2 3 _
  4 5 6 _

  Args:
      numbers: The elements of the matrix
      size: The width (also height) of the matrix
      min_index: The minimum index
  """

  has_diagonal = False


class UpperCol(LowerRow):
  """Upper-triangular column-wise matrix without diagonal.

  Same as LowerRow but stored column-wise instead of row-wise.
  """

  pass


class LowerCol(UpperRow):
  """Lower-triangular column-wise matrix without diagonal.

  Same as UpperRow but stored column-wise instead of row-wise.
  """

  pass


class UpperDiagCol(LowerDiagRow):
  """Upper-triangular column-wise matrix with diagonal.

  Same as LowerDiagRow but stored column-wise instead of row-wise.
  """

  pass


class LowerDiagCol(UpperDiagRow):
  """Lower-triangular column-wise matrix with diagonal.

  Same as UpperDiagRow but stored column-wise instead of row-wise.
  """

  pass


#: Map of EDGE_WEIGHT_FORMAT names to matrix classes
TYPES: dict[str, type[Matrix]] = {
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
