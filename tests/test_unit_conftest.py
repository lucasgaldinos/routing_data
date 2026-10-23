"""Tests for the test-suite infrastructure in ``tests/conftest.py``.

WHAT: Verify the level-marker derivation helper and the collection hook.
WHY: The filename is the single source of truth for the level marker; if the
     mapping or the no-duplicate rule breaks, every gate silently mislabels.
EXPECTED: Known prefixes map to their level, unknown files return None and warn
     once, and an explicit marker is never duplicated.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
  from importlib.machinery import ModuleSpec
  from types import ModuleType

_CONFTEST_PATH: Path = Path(__file__).parent / "conftest.py"


def _load_conftest() -> ModuleType:
  spec: ModuleSpec | None = importlib.util.spec_from_file_location("tests_conftest_under_test", _CONFTEST_PATH)
  if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load {_CONFTEST_PATH}")
  module: ModuleType = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


_CONFTEST: ModuleType = _load_conftest()


@pytest.mark.parametrize(
  ("filename", "expected"),
  [
    ("test_unit_parser.py", "unit"),
    ("test_integration_api.py", "integration"),
    ("test_e2e_pipeline.py", "e2e"),
    ("test_performance_scan.py", "performance"),
    ("conftest.py", None),
    ("helper.py", None),
  ],
)
def test_level_marker_for(filename: str, expected: str | None) -> None:
  """WHAT: Map filenames to levels. WHY: Gate selection depends on it.
  EXPECTED: Each known prefix maps; anything else returns None.
  """
  assert _CONFTEST.level_marker_for(filename) == expected


class _FakeItem:
  """Minimal stand-in for a collected pytest item."""

  def __init__(self, filename: str, existing: set[str] | None = None) -> None:
    self.path: Path = Path(filename)
    self._existing: set[str] = existing or set()
    self.added: list[str] = []

  def get_closest_marker(self, name: str) -> object | None:
    return object() if name in self._existing else None

  def add_marker(self, marker: Any) -> None:
    self.added.append(marker.name)


def test_hook_adds_the_derived_level_marker() -> None:
  """WHAT: Run the hook over unit and integration items.
  WHY: The derived marker is the only level signal.
  EXPECTED: Each item receives exactly its own level marker.
  """
  unit_item = _FakeItem("test_unit_parser.py")
  integration_item = _FakeItem("test_integration_api.py")

  _CONFTEST.pytest_collection_modifyitems(None, [unit_item, integration_item])

  assert unit_item.added == ["unit"]
  assert integration_item.added == ["integration"]


def test_hook_does_not_duplicate_an_explicit_marker() -> None:
  """WHAT: Run the hook on an item that already declares its level.
  WHY: A hand-written marker must not be added twice.
  EXPECTED: Nothing is added.
  """
  item = _FakeItem("test_unit_matrix_formats.py", existing={"unit"})

  _CONFTEST.pytest_collection_modifyitems(None, [item])

  assert item.added == []


def test_hook_warns_once_for_unprefixed_files() -> None:
  """WHAT: Collect two items from an unprefixed file.
  WHY: Ad-hoc tests must be visible without aborting collection.
  EXPECTED: One PytestWarning, no marker added.
  """
  first = _FakeItem("scratch.py")
  second = _FakeItem("scratch.py")

  with pytest.warns(pytest.PytestWarning, match="declares no test level"):
    _CONFTEST.pytest_collection_modifyitems(None, [first, second])

  assert first.added == []
  assert second.added == []
