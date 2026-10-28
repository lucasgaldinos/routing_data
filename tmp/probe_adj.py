"""Throwaway probe: does ADJ_LIST keep every neighbour of a row?"""

import pathlib
import tempfile

from tsplib_parser.parser import FormatParser

ADJ = """NAME : adj
TYPE : TSP
DIMENSION : 4
EDGE_WEIGHT_TYPE : EXPLICIT
EDGE_WEIGHT_FORMAT : FULL_MATRIX
EDGE_DATA_FORMAT : ADJ_LIST
EDGE_DATA_SECTION
1 2 3 -1
2 1 -1
3 1 -1
4 -1
-1
EDGE_WEIGHT_SECTION
0 1 1 9
1 0 9 9
1 9 0 9
9 9 9 0
EOF
"""

target = pathlib.Path(tempfile.mkdtemp()) / "adj.tsp"
target.write_text(ADJ, encoding="utf-8")
result = FormatParser().parse_file(target)
print("edges:", result["problem_data"].get("edges"))
print("top-level edges:", result.get("edges"))
