#!/usr/bin/env python3
"""
Test script to verify full edge weight pipeline: parse → transform → database.
"""

import json
import sys
from pathlib import Path

import duckdb

from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.utils.logging import setup_logging
from tsplib_parser.parser import FormatParser


def main():
  logger = setup_logging(level="INFO")

  # Use temporary database
  db_path = "/tmp/test_edge_weights.duckdb"
  if Path(db_path).exists():
    Path(db_path).unlink()

  print(f"\n{'=' * 70}")
  print("Testing full edge weight pipeline")
  print(f"{'=' * 70}\n")

  try:
    # Step 1: Parse
    parser = FormatParser(logger=logger)
    file_path = "datasets_raw/problems/atsp/br17.atsp"
    parsed_data = parser.parse_file(file_path)
    print("✓ Step 1: Parsing successful")

    # Step 2: Transform
    transformer = DataTransformer(logger=logger)
    transformed_data = transformer.transform_problem(parsed_data)
    print("✓ Step 2: Transformation successful")

    # Verify edge_weight_matrix exists
    if "edge_weight_matrix" not in transformed_data:
      print("✗ ERROR: edge_weight_matrix not in transformed data")
      return 1

    matrix = transformed_data["edge_weight_matrix"]
    print(f"  - Matrix dimensions: {len(matrix)}x{len(matrix[0])}")

    # Step 3: Prepare edge weight data
    edge_weight_data = {
      "dimension": transformed_data["problem_data"].get("dimension"),
      "matrix_format": transformed_data["problem_data"].get("edge_weight_format"),
      "is_symmetric": transformed_data["problem_data"].get("edge_weight_type") == "EXPLICIT",
      "matrix_json": json.dumps(matrix),
    }
    print("✓ Step 3: Edge weight data prepared")
    print(f"  - Format: {edge_weight_data['matrix_format']}")
    print(f"  - Symmetric: {edge_weight_data['is_symmetric']}")
    print(f"  - JSON size: {len(edge_weight_data['matrix_json'])} bytes")

    # Step 4: Database insertion
    db_manager = DatabaseManager(db_path=db_path, logger=logger)
    problem_id = db_manager.insert_problem_atomic(
      problem_data=transformed_data["problem_data"],
      nodes=transformed_data["nodes"],
      file_path=file_path,
      checksum="test_checksum_123",
      edge_weight_data=edge_weight_data,
    )
    print(f"✓ Step 4: Database insertion successful (problem_id={problem_id})")

    # Step 5: Verify database contents
    conn = duckdb.connect(db_path)

    # Check problems table
    result = conn.execute(
      "SELECT name, type, dimension, edge_weight_type, edge_weight_format FROM problems WHERE id = ?", [problem_id]
    ).fetchone()
    print("\n✓ Step 5: Database verification")
    print("  Problems table:")
    print(f"    - Name: {result[0]}")
    print(f"    - Type: {result[1]}")
    print(f"    - Dimension: {result[2]}")
    print(f"    - Edge weight type: {result[3]}")
    print(f"    - Edge weight format: {result[4]}")

    # Check edge_weight_matrices table
    result = conn.execute(
      "SELECT dimension, matrix_format, is_symmetric, length(matrix_json) FROM edge_weight_matrices WHERE problem_id = ?",
      [problem_id],
    ).fetchone()

    if result:
      print("  Edge weight matrices table:")
      print(f"    - Dimension: {result[0]}")
      print(f"    - Format: {result[1]}")
      print(f"    - Symmetric: {result[2]}")
      print(f"    - JSON size: {result[3]} bytes")

      # Retrieve and verify matrix
      matrix_json = conn.execute(
        "SELECT matrix_json FROM edge_weight_matrices WHERE problem_id = ?", [problem_id]
      ).fetchone()[0]

      retrieved_matrix = json.loads(matrix_json)
      print("\n✓ Retrieved matrix from database:")
      print(f"    - Dimensions: {len(retrieved_matrix)}x{len(retrieved_matrix[0])}")
      print(f"    - First row: {retrieved_matrix[0][:5]}...")
      print(f"    - Matrix[0,1]: {retrieved_matrix[0][1]}")
      print(f"    - Matrix[1,0]: {retrieved_matrix[1][0]}")

      # Verify it matches original
      assert retrieved_matrix == matrix, "Retrieved matrix doesn't match original!"
      print("\n✓ Matrix verification: Retrieved matrix matches original")

    else:
      print("✗ ERROR: No edge weight data in database")
      return 1

    conn.close()

    print(f"\n{'=' * 70}")
    print("✓ ALL TESTS PASSED - Full pipeline working!")
    print(f"{'=' * 70}\n")

    return 0

  except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback

    traceback.print_exc()
    return 1


if __name__ == "__main__":
  sys.exit(main())
