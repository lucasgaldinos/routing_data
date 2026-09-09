"""
Core TSPLIB95 parsing models and field system.

This module contains a standalone implementation of TSPLIB95 parsing, designed
specifically for database-oriented ETL pipelines. It provides a field-based
architecture for declarative problem specification parsing.

Architecture
------------
- **Field System**: Declarative fields (StringField, IntegerField, etc.) define TSPLIB95 keywords
- **Transformers**: Convert text to structured data (FuncT, listT, MapT, etc.)
- **StandardProblem**: Main problem class using fields to parse TSPLIB95 format
- **BiSep & Utils**: Bidirectional separator and utility functions for text processing

Key Classes
-----------
StandardProblem
    Main problem class with fields for all TSPLIB95 keywords.
    Uses `as_name_dict()` to export parsed data as dict.

Field (base class)
    Base for all field types. Fields are descriptors that parse and validate data.

TransformerField
    Field subclass that uses transformers for parsing.

Usage Note
----------
This is our standalone implementation using tsplib95 as a reference.
The converter primarily uses FormatParser (parser.py) which wraps these models.
Direct usage of StandardProblem is discouraged - use FormatParser instead.

Type Safety
-----------
This module has been enhanced with comprehensive type hints for improved
IDE support and static type checking with mypy/Pylance.
"""

import itertools
import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar

from . import exceptions, matrix

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# Minimal inline utilities (from bisep.py and utils.py)
# ============================================================================


class BiSep:
  """Bidirectional separator for parsing."""

  def __init__(self, *, in_: str | None = None, out: str = " ") -> None:
    self.i: str | None = in_
    self.o: str = out

  def split(self, text: str, maxsplit: int | None = None) -> list[str]:
    maxsplit_val: int = -1 if maxsplit is None else maxsplit
    return text.split(self.i, maxsplit=maxsplit_val)

  def join(self, items: list[str]) -> str:
    # self.o is never None (always has default ' '), but keep defensive check
    o: str = " " if not self.o else self.o
    return o.join(items)


def _bisep_from_value(value: str | tuple[str | None, str] | None) -> BiSep:
  """Create BiSep from value - inlined from bisep.py"""
  if value is None or isinstance(value, str):
    i: str | None = value
    o: str = value if value is not None else " "
  else:
    try:
      i, o = value
    except Exception:
      raise ValueError(f"must be a string or an in/out tuple, not {value}") from None
  return BiSep(in_=i, out=o)


def _friendly_join(items: list[str], limit: int | None = None) -> str:
  """Join items in a friendly way for error messages - inlined from utils.py"""
  if not items:
    return ""

  if limit is not None:
    truncated = len(items) - limit
    items_limited = items[:limit]
    if truncated > 0:
      items_limited.append(f"{truncated} more")
    items = items_limited

  *items_rest, last_item = items
  if not items_rest:
    return str(last_item)

  # oxford commas are important
  if len(items_rest) == 1:
    return f"{items_rest[0]} and {last_item}"
  return f"{', '.join(items_rest)}, and {last_item}"


# ============================================================================
# Minimal transformers (from transformers.py)
# ============================================================================

# Type variable for generic transformers
T = TypeVar("T")  # Generic output type for transformers


class Transformer[T]:
  """Base transformer class for parsing text into structured data."""

  def parse(self, text: str) -> T:
    """Parse text into a value."""
    raise NotImplementedError()

  def validate(self, value: T) -> None:
    """Validate a value."""
    pass


class FuncT(Transformer[T]):
  """Transformer that applies a function to parse text."""

  def __init__(self, *, func: Callable[[str], T] | None = None) -> None:
    self.func: Callable[[str], T] = func or (lambda x: x)

  def parse(self, text: str) -> T:
    try:
      return self.func(text)
    except Exception as e:
      error: str = f"could not apply {self.func.__name__} to {text}: {e}"
      raise exceptions.ParseError(error) from e


class NumberT(Transformer[int | float]):
  """Transformer for any number, int or float."""

  def parse(self, text: str) -> int | float:
    for func in (int, float):
      try:
        return func(text)
      except ValueError:
        pass
    error: str = f"could not convert text to number: {text}"
    raise exceptions.ParseError(error)


class ContainerT[T_Container](Transformer[T_Container]):
  """Base transformer for containers (lists, dicts)."""

  def __init__(
    self,
    *,
    value: Transformer[Any] | None = None,
    sep: str | tuple[str | None, str] | None = None,
    terminal: str | None = None,
    terminal_required: bool = True,
    size: int | None = None,
    filter_empty: bool = True,
  ) -> None:
    self.child_tf: Transformer[Any] = value or Transformer()
    self.sep: BiSep = _bisep_from_value(sep)
    self.terminal: str | None = terminal
    self.terminal_required: bool = terminal_required
    self.size: int | None = size
    self.filter_empty: bool = filter_empty

  def parse(self, text: str) -> T_Container:
    """Parse the text into a container of items."""
    # start without unpredictable whitespace
    text = text.strip()

    # if we have a terminal, make sure it's there and remove it
    if self.terminal:
      if not text.endswith(self.terminal) and self.terminal_required:
        raise exceptions.ParseError(f'must end with {self.terminal}, not "{text[-len(self.terminal) :]}"')
      text = text[: -len(self.terminal)].strip()

    # split text into raw items
    if self.sep.i is None:
      items: list[str] = text.split()
    else:
      items = self.sep.split(text)

    # filter out empty items if requested
    if self.filter_empty:
      items = [i for i in items if i]

    # parse each item using the child transformer
    errors: list[str] = []
    parsed_items: list[Any] = []
    for _, item in enumerate(items):
      try:
        parsed_items.append(self.child_tf.parse(item))
      except exceptions.ParseError as e:
        errors.append(str(e))

    # if there are errors, collect them
    if errors:
      error = _friendly_join(errors, limit=3)
      raise exceptions.ParseError(f"parsing errors: {error}")

    # check size requirements
    if self.size is not None and len(parsed_items) != self.size:
      raise exceptions.ParseError(f"expected {self.size} items, got {len(parsed_items)}")

    return self.pack(parsed_items)

  def pack(self, items: list[Any]) -> T_Container:
    """Pack items into final container."""
    raise NotImplementedError()

  def unpack(self, container: T_Container) -> list[Any]:
    """Unpack container into items."""
    raise NotImplementedError()


class listT(ContainerT[list[Any]]):
  """Transformer for a list of items."""

  def pack(self, items: list[Any]) -> list[Any]:
    return list(items)

  def unpack(self, container: list[Any]) -> list[Any]:
    return list(container)


class MapT(ContainerT[dict[Any, Any]]):
  """Transformer for a key-value mapping of items."""

  def __init__(
    self,
    *,
    key: Transformer[Any] | None = None,
    value: Transformer[Any] | None = None,
    kv_sep: str = "=",
    **kwargs: Any,
  ) -> None:
    super().__init__(value=value, **kwargs)
    self.key_tf: Transformer[Any] = key or Transformer()
    self.kv_sep: BiSep = _bisep_from_value(kv_sep)

  def parse(self, text: str) -> dict[Any, Any]:
    # start without unpredictable whitespace
    text = text.strip()

    # if we have a terminal, make sure it's there and remove it
    if self.terminal:
      if not text.endswith(self.terminal) and self.terminal_required:
        raise exceptions.ParseError(f'must end with {self.terminal}, not "{text[-len(self.terminal) :]}"')
      text = text[: -len(self.terminal)].strip()

    # split text into raw items
    if self.sep.i is None:
      items: list[str] = text.split()
    else:
      items = self.sep.split(text)

    # filter out empty items if requested
    if self.filter_empty:
      items = [i for i in items if i]

    # parse each item as a key-value pair
    data: dict[Any, Any] = {}
    errors: list[str] = []
    for item in items:
      if self.kv_sep.i is None:
        # no separator means key and value are the same
        raw_key: str = item
        raw_value: str = item
      elif self.kv_sep.i == " ":
        # Whitespace separator: split on ANY whitespace run (files in the
        # wild separate columns with spaces or tabs). str.split(maxsplit=1)
        # splits on runs of whitespace, so "1\t678\t543" and "1 678 543"
        # both parse to key="1", value="678 543".
        parts: list[str] = item.split(maxsplit=1)
        if len(parts) < 2:
          errors.append(f'item "{item}" is not a valid key-value pair')
          continue
        raw_key, raw_value = parts
      else:
        try:
          raw_key, raw_value = self.kv_sep.split(item, maxsplit=1)
        except ValueError:
          errors.append(f'item "{item}" is not a valid key-value pair')
          continue

      # parse the key and value
      try:
        key_parsed: Any = self.key_tf.parse(raw_key)
      except exceptions.ParseError as e:
        errors.append(f'bad key in "{item}": {e}')
        continue

      try:
        value_parsed: Any = self.child_tf.parse(raw_value)
      except exceptions.ParseError as e:
        errors.append(f'bad value in "{item}": {e}')
        continue

      data[key_parsed] = value_parsed

    # if there are errors, collect them
    if errors:
      error = _friendly_join(errors)
      raise exceptions.ParseError(f"parsing errors: {error}")

    # check size requirements
    if self.size is not None and len(data) != self.size:
      raise exceptions.ParseError(f"expected {self.size} items, got {len(data)}")

    return data

  def pack(self, items: list[tuple[Any, Any]]) -> dict[Any, Any]:
    return dict(items)

  def unpack(self, container: dict[Any, Any]) -> list[tuple[Any, Any]]:
    return list(container.items())


class EdgeDataT(Transformer[list[list[int]]]):
  """Transformer for TSPLIB graph edge data (EDGE_LIST or ADJ_LIST).

  The TSPLIB spec declares the layout via the ``EDGE_DATA_FORMAT`` keyword,
  but that keyword may legally appear AFTER the section. Rather than wait for
  it, the layout is sniffed from the data: adjacency-list lines contain a
  ``:`` after the source node ("5: 1 2"), plain edge lists never do.

  Output is a flat list of 1-based ``[from, to]`` pairs for BOTH layouts —
  the ETL stores edges as pairs, so the dict shape upstream tsplib95 uses for
  ADJ_LIST is not needed here.

  Any line that cannot yield an integer edge raises (no silent drops).
  """

  def parse(self, text: str) -> list[list[int]]:
    text = text.strip()
    if not text:
      return []
    lines: list[str] = [ln.strip() for ln in text.split("\n") if ln.strip() and ln.strip() != "-1"]
    if not lines:
      return []
    if any(":" in ln for ln in lines):
      return self._parse_adj_list(lines)
    return self._parse_edge_list(lines)

  def _parse_edge_list(self, lines: list[str]) -> list[list[int]]:
    """Parse ``<from> <to>`` lines. Extra tokens beyond the pair are ignored."""
    edges: list[list[int]] = []
    for line in lines:
      parts: list[str] = line.split()
      if len(parts) < 2:
        raise exceptions.ParseError(f'EDGE_LIST: expected "<from> <to>", got {line!r}')
      try:
        edges.append([int(parts[0]), int(parts[1])])
      except ValueError:
        raise exceptions.ParseError(f"EDGE_LIST: non-integer edge endpoint in {line!r}") from None
    return edges

  def _parse_adj_list(self, lines: list[str]) -> list[list[int]]:
    """Parse ``from: to1 to2 ... -1`` lines into ``[from, to]`` pairs."""
    edges: list[list[int]] = []
    for line in lines:
      if ":" not in line:
        raise exceptions.ParseError(f"ADJ_LIST: line missing ':' separator: {line!r}")
      from_part, to_part = line.split(":", 1)
      try:
        source: int = int(from_part.strip())
      except ValueError:
        raise exceptions.ParseError(f"ADJ_LIST: bad source node in {line!r}") from None
      for neighbor in to_part.split():
        if neighbor == "-1":
          continue
        try:
          edges.append([source, int(neighbor)])
        except ValueError:
          raise exceptions.ParseError(f"ADJ_LIST: bad neighbor {neighbor!r} in {line!r}") from None
    return edges


# ============================================================================
# Minimal fields (from fields.py)
# ============================================================================


class Field:
  """Base field class for TSPLIB95 problem descriptors."""

  default: Any | Callable[[], Any] | None = None

  def __init__(self, keyword: str, **options: Any) -> None:
    self.keyword: str = keyword
    self.name: str | None = None
    for key, value in options.items():
      setattr(self, key, value)

  def __set_name__(self, cls: type, name: str) -> None:
    if self.name is None:
      self.name = name

  def get_default_value(self) -> Any:
    """Get the default value for this field."""
    default: Any | Callable[[], Any] | None = self.default
    if callable(default):
      return default()
    return default

  def parse(self, text: str) -> Any:
    """Parse text into field value."""
    raise NotImplementedError()

  def validate(self, value: Any) -> None:
    """Validate a field value."""
    pass


class TransformerField(Field):
  """Field that uses a transformer for parsing."""

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)
    self.tf: Transformer[Any] = self.__class__.build_transformer()

  @classmethod
  def build_transformer(cls) -> Transformer[Any]:
    """Build the transformer for this field."""
    raise NotImplementedError()

  def parse(self, text: str) -> Any:
    """Parse text using the field's transformer."""
    return self.tf.parse(text)

  def validate(self, value: Any) -> None:
    """Validate using the field's transformer."""
    return self.tf.validate(value)


class StringField(TransformerField):
  """Simple string field."""

  @classmethod
  def build_transformer(cls) -> Transformer[str]:
    return FuncT(func=str)


class IntegerField(TransformerField):
  """Simple integer field."""

  default: int = 0

  @classmethod
  def build_transformer(cls) -> Transformer[int]:
    return FuncT(func=int)


class IndexedCoordinatesField(TransformerField):
  """Field for coordinates by index."""

  default: Callable[[], dict[Any, Any]] = dict

  def __init__(self, *args: Any, dimensions: int | tuple[int, ...] | None = None, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)
    self.dimensions: tuple[int, ...] | None = self._tuplize(dimensions)

  @staticmethod
  def _tuplize(dimensions: int | tuple[int, ...] | None) -> tuple[int, ...] | None:
    return (dimensions,) if isinstance(dimensions, int) else (dimensions if isinstance(dimensions, tuple) else None)

  @classmethod
  def build_transformer(cls) -> Transformer[dict[int, list[int | float]]]:
    key: FuncT[int] = FuncT(func=int)
    value: listT = listT(value=NumberT())
    return MapT(key=key, value=value, sep="\n", kv_sep=" ")

  def validate(self, value: dict[int, list[int | float]]) -> None:
    super().validate(value)
    cards = set(len(coord) for coord in value.values())
    if self.dimensions is not None and cards - set(self.dimensions):
      raise ValueError(f"wrong coordinate dimensions: {cards}")


class DepotsField(TransformerField):
  """Field for depots."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[int]]:
    depot: FuncT[int] = FuncT(func=int)
    return listT(value=depot, terminal="-1")


class DemandsField(TransformerField):
  """Field for demands."""

  default: Callable[[], dict[Any, Any]] = dict

  @classmethod
  def build_transformer(cls) -> Transformer[dict[int, int]]:
    node: FuncT[int] = FuncT(func=int)
    demand: FuncT[int] = FuncT(func=int)
    return MapT(key=node, value=demand, sep="\n", kv_sep=" ")


class MatrixField(TransformerField):
  """Field for a matrix of numbers (EDGE_WEIGHT_SECTION)."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[list[int | float]]]:
    row: listT = listT(value=NumberT())
    return listT(value=row, sep="\n")


class EdgeListField(TransformerField):
  """Field for a list of edges (``FIXED_EDGES_SECTION``)."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[list[int]]]:
    pair: listT = listT(value=FuncT(func=int), size=2)
    return listT(value=pair, sep="\n", terminal="-1")


class EdgeDataField(TransformerField):
  """Field for graph edge data (``EDGE_DATA_SECTION``).

  Parses both ``EDGE_LIST`` and ``ADJ_LIST`` layouts via content sniffing
  (see :class:`EdgeDataT`), so it is independent of ``EDGE_DATA_FORMAT``
  keyword ordering.
  """

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[list[int]]]:
    return EdgeDataT()


class ToursField(Field):
  """Field for one or more tours."""

  default: Callable[[], list[Any]] = list

  def __init__(self, *args: Any, require_terminal: bool = True) -> None:
    super().__init__(*args)
    self.terminal: str = "-1"
    self.require_terminal: bool = require_terminal
    self._end_terminals: re.Pattern[str] = re.compile(rf"(?:(?:\s+|\b|^){self.terminal})+$")
    self._any_terminal: re.Pattern[str] = re.compile(rf"(?:\s+|\b){self.terminal}(?:\b|\s+)")

  def parse(self, text: str) -> list[list[int]]:
    """Parse the text into a list of tours."""
    tours: list[list[int]] = []

    # remove any terminal at the end
    text = self._end_terminals.sub("", text).strip()
    if not text:
      return tours

    # split text on any terminal that's not at the end
    segments: list[str] = self._any_terminal.split(text)

    for segment in segments:
      if not segment.strip():
        continue
      tour: list[int] = []
      for city in segment.split():
        if city == self.terminal:
          break
        try:
          tour.append(int(city))
        except ValueError:
          raise exceptions.ParseError(f"bad city: {city}") from None
      if tour:
        tours.append(tour)

    return tours


# ============================================================================
# Minimal models (from models.py)
# ============================================================================


class FileMeta(type):
  """Metaclass that builds field mappings for Problem classes."""

  # Class attributes that will be added to Problem classes
  fields_by_name: dict[str, Field]
  fields_by_keyword: dict[str, Field]

  def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type:
    cls = super().__new__(mcs, name, bases, attrs)

    # collect fields from this class and all parent classes
    fields: dict[str, Field] = {}
    for klass in reversed(cls.__mro__):
      for key, value in vars(klass).items():
        if isinstance(value, Field):
          fields[key] = value

    # build name/keyword mappings
    cls.fields_by_name = fields
    cls.fields_by_keyword = {f.keyword: f for f in fields.values()}

    return cls


class Problem(metaclass=FileMeta):
  """Base problem class."""

  # Attributes added by metaclass
  fields_by_name: dict[str, Field]
  fields_by_keyword: dict[str, Field]

  def __init__(self, **kwargs: Any) -> None:
    for name, value in kwargs.items():
      setattr(self, name, value)

  def __getattribute__(self, name: str) -> Any:
    # check for a value like normal
    try:
      attrs: dict[str, Any] = object.__getattribute__(self, "__dict__")
      return attrs[name]
    except KeyError:
      pass

    # value missing, so try to return the default
    # for the corresponding field
    try:
      cls = object.__getattribute__(self, "__class__")
      field = cls.fields_by_name[name]
    except KeyError:
      # no field, so get the attribute normally (will raise AttributeError)
      return object.__getattribute__(self, name)
    else:
      return field.get_default_value()

  def as_dict(self, by_keyword: bool = False) -> dict[str, Any]:
    """Return the problem data as a dictionary."""
    data: dict[str, Any] = {}
    for name, field in self.__class__.fields_by_name.items():
      value = getattr(self, name)
      if name in self.__dict__ or value != field.get_default_value():
        key: str = field.keyword if by_keyword else name
        data[key] = value
    return data

  def as_name_dict(self) -> dict[str, Any]:
    """Return the problem data as a dictionary by field name."""
    return self.as_dict(by_keyword=False)

  def as_keyword_dict(self) -> dict[str, Any]:
    """Return the problem data as a dictionary by field keyword."""
    return self.as_dict(by_keyword=True)

  @classmethod
  def parse(cls, text: str, **options: Any) -> "Problem":
    """Parse text into a Problem instance."""
    problem = cls()

    # split text into sections
    for line in text.strip().split("\n"):
      line_stripped: str = line.strip()
      if not line_stripped or line_stripped.startswith("#"):
        continue

      # split on first colon
      if ":" in line_stripped:
        keyword_str, content_str = line_stripped.split(":", 1)
        keyword: str = keyword_str.strip()
        content: str = content_str.strip()

        # find the field for this keyword
        if keyword in cls.fields_by_keyword:
          field = cls.fields_by_keyword[keyword]
          try:
            value: Any = field.parse(content)
            if field.name:
              setattr(problem, field.name, value)
          except Exception as e:
            # Skip parsing errors for robustness
            logger.debug("Skipping parse error for keyword %s: %s", keyword, e)
      else:
        # section data - collect until we find next keyword or EOF
        keyword_section: str = line_stripped
        if keyword_section in cls.fields_by_keyword:
          # For section fields, we need to collect following lines
          # This is a simplified version - full parsing would require
          # more sophisticated section handling
          pass

    return problem


def _looks_like_keyword_header(line: str) -> bool:
  """Return True when ``line`` starts with an all-caps TSPLIB keyword + colon.

  Used to detect keyword lines that legally follow a data section without a
  ``*_SECTION`` boundary (e.g. ``FIXED_EDGES :`` in some HCP files). ADJ_LIST
  data lines like ``"5: 1 2"`` start with a numeric label and are not headers.
  """
  prefix: str = line.split(":", 1)[0].strip()
  return (
    bool(prefix) and any(c.isalpha() for c in prefix) and all(c.isupper() or c.isdigit() or c == "_" for c in prefix)
  )


def _fixed_inline_pairs(value: str, errors: list[str]) -> list[str]:
  """Split an inline ``FIXED_EDGES :`` value into ``'<from> <to>'`` pseudo-lines.

  The keyword value is a flat, ``-1``-terminated token stream of ``(from, to)``
  pairs; the pseudo-lines let it reuse the fixed-edge line parser.
  """
  tokens: list[str] = value.split()
  out: list[str] = []
  i: int = 0
  while i < len(tokens):
    if tokens[i] == "-1":
      i += 1
      break
    if i + 1 >= len(tokens):
      errors.append(f"FIXED_EDGES: dangling edge endpoint {tokens[i]!r} (missing '-1' terminator)")
      i += 1
      continue
    out.append(f"{tokens[i]} {tokens[i + 1]}")
    i += 2
  if i < len(tokens):
    errors.append(f"FIXED_EDGES: unexpected tokens after '-1': {tokens[i:]}")
  return out


class StandardProblem(Problem):
  """Standard TSPLIB95 problem with common fields."""

  # Basic metadata fields
  name = StringField("NAME")
  comment = StringField("COMMENT")
  problem_type = StringField("TYPE")  # Renamed from 'type' to avoid shadowing Python built-in
  dimension = IntegerField("DIMENSION")
  capacity = IntegerField("CAPACITY")
  node_coord_type = StringField("NODE_COORD_TYPE")
  edge_weight_type = StringField("EDGE_WEIGHT_TYPE")
  display_data_type = StringField("DISPLAY_DATA_TYPE")
  edge_weight_format = StringField("EDGE_WEIGHT_FORMAT")
  edge_data_format = StringField("EDGE_DATA_FORMAT")

  # Section data fields
  node_coords = IndexedCoordinatesField("NODE_COORD_SECTION", dimensions=(2, 3))
  edge_data = EdgeDataField("EDGE_DATA_SECTION")
  edge_weights = MatrixField("EDGE_WEIGHT_SECTION")
  display_data = IndexedCoordinatesField("DISPLAY_DATA_SECTION", dimensions=2)
  fixed_edges = EdgeListField("FIXED_EDGES_SECTION")
  depots = DepotsField("DEPOT_SECTION")
  demands = DemandsField("DEMAND_SECTION")
  tours = ToursField("TOUR_SECTION")

  @classmethod
  def parse(cls, text: str, **options: Any) -> "StandardProblem":
    """Parse TSPLIB95 format text into a StandardProblem.

    Single pass over the file lines. Known keywords and data sections whose
    content fails to parse are hard errors (aggregated and raised together at
    the end), never silently dropped. Unknown keywords are tolerated, as the
    spec allows extensions.

    ``EDGE_DATA_SECTION`` is parsed by a content-sniffing field (see
    ``EdgeDataField``), so it does not depend on the ``EDGE_DATA_FORMAT``
    keyword, which the spec allows to appear anywhere. Fixed edges may be
    declared as a ``FIXED_EDGES_SECTION`` or as the non-standard
    ``FIXED_EDGES :`` keyword form; both route into ``fixed_edges``.

    Raises
    ------
    ParseError
        When any known keyword or section content is unparsable.
    """
    problem = cls()
    current_section: str | None = None
    section_lines: list[str] = []
    errors: list[str] = []

    def close_section() -> None:
      """Finalize the section currently being collected."""
      nonlocal current_section, section_lines
      if not current_section:
        section_lines = []
        return
      if current_section in cls.fields_by_keyword:
        field = cls.fields_by_keyword[current_section]
        try:
          parsed_value_section: Any = field.parse("\n".join(section_lines))
          if field.name:
            setattr(problem, field.name, parsed_value_section)
        except Exception as e:
          errors.append(f"invalid {current_section}: {e}")
      current_section = None
      section_lines = []

    for line in text.split("\n"):
      line_stripped: str = line.strip()
      if not line_stripped:
        continue

      if ":" in line_stripped and not current_section:
        # Keyword line (only when not inside a data section).
        keyword_str, value_str = line_stripped.split(":", 1)
        keyword: str = keyword_str.strip()
        value: str = value_str.strip()

        if keyword in cls.fields_by_keyword:
          field = cls.fields_by_keyword[keyword]
          try:
            parsed_value: Any = field.parse(value)
            if field.name:
              setattr(problem, field.name, parsed_value)
          except Exception as e:
            errors.append(f"invalid value for {keyword}: {e}")
      elif line_stripped.endswith("_SECTION") or line_stripped == "EOF":
        # Section header / EOF: close the section being collected, then open
        # the new one (EOF opens nothing).
        close_section()
        current_section = line_stripped if line_stripped != "EOF" else None
        section_lines = []
      else:
        # Data line. A TSPLIB keyword may legally follow a data section
        # without a ``*_SECTION`` boundary (the ``FIXED_EDGES :`` form used
        # by some HCP files); such header lines terminate the section being
        # collected. ADJ_LIST data lines like "5: 1 2" have a numeric label
        # and are NOT treated as headers.
        if ":" in line_stripped and _looks_like_keyword_header(line_stripped):
          close_section()
          header_keyword, header_value = (part.strip() for part in line_stripped.split(":", 1))
          if header_keyword == "FIXED_EDGES":
            # Non-standard keyword whose value runs to a "-1". Reuse the
            # standard FIXED_EDGES_SECTION field for it: inline pairs seed
            # the section and following lines are collected until the next
            # header/EOF. A fully inline "-1"-terminated value parses now.
            current_section = "FIXED_EDGES_SECTION"
            section_lines = list(_fixed_inline_pairs(header_value, errors)) if header_value else []
            if header_value and header_value.split()[-1] == "-1":
              section_lines.append("-1")
              close_section()
              current_section = None
            continue
          if header_keyword in cls.fields_by_keyword:
            field = cls.fields_by_keyword[header_keyword]
            try:
              parsed_value_kw: Any = field.parse(header_value)
              if field.name:
                setattr(problem, field.name, parsed_value_kw)
            except Exception as e:
              errors.append(f"invalid value for {header_keyword}: {e}")
          # Unknown keyword extensions are tolerated (spec allows them).
          current_section = None
          section_lines = []
          continue
        # Data line inside the current section.
        section_lines.append(line_stripped)

    # Close any trailing section.
    close_section()

    if errors:
      raise exceptions.ParseError("TSPLIB parse errors: " + "; ".join(errors))
    return problem

  def create_explicit_matrix(self) -> matrix.Matrix | None:
    """Convert edge_weights list[list] to a Matrix object for EXPLICIT problems.

    ``DIMENSION`` is authoritative (TSPLIB spec): the flattened weight list
    must match the element count implied by ``EDGE_WEIGHT_FORMAT`` and
    ``DIMENSION``. Two real-world deviations from the core format are
    accommodated, both detected by element count and validated against
    ``DIMENSION`` rather than guessed:

    1. Some SOPLIB-derived files prepend a leading integer equal to
        ``DIMENSION`` to the ``EDGE_WEIGHT_SECTION`` (a non-conforming marker
        that never appears in the spec).
    2. Some VRP files store customer-only matrices (``DIMENSION`` includes
        the depot; the matrix does not).

    Any other element count raises a ParseError instead of silently
    truncating or padding.

    Returns:
        Matrix object if edge_weight_format is set, None otherwise
    """
    if not self.edge_weight_format or not self.edge_weights:
      return None

    fmt: str = getattr(self, "edge_weight_format", None) or ""
    weights_raw: Any = getattr(self, "edge_weights", None) or []
    dimension: int = int(getattr(self, "dimension", 0) or 0)
    problem_type: str = getattr(self, "problem_type", None) or ""

    MatrixClass: type[matrix.Matrix] | None = matrix.TYPES.get(fmt)
    if not MatrixClass:
      return None

    weights: list[int | float] = list(itertools.chain(*weights_raw))
    expected: int = MatrixClass._calculate_expected_size(dimension)
    actual_dimension: int = dimension

    # Deviation 1: leading DIMENSION marker (SOPLIB-derived files). Detected
    # by count (exactly one extra element) AND value (equal to DIMENSION),
    # so a conforming matrix is never touched.
    if len(weights) == expected + 1 and weights and int(weights[0]) == dimension:
      logger.info("Dropping leading DIMENSION marker (%s) from EDGE_WEIGHT_SECTION", weights[0])
      weights = weights[1:]

    # Deviation 2: customer-only CVRP/VRP matrix (depot excluded).
    if problem_type in ["CVRP", "VRP"]:
      expected_customers: int = MatrixClass._calculate_expected_size(dimension - 1)
      if len(weights) == expected_customers:
        actual_dimension = dimension - 1
        expected = expected_customers

    if len(weights) != expected:
      raise exceptions.ParseError(
        f"{fmt} matrix with dimension {dimension} requires {expected} "
        f"elements, but EDGE_WEIGHT_SECTION contains {len(weights)}"
      )

    return MatrixClass(weights, actual_dimension, min_index=0)
