"""
TSPLIB95 Converter Package

A simple and efficient converter for TSPLIB95/VRP problem instances.
Converts routing problem files into JSON format and DuckDB database.

Features:
- Fast parsing without O(n²) edge precomputation
- Support for TSP, VRP, ATSP, HCP, SOP, and TOUR files
- Handles both coordinate-based and explicit weight matrix problems
- Simple API for package usage
- JSON and database output formats

Example usage:
    import converter

    # Parse single file
    data = converter.parse_file("path/to/problem.tsp")

    # Convert to JSON
    converter.to_json(data, "output.json")

    # Store in database
    converter.to_database(data, "routing.duckdb")

    # Process directory
    converter.process_directory("problems/", "output/")
"""

from __future__ import annotations

from .api import (
  create_simple_converter,
  parse_file,
  process_directory,
  to_database,
  to_json,
)

__version__ = "1.0.0"
__author__ = "TCC Routing Data Project"
__all__ = ["create_simple_converter", "parse_file", "process_directory", "to_database", "to_json"]
