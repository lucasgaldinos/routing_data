---
title: "TSPLIB-Extended Format Specification"
description: "Format specification for the TSPLIB-extended problem and solution dialect, accepted third-party benchmark formats, and lossless conversions."
date_created: 2026-10-25
date_changed: 2026-10-26
author: ["Lucas Galdino"]
status: active
type: specification
scope: [tsplib_parser, converter, cordeau]
related_files:
  - ./tsplib95_format.md
  - ./tsplib_format_extended.md
  - ./LKH-3-Keld-Helsgaun.md
  - ./ARCHITECTURE_DECISIONS.md
tags: [spec/tsplib95, spec/tsplib-extended, spec/cordeau, spec/solomon, spec/solutions, parser, converter]
---

# TSPLIB-extended format specification

This document specifies the **TSPLIB-extended** file format for vehicle routing problems and their solutions, together with the third-party benchmark formats converted into this dialect. Historical design rationale, requirements, and rejected alternatives are recorded in [tsplib_format_extended.md](./tsplib_format_extended.md) and [ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md).

## 1. Scope and authority

### 1.1 Objectives

The TSPLIB-extended specification supports four repository capabilities:

1. **Problem format conversion**: Convert third-party routing problem instances (Cordeau multi-depot and periodic files, Solomon and Homberger `.txt` files) into a lossless, parseable TSPLIB-extended problem document (`ExtendedProblem`), with a programmatic API to read and emit them.
2. **Solution format conversion**: Convert third-party routing solution files (TSPLIB `.opt.tour`, CVRPLIB and Solomon/Homberger `.sol`, Cordeau `.res`) into a lossless, parseable TSPLIB-extended solution document (`TYPE : TOUR`), with a programmatic API to read and emit them.
3. **Unified parsing**: Parse both core TSPLIB95 files (`StandardProblem`) and TSPLIB-extended files (`ExtendedProblem`) into a single typed `ParseResult` contract in [`src/tsplib_parser/`](../../src/tsplib_parser/__init__.py).
4. **Analytical storage transformation**: Transform parsed TSPLIB-extended problem and solution structures into normalized `json`, DuckDB (`db`), and `parquet` representations in [`src/converter/`](../../src/converter/__init__.py).

### 1.2 Authority order

1. **Primary authority ([TSPLIB95 specification](./tsplib95_format.md))**: Governs lexical structure, core header keywords ([spec §1.1](./tsplib95_format.md#11-the-specification-part)), core data sections ([spec §1.2](./tsplib95_format.md#12-the-data-part)), explicit matrix layouts ([spec §1.1.7](./tsplib95_format.md#117-edge_weight_format-string)), and distance functions ([spec §2](./tsplib95_format.md#2-the-distance-functions)).
2. **Extension inspiration ([LKH-3 reference](./LKH-3-Keld-Helsgaun.md))**: Inspires the extended `TYPE` tokens ([§3.3](#33-problem-type-vocabulary)), extended header keywords ([§3.2](#32-extended-header-keywords)), and constraint sections ([§4.2](#42-extended-data-sections)). LKH-3 is a solver rather than a format authority; where LKH-3 restricts a core TSPLIB95 construct (such as permitting only a single depot), TSPLIB-extended follows the [TSPLIB95 specification](./tsplib95_format.md).
3. **TSPLIB-extended additions**: Defines multi-depot heterogeneous depot sections (`DEPOT_CAPACITY_SECTION`, `DEPOT_DURATION_SECTION` in [§4.2](#42-extended-data-sections)) and the canonical multi-route solution document ([§6](#6-solution-format-specification)).

---

## 2. File structure and lexical rules

A TSPLIB-extended document is a plain-text file encoded in UTF-8 (with `latin-1` fallback when reading legacy benchmark files) consisting of two parts in order:

1. **Specification part**: Header lines of the form `<KEYWORD> : <value>` (or `<KEYWORD>: <value>`). Leading and trailing whitespace around `<KEYWORD>` and `<value>` is ignored.
2. **Data part**: Named data sections introduced by a standalone `<SECTION_KEYWORD>` line, followed by section body lines and terminated by `-1`, the next `<SECTION_KEYWORD>`, or `EOF`.

### 2.1 Lexical conventions

- **Comments**: Any line whose first non-whitespace character is `#` is a comment and is ignored before tokenization. Human-readable metadata inside the document uses the `COMMENT : <string>` header ([spec §1.1.3](./tsplib95_format.md#113-comment-string)).
- **Numbers**: Integers are signed base-10 tokens (`-?[0-9]+`). Real numbers accept decimal and scientific notation (`-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?`).
- **End-of-file**: `EOF` ([spec §1.1.11](./tsplib95_format.md#1111-eof)) is optional; parsing terminates at `EOF` or at physical end-of-stream.
- **Node numbering**: Every node identifier written in a problem or canonical solution file is **1-based** (`1..DIMENSION`). When `FormatParser.parse_file()` extracts arrays into `ParseResult`, node identifiers and positional arrays are re-based to **0-based** (`0..DIMENSION - 1`) as defined in [§8](#8-numbering-and-index-frames).

---

## 3. Problem specification part (header keywords)

### 3.1 Core TSPLIB95 keywords

Core header keywords are registered on `StandardProblem` and inherited by `ExtendedProblem`.

| Keyword | Value type | Required | `ProblemData` key | Specification reference |
| --- | --- | --- | --- | --- |
| `NAME` | string | yes | `name` | [spec §1.1.1](./tsplib95_format.md#111-name-string) |
| `TYPE` | enum string | yes | `type` | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `COMMENT` | string (repeatable) | no | `comment` | [spec §1.1.3](./tsplib95_format.md#113-comment-string) |
| `DIMENSION` | integer (`>= 1`) | yes | `dimension` | [spec §1.1.4](./tsplib95_format.md#114-dimension-integer) |
| `CAPACITY` | integer (`> 0`) | conditional | `capacity` | [spec §1.1.5](./tsplib95_format.md#115-capacity-integer) |
| `EDGE_WEIGHT_TYPE` | enum string | conditional | `edge_weight_type` | [spec §1.1.6](./tsplib95_format.md#116-edge_weight_type-string) |
| `EDGE_WEIGHT_FORMAT` | enum string | conditional | `edge_weight_format` | [spec §1.1.7](./tsplib95_format.md#117-edge_weight_format-string) |
| `EDGE_DATA_FORMAT` | enum string | conditional | `edge_data_format` | [spec §1.1.8](./tsplib95_format.md#118-edge_data_format-string) |
| `NODE_COORD_TYPE` | enum string | no | `node_coord_type` | [spec §1.1.9](./tsplib95_format.md#119-node_coord_type-string) |
| `DISPLAY_DATA_TYPE` | enum string | no | `display_data_type` | [spec §1.1.10](./tsplib95_format.md#1110-display_data_type-string) |
| `EOF` | marker | no | — | [spec §1.1.11](./tsplib95_format.md#1111-eof) |

#### Core header rules

- Multiple `COMMENT` lines are joined with `\n` in file order.
- `CAPACITY` is required when `DEMAND_SECTION` ([§4.1](#41-core-data-sections)) is present and `DEPOT_CAPACITY_SECTION` ([§4.2](#42-extended-data-sections)) is absent.
- `EDGE_WEIGHT_FORMAT` is required when `EDGE_WEIGHT_TYPE` is `EXPLICIT`.
- `EDGE_DATA_FORMAT` (`EDGE_LIST` or `ADJ_LIST`) is required when `EDGE_DATA_SECTION` is present.
- `NODE_COORD_TYPE` defaults to `TWOD_COORDS` for 2-D weight types ([§5](#5-distance-functions)), `THREED_COORDS` for 3-D weight types, and `NO_COORDS` otherwise.
- `DISPLAY_DATA_TYPE` (`COORD_DISPLAY`, `TWOD_DISPLAY`, or `NO_DISPLAY`) defaults to `COORD_DISPLAY` when coordinates are present and `DISPLAY_DATA_SECTION` is absent, `TWOD_DISPLAY` when `DISPLAY_DATA_SECTION` is present, and `NO_DISPLAY` otherwise.

### 3.2 Extended header keywords

Extended header keywords are registered as typed fields on `ExtendedProblem` in [`src/tsplib_parser/models.py`](../../src/tsplib_parser/models.py).

| Keyword | Value type | `ProblemData` key | Meaning |
| --- | --- | --- | --- |
| `VEHICLES` | integer | `vehicles` | Fleet size (number of vehicles available across the instance). |
| `SALESMEN` | integer | `salesmen` | Number of salesmen in multi-salesman (`MTSP`, `BMTSP`) instances. |
| `EXTERNAL_SALESMEN` | integer | `external_salesmen` | Number of external salesmen in colored/open `MTSP` instances. |
| `DISTANCE` | real | `max_distance` | Maximum route distance or duration limit when uniform across depots. |
| `SERVICE_TIME` | real | `service_time` | Uniform service duration at every customer node. |
| `CAPACITY_VOL` | integer | `capacity_vol` | Vehicle volume capacity in 2-D weight-and-volume `CVRP` instances. |
| `CAPACITY_WEIGHT` | integer | `capacity_weight` | Explicit vehicle weight capacity companion to `CAPACITY_VOL`. |
| `PERIODS` | integer | `periods` | Planning horizon length in periodic routing (`PVRP`, `PVRPTW`) instances. |
| `SCALE` | integer | `scale` | Multiplier applied to continuous distances before integer rounding. |
| `RISK_THRESHOLD` | integer | `risk_threshold` | Maximum cumulative risk threshold in risk-constrained (`RCTVRP`, `RCTVRPTW`) instances. |
| `GRID_SIZE` | real | `grid_size` | Grid box side length for geometric / planar grid problems. |
| `K` | integer | `k` | Target subset size $k$ in $k$-TSP (`K-TSP`, `O-K-TSP`) instances. |
| `PROBABILITY` | real | `probability` | Homogeneous node presence probability in probabilistic TSP (`PTSP`). |

#### Rejected header keywords

- `DEPOTS` and `DEMAND_DIMENSION` are not part of TSPLIB-extended: depot count is `len(DEPOT_SECTION)` ([§4.1](#41-core-data-sections)) and multi-column demands are inferred directly from `DEMAND_SECTION` row width.

### 3.3 Problem `TYPE` vocabulary

Before looking up `PROBLEM_REGISTRY`, `normalize_problem_type()` in [`src/tsplib_parser/types.py`](../../src/tsplib_parser/types.py) strips any parenthetical comment (for example, `TSP (M.~Hofmeister)` becomes `TSP`), uppercases the leading token, and resolves `PROBLEM_TYPE_ALIASES` (`VRP` normalizes to `CVRP`).

#### Core `TYPE` values (`VALID_PROBLEM_TYPES`, dispatched to `StandardProblem`)

| Token | Meaning | Specification reference |
| --- | --- | --- |
| `TSP` | Symmetric traveling salesman problem | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `ATSP` | Asymmetric traveling salesman problem | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `SOP` | Sequential ordering problem (precedence-constrained ATSP) | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `HCP` | Hamiltonian cycle problem | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `CVRP` | Capacitated vehicle routing problem (`VRP` is accepted as an alias and normalized to `CVRP`) | [spec §1.1.2](./tsplib95_format.md#112-type-string) |
| `TOUR` | Collection of tours / canonical solution document ([§6](#6-solution-format-specification)) | [spec §1.1.2](./tsplib95_format.md#112-type-string) |

#### Extended `TYPE` values (`EXTENDED_PROBLEM_TYPES`, dispatched to `ExtendedProblem`)

| Category | Canonical `TYPE` tokens |
| --- | --- |
| Time-window routing | `TSPTW`, `CVRPTW`, `VRPBTW`, `VRPMPDTW`, `VRPSPDTW`, `RCTVRPTW`, `MDVRPTW`, `PVRPTW`, `SDVRPTW` |
| Multi-depot, periodic, and split-delivery VRP | `MDVRP`, `MDMTSP`, `PVRP`, `SDVRP`, `OVRP`, `CCVRP`, `DCVRP`, `ACVRP`, `ADCVRP`, `RCTVRP` |
| Pickup, delivery, and backhaul | `PDPTW`, `PDTSP`, `PDTSPF`, `PDTSPL`, `TSPPD`, `1-PDTSP`, `M-PDTSP`, `M1-PDTSP`, `VRPB`, `VRPMPD`, `VRPSPD`, `TSPDL` |
| Multi-salesman and colored TSP | `MTSP`, `BMTSP`, `CTSP`, `CTSP-D`, `CBTSP`, `CBNTSP`, `CCCTSP`, `MSCTSP`, `TSP_MD` |
| Clustered and generalized TSP/VRP | `GCTSP`, `CLUVRP`, `SOFTCLUVRP`, `CATSPP` |
| Prize-collecting, selective, and Steiner | `OP`, `TOP`, `PCTSP`, `PC-TSP`, `PTP`, `STTSP`, `K-TSP`, `O-K-TSP` |
| Latency, repairman, and miscellaneous | `MLP`, `TRP`, `MTRP`, `MTRPD`, `BWTSP`, `HPP`, `PTSP` |

---

## 4. Problem data part (data sections)

### 4.1 Core data sections

Core data sections follow [spec §1.2](./tsplib95_format.md#12-the-data-part) and are registered on `StandardProblem` (and inherited by `ExtendedProblem`). All node IDs in the file are 1-based integers in `1..DIMENSION`.

| Section keyword | Row grammar | Terminator | `ParseResult` target | Specification reference |
| --- | --- | --- | --- | --- |
| `NODE_COORD_SECTION` | `<node> <x> <y>` (`TWOD_COORDS`) or `<node> <x> <y> <z>` (`THREED_COORDS`) | next section / `EOF` | `coords` (`list[list[float]]`, 0-based by node index) | [spec §1.2.1](./tsplib95_format.md#121-node_coord_section) |
| `DEPOT_SECTION` | `<node>` (one depot node ID per line) | `-1` | `depots` (`list[int]`, 0-based node indices) | [spec §1.2.2](./tsplib95_format.md#122-depot_section) |
| `DEMAND_SECTION` | `<node> <demand>` (or `<node> <weight> <volume>`) | next section / `EOF` | `demands` (`list[int]`, 0-based) and optional `problem_data["volume_demands"]` | [spec §1.2.3](./tsplib95_format.md#123-demand_section) |
| `EDGE_DATA_SECTION` | `EDGE_LIST`: `<u> <v>`; `ADJ_LIST`: `<u_0> <v_1> ... <v_k> -1` | `-1` | `edges` (`list[list[int]]`, 0-based `[u, v]` pairs) | [spec §1.2.4](./tsplib95_format.md#124-edge_data_section) |
| `FIXED_EDGES_SECTION` | `<u> <v>` | `-1` | `fixed_edges` (`list[list[int]]`, 0-based `[u, v]` pairs) | [spec §1.2.5](./tsplib95_format.md#125-fixed_edges_section) |
| `DISPLAY_DATA_SECTION` | `<node> <x> <y>` | next section / `EOF` | `display_coords` (`list[list[float]]`, 0-based) | [spec §1.2.6](./tsplib95_format.md#126-display_data_section) |
| `TOUR_SECTION` | `<node>` (one or more integer node IDs per line) | `-1` per tour, `-1` for section | `tours` (`list[TourDict]`, 0-based node indices) | [spec §1.2.7](./tsplib95_format.md#127-tour_section) |
| `EDGE_WEIGHT_SECTION` | whitespace-separated numbers in `EDGE_WEIGHT_FORMAT` order | next section / `EOF` | `problem_data["edge_weights"]` (`Matrix`) | [spec §1.2.8](./tsplib95_format.md#128-edge_weight_section) |

### 4.2 Extended data sections

Extended data sections are registered on `ExtendedProblem` and extracted into `ParseResult["problem_data"]`.

| Section keyword | Row grammar | Terminator | `ProblemData` key and type | Meaning |
| --- | --- | --- | --- | --- |
| `TIME_WINDOW_SECTION` | `<node> <earliest> <latest>` (int, real, real) | next section / `EOF` | `time_windows`: `list[list[float]]` (0-based, shape `DIMENSION x 2`) | Service start window $[e_i, l_i]$ for every node $i \in \{1..\text{DIMENSION}\}$. |
| `SERVICE_TIME_SECTION` | `<node> <duration>` (int, real) | next section / `EOF` | `service_times`: `list[list[float]]` (0-based, shape `DIMENSION x 1`) | Per-node service duration $s_i$. |
| `PICKUP_AND_DELIVERY_SECTION` | `<node> <d_1> ... <d_k>` (int followed by 3, 5, or 6 numbers) | next section / `EOF` | `pickup_and_delivery`: `list[list[float]]` (0-based) | Per-node pickup/delivery attributes (6-column LKH-3 layout `<node> <cap> <e> <l> <s> <pickup> <delivery>`, plus 4- and 7-column benchmark variants). |
| `BACKHAUL_SECTION` | `<node>` (one backhaul node ID per line) | `-1` | `backhauls`: `list[int]` (1-based node IDs) | Nodes that are backhaul (pickup) customers in `VRPB` / `VRPBTW` instances. |
| `DEPOT_CAPACITY_SECTION` | `<depot_ordinal> <max_load>` (int, int) | next section / `EOF` | `depot_capacities`: `dict[int, int]` or `list[int]` | Per-depot vehicle capacity when depots have heterogeneous load limits (`1..len(DEPOT_SECTION)`). |
| `DEPOT_DURATION_SECTION` | `<depot_ordinal> <max_duration>` (int, real) | next section / `EOF` | `depot_durations`: `dict[int, float]` | Per-depot maximum route duration/distance when depots have heterogeneous limits (`1..len(DEPOT_SECTION)`). |
| `REQUIRED_NODES_SECTION` | `<node>` (one required node ID per line) | `-1` | `required_nodes`: `list[int]` (1-based node IDs) | Nodes that must be visited in a Steiner traveling salesman (`STTSP`) instance. |

> [!note]
> `CTSP_SET_SECTION` is named in the [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) changelog for colored TSP (`CTSP`), but no line grammar is published in the specification sources; it is therefore not registered as a parser field. When a core-typed problem (`StandardProblem`) carries an extended section such as `TIME_WINDOW_SECTION`, `_preprocess_vrp_file()` strips the unparseable section body, records the section name in `problem_data["stripped_sections"]`, and sets the corresponding boolean flag (`has_time_windows`, `has_service_times`, `has_pickup_delivery`, or `has_backhauls`).

### 4.3 Explicit matrix formats

When `EDGE_WEIGHT_TYPE : EXPLICIT` is declared, `EDGE_WEIGHT_SECTION` ([spec §1.2.8](./tsplib95_format.md#128-edge_weight_section)) contains whitespace-separated numbers whose count is determined by `DIMENSION` ($n$) and `EDGE_WEIGHT_FORMAT` ([spec §1.1.7](./tsplib95_format.md#117-edge_weight_format-string)):

| `EDGE_WEIGHT_FORMAT` | Matrix layout | Required element count | Matrix class (`src/tsplib_parser/matrix.py`) |
| --- | --- | --- | --- |
| `FULL_MATRIX` | Full $n \times n$ row-major matrix | $n^2$ | `FullMatrix` |
| `UPPER_ROW` | Upper triangle, row-wise, without diagonal | $n(n - 1) / 2$ | `UpperRow` |
| `LOWER_ROW` | Lower triangle, row-wise, without diagonal | $n(n - 1) / 2$ | `LowerRow` |
| `UPPER_DIAG_ROW` | Upper triangle, row-wise, with diagonal | $n(n + 1) / 2$ | `UpperDiagRow` |
| `LOWER_DIAG_ROW` | Lower triangle, row-wise, with diagonal | $n(n + 1) / 2$ | `LowerDiagRow` |
| `UPPER_COL` | Upper triangle, column-wise, without diagonal | $n(n - 1) / 2$ | `UpperCol` |
| `LOWER_COL` | Lower triangle, column-wise, without diagonal | $n(n - 1) / 2$ | `LowerCol` |
| `UPPER_DIAG_COL` | Upper triangle, column-wise, with diagonal | $n(n + 1) / 2$ | `UpperDiagCol` |
| `LOWER_DIAG_COL` | Lower triangle, column-wise, with diagonal | $n(n + 1) / 2$ | `LowerDiagCol` |

#### Tolerated explicit-matrix benchmark deviations

1. **Omitted zero diagonal on `*_DIAG_*` formats (`NO_DIAG_FORMAT_FALLBACK`)**: If a file declares `LOWER_DIAG_ROW`, `UPPER_DIAG_ROW`, `LOWER_DIAG_COL`, or `UPPER_DIAG_COL` but supplies exactly $n(n - 1) / 2$ numbers instead of $n(n + 1) / 2$, `StandardProblem.create_explicit_matrix()` falls back to the corresponding diagonal-free class (`LOWER_ROW`, `UPPER_ROW`, `LOWER_COL`, `UPPER_COL`) and logs a warning. Any other element count raises `ParseError`.
2. **Leading dimension integer in `.sop` matrices**: Sequential ordering problem (`SOP`) files whose `EDGE_WEIGHT_SECTION` begins with a standalone integer equal to `DIMENSION` followed by $n^2$ matrix entries ($n^2 + 1$ integers total) have the leading dimension token stripped before constructing `FullMatrix`.

---

## 5. Distance functions

`EDGE_WEIGHT_TYPE` ([spec §1.1.6](./tsplib95_format.md#116-edge_weight_type-string)) selects how edge weights $d(i, j)$ are obtained. Where the TSPLIB95 specification prescribes `nint`, rounding follows [spec §2](./tsplib95_format.md#2-the-distance-functions): $\text{nint}(x) = \lfloor x + 0.5 \rfloor$.

| `EDGE_WEIGHT_TYPE` | Coordinate dimension | Distance definition | Specification reference |
| --- | --- | --- | --- |
| `EXPLICIT` | none (`EDGE_WEIGHT_SECTION`) | Explicit weights from `EDGE_WEIGHT_SECTION` ([§4.3](#43-explicit-matrix-formats)) | [spec §1.1.6](./tsplib95_format.md#116-edge_weight_type-string) |
| `EUC_2D` | 2-D | $\text{nint}(\sqrt{\Delta x^2 + \Delta y^2})$ | [spec §2.1](./tsplib95_format.md#21-euclidean-distance-l2-metric) |
| `EUC_3D` | 3-D | $\text{nint}(\sqrt{\Delta x^2 + \Delta y^2 + \Delta z^2})$ | [spec §2.1](./tsplib95_format.md#21-euclidean-distance-l2-metric) |
| `MAN_2D` | 2-D | $\text{nint}(\lvert \Delta x \rvert + \lvert \Delta y \rvert)$ | [spec §2.2](./tsplib95_format.md#22-manhattan-distance-l1-metric) |
| `MAN_3D` | 3-D | $\text{nint}(\lvert \Delta x \rvert + \lvert \Delta y \rvert + \lvert \Delta z \rvert)$ | [spec §2.2](./tsplib95_format.md#22-manhattan-distance-l1-metric) |
| `MAX_2D` | 2-D | $\max(\text{nint}(\lvert \Delta x \rvert), \text{nint}(\lvert \Delta y \rvert))$ | [spec §2.3](./tsplib95_format.md#23-maximum-distance-l-metric) |
| `MAX_3D` | 3-D | $\max(\text{nint}(\lvert \Delta x \rvert), \text{nint}(\lvert \Delta y \rvert), \text{nint}(\lvert \Delta z \rvert))$ | [spec §2.3](./tsplib95_format.md#23-maximum-distance-l-metric) |
| `GEO` | 2-D (`DDD.MM` latitude/longitude) | Great-circle distance on sphere of radius $R = 6378.388\text{ km}$ | [spec §2.4](./tsplib95_format.md#24-geographical-distance) |
| `ATT` | 2-D | Pseudo-Euclidean: $r = \sqrt{(\Delta x^2 + \Delta y^2) / 10}$, $t = \text{nint}(r)$, $d = t + 1$ if $t < r$ else $t$ | [spec §2.5](./tsplib95_format.md#25-pseudo-euclidean-distance) |
| `CEIL_2D` | 2-D | $\lceil \sqrt{\Delta x^2 + \Delta y^2} \rceil$ | [spec §2.6](./tsplib95_format.md#26-ceiling-of-the-euclidean-distance) |
| `XRAY1` | 3-D | Diffractometer motor-angle distance (min-angle model) | [spec §2.7](./tsplib95_format.md#27-distance-for-crystallography-problems) |
| `XRAY2` | 3-D | Diffractometer motor-angle distance (weighted model) | [spec §2.7](./tsplib95_format.md#27-distance-for-crystallography-problems) |
| `SPECIAL` | problem-specific | Admitted in `EDGE_WEIGHT_TYPES` vocabulary; no general closed-form formula exists | [spec §1.1.6](./tsplib95_format.md#116-edge_weight_type-string) |

---

## 6. Solution format specification

Every routing solution converted into TSPLIB-extended is represented as a self-describing `TYPE : TOUR` document that uses **1-based problem node IDs** throughout.

### 6.1 Canonical solution document grammar

```text
NAME : <solution-name>
TYPE : TOUR
COMMENT : <free text>                       (optional, repeatable)
PROBLEM : <instance-name>
DIMENSION : <integer>                       (optional when not known from the source)
COST : <number>                             (optional)
DEPOT_SECTION                               (optional; present when routes are anchored at depots)
<depot-node-id>
...
-1
ROUTE_SECTION
<route-id> <node-id> <node-id> ...
...
-1
ROUTE_DEPOT_SECTION                         (optional; present if and only if DEPOT_SECTION is present)
<route-id> <depot-node-id>
...
-1
ROUTE_COST_SECTION                          (optional)
<route-id> <number>
...
-1
ROUTE_LOAD_SECTION                          (optional)
<route-id> <number>
...
-1
EOF
```

### 6.2 Structural rules and semantic invariants

1. **Header keywords**:
   - `NAME` is required and identifies the solution document.
   - `TYPE` is always `TOUR` ([spec §1.1.2](./tsplib95_format.md#112-type-string)) in a solution document; problem files declare their own problem `TYPE` from [§3.3](#33-problem-type-vocabulary).
   - `PROBLEM` is required and names the problem instance this solution solves (typically matching the problem's `NAME`).
   - `DIMENSION` is optional; when present, it equals the total node count (customers plus depots) of the linked problem.
   - `COST` is optional and records the total objective value stated by the solution source as an integer or real number.
2. **Depot declaration (`DEPOT_SECTION`)**:
   - Reuses the core `DEPOT_SECTION` grammar ([spec §1.2.2](./tsplib95_format.md#122-depot_section)): one 1-based problem depot node ID per line, terminated by `-1`.
   - Present when routes originate at one or more depots (CVRPLIB/Solomon `.sol` and Cordeau `.res`); omitted for depot-free tours (`.opt.tour`).
   - Depot node IDs match the problem's own `DEPOT_SECTION`: node `1` for single-depot `.vrp` and converted Solomon/Homberger instances, and nodes `n + 1 .. n + t` for Cordeau multi-depot instances.
3. **Route tables (`ROUTE_*_SECTION`)**:
   - Every `ROUTE_*_SECTION` is terminated by a standalone `-1` line.
   - `<route-id>` is a 1-based contiguous integer `1..m`, where $m$ is the number of routes in `ROUTE_SECTION`.
   - `ROUTE_SECTION` is required. Each line begins with `<route-id>` followed by the ordered, space-separated sequence of 1-based problem customer node IDs visited on that route (excluding the start/end depot). An empty route has `<route-id>` alone on its line.
   - `ROUTE_DEPOT_SECTION` is present if and only if `DEPOT_SECTION` is present. Each line `<route-id> <depot-node-id>` assigns route `<route-id>` to a depot node ID that appears in `DEPOT_SECTION`.
   - `ROUTE_COST_SECTION` and `ROUTE_LOAD_SECTION` are optional; when present, each contains one `<route-id> <value>` line for every route `1..m` in `ROUTE_SECTION`.
   - Every customer node ID in `ROUTE_SECTION` must lie in `1..DIMENSION` and must not appear in `DEPOT_SECTION`.

### 6.3 Worked solution examples

#### Depot-free TSP tour (`gr48.opt.tour`)

```text
NAME : gr48.opt.tour
COMMENT : Optimal tour for gr48 (5046)
TYPE : TOUR
PROBLEM : gr48
DIMENSION : 48
COST : 5046
ROUTE_SECTION
1 1 25 32 23 14 27 48 16 11 26 20 38 41 33 21 30 43 35 12 36 7 18 39 37 6 29 5 44 24 10 45 15 40 19 42 13 46 31 22 3 28 8 4 34 47 9 2 17
-1
EOF
```

#### Single-depot CVRPTW solution (`C101.sol`, first 3 of 10 routes)

In the problem file converted from `C101.txt` ([§7.3](#73-solomon-and-homberger-cvrptw-instances-txt)), the depot is node `1` and customer $k \in \{1..100\}$ is node $k + 1 \in \{2..101\}$:

```text
NAME : C101
TYPE : TOUR
PROBLEM : C101
DIMENSION : 101
COST : 827.3
DEPOT_SECTION
1
-1
ROUTE_SECTION
1 6 4 8 9 11 12 10 7 5 3 2 76
2 14 18 19 20 16 17 15 13
3 21 25 26 28 30 31 29 27 24 23 22
-1
ROUTE_DEPOT_SECTION
1 1
2 1
3 1
-1
EOF
```

#### Multi-depot MDVRP solution (`p01.res`, 4 depots at nodes `51..54`, first 4 of 11 routes)

In `p01` ([§7.2](#72-cordeau-multi-depot-and-periodic-vrp-instances)), customers are nodes `1..50` and the four depots are nodes `51..54`:

```text
NAME : p01
TYPE : TOUR
PROBLEM : p01
DIMENSION : 54
COST : 576.87
DEPOT_SECTION
51
52
53
54
-1
ROUTE_SECTION
1 44 45 33 15 37 17 42 19 40 41 13 18
2 46 12 5 47 4
3 48 23 7 43 24 6
4 49 10 39 30 34 9 50 16 21 29
-1
ROUTE_DEPOT_SECTION
1 51
2 51
3 51
4 52
-1
ROUTE_COST_SECTION
1 163.30
2 65.06
3 79.66
4 103.52
-1
ROUTE_LOAD_SECTION
1 77
2 55
3 53
4 76
-1
EOF
```

---

## 7. Accepted input formats and conversions

### 7.1 Native TSPLIB95 and TSPLIB-extended files (`.tsp`, `.atsp`, `.sop`, `.hcp`, `.vrp`)

Files that already follow the keyword-colon specification part ([§3](#3-problem-specification-part-header-keywords)) and section-keyword data part ([§4](#4-problem-data-part-data-sections)) are parsed directly by `FormatParser.parse_file()`:

- `FormatParser` extracts the declared `TYPE` header, normalizes it via `normalize_problem_type()` ([§3.3](#33-problem-type-vocabulary)), and dispatches to `StandardProblem` or `ExtendedProblem` via `get_problem_class_for_type()`.
- File extensions (`.tsp`, `.atsp`, `.sop`, `.hcp`, `.vrp`, `.tour` in `EXTENSION_TYPE_HINTS`) are used only as diagnostic hints; the declared `TYPE` header governs class dispatch.

### 7.2 Cordeau multi-depot and periodic VRP instances

Cordeau benchmark files (`p01`..`p23`, `pr01`..`pr10`) have no keyword headers and use a positional whitespace-separated layout parsed by `CordeauParser` (`src/tsplib_parser/cordeau/cordeau_parser.py`):

1. **Line 1 (header)**: `<type> <m> <n> <t>`
   - `<type>`: integer code in `0..7` (`0` = `TSP`, `1` = `CVRP`, `2` = `MDVRP`, `3` = `SDVRP`, `4` = `VRPTW`, `5` = `PVRPTW`, `6` = `MDVRPTW`, `7` = `SDVRPTW`; for `PVRP`, the corpus encodes `<type> = 1` with `<t> > 1`).
   - `<m>`: vehicles per depot.
   - `<n>`: number of customers.
   - `<t>`: number of depots (`MDVRP`, `MDVRPTW`) or number of periods (`PVRP`, `PVRPTW`).
2. **Lines `2 .. t + 1` (per-depot / per-period constraints)**: `<D> <Q>`
   - `<D>`: maximum route duration/distance (`0` means unconstrained).
   - `<Q>`: maximum vehicle load capacity.
3. **Lines `t + 2 .. t + 1 + n` (customer lines, IDs `1..n`)**:
   - Without time windows: `<i> <x> <y> <d> <q> <f> <a_1> ... <a_f>` (`<i>` node ID, `<x> <y>` coordinates, `<d>` service duration, `<q>` demand, `<f>` visit frequency, followed by `<f>` visit-combination integers).
   - With time windows: `<i> <x> <y> <d> <q> <f> <a_1> ... <a_f> <e> <l>` (`<e> <l>` earliest and latest service start times).
4. **Lines `t + 2 + n .. t + 1 + n + t` (depot lines, IDs `n + 1 .. n + t`)**:
   - Same column layout as customer lines, with `<q> = 0` and `<f> = 0`.

#### Conversion to TSPLIB-extended (`CordeauConverter.to_tsplib`)

- **Header**: Emits `NAME`, `COMMENT`, `TYPE` (`MDVRP` or `MDVRPTW`), `DIMENSION : n + t`, `EDGE_WEIGHT_TYPE : EUC_2D`, and `VEHICLES : m * t`.
- **Node numbering**: Preserves the source file's 1-based IDs without renumbering — customers remain `1..n` and depots remain `n + 1 .. n + t` in `NODE_COORD_SECTION` and `DEMAND_SECTION`, and `DEPOT_SECTION` lists `n + 1 .. n + t` terminated by `-1`.
- **Depot constraints**:
  - When all $t$ depots share the same `<Q>`, emits `CAPACITY : <Q>`; when `<Q>` varies across depots, emits `DEPOT_CAPACITY_SECTION` with `<depot_ordinal> <Q>` for `1..t`.
  - When all $t$ depots share the same positive `<D>`, emits `DISTANCE : <D>`; when `<D>` varies across depots, emits `DEPOT_DURATION_SECTION` with `<depot_ordinal> <D>` for `1..t`.
- **Time windows and service times**: Emits `TIME_WINDOW_SECTION` (`<node> <e> <l>`) when any node specifies time windows, and `SERVICE_TIME_SECTION` (`<node> <d>`) when any node has `<d> > 0`.

### 7.3 Solomon and Homberger CVRPTW instances (`.txt`)

Solomon and Homberger `.txt` files encode single-depot `CVRPTW` instances in two textual spellings:

1. **Headered Solomon/Homberger layout**:
   - Line 1: `<instance-name>`
   - Line 4: `VEHICLE`
   - Line 5: `NUMBER     CAPACITY`
   - Line 6: `<vehicles> <capacity>`
   - Line 9: `CUSTOMER` header followed by 7-column node rows (`CUST NO.  XCOORD.  YCOORD.  DEMAND  READY TIME  DUE DATE  SERVICE TIME`) starting with `0` (the depot) and continuing through `1..N` (customers).
2. **Bare 7-column layout**:
   - No text header; every non-empty line is `<id> <x> <y> <demand> <ready_time> <due_date> <service_time>` for `id = 0..N` (where row `0` is the depot with `demand = 0`).

#### Conversion to TSPLIB-extended

- Emits `TYPE : CVRPTW`, `DIMENSION : N + 1`, `EDGE_WEIGHT_TYPE : EUC_2D`, `VEHICLES` and `CAPACITY` (when present in the header), `NODE_COORD_SECTION`, `DEMAND_SECTION`, `TIME_WINDOW_SECTION`, `SERVICE_TIME_SECTION`, and `DEPOT_SECTION`.
- **Node ID shift (`+1`)**: Because TSPLIB95 node IDs are 1-based ([§2.1](#21-lexical-conventions)), every source node ID $i \in \{0..N\}$ is shifted to $i + 1 \in \{1..N + 1\}$. The depot (`0` in the `.txt` file) becomes node `1` in `DEPOT_SECTION`, and customer $k \in \{1..N\}$ becomes node $k + 1 \in \{2..N + 1\}$.

### 7.4 Solution input formats (`.opt.tour`, `.sol`, `.res`)

Three native solution formats are accepted and converted into the canonical `TYPE : TOUR` solution document ([§6](#6-solution-format-specification)):

#### TSPLIB `.opt.tour` (`TYPE : TOUR`)

- **Native grammar**: Standard TSPLIB95 file declaring `TYPE : TOUR` and a `TOUR_SECTION` ([spec §1.2.7](./tsplib95_format.md#127-tour_section)) containing 1-based problem node IDs terminated by `-1`.
- **Conversion to canonical solution**: Preserves the 1-based node IDs verbatim as route `1` in `ROUTE_SECTION` (joining wrapped multi-line tours into a single route line), sets `PROBLEM` from the stem before `.opt.tour`, and extracts any parenthetical objective value from `COMMENT` into `COST` when numeric.

#### CVRPLIB and Solomon/Homberger `.sol`

- **Native grammar**:
  - One or more route lines matching `^Route\s+#(\d+)\s*:\s*(.*)$`, where the right-hand side is a space-separated list of **1-based customer ordinals** (`1..N`, with the depot omitted).
  - A trailing summary line matching `^Cost\s+([+-]?\d+(?:\.\d+)?)$` (case-insensitive), optionally followed by `Time` lines.
- **Conversion to canonical solution**:
  - Because the single depot is node `1` in both native `.vrp` files and converted `.txt` files ([§7.3](#73-solomon-and-homberger-cvrptw-instances-txt)), every customer ordinal $k \in \{1..N\}$ in a `Route #r:` line represents problem node ID $k + 1 \in \{2..N + 1\}$.
  - Emits `DEPOT_SECTION` with `1`, shifts each customer ordinal $k \mapsto k + 1$ in `ROUTE_SECTION`, emits `ROUTE_DEPOT_SECTION` mapping each route `<r> 1`, and copies the stated `Cost` value into `COST`.

#### Cordeau `.res`

- **Native grammar**:
  - Line 1: `<total_cost>` (`float`, optionally followed by CPU runtime numbers on the same line).
  - Subsequent lines (one per route): `<l> <k> <d> <q> <list of customer node IDs>`, where `<l>` is the 1-based depot ordinal (`1..t`), `<k>` is the per-depot vehicle number, `<d>` is the route duration/cost (`float`), `<q>` is the route load (`int`), and `<list>` is the space-separated sequence of 1-based problem customer node IDs (`1..n`), optionally leading and trailing with `0` depot markers.
- **Conversion to canonical solution**:
  - Strips any leading or trailing `0` tokens from `<list>`.
  - Keeps customer node IDs `1..n` unchanged in `ROUTE_SECTION` (since Cordeau conversion preserves customer IDs `1..n`, [§7.2](#72-cordeau-multi-depot-and-periodic-vrp-instances)).
  - Resolves depot ordinal `<l>` (`1..t`) to its 1-based problem depot node ID `DEPOT_SECTION[l - 1]` (`n + l`) in `ROUTE_DEPOT_SECTION`.
  - Records `<d>` in `ROUTE_COST_SECTION`, `<q>` in `ROUTE_LOAD_SECTION`, and `<total_cost>` in `COST`.

---

## 8. Numbering and index frames

Every file on disk uses **1-based** numbering, while `ParseResult` and database/Parquet tables use **0-based** indexing.

| Artifact | Depot node ID(s) | Customer node IDs | Mapping to 0-based `ParseResult["coords"]` index |
| --- | --- | --- | --- |
| Native TSPLIB `.tsp` / `.atsp` / `.sop` / `.hcp` | none | `1..n` | $\text{index} = \text{id} - 1$ |
| Native CVRPLIB `.vrp` (single depot at node `1`) | `1` | `2..n` | $\text{index} = \text{id} - 1$ (depot at `0`, customer $k$ at `k`) |
| Converted Solomon / Homberger `.txt` ([§7.3](#73-solomon-and-homberger-cvrptw-instances-txt)) | `1` (shifted from `0`) | `2..N + 1` (shifted from `1..N`) | $\text{index} = \text{id} - 1$ (depot at `0`, original customer $k$ at `k`) |
| Converted Cordeau instance ([§7.2](#72-cordeau-multi-depot-and-periodic-vrp-instances)) | `n + 1 .. n + t` | `1..n` | $\text{index} = \text{id} - 1$ (customer $i$ at `i - 1`, depot $l$ at `n + l - 1`) |
| Canonical `TYPE : TOUR` solution ([§6.1](#61-canonical-solution-document-grammar)) | matches problem `DEPOT_SECTION` | matches problem customer node IDs | $\text{index} = \text{id} - 1$ |
| Native `.opt.tour` ([§7.4](#74-solution-input-formats-opttour-sol-res)) | none | `1..n` (problem node IDs) | $\text{index} = \text{id} - 1$ |
| Native `.sol` ([§7.4](#74-solution-input-formats-opttour-sol-res)) | omitted (implicit depot at `0`-based index `0`) | `1..N` (customer ordinals) | $\text{index} = \text{ordinal}$ (since depot occupies `0`-based index `0`) |
| Native `.res` ([§7.4](#74-solution-input-formats-opttour-sol-res)) | depot ordinal `l` in `1..t` | `1..n` (problem customer node IDs) | customer $\text{index} = \text{id} - 1$; depot $\text{index} = \text{DEPOT\_SECTION}[l - 1] - 1$ |

---

## 9. Validation invariants

Validation is separate from grammar tokenization ([`src/tsplib_parser/validation.py`](../../src/tsplib_parser/validation.py)) and executes in two stages during `FormatParser.parse_file()`:

### 9.1 Stage 1 — Pre-extraction 1-based specification validation (`validate_problem`)

- **Required header presence**: `TYPE` must be non-empty and normalize to a member of `problem_class.allowed_problem_types` ([§3.3](#33-problem-type-vocabulary)). For all non-`TOUR` problems, `DIMENSION` must be a positive integer (`>= 1`).
- **Weight-source completeness**: Every weight-bearing problem (`TSP`, `ATSP`, `SOP`, `CVRP`, and extended routing variants) must declare either `EDGE_WEIGHT_TYPE` ([§5](#5-distance-functions)) or `EDGE_DATA_FORMAT` ([§3.1](#31-core-tsplib95-keywords)). When `EDGE_WEIGHT_TYPE` is `EXPLICIT`, `EDGE_WEIGHT_FORMAT` must be a valid member of `MATRIX_EDGE_WEIGHT_FORMATS | FUNCTIONAL_EDGE_WEIGHT_FORMATS` ([§4.3](#43-explicit-matrix-formats)).
- **Coordinate count and dimensionality**: When `NODE_COORD_SECTION` is present, it must contain exactly `DIMENSION` entries keyed `1..DIMENSION`, and every coordinate tuple must match the dimension required by `NODE_COORD_TYPE` or `EDGE_WEIGHT_TYPE` (`2` for `TWOD_COORDS` / `TWOD_WEIGHT_TYPES`, `3` for `THREED_COORDS` / `THREED_WEIGHT_TYPES`). When `DISPLAY_DATA_SECTION` is present, it must contain `DIMENSION` 2-D coordinate tuples.
- **CVRP and extended VRP completeness**: When `DEMAND_SECTION` is present, it must contain `DIMENSION` entries and must be accompanied by a positive `CAPACITY` header or a `DEPOT_CAPACITY_SECTION` ([§4.2](#42-extended-data-sections)). Every depot node ID in `DEPOT_SECTION` must lie in `1..DIMENSION`.

### 9.2 Stage 2 — Post-extraction 0-based contract validation (`validate_parse_result`)

- **Top-level contract keys**: `ParseResult` must contain `problem_data`, `coords`, `display_coords`, `demands`, `depots`, `edges`, `fixed_edges`, `tours`, and `metadata`.
- **0-based array lengths and bounds**:
  - When non-empty, `coords`, `display_coords`, and `demands` must each have length `DIMENSION`.
  - Every depot index in `depots`, every endpoint in `edges` and `fixed_edges`, and every node index in `tours` must be an integer in `0 .. DIMENSION - 1`.
- **Extended section shapes**: When present in `problem_data`, `time_windows` must have shape `DIMENSION x 2` and `service_times` must have shape `DIMENSION x 1`.
