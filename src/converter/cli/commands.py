"""Command-line interface for TSPLIB95 ETL Converter."""

import click
from pathlib import Path
import logging
import sys
import time
from typing import Any, Literal, Optional
import json

from ..utils.logging import setup_logging
from ..utils.exceptions import ConverterError
from ..utils.parallel import ParallelProcessor
from ..utils.update import UpdateManager
from ..utils.worker_functions import process_file_for_parallel
from ..database.operations import DatabaseManager
from ..core.scanner import FileScanner
from tsplib_parser.parser import FormatParser
from ..core.transformer import DataTransformer
from ..output.json_writer import JSONWriter
from ..output.parquet_writer import ParquetWriter


@click.group()
@click.version_option(version="0.1.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose) -> None:
    """TSPLIB95 ETL Converter - Convert TSPLIB/VRP instances to JSON and DuckDB."""
    ctx.ensure_object(dict)
    log_level: Literal['DEBUG'] | Literal['INFO'] = 'DEBUG' if verbose else 'INFO'
    ctx.obj['logger'] = setup_logging(log_level)


@cli.command()
@click.option('--input', '-i', type=click.Path(exists=True),
              required=True,
              help='Input directory containing TSPLIB files')
@click.option('--output', '-o', type=click.Path(),
              default='./datasets',
              help='Output directory; the database is written to <output>/db/routing.duckdb '
                '(config.yaml database_path is NOT consulted; to target the canonical '
                'db/routing.duckdb, pass -o <submodule-root>)')
@click.option('--parallel/--no-parallel', default=True,
              help='Enable parallel processing (default: enabled)')
@click.option('--workers', default=4, type=int,
              help='Number of parallel workers (default: 4)')
@click.option('--batch-size', default=100, type=int,
              help='Batch size for processing (default: 100)')
@click.option('--types', multiple=True,
              help='Problem types to process (e.g., --types TSP --types VRP)')
@click.option('--force/--no-force', default=False,
              help='Force reprocessing of existing files')
@click.pass_context
def process(ctx, input, output, parallel, workers, batch_size, types, force):
    """
    Process TSPLIB files and generate database output.

    Examples:
        converter process -i datasets_raw/problems -o datasets/
        converter process --input datasets_raw/problems --parallel --workers 8
        converter process --types TSP --types VRP --force
    """
    logger = ctx.obj['logger']

    try:
        logger.info("Starting TSPLIB file processing")
        logger.info(f"Input directory: {input}")
        logger.info(f"Output directory: {output}")
        logger.info(f"Parallel processing: {parallel} (workers: {workers})")

        # Initialize components
        db_path = Path(output) / 'db' / 'routing.duckdb'
        db_manager = DatabaseManager(str(db_path), logger)
        update_manager = UpdateManager(db_manager, logger)
        scanner = FileScanner(batch_size=batch_size, logger=logger)
        parser = FormatParser(logger)
        transformer = DataTransformer(logger)
        json_writer = JSONWriter(str(Path(output) / 'json'), logger=logger)

        # Get file patterns
        if types:
            patterns = [f"*.{t.lower()}" for t in types]
        else:
            patterns = ['*.tsp', '*.vrp', '*.atsp', '*.hcp', '*.sop']

        # Scan for files from multiple sources
        logger.info(f"Scanning for files with patterns: {patterns}")
        file_list = []

        # Primary input directory
        files_from_input = scanner.scan_files(directory=input, patterns)
        file_list.extend(files_from_input)
        logger.info(f"Found {len(files_from_input)} files in {input}")

        # Additional CVRPLIB directory (if exists)
        # Calculate path: datasets_raw/zips/all_problems -> datasets_raw -> datasets_raw/cvrplib
        input_path = Path(input)
        raw_base: Path = input_path.parent.parent if 'all_problems' in str(input_path) else input_path.parent
        cvrplib_path: Path = raw_base / 'cvrplib'
        if cvrplib_path.exists():
            files_from_cvrplib = scanner.scan_files(str(cvrplib_path), patterns)
            file_list.extend(files_from_cvrplib)
            logger.info(f"Found {len(files_from_cvrplib)} files in {cvrplib_path}")

        # Filter out MDVRP files (exclude datasets_raw/umalaga/mdvrp/)
        file_list = [f for f in file_list if '/mdvrp/' not in f and '/mdvrp-converted/' not in f]

        logger.info(f"Total: {len(file_list)} files to process (MDVRP excluded)")

        if not file_list:
            logger.warning("No files found to process")
            return

        # Check for updates if not forcing
        if not force:
            logger.info("Checking for changed files...")
            update_stats = update_manager.perform_incremental_update(file_list, force=False)
            files_to_process = update_stats['processed']
            logger.info(f"Files to process: {len(files_to_process)} "
                       f"(new: {update_stats['new_files']}, "
                       f"modified: {update_stats['modified_files']}, "
                       f"skipped: {len(update_stats['skipped'])})")
        else:
            files_to_process = file_list
            logger.info("Force mode: processing all files")

        if not files_to_process:
            logger.info("No files need processing")
            return

        # Process files
        start_time = time.time()

        # Use ParallelProcessor for both parallel and sequential processing
        # Sequential mode: workers=1, Parallel mode: workers=N
        effective_workers = workers if (parallel and len(files_to_process) > 1) else 1

        processor = ParallelProcessor(
            max_workers=effective_workers,
            batch_size=batch_size,
            logger=logger
        )

        # Use ProcessPoolExecutor for CPU-bound work (parsing/transformation)
        # This bypasses Python's GIL for true parallelism
        use_processes = effective_workers > 1  # Only use processes for parallel mode

        # Call worker function with output_dir parameter
        from functools import partial
        worker_func = partial(process_file_for_parallel, output_dir=str(output))

        results = processor.process_files_parallel(
            files_to_process,
            worker_func,
            use_processes=use_processes
        )

        # Post-process results: Write to database and JSON
        logger.info("Writing results to database and JSON files...")

        # Filter successful results for batch processing
        successful_results = [r for r in results.get('results', []) if r.get('success')]
        failed_results = [r for r in results.get('results', []) if not r.get('success')]

        # BATCH DATABASE INSERT (single transaction for all files)
        # This eliminates connection/transaction overhead: 113 files × 1.5s → ~10s total
        batch_result = db_manager.insert_problems_batch(successful_results)

        # PARALLEL JSON WRITES (I/O-bound, can use ThreadPoolExecutor)
        # Overlaps disk I/O for multiple files simultaneously
        from concurrent.futures import ThreadPoolExecutor, as_completed
        json_write_successful = 0
        json_write_failed = 0

        with ThreadPoolExecutor(max_workers=min(4, effective_workers)) as json_executor:
            # Submit all JSON write tasks
            json_futures = {
                json_executor.submit(json_writer.write_problem, result['transformed_data']): result
                for result in successful_results
            }

            # Collect results as they complete
            for future in as_completed(json_futures):
                result = json_futures[future]
                try:
                    future.result()  # Raises exception if write failed
                    json_write_successful += 1
                except Exception as e:
                    json_write_failed += 1
                    logger.error(f"Failed to write JSON for {result['file_path']}: {e}")

        # Calculate total failures (processing + database + JSON)
        total_failed = len(failed_results) + batch_result['total_failed'] + json_write_failed

        logger.info(
            f"Database writes: {batch_result['total_inserted']} successful, "
            f"{batch_result['total_failed']} failed"
        )
        logger.info(
            f"JSON writes: {json_write_successful} successful, {json_write_failed} failed"
        )

        # Log results with mode indicator
        mode = "Parallel" if effective_workers > 1 else "Sequential"
        executor_type = "(ProcessPoolExecutor)" if use_processes else "(ThreadPoolExecutor)"
        logger.info(f"{mode} processing completed {executor_type}:")
        logger.info(f"  Successful: {results['successful']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"  Time: {results['processing_time']:.2f}s")
        if effective_workers > 1:
            logger.info(f"  Throughput: {results['throughput']:.2f} files/sec")

        # Show final statistics
        stats: dict[str, Any] = db_manager.get_problem_stats()
        logger.info(f"Database statistics:")
        logger.info(f"  Total problems: {stats['total_problems']}")
        for type_stat in stats['by_type']:
            logger.info(f"  {type_stat['type']}: {type_stat['count']} problems "
                        f"(avg dim: {type_stat['avg_dimension']}, "
                        f"max dim: {type_stat['max_dimension']})")

        click.echo(message=f"\n✓ Processing complete. Database: {db_path}")

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        click.echo(message=f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--database', '-d', type=click.Path(exists=True),
              default='./db/routing.duckdb',
              help='Database file to validate (default: ./db/routing.duckdb)')
@click.pass_context
def validate(ctx, database):
    """
    Validate database integrity and data quality.

    Performs comprehensive validation:
    - Database schema and data integrity
    - Data quality checks
    - Constraint verification
    """
    logger = ctx.obj['logger']

    try:
        logger.info(f"Validating database: {database}")

        if not Path(database).exists():
            click.echo(f"✗ Database not found: {database}", err=True)
            sys.exit(1)

        db_manager = DatabaseManager(database, logger)
        stats = db_manager.get_problem_stats()

        click.echo(f"\n✓ Database validation successful")
        click.echo(f"  Total problems: {stats['total_problems']}")

        for type_stat in stats['by_type']:
            click.echo(f"  {type_stat['type']}: {type_stat['count']} problems")

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        click.echo(f"✗ Validation error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--database', '-d', required=True, type=click.Path(exists=True),
              help='Database file to analyze')
@click.option('--type', '-t', type=click.Choice(['TSP', 'VRP', 'ATSP', 'HCP', 'SOP', 'TOUR']),
              help='Filter by problem type')
@click.option('--format', type=click.Choice(['table', 'json']), default='table',
              help='Output format (default: table)')
@click.option('--limit', type=int, default=20,
              help='Maximum number of problems to show (default: 20)')
@click.pass_context
def analyze(ctx, database, type, format, limit):
    """
    Analyze processed problems and generate statistics.

    Generates comprehensive analysis:
    - Problem type distribution and size statistics
    - Problem details and characteristics
    - Data quality assessment
    """
    logger = ctx.obj['logger']

    try:
        logger.info(f"Analyzing database: {database}")

        db_manager = DatabaseManager(database, logger)

        # Get statistics
        stats = db_manager.get_problem_stats()

        if format == 'json':
            # JSON output
            output = {
                'statistics': stats,
                'problems': db_manager.query_problems(
                    problem_type=type,
                    limit=limit
                )
            }
            click.echo(json.dumps(output, indent=2))

        else:
            # Table output
            click.echo("\n=== Database Statistics ===")
            click.echo(f"Total problems: {stats['total_problems']}")
            click.echo("\nBy type:")
            for type_stat in stats['by_type']:
                click.echo(f"  {type_stat['type']:6} : {type_stat['count']:4} problems "
                          f"(avg: {type_stat['avg_dimension']:6.1f}, "
                          f"max: {type_stat['max_dimension']:5})")

            # Show sample problems
            problems = db_manager.query_problems(
                problem_type=type,
                limit=limit
            )

            if problems:
                click.echo(f"\n=== Sample Problems (limit: {limit}) ===")
                click.echo(f"{'Name':<20} {'Type':<6} {'Dim':>5} {'Weight Type':<15}")
                click.echo("-" * 60)
                for p in problems:
                    click.echo(f"{p['name']:<20} {p['type']:<6} {p['dimension']:>5} "
                              f"{p.get('edge_weight_type', 'N/A'):<15}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        click.echo(f"✗ Analysis error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(), default='config.yaml',
              help='Output path for configuration file')
def init(output):
    """
    Initialize configuration file with default settings.

    Creates a template configuration file with documented options.
    """
    config_template = """# TSPLIB95 ETL Converter Configuration

# Input settings
input_path: "./datasets_raw/problems"
file_patterns:
  - "*.tsp"
  - "*.vrp"
  - "*.atsp"
  - "*.hcp"
  - "*.sop"
  - "*.tour"

# Output settings
json_output_path: "./datasets/json"

# NOTE (2026-08-28, Task 2.6): `database_path` is the default recorded by
# `converter init` and read via `converter.config.load_config()`. The canonical
# DB for this submodule is `db/routing.duckdb` (submodule root). This value is
# NOT read by `converter process` — that command derives its DB path from the
# `-o/--output` option as `<output>/db/routing.duckdb` (default `./datasets`,
# src/converter/cli/commands.py `process`). To target the canonical DB, run:
#
#   uv run converter process -i datasets/problems -o <submodule-root>
#
# Relative paths resolve against the process CWD (load_config() does not
# resolve against this file's location).
database_path: "./db/routing.duckdb"

# Processing settings
batch_size: 100
max_workers: 4
memory_limit_mb: 2048

# Logging
log_level: "INFO"
log_file: "./logs/converter.log"
"""

    output_path = Path(output)

    if output_path.exists():
        click.confirm(f"File {output} already exists. Overwrite?", abort=True)

    output_path.write_text(config_template)
    click.echo(f"✓ Configuration file created: {output}")


@cli.command(name='export-parquet')
@click.option('--database', '-d', type=click.Path(exists=True),
              default='./db/routing.duckdb',
              help='Database file to export (default: ./db/routing.duckdb)')
@click.option('--output', '-o', type=click.Path(),
              default='./datasets/parquet',
              help='Output directory for Parquet files (default: ./datasets/parquet)')
@click.option('--tables', '-t', multiple=True,
              help='Specific tables to export (default: all tables). Can be specified multiple times.')
@click.option('--compression', '-c',
              type=click.Choice(['snappy', 'gzip', 'zstd', 'uncompressed']),
              default='snappy',
              help='Compression codec (default: snappy)')
@click.option('--info/--no-info', default=True,
              help='Show Parquet file information after export')
@click.pass_context
def export_parquet(ctx, database, output, tables, compression, info):
    """
    Export database tables to Apache Parquet format.

    Parquet is a columnar storage format optimized for analytics and ML workflows.
    Supports efficient compression and is compatible with pandas, polars, DuckDB, etc.

    Examples:
        # Export all tables
        converter export-parquet -d db/routing.duckdb

        # Export specific tables
        converter export-parquet -t problems -t nodes -o ./exports/

        # Use different compression
        converter export-parquet -c zstd -o ./parquet_compressed/

        # No info display
        converter export-parquet --no-info
    """
    logger = ctx.obj['logger']

    try:
        logger.info(f"Exporting database to Parquet format")
        logger.info(f"Database: {database}")
        logger.info(f"Output directory: {output}")
        logger.info(f"Compression: {compression}")

        if not Path(database).exists():
            click.echo(f"✗ Database not found: {database}", err=True)
            sys.exit(1)

        # Create Parquet writer
        writer = ParquetWriter(
            output_dir=output,
            compression=compression,
            logger=logger
        )

        # Export tables
        table_list = list(tables) if tables else None
        exported_files = writer.export_from_database(
            db_path=database,
            tables=table_list
        )

        # Display results
        click.echo(f"\n✓ Exported {len(exported_files)} table(s) to Parquet:")

        total_size_mb = 0
        for table_name, file_path in exported_files.items():
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            total_size_mb += file_size_mb
            click.echo(f"  {table_name:25} → {Path(file_path).name:30} ({file_size_mb:6.2f} MB)")

        click.echo(f"\nTotal size: {total_size_mb:.2f} MB")
        click.echo(f"Output directory: {output}")

        # Show detailed info if requested
        if info and exported_files:
            click.echo("\n=== Parquet File Details ===")
            for table_name, file_path in exported_files.items():
                try:
                    file_info = writer.get_parquet_info(file_path)
                    click.echo(f"\n{table_name}:")
                    click.echo(f"  Rows: {file_info['row_count']:,}")
                    click.echo(f"  Columns: {file_info['column_count']}")
                    click.echo(f"  Size: {file_info['size_mb']:.2f} MB")
                    click.echo(f"  Compression: {file_info['compression']}")
                except Exception as e:
                    logger.warning(f"Could not get info for {table_name}: {e}")

    except Exception as e:
        logger.error(f"Parquet export failed: {e}", exc_info=True)
        click.echo(message=f"✗ Export error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--database', '-d', type=click.Path(exists=True),
              default='./db/routing.duckdb',
              help='Database file to inspect (default: ./db/routing.duckdb)')
@click.option('--table', type=str, default=None,
              help='Show details for a specific table only')
@click.option('--detail/--no-detail', default=False,
              help='Show schema and sample data for all tables (default: off)')
@click.pass_context
def inspect(ctx, database, table, detail) -> None:
    """
    Inspect DuckDB database: list tables, row counts, and schemas.

    Enumerates tables generically via information_schema (no hardcoded table
    names). With --table, shows that table's schema and up to 5 sample rows.
    With --detail, shows schema for every table.

    Examples:
        converter inspect
        converter inspect --table problems
        converter inspect --detail
    """
    import duckdb

    def format_bytes(size_bytes: int) -> str:
        """Format bytes into human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    try:
        db_path = Path(database)
        if not db_path.exists():
            click.echo(f"✗ Database not found: {db_path}", err=True)
            sys.exit(1)

        file_size = db_path.stat().st_size
        click.echo(f"📊 Database: {db_path}")
        click.echo(f"💾 File size: {format_bytes(file_size)}")
        click.echo("=" * 80)

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            tables = [row[0] for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()]

            if not tables:
                click.echo("⚠️  No tables found in database")
                return

            click.echo(f"\n📋 Tables found: {len(tables)}\n")

            for name in tables:
                if table and name != table:
                    continue

                click.echo(f"🔸 Table: {name}")
                click.echo("-" * 80)

                row_count = conn.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
                click.echo(f"   Rows: {row_count:,}")

                schema = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
                click.echo(f"   Columns: {len(schema)}")

                show_schema = detail or (table and name == table)
                if show_schema:
                    click.echo("\n   Schema:")
                    for _col_id, col_name, col_type, not_null, default, pk in schema:
                        null_str = "NOT NULL" if not_null else "NULL"
                        pk_str = " PRIMARY KEY" if pk else ""
                        default_str = f" DEFAULT {default}" if default else ""
                        click.echo(
                            f"      {col_name:<30} {col_type:<15} "
                            f"{null_str}{pk_str}{default_str}"
                        )

                if show_schema and row_count > 0:
                    click.echo("\n   Sample data (first 5 rows):")
                    columns = [row[1] for row in schema]
                    click.echo("  " + " | ".join(str(c) for c in columns))
                    for row in conn.execute(
                        f'SELECT * FROM "{name}" LIMIT 5'
                    ).fetchall():
                        click.echo("  " + " | ".join(str(v) for v in row))

                click.echo()
        finally:
            conn.close()
    except Exception as e:
        logger = ctx.obj['logger']
        logger.error(f"Inspection failed: {e}", exc_info=True)
        click.echo(f"✗ Inspection error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
