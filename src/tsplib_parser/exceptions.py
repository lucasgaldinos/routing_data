"""
Clean exception hierarchy for TSPLIB95 format utilities.

Exception Hierarchy:
    FormatError (base)
    ├── ParseError (file reading/parsing issues)
    ├── ValidationError (invalid data)
    └── UnsupportedFeatureError (special distance functions, extensions)

Design Principles:
- Clear exception types for targeted error handling
- Base class allows catching all format-related errors
- Specific subclasses enable retry logic (e.g., retry ParseError, fail on UnsupportedFeatureError)
"""

__all__ = [
  "FormatError",
  "ParseError",
  "UnsupportedFeatureError",
  "ValidationError",
]


class FormatError(Exception):
  """
  Base exception for all TSPLIB format-related errors.

  Provides context wrapping and message amendment utilities.
  All format exceptions inherit from this base class.

  Examples
  --------
  >>> try:
  ...   parse_tsplib("broken.tsp")
  ... except FormatError as e:
  ...   print(f"Format error: {e}")
  """

  @classmethod
  def wrap(cls, exc: Exception, message: str) -> "FormatError":
    """
    Wrap an existing exception with additional context.

    Parameters
    ----------
    exc : Exception
        Original exception to wrap
    message : str
        Context message to prepend

    Returns
    -------
    FormatError
        New exception with combined message
    """
    if exc.args and exc.args[0]:
      message = f"{message}: {exc.args[0]}"
    return cls(message, *exc.args[1:])

  def amend(self, message: str) -> "FormatError":
    """
    Amend this exception with additional context.

    Parameters
    ----------
    message : str
        Context message to prepend

    Returns
    -------
    FormatError
        New exception with combined message
    """
    return self.__class__.wrap(self, message)


class ParseError(FormatError, ValueError):
  """
  Exception raised when TSPLIB file cannot be parsed.

  Use Cases:
  - File doesn't exist
  - File is not readable
  - Invalid TSPLIB format/syntax
  - Encoding issues

  Examples
  --------
  >>> if not file.exists():
  ...   raise ParseError(f"File not found: {filepath}")
  """

  pass


class ValidationError(FormatError):
  """
  Exception raised when parsed data fails validation.

  Use Cases:
  - Missing required fields (NAME, TYPE, DIMENSION)
  - Invalid field values (negative dimension, unknown type)
  - Inconsistent data (node count != dimension)

  Examples
  --------
  >>> if dimension <= 0:
  ...   raise ValidationError(f"Invalid dimension: {dimension}")
  """

  pass


class UnsupportedFeatureError(FormatError):
  """
  Exception raised for unsupported TSPLIB features.

  Use Cases:
  - SPECIAL distance types without custom function
  - Unimplemented edge weight formats
  - Extended VRP features not yet supported

  Examples
  --------
  >>> if edge_type == "SPECIAL" and not special_func:
  ...   raise UnsupportedFeatureError("SPECIAL distance requires custom function")
  """

  pass
