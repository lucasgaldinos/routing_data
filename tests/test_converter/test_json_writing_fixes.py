"""
Tests for Issues #3 and #4: JSON writing duplication and dead 'edges' field.

Issue #3: api.py:to_json() duplicates JSONWriter logic
Issue #4: JSONWriter includes 'edges': [] which is always empty

Tests verify:
1. JSONWriter does NOT include 'edges' field after fix
2. api.py:to_json() uses consistent JSON structure (no duplication)
3. Both methods produce identical output format
"""

import json

import pytest

from converter.api import SimpleConverter
from converter.output.json_writer import JSONWriter
from converter.utils.logging import setup_logging


@pytest.fixture
def sample_data():
  """Sample transformed problem data."""
  return {
    "problem_data": {"name": "test_problem", "type": "TSP", "dimension": 3, "edge_weight_type": "EUC_2D"},
    "nodes": [
      {"node_id": 0, "x": 0.0, "y": 0.0, "z": None, "demand": None, "is_depot": False},
      {"node_id": 1, "x": 1.0, "y": 1.0, "z": None, "demand": None, "is_depot": False},
      {"node_id": 2, "x": 2.0, "y": 2.0, "z": None, "demand": None, "is_depot": False},
    ],
    "tours": [],
    "metadata": {"file_path": "test.tsp", "file_size": 100},
  }


class TestRemoveDeadEdgesField:
  """Test Issue #4: Remove 'edges' field from JSONWriter output."""

  def test_json_writer_no_edges_field(self, sample_data, tmp_path):
    """
    WHAT: Verify JSONWriter does NOT include 'edges' field
    WHY: Issue #4 - 'edges' field is always empty, database has no edges table
    EXPECTED: JSON output should NOT contain 'edges' key
    """
    logger = setup_logging()
    json_writer = JSONWriter(str(tmp_path), logger=logger)

    # Write problem
    output_path = json_writer.write_problem(sample_data, organize_by_type=False)

    # Read back and verify
    with open(output_path) as f:
      json_data = json.load(f)

    # Should NOT have edges field
    assert "edges" not in json_data, "JSONWriter should not include 'edges' field"

    # Should have other expected fields
    assert "problem" in json_data
    assert "nodes" in json_data
    assert "tours" in json_data
    assert "metadata" in json_data


class TestJSONWritingDeduplication:
  """Test Issue #3: Remove duplication between api.py and JSONWriter."""

  def test_api_to_json_no_edges(self, sample_data, tmp_path):
    """
    WHAT: Verify api.to_json() does NOT include 'edges' field
    WHY: Issue #3 - api.py should use same structure as JSONWriter
    EXPECTED: JSON output should NOT contain 'edges' key
    """
    logger = setup_logging()
    converter = SimpleConverter(logger=logger)

    output_file = tmp_path / "test_output.json"
    converter.to_json(sample_data, str(output_file))

    # Read back and verify
    with open(output_file) as f:
      json_data = json.load(f)

    # Should NOT have edges field
    assert "edges" not in json_data, "api.to_json() should not include 'edges' field"

  def test_api_and_writer_produce_identical_output(self, sample_data, tmp_path):
    """
    WHAT: Verify api.to_json() and JSONWriter produce identical output
    WHY: Issue #3 - eliminate duplication by using same code path
    EXPECTED: Identical JSON structure and content
    """
    logger = setup_logging()
    converter = SimpleConverter(logger=logger)
    json_writer = JSONWriter(str(tmp_path / "writer"), logger=logger)

    # Generate output from api.to_json()
    api_output_file = tmp_path / "api" / "test_problem.json"
    api_output_file.parent.mkdir(parents=True, exist_ok=True)
    converter.to_json(sample_data, str(api_output_file))

    # Generate output from JSONWriter
    writer_output = json_writer.write_problem(sample_data, organize_by_type=False)

    # Read both
    with open(api_output_file) as f:
      api_data = json.load(f)

    with open(writer_output) as f:
      writer_data = json.load(f)

    # Should be identical
    assert api_data == writer_data, "api.to_json() and JSONWriter should produce identical output"

  def test_both_methods_handle_empty_lists(self, tmp_path):
    """
    WHAT: Verify both methods handle empty nodes/tours correctly
    WHY: Edge case testing for consistency
    EXPECTED: Empty lists, not null values
    """
    logger = setup_logging()
    converter = SimpleConverter(logger=logger)
    json_writer = JSONWriter(str(tmp_path / "writer"), logger=logger)

    minimal_data = {
      "problem_data": {"name": "minimal", "type": "TSP", "dimension": 0},
      "nodes": [],
      "tours": [],
      "metadata": {},
    }

    # Test api.to_json()
    api_file = tmp_path / "api_minimal.json"
    converter.to_json(minimal_data, str(api_file))

    with open(api_file) as f:
      api_data = json.load(f)

    assert api_data["nodes"] == []
    assert api_data["tours"] == []

    # Test JSONWriter
    writer_file = json_writer.write_problem(minimal_data, organize_by_type=False)

    with open(writer_file) as f:
      writer_data = json.load(f)

    assert writer_data["nodes"] == []
    assert writer_data["tours"] == []

    # Should match
    assert api_data == writer_data
