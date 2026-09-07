"""JSON output writer for TSPLIB converter."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from ..core.transformer import DataTransformer


class JSONWriter:
    """
    JSON output writer for TSPLIB converter.

    Features:
    - Flattened JSON structure generation
    - Directory organization by problem type
    - File management and overwrites
    - Pretty printing support
    """

    def __init__(
        self,
        output_dir: str = "./datasets/json",
        pretty: bool = True,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize JSON writer.

        Args:
            output_dir: Base directory for JSON output
            pretty: Whether to pretty-print JSON
            logger: Optional logger instance
        """
        self.output_dir = Path(output_dir)
        self.pretty = pretty
        self.logger = logger or logging.getLogger(__name__)
        self.transformer = DataTransformer(logger=self.logger)

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_problem(
        self,
        data: Dict[str, Any],
        organize_by_type: bool = True
    ) -> str:
        """
        Write problem data to JSON file.

        Args:
            data: Problem data dictionary
            organize_by_type: Whether to organize files by problem type

        Returns:
            Path to written JSON file
        """
        # Extract problem metadata
        problem_data = data.get('problem_data', {})
        problem_name = problem_data.get('name', 'unknown')
        problem_type = problem_data.get('type', 'unknown')

        # Determine output path
        if organize_by_type:
            type_dir = self.output_dir / problem_type.lower()
            type_dir.mkdir(parents=True, exist_ok=True)
            output_path = type_dir / f"{problem_name}.json"
        else:
            output_path = self.output_dir / f"{problem_name}.json"

        # Use transformer to create consistent JSON structure (no duplication)
        json_data = self.transformer.to_json_format(data)

        # Write JSON file
        try:
            with open(output_path, 'w') as f:
                if self.pretty:
                    json.dump(json_data, f, indent=2, default=str)
                else:
                    json.dump(json_data, f, default=str)

            self.logger.info(f"Wrote JSON file: {output_path}")
            return str(output_path)

        except Exception as e:
            self.logger.error(f"Failed to write JSON file {output_path}: {e}")
            raise

    def write_batch(
        self,
        data_list: list,
        organize_by_type: bool = True
    ) -> list:
        """
        Write multiple problems to JSON files.

        Args:
            data_list: List of problem data dictionaries
            organize_by_type: Whether to organize by type

        Returns:
            List of paths to written JSON files
        """
        paths = []

        for data in data_list:
            try:
                path = self.write_problem(data, organize_by_type)
                paths.append(path)
            except Exception as e:
                self.logger.error(f"Failed to write problem: {e}")

        return paths

    def get_output_path(
        self,
        problem_name: str,
        problem_type: str = None,
        organize_by_type: bool = True
    ) -> str:
        """
        Get output path for a problem without writing.

        Args:
            problem_name: Name of problem
            problem_type: Type of problem
            organize_by_type: Whether to organize by type

        Returns:
            Expected output path as string
        """
        if organize_by_type and problem_type:
            type_dir = self.output_dir / problem_type.lower()
            output_path = type_dir / f"{problem_name}.json"
        else:
            output_path = self.output_dir / f"{problem_name}.json"

        return str(output_path)
