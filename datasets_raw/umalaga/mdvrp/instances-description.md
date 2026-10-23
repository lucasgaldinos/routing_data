---
title: "Description for files of Cordeau’s Instances | Vehicle Routing Problem"
source: "https://neo.lcc.uma.es/vrp/vrp-instances/description-for-files-of-cordeaus-instances/"
created: 2026-10-22
description: "Reference documentation for the file format of Cordeau's VRP benchmark instances, covering the structure of data and solution files across VRP, PVRP, MDVRP, SDVRP, and their time-windowed variants."
tags:
  - "operations-research/optimization/vehicle-routing"
  - "computer-science/algorithms/combinatorial"
  - "operations-research/benchmarking"
  - "data-formatting/file-formats"
  - "information-science/documentation"
image:
icon: "https://neo.lcc.uma.es/favicon.ico"
---

# Description for Files of Cordeau's Instances

The format of data and solution files in all directories is as follows.

## Data Files

### Header Line

The first line contains the following information:

| Field | Description |
| ------- | ------------- |
| `type` | Problem type (see table below) |
| `m` | Number of vehicles |
| `n` | Number of customers |
| `t` | Number of days (PVRP), depots (MDVRP), or vehicle types (SDVRP) |

#### Problem Types (`type`)

| Value | Type |
| ------- | ------ |
| 0 | VRP |
| 1 | PVRP |
| 2 | MDVRP |
| 3 | SDVRP |
| 4 | VRPTW |
| 5 | PVRPTW |
| 6 | MDVRPTW |
| 7 | SDVRPTW |

Format: `type m n t`

### Day / Depot / Vehicle Type Lines

The next `t` lines contain, for each day (or depot or vehicle type), the following information:

| Field | Description |
| ------- | ------------- |
| `D` | Maximum duration of a route |
| `Q` | Maximum load of a vehicle |

Format: `D Q`

### Customer Lines

The next lines contain, for each customer, the following information:

| Field | Description |
| ------- | ------------- |
| `i` | Customer number |
| `x` | x coordinate |
| `y` | y coordinate |
| `d` | Service duration |
| `q` | Demand |
| `f` | Frequency of visit |
| `a` | Number of possible visit combinations |
| `list` | List of all possible visit combinations |
| `e` | Beginning of time window (earliest time for start of service), if any |
| `l` | End of time window (latest time for start of service), if any |

Format: `i x y d q f a list e l`

### Visit Combination Encoding

Each visit combination is coded with the decimal equivalent of the corresponding binary bit string.

> **Example:** In a 5-day period, the code `10` is equivalent to the bit string `01010`, meaning a customer is visited on days 2 and 4. (Days are numbered from left to right.)

### Notes

- In the case of the **MDVRP**, the lines go from `1` to `n + t`, and the last `t` entries correspond to the `t` depots.
- In the case of the **VRP, PVRP, and MDVRP**, the lines go from `0` to `n`, and the first entry corresponds to the unique depot.

## Solution Files

### Cost Line

The first line contains the cost of the solution (total duration excluding service time).

### Route Lines

The next lines contain, for each route, the following information:

| Field | Description |
| ------- | ------------- |
| `l` | Number of the day (or depot or vehicle type) |
| `k` | Number of the vehicle |
| `d` | Duration of the route |
| `q` | Load of the vehicle |
| `list` | Ordered sequence of customers (with start-of-service times, if applicable) |

Format: `l k d q list`
