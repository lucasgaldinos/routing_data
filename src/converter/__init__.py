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

# Lazy imports to avoid circular dependencies
from collections.abc import Callable
from typing import Any

from submodules.Routing_data.src.converter.api import (
    create_simple_converter,
    parse_file,
    process_directory,
    to_database,
    to_json,
)


def __getattr__(name) -> Callable[..., dict[str, Any]] | Callable[..., None] | Callable[..., int] | Callable[..., dict[str, Any]] | Callable[..., SimpleConverter]:
    if name == 'parse_file':
        from .api import parse_file
        return parse_file
    elif name == 'to_json':
        from .api import to_json
        return to_json
    elif name == 'to_database':
        from .api import to_database
        return to_database
    elif name == 'process_directory':
        from .api import process_directory
        return process_directory
    elif name == 'create_simple_converter':
        from .api import create_simple_converter
        return create_simple_converter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__version__ = "1.0.0"
__author__ = "TCC Routing Data Project"
__all__ = [
    "create_simple_converter",
    "parse_file",
    "process_directory",
    "to_database",
    "to_json"
]
