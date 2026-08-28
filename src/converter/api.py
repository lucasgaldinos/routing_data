"""
Simple API for TSPLIB95 Converter Package

Provides clean, easy-to-use functions for parsing TSPLIB files
and converting them to various output formats.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from logging import Logger

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

    def __init__(self, logger: Optional[Logger] = None) -> None:
        """Initialize the converter with default components."""
        self.logger: Logger = logger or setup_logging()
        self.parser = FormatParser(logger=self.logger)
        self.transformer = DataTransformer(logger=self.logger)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
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

    def to_json(self, data: Dict[str, Any], output_path: str) -> None:
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
        with open(output_path, 'w') as f:
            json.dump(json_data, f, indent=2)

    def to_database(self, data: Dict[str, Any], db_path: str) -> int:
        """
        Store problem data in DuckDB database.

        Args:
            data: Parsed problem data
            db_path: Path to DuckDB database file

        Returns:
            Problem ID in database
        """
        # Initialize database manager
        db_manager = DatabaseManager(db_path, logger=self.logger)

        # Insert problem data
        problem_id = db_manager.insert_problem(data['problem_data'])

        # Insert nodes if available
        if data.get('nodes'):
            db_manager.insert_nodes(problem_id, data['nodes'])

        return problem_id

    def process_directory(self, input_dir: str, output_dir: str,
                         formats: Optional[List[str]] = None, workers: int = 4) -> Dict[str, Any]:
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
            formats = ['json']

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        # Find TSPLIB files
        patterns = ['*.tsp', '*.vrp', '*.atsp', '*.hcp', '*.sop', '*.tour']
        files: List[Path] = []
        for pattern in patterns:
            files.extend(input_path.glob(f"**/{pattern}"))

        # Initialize outputs
        json_writer: Optional[JSONWriter] = None
        db_manager: Optional[DatabaseManager] = None

        if 'json' in formats:
            json_writer = JSONWriter(str(output_path / 'json'), logger=self.logger)

        if 'database' in formats:
            db_manager = DatabaseManager(str(output_path / 'routing.duckdb'), logger=self.logger)

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
                    problem_id = db_manager.insert_problem(data['problem_data'])
                    if data.get('nodes'):
                        db_manager.insert_nodes(problem_id, data['nodes'])

                successful += 1
                self.logger.info(f"Processed: {file_path.name}")

            except Exception as e:
                failed += 1
                self.logger.error(f"Failed to process {file_path}: {e}")

        return {
            'total_files': len(files),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(files) if files else 0
        }


# Global instance for simple function-based API
_default_converter = SimpleConverter()


def parse_file(file_path: str) -> Dict[str, Any]:
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


def to_json(data: Dict[str, Any], output_path: str) -> None:
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


def to_database(data: Dict[str, Any], db_path: str) -> int:
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


def process_directory(input_dir: str, output_dir: str,
                     formats: Optional[List[str]] = None, workers: int = 4) -> Dict[str, Any]:
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


def create_simple_converter(logger: Optional[Logger] = None) -> SimpleConverter:
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