"""Declarative field descriptors for TSPLIB95 and LKH-3 problem specifications.

This module provides descriptor classes (Field and its subclasses) representing
metadata headers (StringField, IntegerField, NumberField) and data sections
(IndexedCoordinatesField, MatrixField, DemandsField, EdgeListField, EdgeDataField,
ToursField).
"""

import re
from collections.abc import Callable
from typing import Any

from . import exceptions
from .transformers import (
  EdgeDataT,
  FuncT,
  ListT,
  MapT,
  NumberT,
  Transformer,
)


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

  def __get__(self, instance: Any, owner: type | None = None) -> Any:
    """Descriptor getter returning the descriptor on class access or the default value on instance access.

    When an attribute has been populated on the instance (e.g. by parser or assignment),
    Python's non-data descriptor lookup resolves instance.__dict__[name] before calling
    this method. This method is therefore only invoked when the instance attribute is
    unset, cleanly returning the field default.
    """
    if instance is None:
      return self
    return self.get_default_value()

  def get_default_value(self) -> Any:
    """Get the default value for this field."""
    default: Any | Callable[[], Any] | None = self.default
    if callable(default):
      return default()
    return default

  def parse(self, text: str) -> Any:
    """Parse text into field value."""
    raise NotImplementedError()

  def parse_for_problem(self, text: str, problem: Any) -> Any:
    """Parse section text in the context of ``problem`` (after header fields are populated)."""
    return self.parse(text)


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


class NumberField(TransformerField):
  """Simple numeric field (int or float)."""

  default: int | float = 0

  @classmethod
  def build_transformer(cls) -> Transformer[int | float]:
    return NumberT()


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
  def build_transformer(cls) -> Transformer[dict[int, list[float]]]:
    key: FuncT[int] = FuncT(func=int)
    value: ListT = ListT(value=FuncT(func=float))
    return MapT(key=key, value=value, sep="\n", kv_sep=" ")


class DepotsField(TransformerField):
  """Field for depots."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[int]]:
    depot: FuncT[int] = FuncT(func=int)
    return ListT(value=depot, terminal="-1")


class DemandsField(TransformerField):
  """Field for demands."""

  default: Callable[[], dict[Any, Any]] = dict

  @classmethod
  def build_transformer(cls) -> Transformer[dict[int, int]]:
    node: FuncT[int] = FuncT(func=int)
    demand: FuncT[int] = FuncT(func=int)
    return MapT(key=node, value=demand, sep="\n", kv_sep=" ")


class DurationsField(TransformerField):
  """Field mapping node IDs to numeric durations or distances."""

  default: Callable[[], dict[Any, Any]] = dict

  @classmethod
  def build_transformer(cls) -> Transformer[dict[int, float]]:
    node: FuncT[int] = FuncT(func=int)
    duration: FuncT[float] = FuncT(func=float)
    return MapT(key=node, value=duration, sep="\n", kv_sep=" ")


class MatrixField(TransformerField):
  """Field for a matrix of numbers (EDGE_WEIGHT_SECTION)."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[list[int | float]]]:
    row: ListT = ListT(value=NumberT())
    return ListT(value=row, sep="\n")


class EdgeListField(TransformerField):
  """Field for a list of edges (``FIXED_EDGES_SECTION``)."""

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> Transformer[list[list[int]]]:
    pair: ListT = ListT(value=FuncT(func=int), size=2)
    return ListT(value=pair, sep="\n", terminal="-1")


class EdgeDataField(TransformerField):
  """Field for graph edge data (``EDGE_DATA_SECTION``).

  Parses both ``EDGE_LIST`` and ``ADJ_LIST`` layouts (see :class:`EdgeDataT`),
  honoring ``EDGE_DATA_FORMAT`` when declared on the problem and falling back
  to content sniffing when omitted.
  """

  default: Callable[[], list[Any]] = list

  @classmethod
  def build_transformer(cls) -> EdgeDataT:
    return EdgeDataT()

  def parse_for_problem(self, text: str, problem: Any) -> list[list[int]]:
    """Parse ``text`` using ``problem.edge_data_format`` when available."""
    edge_fmt: str | None = getattr(problem, "edge_data_format", None) or None
    if isinstance(self.tf, EdgeDataT):
      return self.tf.parse(text, edge_data_format=edge_fmt)
    return self.tf.parse(text)


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


__all__: list[str] = [
  "DemandsField",
  "DepotsField",
  "DurationsField",
  "EdgeDataField",
  "EdgeListField",
  "Field",
  "IndexedCoordinatesField",
  "IntegerField",
  "MatrixField",
  "NumberField",
  "StringField",
  "ToursField",
  "TransformerField",
]

