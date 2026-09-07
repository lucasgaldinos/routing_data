"""
Module-level worker functions for ProcessPoolExecutor.

These functions must be defined at module level (not nested) to be picklable
by multiprocessing. They receive all dependencies as arguments instead of
capturing them from closures.
"""

import hashlib
from pathlib import Path
from typing import Any


def process_file_for_parallel(  # noqa: ARG001 — output_dir kept for the worker API shape
    file_path: str, output_dir: str
) -> dict[str, Any]:
    """
    Process a single TSPLIB file for parallel execution.

    This function is designed to be picklable for ProcessPoolExecutor.
    It performs CPU-bound operations (parsing, transformation) and returns
    results for the main process to handle I/O operations (DB, JSON writes).

    Args:
        file_path: Path to TSPLIB file to process
        output_dir: Output directory for JSON files

    Returns:
        Dictionary with processed data:
        {
            'file_path': str,
            'success': bool,
            'problem_data': dict (if success),
            'transformed_data': dict (if success),
            'checksum': str (if success),
            'solution_data': dict (if success and solution found),
            'edge_weight_data': dict (if success and EXPLICIT),            'edges': list (if success; HCP adjacency pairs),
            'fixed_edges': list (if success; FIXED_EDGES pairs),            'error': str (if failure),
            'error_type': str (if failure)
        }
    """
    try:
        # Import here to avoid pickling issues with module-level imports
        import logging

        from tsplib_parser.parser import FormatParser

        from converter.core.transformer import DataTransformer

        # Use process-local logger (not pickled from parent)
        logger = logging.getLogger(f"worker.{Path(file_path).name}")
        logger.setLevel(logging.INFO)

        # Initialize components
        parser = FormatParser(logger=logger)
        transformer = DataTransformer(logger=logger)

        # Step 1: Parse file (CPU-bound)
        logger.info(f"Processing new file: {file_path}")
        parsed_result = parser.parse_file(file_path)

        # Step 2: Transform data (CPU-bound)
        transformed_data = transformer.transform_problem(problem_data=parsed_result)

        # Step 3: Calculate checksum (CPU-bound)
        checksum: str = calculate_checksum(file_path)

        # Step 4: Check for solution file (I/O, but minimal)
        solution_data = None
        tour_file: str | None = transformer.find_solution_file(problem_file_path=file_path)
        if tour_file:
            # Decision #6: thread the linked problem's dimension so the tour
            # parser can pre-inject a missing DIMENSION line.
            problem_dimension = transformed_data["problem_data"].get("dimension")
            solution_data: dict[str, Any] | None = transformer.parse_solution_data(
                solution_file_path=tour_file, parser=parser, problem_dimension=problem_dimension
            )

        # Step 4b: Task 2.2 — backfill a missing solution cost from the problem's
        # weight data when the source comment is absent (user decision
        # 2026-08-28). The EXPLICIT matrix wins; otherwise coords +
        # edge_weight_type. Unweighted problems (e.g. HCP adjacency) stay NULL.
        if solution_data is not None and solution_data.get("cost") is None:
            from converter.utils.cost import compute_routes_cost

            backfilled = compute_routes_cost(
                solution_data.get("routes", []),
                matrix=transformed_data.get("edge_weight_matrix"),
                coords=transformed_data.get("coords"),
                edge_weight_type=transformed_data["problem_data"].get("edge_weight_type"),
            )
            if backfilled is not None:
                solution_data["cost"] = backfilled
                logger.info(
                    "Backfilled cost for %s: %.2f (%s)",
                    file_path,
                    backfilled,
                    (
                        "matrix"
                        if transformed_data.get("edge_weight_matrix") is not None
                        else "coords"
                    ),
                )

        # Step 5: Prepare edge weight data if present (EXPLICIT problems)
        # Decision #2: emit the full n x n nested-list `matrix`, not a JSON string.
        edge_weight_data = None
        if "edge_weight_matrix" in transformed_data:
            # Use actual matrix dimension (may differ from problem dimension for VRP customer-only matrices)
            matrix = transformed_data["edge_weight_matrix"]
            edge_weight_data = {
                "matrix": matrix,
                "matrix_format": transformed_data["problem_data"].get("edge_weight_format"),
                "is_symmetric": parsed_result["metadata"]["is_symmetric"],
            }

        return {
            "file_path": file_path,
            "success": True,
            "problem_data": transformed_data["problem_data"],
            "nodes": transformed_data["nodes"],
            "transformed_data": transformed_data,  # For JSON output
            "checksum": checksum,
            "solution_data": solution_data,
            "edge_weight_data": edge_weight_data,
            "edges": transformed_data.get("edges"),
            "fixed_edges": transformed_data.get("fixed_edges"),
            # Schema v2 array-column payload (Task 1.2 / Decision 3)
            "coords": transformed_data.get("coords"),
            "display_coords": transformed_data.get("display_coords"),
            "demands": transformed_data.get("demands"),
            "depots": transformed_data.get("depots"),
            "metadata": parsed_result["metadata"],
        }

    except Exception as e:
        return {
            "file_path": file_path,
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def calculate_checksum(file_path: str) -> str:
    """
    Calculate SHA-256 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal checksum string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
