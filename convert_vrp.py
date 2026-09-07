#!/usr/bin/env python3
"""
Quick VRP Converter

A simple, user-friendly script for converting VRP/TSPLIB files.
Usage: ./convert_vrp.py input_directory output_directory
"""

import os
import sys

from converter.api import process_directory


def main():
    if len(sys.argv) != 3:
        print("Usage: ./convert_vrp.py <input_directory> <output_directory>")
        print("Example: ./convert_vrp.py ../vrp_files ./output")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist")
        sys.exit(1)

    print(f"Converting VRP files from {input_dir} to {output_dir}")
    print("This will create both JSON files and a DuckDB database")
    print()

    try:
        process_directory(input_dir, output_dir, workers=4)
        print("\n✅ Conversion completed successfully!")
        print(f"📁 JSON files: {output_dir}/json/")
        print(f"🗄️  Database: {output_dir}/db/routing.duckdb")
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
