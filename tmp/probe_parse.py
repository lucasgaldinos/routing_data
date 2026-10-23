"""Throwaway probe: show what `FormatParser.parse_file` actually returns.

Run under the debugger with a breakpoint on the `result = ...` line to inspect the
return contract (keys, value types, per-key origin) on a real corpus file.
"""

from __future__ import annotations

import pathlib
from pprint import pprint

from tsplib_parser.parser import FormatParser

HERE = pathlib.Path(__file__).resolve().parent.parent
CORPUS = HERE / "datasets_raw" / "problems"


def probe(relative: str) -> dict[str, object]:
  parser = FormatParser()
  result = parser.parse_file(str(CORPUS / relative))  # BREAKPOINT: inspect `result`
  print(f"--- {relative} ---")
  for key, value in result.items():
    kind = type(value).__name__
    if isinstance(value, dict):
      detail = f"{kind} keys={sorted(value)}"
    elif isinstance(value, list):
      first = type(value[0]).__name__ if value else "empty"
      detail = f"{kind} len={len(value)} first={first}"
    else:
      detail = f"{kind} = {value!r}"
    print(f"  {key:14} {detail}")
  return result


TSP = probe("tsp/gr17.tsp")  # 2-D TSP with an explicit display-data-free body
VRP = probe("vrp/eil22.vrp")
TOUR = probe("tour/kroD100.opt.tour")
HCP = probe("hcp/alb1000.hcp")
pprint(sorted(TSP["problem_data"]))  # type: ignore[arg-type]
print("return type annotation:", FormatParser.parse_file.__annotations__)
