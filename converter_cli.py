#!/usr/bin/env python3
"""
TSPLIB95 Converter CLI Entry Point

A proper CLI script that can be called directly without using 'python -m'.
This provides a more user-friendly interface for the converter.
"""

from converter.cli.commands import cli


if __name__ == '__main__':
    cli()