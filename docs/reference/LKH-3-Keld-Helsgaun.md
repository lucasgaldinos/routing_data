---
title: "LKH-3 (Keld Helsgaun)"
source: "http://akira.ruc.dk/~keld/research/LKH-3/"
author:
  - "Keld Helsgaun"
published:
created: 2026-10-14
description:
tags:
---

# LKH-3

**Version 3.0.14 (June** **2026)**

![VRP image](http://akira.ruc.dk/~keld/research/LKH-3/vrp.jpg)

LKH-3 is an extension of [LKH-2](http://akira.ruc.dk/~keld/research/LKH) for solving constrained traveling salesman and vehicle routing problems. The extension has been desribed in the report

> K. Helsgaun, [*An Extension of the Lin-Kernighan-Helsgaun TSP Solver for Constrained Traveling Salesman and Vehicle Routing Problems*](http://akira.ruc.dk/~keld/research/LKH-3/LKH-3_REPORT.pdf). Technical Report, Roskilde University, 2017.

## LKH-3 solving capabilities

Currently, LKH-3 is able to solve the following problem types:

From LKH-2:

> - TSP: Symmetric traveling salesman problem
> - ATSP: Asymmetric traveling salesman problem
> - HCP: Hamiltonian cycle problem
> - HPP: Hamiltonian path problem
>
> Since constraint handling adds overhead, LKH-2 is recommended for these problem types.

New in LKH-3:

> - [ACVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/ACVRP.tgz): Asymmetric capacitated vehicle routing problem
> - [ADCVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/ADCVRP.tgz): Asymmetric distance constrained vehicle routing problem
> - [BMTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/BMTSP.tgz): Bounded multiple traveling salesman problem
> - [BWTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/BWTSP.tgz): Black and white traveling salesman problem
> - [CATSPP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CATSPP.tgz): Constrained asymmetric traveling salesman path problem
> - [CBTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CBTSP.tgz): Colored balanced traveling salesman problem
> - [CBnTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CBnTSP.tgz): Colored bottleneck traveling salesman problem
> - [CluVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CluVRP.tgz): Clustered vehicle routing problem
> - [CCCTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CCCTSP.tgz): Cumulative capacitated colored traveling salesman problem
> - [CCVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CCVRP.tgz): Cumulative capacitated vehicle routing problem
> - [CTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CTSP.tgz): Colored traveling salesman problem
> - [CTSP-d](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CTSP-d.tgz): Clustered traveling salesman problem with *d* -relaxed priority rule
> - [CVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CVRP.tgz): Capacitated vehicle routing problem
> - [CVRPTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/CVRPTW.tgz): Capacitated vehicle routing problem with time windows
> - [DCVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/DCVRP.tgz): Distance constrained capacitated vehicle routing problem
> - [GCTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/GCTSP.tgz): General colored traveling salesmen problem
> - [k-TSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/k-TSP.tgz): K-traveling salesman problem
> - [1-PDTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/1-PDTSP.tgz): One-commodity pickup-and-delivery traveling salesman problem
> - [m-PDTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/m-PDTSP.tgz): Multi-commodity pickup-and-delivery traveling salesman problem
> - [m1-PDTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/m1-PDTSP.tgz): Multi-commodity one-to-one pickup-and-delivery traveling salesman problem
> - [MDMTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/MDMTSP.tgz): Multiple depot multiple traveling salesman problem
> - [MLP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/MLP.tgz): Minimum latency problem
> - [MSCTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/MSCTSP.tgz): Maximum scattered colored traveling salesman problem
> - [MTRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/MTRP.tgz): Multiple traveling repairman problem
> - [MTRPD](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/MTRPD.tgz): Multiple traveling repairman problem with distance constraints
> - [mTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/mTSP.tgz): Multiple traveling salesmen problem
> - [mTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/mTSP.tgz): Open close multiple traveling salesman problem
> - [O-k-TSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/O-k-TSP.tgz): Open k-traveling salesman problem
> - [OP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/OP.tgz): Orienteering problem
> - [OVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/OVRP.tgz): Open vehicle routing problem
> - [PCTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PCTSP.tgz): Precedence-constrained colored traveling salesman problem
> - [PC-TSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PC-TSP.tgz): Prize-collecting traveling salesman problem
> - [PDPTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PDPTW.tgz): Pickup-and-delivery problem with time windows
> - [PDTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PDTSP.tgz): Pickup-and-delivery traveling salesman problem
> - [PDTSPF](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PDTSPF.tgz): Pickup-and-delivery traveling salesman problem with FIFO loading
> - [PDTSPL](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PDTSPL.tgz): Pickup-and-delivery traveling salesman problem with LIFO loading
> - [PTP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PTP.tgz): Profitable tour problem
> - [PTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/PTSP.tgz): Homogeneous probability traveling salesman problem
> - [RCTVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/RCTVRP.tgz): Risk-constrained cash-in-transit vehicle routing problem
> - [RCTVRPTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/RCTVRPTW.tgz): Risk-constrained cash-in-transit vehicle routing with time windows
> - [SoftCluVRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/SoftCluVRP.tgz): Soft-clustered vehicle routing problem
> - [SOP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/SOP.tgz): Sequential ordering problem
> - [STTSP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/STTSP.tgz): Steiner traveling salesman problem
> - [TOP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TOP.tgz): Team orienteering problem
> - [TRP](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TRP.tgz): Traveling repairman problem
> - [TSP_mD](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TSPMD.tgz): Traveling salesman problem with multiple drones
> - [TSPDL](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TSPDL.tgz): Traveling salesman problem with draft limits
> - [TSPPD](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TSPPD.tgz): Traveling salesman problem with pickups and deliveries
> - [TSPTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/TSPTW.tgz): Traveling salesman problem with time windows
> - [VRPB](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPB.tgz): Vehicle routing problem with backhauls
> - [VRPBTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPBTW.tgz): Vehicle routing problem with backhauls and time windows
> - [VRPMPD](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPMPD.tgz): Vehicle routing problem with mixed pickup and delivery
> - [VRPMPDTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPMPDTW.tgz): Vehicle routing problem with mixed pickup and delivery and time windows
> - [VRPSPD](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPSPD.tgz): Vehicle routing problem with simultaneous pickup and delivery
> - [VRPSPDTW](http://akira.ruc.dk/~keld/research/LKH-3/BENCHMARKS/VRPSPDTW.tgz): Vehicle routing problem with simultaneous pickup-delivery and time windows

Extensive testing on benchmark instances from the literature has shown that LKH-3 is effective. Best known solutions are often obtained, and in some cases, new best solutions are found. Instances and best solutions obtained by LKH-3 may be downloaded by clicking on the problem types above. Unpack a downloaded file, *file_name.*tgz*,* by executing

```bash
tar xvfz *file_name*.tgz
```

Run scripts are provided for Unix/Linux.

A list of scientific applications of LKH may be seen [here](http://webhotel4.ruc.dk/~keld/research/LKH/ScientificApplications.html).

## Installation

LKH-3 has been implemented in the programming language C. The software is entirely written in ANSI C and portable across a number of computer platforms and C compilers.

The code can be downloaded here: [LKH-3.0.14.tgz](http://akira.ruc.dk/~keld/research/LKH-3/LKH-3.0.14.tgz) (gzipped tar file, approximately 2 MB).

On a Unix/Linux machine execute the following commands:

```bash
tar xvfz LKH-3.0.14.tgz
cd LKH-3.0.14
make
```

An executable file called LKH will now be available in the directory LKH-3.0.14.

A stand-alone executable for Windows machines may be downloaded [here](http://akira.ruc.dk/~keld/research/LKH-3/LKH-3.exe). A Visual Studio 2022 project is available [here.](http://akira.ruc.dk/~keld/research/LKH-3/LKHWin-3.0.14.zip)

The code is distributed for academic and non-commercial use. The author reserves all rights to the code.

## CHANGES

### CHANGES IN VERSION LKH-3.0.14

Added code for solving

- the Orienteering Problem (OP),
- the Team Orienteering Problem (TOP),
- the Traveling Salesman with Multiple Drones (TSP-mD)
- (PROBLEM_TYPE = TSPMD; new keywords: DRONES, ENDURANCE),
- the Open k-Traveling Salesman Problem (O-k-TSP) (PROBLEM_TYPE = OKSTP),
- the Prize-collecting Traveling Salesman Problem (PC-TSP), and
- the Profitable Tour Problem (PTP); new keyword: ALPHA.

### CHANGES IN VERSION LKH-3.0.13

Added code for solving

- the maximum scattered colored traveling salesman problem (MSCTSP),
- the precedence-constrained colored traveling salesman problem (PCTSP), and
- the constrained asymmetric traveling salesman path problem (CATSPP).

### CHANGES IN VERSION LKH-3.0.12

Added code for solving

- the general colored traveling salesman problem (GCTSP) and
- the capacitated colored traveling salesman problem (CCCTSP).

### CHANGES IN VERSION LKH-3.0.11

Added code for solving

- the clustered vehicle routing problem (CluVRP) and
- the soft-clustered vehicle routing problem (SoftCluVRP).

### CHANGES IN VERSION LKH-3.0.10

Added code for solving

- the bounded multiple traveling salesman problem (BMTSP),
- the colored balanced traveling salesman problem (CBTSP),
- the colored bottleneck traveling salesman problem (CBnTSP),
- the homogeneous probability traveling salesman problem (PTSP), and
- the tlustered traveling salesman problem with *d* -relaxed priority rule (CTSP-d).
- New keyword:

  > PROBABILITY

### CHANGES IN VERSION LKH-3.0.9

- Added code for solving the k-traveling salesman problem (kTSP).
- New keyword:

  > K

### CHANGES IN VERSION LKH-3.0.8

- Tours may now be recombined by Xavier Clarist's recombination (CLARIST).

  CLARIST recombination is used by giving the following specification in the parameter file

  > RECOMBINATION = CLARIST

### CHANGES IN LKH-3.0.7

- Added code for solving the asymmetric distance constrained vehicle routing problem (ADCVRP).

### CHANGES IN LKH-3.0.6

- Added code for solving the Steiner traveling saleman problem (STTSP).
- New keyword:

  > REQUIRED_NODES_SECTION

### CHANGES IN LKH-3.0.5

- Added code for solving the open close multiple traveling saleman problem (OCMTSP).
- New keyword:

  > EXTERNAL_SALESMEN

### CHANGES IN LKH-3.0.4

- Added code for solving the colored traveling saleman problem (CTSP). The node coloring is described in a

  > CTSP_SET_SECTION

- New initial tour algorithm: CTSP
- Added code for solving the minimum latency problem (MLP).

### CHANGES IN LKH-3.0.3

- Candidate sets may now be created by means of POPMUSIC by giving the following specification in the parameter file for LKH:

  > CANDIDATE_SET_TYPE = POPMUSIC

  The value of the parameter MAX_CANDIDATES is used to trim the candidate set. There are, however, some other POPMUSIC related parameters. If not specified, they will take their default values. These parameters are:

  > POPMUSIC_SAMPLE_SIZE = \<int>
  > Sample size.
  > Default: 10
  >
  > POPMUSIC_SOLUTIONS = \<int>
  > Number of solutions to generate.
  > Default: 50
  >
  > POPMUSIC_MAX_NEIGHBORS = \<int>
  > Maximum number of nearest neighbors used as candidates in iterated 3-opt for
  > POPMUSIC.
  > Default: 5
  >
  > POPMUSIC_TRIALS = \<int>
  > Number of trials used in iterated 3-opt for POPMUSIC. If the value is zero, the number of trials is the size of the subpath to be optimized.
  > Default: 1
  >
  > POPMUSIC_INITIAL_TOUR = { YES | NO }
  > Specifies whether the first generated POPMUSIC tour is used as initial tour for Lin-Kernighan.
  > Default: NO

### CHANGES IN LKH-3.0.2

- Tours may now be recombined by GPX2 (Generalized Partition Crossover 2) instead of IPT (Iterative Partial Transcription).

  GPX2 is used by giving the following specification in the parameter file:

  > RECOMBINATION = GPX2

  The possible settings are:

  > RECOMBINATION = { IPT | GPX2 }

  IPT is default.

### CHANGES IN LKH-3.0.1

- Added code for solving the traveling saleman problem with draft limits (TSPDL).

## NEW IN LKH-3

### New parameter keywords

> - BWTSP = \<integer> \<integer> \[ \<integer> \]
> - DEPOT = \<integer>
> - MAKESPAN = { YES | NO }
> - MTSP_MIN_SIZE = \<integer>
> - MTSP_MAX_SIZE = \<integer>
> - MTSP_OBJECTIVE = \[ MINMAX | MINMAX_SIZE | MINSUM \]
> - MTSP_SOLUTION_FILE = \<string>
> - SINTEF_SOLUTION_FILE = \<string>
> - SALESMEN = \<integer>
> - SCALE = \<integer>
> - SPECIAL
> - VEHICLES = \<integer>

### New initial tour algorithms

> - CVRPR
> - MTSP
> - SOP

### New move types

> - 3 SPECIAL
> - 5 SPECIAL

### New TSPLIB format keywords

The specification part:

- DISTANCE: \<real>
- GRID_SIZE: \<real>
- RISK_THRESHOLD: \<integer>
- SALESMEN: \<integer>
- SCALE: \<integer>
- SERVICE_TIME: \<integer>
- VEHICLES: \<integer>

### New edge weight types

- EXACT_2D
- EXACT_3D
- FLOOR_2D
- FLOOR_3D
- TOR_2D
- TOR_3D

And the **data part**

- BACKHAUL_SECTION
- PICKUP_AND_DELIVERY_SECTION
- SERVICE_TIME_SECTION
- TIME_WINDOW_SECTION

[home](http://www.akira.ruc.dk/~keld)
