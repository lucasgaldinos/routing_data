"""Throwaway probe: parse one problem file from every corpus folder."""

from pathlib import Path

from tsplib_parser.cordeau.cordeau_parser import CordeauParser
from tsplib_parser.parser import FormatParser

ROOT = Path("datasets_raw")
PROBLEM_FOLDERS = [
    "problems/tsp",
    "problems/atsp",
    "problems/sop",
    "problems/hcp",
    "problems/vrp",
    "problems/tour",
    "cvrplib/Holmberger",
    "cvrplib/VRP-set-D",
    "cvrplib/Vrp-Set-Li",
    "cvrplib/Vrp-Set-Solomon",
    "cvrplib/vrp-XXL",
    "umalaga/mdvrp/C-mdvrp",
]

parser = FormatParser()
cordeau = CordeauParser()

for folder in PROBLEM_FOLDERS:
    directory = ROOT / folder
    candidates = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix not in {".sol", ".res"})
    if not candidates:
        print(f"{folder:32} EMPTY")
        continue
    target = candidates[0]
    try:
        if folder.endswith("C-mdvrp"):
            problem = cordeau.parse_file(file_path=target)
            print(
                f"{folder:32} {target.name:16} OK  Cordeau  type={problem.type_name} "
                f"dim={problem.dimension} depots={problem.num_depots}"
            )
            continue
        result = parser.parse_file(target)
        data = result["problem_data"]
        print(
            f"{folder:32} {target.name:16} OK  type={data.get('type')} "
            f"dim={data.get('dimension')} coords={len(result['coords'])} "
            f"demands={len(result['demands'])} depots={len(result['depots'])} "
            f"tours={len(result['tours'])} ewt={data.get('edge_weight_type')}"
        )
    except Exception as exc:  # noqa: BLE001 - probe wants the failure text
        print(f"{folder:32} {target.name:16} FAIL {type(exc).__name__}: {str(exc)[:120]}")
