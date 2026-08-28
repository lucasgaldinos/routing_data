"""Database operations for TSPLIB data storage and retrieval."""

import duckdb
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from ..utils.exceptions import DatabaseError, NotFoundError


class DatabaseManager:
    """
    Complete database management for TSPLIB converter.

    Features:
    - Thread-safe database operations for parallel processing
    - Bulk insert operations with prepared statements
    - Conflict resolution and incremental updates
    - Query interface for analysis and validation
    - Transaction management and error recovery
    """

    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to DuckDB database file
            logger: Optional logger instance
        """
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger(__name__)
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        """Create database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _initialize_schema(self):
        """Initialize database schema and indexes."""
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                # Create sequences first
                conn.execute("CREATE SEQUENCE IF NOT EXISTS problems_seq START 1")
                conn.execute("CREATE SEQUENCE IF NOT EXISTS nodes_seq START 1")
                conn.execute("CREATE SEQUENCE IF NOT EXISTS file_tracking_seq START 1")
                conn.execute("CREATE SEQUENCE IF NOT EXISTS solutions_seq START 1")

                # Create problems table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS problems (
                        id INTEGER PRIMARY KEY DEFAULT nextval('problems_seq'),
                        name VARCHAR NOT NULL,
                        type VARCHAR NOT NULL,
                        comment VARCHAR,
                        dimension INTEGER NOT NULL,
                        capacity INTEGER,
                        edge_weight_type VARCHAR,
                        edge_weight_format VARCHAR,
                        tsplib_name VARCHAR,
                        fixed_edges INTEGER[][],
                        adjacency INTEGER[][],
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (name, type)
                    )
                """)

                # Migrate schema to add VRP variant fields
                self._migrate_schema(conn)

                # Create nodes table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        id INTEGER PRIMARY KEY DEFAULT nextval('nodes_seq'),
                        problem_id INTEGER NOT NULL,
                        node_id INTEGER NOT NULL,
                        x DOUBLE,
                        y DOUBLE,
                        z DOUBLE,
                        demand INTEGER DEFAULT 0,
                        is_depot BOOLEAN DEFAULT FALSE,
                        display_x DOUBLE,
                        display_y DOUBLE,
                        FOREIGN KEY (problem_id) REFERENCES problems(id)
                    )
                """)

                # NO EDGES TABLE - edges are computed on-demand for coordinate-based problems

                # Create edge_weight_matrices table for EXPLICIT distance problems
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS edge_weight_matrices (
                        problem_id INTEGER PRIMARY KEY,
                        matrix_format VARCHAR NOT NULL,
                        is_symmetric BOOLEAN NOT NULL,
                        matrix INTEGER[][],
                        FOREIGN KEY (problem_id) REFERENCES problems(id)
                    )
                """)

                # Create solutions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS solutions (
                        id INTEGER PRIMARY KEY DEFAULT nextval('solutions_seq'),
                        problem_id INTEGER NOT NULL,
                        solution_name VARCHAR,
                        solution_type VARCHAR,
                        cost DOUBLE,
                        routes INTEGER[][],
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (problem_id) REFERENCES problems(id)
                    )
                """)

                # Create file tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS file_tracking (
                        id INTEGER PRIMARY KEY DEFAULT nextval('file_tracking_seq'),
                        file_path VARCHAR UNIQUE NOT NULL,
                        problem_id INTEGER,
                        checksum VARCHAR,
                        last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_size BIGINT,
                        FOREIGN KEY (problem_id) REFERENCES problems(id)
                    )
                """)

                # Create indexes for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_problems_type_dim
                    ON problems(type, dimension)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_nodes_problem
                    ON nodes(problem_id, node_id)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_solutions_problem
                    ON solutions(problem_id)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_edge_matrices_problem
                    ON edge_weight_matrices(problem_id)
                """)


                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_tracking_path
                    ON file_tracking(file_path)
                """)

                self.logger.info(f"Database schema initialized at {self.db_path}")

        except Exception as e:
            self.logger.error(f"Failed to initialize database schema: {e}")
            raise

    def _migrate_schema(self, conn):
        """Apply schema migrations for VRP variant support with transaction protection."""
        try:
            # Check if VRP fields exist and add them if needed
            result = conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'problems' AND column_name = 'capacity_vol'
            """).fetchall()

            if not result:
                # Wrap ALTER TABLE statements in transaction for atomicity
                conn.execute("BEGIN TRANSACTION")
                try:
                    # Add VRP variant fields (all-or-nothing)
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS capacity_vol INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS capacity_weight INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS max_distance DOUBLE")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS service_time DOUBLE")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS vehicles INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS depots INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS periods INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS has_time_windows BOOLEAN")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS has_pickup_delivery BOOLEAN")
                    conn.execute("COMMIT")
                    self.logger.debug("Added VRP variant fields to problems table")
                except Exception as e:
                    conn.execute("ROLLBACK")
                    # Only raise if it's not a "column already exists" type error
                    if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                        self.logger.error(f"Schema migration failed: {e}")
                        raise DatabaseError(
                            f"Failed to migrate schema: {e}",
                            operation="schema_migration"
                        )

        except Exception as e:
            # If information_schema query fails, try direct column addition with IF NOT EXISTS
            # This is a fallback for databases that don't support information_schema
            if "information_schema" in str(e).lower() or "catalog" in str(e).lower():
                try:
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS capacity_vol INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS capacity_weight INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS max_distance DOUBLE")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS service_time DOUBLE")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS vehicles INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS depots INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS periods INTEGER")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS has_time_windows BOOLEAN")
                    conn.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS has_pickup_delivery BOOLEAN")
                except Exception as fallback_error:
                    # Only ignore "column exists" errors, raise everything else
                    if "already exists" not in str(fallback_error).lower():
                        self.logger.error(f"Schema migration fallback failed: {fallback_error}")
                        raise DatabaseError(
                            f"Failed to migrate schema (fallback): {fallback_error}",
                            operation="schema_migration_fallback"
                        )
            else:
                # Not an information_schema issue, re-raise
                raise

    def insert_problem(self, problem_data: Dict[str, Any]) -> int:
        """
        Insert problem data into database.

        Args:
            problem_data: Dictionary with problem information

        Returns:
            Problem ID
        """
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                INSERT INTO problems (name, type, comment, dimension, capacity,
                                     edge_weight_type, edge_weight_format,
                                     capacity_vol, capacity_weight, max_distance,
                                     service_time, vehicles, depots, periods,
                                     has_time_windows, has_pickup_delivery)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, [
                problem_data.get('name'),
                problem_data.get('type'),
                problem_data.get('comment'),
                problem_data.get('dimension'),
                problem_data.get('capacity'),
                problem_data.get('edge_weight_type'),
                problem_data.get('edge_weight_format'),
                problem_data.get('capacity_vol'),
                problem_data.get('capacity_weight'),
                problem_data.get('max_distance'),
                problem_data.get('service_time'),
                problem_data.get('vehicles'),
                problem_data.get('depots'),
                problem_data.get('periods'),
                problem_data.get('has_time_windows'),
                problem_data.get('has_pickup_delivery')
            ]).fetchone()

            return result[0] if result else None

    def insert_nodes(self, problem_id: int, nodes: List[Dict[str, Any]]) -> int:
        """
        Insert node data for a problem.

        Args:
            problem_id: Problem ID
            nodes: List of node dictionaries

        Returns:
            Number of nodes inserted
        """
        if not nodes:
            return 0

        with duckdb.connect(str(self.db_path)) as conn:
            for node in nodes:
                conn.execute("""
                    INSERT INTO nodes (problem_id, node_id, x, y, z, demand, is_depot,
                                      display_x, display_y)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    problem_id,
                    node.get('node_id'),
                    node.get('x'),
                    node.get('y'),
                    node.get('z'),
                    node.get('demand', 0),
                    node.get('is_depot', False),
                    node.get('display_x'),
                    node.get('display_y')
                ])

        return len(nodes)

    def insert_problems_batch(
        self,
        problem_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Insert multiple problems using pandas DataFrames for maximum performance.

        Leverages DuckDB's native pandas integration and columnar engine for bulk inserts.
        This approach is ~24x faster than executemany() for large datasets.

        Why pandas > numpy:
        - DuckDB has zero-copy pandas DataFrame support
        - Handles mixed types (str, float, int, bool) naturally
        - Column-oriented like DuckDB (numpy is row-oriented)
        - Built-in NULL handling

        Args:
            problem_results: List of result dictionaries from worker processes

        Returns:
            Dictionary with:
                - successful: List of successfully inserted problem names
                - failed: List of dicts with {'name': str, 'error': str} for failures
                - total_inserted: Count of successful inserts
                - total_failed: Count of failures

        Examples:
            >>> results = processor.process_files_parallel(...)
            >>> batch_result = db.insert_problems_batch(results['results'])
            >>> print(f"Inserted {batch_result['total_inserted']} problems in ~15 seconds")
        """
        import time
        import pandas as pd

        batch_start = time.time()
        successful = []
        failed = []

        if not problem_results:
            return {
                'successful': successful,
                'failed': failed,
                'total_inserted': 0,
                'total_failed': 0
            }

        # Step 1: Collect all data into lists (fast Python operation)
        all_problems = []
        all_nodes = []
        all_edge_weights = []
        all_solutions = []
        all_file_tracking = []

        collect_start = time.time()
        for temp_id, result in enumerate(problem_results, start=1):
            try:
                problem_data = result.get('problem_data')
                if not problem_data:
                    continue

                # Collect problem data. Graph columns (adjacency/fixed_edges)
                # come from the worker's top-level edges/fixed_edges keys
                # (Decision #4). Name disambiguation runs below (Decision in
                # TODO: name = file stem when the internal NAME collides within
                # the same type; original NAME goes to tsplib_name).
                problem_record = {
                    'temp_id': temp_id,  # Temporary ID for mapping (never name)
                    'name': problem_data.get('name'),
                    'type': problem_data.get('type'),
                    'comment': problem_data.get('comment'),
                    'dimension': problem_data.get('dimension'),
                    'capacity': problem_data.get('capacity'),
                    'edge_weight_type': problem_data.get('edge_weight_type'),
                    'edge_weight_format': problem_data.get('edge_weight_format'),
                    'capacity_vol': problem_data.get('capacity_vol'),
                    'capacity_weight': problem_data.get('capacity_weight'),
                    'max_distance': problem_data.get('max_distance'),
                    'service_time': problem_data.get('service_time'),
                    'vehicles': problem_data.get('vehicles'),
                    'depots': problem_data.get('depots'),
                    'periods': problem_data.get('periods'),
                    'has_time_windows': problem_data.get('has_time_windows'),
                    'has_pickup_delivery': problem_data.get('has_pickup_delivery'),
                    'tsplib_name': None,  # Set during disambiguation
                    'adjacency': result.get('edges'),
                    'fixed_edges': result.get('fixed_edges'),
                    'file_stem': Path(result['file_path']).stem
                        if result.get('file_path') else None,
                }
                all_problems.append(problem_record)

                # Collect nodes with temp_id reference
                for node in result.get('nodes', []):
                    node_record = {
                        'temp_problem_id': temp_id,
                        'node_id': node.get('node_id'),
                        'x': node.get('x'),
                        'y': node.get('y'),
                        'z': node.get('z'),
                        'demand': node.get('demand', 0),
                        'is_depot': node.get('is_depot', False),
                        'display_x': node.get('display_x'),
                        'display_y': node.get('display_y')
                    }
                    all_nodes.append(node_record)

                # Collect edge weights (Decision #2: nested-list matrix)
                edge_weight_data = result.get('edge_weight_data')
                if edge_weight_data:
                    edge_record = {
                        'temp_problem_id': temp_id,
                        'matrix_format': edge_weight_data.get('matrix_format'),
                        'is_symmetric': edge_weight_data.get('is_symmetric'),
                        'matrix': edge_weight_data.get('matrix')
                    }
                    all_edge_weights.append(edge_record)

                # Collect solutions
                solution_data = result.get('solution_data')
                if solution_data:
                    solution_record = {
                        'temp_problem_id': temp_id,
                        'solution_name': solution_data.get('name'),
                        'solution_type': solution_data.get('type'),
                        'cost': solution_data.get('cost'),
                        'routes': solution_data.get('routes', [])
                    }
                    all_solutions.append(solution_record)

                # Collect file tracking
                file_path = result.get('file_path')
                if file_path:
                    file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
                    tracking_record = {
                        'temp_problem_id': temp_id,
                        'file_path': file_path,
                        'checksum': result.get('checksum'),
                        'file_size': file_size
                    }
                    all_file_tracking.append(tracking_record)

            except Exception as e:
                problem_name = result.get('problem_data', {}).get('name', 'unknown')
                failed.append({'name': problem_name, 'error': f"Data collection failed: {e}"})
                self.logger.error(f"Failed to collect data for {problem_name}: {e}")

        # Step 1b: Disambiguate duplicate (name, type). name = file stem when the
        # internal NAME collides within the same type; original NAME goes to
        # tsplib_name (e.g. linhp318.tsp declares NAME: lin318 -> stored as
        # linhp318). Cross-type twins (att48 as TSP and as CVRP) keep the same
        # name; the type column + UNIQUE(name, type) disambiguate them.
        name_type_counts = {}
        for pr in all_problems:
            key = (pr['name'], pr['type'])
            name_type_counts[key] = name_type_counts.get(key, 0) + 1
        for pr in all_problems:
            key = (pr['name'], pr['type'])
            if (
                name_type_counts[key] > 1
                and pr.get('file_stem')
                and pr['file_stem'] != pr['name']
            ):
                pr['tsplib_name'] = pr['name']
                pr['name'] = pr['file_stem']

        collect_time = time.time() - collect_start
        self.logger.info(f"Data collection: {len(all_problems)} problems, {len(all_nodes)} nodes in {collect_time:.2f}s")

        # Step 2: Convert to pandas DataFrames (fast columnar operation)
        df_start = time.time()
        problems_df = pd.DataFrame(all_problems)
        nodes_df = pd.DataFrame(all_nodes) if all_nodes else None
        edge_weights_df = pd.DataFrame(all_edge_weights) if all_edge_weights else None
        solutions_df = pd.DataFrame(all_solutions) if all_solutions else None
        file_tracking_df = pd.DataFrame(all_file_tracking) if all_file_tracking else None
        df_time = time.time() - df_start

        self.logger.info(f"DataFrame creation: {df_time:.2f}s")

        # Step 3: Bulk insert via DuckDB (FAST columnar engine)
        insert_start = time.time()
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("BEGIN TRANSACTION")

            try:
                # Insert problems, capturing generated ids. Decision #10: the
                # mapping is keyed by temp_id (never name). The installed DuckDB
                # (1.5.5) rejects RETURNING source columns, so use the documented
                # fallback: RETURNING id zipped to temp_id by source row order
                # (DuckDB preserves INSERT...SELECT order for a DataFrame/temp
                # table scan).
                conn.register(view_name='problems_temp', python_object=problems_df)
                returned_ids: list[tuple[Any, ...]] = conn.execute(query="""
                    INSERT INTO problems (name, type, comment, dimension, capacity,
                                         edge_weight_type, edge_weight_format,
                                         capacity_vol, capacity_weight, max_distance,
                                         service_time, vehicles, depots, periods,
                                         has_time_windows, has_pickup_delivery,
                                         tsplib_name, fixed_edges, adjacency)
                    SELECT name, type, comment, dimension, capacity,
                           edge_weight_type, edge_weight_format,
                           capacity_vol, capacity_weight, max_distance,
                           service_time, vehicles, depots, periods,
                           has_time_windows, has_pickup_delivery,
                           tsplib_name, fixed_edges, adjacency
                    FROM problems_temp
                    RETURNING id
                """).fetchall()

                problem_id_mapping = dict(zip(
                    [pr['temp_id'] for pr in all_problems],
                    [row[0] for row in returned_ids]
                ))

                # Register the mapping for foreign-key joins
                mapping_df = pd.DataFrame(data=[
                    {'temp_id': tid, 'real_id': rid}
                    for tid, rid in problem_id_mapping.items()
                ])
                conn.register(view_name='problem_id_mapping', python_object=mapping_df)

                # Insert nodes with real problem IDs
                if nodes_df is not None:
                    conn.register(view_name='nodes_temp', python_object=nodes_df)
                    conn.execute(query="""
                        INSERT INTO nodes (problem_id, node_id, x, y, z, demand, is_depot, display_x, display_y)
                        SELECT m.real_id, n.node_id, n.x, n.y, n.z, n.demand, n.is_depot, n.display_x, n.display_y
                        FROM nodes_temp n
                        JOIN problem_id_mapping m ON n.temp_problem_id = m.temp_id
                    """)

                # Insert edge weight matrices (Decision #2: nested-list matrix)
                if edge_weights_df is not None:
                    conn.register(view_name='edges_temp', python_object=edge_weights_df)
                    conn.execute(query="""
                        INSERT INTO edge_weight_matrices (problem_id, matrix_format, is_symmetric, matrix)
                        SELECT m.real_id, e.matrix_format, e.is_symmetric, e.matrix
                        FROM edges_temp e
                        JOIN problem_id_mapping m ON e.temp_problem_id = m.temp_id
                    """)

                # Insert solutions
                if solutions_df is not None:
                    conn.register('solutions_temp', solutions_df)
                    conn.execute("""
                        INSERT INTO solutions (problem_id, solution_name, solution_type, cost, routes)
                        SELECT m.real_id, s.solution_name, s.solution_type, s.cost, s.routes
                        FROM solutions_temp s
                        JOIN problem_id_mapping m ON s.temp_problem_id = m.temp_id
                    """)

                # Insert file tracking
                if file_tracking_df is not None:
                    conn.register('tracking_temp', file_tracking_df)
                    conn.execute("""
                        INSERT INTO file_tracking (file_path, problem_id, checksum, file_size)
                        SELECT f.file_path, m.real_id, f.checksum, f.file_size
                        FROM tracking_temp f
                        JOIN problem_id_mapping m ON f.temp_problem_id = m.temp_id
                        ON CONFLICT (file_path) DO UPDATE SET
                            problem_id = EXCLUDED.problem_id,
                            checksum = EXCLUDED.checksum,
                            last_processed = now(),
                            file_size = EXCLUDED.file_size
                    """)

                conn.execute("COMMIT")
                successful = [row['name'] for row in all_problems]

            except Exception as e:
                conn.execute("ROLLBACK")
                self.logger.error(f"Batch insert failed: {e}")
                failed = [{'name': row['name'], 'error': str(e)} for row in all_problems]

        insert_time = time.time() - insert_start
        batch_total = time.time() - batch_start

        self.logger.info(
            f"Batch insert complete: {len(successful)} successful, {len(failed)} failed"
        )
        self.logger.info(
            f"Timing breakdown: Collect={collect_time:.2f}s, DataFrame={df_time:.2f}s, "
            f"Insert={insert_time:.2f}s, Total={batch_total:.2f}s"
        )

        return {
            'successful': successful,
            'failed': failed,
            'total_inserted': len(successful),
            'total_failed': len(failed)
        }

    def load(self, name: str, type: str) -> Dict[str, Any]:
        """
        Load a single problem by exact (name, type).

        Both arguments are required. Ambiguity is impossible because the schema
        enforces UNIQUE(name, type) (Decision #7).

        Args:
            name: Problem name
            type: Problem type (e.g. 'TSP', 'CVRP')

        Returns:
            Dictionary of the problem row (includes tsplib_name, adjacency,
            fixed_edges).

        Raises:
            NotFoundError: If no row matches (name, type).
        """
        with duckdb.connect(database=str(object=self.db_path)) as conn:
            row: tuple[Any, ...] | None = conn.execute(
                query="SELECT * FROM problems WHERE name = ? AND type = ?",
                parameters=[name, type]
            ).fetchone()
            if not row:
                raise NotFoundError(
                    message=f"Problem '{name}' of type '{type}' not found",
                    name=name,
                    type=type
                )
            columns = [col[0] for col in conn.execute(
                "SELECT * FROM problems WHERE 1=0"
            ).description]
            return dict(zip(columns, row))

    def load_matrix(self, name: str, type: str) -> list[list[int]]:
        """
        Load the full distance matrix for an EXPLICIT problem as a nested list.

        Args:
            name: Problem name
            type: Problem type (e.g. 'TSP', 'CVRP')

        Returns:
            Nested list (n x n) of integer edge weights.

        Raises:
            NotFoundError: If the problem or its edge-weight matrix is missing.
        """
        with duckdb.connect(str(self.db_path)) as conn:
            row = conn.execute("""
                SELECT e.matrix
                FROM edge_weight_matrices e
                JOIN problems p ON p.id = e.problem_id
                WHERE p.name = ? AND p.type = ?
            """, [name, type]).fetchone()
            if not row or row[0] is None:
                raise NotFoundError(
                    f"Edge weight matrix for '{name}' of type '{type}' not found",
                    name=name,
                    type=type
                )
            return [list(inner) for inner in row[0]]

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file tracking information.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file tracking info or None
        """
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute("""
                SELECT problem_id, checksum, last_processed, file_size
                FROM file_tracking
                WHERE file_path = ?
            """, [file_path]).fetchone()

            if result:
                return {
                    'problem_id': result[0],
                    'checksum': result[1],
                    'last_processed': result[2],
                    'file_size': result[3]
                }

            return None

    def update_file_tracking(self, tracking_info: Dict[str, Any]) -> None:
        """
        Update file tracking information.

        Args:
            tracking_info: Dictionary with tracking information
        """
        with duckdb.connect(str(self.db_path)) as conn:
            # Check if file path exists
            existing = conn.execute("""
                SELECT id FROM file_tracking WHERE file_path = ?
            """, [tracking_info['file_path']]).fetchone()

            if existing:
                # Update existing record
                conn.execute("""
                    UPDATE file_tracking
                    SET problem_id = ?, checksum = ?, last_processed = ?, file_size = ?
                    WHERE file_path = ?
                """, [
                    tracking_info['problem_id'],
                    tracking_info['checksum'],
                    tracking_info['last_processed'],
                    tracking_info['file_size'],
                    tracking_info['file_path']
                ])
            else:
                # Insert new record
                conn.execute("""
                    INSERT INTO file_tracking
                    (file_path, problem_id, checksum, last_processed, file_size)
                    VALUES (?, ?, ?, ?, ?)
                """, [
                    tracking_info['file_path'],
                    tracking_info['problem_id'],
                    tracking_info['checksum'],
                    tracking_info['last_processed'],
                    tracking_info['file_size']
                ])

    def get_problem_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored problems.

        Returns:
            Dictionary with statistics
        """
        with duckdb.connect(str(self.db_path)) as conn:
            # Count by type
            type_counts = conn.execute("""
                SELECT type, COUNT(*) as count, AVG(dimension) as avg_dim, MAX(dimension) as max_dim
                FROM problems
                GROUP BY type
            """).fetchall()

            # Total count
            total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]

            return {
                'total_problems': total,
                'by_type': [
                    {
                        'type': row[0],
                        'count': row[1],
                        'avg_dimension': round(row[2], 2) if row[2] else 0,
                        'max_dimension': row[3]
                    }
                    for row in type_counts
                ]
            }

    def query_problems(
        self,
        problem_type: Optional[str] = None,
        min_dimension: Optional[int] = None,
        max_dimension: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query problems with filters.

        Args:
            problem_type: Filter by problem type
            min_dimension: Minimum dimension
            max_dimension: Maximum dimension
            limit: Maximum results to return

        Returns:
            List of problem dictionaries
        """
        query = "SELECT * FROM problems WHERE 1=1"
        params = []

        if problem_type:
            query += " AND type = ?"
            params.append(problem_type)

        if min_dimension is not None:
            query += " AND dimension >= ?"
            params.append(min_dimension)

        if max_dimension is not None:
            query += " AND dimension <= ?"
            params.append(max_dimension)

        query += " LIMIT ?"  # Parameterized to prevent SQL injection
        params.append(limit)

        with duckdb.connect(str(self.db_path)) as conn:
            results = conn.execute(query, params).fetchall()

            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'type': row[2],
                    'comment': row[3],
                    'dimension': row[4],
                    'capacity': row[5],
                    'edge_weight_type': row[6],
                    'edge_weight_format': row[7]
                }
                for row in results
            ]

    def export_problem(self, problem_id: int) -> Dict[str, Any]:
        """
        Export complete problem data.

        Args:
            problem_id: Problem ID to export

        Returns:
            Dictionary with complete problem data
        """
        with duckdb.connect(str(self.db_path)) as conn:
            # Get problem data
            problem = conn.execute("""
                SELECT * FROM problems WHERE id = ?
            """, [problem_id]).fetchone()

            if not problem:
                raise DatabaseError(
                    f"Problem {problem_id} not found",
                    operation="get_problem_with_nodes"
                )

            # Get nodes
            nodes = conn.execute("""
                SELECT * FROM nodes WHERE problem_id = ?
            """, [problem_id]).fetchall()

            # NO EDGES - not precomputed

            return {
                'problem': {
                    'id': problem[0],
                    'name': problem[1],
                    'type': problem[2],
                    'comment': problem[3],
                    'dimension': problem[4]
                },
                'nodes': [
                    {
                        'node_id': node[2],
                        'x': node[3],
                        'y': node[4],
                        'z': node[5],
                        'demand': node[6],
                        'is_depot': node[7]
                    }
                    for node in nodes
                ]
            }
