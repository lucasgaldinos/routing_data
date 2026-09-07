"""
Simple API for TSPLIB95 Converter Package

Provides clean, easy-to-use functions for parsing TSPLIB files
and converting them to various output formats.
"""

import json
import os
from logging import Logger
from pathlib import Path
from typing import Any

from tsplib_parser.parser import FormatParser

from .core.transformer import DataTransformer
from .database.operations import DatabaseManager
from .output.json_writer import JSONWriter
from .utils.logging import setup_logging


class SimpleConverter:
    """
    A simple, easy-to-use converter for TSPLIB problems.

    Usage:
        converter = SimpleConverter()
        data = converter.parse_file("problem.tsp")
        converter.to_json(data, "output.json")
    """

    def __init__(self, logger: Logger | None = None) -> None:
        """Initialize the converter with default components."""
        self.logger: Logger = logger or setup_logging()
        self.parser = FormatParser(logger=self.logger)
        self.transformer = DataTransformer(logger=self.logger)

    def parse_file(self, file_path: str) -> dict[str, Any]:
        """
        Parse a single TSPLIB file.

        Args:
            file_path: Path to the TSPLIB file

        Returns:
            Dictionary containing problem data, nodes, tours, and metadata
        """
        # Parse the file
        parsed_data = self.parser.parse_file(file_path)

        # Transform for better structure
        transformed_data = self.transformer.transform_problem(parsed_data)

        return transformed_data

    def to_json(self, data: dict[str, Any], output_path: str) -> None:
        """
        Save problem data as JSON file.

        Args:
            data: Parsed problem data
            output_path: Path for output JSON file
        """
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Convert to JSON-friendly format
        json_data = self.transformer.to_json_format(data)

        # Write to file
        with open(output_path, "w") as f:
            json.dump(json_data, f, indent=2)

    def to_database(self, data: dict[str, Any], db_path: str) -> int:
        """
        Store problem data in DuckDB database (schema v2).

        Args:
            data: Parsed and transformed problem data
            db_path: Path to DuckDB database file

        Returns:
            Problem ID in database
        """
        # Initialize database manager
        db_manager = DatabaseManager(db_path, logger=self.logger)

        # Hub + per-type row in one transaction (Task 1.2 dispatch). The v2
        # insert payload merges problem_data with the top-level array-column
        # keys; the v1 `insert_nodes` path is retired with the nodes table
        # (Decision 3).
        problem_id = db_manager.insert_problem(_merge_v2_payload(data))

        return problem_id

    def process_directory(
        self,
        input_dir: str,
        output_dir: str,
        formats: list[str] | None = None,
        workers: int = 4,  # noqa: ARG002 — unused; kept for the public API shape
    ) -> dict[str, Any]:
        """
        Process all TSPLIB files in a directory.

        Args:
            input_dir: Directory containing TSPLIB files
            output_dir: Output directory for results
            formats: List of output formats ('json', 'database')

        Returns:
            Processing statistics
        """
        if formats is None:
            formats = ["json"]

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        # Find TSPLIB files
        patterns = ["*.tsp", "*.vrp", "*.atsp", "*.hcp", "*.sop", "*.tour"]
        files: list[Path] = []
        for pattern in patterns:
            files.extend(input_path.glob(f"**/{pattern}"))

        # Initialize outputs
        json_writer: JSONWriter | None = None
        db_manager: DatabaseManager | None = None

        if "json" in formats:
            json_writer = JSONWriter(str(output_path / "json"), logger=self.logger)

        if "database" in formats:
            db_manager = DatabaseManager(str(output_path / "routing.duckdb"), logger=self.logger)

        # Process files
        successful = 0
        failed = 0

        for file_path in files:
            try:
                # Parse and transform
                data = self.parse_file(str(file_path))

                # Write outputs
                if json_writer:
                    json_writer.write_problem(data)

                if db_manager:
                    db_manager.insert_problem(_merge_v2_payload(data))

                successful += 1
                self.logger.info(f"Processed: {file_path.name}")

            except Exception as e:
                failed += 1
                self.logger.error(f"Failed to process {file_path}: {e}")

        return {
            "total_files": len(files),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(files) if files else 0,
        }


def _merge_v2_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build the schema-v2 insert payload from a transformed result.

    ``DatabaseManager.insert_problem`` expects the merged payload (Task 1.2):
    the hub + shared columns live under ``problem_data``; the per-type array
    columns (``coords`` / ``display_coords`` / ``demands`` / ``depots``) and
    the graph data (``edges`` / ``fixed_edges``) are top-level siblings. The v1
    ``nodes`` row-table is gone (Decision 3), so no ``nodes`` key is forwarded.

    Satellite data rides along under the keys ``_insert_batch_satellites``
    consumes (Task 2.1 rework): an EXPLICIT problem's ``edge_weight_matrix`` is
    wrapped into ``edge_weight_data`` (the matrix row is the problem's only
    distance data — dropping it stores an unreadable problem), and
    ``solution_data`` / ``file_path`` / ``checksum`` / ``file_size`` pass
    through so the write path persists them when the payload provides them.
    """
    problem_data: dict[str, Any] = dict(data.get("problem_data", {}))
    file_path: str | None = data.get("file_path") or problem_data.get("file_path")
    merged: dict[str, Any] = {
        **problem_data,
        "coords": data.get("coords"),
        "display_coords": data.get("display_coords"),
        "demands": data.get("demands", []),
        "depots": data.get("depots", []),
        "adjacency": data.get("edges"),
        "fixed_edges": data.get("fixed_edges"),
        # Satellites (Task 2.1): EXPLICIT problems carry their only distance
        # data as a matrix row in edge_weight_matrices.
        "edge_weight_data": (
            {
                "matrix": data["edge_weight_matrix"],
                "matrix_format": problem_data.get("edge_weight_format"),
                "is_symmetric": data.get("metadata", {}).get("is_symmetric"),
            }
            if data.get("edge_weight_matrix") is not None
            else None
        ),
        "solution_data": data.get("solution_data"),
        "file_path": file_path,
        "checksum": data.get("checksum"),
        "file_size": (
            Path(file_path).stat().st_size if file_path and Path(file_path).exists() else 0
        ),
    }
    return merged


# Global instance for simple function-based API
_default_converter = SimpleConverter()


def parse_file(file_path: str) -> dict[str, Any]:
    """
    Parse a single TSPLIB file.

    Args:
        file_path: Path to the TSPLIB file

    Returns:
        Dictionary containing problem data, nodes, tours, and metadata

    Example:
        data = parse_file("gr17.tsp")
        print(f"Problem: {data['problem_data']['name']}")
        print(f"Nodes: {len(data['nodes'])}")
    """
    return _default_converter.parse_file(file_path)


def to_json(data: dict[str, Any], output_path: str) -> None:
    """
    Save problem data as JSON file.

    Args:
        data: Parsed problem data from parse_file()
        output_path: Path for output JSON file

    Example:
        data = parse_file("problem.tsp")
        to_json(data, "output/problem.json")
    """
    return _default_converter.to_json(data, output_path)


def to_database(data: dict[str, Any], db_path: str) -> int:
    """
    Store problem data in DuckDB database.

    Args:
        data: Parsed problem data from parse_file()
        db_path: Path to DuckDB database file

    Returns:
        Problem ID in database

    Example:
        data = parse_file("problem.tsp")
        problem_id = to_database(data, "routing.duckdb")
    """
    return _default_converter.to_database(data, db_path)


def process_directory(
    input_dir: str, output_dir: str, formats: list[str] | None = None, workers: int = 4
) -> dict[str, Any]:
    """
    Process all TSPLIB files in a directory.

    Args:
        input_dir: Directory containing TSPLIB files
        output_dir: Output directory for results
        formats: List of output formats ('json', 'database')

    Returns:
        Processing statistics

    Example:
        stats = process_directory("problems/", "output/", ["json", "database"])
        print(f"Processed {stats['successful']} files")
    """
    return _default_converter.process_directory(input_dir, output_dir, formats, workers)


def create_simple_converter(logger: Logger | None = None) -> SimpleConverter:
    """
    Create a new SimpleConverter instance.

    Args:
        logger: Optional custom logger

    Returns:
        New SimpleConverter instance

    Example:
        converter = create_simple_converter()
        data = converter.parse_file("problem.tsp")
    """
    return SimpleConverter(logger=logger)
