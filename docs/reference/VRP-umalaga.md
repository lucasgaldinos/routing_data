---
title: "Vehicle Routing Problem | Vehicle Routing Problem"
source: "https://neo.lcc.uma.es/vrp/vehicle-routing-problem/"
author:
published:
created: 2026-10-22
description:
tags:
  - "operational-research"
---
## Introduction

The vehicle routing problem (VRP) is a combinatorial optimization and integer programming problem seeking to service a number of customers with a fleet of vehicles. Proposed by Dantzig and Ramser in 1959, VRP is an important problem in the fields of transportation, distribution, and logistics.

## Description

The Vehicle Routing Problem (VRP) is a generic name given to a whole class of problems in which a set of routes for a fleet of vehicles based at one or several depots must be determined for a number of geographically dispersed cities or customers. The objective of the VRP is to deliver a set of customers with known demands on minimum-cost vehicle routes originating and terminating at a depot. In the two figures below we can see a picture of a typical input for a VRP problem and one of its possible outputs:

![Vehicle Routing Problem](https://neo.lcc.uma.es/vrp/wp-content/uploads/vrp.png)

An instance of a VRP (left) and its solution (right)

## Formulation

The VRP is a combinatorial problem whose ground set is the edges of a graph ${G(V,E)}$. The notation used for this problem is as follows:

- ${V = \left\lbrace v_{0}, v_{1}, …, v_{n} \right\rbrace}$ is a vertex set, where:
- Consider a depot to be located at ${v_0}$.
	- Let ${V’ = V \backslash \left\lbrace v_{0} \right\rbrace}$ be used as the set of ${n}$ cities.
- ${A = \left\lbrace(v_{i},v_{j}) | v_{i},v_{j} \in V; i \neq j \right\rbrace}$ is an arc set.
- ${C}$ is a matrix of non-negative costs or distances ${c_{ij}}$ between customers ${v_{i}}$ and ${v_{j}}$.
- ${d}$ is a vector of the customer demands.
- ${R_{i}}$ is the route for vehicle ${i}$.
- ${m}$ is the number of vehicles (all identical). One route is assigned to each vehicle.

When ${c_{ij} = c_{ji}}$ for all ${(v_{i}, v_{j}) \in A}$ the problem is said to be symmetric and it is then common to replace ${A}$ with the edge set ${E = \left\lbrace(v_{i},v_{j}) | v_{i},v_{j} \in V; i \lt j \right\rbrace}$.

With each vertex ${v_{i}}$ in ${V’}$ is associated a quantity ${q_{i}}$ of some goods to be delivered by a vehicle. The VRP thus consists of determining a set of ${m}$ vehicle routes of minimal total cost, starting and ending at a depot, such that every vertex in ${V’}$ is visited exactly once by one vehicle.

For easy computation, it can be defined ${b(V) = \left\lceil \sum_{v_{i} \in V} d_{i}) / C \right\rceil}$, an obvious lower bound on the number of trucks needed to service the customers in set ${V}$.

We will consider a service time ${\delta_{i}}$ (time needed to unload all goods), required by a vehicle to unload the quantity ${q_{i}}$ at ${v_{i}}$. It is required that the total duration of any vehicle route (travel plus service times) may not surpass a given bound ${D}$, so, in this context the cost ${c_{ij}}$ is taken to be the travel time between the cities. The VRP defined above is NP-hard \[[Lenstra & Rinnooy Kan 1981](https://neo.lcc.uma.es/vrp/bibliography-on-vrp/#LenstraKan)\].

A feasible solution is composed of:

- a partition ${R_{1}, … , R_{m}}$ of ${V}$;
- a permutation ${\sigma_{i}}$ of ${R_{i} \bigcup {0}}$ specifying the order of the customers on route ${i}$.

The **cost of a given route** (${R_{i} = \left\lbrace v_{0}, v_{1}, …, v_{m+1} \right\rbrace}$), where ${v_{i} \in V}$ and ${v_{0} = v_{m+1} = 0}$ (0 denotes the depot), is given by ${C(R_{i}) = \sum_{i=0}^{m} c_{i,i+1} + \sum_{i=1}^{m} \delta_{i}}$.

A route ${R_{i}}$ is feasible if the vehicle stop exactly once in each customer and the total duration of the route does not exceed a prespecified bound ${D}$: ${C(R_{i}) \leq D}$.

Finally, the **cost of the problem solution** ${S}$ is: ${F_{VRP} = \sum_{i=1}^{m} F(R_{i})}$.