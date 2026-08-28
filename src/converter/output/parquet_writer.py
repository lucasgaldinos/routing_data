"""Parquet output writer for TSPLIB converter.

Exports routing problem data to Apache Parquet format for efficient
columnar storage and analysis with ML frameworks.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

import duckdb


class ParquetWriter:
    """
    Parquet output writer for TSPLIB converter.

    Features:
    - Export tables to Parquet columnar format
    - Efficient for data science and ML workflows
    - Compression support (snappy, gzip, zstd)
    - Single-file or multi-file export modes

    Example:
        >>> writer = ParquetWriter(output_dir="datasets/parquet")
        >>> writer.export_from_database("datasets/db/routing.duckdb")
        >>> # Creates: problems.parquet, nodes.parquet, edge_weight_matrices.parquet
    """

    def __init__(
        self,
        output_dir: str = "./datasets/parquet",
        compression: str = "snappy",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize Parquet writer.

        Args:
            output_dir: Base directory for Parquet output
            compression: Compression codec ('snappy', 'gzip', 'zstd', 'uncompressed')
            logger: Optional logger instance
        """
        self.output_dir = Path(output_dir)
        self.compression = compression
        self.logger = logger or logging.getLogger(__name__)

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Parquet writer initialized: {self.output_dir}")

    def export_from_database(
        self,
        db_path: str,
        tables: Optional[List[str]] = None,
        single_file: bool = False
    ) -> Dict[str, str]:
        """
        Export tables from DuckDB database to Parquet files.

        Args:
            db_path: Path to DuckDB database file
            tables: List of table names to export (None = all tables)
            single_file: If True, export all tables to single multi-table Parquet

        Returns:
            Dict mapping table names to output file paths

        Raises:
            FileNotFoundError: If database file doesn't exist
            ValueError: If specified table doesn't exist

        Example:
            >>> writer = ParquetWriter()
            >>> files = writer.export_from_database(
            ...     "datasets/db/routing.duckdb",
            ...     tables=["problems", "nodes"]
            ... )
            >>> print(files)
            {'problems': 'datasets/parquet/problems.parquet', ...}
        """
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        conn = duckdb.connect(str(db_path), read_only=True)

        try:
            # Get available tables
            available_tables = [
                row[0] for row in conn.execute("SHOW TABLES").fetchall()
            ]

            # Determine tables to export
            if tables is None:
                export_tables = available_tables
            else:
                # Validate requested tables
                invalid = set(tables) - set(available_tables)
                if invalid:
                    raise ValueError(f"Tables not found: {invalid}")
                export_tables = tables

            self.logger.info(f"Exporting {len(export_tables)} tables to Parquet")

            if single_file:
                return self._export_single_file(conn, export_tables)
            else:
                return self._export_multi_file(conn, export_tables)

        finally:
            conn.close()

    def _export_multi_file(
        self,
        conn: duckdb.DuckDBPyConnection,
        tables: List[str]
    ) -> Dict[str, str]:
        """Export each table to separate Parquet file."""
        output_files = {}

        for table in tables:
            output_path = self.output_dir / f"{table}.parquet"

            # DuckDB native Parquet export
            query = f"""
                COPY {table}
                TO '{output_path}'
                (FORMAT PARQUET, COMPRESSION '{self.compression}')
            """

            self.logger.debug(f"Exporting table '{table}' to {output_path}")
            conn.execute(query)

            # Get file size for logging
            size_mb = output_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"✓ Exported {table}: {size_mb:.2f} MB ({output_path.name})")

            output_files[table] = str(output_path)

        return output_files

    def _export_single_file(
        self,
        conn: duckdb.DuckDBPyConnection,
        tables: List[str]
    ) -> Dict[str, str]:
        """
        Export all tables to single Parquet file with table metadata.

        Note: Uses nested structure with table name as column.
        Useful for archival but less convenient for direct analysis.
        """
        output_path = self.output_dir / "routing_data.parquet"

        # Create a unified structure
        # This is a simplified approach - for production you might want
        # to use a proper multi-table format like Iceberg

        self.logger.warning(
            "Single-file export creates separate files with '_all' suffix. "
            "For true single-file storage, consider using database file directly."
        )

        # For now, just export to separate files with common prefix
        output_files = {}
        for table in tables:
            table_output = self.output_dir / f"routing_data_{table}.parquet"

            query = f"""
                COPY {table}
                TO '{table_output}'
                (FORMAT PARQUET, COMPRESSION '{self.compression}')
            """

            conn.execute(query)
            output_files[table] = str(table_output)

            size_mb = table_output.stat().st_size / (1024 * 1024)
            self.logger.info(f"✓ Exported {table}: {size_mb:.2f} MB")

        return output_files

    def export_table(
        self,
        db_path: str,
        table_name: str,
        output_filename: Optional[str] = None
    ) -> str:
        """
        Export single table to Parquet file.

        Args:
            db_path: Path to DuckDB database file
            table_name: Name of table to export
            output_filename: Custom output filename (default: {table_name}.parquet)

        Returns:
            Path to created Parquet file

        Example:
            >>> writer = ParquetWriter()
            >>> path = writer.export_table(
            ...     "datasets/db/routing.duckdb",
            ...     "problems",
            ...     output_filename="tsp_problems.parquet"
            ... )
        """
        if output_filename is None:
            output_filename = f"{table_name}.parquet"

        files = self.export_from_database(
            db_path,
            tables=[table_name]
        )

        # Rename if custom filename provided
        if output_filename != f"{table_name}.parquet":
            old_path = Path(files[table_name])
            new_path = self.output_dir / output_filename
            old_path.rename(new_path)
            return str(new_path)

        return files[table_name]

    def get_parquet_info(self, parquet_file: str) -> Dict[str, Any]:
        """
        Get metadata information about a Parquet file.

        Args:
            parquet_file: Path to Parquet file

        Returns:
            Dict with file metadata (row_count, columns, size_mb, etc.)

        Example:
            >>> writer = ParquetWriter()
            >>> info = writer.get_parquet_info("datasets/parquet/problems.parquet")
            >>> print(f"Rows: {info['row_count']}, Columns: {info['column_count']}")
        """
        parquet_path = Path(parquet_file)

        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        conn = duckdb.connect(":memory:")

        try:
            # Get schema
            schema = conn.execute(
                f"DESCRIBE SELECT * FROM '{parquet_path}'"
            ).fetchall()

            # Get row count
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM '{parquet_path}'"
            ).fetchone()[0]

            # Get file size
            size_mb = parquet_path.stat().st_size / (1024 * 1024)

            return {
                "file_path": str(parquet_path),
                "row_count": row_count,
                "column_count": len(schema),
                "columns": [{"name": col[0], "type": col[1]} for col in schema],
                "size_mb": round(size_mb, 2),
                "compression": self.compression
            }

        finally:
            conn.close()


def export_database_to_parquet(
    db_path: str,
    output_dir: str = "./datasets/parquet",
    compression: str = "snappy",
    logger: Optional[logging.Logger] = None
) -> Dict[str, str]:
    """
    Convenience function to export entire database to Parquet files.

    Args:
        db_path: Path to DuckDB database file
        output_dir: Output directory for Parquet files
        compression: Compression codec to use
        logger: Optional logger instance

    Returns:
        Dict mapping table names to output file paths

    Example:
        >>> from converter.output.parquet_writer import export_database_to_parquet
        >>> files = export_database_to_parquet("datasets/db/routing.duckdb")
        >>> print(f"Exported {len(files)} tables")
    """
    writer = ParquetWriter(output_dir=output_dir, compression=compression, logger=logger)
    return writer.export_from_database(db_path)
