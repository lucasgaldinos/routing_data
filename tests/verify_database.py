#!/usr/bin/env python3
"""
Script to verify edge weight matrices in database.
"""

import json

import duckdb

db_path = "datasets/db/routing.duckdb"

print(f"\n{'=' * 70}")
print("Verifying edge weight matrices in database")
print(f"{'=' * 70}\n")

conn = duckdb.connect(db_path)

# Check total ATSP problems
result = conn.execute("""
    SELECT COUNT(*) FROM problems WHERE type = 'ATSP'
""").fetchone()
total_atsp = result[0]
print(f"Total ATSP problems: {total_atsp}")

# Check how many have edge weights
result = conn.execute("""
    SELECT COUNT(*) FROM edge_weight_matrices
""").fetchone()
total_with_weights = result[0]
print(f"Total with edge weights: {total_with_weights}\n")

# Get details for each
results = conn.execute("""
    SELECT p.name, p.dimension, p.edge_weight_format, 
           e.dimension as matrix_dim, e.matrix_format,
           length(e.matrix_json) as json_size
    FROM problems p
    JOIN edge_weight_matrices e ON p.id = e.problem_id
    WHERE p.type = 'ATSP'
    ORDER BY p.dimension
""").fetchall()

print(f"Edge weight matrices found: {len(results)}\n")
print(f"{'Name':<15} {'Dim':<6} {'Format':<15} {'Matrix':<8} {'JSON Size':>12}")
print(f"{'-' * 70}")
for row in results:
  name, dim, format, matrix_dim, matrix_format, json_size = row
  print(f"{name:<15} {dim:<6} {format:<15} {matrix_dim}x{matrix_dim:<5} {json_size:>12,} bytes")

# Verify one matrix content
print(f"\n{'=' * 70}")
print("Sample verification: br17.atsp")
print(f"{'=' * 70}\n")

result = conn.execute("""
    SELECT e.matrix_json
    FROM problems p
    JOIN edge_weight_matrices e ON p.id = e.problem_id
    WHERE p.name = 'br17'
""").fetchone()

if result:
  matrix = json.loads(result[0])
  print(f"Matrix dimensions: {len(matrix)}x{len(matrix[0])}")
  print(f"First row: {matrix[0]}")
  print(f"Matrix[0,1]: {matrix[0][1]}")
  print(f"Matrix[1,0]: {matrix[1][0]}")
  print("\n✓ Edge weights successfully stored and retrieved!")
else:
  print("✗ No matrix found for br17")

conn.close()

print(f"\n{'=' * 70}")
print("✓ VERIFICATION COMPLETE")
print(f"{'=' * 70}\n")
