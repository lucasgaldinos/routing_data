"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def test_data_dir() -> Path:
  """Path to test data directory containing TSPLIB files."""
  return Path(__file__).parent.parent / "datasets_raw" / "problems"


@pytest.fixture
def tsp_files_small(test_data_dir: Path) -> dict[str, Path]:
  """Small TSP test files (< 100 nodes) with different characteristics."""
  return {
    "gr17": test_data_dir / "tsp" / "gr17.tsp",  # 17 nodes, EUC_2D
    "att48": test_data_dir / "tsp" / "att48.tsp",  # 48 nodes, ATT distance
    "berlin52": test_data_dir / "tsp" / "berlin52.tsp",  # 52 nodes, EUC_2D
  }


@pytest.fixture
def tsp_files_medium(test_data_dir: Path) -> dict[str, Path]:
  """Medium TSP test files (100-1000 nodes)."""
  return {
    "a280": test_data_dir / "tsp" / "a280.tsp",  # 280 nodes
    "att532": test_data_dir / "tsp" / "att532.tsp",  # 532 nodes
  }


@pytest.fixture
def atsp_files(test_data_dir: Path) -> dict[str, Path]:
  """ATSP test files (asymmetric TSP)."""
  return {
    "br17": test_data_dir / "atsp" / "br17.atsp",  # 17 nodes, small
    "p43": test_data_dir / "atsp" / "p43.atsp",  # 43 nodes
    "ftv170": test_data_dir / "atsp" / "ftv170.atsp",  # 170 nodes, medium
  }


@pytest.fixture
def vrp_files(test_data_dir: Path) -> dict[str, Path]:
  """VRP test files with demands."""
  return {
    "eil7": test_data_dir / "vrp" / "eil7.vrp",  # 7 nodes, tiny
    "eil13": test_data_dir / "vrp" / "eil13.vrp",  # 13 nodes, small
    "eil51": test_data_dir / "vrp" / "eil51.vrp",  # 51 nodes, medium
  }


@pytest.fixture
def gr17_tsp(test_data_dir: Path) -> str:
  """Path to gr17.tsp test file (17-city TSP, symmetric, EUC_2D)."""
  tsp_path = test_data_dir / "tsp" / "gr17.tsp"
  if not tsp_path.exists():
    pytest.skip(f"Test file not found: {tsp_path}")
  return str(tsp_path)


@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
  """Temporary output directory for test file operations."""
  temp_dir = tempfile.mkdtemp(prefix="test_routing_")
  yield temp_dir
  # Cleanup after test
  shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def in_memory_db():
  """In-memory DuckDB database for testing without file I/O."""
  from src.converter.database.operations import DatabaseManager

  # Use :memory: for in-memory database
  db = DatabaseManager(":memory:")
  yield db
  # Database automatically cleaned up when object is destroyed


@pytest.fixture
def sample_problem_data() -> dict[str, Any]:
  """Sample TSPLIB problem data for testing."""
  return {
    "name": "test_problem",
    "type": "TSP",
    "comment": "Test problem for unit tests",
    "dimension": 5,
    "edge_weight_type": "EUC_2D",
    "node_coord_type": "TWOD_COORDS",
  }


@pytest.fixture
def sample_nodes() -> list[dict[str, Any]]:
  """Sample node coordinates for testing."""
  return [
    {"node_id": 1, "x": 0.0, "y": 0.0},
    {"node_id": 2, "x": 1.0, "y": 0.0},
    {"node_id": 3, "x": 1.0, "y": 1.0},
    {"node_id": 4, "x": 0.0, "y": 1.0},
    {"node_id": 5, "x": 0.5, "y": 0.5},
  ]


@pytest.fixture
def malformed_tsp_content() -> str:
  """Malformed TSPLIB content for error handling tests.

  A valid-looking header (name/type/dimension) followed by a poisoned
  NODE_COORD_SECTION. The parser must reject the file instead of silently
  dropping the whole coordinate section.
  """
  return """NAME: malformed
TYPE: TSP
DIMENSION: 3
NODE_COORD_SECTION
1 invalid data here
2 3.0
This is not a valid line
EOF
"""


@pytest.fixture
def malformed_demand_content() -> str:
  """CVRP whose DEMAND_SECTION has one non-integer demand line.

  A single poisoned line must reject the whole file, not erase the 21 valid
  demand rows alongside it.
  """
  return """NAME: malformed_demand
TYPE: CVRP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EUC_2D
CAPACITY: 10
NODE_COORD_SECTION
1 0 0
2 1 0
3 0 1
DEMAND_SECTION
1 0
2 BOGUS
3 5
DEPOT_SECTION
1
-1
EOF
"""


@pytest.fixture
def malformed_matrix_content() -> str:
  """ATSP whose EDGE_WEIGHT_SECTION contains one non-numeric token.

  One bad cell must reject the file rather than silently erasing the whole
  weight matrix.
  """
  return """NAME: malformed_matrix
TYPE: ATSP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EDGE_WEIGHT_SECTION
0 1 2
3 X 5
6 7 0
EOF
"""


@pytest.fixture
def malformed_edge_data_content() -> str:
  """HCP whose EDGE_DATA_SECTION has an unparsable edge line."""
  return """NAME: malformed_edges
TYPE: HCP
DIMENSION: 4
EDGE_DATA_FORMAT: EDGE_LIST
EDGE_DATA_SECTION
1 2
NOTANEDGE
3 4
-1
EOF
"""


@pytest.fixture
def missing_dimension_content() -> str:
  """TSP that omits the mandatory DIMENSION keyword."""
  return """NAME: no_dimension
TYPE: TSP
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 1 0
EOF
"""


@pytest.fixture
def explicit_without_weights_content() -> str:
  """Problem declaring EXPLICIT weights but carrying no EDGE_WEIGHT_SECTION."""
  return """NAME: no_weights
TYPE: ATSP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EXPLICIT
EDGE_WEIGHT_FORMAT: FULL_MATRIX
EOF
"""


@pytest.fixture
def tab_separated_coords_content() -> str:
  """TSP whose NODE_COORD_SECTION is TAB-separated (seen in the wild, e.g.
  pa561.tsp's DISPLAY_DATA_SECTION). Coordinate parsing must be agnostic to
  the whitespace column separator."""
  return (
    "NAME: tab_coords\nTYPE: TSP\nDIMENSION: 3\nEDGE_WEIGHT_TYPE: EUC_2D\nNODE_COORD_SECTION\n"
    "1\t0\t0\n2\t1\t0\n3\t0\t1\nEOF\n"
  )


@pytest.fixture
def fixed_edges_keyword_content() -> str:
  """HCP that declares fixed edges via the ``FIXED_EDGES :`` keyword form
  (alb4000-style: keyword follows EDGE_DATA_SECTION, pairs run to a ``-1``)."""
  return """NAME: alb_style
TYPE: HCP
DIMENSION: 4
EDGE_DATA_FORMAT: EDGE_LIST
EDGE_DATA_SECTION
1 2
2 3
3 4
4 1
-1
FIXED_EDGES :
  1 2
  3 4
-1
EOF
"""
