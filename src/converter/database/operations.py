"""Database operations for TSPLIB data storage and retrieval."""

import logging
import time
from pathlib import Path
from typing import Any, ClassVar

import duckdb

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

    def __init__(self, db_path: str, logger: logging.Logger | None = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to DuckDB database file
            logger: Optional logger instance
        """
        self.db_path = Path(db_path)
        self.logger: logging.Logger = logger or logging.getLogger(name=__name__)
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self) -> None:
        """Create database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _initialize_schema(self) -> None:
        """Initialize database schema and indexes

        v2 topology: a thin ``problems`` hub (discovery index) + five self-contained per-type tables with duplicated common columns (Decision 1) + three satellites (Decision 2). Node data lives in array columns on the type tables (Decision 3); the v1 ``nodes`` row-table is dropped.
        """
        try:
            with duckdb.connect(database=str(self.db_path)) as conn:
                # Sequences (nodes_seq dropped with the nodes table, Decision 3)
                conn.execute(query="CREATE SEQUENCE IF NOT EXISTS problems_seq START 1")
                conn.execute(query="CREATE SEQUENCE IF NOT EXISTS file_tracking_seq START 1")
                conn.execute(query="CREATE SEQUENCE IF NOT EXISTS solutions_seq START 1")

                # Hub: discovery index only. "Which table holds att48?" lives here.
                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS problems (
                        id INTEGER PRIMARY KEY DEFAULT nextval('problems_seq'),
                        name VARCHAR NOT NULL,
                        type VARCHAR NOT NULL
                            CHECK (type IN ('TSP', 'ATSP', 'CVRP', 'HCP', 'SOP')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (name, type)
                    )
                """)

                # Type tables: self-contained; common columns duplicated BY DESIGN (Decision 1). coords is NULL iff EXPLICIT (the matrix row in edge_weight_matrices holds the data).
                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS tsp_problems (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        dimension INTEGER NOT NULL,
                        comment VARCHAR,
                        edge_weight_type VARCHAR NOT NULL,
                        edge_weight_format VARCHAR,
                        tsplib_name VARCHAR,
                        coords DOUBLE[][],
                        display_coords DOUBLE[][]
                    )
                """)

                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS atsp_problems (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        dimension INTEGER NOT NULL,
                        comment VARCHAR,
                        tsplib_name VARCHAR
                    )
                """)

                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS cvrp_problems (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        dimension INTEGER NOT NULL,
                        capacity INTEGER NOT NULL,
                        comment VARCHAR,
                        edge_weight_type VARCHAR NOT NULL,
                        edge_weight_format VARCHAR,
                        tsplib_name VARCHAR,
                        coords DOUBLE[][],
                        demands INTEGER[] NOT NULL,
                        depots INTEGER[] NOT NULL
                    )
                """)

                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS hcp_problems (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        dimension INTEGER NOT NULL,
                        adjacency INTEGER[][] NOT NULL,
                        comment VARCHAR,
                        tsplib_name VARCHAR
                    )
                """)

                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS sop_problems (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        dimension INTEGER NOT NULL,
                        fixed_edges INTEGER[][],
                        comment VARCHAR,
                        tsplib_name VARCHAR
                    )
                """)

                # Satellites: single tables, FK -> hub (Decision 2).
                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS edge_weight_matrices (
                        problem_id INTEGER PRIMARY KEY REFERENCES problems(id),
                        matrix_format VARCHAR NOT NULL,
                        is_symmetric BOOLEAN NOT NULL,
                        matrix INTEGER[][] NOT NULL
                    )
                """)

                # Create solutions table
                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS solutions (
                        id INTEGER PRIMARY KEY DEFAULT nextval('solutions_seq'),
                        problem_id INTEGER NOT NULL REFERENCES problems(id),
                        solution_name VARCHAR,
                        solution_type VARCHAR,
                        cost DOUBLE,
                        routes INTEGER[][] NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute(query="""
                    CREATE TABLE IF NOT EXISTS file_tracking (
                        id INTEGER PRIMARY KEY DEFAULT nextval('file_tracking_seq'),
                        file_path VARCHAR UNIQUE NOT NULL,
                        problem_id INTEGER REFERENCES problems(id),
                        checksum VARCHAR,
                        last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_size BIGINT
                    )
                """)

                # Indexes for query performance
                conn.execute(query="""
                    CREATE INDEX IF NOT EXISTS idx_problems_type
                    ON problems(type)
                """)

                conn.execute(query="""
                    CREATE INDEX IF NOT EXISTS idx_solutions_problem
                    ON solutions(problem_id)
                """)

                conn.execute(query="""
                    CREATE INDEX IF NOT EXISTS idx_edge_matrices_problem
                    ON edge_weight_matrices(problem_id)
                """)

                conn.execute(query="""
                    CREATE INDEX IF NOT EXISTS idx_file_tracking_path
                    ON file_tracking(file_path)
                """)

                self.logger.info(msg=f"Database schema initialized at {self.db_path}")

        except Exception as e:
            self.logger.error(msg=f"Failed to initialize database schema: {e}")
            raise

    # ------------------------------------------------------------------
    # Schema v2 write path (Task 1.2): per-type insert dispatch.
    # One explicit transaction per problem: hub row + type-table row, so a
    # mid-insert failure rolls back both (no orphan rows).
    # ------------------------------------------------------------------

    _TYPE_INSERTERS: ClassVar[dict[str, str]] = {
        "TSP": "_insert_tsp",
        "ATSP": "_insert_atsp",
        "CVRP": "_insert_cvrp",
        "HCP": "_insert_hcp",
        "SOP": "_insert_sop",
    }

    # Schema-v2 read-path registry (Task 1.5): hub -> owning type table. Same
    # dispatch shape as ``_TYPE_INSERTERS``; ``load`` / ``get_problem_stats`` /
    # ``query_problems`` resolve reads through it instead of the removed v1 STI
    # columns on the hub.
    _TYPE_TABLES: ClassVar[dict[str, str]] = {
        "TSP": "tsp_problems",
        "ATSP": "atsp_problems",
        "CVRP": "cvrp_problems",
        "HCP": "hcp_problems",
        "SOP": "sop_problems",
    }

    def _resolve_type_table(self, problem_type: Any) -> str:
        """Return the schema-v2 type table name for a problem type.

        Normalizes the type exactly like the write path (``_normalize_type_for_schema``,
        VRP-family variants -> ``cvrp_problems``) so reads resolve the same table a
        write would have stored.
        """
        return self._TYPE_TABLES[self._normalize_type_for_schema(problem_type=problem_type)]

    @staticmethod
    def _normalize_type_for_schema(problem_type: Any) -> str:
        """Map a parser problem type onto the five schema v2 types.

        VRP-family variants (VRP, MC-VRP, TW-VRP, PD-VRP, ...) all land in ``cvrp_problems``; the schema CHECK only admits the five canonical types. Raises ``DatabaseError`` for anything else.
        """
        if not isinstance(problem_type, str):
            raise DatabaseError(
                message=f"Invalid problem type {problem_type!r}", operation="insert_problem"
            )
        t: str = problem_type.strip().upper()
        if t in ("TSP", "ATSP", "CVRP", "HCP", "SOP"):
            return t
        if "VRP" in t:
            return "CVRP"
        raise DatabaseError(
            message=f"Unsupported problem type {problem_type!r}", operation="insert_problem"
        )

    def _insert_hub(self, conn: Any, data: dict[str, Any]) -> int:
        """Insert the hub row and return its generated id."""
        result = conn.execute(
            "INSERT INTO problems (name, type) VALUES (?, ?) RETURNING id",
            [data.get("name"), self._normalize_type_for_schema(problem_type=data.get("type"))],
        ).fetchone()
        if not result:
            raise DatabaseError(message="Failed to insert hub row", operation="insert_problem")
        return int(result[0])

    def _insert_tsp(self, conn: Any, problem_id: int, data: dict[str, Any]) -> None:
        """Insert the ``tsp_problems`` row for an already-inserted hub id."""
        conn.execute(
            """
            INSERT INTO tsp_problems
                (problem_id, dimension, comment, edge_weight_type, edge_weight_format,
                tsplib_name, coords, display_coords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                problem_id,
                data.get("dimension"),
                data.get("comment"),
                data.get("edge_weight_type"),
                data.get("edge_weight_format"),
                data.get("tsplib_name"),
                data.get("coords"),
                data.get("display_coords"),
            ],
        )

    def _insert_atsp(self, conn: Any, problem_id: int, data: dict[str, Any]) -> None:
        """Insert the ``atsp_problems`` row for an already-inserted hub id."""
        conn.execute(
            """
            INSERT INTO atsp_problems (problem_id, dimension, comment, tsplib_name)
            VALUES (?, ?, ?, ?)
            """,
            [
                problem_id,
                data.get("dimension"),
                data.get("comment"),
                data.get("tsplib_name"),
            ],
        )

    def _insert_cvrp(self, conn: Any, problem_id: int, data: dict[str, Any]) -> None:
        """Insert the ``cvrp_problems`` row for an already-inserted hub id."""
        demands: list[Any] = data.get("demands") or []
        depots: list[Any] = data.get("depots") or []
        dimension: Any | None = data.get("dimension")
        if dimension is not None and len(demands) != int(dimension):
            raise DatabaseError(
                message=f"demands length {len(demands)} != dimension {dimension}",
                operation="insert_problem",
            )
        conn.execute(
            """
            INSERT INTO cvrp_problems
                (problem_id, dimension, capacity, comment, edge_weight_type,
                 edge_weight_format, tsplib_name, coords, demands, depots)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                problem_id,
                dimension,
                data.get("capacity"),
                data.get("comment"),
                data.get("edge_weight_type"),
                data.get("edge_weight_format"),
                data.get("tsplib_name"),
                data.get("coords"),
                demands,
                depots,
            ],
        )

    def _insert_hcp(self, conn: Any, problem_id: int, data: dict[str, Any]) -> None:
        """Insert the ``hcp_problems`` row for an already-inserted hub id."""
        # adjacency may arrive under the transformer's legacy top-level `edges`
        # key; accept both spellings (schema column name wins).
        adjacency: Any | None = data.get("adjacency")
        if adjacency is None:
            adjacency = data.get("edges")
        conn.execute(
            """
            INSERT INTO hcp_problems (problem_id, dimension, adjacency, comment, tsplib_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                problem_id,
                data.get("dimension"),
                adjacency,
                data.get("comment"),
                data.get("tsplib_name"),
            ],
        )

    def _insert_sop(self, conn: Any, problem_id: int, data: dict[str, Any]) -> None:
        """Insert the ``sop_problems`` row for an already-inserted hub id."""
        conn.execute(
            """
            INSERT INTO sop_problems (problem_id, dimension, fixed_edges, comment, tsplib_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                problem_id,
                data.get("dimension"),
                data.get("fixed_edges"),
                data.get("comment"),
                data.get("tsplib_name"),
            ],
        )

    def insert_problem(self, problem_data: dict[str, Any]) -> int:
        """Insert one problem into the v2 schema: hub row + type-table row.

        The hub, type-table and satellite rows (``edge_weight_matrices`` / ``solutions`` / ``file_tracking``) are written in a single explicit transaction so a mid-insert failure rolls them all back. ``problem_data`` is the merged payload produced by the transformer: hub fields (name, type), shared columns (dimension, comment, capacity, edge_weight_type, edge_weight_format, tsplib_name), the per-type array payload (coords, display_coords, demands, depots, adjacency, fixed_edges) and the satellite keys ``_insert_batch_satellites`` consumes (edge_weight_data, solution_data, file_path, checksum, file_size) — so an EXPLICIT problem round-trips with its matrix row present (Task 2.1).

        Returns:
            The generated hub ``problems.id``.
        """
        ptype: str = self._normalize_type_for_schema(problem_type=problem_data.get("type"))
        inserter = getattr(self, self._TYPE_INSERTERS[ptype])
        with duckdb.connect(database=str(self.db_path)) as conn:
            conn.execute(query="BEGIN TRANSACTION")
            try:
                problem_id: int = self._insert_hub(conn, data=problem_data)
                inserter(conn, problem_id, problem_data)
                self._insert_batch_satellites(conn, problem_id, payload=problem_data)
                conn.execute(query="COMMIT")
            except Exception:
                conn.execute(query="ROLLBACK")
                raise
        return problem_id

    def insert_problems_batch(self, problem_results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Insert multiple problems into the v2 schema in one explicit transaction.

        Each worker result is dispatched per type: hub row + type-table row via
        the ``_TYPE_INSERTERS`` helpers, plus its satellite rows
        (``edge_weight_matrices`` / ``solutions`` / ``file_tracking``). The
        whole batch shares one transaction, so a mid-batch failure rolls back
        every row written so far (no orphan hub rows).

        Args:
            problem_results: list of result dictionaries from worker processes

        Returns:
            dictionary with:
                - successful: list of successfully inserted problem names
                - failed: list of dicts with {'name': str, 'error': str} for failures
                - total_inserted: Count of successful inserts
                - total_failed: Count of failures
        """
        batch_start = time.time()
        successful: list[str] = []
        failed: list[dict[str, str]] = []

        if not problem_results:
            return {
                "successful": successful,
                "failed": failed,
                "total_inserted": 0,
                "total_failed": 0,
            }

        # Step 1: Collect the merged per-type payload + satellites (fast Python).
        # Per-row collection errors are captured per row; rows that fail here
        # never enter the batch transaction.
        collected: list[dict[str, Any]] = []
        collect_start = time.time()
        for result in problem_results:
            try:
                if not result.get("problem_data"):
                    continue
                collected.append(self._build_batch_problem_payload(result))
            except Exception as e:
                problem_name = result.get("problem_data", {}).get("name", "unknown")
                failed.append({"name": problem_name, "error": f"Data collection failed: {e}"})
                self.logger.error("Failed to collect data for %s: %s", problem_name, e)
        collect_time = time.time() - collect_start
        self.logger.info("Data collection: %d problems in %.2fs", len(collected), collect_time)

        # Step 1b: Disambiguate duplicate (name, type). name = file stem when the
        # internal NAME collides within the same type; original NAME goes to
        # tsplib_name (e.g. linhp318.tsp declares NAME: lin318 -> stored as
        # linhp318). Cross-type twins (att48 as TSP and as CVRP) keep the same
        # name; the type column + UNIQUE(name, type) disambiguate them.
        self._disambiguate_names(collected)

        if not collected:
            return {
                "successful": successful,
                "failed": failed,
                "total_inserted": 0,
                "total_failed": len(failed),
            }

        # Step 2: Insert everything in one transaction; any failure rolls back
        # the whole batch (rollback-all-on-failure, Task 1.4 DoD).
        insert_start = time.time()
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                for payload in collected:
                    problem_id = self._insert_hub(conn, data=payload)
                    ptype = self._normalize_type_for_schema(problem_type=payload.get("type"))
                    getattr(self, self._TYPE_INSERTERS[ptype])(conn, problem_id, payload)
                    self._insert_batch_satellites(conn, problem_id, payload)
                conn.execute("COMMIT")
                successful = [payload["name"] for payload in collected]
            except Exception as e:
                conn.execute("ROLLBACK")
                self.logger.error("Batch insert failed: %s", e)
                failed = [{"name": payload["name"], "error": str(e)} for payload in collected]

        insert_time = time.time() - insert_start
        batch_total = time.time() - batch_start
        self.logger.info(
            "Batch insert complete: %d successful, %d failed",
            len(successful),
            len(failed),
        )
        self.logger.info(
            "Timing breakdown: Collect=%.2fs, Insert=%.2fs, Total=%.2fs",
            collect_time,
            insert_time,
            batch_total,
        )

        return {
            "successful": successful,
            "failed": failed,
            "total_inserted": len(successful),
            "total_failed": len(failed),
        }

    def _build_batch_problem_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        """Build the merged v2 problem payload + satellites from a worker result.

        Mirrors ``insert_problem``'s merged payload: hub fields (name, type),
        shared columns (dimension, comment, capacity, edge_weight_type,
        edge_weight_format, tsplib_name) and the per-type array payload
        (coords, display_coords, demands, depots, adjacency, fixed_edges).
        Satellite data rides along under dedicated keys.
        """
        problem_data = result.get("problem_data", {})
        file_path = result.get("file_path")
        return {
            "name": problem_data.get("name"),
            "type": problem_data.get("type"),
            "comment": problem_data.get("comment"),
            "dimension": problem_data.get("dimension"),
            "capacity": problem_data.get("capacity"),
            "edge_weight_type": problem_data.get("edge_weight_type"),
            "edge_weight_format": problem_data.get("edge_weight_format"),
            "tsplib_name": None,  # Set during disambiguation
            # Per-type array payload (worker top-level keys, Task 1.2/Decision 3)
            "coords": result.get("coords"),
            "display_coords": result.get("display_coords"),
            "demands": result.get("demands", []),
            "depots": result.get("depots", []),
            # Graph data (worker top-level keys, Decision #4)
            "adjacency": result.get("edges"),
            "fixed_edges": result.get("fixed_edges"),
            # Satellites
            "edge_weight_data": result.get("edge_weight_data"),
            "solution_data": result.get("solution_data"),
            "file_path": file_path,
            "checksum": result.get("checksum"),
            "file_size": (
                Path(file_path).stat().st_size if file_path and Path(file_path).exists() else 0
            ),
            "file_stem": Path(file_path).stem if file_path else None,
        }

    def _disambiguate_names(self, collected: list[dict[str, Any]]) -> None:
        """Apply the batch name→file-stem disambiguation in place (v1 logic preserved)."""
        name_type_counts: dict[tuple[Any, Any], int] = {}
        for payload in collected:
            key: tuple[Any, Any] = (payload["name"], payload["type"])
            name_type_counts[key] = name_type_counts.get(key, 0) + 1
        for payload in collected:
            key = (payload["name"], payload["type"])
            if (
                name_type_counts[key] > 1
                and payload.get("file_stem")
                and payload["file_stem"] != payload["name"]
            ):
                payload["tsplib_name"] = payload["name"]
                payload["name"] = payload["file_stem"]

    def _insert_batch_satellites(self, conn: Any, problem_id: int, payload: dict[str, Any]) -> None:
        """Insert a problem's satellite rows (matrix / solutions / file_tracking)."""
        edge_weight_data: Any | None = payload.get("edge_weight_data")
        if edge_weight_data and edge_weight_data.get("matrix") is not None:
            conn.execute(
                """
                INSERT INTO edge_weight_matrices
                    (problem_id, matrix_format, is_symmetric, matrix)
                VALUES (?, ?, ?, ?)
                """,
                [
                    problem_id,
                    edge_weight_data.get("matrix_format"),
                    edge_weight_data.get("is_symmetric"),
                    edge_weight_data.get("matrix"),
                ],
            )

        solution_data: Any | None = payload.get("solution_data")
        if solution_data:
            conn.execute(
                """
                INSERT INTO solutions
                    (problem_id, solution_name, solution_type, cost, routes)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    problem_id,
                    solution_data.get("name"),
                    solution_data.get("type"),
                    solution_data.get("cost"),
                    solution_data.get("routes", []),
                ],
            )

        file_path: Any | None = payload.get("file_path")
        if file_path:
            conn.execute(
                """
                INSERT INTO file_tracking (file_path, problem_id, checksum, file_size)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (file_path) DO UPDATE SET
                    problem_id = EXCLUDED.problem_id,
                    checksum = EXCLUDED.checksum,
                    last_processed = now(),
                    file_size = EXCLUDED.file_size
                """,
                [file_path, problem_id, payload.get("checksum"), payload.get("file_size")],
            )

    def load(self, name: str, type: str) -> dict[str, Any]:
        """
        Load a single problem by exact (name, type).

        Both arguments are required. Ambiguity is impossible because the schema
        enforces UNIQUE(name, type) (Decision #7).

        Args:
            name: Problem name
            type: Problem type (e.g. 'TSP', 'CVRP')

        Returns:
            dictionary of the full type-table row joined to the hub row (includes tsplib_name, adjacency, fixed_edges and the per-type array columns, e.g. coords).

        Raises:
            NotFoundError: If no row matches (name, type).
        """
        normalized_type: str = self._normalize_type_for_schema(problem_type=type)
        table: str = self._TYPE_TABLES[normalized_type]
        with duckdb.connect(database=str(object=self.db_path)) as conn:
            row: tuple[Any, ...] | None = conn.execute(
                query=(
                    f"""SELECT * FROM problems p
                    JOIN {table} t ON t.problem_id = p.id
                    WHERE p.name = ? AND p.type = ?"""
                ),
                parameters=[name, normalized_type],
            ).fetchone()
            if not row:
                raise NotFoundError(
                    message=f"Problem '{name}' of type '{type}' not found", name=name, type=type
                )
            columns: list[str] = [
                col[0]
                for col in conn.execute(
                    query=(
                        f"""SELECT * FROM problems p
                        JOIN {table} t ON t.problem_id = p.id
                        WHERE 1=0"""
                    )
                ).description
            ]
            return dict(zip(columns, row, strict=True))

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
        with duckdb.connect(database=str(self.db_path)) as conn:
            row: tuple[Any, ...] | None = conn.execute(
                query="""
                SELECT e.matrix
                FROM edge_weight_matrices e
                JOIN problems p ON p.id = e.problem_id
                WHERE p.name = ? AND p.type = ?
            """,
                parameters=[name, type],
            ).fetchone()
            if not row or row[0] is None:
                raise NotFoundError(
                    message=f"Edge weight matrix for '{name}' of type '{type}' not found",
                    name=name,
                    type=type,
                )
            return [list(inner) for inner in row[0]]

    def get_file_info(self, file_path: str) -> dict[str, Any] | None:
        """
        Get file tracking information.

        Args:
            file_path: Path to file

        Returns:
            dictionary with file tracking info or None
        """
        with duckdb.connect(database=str(self.db_path)) as conn:
            result: tuple[Any, ...] | None = conn.execute(
                query="""
                SELECT problem_id, checksum, last_processed, file_size
                FROM file_tracking
                WHERE file_path = ?
            """,
                parameters=[file_path],
            ).fetchone()

            if result:
                return {
                    "problem_id": result[0],
                    "checksum": result[1],
                    "last_processed": result[2],
                    "file_size": result[3],
                }

            return None

    def update_file_tracking(self, tracking_info: dict[str, Any]) -> None:
        """
        Update file tracking information.

        Args:
            tracking_info: dictionary with tracking information
        """
        with duckdb.connect(database=str(self.db_path)) as conn:
            # Check if file path exists
            existing: tuple[Any, ...] | None = conn.execute(
                query="""
                SELECT id FROM file_tracking WHERE file_path = ?
            """,
                parameters=[tracking_info["file_path"]],
            ).fetchone()

            if existing:
                # Update existing record
                conn.execute(
                    query="""
                    UPDATE file_tracking
                    SET problem_id = ?, checksum = ?, last_processed = ?, file_size = ?
                    WHERE file_path = ?
                """,
                    parameters=[
                        tracking_info["problem_id"],
                        tracking_info["checksum"],
                        tracking_info["last_processed"],
                        tracking_info["file_size"],
                        tracking_info["file_path"],
                    ],
                )
            else:
                # Insert new record
                conn.execute(
                    query="""
                    INSERT INTO file_tracking
                    (file_path, problem_id, checksum, last_processed, file_size)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    parameters=[
                        tracking_info["file_path"],
                        tracking_info["problem_id"],
                        tracking_info["checksum"],
                        tracking_info["last_processed"],
                        tracking_info["file_size"],
                    ],
                )

    def get_problem_stats(self) -> dict[str, Any]:
        """
        Get statistics about stored problems.

        Returns:
            dictionary with statistics
        """
        with duckdb.connect(database=str(self.db_path)) as conn:
            # Dimension lives on the five type tables (the hub has no STI
            # columns, Task 1.1). Aggregate per type over a UNION ALL of the
            # type tables joined to the hub; LEFT JOIN keeps hub rows counted
            # even if a type row were ever missing.
            dimension_union: str = " UNION ALL ".join(
                f"""SELECT problem_id, dimension
                FROM {table}"""
                for table in self._TYPE_TABLES.values()
            )
            type_counts: list[tuple[Any, ...]] = conn.execute(query=f"""
                SELECT p.type,
                      COUNT(*) AS count,
                      AVG(t.dimension) AS avg_dim,
                      MAX(t.dimension) AS max_dim
                FROM problems p
                LEFT JOIN ({dimension_union}) t ON t.problem_id = p.id
                GROUP BY p.type
                ORDER BY p.type
            """).fetchall()

            # Total count
            total_row: tuple[Any, ...] | None = conn.execute(
                query="SELECT COUNT(*) FROM problems"
            ).fetchone()
            if total_row is None:
                raise DatabaseError(
                    message="Failed to count problems", operation="get_problem_stats"
                )
            total = total_row[0]

            return {
                "total_problems": total,
                "by_type": [
                    {
                        "type": row[0],
                        "count": row[1],
                        "avg_dimension": round(number=row[2], ndigits=2) if row[2] else 0,
                        "max_dimension": row[3],
                    }
                    for row in type_counts
                ],
            }

    def query_problems(
        self,
        problem_type: str | None = None,
        min_dimension: int | None = None,
        max_dimension: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query problems with filters.

        The hub has no STI columns (Task 1.1), so the query reads each type
        table joined to the hub and UNION ALLs them. ``capacity`` /
        ``edge_weight_type`` / ``edge_weight_format`` exist only on the TSP and
        CVRP type tables; the other tables contribute typed NULLs.

        Args:
            problem_type: Filter by problem type (VRP-family variants are
                normalized to CVRP, matching the write path).
            min_dimension: Minimum dimension
            max_dimension: Maximum dimension
            limit: Maximum results to return

        Returns:
            list of problem dictionaries
        """
        selects: list[str] = []
        for ptype in ("TSP", "ATSP", "CVRP", "HCP", "SOP"):
            table: str = self._TYPE_TABLES[ptype]
            has_weights: bool = ptype in ("TSP", "CVRP")
            capacity_col: str = f"{table}.capacity" if ptype == "CVRP" else "CAST(NULL AS INTEGER)"
            ewt_col: str = f"{table}.edge_weight_type" if has_weights else "CAST(NULL AS VARCHAR)"
            ewf_col: str = f"{table}.edge_weight_format" if has_weights else "CAST(NULL AS VARCHAR)"
            selects.append(f"""
                SELECT p.id, p.name, p.type, {table}.comment AS comment,
                      {table}.dimension AS dimension,
                      {capacity_col} AS capacity,
                      {ewt_col} AS edge_weight_type,
                      {ewf_col} AS edge_weight_format
                FROM problems p
                JOIN {table} ON {table}.problem_id = p.id
                """)

        query = "SELECT * FROM (" + " UNION ALL ".join(selects) + ") q WHERE 1=1"
        params: list[Any] = []

        if problem_type:
            query += " AND q.type = ?"
            params.append(self._normalize_type_for_schema(problem_type=problem_type))

        if min_dimension is not None:
            query += " AND q.dimension >= ?"
            params.append(min_dimension)

        if max_dimension is not None:
            query += " AND q.dimension <= ?"
            params.append(max_dimension)

        query += " ORDER BY q.name LIMIT ?"  # Parameterized to prevent SQL injection
        params.append(limit)

        with duckdb.connect(str(self.db_path)) as conn:
            results: list[tuple[Any, ...]] = conn.execute(query, parameters=params).fetchall()

            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "comment": row[3],
                    "dimension": row[4],
                    "capacity": row[5],
                    "edge_weight_type": row[6],
                    "edge_weight_format": row[7],
                }
                for row in results
            ]

    def export_problem(self, problem_id: int) -> dict[str, Any]:
        """
        Export complete problem data.

        Args:
            problem_id: Problem ID to export

        Returns:
            dictionary with complete problem data
        """
        with duckdb.connect(database=str(self.db_path)) as conn:
            # Get problem data
            problem: tuple[Any, ...] | None = conn.execute(
                query="""
                SELECT * FROM problems WHERE id = ?
            """,
                parameters=[problem_id],
            ).fetchone()

            if not problem:
                raise DatabaseError(
                    message=f"Problem {problem_id} not found", operation="get_problem_with_nodes"
                )

            # Get nodes
            nodes: list[tuple[Any, ...]] = conn.execute(
                query="""
                SELECT * FROM nodes WHERE problem_id = ?
            """,
                parameters=[problem_id],
            ).fetchall()

            # NO EDGES - not precomputed

            return {
                "problem": {
                    "id": problem[0],
                    "name": problem[1],
                    "type": problem[2],
                    "comment": problem[3],
                    "dimension": problem[4],
                },
                "nodes": [
                    {
                        "node_id": node[2],
                        "x": node[3],
                        "y": node[4],
                        "z": node[5],
                        "demand": node[6],
                        "is_depot": node[7],
                    }
                    for node in nodes
                ],
            }
