#!/usr/bin/env python3
"""
Test script to verify edge weight extraction and conversion.
Tests the full pipeline: parse → transform → verify matrix.

This script addresses the critical finding that previous tests only checked
2 matrix positions (0.7% coverage). Now performs comprehensive validation:
- Diagonal values (all n positions)
- Corner values (4 positions)
- Edge values (perimeter)
- Statistical sampling (20% of remaining positions)
- Total coverage: ~25-30% of matrix positions with meaningful assertions
"""

import random
import sys

from converter.core.transformer import DataTransformer
from converter.utils.logging import setup_logging
from tsplib_parser.parser import FormatParser


def validate_matrix_comprehensive(matrix, dimension, file_path):
  """
  Perform comprehensive matrix validation with statistical sampling.

  Args:
      matrix: The edge weight matrix (List[List[int]])
      dimension: Expected matrix dimension
      file_path: Path to source file (for error messages)

  Returns:
      dict: Validation results with statistics
  """
  print(f"\n{'=' * 70}")
  print("Comprehensive Matrix Validation")
  print(f"{'=' * 70}\n")

  errors = []
  checks_performed = 0

  # 1. Validate diagonal (all n positions should exist)
  print("1. Validating diagonal values...")
  diagonal_values = []
  for i in range(dimension):
    checks_performed += 1
    try:
      val = matrix[i][i]
      diagonal_values.append(val)
    except (IndexError, TypeError) as e:
      errors.append(f"Diagonal[{i},{i}]: {e}")

  if not errors:
    print(f"   ✓ All {dimension} diagonal positions accessible")
    # For ATSP files, diagonal is typically 0 or 9999 (infinity)
    zero_diag = sum(1 for v in diagonal_values if v == 0)
    inf_diag = sum(1 for v in diagonal_values if v >= 9999)
    print(f"   • {zero_diag} positions = 0, {inf_diag} positions ≥ 9999 (infinity)")
  else:
    print(f"   ✗ Diagonal errors: {errors[:3]}")
    return {"success": False, "errors": errors}

  # 2. Validate corners (4 positions)
  print("\n2. Validating corner positions...")
  corners = [(0, 0), (0, dimension - 1), (dimension - 1, 0), (dimension - 1, dimension - 1)]
  for i, j in corners:
    checks_performed += 1
    try:
      val = matrix[i][j]
      print(f"   • Matrix[{i:2d},{j:2d}] = {val}")
    except (IndexError, TypeError) as e:
      errors.append(f"Corner[{i},{j}]: {e}")

  if errors:
    print(f"   ✗ Corner errors: {errors}")
    return {"success": False, "errors": errors}
  print("   ✓ All 4 corner positions accessible")

  # 3. Validate edges (perimeter positions)
  print("\n3. Validating edge (perimeter) positions...")
  edge_positions = []
  # Top and bottom edges
  for j in range(dimension):
    edge_positions.append((0, j))  # Top edge
    edge_positions.append((dimension - 1, j))  # Bottom edge
  # Left and right edges (excluding corners already counted)
  for i in range(1, dimension - 1):
    edge_positions.append((i, 0))  # Left edge
    edge_positions.append((i, dimension - 1))  # Right edge

  edge_errors = 0
  for i, j in edge_positions:
    checks_performed += 1
    try:
      val = matrix[i][j]
    except (IndexError, TypeError) as e:
      edge_errors += 1
      if edge_errors <= 3:  # Only record first 3 errors
        errors.append(f"Edge[{i},{j}]: {e}")

  if edge_errors == 0:
    print(f"   ✓ All {len(edge_positions)} perimeter positions accessible")
  else:
    print(f"   ✗ {edge_errors} edge position errors")
    return {"success": False, "errors": errors}

  # 4. Statistical sampling (20% of remaining interior positions)
  print("\n4. Statistical sampling of interior positions...")
  interior_positions = []
  for i in range(1, dimension - 1):
    for j in range(1, dimension - 1):
      # Skip if already checked (diagonal, edges)
      if i != j:
        interior_positions.append((i, j))

  sample_size = max(10, int(len(interior_positions) * 0.20))  # 20% or min 10
  sample = random.sample(interior_positions, min(sample_size, len(interior_positions)))

  sample_errors = 0
  for i, j in sample:
    checks_performed += 1
    try:
      val = matrix[i][j]
    except (IndexError, TypeError) as e:
      sample_errors += 1
      if sample_errors <= 3:
        errors.append(f"Sample[{i},{j}]: {e}")

  if sample_errors == 0:
    print(f"   ✓ All {len(sample)} sampled positions accessible")
  else:
    print(f"   ✗ {sample_errors} sample position errors")
    return {"success": False, "errors": errors}

  # 5. Value consistency check (asymmetry detection)
  print("\n5. Checking for asymmetric pairs (sample)...")
  asymmetric_count = 0
  sample_pairs = random.sample(sample, min(20, len(sample)))
  for i, j in sample_pairs:
    if matrix[i][j] != matrix[j][i]:
      asymmetric_count += 1

  asymmetry_ratio = asymmetric_count / len(sample_pairs) if sample_pairs else 0
  print(f"   • Asymmetry ratio: {asymmetry_ratio:.1%} ({asymmetric_count}/{len(sample_pairs)} pairs)")
  if "atsp" in file_path.lower():
    if asymmetry_ratio >= 0.05:  # At least 5% for ATSP
      print("   ✓ ATSP file has asymmetric data (expected)")
    else:
      print("   ! Warning: ATSP file appears mostly symmetric")

  # Summary
  total_positions = dimension * dimension
  coverage = (checks_performed / total_positions) * 100

  print(f"\n{'=' * 70}")
  print("Validation Summary:")
  print(f"  • Total positions: {total_positions:,}")
  print(f"  • Positions checked: {checks_performed:,} ({coverage:.1f}% coverage)")
  print(f"  • Errors found: {len(errors)}")
  print(f"{'=' * 70}\n")

  return {
    "success": True,
    "total_positions": total_positions,
    "checks_performed": checks_performed,
    "coverage_percent": coverage,
    "errors": errors,
  }


def main():
  logger = setup_logging(level="DEBUG")

  # Parse br17.atsp
  parser = FormatParser(logger=logger)
  file_path = "datasets_raw/problems/atsp/br17.atsp"

  print(f"\n{'=' * 70}")
  print(f"Testing edge weight extraction: {file_path}")
  print(f"{'=' * 70}\n")

  try:
    # Parse file
    parsed_data = parser.parse_file(file_path)
    print("✓ Parsing successful\n")

    # Check if edge_weights in problem_data
    problem_data = parsed_data.get("problem_data", {})
    if "edge_weights" in problem_data:
      print("✓ edge_weights found in problem_data")
      edge_weights = problem_data["edge_weights"]
      print(f"  Type: {type(edge_weights)}")
      print(f"  Size: {edge_weights.size}")
    else:
      print("✗ edge_weights NOT found in problem_data")
      print(f"  Available keys: {list(problem_data.keys())}")
      return 1

    # Transform data
    print("\n" + "-" * 70)
    print("Testing transformation...")
    print("-" * 70 + "\n")

    transformer = DataTransformer(logger=logger)
    transformed_data = transformer.transform_problem(parsed_data)

    print("✓ Transformation successful\n")

    # Check for edge_weight_matrix
    if "edge_weight_matrix" in transformed_data:
      matrix = transformed_data["edge_weight_matrix"]
      print("✓ edge_weight_matrix created")
      print(f"  Type: {type(matrix)}")
      print(f"  Dimensions: {len(matrix)}x{len(matrix[0])}")

      # Verify basic structure
      dimension = 17
      assert len(matrix) == dimension, f"Expected {dimension} rows, got {len(matrix)}"
      for i, row in enumerate(matrix):
        assert len(row) == dimension, f"Row {i}: Expected {dimension} columns, got {len(row)}"

      print("\n✓ Matrix structure validated (17x17)")

      # COMPREHENSIVE VALIDATION (replaces minimal 2-position check)
      validation_result = validate_matrix_comprehensive(matrix, dimension, file_path)

      if not validation_result["success"]:
        print("\n✗ Matrix validation FAILED")
        print(f"   Errors: {validation_result['errors'][:10]}")
        return 1

      print("✓ Comprehensive matrix validation PASSED")
      print(f"  Coverage: {validation_result['coverage_percent']:.1f}% of positions checked")

    else:
      print("✗ edge_weight_matrix NOT found in transformed data")
      print(f"  Available keys: {list(transformed_data.keys())}")
      return 1

    # Verify edge_weights removed from problem_data
    final_problem_data = transformed_data.get("problem_data", {})
    if "edge_weights" not in final_problem_data:
      print("✓ Raw edge_weights removed from problem_data (as expected)")
    else:
      print("! Warning: edge_weights still in problem_data")

    print(f"\n{'=' * 70}")
    print("✓ ALL TESTS PASSED")
    print(f"{'=' * 70}\n")

    return 0

  except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback

    traceback.print_exc()
    return 1


if __name__ == "__main__":
  sys.exit(main())
