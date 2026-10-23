"""Text transformers for TSPLIB95 and LKH-3 data deserialization.

This module provides bidirectional separators and transformer classes that convert raw
text sections and scalar values into strongly typed Python structures (integers,
floats, adjacency lists, coordinate lists, and key-value maps).
"""

import logging
from collections.abc import Callable
from typing import Any, cast

from . import exceptions

logger: logging.Logger = logging.getLogger(__name__)


class BiSep:
  """Bidirectional separator for parsing."""

  def __init__(self, *, in_: str | None = None, out: str = " ") -> None:
    self.i: str | None = in_
    self.o: str = out

  @classmethod
  def from_value(cls, value: str | tuple[str | None, str] | None) -> "BiSep":
    """Normalize a separator declaration into a BiSep instance.

    Accepts ``None`` (split on any whitespace), a plain separator string, or
    an ``(in, out)`` tuple where ``in`` splits text and ``out`` joins it.
    """
    if value is None or isinstance(value, str):
      i: str | None = value
      o: str = value if value is not None else " "
    else:
      try:
        i, o = value
      except Exception:
        raise ValueError(f"must be a string or an in/out tuple, not {value}") from None
    return cls(in_=i, out=o)

  def split(self, text: str, maxsplit: int | None = None) -> list[str]:
    maxsplit_val: int = -1 if maxsplit is None else maxsplit
    return text.split(self.i, maxsplit=maxsplit_val)

  def join(self, items: list[str]) -> str:
    # self.o is never None (always has default ' '), but keep defensive check
    o: str = " " if not self.o else self.o
    return o.join(items)


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


class Transformer[T]:
  """Base transformer class for parsing text into structured data.

  Transformers convert text into values. Validating the *parsed model* is the
  job of ``tsplib_parser.validation.validate_problem_data``; there is
  deliberately no ``validate`` hook here, because a no-op implementation made
  ``Field.validate`` look like real validation while never failing.
  """

  def parse(self, text: str) -> T:
    """Parse text into a value."""
    raise NotImplementedError()


class FuncT[T](Transformer[T]):
  """Transformer that applies a function to parse text."""

  def __init__(self, *, func: Callable[[str], T] | None = None) -> None:
    # Default is a no-op pass-through, only sound when T is str; cast needed
    # because the identity lambda cannot be expressed as returning an arbitrary T.
    self.func: Callable[[str], T] = func or cast("Callable[[str], T]", lambda x: x)

  def parse(self, text: str) -> T:
    # Only ValueError/TypeError are data problems - exactly what int(), float()
    # and str() raise on malformed text. Any other exception is a real bug in
    # ``func`` and must propagate unmasked rather than be blamed on the file.
    try:
      return self.func(text)
    except (ValueError, TypeError) as e:
      # ``functools.partial`` objects and callable instances have no
      # ``__name__``; falling back to the type name avoids raising
      # AttributeError inside the error handler and masking the real failure.
      name: str = getattr(self.func, "__name__", type(self.func).__name__)
      error: str = f"could not apply {name} to {text}: {e}"
      raise exceptions.ParseError(error) from e


class NumberT(Transformer[int | float]):
  """Transformer for any number, int or float."""

  def parse(self, text: str) -> int | float:
    # int() first, float() second: int("12.5") legitimately fails, so that
    # ValueError is control flow, not an error. Only when BOTH fail is the text
    # not a number. Report the offending text and chain the last conversion
    # failure so the root cause survives (same contract as FuncT.parse).
    last_error: ValueError | None = None
    for func in (int, float):
      try:
        return func(text)
      except ValueError as e:
        last_error = e
    raise exceptions.ParseError(f"could not convert text to number: {text}") from last_error


class EdgeDataT(Transformer[list[list[int]]]):
  """Transformer for TSPLIB graph edge data (EDGE_LIST or ADJ_LIST).

  Honors the declared ``EDGE_DATA_FORMAT`` when provided, or sniffs the layout
  when ``edge_data_format`` is ``None`` (for example, before a trailing
  ``EDGE_DATA_FORMAT`` keyword is reached). Supports both the colon-separated
  ``<v>: <w1> <w2> ... -1`` form and the TSPLIB95 §1.2.4 colon-less
  ``<v> <w1> <w2> ... -1`` form for ``ADJ_LIST``.

  Output is a flat list of 1-based ``[from, to]`` pairs for BOTH layouts.
  Any line that cannot yield valid integer edges raises ``ParseError``.
  """

  def parse(self, text: str, edge_data_format: str | None = None) -> list[list[int]]:
    text = text.strip()
    if not text:
      return []
    lines: list[str] = [ln.strip() for ln in text.split("\n") if ln.strip() and ln.strip() != "-1"]
    if not lines:
      return []
    fmt: str | None = edge_data_format.strip().upper() if edge_data_format else None
    if fmt == "ADJ_LIST":
      return self._parse_adj_list(lines)
    if fmt == "EDGE_LIST":
      return self._parse_edge_list(lines)
    if fmt is not None:
      raise exceptions.ParseError(f"Unsupported EDGE_DATA_FORMAT: {edge_data_format!r}")
    if any(":" in ln for ln in lines) or any(len(ln.split()) >= 3 and ln.split()[-1] == "-1" for ln in lines):
      return self._parse_adj_list(lines)
    return self._parse_edge_list(lines)

  def _parse_edge_list(self, lines: list[str]) -> list[list[int]]:
    """Parse ``<from> <to>`` lines. Extra tokens beyond the pair are rejected."""
    edges: list[list[int]] = []
    for line in lines:
      parts: list[str] = line.split()
      if len(parts) != 2:
        raise exceptions.ParseError(f'EDGE_LIST: expected "<from> <to>", got {line!r}')
      try:
        edges.append([int(parts[0]), int(parts[1])])
      except ValueError:
        raise exceptions.ParseError(f"EDGE_LIST: non-integer edge endpoint in {line!r}") from None
    return edges

  def _parse_adj_list(self, lines: list[str]) -> list[list[int]]:
    """Parse ``<v>: <w1> <w2> ... -1`` or ``<v> <w1> <w2> ... -1`` lines into ``[from, to]`` pairs."""
    edges: list[list[int]] = []
    for line in lines:
      if ":" in line:
        from_part, to_part = line.split(":", 1)
        try:
          source: int = int(from_part.strip())
        except ValueError:
          raise exceptions.ParseError(f"ADJ_LIST: bad source node in {line!r}") from None
        neighbor_tokens: list[str] = to_part.split()
      else:
        tokens: list[str] = line.split()
        if len(tokens) < 2 or tokens[-1] != "-1":
          raise exceptions.ParseError(f"ADJ_LIST: line must be '<v>: <w1> ...' or '<v> <w1> ... -1', got {line!r}")
        try:
          source = int(tokens[0])
        except ValueError:
          raise exceptions.ParseError(f"ADJ_LIST: bad source node in {line!r}") from None
        neighbor_tokens = tokens[1:]

      for neighbor in neighbor_tokens:
        if neighbor == "-1":
          continue
        try:
          edges.append([source, int(neighbor)])
        except ValueError:
          raise exceptions.ParseError(f"ADJ_LIST: bad neighbor {neighbor!r} in {line!r}") from None
    return edges


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
    self.sep: BiSep = BiSep.from_value(sep)
    self.terminal: str | None = terminal
    self.terminal_required: bool = terminal_required
    self.size: int | None = size
    self.filter_empty: bool = filter_empty

  def _split_items(self, text: str) -> list[str]:
    """Strip text, enforce/remove the terminal sentinel, and split into items.

    Shared by ContainerT and MapT so the section prologue (whitespace, the
    ``-1``-style terminal rule, and the separator) lives in exactly one place.
    """
    # start without unpredictable whitespace
    text = text.strip()

    # if we have a terminal, make sure it's there and remove it
    if self.terminal:
      if not text.endswith(self.terminal) and self.terminal_required:
        raise exceptions.ParseError(f'must end with {self.terminal}, not "{text[-len(self.terminal) :]}"')
      text = text[: -len(self.terminal)].strip()

    # split text into raw items
    if self.sep.i is None:
      return text.split()
    return self.sep.split(text)

  def parse(self, text: str) -> T_Container:
    """Parse the text into a container of items."""
    items: list[str] = self._split_items(text)

    # Parse each non-empty item with the child transformer. Failures are tagged
    # with their 1-based position in the source block (line numbers for a "\n"
    # separator, token numbers for a whitespace separator) so the aggregated
    # error can point at the exact offending row. Empty items are skipped here
    # (not pre-filtered) so numbering still matches the source text.
    errors: list[str] = []
    parsed_items: list[Any] = []
    for index, item in enumerate(items, start=1):
      if self.filter_empty and not item:
        continue
      try:
        parsed_items.append(self.child_tf.parse(item))
      except exceptions.ParseError as e:
        errors.append(f"item {index}: {e}")

    # if there are errors, collect them
    if errors:
      error: str = _friendly_join(errors, limit=3)
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


class ListT(ContainerT[list[Any]]):
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
    self.kv_sep: BiSep = BiSep.from_value(kv_sep)

  def parse(self, text: str) -> dict[Any, Any]:
    items: list[str] = self._split_items(text)

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

      if key_parsed in data:
        # Last-wins would silently discard a row; a repeated key means the
        # section is corrupt, exactly like an unparsable one.
        errors.append(f'duplicate key "{key_parsed}" in "{item}"')
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


__all__: list[str] = [
  "BiSep",
  "ContainerT",
  "EdgeDataT",
  "FuncT",
  "ListT",
  "MapT",
  "NumberT",
  "Transformer",
  "_friendly_join",
]

