"""Throwaway probe: show what `FormatParser.parse_file` actually returns.

Put a breakpoint on the `result = ...` line and inspect `result` in the debugger:
the return contract is an untyped `dict[str, Any]` (PC1), so this script is how we
see it instead of trusting the annotation.
"""

import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))  # keep the probe runnable without PYTHONPATH

from tsplib_parser.parser import FormatParser  # noqa: E402

CORPUS = HERE / "datasets_raw" / "problems"


def describe(key: str, value: Any) -> None:
  if isinstance(value, dict):
    print(f"  {key:14} dict  keys={sorted(str(k) for k in value)}")
  elif isinstance(value, list):
    first = type(value[0]).__name__ if value else "empty"
    print(f"  {key:14} list  len={len(value)} first={first}")
  else:
    print(f"  {key:14} {type(value).__name__} = {value!r}")


def probe(relative: str) -> dict[str, Any]:
  parser = FormatParser()
  result = parser.parse_file(str(CORPUS / relative))  # BREAKPOINT: inspect `result`
  print(f"--- {relative} ---")
  for key, value in result.items():
    describe(key, value)
  return result


TSP = probe("tsp/gr17.tsp")
VRP = probe("vrp/eil22.vrp")
TOUR = probe("tour/kroD100.opt.tour")
HCP = probe("hcp/alb1000.hcp")
print("annotation:", FormatParser.parse_file.__annotations__)
print("tsp problem_data keys:", sorted(TSP["problem_data"]))
