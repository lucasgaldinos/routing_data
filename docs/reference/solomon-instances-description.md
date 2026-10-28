---
title: "Capacitated VRP with Time Windows Instances | Vehicle Routing Problem"
source: "https://neo.lcc.uma.es/vrp/vrp-instances/capacitated-vrp-with-time-windows-instances/"
author:
  - "[[Lucas Galdino]]"
published:
created: 2026-10-25
description: "Reference documentation for the file format of Solomon's VRPTW benchmark instances, covering data and solution file structure and the extended Homberger sets with 200–1000 customers."
tags:
  - "operations-research/optimization/vehicle-routing/vrptw"
  - "operations-research/benchmarking/benchmark-instances"
  - "computer-science/algorithms/combinatorial"
  - "data-formatting/file-formats"
  - "information-science/documentation"
  - "solomon/generated"
  - "homberger/generated"
  - "breedam/generated"
  - "cordeau/generated"
  - "russell/generated"
image:
icon: "https://neo.lcc.uma.es/favicon.ico"
---
---
title: "Description for files of Solomon’s Instances | Vehicle Routing Problem"
source: "https://neo.lcc.uma.es/vrp/vrp-instances/description-for-files-of-solomons-instances/"
created: 2026-10-22
description: "Reference documentation for the file format of Solomon's VRPTW benchmark instances, covering the structure of data files and solution files."
tags:
  - "operations-research/optimization/vehicle-routing"
  - "computer-science/algorithms/combinatorial"
  - "operations-research/benchmarking"
  - "data-formatting/file-formats"
  - "information-science/documentation"
image:
icon: "https://neo.lcc.uma.es/favicon.ico"
---

# Description for Files of Solomon's Instances

## Data Files

The first line contains the problem's name.

The next line is composed of:

`K Q`

| Field | Description |
| ------- | ------------- |
| `K` | Vehicle number |
| `Q` | Capacity |

The rest of the lines have the following structure:

`i x y q e l d`

| Field | Description |
| ------- | ------------- |
| `i` | Customer number |
| `x` | x coordinate |
| `y` | y coordinate |
| `q` | Demand |
| `e` | Ready time |
| `l` | Due date |
| `d` | Service duration |

## Solution Files

Contains, for each route, the sequence of customers to be visited.

The last line contains the cost of the solution (total duration excluding service time).