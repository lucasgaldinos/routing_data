---
title: "TSPLIB and extended TSPLIB formats"
description: >
  Single authoritative description of every file format this project reads and
  writes: TSPLIB95 core, the LKH-3 extensions, the Cordeau and Solomon/Holmberger
  native families, the three corpus solution formats, and the project-defined
  extended tour document that carries multi-route solutions.
created: 2026-10-25
status: review
type: guide
scope: global
modifications:
  - date_modified: 2026-10-25
    modifications:
      - description: >
          Created as the unified format reference. Supersedes the format sections
          of tsplib95_format.md, LKH-3-Keld-Helsgaun.md,
          courdeau-instances-description.md and solomon-instances-description.md,
          and defines the .opt.tour, .sol and .res grammars plus the
          project-defined ROUTE_SECTION solution document, none of which had a
          specification before.
  - date_modified: 2026-10-26
    modifications:
      - description: >
          Replaced the invented DEPOTS header with the spec's DEPOT_SECTION in
          the canonical solution document, the Solomon conversion target and
          both worked examples; repaired four reference-style links that had no
          definition and two broken heading anchors; corrected the MDVRP row
          against the LKH-3 reference, which lists MDMTSP and not MDVRP; renamed
          this document's decision namespace from D to FMT so it stops colliding
          with the architecture decision log; restated COM-002 because the
          non-commercial licence covers the solver, not this parser.
      - description: >
          Removed the second node numbering. The canonical document now uses
          TSPLIB node ids everywhere: the C101 example lists depot node 1
          instead of a depot 0 that no problem file contains, and its route
          values are shifted onto node ids. One corpus counter-example would
          have been enough to catch the original mistake: every .vrp file
          starts DEPOT_SECTION at node 1 (eil13.vrp:32-34, Li_21.vrp:1132-1134).
      - description: >
          Dropped two canonical-document keywords that carried no information:
          NODE_ID_SCHEME had a single legal value, and VEHICLES was a checksum
          of the ROUTE_SECTION line count. Named the full extended TYPE
          vocabulary instead of the 20-value subset, and recorded that the
          undefined TRPP token was removed and class dispatch now normalizes the
          declared type.
      - description: >
          Removed the coloured-TSP family from the accepted vocabulary: CTSP,
          CTSP-D, GCTSP, CCCTSP, MSCTSP, PCTSP, CBTSP and CBNTSP all need
          CTSP_SET_SECTION, whose grammar the source of record never publishes.
          Recorded the exact vocabulary size (7 core + 46 extended) and a
          per-folder parse sample taken on 2026-10-26.
related_files:
  - "[TSPLIB 95 (Reinelt), local copy](./tsplib95_format.md)"
  - "[LKH-3 (Helsgaun), local copy](./LKH-3-Keld-Helsgaun.md)"
  - "[Cordeau instance and solution description](./courdeau-instances-description.md)"
  - "[Solomon instance and solution description](./solomon-instances-description.md)"
  - "[Architecture decision log](./ARCHITECTURE_DECISIONS.md)"
  - "[Format expansion plan](../../src/tsplib_parser/TODO.md)"
tags:
  - notes/format-spec
  - analysis/format
  - guide/reference
  - data-formatting/file-formats
  - notes/tsplib
  - notes/lkh3
  - notes/cvrplib
  - notes/cordeau
  - notes/solomon
  - notes/solutions
  - analysis/numbering
  - notes/indexing
  - notes/corpus
  - guide/parser
---

# TSPLIB and extended TSPLIB formats

## 1. Purpose and scope

This document is the single description of the file formats this repository reads and writes.
It replaces, for format purposes, the four earlier reference documents listed above; those stay in the tree as provenance for the upstream text they copy, but they are no longer the place to look up a grammar.

Scope:

- the TSPLIB95 core grammar, keyword vocabulary and distance functions;
- the LKH-3 extension keywords and sections;
- the two native problem families that are converted into the TSPLIB dialect (Cordeau, Solomon/Holmberger);
- the three solution families found in the corpus and the one solution document this project defines.

Out of scope: storage decisions (DuckDB tables, parquet layout, JSON writers), CLI behaviour, and the solver side of LKH-3.
Those are covered by `docs/ARCHITECTURE.md` and the two `TODO.md` registers.

Audience: anyone writing a parser, a converter or a validator for this repository, and anyone reviewing such a change.
The document assumes the corpus in `datasets_raw/**` is read-only.

> [!IMPORTANT]
> One format in this document is defined by this project and by nothing else: the `ROUTE_SECTION` solution document of §10.4.
> It is not TSPLIB95, not TSPLIB, and not LKH-3. Every place it is mentioned carries that label. Do not cite it as an upstream format.

## 2. Definitions

| Term | Meaning in this document |
| --- | --- |
| TSPLIB95 | The instance library and file format published by Gerhard Reinelt, described by [TSPLIB95 spec](./tsplib95_format.md). Cited as "spec §x.y" below. |
| LKH-3 | Helsgaun's Lin-Kernighan solver and its TSPLIB extension, described by [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) and [LKH-3 report](./lkh-3.pdf). Cited as "LKH-3 §x". |
| TSPLIB-extended | TSPLIB95 core plus the LKH-3 additions plus the project-defined keywords of §8. The dialect every converter emits. |
| native format | A third-party layout that is not keyword-driven: Cordeau (positional), Solomon/Holmberger (positional blocks), CVRPLIB solutions (line-prefixed). |
| problem file | A file that states an instance: `.tsp`, `.atsp`, `.sop`, `.hcp`, `.vrp`, `.txt`, and the suffix-less Cordeau files. |
| solution file | A file that states routes and, optionally, a cost: `.opt.tour`, `.sol`, `.res`. |
| node id | The integer a file uses for a node. TSPLIB node ids are 1-based. |
| depot number | The position of a depot inside `DEPOT_SECTION`, counting from 1. Independent of the depot's node id. |
| array index | A position inside a `ParseResult` array (`coords`, `demands`, `depots`, …). Always 0-based. |
| index frame | The rule that maps a file's node id (or depot number) to an array index. §12. |
| route | One vehicle's ordered customer sequence, starting and ending at one depot, or a closed cycle when the problem has no depot. |
| cycle | A closed tour that visits every node once and has no depot; the only shape a `TOUR_SECTION` can express for a TSP/HCP instance. |
| stated cost | A number written in a solution file. Not necessarily equal to a recomputation; §10 records the convention per family. |
| canonical solution document | The project-defined `ROUTE_SECTION` document of §10.4. |

Symbols used in §7:

| Symbol | Meaning |
| --- | --- |
| $d_{ij}$ | edge weight (distance) between node $i$ and node $j$ |
| $x_i, y_i, z_i$ | coordinates of node $i$ |
| $\operatorname{nint}(x)$ | nearest integer, TSPLIB's C `nint`: add 0.5, truncate toward zero |

$$\begin{equation}
d_{ij} = \operatorname{nint}\left(\sqrt{(x_i - x_j)^2 + (y_i - y_j)^2}\right)
\end{equation}$$

## 3. Provenance and authority

Every format below belongs to exactly one of four authorities.
When this document and a source disagree, §13 records the disagreement instead of silently choosing a side.

| Format element | Authority | Source of record | Implemented |
| --- | --- | --- | --- |
| core grammar, `NAME`…`EOF`, all `*_SECTION` of §1.2 | upstream TSPLIB95 | spec §1, [TSPLIB95 spec](./tsplib95_format.md); [TSPLIB95 PDF](./tsplib95_specification.pdf) | yes, `src/tsplib_parser/` |
| core `TYPE` vocabulary (TSP, ATSP, SOP, HCP, CVRP, TOUR) | upstream TSPLIB95 | spec §1.1.2 | yes |
| distance functions of §2.1–§2.7 | upstream TSPLIB95 | spec §2; [TSPLIB95 PDF](./tsplib95_specification.pdf) | yes, `src/converter/utils/cost.py` |
| `VEHICLES`, `SALESMEN`, `DISTANCE`, `RISK_THRESHOLD`, `SCALE`, `GRID_SIZE`, `SERVICE_TIME` | upstream LKH-3 | LKH-3 §3.1.1, [LKH-3 report](./lkh-3.pdf); [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) | partly, see §8 |
| `BACKHAUL_SECTION`, `PICKUP_AND_DELIVERY_SECTION`, `SERVICE_TIME_SECTION`, `TIME_WINDOW_SECTION`, `REQUIRED_NODES_SECTION`, `CTSP_SET_SECTION` | upstream LKH-3 | LKH-3 §3.1.2, [LKH-3 report](./lkh-3.pdf) | sections 1–4 yes |
| `EXACT_2D/3D`, `FLOOR_2D/3D`, `TOR_2D/3D` | upstream LKH-3 | LKH-3 §3.1.1, [LKH-3 report](./lkh-3.pdf) | **no** |
| Cordeau instance and `.res` layout | third party (UMA / Cordeau) | [Cordeau description](./courdeau-instances-description.md); corpus `datasets_raw/umalaga/mdvrp/` | instance yes, `.res` no |
| Solomon/Holmberger `.txt` layout | third party (UMA / Gehring–Homberger) | [Solomon description](./solomon-instances-description.md); corpus `datasets_raw/cvrplib/Holmberger/`, `.../Vrp-Set-Solomon/` | **no** (planned, [format expansion plan](../../src/tsplib_parser/TODO.md) §10.2) |
| CVRPLIB `.sol` layout | third-party community convention, undocumented upstream | corpus only; measured in §10.2 | yes, in `src/converter/core/solutions.py` |
| TSPLIB `.opt.tour` layout | upstream TSPLIB95 (file naming convention of the distribution) | spec §1.2.7, §3.1 (`.opt.tour` suffix); [TSPLIB95 spec](./tsplib95_format.md) | yes, in `src/converter/core/solutions.py` |
| `PERIODS`, `CAPACITY_VOL`, `CAPACITY_WEIGHT` | **this project** | absent from both LKH-3 sources and the corpus | yes, `ExtendedProblem` |
| `DEPOT_CAPACITY_SECTION`, `DEPOT_DURATION_SECTION` | **this project** | absent from both LKH-3 sources | yes, emitted by `src/tsplib_parser/cordeau/cordeau_converter.py:104,110` |
| `PROBLEM`, `COST`, `ROUTE_SECTION`, `VEHICLES`-as-route-count | **this project** | this document, §10.4 | no |

> [!WARNING]
> The five project-defined problem keywords are an extension of an extension.
> A file that uses `DEPOT_CAPACITY_SECTION`, `DEPOT_DURATION_SECTION`, `PERIODS`, `CAPACITY_VOL` or `CAPACITY_WEIGHT` is **not** readable by an LKH-3 binary, and the LKH-3 report states that LKH-3 "at present only allows one depot" ([LKH-3 report](./lkh-3.pdf), §3.1.2).
> The Cordeau converter emits `TYPE : MDVRP` with a multi-node `DEPOT_SECTION` (`src/tsplib_parser/cordeau/cordeau_converter.py`). See §13.

Rejected in problem files, and mentioned nowhere else: `DEPOTS`.
The keyword is absent from the spec, from both LKH-3 sources and from the corpus; a problem file that carries it is stripped without being recorded (`_DERIVED_HEADER_FIELDS`).
A solution does not need it either: its depots are the `DEPOT_SECTION` of [§10.4](#104-the-canonical-solution-document).

## 4. Requirements, constraints and guidelines

- **REQ-001**: every format claim in project documentation cites either a source section or a corpus measurement naming the file path.
- **REQ-002**: the parser accepts every corpus file whose role is "problem" in [§11](#11-role-and-format-of-every-corpus-file-type) without raising.
- **REQ-003**: a solution document preserves the source's node sequence exactly, in order, with no id remapping inside the document.
- **REQ-004**: node ids inside a solution file and inside a solution document are 1-based and equal the problem file's node numbers, except where [§10.3](#103-res) states the source uses a different numbering.
- **REQ-005**: `DIMENSION` in a solution document equals the linked problem's `DIMENSION`.
- **REQ-006**: importing `.sol`, `.res` or `.opt.tour` copies the stated cost verbatim; recomputation is a separate, explicitly requested step.
- **REQ-007**: any array that crosses a package boundary is 0-based (`ParseResult`), per [architecture decisions](./ARCHITECTURE_DECISIONS.md#d3--1-based-tsplib-to-0-based-database-index-conversion) D3.
- **REQ-008**: an `EDGE_WEIGHT_TYPE` without an implementation raises a typed unsupported-feature error; it must never produce a number.
- **REQ-009**: a new native family is added as a front end that emits the TSPLIB-extended dialect, never as a new downstream schema ([format expansion plan](../../src/tsplib_parser/TODO.md) §10.1).
- **REQ-010**: a solution and a problem are linked by the rules of [§10.7](#107-linking-a-solution-to-a-problem), never by the solution's `NAME` value.
- **CON-001**: nothing under `datasets_raw/` is modified, generated into, or written by tests.
- **CON-002**: a route occupies exactly one physical line; the canonical parser rejects a wrapped route.
- **CON-003**: a file's role is never inferred from its suffix alone (`.tour` is a solution, `.txt` is a problem, Cordeau instances have no suffix).
- **CON-004**: the project-defined document never carries a `*.tsp`, `*.vrp` or `*.tour` suffix, and its `TYPE` is always `TOUR`.
- **GUD-001**: use an LKH-3 keyword when one exists; invent a keyword only when none does, and record it in the provenance table of [§3](#3-provenance-and-authority).
- **GUD-002**: keep the canonical document minimal — derived values are recomputed by the validator, not stored.
- **PAT-001**: a native family is an island with `*_types.py`, `*_parser.py`, `*_converter.py` and `to_parse_result()`, following `src/tsplib_parser/cordeau/`.
- **PAT-002**: one canonical representation, N front ends; no per-format branch downstream of the front end.

## 5. The common grammar

### 5.1 Header lines

A header line is `<KEYWORD> : <value>` (spec §1.1).
The keyword is alphanumeric and uppercase; the value is a string, an integer or a real.

Measured over `datasets_raw/**`, writers are inconsistent about the colon:

| Spelling | Example file | Line |
| --- | --- | --- |
| no space before the colon | `datasets_raw/problems/tsp/gr48.tsp` | `NAME: gr48` |
| one space on both sides | `datasets_raw/cvrplib/vrp-XXL/Brussels1.vrp` | `NAME :  Brussels1` (two spaces after the colon) |
| no colon at all | `datasets_raw/problems/tsp/gr48.tsp` | `EDGE_WEIGHT_SECTION` (a section marker, not a header) |

A reader must accept any amount of whitespace around the colon, and must accept a header value containing spaces (spec §1.1.3 allows free text in `COMMENT`).

The order of headers is arbitrary in principle but must be self-consistent (spec §1.1).
A reader must therefore parse all headers before interpreting any section, which is what `StandardProblem.parse` does in two passes (`src/tsplib_parser/models.py:157-186`).

### 5.2 Sections and terminators

A data section begins with a line holding a `*_SECTION` keyword (spec §1.2).
Its length is either implicit — derived from `DIMENSION` and another keyword — or explicit, ended by a terminator.

| Section | Terminator | Terminator count | Source |
| --- | --- | --- | --- |
| `NODE_COORD_SECTION` | none (length from `DIMENSION`) | — | spec §1.2.1 |
| `DEMAND_SECTION` | none (length from `DIMENSION`) | — | spec §1.2.3 |
| `DEPOT_SECTION` | `-1` | 1 | spec §1.2.2 |
| `EDGE_DATA_SECTION`, `EDGE_LIST` | `-1` | 1 | spec §1.2.4 |
| `EDGE_DATA_SECTION`, `ADJ_LIST` | `-1` per node, plus one final `-1` | 2 | spec §1.2.4 |
| `FIXED_EDGES_SECTION` | `-1` | 1 | spec §1.2.5 |
| `TOUR_SECTION` | `-1` per tour, plus one final `-1` | 2 | spec §1.2.7 |
| `EDGE_WEIGHT_SECTION` | none (length from `DIMENSION` and `EDGE_WEIGHT_FORMAT`) | — | spec §1.2.8 |
| `DISPLAY_DATA_SECTION` | none (length from `DIMENSION`) | — | spec §1.2.6 |
| `ROUTE_SECTION` | `-1` | 1 | this project, [§10.4](#104-the-canonical-solution-document) |

`EOF` terminates the file and is optional (spec §1.1.11).
Measured 2026-10-25: 12 of 512 TSPLIB-layout corpus files carry no `EOF` — `problems/tsp/usa13509.tsp`, `problems/tsp/pr1002.tsp`, `problems/tour/a280.opt.tour`, `problems/tour/brg180.opt.tour`, `problems/tour/ch130.opt.tour`, `problems/tour/ulysses22.opt.tour`, each shipped twice.
A reader must therefore treat end-of-file as an implicit section terminator, and must not require the `-1` of a `TOUR_SECTION` to be followed by `EOF`.

Measured 2026-10-25: 82 of 82 `*.opt.tour` files carry exactly one `-1` line, so the "one `-1` per tour" rule has no multi-tour exemplar in the corpus even though the spec allows it.

### 5.3 Comments, blank lines, encoding, line endings

- Blank lines are ignored everywhere (spec does not forbid them; the tokenizer skips them, `src/tsplib_parser/tokenization.py:70`).
- A line whose first non-blank character is `#` is a comment and is ignored everywhere (`src/tsplib_parser/tokenization.py:70`). Measured 2026-10-25: no corpus file contains one, so the rule is implementation-defined rather than corpus-verified.
- Text is decoded as UTF-8, falling back to latin-1 on the first non-UTF-8 byte (`src/tsplib_parser/parser.py:147-151`, `src/converter/core/solutions.py:76-90`).
- LF and CRLF are both accepted. Measured 2026-10-25: 10 corpus files use CRLF, all in `datasets_raw/cvrplib/vrp-XXL/` (`Antwerp1.vrp`, `Antwerp2.vrp`, `Leuven1.vrp`, and seven siblings).

### 5.4 Deviations from the core grammar measured in the corpus

| Deviation | Count | Where | What a reader must do |
| --- | --- | --- | --- |
| `EDGE_WEIGHT_SECTION` prefixed by one integer equal to `DIMENSION` | 41 unique SOP files (82 shipped twice) | `datasets_raw/problems/sop/*.sop`, `datasets_raw/zips/all_problems/sop/*.sop` | drop the leading token when, and only when, its value equals `DIMENSION` and the remaining count matches the declared format |
| `*_DIAG_ROW` declared but the zero diagonal omitted | 3 unique files (6 shipped twice): `eil7.vrp`, `eil13.vrp`, `eil31.vrp` | `datasets_raw/problems/vrp/` | interpret as the corresponding no-diagonal format when the count matches exactly |
| three coordinate columns without `NODE_COORD_TYPE : THREED_COORDS` | 2 unique files (4 shipped twice): `xray14012_1.tsp`, `xray14012_2.tsp` | `datasets_raw/problems/tsp/` | accept three columns when the section carries three |
| no `EOF` | 6 unique files (12 shipped twice) | see [§5.2](#52-sections-and-terminators) | end the file at end-of-file |
| `EDGE_WEIGHT_FORMAT : FUNCTION` written for coordinate-based problems | 2 unique files (4 shipped twice): `burma14.tsp`, `gr431.tsp` | `datasets_raw/problems/tsp/` | `FUNCTION` means "computed from coordinates", never a matrix layout |

Both matrix deviations are handled in `StandardProblem.create_explicit_matrix` (`src/tsplib_parser/models.py:196-246`), which documents the same two cases and raises on any other element count.
A parser that silently truncates or pads is non-conforming with this document.

## 6. Type vocabulary

### 6.1 Core `TYPE` values

Spec §1.1.2 defines six values.
Measured 2026-10-25 over the 512 TSPLIB-layout problem and tour files:

| `TYPE` value | Spec | Admitted by `StandardProblem` | Corpus files | Note |
| --- | --- | --- | ---: | --- |
| `TSP` | yes | yes | 220 | |
| `TSP (M.~Hofmeister)` | no (parenthetical qualifier) | after normalization | 6 | `src/tsplib_parser/types.py:196-212` strips the parenthetical |
| `ATSP` | yes | yes | 38 | |
| `SOP` | yes | yes | 82 | |
| `HCP` | yes | yes | 18 | |
| `CVRP` | yes | yes | 66 | |
| `TOUR` | yes | yes | 82 | a solution, not a problem, in all 82 corpus files |
| `VRP` | **no** | via alias `VRP → CVRP` | 0 | see [§13](#13-spec-versus-code) item 1 |

### 6.2 Aliases

`PROBLEM_TYPE_ALIASES` maps `VRP` to `CVRP` (`src/tsplib_parser/types.py:85-90`).
The alias exists in code only: spec §1.1.2 lists no `VRP` value, and no corpus file declares one.
Its purpose is to accept the umbrella spelling of third-party VRP sources, not to describe TSPLIB95.

### 6.3 Extended `TYPE` values

`EXTENDED_PROBLEM_TYPES` (`src/tsplib_parser/types.py:112`) is the vocabulary `ExtendedProblem` admits: the 7 tokens of §6.1 (`VRP` alias included) plus the 47 values below.

Three accepted tokens have no counterpart in the [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) capability list, and none of them is an oversight:

- `MDVRP` and `MDVRPTW` are the project's multi-depot types. The reference defines `MDMTSP` — multiple depot *travelling salesman* — and no multi-depot vehicle-routing type at all. The Cordeau front end emits `MDVRP` or `MDVRPTW` depending on the instance's type code, so refusing the spelling would leave the parser unable to read a document it wrote.
- `TOUR` is not a problem type in the reference because the reference is a solver; `TOUR` is a `TYPE` value in spec [§1.1.2](./tsplib95_format.md#112-type-string).

Eight further tokens differ from the reference list by letter case only (`CluVRP`/`CLUVRP`, `k-TSP`/`K-TSP`, `O-k-TSP`/`O-K-TSP`, `mTSP`/`MTSP`, `m-PDTSP`/`M-PDTSP`, `m1-PDTSP`/`M1-PDTSP`, `SoftCluVRP`/`SOFTCLUVRP`, `TSP_mD`/`TSP_MD`); the parsed vocabulary is uppercase, which `get_problem_class_for_type` normalizes before dispatch.

The coloured-TSP family is **deliberately not accepted**: `CTSP`, `CTSP-D`, `GCTSP`, `CCCTSP`, `MSCTSP`, `PCTSP`, `CBTSP`, `CBNTSP`.
Every one of them needs `CTSP_SET_SECTION`, and the reference names that section without publishing its grammar. Accepting the `TYPE` would parse the geometry and discard the colouring — a different problem. A file declaring one is refused:

- with the section present: `ParseError: unsupported CTSP_SET_SECTION: no field registered for its body`;
- without it: `ValidationError: Unknown problem type: CTSP`.

```text
1-PDTSP  ACVRP  ADCVRP  BMTSP  BWTSP  CATSPP  CCVRP  CLUVRP  CVRPTW  DCVRP
HPP      K-TSP  M-PDTSP M1-PDTSP  MDMTSP  MDVRP  MDVRPTW  MLP  MTRP  MTRPD
MTSP     O-K-TSP  OP  OVRP  PC-TSP  PDPTW  PDTSP  PDTSPF  PDTSPL  PTP  PTSP
RCTVRP   RCTVRPTW  SOFTCLUVRP  STTSP  TOP  TRP  TSPDL  TSPPD  TSPTW  TSP_MD
VRPB     VRPBTW  VRPMPD  VRPMPDTW  VRPSPD  VRPSPDTW
```

A declared `TYPE` is normalized before class dispatch (`get_problem_class_for_type`), so `k-TSP`, `mTSP` and `TSP (M.~Hofmeister)` reach the class registered for `K-TSP`, `MTSP` and `TSP`.
A spelling outside the vocabulary falls back to `StandardProblem`, which is what a core TSPLIB95 file expects.

Most of these values add nothing beyond the token itself. These carry a field:

- `CVRPTW`, `TSPTW` read `TIME_WINDOW_SECTION`; any type with a service time reads `SERVICE_TIME_SECTION`.
- `PDPTW`, `PDTSP`, `PDTSPF`, `PDTSPL`, `VRPMPD` read `PICKUP_AND_DELIVERY_SECTION`.
- `VRPB` reads `BACKHAUL_SECTION`; `DCVRP` reads `DISTANCE`; `MTSP` reads `VEHICLES`.
- `MDVRP` reads `DEPOT_SECTION`, and the depot count is that section's length.

### 6.4 Extension hints

`EXTENSION_TYPE_HINTS` (`src/tsplib_parser/types.py:148-155`) maps a suffix to an expected type: `.tsp → TSP`, `.atsp → ATSP`, `.sop → SOP`, `.hcp → HCP`, `.vrp → CVRP`, `.tour → TOUR`.
The hint never decides on its own; it is compared with the declared `TYPE` and a disagreement is reported.
Because the mapping is role-blind, `.tour` (a solution suffix) resolves to the problem type `TOUR`; that is the defect recorded as **PB16** in [format expansion plan](../../src/tsplib_parser/TODO.md) §10.0.

## 7. `EDGE_WEIGHT_TYPE` and `EDGE_WEIGHT_FORMAT`

### 7.1 Distance functions

`EDGE_WEIGHT_TYPE` selects how $d_{ij}$ is computed (spec §1.1.6, §2).
Measured 2026-10-25 over the 430 corpus problem files (the 18 `.hcp` files declare no edge weight type; they use `EDGE_DATA_SECTION`):

| Value | Rule | Spec | Implemented in `src/converter/utils/cost.py` | Corpus files |
| --- | --- | --- | --- | ---: |
| `EXPLICIT` | weights listed in `EDGE_WEIGHT_SECTION` | §1.2.8 | yes, via `Matrix` | 172 |
| `EUC_2D` | $\operatorname{nint}$ of the Euclidean distance | §2.1 | yes | 204 |
| `EUC_3D` | same in 3-D | §2.1 | yes | 0 |
| `CEIL_2D` | Euclidean distance rounded up | §2.6 | yes, `math.ceil` | 8 |
| `MAN_2D`, `MAN_3D` | Manhattan distance, then $\operatorname{nint}$ | §2.2 | yes | 0 |
| `MAX_2D`, `MAX_3D` | maximum of the per-axis absolute differences, each $\operatorname{nint}$ first | §2.3 | yes | 0 |
| `GEO` | great-circle distance, $R = 6378.388$ km, coordinates in `DDD.MM`, result `int(d + 1.0)` | §2.4 | yes | 20 |
| `ATT` | pseudo-Euclidean: $r_{ij} = \sqrt{((x_i-x_j)^2+(y_i-y_j)^2)/10}$, then `nint`, plus 1 when the rounded value is below the raw one | §2.5 | yes | 4 |
| `XRAY1` | per-axis motor differences divided by speeds `1.00, 1.0, 1.00`, maximum, $\times 100$, $\operatorname{nint}$ | §2.7 | yes | 2 |
| `XRAY2` | same with speeds `1.25, 1.5, 1.15` | §2.7 | yes | 2 |
| `SPECIAL` | a function documented elsewhere; no formula | §1.1.6 | **no** — vocabulary only | 0 |

`SPECIAL` is in `EDGE_WEIGHT_TYPES` (`src/tsplib_parser/types.py:159-176`) precisely so that a file declaring it is reported as an unsupported feature rather than an unknown keyword.
LKH-3 adds six further types that are **not** in this project's vocabulary: `EXACT_2D`, `EXACT_3D`, `FLOOR_2D`, `FLOOR_3D`, `TOR_2D`, `TOR_3D` (LKH-3 §3.1.1).
A file declaring one is rejected today.

The `XRAY2` speeds are not derivable from the local sources: spec §2.7 gives the `XRAY1` formula and points at the distributed `DEQ`/`DUN` routines, which are not in this repository.
`src/converter/utils/cost.py:110-120` is the only in-repo statement of them, and it is the implementation, not a citation.

### 7.2 Matrix formats

`EDGE_WEIGHT_FORMAT` describes how an `EXPLICIT` matrix is laid out (spec §1.1.7).
All nine matrix formats are implemented (`src/tsplib_parser/matrix.py`, recorded in [architecture decisions](./ARCHITECTURE_DECISIONS.md) §"Matrix implementation facts").

| Format | Layout | Corpus files |
| --- | --- | ---: |
| `FULL_MATRIX` | $n \times n$, row-major | 124 |
| `LOWER_DIAG_ROW` | lower triangle, row-wise, diagonal included | 24 |
| `LOWER_ROW` | lower triangle, row-wise, diagonal omitted | 12 |
| `UPPER_ROW` | upper triangle, row-wise, diagonal omitted | 6 |
| `UPPER_DIAG_ROW` | upper triangle, row-wise, diagonal included | 6 |
| `UPPER_COL`, `LOWER_COL` | the same triangles, column-wise, diagonal omitted | 0 |
| `UPPER_DIAG_COL`, `LOWER_DIAG_COL` | the same triangles, column-wise, diagonal included | 0 |
| `FUNCTION` | not a matrix: weights come from the distance function | 4 |

Element counts are fixed by `DIMENSION`: $n^2$ for `FULL_MATRIX`, $n(n+1)/2$ for a diagonal-inclusive triangle, $n(n-1)/2$ for a diagonal-free triangle.
A count that matches none of these is a parse error; §5.4 lists the two tolerated deviations.

Column formats reuse the row implementation by swapping the index pair; the duality is recorded in [architecture decisions](./ARCHITECTURE_DECISIONS.md).
Corpus coverage for the column formats and for `UPPER_DIAG_ROW` beyond six files is thin, so a test for them must be synthetic.

## 8. Extended keywords and sections

### 8.1 Header keywords

| Keyword | Value type | Arity | Authority | Registered in `ExtendedProblem` | Corpus files |
| --- | --- | --- | --- | --- | ---: |
| `VEHICLES` | integer | 1 | LKH-3 §3.1.1 | yes (`vehicles`) | 0 |
| `SALESMEN` | integer | 1 | LKH-3 §3.1.1 | yes (`salesmen`) | 0 |
| `DISTANCE` | real | 1 | LKH-3 §3.1.1 | yes (`max_distance`) | 12 |
| `RISK_THRESHOLD` | integer | 1 | LKH-3 §3.1.1 | yes (`risk_threshold`) | 0 |
| `SCALE` | integer | 1 | LKH-3 §3.1.1 | yes (`scale`) | 0 |
| `SERVICE_TIME` | real | 1 | LKH-3 §3.1.1 | yes (`service_time`) | 0 |
| `GRID_SIZE` | real | 1 | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) only | yes (`grid_size`) | 0 |
| `K` | integer | 1 | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) only (kTSP) | yes (`k`) | 0 |
| `PROBABILITY` | real | 1 | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) only (PTSP) | yes (`probability`) | 0 |
| `EXTERNAL_SALESMEN` | integer | 1 | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) only (OCMTSP) | yes (`external_salesmen`) | 0 |
| `PERIODS` | integer | 1 | **this project** | yes (`periods`) | 0 |
| `CAPACITY_VOL` | integer | 1 | **this project** | yes (`capacity_vol`) | 0 |
| `CAPACITY_WEIGHT` | integer | 1 | **this project** | yes (`capacity_weight`) | 0 |

`DISTANCE` is the only LKH-3 extension keyword the corpus uses: 12 files under `datasets_raw/cvrplib/Vrp-Set-Li/` declare it, e.g. `Li_21.vrp` line 7 `DISTANCE : 1800`.

Every keyword in this table is a typed field on `ExtendedProblem`, so a declared value reaches the parse result instead of being ignored as an unknown header.

### 8.2 Data sections

| Section | Line grammar | Terminator | Authority | Registered in `ExtendedProblem` |
| --- | --- | --- | --- | --- |
| `TIME_WINDOW_SECTION` | `<integer> <real> <real>` — node, earliest, latest | none | LKH-3 §3.1.2 | yes, 2 real columns |
| `SERVICE_TIME_SECTION` | `<integer> <real>` — node, service time; the depot must occur with 0 | none | LKH-3 §3.1.2 | yes, 1 real column |
| `PICKUP_AND_DELIVERY_SECTION` | `<integer> <integer> <real> <real> <real> <integer> <integer>` — node, demand, earliest, latest, service, pickup, delivery | none | LKH-3 §3.1.2 | yes, but accepts 4, 6 or 7 columns |
| `BACKHAUL_SECTION` | one node number per line | `-1` | LKH-3 §3.1.2 | yes, as a node list |
| `REQUIRED_NODES_SECTION` | one node number per line | `-1` | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) (3.0.6) | yes, as a node list |
| `CTSP_SET_SECTION` | node set per line | not stated in the source of record | [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) only | **no** — no grammar is published, so the eight coloured-TSP `TYPE` values that need it are refused as well ([§6.3](#63-extended-type-values)) |
| `DEPOT_CAPACITY_SECTION` | `<integer> <integer>` — depot number, capacity | none | **this project** | yes |
| `DEPOT_DURATION_SECTION` | `<integer> <real>` — depot number, maximum duration | none | **this project** | yes |

`DEPOT_SECTION` is core TSPLIB (spec §1.2.2), not an LKH-3 addition; the LKH-3 report reminds the reader of that and adds that LKH-3 "at present only allows one depot" (LKH-3 §3.1.2).

### 8.3 What happens to an extension section in a core-typed file

`_preprocess_vrp_file` strips `TIME_WINDOW_SECTION`, `PICKUP_AND_DELIVERY_SECTION`, `PICKUP_SECTION`, `SERVICE_TIME_SECTION`, `BACKHAUL_SECTION`, `DELIVERY_SECTION`, `PICKUP_DELIVERY_SECTION`, `STANDTIME_SECTION`, `READY_TIME_SECTION` and `DUE_DATE_SECTION` whenever the target class does not register them (`src/tsplib_parser/parser.py:29-47`).
The class is chosen from the declared `TYPE` (or from a hint), so `TYPE : CVRP` with a `TIME_WINDOW_SECTION` loses the windows and keeps only the boolean `has_time_windows`.
A reader must not assume that "the file parsed" means "the file's data survived".

## 9. Native problem families and their conversion

Both families converge on the TSPLIB-extended dialect (REQ-009).
The Cordeau island is the implemented precedent; the Solomon island is planned with the same shape ([format expansion plan](../../src/tsplib_parser/TODO.md) §§10.1–10.2).

### 9.1 Cordeau (implemented)

Grammar (per [Cordeau description](./courdeau-instances-description.md) §"Data Files", verified against `datasets_raw/umalaga/mdvrp/C-mdvrp/`):

| Part | Layout |
| --- | --- |
| header | `type m n t` — type 0..7, vehicles, customers, days/depots/vehicle types |
| `t` constraint lines | `D Q` — maximum route duration, maximum vehicle load |
| node lines | `i x y d q f a list e l` — id, coordinates, service duration, demand, frequency, combination count, combination list, earliest, latest |
| MDVRP numbering | customers `1..n`, depots `n+1..n+t` |
| single-depot numbering | depot `0`, customers `1..n` |

Measured 2026-10-25: all 33 corpus instances are type `2` (MDVRP), with 1–13 vehicles per depot and 2–9 depots; `p01` is `2 4 50 4`, so 50 customers then four depot lines `51`–`54`.
Depot lines carry `f = 0` and `a = 0` and no combination list (measured on `p01`).
The `f`, `a` and `list` columns are vestigial for type 2: every customer line in `p01` carries `1 4 1 2 4 8`.

Conversion (`CordeauConverter.to_tsplib`, `src/tsplib_parser/cordeau/cordeau_converter.py:69-160`):

1. **Keep the native node ids**: customers `1..n`, depots `n+1..n+t`. No renumbering, so a `.res` that names customer `44` names node `44`, and the converted file can be traced back without a rule.
2. Emit `TYPE : MDVRP`, `DIMENSION : n+t`, `EDGE_WEIGHT_TYPE : EUC_2D`, `VEHICLES : m·t`.
3. Emit `CAPACITY` and `DISTANCE` only when the `t` depot constraints are uniform.
4. Emit `NODE_COORD_SECTION`, `DEMAND_SECTION` (depot demand 0) and `DEPOT_SECTION` (`n+1`…`n+t`, then `-1`).
5. Emit `DEPOT_CAPACITY_SECTION` and `DEPOT_DURATION_SECTION` only when the constraints are heterogeneous.
6. Emit `TIME_WINDOW_SECTION` and `SERVICE_TIME_SECTION` only when the source carries windows.

`CordeauProblem.to_parse_result()` mirrors the same sections as 0-based arrays (`src/tsplib_parser/cordeau/cordeau_types.py:236-300`), with `depots` listing the indices of the depot nodes.

> [!NOTE]
> Step 1 reverses an earlier choice. The original bridge renumbered depots to nodes `1..t` and customers to `t+1..n+t`, which made the converted file unable to name the source nodes without an undocumented rule. That renumbering was justified by an LKH-3 requirement that does not exist: `DEPOT_SECTION` is core TSPLIB (spec §1.2.2) and accepts any node numbers, while LKH-3 "at present only allows one depot" (LKH-3 report §3.1.2). This dialect is therefore **TSPLIB-extended, inspired by LKH-3, not a copy of it**; a multi-depot instance is legal here because it is legal in TSPLIB.
> The depot *number* still identifies a depot inside a solution document (§10.4), because a solution file states no node ids for depots and an orphan solution has no instance to resolve them against.

### 9.2 Solomon and Holmberger (planned)

Two spellings exist and both are in scope.

The **headered** spelling is what the corpus uses, measured 2026-10-25 over all 356 `.txt` files (300 in `datasets_raw/cvrplib/Holmberger/`, 56 in `datasets_raw/cvrplib/Vrp-Set-Solomon/`):

```text datasets_raw/cvrplib/Vrp-Set-Solomon/C101.txt#L1-L8
C101

VEHICLE
NUMBER     CAPACITY
  25         200

CUSTOMER
CUST NO.  XCOORD.   YCOORD.    DEMAND   READY TIME  DUE DATE   SERVICE   TIME
```

Then a column-header line, then one row per node.

Measured properties of the headered spelling (356/356 files):

- line 1 is the instance name and equals the file stem;
- the block sequence is `VEHICLE`, `NUMBER CAPACITY`, `<K> <Q>`, `CUSTOMER`, column header, rows;
- every row has exactly seven columns `i x y q e l d`;
- the depot is `i = 0` and comes first;
- ready time, due date and service time exist for every node, the depot included;
- all coordinates are integers.

The **bare** spelling is the one [Solomon description](./solomon-instances-description.md) documents: line 1 is the name, line 2 is `K Q`, and the remaining lines are `i x y q e l d` with no block markers.
No corpus file uses it.

Target file after conversion (REQ-009):

```text
NAME : C101
TYPE : CVRPTW
DIMENSION : 101
VEHICLES : 25
CAPACITY : 200
EDGE_WEIGHT_TYPE : EUC_2D
NODE_COORD_SECTION
1 40 50
2 45 68
...
DEMAND_SECTION
1 0
2 10
...
DEPOT_SECTION
1
-1
TIME_WINDOW_SECTION
1 0 1236
2 912 967
...
SERVICE_TIME_SECTION
1 0
2 90
...
EOF
```

Conversion rules:

- node id = source `i` + 1, so the depot becomes node `1` and customers `2..DIMENSION`;
- `DIMENSION` = number of node rows, depot included (`101` for `C101`);
- `VEHICLES` = `K`, `CAPACITY` = `Q` from the source header;
- `DEPOT_SECTION` lists the depot node and is always emitted, because the problem has a depot (spec §1.2.2);
- `DEMAND_SECTION` repeats every node, depot with demand `0` (spec §1.2.3);
- `TIME_WINDOW_SECTION` and `SERVICE_TIME_SECTION` repeat every node, depot included, per LKH-3 §3.1.2 ("The depot node must also occur in this section. Its service time is 0").

## 10. Solution formats

The corpus carries three solution families and this project defines a fourth document.
All four describe the same thing — an ordering of nodes, grouped into routes, with optional costs — and none of the first three can carry all of it.

| Family | Files | Expresses | Cannot express |
| --- | ---: | --- | --- |
| `.opt.tour` | 82 | one cycle, 1-based ids, optional cost in `COMMENT` | routes, depots, vehicles, per-route costs |
| `.sol` | 390 | routes per vehicle, 1-based customer ordinals, one total cost | depots, per-route costs, loads |
| `.res` | 33 | depot number, vehicle number, duration, load per route, total cost | a depot *node id* independent of numbering, windows or service times |
| canonical `ROUTE_SECTION` | 0 (project-defined) | routes, depot node ids, vehicle numbers, per-route cost and load, total cost | nothing the three above carry, except `COMMENT` text |

### 10.1 `.opt.tour`

Grammar (spec §1.1 for headers, §1.2.7 for the section):

```text
NAME : <string>          # optional in the spec, present in 82/82 corpus files
COMMENT : <string>       # optional
DIMENSION : <integer>    # optional in practice
TOUR_SECTION
<node> <node> ... <node>
-1
EOF                      # optional
```

Measured 2026-10-25 over the 82 corpus files:

| Property | Result |
| --- | --- |
| declares `DIMENSION` | 81/82; `rd100.opt.tour` omits it |
| declares `COMMENT` | 58/82 |
| `COMMENT` states a cost | 52/82, in three shapes: `(5046)`, `(Length 629)`, `Length 6110` |
| number of `-1` lines | exactly one, in 82/82 |
| node ids | a permutation of `1..DIMENSION`, in 82/82 |
| `NAME` equals the file name or its stem | 58/82 |

The 24 files whose `NAME` is not the stem are the reason `NAME` cannot be the link to the problem: `datasets_raw/problems/tour/a280.opt.tour` declares `NAME : ./TSPLIB/a280.tsp.optbc.tour` (a relative path) and `datasets_raw/problems/tour/alb1000.opt.tour` declares `NAME : alb1000.opt`.

Ids are 1-based node numbers of a **depot-free** array, so array index = id − 1 ([§12](#12-numbering-and-index-frames)).
The cost in a `COMMENT` is the tour length the distributor computed, not necessarily the answer to any recomputation; [§12](#12-numbering-and-index-frames) shows that four sampled files reproduce it exactly.

There is no keyword anywhere in the family that names the instance, the problem type, or the vehicles used.
A `.tour` file that solves a CVRP instance would be indistinguishable from one that solves a TSP instance, and a multi-route `.tour` — syntactically legal, spec §1.2.7 — would carry no depot assignment.
That gap is what [§10.4](#104-the-canonical-solution-document) closes.

> [!NOTE]
> Both TSPLIB95 and LKH-3 stop at "a collection of tours".
> TSPLIB95 §1.2.7 allows several tours in one `TOUR_SECTION`, each ended by `-1`, but assigns no depot, no vehicle number and no per-route cost to any of them.
> LKH-3 does not extend the tour file at all: its multi-vehicle output is written through the separate parameters `MTSP_SOLUTION_FILE` and `SINTEF_SOLUTION_FILE`, the latter "written in SINTEF format" (LKH-3 §3.2), while the only documented tour-file grammar is LKH-1's single-tour `INPUT_TOUR_FILE`, "a list of integers … terminated by a -1" ([LKH user guide](./lkh.pdf) §`INPUT_TOUR_FILE`).
> No upstream document in this repository specifies a multi-route solution file, which is why this project defines one.

### 10.2 `.sol`

Grammar (no upstream document; measured 2026-10-25 over 390 files):

```text
Route #1: <customer> <customer> ...
Route #2: <customer> ...
...
Route #N: <customer> ...
Cost <number>
```

- A route header is `Route` (case-insensitive), then `#`, then the route number, then `:`.
- A route body may wrap across several physical lines; the body ends at the next route header or at the `Cost` line. Measured 2026-10-25: no corpus file wraps a route — `datasets_raw/cvrplib/vrp-XXL/Brussels1.sol` holds exactly 512 route lines plus one `Cost` line in 513 lines — so a wrapped body is accepted defensively and has no corpus exemplar.
- `Cost` is the last non-blank line in 390/390 files, and appears exactly once.
- Ids are customer ordinals, 1-based, with the depot never listed; array index = id ([§12](#12-numbering-and-index-frames)).

Measured invariants (390/390 files): route numbers are exactly `1..k` in order, no route is empty, and the union of all route ids is exactly `1..n` with no repeats.

Cost semantics, per [Solomon description](./solomon-instances-description.md) §"Solution Files" for the time-windowed families: the total duration **excluding service time**.
Recomputation from the instance under that reading:

| Instance | Stated | Recomputed | Convention |
| --- | ---: | ---: | --- |
| `datasets_raw/cvrplib/vrp-XXL/Brussels1` | 501719 | 501719.0 | `nint` per edge, route closed at the depot |
| `datasets_raw/cvrplib/Vrp-Set-Li/Li_21` | 16212.82548 | 16212.82556 | real per edge, route closed at the depot |
| `datasets_raw/cvrplib/VRP-set-D/Loggi-n401-k23` | 336903 | 336903 | `LOWER_ROW` explicit matrix |
| `datasets_raw/cvrplib/Vrp-Set-Solomon/C101` | 827.3 | 828.94 | real per edge — **does not reconcile** |
| `datasets_raw/cvrplib/Holmberger/RC1_6_1` | 16944.2 | 16967.65 | real per edge — **does not reconcile** |

> [!CAUTION]
> The 356 `.sol` files that pair with a `.txt` instance carry a `Cost` that is **systematically lower** than the Euclidean total of their own route lists.
> Measured 2026-10-25 over all 356 pairs: the difference is negative in 356/356 cases, between −1.64 and −46.17 (mean −3.52 over the 56 Solomon files, −23.28 over the 300 Holmberger files).
> The routes themselves are consistent with the shipped instance — they satisfy capacity and every time window of `C101` and `RC1_6_1`, and they visit each customer exactly once — so the mismatch is in the stated number, not in the sequencing.
> A validator must therefore treat `Cost` as advisory for this family and must not reject a solution on a cost mismatch alone.

### 10.3 `.res`

Grammar (per [Cordeau description](./courdeau-instances-description.md) §"Solution Files", refined by measurement over 33 files):

```text
<total cost>
<l> <k> <d> <q> <delimiter> <customer> ... <customer> <delimiter>
...
```

| Field | Meaning | Measured |
| --- | --- | --- |
| line 1 | total cost | a number; `576.87` for `p01` |
| `l` | depot number, `1..t`, i.e. a position in the depot list — **not** a node id | `1..4` for `p01` |
| `k` | vehicle number within that depot, restarting at `1` for each `l` | `p01` uses 3, 4, 2 and 2 vehicles |
| `d` | route duration, **travel plus service time** | `pr01` route 1: travel 227.24 + service 148.0 = 375.24 |
| `q` | route load, equal to the demand sum of the route's customers | 0 mismatches over `p01`, `pr01`, `p10`, `pr10`, `p23` |
| delimiters | one of two spellings, see below | 23 files use `0`, 10 use the depot node id |

The two delimiter spellings:

- `0 … 0` — used by `datasets_raw/umalaga/mdvrp/C-mdvrp-sol/p01.res` … `p23.res` (23 files);
- `<depot node id> … <depot node id>` — used by `pr01.res` … `pr10.res` (10 files), where the depot node ids are `n+1..n+t`.

The delimiters are redundant with `l` in both spellings, so a reader may discard them; a writer that must reproduce a `.res` file byte for byte needs to know which spelling the source used.

Line 1 is **travel only**.
Verified on `pr01`, whose service times are non-zero: sum of `d` = 1414.32, sum of travel = 861.32, sum of service = 553.0, and line 1 states 861.32.
On `p01` every service time is 0, so both readings coincide: line 1 states 576.87 and the sum of `d` is 576.86, the difference being rounding in the stated values.

The corpus contains only type-2 (MDVRP) instances, so `l` is always a depot number.
For types 1 and 5 (PVRP, PVRPTW) the same column is a day number and a customer may appear on several days; a validator must not assume global uniqueness for those types ([§10.6](#106-invariants-a-validator-must-check)).

### 10.4 The canonical solution document

> [!IMPORTANT]
> Format defined by this project.
> It is not TSPLIB95, not TSPLIB and not LKH-3, and no upstream reader can parse it.
> Its only purpose is to hold a multi-route, multi-depot solution losslessly inside this repository, so that one shape feeds the database, the JSON writer and the parquet writer.

The document follows TSPLIB's own idiom: one section per quantity, each a two-column table terminated by `-1`, so no line carries positional fields whose meaning has to be remembered.

```text
NAME : <string>            # required, copied from the source header, else the file stem
TYPE : TOUR                # required, always TOUR
PROBLEM : <string>         # optional, the instance this solution refers to
DIMENSION : <integer>      # required
COST : <number>            # optional, the total the source states
DEPOT_SECTION              # required when any route names a depot
<depot node id>
-1
ROUTE_SECTION              # required
<route> <node> <node> ...
-1
ROUTE_DEPOT_SECTION        # optional
<route> <depot node id>
-1
ROUTE_COST_SECTION         # optional
<route> <cost>
-1
ROUTE_LOAD_SECTION         # optional
<route> <load>
-1
EOF                        # optional
```

Rules:

1. Header lines use the common grammar of §5.1. A writer emits the order above; a reader accepts any order before the first section.
2. `NAME` is copied verbatim from the source when the source has one, and is the file stem otherwise. It is **not** the link to the problem.
3. In this document `TYPE` is always `TOUR` — it is a solution document, and `TOUR` is the spec's own solution type (spec §1.1.2). It is never a problem type: a problem file states its own `TYPE`, which is one of §6.1 or §6.3.
4. `PROBLEM` names the instance the solution refers to: the source file stem with `.opt.tour`, a trailing `.opt` and `.sol`/`.res` suffixes removed. It is the only content-level link; a solution whose `PROBLEM` matches no stored problem is an orphan.
5. `DIMENSION` is the size of the numbering the document uses, depots included: the highest node id, equal to the linked problem's `DIMENSION` (REQ-005). A depot-free cycle document states its cycle length.
6. `DEPOT_SECTION` is present exactly when some route names a depot, and lists the depot node ids in the order the linked problem lists them (spec §1.2.2). A depot-free cycle document has neither `DEPOT_SECTION` nor `ROUTE_DEPOT_SECTION`.
7. `COST`, when present, is the total the source states, copied verbatim. It is never recomputed and never normalized.
8. One route occupies exactly one physical line in `ROUTE_SECTION`. A reader rejects a continuation line.
9. The first column of every `ROUTE_*` section is a **route id**: a positive integer, unique in the document, and **the same set in all four sections**. A route present in `ROUTE_SECTION` and absent from `ROUTE_COST_SECTION` simply has no stated cost; a route present in `ROUTE_COST_SECTION` and absent from `ROUTE_SECTION` is an error.
10. `ROUTE_DEPOT_SECTION` carries a **depot node id**, and every value must appear in the document's own `DEPOT_SECTION`. Reusing the spec's section removes the depot-number-to-node map: the document states its depots once and the routes point into that list. A `.res` source that states depot numbers is resolved when the document is built from the linked instance; an orphan `.res` is rejected ([§10.7](#107-linking-a-solution-to-a-problem)).
11. `<cost>` and `<load>` are stated values only. A source that states nothing produces an absent section, never a sentinel: `-1` is the terminator everywhere and never a value.
12. `ROUTE_SECTION` is the only required route section. `ROUTE_DEPOT_SECTION`, `ROUTE_COST_SECTION` and `ROUTE_LOAD_SECTION` are emitted only when the source states the quantity.
13. A route may carry no node at all: `<route>` alone on its line. It means "this vehicle is used for nothing" and is legal in the document.
14. A single-cycle tour is one route line with no `DEPOT_SECTION` and no `ROUTE_DEPOT_SECTION`.
15. Every node value is the linked problem's node id, 1-based, exactly as its `DEPOT_SECTION`, `DEMAND_SECTION` and `NODE_COORD_SECTION` state it, in visit order, with the depot never repeated. There is no second numbering: a source that numbers nodes differently is shifted when the document is built — a `.sol` omits the depot and starts at `1`, so under a TSPLIB CVRP, where the depot is node `1`, customer `k` becomes node `k + 1`.

Mapping from each source:

| Source | `ROUTE_SECTION` | `ROUTE_DEPOT_SECTION` | `ROUTE_COST_SECTION` | `ROUTE_LOAD_SECTION` | `DEPOT_SECTION` | `COST` |
| --- | --- | --- | --- | --- | --- | --- |
| `.opt.tour`, one cycle | one line, the cycle | absent | absent | absent | absent | the `COMMENT` cost, else absent |
| `.sol` | one line per `Route #N`, every id shifted onto node ids | the single depot node | absent | absent | `1` | the `Cost` value |
| `.res` | one line per route line | the depot node of `l` | `d` | `q` | the `t` depot node ids | line 1 |

Mapping back to a `.opt.tour` file is defined only for a document with exactly one route and no depot.
The writer then emits `DIMENSION`, `TOUR_SECTION`, the route's node tokens, `-1`, `EOF`.
The node sequence, the `-1` and the `EOF` are reproduced exactly; `NAME` and `COMMENT` are normalized and are not byte-identical to the source.

### 10.5 Worked examples

Single cycle: `datasets_raw/zips/all_problems/tour/gr48.opt.tour` (48 nodes, no depot, cost stated in the `COMMENT`).

```text
NAME : gr48.opt.tour
TYPE : TOUR
PROBLEM : gr48
DIMENSION : 48
COST : 5046
ROUTE_SECTION
1 29 7 28 44 41 46 18 34 23 25 3 19 4 30 38 20 35 42 39 40 2 45 43 47 37 24 15 10 12 31 5 33 8 22 21 17 27 32 9 14 6 26 36 11 16 48 13 1
-1
EOF
```

Single depot, ten vehicles, no per-route data: `datasets_raw/cvrplib/Vrp-Set-Solomon/C101.sol`.

```text
NAME : C101.sol
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
4 33 34 32 36 38 39 40 37 35
5 44 43 42 41 45 47 46 49 52 51 53 50 48
6 58 56 55 54 57 59 61 60
7 68 66 64 63 75 73 62 65 69 67 70
8 82 79 77 72 71 74 78 80 81
9 91 88 87 84 83 85 86 89 90 92
10 99 97 96 95 93 94 98 101 100
-1
EOF
```

Four depots, eleven routes, per-route duration and load: `datasets_raw/umalaga/mdvrp/C-mdvrp-sol/p01.res`.

```text
NAME : p01.res
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
1 44 45 33 15 37 17
2 42 19 40 41 13
3 25 18 4
4 6 27 1 32 11 46
5 48 8 26 31 28 22
6 23 7 43 24 14
7 12 47
8 9 34 30 39 10
9 49 5 38
10 35 36 3 20
11 21 50 16 2 29
-1
ROUTE_DEPOT_SECTION
1 51
2 51
3 51
4 52
5 52
6 52
7 52
8 53
9 53
10 54
11 54
-1
ROUTE_COST_SECTION
1 60.06
2 66.55
3 47.00
4 53.44
5 79.47
6 81.40
7 23.50
8 50.41
9 25.22
10 47.67
11 42.14
-1
ROUTE_LOAD_SECTION
1 71
2 79
3 78
4 73
5 80
6 77
7 54
8 75
9 54
10 67
11 69
-1
EOF
```

Route ids are reassigned `1..11` in file order because the `.res` route numbers restart at `1` per depot (`1 1`, `1 2`, …, `2 1`, …); the depot column of the source becomes `ROUTE_DEPOT_SECTION`, so nothing is lost and the ids are unique as rule 9 requires.

### 10.6 Invariants a validator must check

| Id | Invariant | Scope |
| --- | --- | --- |
| **V-01** | every node value satisfies `1 ≤ id ≤ DIMENSION` | always |
| **V-02** | no node value appears twice in `ROUTE_SECTION` | always |
| **V-03** | `count(distinct node values) = DIMENSION − len(DEPOT_SECTION)`, with the length read as `0` when the section is absent | always |
| **V-04** | `ROUTE_DEPOT_SECTION` is present iff `DEPOT_SECTION` is; every depot value appears in `DEPOT_SECTION` | always |
| **V-05** | route ids are unique in the document and identical across the four `ROUTE_*` sections | always |
| **V-07** | a `ROUTE_LOAD_SECTION` entry equals the demand sum of that route's nodes | when the problem is linked || **V-08** | every stated cost and load is non-negative and finite; `COST`, when present, likewise | always |
| **V-09** | `sum(ROUTE_COST_SECTION) = COST` within tolerance | only when every route cost uses the same convention as `COST` — true for a single-route `.opt.tour`, false for `.res` |
| **V-10** | `COST` equals a recomputation within `max(1e-3, 1e-6·COST)` | advisory; must not fail on the 356 `.txt` pairs of §10.2 |
| **V-11** | every section present is terminated by exactly one `-1` line | always |
| **V-12** | a `.opt.tour` round-trip preserves the node sequence element by element | always |
| **V-13** | a route line has no continuation line and no node value outside `ROUTE_SECTION` | always |

`V-06` is unused on purpose. It asserted that the `VEHICLES` header equalled the number of `ROUTE_SECTION` lines, and that header was removed from this document because it restated a count the document already contains. The id is not reused, so a reference to `V-06` in an older note cannot silently point at a different rule.

Cost tolerance evidence: `Li_21` differs from its recomputation by `8e-5` (16212.82548 stated against 16212.82556 recomputed), `Brussels1` and `Loggi` match exactly, and `gr48` matches exactly.
A tolerance below `1e-4` would reject `Li_21`.

An invariant with no failing case is not a validation ([AGENTS](../../AGENTS.md#5-architectural-standards) §5.8): each id above needs one input that violates it.

### 10.7 Linking a solution to a problem

Measured layout (2026-10-25), and the only rules allowed by REQ-010:

| Direction | Rule | Evidence |
| --- | --- | --- |
| forward, `.sol` | the sibling `<parent>/<stem>.sol` | 390/390 files have a same-stem sibling (`.vrp` or `.txt`) |
| forward, `.opt.tour` | `<parent>/../tour/<stem>.opt.tour` | 82/82 tours sit in `tour/` beside the instance's family directory |
| forward, `.res` | `<parent>/../C-mdvrp-sol/<stem>.res` | 33/33 `.res` files sit in `C-mdvrp-sol/` beside `C-mdvrp/` |
| backward | the file stem, compared case-insensitively | 0 of the corpus stems collide; 4 tours share a stem with a `.vrp` twin, which is why the tour rule is restricted to `.tsp` and `.hcp` instances |

The 82 tours belong to 64 `.tsp`, 18 `.hcp` and 4 `.vrp` instances.
The `.vrp` twins must not claim the tour: `att48` and `eil51` ship as both `.tsp` and `.vrp`, and the tour is the TSP one.
`TOUR_INSTANCE_SUFFIXES` encodes exactly that restriction (`src/converter/core/solutions.py:349-360`).

A backward link that finds several stored problems with the same stem must return "ambiguous" rather than pick one (`src/converter/core/solutions.py:391-408`).

## 11. Role and format of every corpus file type

Measured 2026-10-25 over `datasets_raw/**`: 1331 files.
(The format plan counts 1329 at [format expansion plan](../../src/tsplib_parser/TODO.md) §10.0; the difference is two `.md` description files under `datasets_raw/umalaga/mdvrp/`, so both counts describe the same corpus.)

| Suffix | Files | Role | Native grammar | Target |
| --- | ---: | --- | --- | --- |
| `.tsp` | 226 | problem | TSPLIB95 (§5) | parsed as-is |
| `.sop` | 82 | problem | TSPLIB95 SOP, with the leading-`DIMENSION` deviation of §5.4 | parsed as-is |
| `.vrp` | 66 | problem | TSPLIB95 CVRP, plus CVRPLIB `DISTANCE` | parsed as-is |
| `.atsp` | 38 | problem | TSPLIB95 ATSP | parsed as-is |
| `.hcp` | 18 | problem | TSPLIB95 HCP with `EDGE_DATA_FORMAT : EDGE_LIST` | parsed as-is |
| `.txt` | 356 | problem | Solomon/Holmberger CVRPTW, headered spelling ([§9.2](#92-solomon-and-holmberger-planned)) | LKH-3 `CVRPTW` text |
| none | 33 | problem | Cordeau MDVRP ([§9.1](#91-cordeau-implemented)) | LKH-3 `MDVRP` text |
| `.tour` | 82 | **solution** | TSPLIB `TOUR_SECTION` ([§10.1](#101-opttour)) | `ROUTE_SECTION` document |
| `.sol` | 390 | **solution** | CVRPLIB `Route #N` / `Cost` ([§10.2](#102-sol)) | `ROUTE_SECTION` document |
| `.res` | 33 | **solution** | Cordeau route lines ([§10.3](#103-res)) | `ROUTE_SECTION` document |
| `.gz`, `.problems`, `.md` | 7 | archive/index | none | out of scope |

Two consequences, both already recorded as defects in [format expansion plan](../../src/tsplib_parser/TODO.md) §10.0:

- `.tour` is a solution suffix, yet it is the only suffix whose extension hint names a problem type (§6.4); a scanner that globs "everything except `.sol`" will ingest 82 solutions as problems.
- `.txt` and the suffix-less Cordeau instances are problems that no suffix-based glob names.

Sampled 2026-10-26, first problem file of every folder (`.sol` and `.res` excluded, they are the next phase):

| Folder | File | Result |
| --- | --- | --- |
| `problems/tsp` | `a280.tsp` | `TSP`, 280 coords, `EUC_2D` |
| `problems/atsp` | `br17.atsp` | `ATSP`, `EXPLICIT` |
| `problems/sop` | `ESC07.sop` | `SOP`, `EXPLICIT` |
| `problems/hcp` | `alb1000.hcp` | `HCP`, no weight type |
| `problems/vrp` | `att48.vrp` | `CVRP`, 48 coords, 48 demands, 1 depot |
| `problems/tour` | `a280.opt.tour` | `TOUR`, 1 tour |
| `cvrplib/VRP-set-D` | `Loggi-n1001-k31.vrp` | `CVRP`, 1001 coords, `EXPLICIT` |
| `cvrplib/Vrp-Set-Li` | `Li_21.vrp` | `CVRP`, 561 coords, `EUC_2D` |
| `cvrplib/vrp-XXL` | `Antwerp1.vrp` | `CVRP`, 6001 coords, `EUC_2D` |
| `umalaga/mdvrp/C-mdvrp` | `p01` | `MDVRP`, 54 nodes, 4 depots |
| `cvrplib/Holmberger` | `C1_10_1.txt` | **fails** — no native `CVRPTW` front end yet (§9.2) |
| `cvrplib/Vrp-Set-Solomon` | `C101.txt` | **fails** — same reason |

The two failures are the only problem folders without a front end, and they fail by raising, not by returning a partial result.

## 12. Numbering and index frames

### 12.1 Files are 1-based, `ParseResult` arrays are 0-based

| `ParseResult` key | Source section | Mapping, for every `i` in the array |
| --- | --- | --- |
| `coords[i]` | `NODE_COORD_SECTION` | node id `i + 1` |
| `display_coords[i]` | `DISPLAY_DATA_SECTION` | node id `i + 1` |
| `demands[i]` | `DEMAND_SECTION` | node id `i + 1`; a node missing from the section is an error |
| `depots[k]` | `DEPOT_SECTION` | the k-th listed depot, sorted ascending, minus 1 |
| `edges[i]`, `fixed_edges[i]` | `EDGE_DATA_SECTION`, `FIXED_EDGES_SECTION` | each endpoint minus 1 |
| `tours[i]["nodes"]` | `TOUR_SECTION` | each node minus 1 |

The conversion is implemented once, in `FormatParser._extract_*` (`src/tsplib_parser/parser.py:420-490`), and it is the rule recorded as D3 in [architecture decisions](./ARCHITECTURE_DECISIONS.md).

### 12.2 The three solution frames

The frames are **per format**, not shared.
A uniform shift preserves contiguity, so no test that only checks "ids are 1..n with no repeats" can detect a wrong frame; only recomputing the stated cost can.

| Format | File ids are | Array the ids index | Frame |
| --- | --- | --- | --- |
| `.opt.tour` | node numbers `1..DIMENSION` | a **depot-free** array (`coords` of a TSP/HCP instance) | array index = id − 1 |
| `.sol` | customer ordinals `1..n`; the depot is never listed | an array whose index `0` is the depot | array index = id |
| `.res` | customers `1..n`, depots `n+1..n+t` in the instance file; `l` = depot number `1..t` | the instance's own node order (no renumbering since §9.1 changed) | customer: node = id, so index = id − 1; depot: node = `DEPOT_SECTION[l − 1]`, index = node − 1 |

The `.sol` frame holds for both sub-families even though they number nodes differently: in a TSPLIB CVRP the depot is node `1`, so customer `k` is node `k+1`; in a Solomon `.txt` the depot is row `0`, so customer `k` is row `k`.
In both cases `parse` puts the depot at array index `0`, and `index = id` selects the right customer.

### 12.3 Proof of the frames

Measured 2026-10-25 by recomputing each file's stated cost from the instance under both frames.
The wrong frame either changes the number or leaves the array.

| Solution file | Instance | Stated | `index = id` | `index = id − 1` |
| --- | --- | ---: | --- | --- |
| `cvrplib/vrp-XXL/Brussels1.sol` | `Brussels1.vrp` (`EUC_2D`) | 501719 | **501719.0** | 8 980 106 (17.9×) |
| `cvrplib/Vrp-Set-Li/Li_21.sol` | `Li_21.vrp` (`EUC_2D`, real) | 16212.82548 | **16212.82556** | 16300.21 (+0.5%) |
| `cvrplib/VRP-set-D/Loggi-n401-k23.sol` | `Loggi-n401-k23.vrp` (`LOWER_ROW`) | 336903 | **336903** | 1 091 550 (+224%) |
| `problems/tour/gr48.opt.tour` | `problems/tsp/gr48.tsp` (`LOWER_DIAG_ROW`) | 5046 | out of bounds (id 48 on a 48×48 matrix) | **5046** |
| `problems/tour/a280.opt.tour` | `problems/tsp/a280.tsp` (`EUC_2D`) | 2579 | out of bounds (id 280) | **2579** |
| `problems/tour/lin105.opt.tour` | `problems/tsp/lin105.tsp` (`EUC_2D`) | 14379 | out of bounds (id 105) | **14379** |
| `problems/tour/pr2392.opt.tour` | `problems/tsp/pr2392.tsp` (`EUC_2D`) | 378032 | out of bounds (id 2392) | **378032** |

`pr2392.opt.tour` lists the identity permutation `1, 2, …, n`; `a280.opt.tour` and `lin105.opt.tour` do not. All three reproduce the length their `COMMENT` states, to the unit, with `nint` distances, which fixes the frame without any assumption about the permutation.

The Cordeau frame follows the same rule as everything else, once the bridge stops renumbering depots (§9.1): customer `k` is node `k`, so its array index is `k − 1`, and depot `l` is whatever `DEPOT_SECTION` lists in position `l`.
Verified on `p01`: 11 route lines, all 50 customers served exactly once, every `q` equal to its route's demand sum, and the sum of `d` = 576.86 against a stated 576.87.

## 13. Spec versus code

Where the documents and the implementation disagree, neither side is silently preferred.
The table records the disagreement and its consequence.

| # | Spec says | Code does | Consequence |
| ---: | --- | --- | --- |
| 1 | spec §1.1.2 lists TSP, ATSP, SOP, HCP, CVRP, TOUR; there is no `VRP` | `PROBLEM_TYPE_ALIASES` maps `VRP → CVRP` and calls `VRP` "the umbrella spelling of TSPLIB95" (`src/tsplib_parser/types.py:85-90`) | harmless: no corpus file declares `VRP`; the docstring overstates the spec |
| 2 | — | `PROBLEM_TYPE_ALIASES` maps `VRP → CVRP`; class dispatch normalizes the declared `TYPE` before the registry lookup (`src/tsplib_parser/models.py:307-320`) | resolved: `VRP`, `k-TSP`, `mTSP` and `TSP (M.~Hofmeister)` now reach the class registered for their canonical token |
| 3 | LKH-3 "at present only allows one depot" (LKH-3 §3.1.2) | Cordeau emits `TYPE : MDVRP` and `t` nodes in `DEPOT_SECTION` (`src/tsplib_parser/cordeau/cordeau_converter.py`) | intended, not a defect: this is a **TSPLIB-extended** dialect (FMT-3), legal because `DEPOT_SECTION` is core TSPLIB. It is not an LKH-3 file and must not be described as one |
| 4 | LKH-3 §3.1.2 has no `DEPOT_CAPACITY_SECTION`, `DEPOT_DURATION_SECTION`, `PERIODS`, `CAPACITY_VOL`, `CAPACITY_WEIGHT` | all five are registered in `ExtendedProblem` (`src/tsplib_parser/models.py:252-265`) and two are emitted | project-defined vocabulary, correctly labelled in §3, but not LKH-3 |
| 5 | `BACKHAUL_SECTION` "contains a list of backhaul nodes", one integer per line (LKH-3 §3.1.2) | registered as `DepotsField`, a node list terminated by `-1` (`src/tsplib_parser/models.py:262`) | resolved: the old `DemandsField` rejected a conforming file with `ParseError: item "3" is not a valid key-value pair` |
| 6 | `PICKUP_AND_DELIVERY_SECTION` has seven columns (LKH-3 §3.1.2) | accepts 4, 6 or 7 columns (`src/tsplib_parser/models.py:262-263`) | a superset; the extra shapes are undocumented |
| 7 | the LKH-3 reference names 58 problem-type tokens, including `TRP`, `ADCVRP`, `RCTVRPTW`, `MTRP`, `MTRPD`, `OP`, `TOP`, `PCTSP`, `CluVRP` and `VRPSPD` | `EXTENDED_PROBLEM_TYPES` now carries all 58 plus `MDVRP`; `TRPP`, a token no source defines, is gone (`src/tsplib_parser/types.py:99-167`) | resolved: an LKH-3 `TYPE` reaches `ExtendedProblem` instead of falling back to `StandardProblem`, so its extension sections are no longer stripped |
| 8 | LKH-3 §3.1.1 adds `EXACT_2D/3D`, `FLOOR_2D/3D`, `TOR_2D/3D` | absent from `EDGE_WEIGHT_TYPES` (`src/tsplib_parser/types.py:159-176`) | a file declaring one is rejected as an unknown keyword, which is the right failure for an unimplemented function but the wrong message |
| 9 | LKH-3 §3.1.1 defines `SALESMEN`, `SCALE`, `RISK_THRESHOLD`; [LKH-3 reference](./LKH-3-Keld-Helsgaun.md) also lists `GRID_SIZE`, `K`, `PROBABILITY`, `EXTERNAL_SALESMEN` | all seven are typed fields on `ExtendedProblem` (`src/tsplib_parser/models.py:265-273`) | resolved: a `SALESMEN : 8` file keeps the value instead of losing it silently |
| 10 | — | `EXTENSION_TYPE_HINTS[".tour"] = TOUR` (`src/tsplib_parser/types.py:148-155`) | a solution suffix is hinted as a problem type; 82 corpus solutions are ingested as problems (**PB16**) |
| 11 | a `TOUR_SECTION` ends with one `-1` per tour plus one more (spec §1.2.7) | `SECTION_GRAMMARS` declares `terminator_lines=2` for `TOUR_SECTION` (`src/tsplib_parser/types.py:424-430`) | the corpus has exactly one `-1` in 82/82 files; the second terminal is optional in practice |
| 12 | `NODE_COORD_TYPE` is §1.1.9 and `EDGE_DATA_FORMAT` is §1.1.8 in [TSPLIB95 spec](./tsplib95_format.md) | the comments swap them (`src/tsplib_parser/types.py:184`, `:194`) | citation defect only |
| 13 | — | [architecture decisions §"Open Items"](./ARCHITECTURE_DECISIONS.md#open-items) says the `.tour` index conversion is "still unverified (potential data-corruption risk)" | resolved: §12.3 measures `index = id − 1` |
| 14 | — | `solomon-instances-description.md` opens with two consecutive YAML blocks and two `title` keys | the file's frontmatter is malformed; the second title is the real one |
| 15 | [Cordeau description](./courdeau-instances-description.md) §"Solution Files" describes `l k d q list` and says the first line is the cost "excluding service time" | the documents never mention the `0 … 0` / depot-node delimiters, and never say that the per-route `d` **includes** service | [§10.3](#103-res) fills both gaps from measurement |
| 16 | LKH-3 §3.2 documents the parameter file (`DEPOT`, `MOVE_TYPE`, …) | this repository parses no parameter file | out of scope, recorded so nobody looks for it here |

## 14. Acceptance criteria

- **AC-001**: Given a corpus problem file from [§11](#11-role-and-format-of-every-corpus-file-type), when the parser runs, then it returns a `ParseResult` with every array 0-based as in [§12.1](#121-files-are-1-based-parseresult-arrays-are-0-based).
- **AC-002**: Given `datasets_raw/problems/tour/gr48.opt.tour`, when it is converted to a canonical document and back, then the 48 node tokens, the `-1` and the `EOF` are reproduced in the same order.
- **AC-003**: Given `datasets_raw/cvrplib/vrp-XXL/Brussels1.sol`, when its cost is recomputed with `index = id` and `nint` distances, then the result is 501719.0.
- **AC-004**: Given the same file, when its cost is recomputed with `index = id − 1`, then the result is not 501719.0.
- **AC-005**: Given `datasets_raw/umalaga/mdvrp/C-mdvrp-sol/p01.res`, when it is parsed, then every `<load>` equals its route's demand sum and every `<depot>` is one of the depot node ids `51..54`.
- **AC-006**: Given a canonical document whose `DEPOT_SECTION` lists node `1` and a route whose depot value is `99`, when it is validated, then V-04 fails.
- **AC-007**: Given a canonical document whose `DIMENSION` is 48 and whose routes list 47 distinct nodes with `DEPOT_SECTION` absent, when it is validated, then V-03 fails.
- **AC-008**: Given a route line wrapped across two physical lines, when it is read, then the reader reports a malformed document (CON-002).
- **AC-009**: Given a `.sol` file from `datasets_raw/cvrplib/Vrp-Set-Solomon/`, when its `Cost` disagrees with a recomputation, then validation reports a warning and not an error ([§10.2](#102-sol)).
- **AC-010**: Given `datasets_raw/problems/sop/ESC11.sop`, when it is parsed, then the leading `DIMENSION` token is dropped and the matrix has 13×13 entries.
- **AC-011**: Given a `TYPE : CVRP` file that also carries a `TIME_WINDOW_SECTION`, when it is parsed, then the section is reported as stripped rather than silently accepted ([§8.3](#83-what-happens-to-an-extension-section-in-a-core-typed-file)).
- **AC-012**: Given an `EDGE_WEIGHT_TYPE : SPECIAL` file, when it is parsed, then a typed unsupported-feature error is raised (REQ-008).

## 15. Test automation strategy

- **Test levels**: unit for each grammar rule, integration for each corpus family, and a corpus sweep that parses every problem file and every solution file.
- **Frameworks**: `pytest`, run through `.venv/bin/python -m pytest` (see [AGENTS §2](../../AGENTS.md#2-environment--tooling-setup) and `[tool.pytest.ini_options]` in `pyproject.toml`).
- **Fixtures**: synthetic in-memory text for each grammar rule; the corpus fixtures in `tests/conftest.py` behind the `requires_dataset` marker for anything that must read `datasets_raw/**`.
- **Frame tests**: every frame claim of [§12](#12-numbering-and-index-frames) is asserted by recomputing a stated cost, never by a uniqueness or range check alone.
- **Round-trip tests**: `.opt.tour` → canonical → `.opt.tour` compares node sequences element by element.
- **Coverage requirement**: every row of [§10.6](#106-invariants-a-validator-must-check) has at least one failing case and one passing case; an invariant with no failing case is not a validation ([AGENTS](../../AGENTS.md) §5.8).
- **CI**: the parser package's targeted gate (`pytest tests/tsplib_parser -m "not slow and not requires_dataset"`) plus `mypy src` at or below the recorded baseline.

## 16. Dependencies and external integrations

### External systems

- **EXT-001**: TSPLIB95 distribution — the instance library and the `.opt.tour` naming convention (spec §3.1, [TSPLIB95 spec](./tsplib95_format.md)).
- **EXT-002**: LKH-3 — the extension vocabulary and the only upstream definition of the added sections (LKH-3 §3, [LKH-3 report](./lkh-3.pdf)).
- **EXT-003**: UMA VRP repository — the Cordeau and Solomon descriptions ([Cordeau description](./courdeau-instances-description.md), [Solomon description](./solomon-instances-description.md)).
- **EXT-004**: CVRPLIB — the `.vrp`, `.txt` and `.sol` files; no upstream format document exists, so the corpus is the only source.

### Data dependencies

- **DAT-001**: `datasets_raw/**` — 1331 files, read-only, treated as the ground truth for every measured claim in this document.
- **DAT-002**: `docs/reference/*.pdf` — the upstream TSPLIB95 and LKH documents; the extracted text is the citation of record when the markdown copies are ambiguous.

### Technology platform dependencies

- **PLT-001**: Python 3.12+ with `math` only for distance functions; no numerical library is required.
- **PLT-002**: DuckDB and parquet writers consume `ParseResult` and the canonical solution document; they are not part of the format layer.

### Compliance dependencies

- **COM-001**: upstream texts are cited and summarized, never copied verbatim into this document; the local copies in `docs/reference/` keep the original wording and attribution.
- **COM-002**: LKH-3 is distributed for academic and non-commercial use ([LKH-3 reference](./LKH-3-Keld-Helsgaun.md) §Installation). That licence covers the solver's code, which this repository neither copies nor links. The format description is a documented interface and is used as an inspiration only.

## 17. Open questions

Decided while writing this document:

| # | Question | Decision |
| ---: | --- | --- |
| FMT-1 | What does the depot column of a solution document mean? | A **depot node id** that must appear in the document's `DEPOT_SECTION` ([§10.4](#104-the-canonical-solution-document) rule 10). The spec already defines that section (spec §1.2.2), so the document reuses it instead of inventing a depot-number namespace |
| FMT-2 | Is the canonical document written to disk? | No. It is produced on demand through an API; nothing is written unless a caller writes it |
| FMT-3 | Is the extended problem dialect LKH-3? | **No.** The core is TSPLIB95; the extension is this project's TSPLIB-extended dialect, inspired by LKH-3 but not bound by it. Multi-depot instances are legal because `DEPOT_SECTION` is core TSPLIB and may list any node numbers (LKH-3 itself allows one depot, report §3.1.2). The class is therefore named `ExtendedProblem`, and the depot count is `len(DEPOT_SECTION)` rather than a `DEPOTS` header (**PB18**, **PB19**) |
| FMT-4 | Is the bare UMA Solomon spelling in scope? | Yes, in addition to the headered corpus spelling ([§9.2](#92-solomon-and-holmberger-planned)) |
| FMT-5 | How are the routes of a solution document laid out? | One section per quantity, each a two-column index table terminated by `-1` (`ROUTE_SECTION`, `ROUTE_DEPOT_SECTION`, `ROUTE_COST_SECTION`, `ROUTE_LOAD_SECTION`), following TSPLIB's own idiom. Positional per-route lines and named blocks were both rejected |
| FMT-6 | Is the Cordeau bridge allowed to renumber nodes? | No. The converted file keeps the native node ids (customers `1..n`, depots `n+1..n+t`), so a `.res` customer id is the node id and the file is traceable without a rule (§9.1) |
| FMT-7 | Are problems and solutions serialized by the same model? | No. Solutions get their own model, their own parser per family and their own writer; `TYPE : TOUR` leaves the problem vocabulary entirely (§13 item 10, `PB16`) |
| FMT-8 | Is `DEPOTS : t` needed? | **No.** A solution document states its depots in `DEPOT_SECTION` (spec §1.2.2) and a problem file never carries the keyword. One fact, one place, and the spec's keyword wins (S5) |
| FMT-9 | Where does a solution's cost come from when the routes allow recomputation? | **Both numbers are stored.** The stated value keeps the column `cost`; the value recomputed from the routes over the linked problem's distance function goes to a separate column, and a disagreement is a validation finding rather than a silent overwrite. Recomputation is possible only when the problem file is present and its `EDGE_WEIGHT_TYPE` is one we implement; otherwise the stated cost is stored as-is and marked unverified — never as zero, never as an error, and a `.tour` file (which states no cost at all) then carries none. Q1's option (c) loses the source value, so it is rejected |
| FMT-10 | Is every accepted `TYPE` defined by the LKH-3 reference? | **No, and three of them never will be.** Measured 2026-10-26: against the reference's 62 capability tokens, 8 of ours differ by letter case only, `TOUR` comes from spec [§1.1.2](./tsplib95_format.md#112-type-string), and `MDVRP`/`MDVRPTW` are the project's multi-depot types — the reference defines `MDMTSP` but no multi-depot vehicle-routing type. Both spellings are accepted because the Cordeau front end emits the instance's real type and the parser must read back what it wrote (`test_mdvrptw_round_trip_keeps_source_node_ids`) |
| FMT-11 | Do the sections of a converted Cordeau document share one node numbering? | **Yes.** `NODE_COORD_SECTION`, `DEMAND_SECTION` and `DEPOT_SECTION` use the source ids (customers `1..n`, depots `n+1..n+t`, FMT-6), and `TIME_WINDOW_SECTION`/`SERVICE_TIME_SECTION` now do too. `HEAD` renumbered the second pair from 1 with the depots first, so in a 2-depot type-6 instance customer 1's window was written on node `3` and nodes `1`–`2` read a fabricated `0.0 0.0`; nodes the source does not constrain now get no row, because `0 <latest>` would state a window the file never had. Evidence is the synthetic type-6 fixture in `test_mdvrptw_round_trip_keeps_source_node_ids`: the corpus holds no type-6 instance to measure, so the claim rests on the code path rather than on a file |

Still open:

| # | Question | Blocks | Options |
| ---: | --- | --- | --- |
| Q1 | Does a plain MDVRP conversion keep its service durations? | losslessness of every Cordeau instance that is not type 6 | (a) emit `SERVICE_TIME_SECTION` whenever a node has a duration and teach the Cordeau→`ParseResult` path to carry them — lossless, changes every existing converted file; (b) keep the section inside the time-window branch — current behaviour, drops data the source states; (c) drop durations at parse time and record the omission — honest but lossy. Measured example: `pr05` node `1` states `d=20.0`; the converted file has no `SERVICE_TIME_SECTION` and the reparse reports none |
| Q2 | How is a multi-period (PVRP/PVRPTW) solution represented, given that a customer may be served on several days? | `.res` import for types 1, 5 | (a) one document per period — simple, matches the corpus; (b) one document with the day in the depot column — reuses the field, overloads its meaning; (c) a new `<period>` column — explicit, breaks the approved shape |
| Q3 | Does the format need a `COST_TYPE` keyword whose value is `DISTANCE` or `DURATION`? | V-09 across families | (a) no, keep the source convention and document it per family — smallest surface; (b) yes, one keyword — makes V-09 checkable everywhere, adds a field every writer must fill |
| Q4 | Must both `.res` delimiter spellings be reproducible on write? | byte-exact `.res` round-trip | (a) no, delimiters are redundant — simpler; (b) yes, record which spelling was read — needed only for byte-exact dumps |
| Q5 | Should the loader derive a load for `.sol` routes (the source states none, so `ROUTE_LOAD_SECTION` is absent)? | V-07 coverage for `.sol` | (a) no — store only what the source states and leave the section absent; (b) yes, derive it and mark it as derived with a provenance flag |
| Q6 | Should `EDGE_WEIGHT_TYPES` gain the six LKH-3 distance types, and `cost.py` implementations? | parsing LKH-3-only instances | (a) not now, no corpus file uses them; (b) add the vocabulary and raise "unsupported" — better error message; (c) implement them — largest change, no test data |
| Q7 | Are `DEPOT_CAPACITY_SECTION`, `DEPOT_DURATION_SECTION`, `PERIODS`, `CAPACITY_VOL`, `CAPACITY_WEIGHT` worth keeping in the dialect given that LKH-3 cannot read them? | `PROBLEM` and the two depot sections | (a) keep — they carry data the corpus has, and this is a project dialect, not an LKH-3 file (decided in FMT-3); (b) rename them into a project namespace to make the ownership obvious; (c) drop — loses heterogeneous capacities |

## References

[architecture decisions](./ARCHITECTURE_DECISIONS.md)
[Cordeau description](./courdeau-instances-description.md)
[LKH user guide](./lkh.pdf)
[LKH-3 report](./lkh-3.pdf)
[LKH-3 reference](./LKH-3-Keld-Helsgaun.md)
[Solomon description](./solomon-instances-description.md)
[TSPLIB95 PDF](./tsplib95_specification.pdf)
[TSPLIB95 spec](./tsplib95_format.md)
