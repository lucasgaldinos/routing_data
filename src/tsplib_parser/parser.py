"""TSPLIB95 parser integration for ETL converter."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Optional

from .exceptions import ParseError, ValidationError
from .models import DemandsField, IndexedCoordinatesField, StandardProblem, StringField
from .validation import validate_problem_data


class FormatParser:
    """TSPLIB95 file parser with complete extraction and normalization.

    Parses TSPLIB95-format routing problems (TSP, VRP, ATSP, HCP, SOP, TOUR)
    and extracts structured data with normalized indices and validated structure.
    Handles VRP variants and SPECIAL distance types.

    Attributes
    ----------
    logger : logging.Logger
        Logger instance for tracking operations
    _additional_vrp_fields : dict
        VRP extension fields from preprocessing (internal use)

    Methods
    -------
    parse_file(file_path, special_func=None)
        Main parsing method - returns complete normalized data
    validate_problem(problem)
        Validates parsed problem structure
    detect_special_distance_type(file_path)
        Checks if file needs custom distance function

    Notes
    -----
    Key Features:
    - Supports all TSPLIB problem types (TSP, VRP, ATSP, HCP, SOP, TOUR)
    - Handles VRP extensions (time windows, pickup-delivery, multi-capacity)
    - SPECIAL distance type support via custom functions
    - 1-based TSPLIB → 0-based database index conversion
    - Comprehensive validation with detailed error messages

    Examples
    --------
    >>> parser = FormatParser()
    >>> data = parser.parse_file('gr17.tsp')
    >>> data.keys()
    dict_keys(['problem_data', 'nodes', 'tours', 'metadata'])

    >>> # Check if special function needed
    >>> if parser.detect_special_distance_type('problem.tsp'):
    ...     data = parser.parse_file('problem.tsp', special_func=my_distance_func)

    See Also
    --------
    format.loaders.parse_tsplib : Simplified parsing interface
    format.extraction : Pure extraction functions
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize TSPLIB parser.

        Parameters
        ----------
        logger : logging.Logger, optional
            Logger instance for tracking parsing operations.
            If None, creates a default logger for this module.

        Examples
        --------
        >>> parser = FormatParser()
        >>> # With custom logger
        >>> import logging
        >>> logger = logging.getLogger('my_app')
        >>> parser = FormatParser(logger=logger)
        """
        self.logger: logging.Logger = logger or logging.getLogger(name=__name__)
        self._additional_vrp_fields: dict[str, Any] = {}

    def parse_file(
        self,
        file_path: str,
        special_func: Optional[Callable[[int, int], float]] = None
    ) -> dict[str, Any]:
        """Parse TSPLIB file and return complete normalized data structure.

        Parses any TSPLIB95-compatible file (TSP, VRP, ATSP, HCP, SOP, TOUR) and
        extracts structured data with normalized indices. Handles VRP variants and SPECIAL distance types via custom functions.

        Parameters
        ----------
        file_path : str
            Path to TSPLIB file to parse
        special_func : callable[[int, int], float], optional
            Custom distance function for SPECIAL edge weight types.
            Function signature: f(node_i, node_j) -> distance

        Returns
        -------
        dict of str to any
            Normalized problem data with keys:
            - problem_data : dict - Basic problem metadata (type, dimension, capacity, etc.)
            - nodes : list of dict - Node coordinates, demands, depot flags (0-based indices)
            - tours : list of dict - Solution tours if available (0-based indices)
            - metadata : dict - File and processing metadata

        Raises
        ------
        ParseError
            If file parsing fails or file format is invalid
        ValidationError
            If parsed problem structure is invalid

        Examples
        --------
        >>> parser = FormatParser()
        >>> data = parser.parse_file('gr17.tsp')
        >>> data['problem_data']['name']
        'gr17'
        >>> len(data['nodes'])
        17

        >>> # With custom distance function for SPECIAL type
        >>> def custom_dist(i, j):
        ...     return abs(i - j) * 1.5
        >>> data = parser.parse_file('special.tsp', special_func=custom_dist)

        Notes
        -----
        - Automatically preprocesses VRP variants (multi-capacity, time windows)
        - Converts 1-based TSPLIB indices to 0-based for database compatibility
        - Does NOT precompute edge weights (computed on-demand for EXPLICIT types)
        """
        try:
            # Preprocess VRP variants before parsing
            processed_file = self._preprocess_vrp_file(file_path)

            # Load and parse TSPLIB file directly (inlined from loaders.load)
            with open(file=processed_file, mode='r', encoding='utf-8') as f:
                text: str = f.read()
            problem: StandardProblem = StandardProblem.parse(text, special=special_func)

            # Clean up temporary file if created
            if processed_file != file_path:
                Path(processed_file).unlink(missing_ok=True)

            # Validate the loaded problem
            self.validate_problem(problem)

            # Extract components - NO EDGE PRECOMPUTATION
            # demands/depots are exposed for ALL problems (incl. coordinate-less
            # EXPLICIT CVRP) so the transformer can build the schema v2 array
            # columns even when _extract_nodes returns [] (Decision 3).
            demands, depots = self._extract_demands_depots(problem)
            result = {
                'problem_data': self._extract_problem_data(problem),
                'nodes': self._extract_nodes(problem),
                'tours': self._extract_tours(problem),
                'metadata': self._extract_metadata(problem, file_path),
                'edges': [],
                'fixed_edges': [],
                'demands': demands,
                'depots': depots,
            }

            # Expose graph data as top-level keys (Decision #4) so the
            # transformer/worker/insert chain reads them uniformly.
            edge_data_format: Any | Literal['EDGE_LIST'] = getattr(problem, 'edge_data_format', None) or 'EDGE_LIST'
            result['edges'] = self._extract_edges(text, edge_data_format)
            result['fixed_edges'] = self._extract_fixed_edges(text)

            # Better logging for different problem types
            problem_type = result['problem_data'].get('type')
            dimension = result['problem_data'].get('dimension', 0)
            node_count = len(result['nodes'])

            if node_count == 0 and dimension > 0:
                # Explicit weight matrix problem
                self.logger.info(msg=f"Successfully parsed {file_path}: {problem_type} "
                               f"dim={dimension} (explicit weights)")
            else:
                # Coordinate-based problem
                self.logger.info(msg=f"Successfully parsed {file_path}: {problem_type} "
                               f"with {node_count} nodes")
            return result

        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def _preprocess_vrp_file(self, file_path: str) -> str:
        """Preprocess VRP file to handle extended variants.

        Processes VRP file extensions not supported by standard TSPLIB95 parser,
        including multi-constraint capacities, time windows, and pickup-delivery.
        Creates a temporary compatible file if modifications are needed.

        Parameters
        ----------
        file_path : str
            Path to original VRP file

        Returns
        -------
        str
            Path to preprocessed file (temporary if modified, original otherwise)

        Notes
        -----
        Handles the following VRP extensions:
        - Multi-constraint capacities: CAPACITY_VOL, CAPACITY_WEIGHT
        - Distance constraints: DISTANCE field
        - Time windows: TIME_WINDOW_SECTION
        - Pickup-delivery: PICKUP_SECTION, DELIVERY_SECTION
        - Multi-dimensional demands: weight and volume

        Extended fields are stored in self._additional_vrp_fields for later
        use in metadata extraction.

        See Also
        --------
        _extract_metadata : Uses stored additional VRP fields
        """
        try:
            with open(file=file_path, mode='r', encoding='utf-8') as f:
                content: str = f.read()
        except UnicodeDecodeError:
            # Try with different encoding if utf-8 fails
            with open(file=file_path, mode='r', encoding='latin-1') as f:
                content: str = f.read()

        original_content: str = content

        # Track additional VRP fields for metadata
        additional_fields: dict[str, Any] = {}

        # Handle multi-constraint CAPACITY fields (CAPACITY_VOL, CAPACITY_WEIGHT)
        lines: list[str] = content.split('\n')
        processed_lines: list[str] = []
        i: int = 0

        in_demand_section: bool = False

        while i < len(lines):
            line: str = lines[i].strip()

            # Track when we're in DEMAND_SECTION
            if line == 'DEMAND_SECTION':
                in_demand_section = True
                processed_lines.append(line)
            elif line.endswith('_SECTION') or line == 'EOF':
                in_demand_section = False

                # Handle special VRP sections
                if line == 'TIME_WINDOW_SECTION':
                    additional_fields['has_time_windows'] = True
                    # Skip time window section for basic TSPLIB95 compatibility
                    j: int = i + 1
                    while j < len(lines) and not lines[j].strip().endswith('_SECTION') and lines[j].strip() != 'EOF':
                        j += 1
                    i = j - 1  # Skip the time window data
                elif line == 'PICKUP_SECTION':
                    additional_fields['has_pickup_delivery'] = True
                    # Skip pickup section for basic TSPLIB95 compatibility
                    j: int = i + 1
                    while j < len(lines) and not lines[j].strip().endswith('_SECTION') and lines[j].strip() != 'EOF':
                        j += 1
                    i = j - 1  # Skip the pickup data
                elif line in ['SERVICE_TIME_SECTION', 'PICKUP_DELIVERY_SECTION', 'DELIVERY_SECTION',
                             'STANDTIME_SECTION', 'READY_TIME_SECTION', 'DUE_DATE_SECTION']:
                    # Skip other extended VRP sections
                    j: int = i + 1
                    while j < len(lines) and not lines[j].strip().endswith('_SECTION') and lines[j].strip() != 'EOF':
                        j += 1
                    i = j - 1  # Skip the section data
                else:
                    processed_lines.append(line)
            elif in_demand_section and line:
                # Handle multi-dimensional demands (weight and volume)
                parts: list[str] = line.split()
                if len(parts) >= 3:
                    # Format: node_id weight_demand volume_demand
                    # For TSPLIB95 compatibility, use only weight demand
                    node_id: str = parts[0]
                    weight_demand: str = parts[1]
                    volume_demand: str = parts[2] if len(parts) > 2 else '0'

                    # Store volume demands for later reference
                    if 'volume_demands' not in additional_fields:
                        additional_fields['volume_demands'] = {}
                    additional_fields['volume_demands'][int(node_id)] = int(volume_demand)

                    # Output only weight demand for standard TSPLIB95 format
                    processed_lines.append(f"{node_id} {weight_demand}")
                else:
                    processed_lines.append(line)

            # Handle CAPACITY field with potential multi-constraint variants
            elif line.startswith('CAPACITY :'):
                # Extract main capacity value
                capacity_match: list[str] = line.split(':', 1)
                if len(capacity_match) == 2:
                    processed_lines.append(f"CAPACITY : {capacity_match[1].strip()}")

                    # Look ahead for CAPACITY_VOL, CAPACITY_WEIGHT, etc.
                    j: int = i + 1
                    while j < len(lines):
                        next_line: str = lines[j].strip()
                        if next_line.startswith('CAPACITY_VOL :'):
                            vol_value: str = next_line.split(':', 1)[1].strip()
                            additional_fields['capacity_vol'] = int(vol_value)
                            j += 1  # Skip this line in main processing
                        elif next_line.startswith('CAPACITY_WEIGHT :'):
                            weight_value: str = next_line.split(':', 1)[1].strip()
                            additional_fields['capacity_weight'] = int(weight_value)
                            j += 1  # Skip this line in main processing
                        elif next_line.startswith(('NODE_COORD_SECTION', 'DEMAND_SECTION', 'DEPOT_SECTION', 'EOF')):
                            break  # End of capacity-related fields
                        elif next_line and ':' in next_line and not next_line.startswith('CAPACITY'):
                            break  # Different field type
                        else:
                            j += 1
                    i = j - 1  # Adjust main loop counter

            # Handle DISTANCE field (distance-constrained VRP)
            elif line.startswith('DISTANCE :'):
                distance_value: str = line.split(':', 1)[1].strip()
                additional_fields['max_distance'] = float(distance_value)
                # Don't add DISTANCE line to processed content (not standard TSPLIB95)

            # Handle other extended VRP fields
            elif any(line.startswith(f'{field} :') for field in [
                'SERVICE_TIME', 'TIME_WINDOW', 'PICKUP_DELIVERY',
                'VEHICLES', 'DEPOTS', 'PERIODS'
            ]):
                field_name: str = line.split(':')[0].strip().lower()
                field_value: str = line.split(':', 1)[1].strip()
                additional_fields[field_name] = field_value
                # Don't add extended fields to processed content

            else:
                processed_lines.append(line)

            i += 1

        # Store additional fields for later use in metadata
        self._additional_vrp_fields = additional_fields

        # Only create temporary file if content was modified
        if additional_fields:
            processed_content: str = '\n'.join(processed_lines)
            if processed_content != original_content:
                # Create temporary processed file
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.vrp', delete=False, encoding='utf-8')
                temp_file.write(processed_content)
                temp_file.close()

                self.logger.debug(f"Preprocessed VRP file {file_path} -> {temp_file.name} "
                                f"(additional fields: {list(additional_fields.keys())})")
                return temp_file.name

        # Return original file if no preprocessing needed
        return file_path

    def _extract_problem_data(self, problem: StandardProblem) -> dict[str, Any]:
        """Extract basic problem metadata from StandardProblem.

        Uses StandardProblem.as_name_dict() for clean data extraction (excludes
        default values). Normalizes problem types and handles VRP variant detection.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        dict of str to any
            Problem metadata including type, dimension, capacity, edge weight info

        Notes
        -----
        - Automatically detects VRP variants (MC-VRP, TW-VRP, PD-VRP, D-VRP)
        - Uses _additional_vrp_fields populated during preprocessing
        - Normalizes problem types (e.g., "TSP (AUTHOR)" → "TSP")
        """
        # Use as_name_dict() to get clean data (excludes defaults)
        data: dict[str, Any] = problem.as_name_dict()

        # Normalize problem type to handle variations like "TSP (M.~HOFMEISTER)"
        # Note: Field is named 'problem_type' in Python to avoid shadowing built-in
        raw_type = data.get('problem_type', '')
        normalized_type: str = self._normalize_problem_type(raw_type)

        # Base problem data
        # Note: Using 'type' as dict key to match database schema (SQL doesn't care about Python built-ins)
        result = {
            'name': data.get('name'),
            'type': normalized_type,  # Maps from problem_type field to 'type' dict key
            'comment': data.get('comment'),
            'dimension': data.get('dimension'),
            'capacity': data.get('capacity'),
            'edge_weight_type': data.get('edge_weight_type'),
            'edge_weight_format': data.get('edge_weight_format'),
            'node_coord_type': data.get('node_coord_type'),
            'display_data_type': data.get('display_data_type'),
        }

        # Add edge weights if present (EXPLICIT problems)
        # Convert List[List] to Matrix object for proper indexing
        if hasattr(problem, 'edge_weights') and problem.edge_weights:
            matrix_obj = problem.create_explicit_matrix()
            if matrix_obj:
                result['edge_weights'] = matrix_obj
            else:
                result['edge_weights'] = problem.edge_weights

        # Add additional VRP fields if present
        if hasattr(self, '_additional_vrp_fields') and self._additional_vrp_fields:
            for field_name, field_value in self._additional_vrp_fields.items():
                result[field_name] = field_value

            # Update type to reflect VRP variant if needed
            # NOTE: max_distance is NOT part of type - it's stored in dedicated field
            vrp_fields = self._additional_vrp_fields
            if any(field in vrp_fields for field in ['capacity_vol', 'has_time_windows', 'has_pickup_delivery']):
                # Complex VRP variant classification
                constraints = []
                if 'capacity_vol' in vrp_fields:
                    constraints.append('MC')  # Multi-Constraint
                if 'has_time_windows' in vrp_fields:
                    constraints.append('TW')  # Time Windows
                if 'has_pickup_delivery' in vrp_fields:
                    constraints.append('PD')  # Pickup-Delivery
                # max_distance is stored in dedicated field, not in type name

                if constraints:
                    result['type'] = f"{''.join(constraints)}-VRP"
                else:
                    result['type'] = 'CVRP'   # Default to CVRP (includes distance-constrained)

        return result

    def _normalize_problem_type(self, raw_type: str) -> str:
        """Normalize problem type strings to standard TSPLIB95 types.

        Removes author annotations and parenthetical comments from problem types.

        Parameters
        ----------
        raw_type : str
            Raw problem type string from TSPLIB file

        Returns
        -------
        str
            Normalized problem type (TSP, ATSP, CVRP, etc.)

        Examples
        --------
        >>> parser._normalize_problem_type("TSP (M.~HOFMEISTER)")
        'TSP'
        >>> parser._normalize_problem_type("ATSP")
        'ATSP'
        """
        if not raw_type:
            return raw_type

        # Extract base type from parenthetical variations
        base_type = raw_type.split('(')[0].strip().upper()

        # Map to standard types
        known_types = {'TSP', 'ATSP', 'CVRP', 'VRP', 'HCP', 'SOP', 'TOUR'}

        if base_type in known_types:
            return base_type

        # Return original if no normalization needed
        return raw_type

    def _extract_nodes(self, problem: StandardProblem) -> list[dict[str, Any]]:
        """Extract node data for coordinate-based problems.

        Converts 1-based TSPLIB node IDs to 0-based database indices. Only
        problems that carry a ``NODE_COORD_SECTION`` produce node rows.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        list of dict
            Node dictionaries with 0-based indices. Each dict contains:
            - node_id : int - 0-based database index
            - x, y, z : float or None - Coordinates
            - demand : int - Node demand (VRP, 0 for non-VRP)
            - is_depot : bool - Depot flag (VRP only)
            - display_x, display_y : float or None - Display coordinates

        Notes
        -----
        - Returns an EMPTY list for coordinate-less problems (EXPLICIT weight
          matrices, HCP adjacency-only, SOP fixed-edge problems). The virtual
          node scaffold that fabricated ``dimension``-many NULL-coordinate rows
          is removed (Decision 3): those rows carried no information and forced
          a meaningless ``nodes == dimension`` invariant.
        - VRP demands/depots are NOT lost for coordinate-less problems: they
          are exposed as the ``demands``/``depots`` keys on the parse result
          (see ``_extract_demands_depots``) and routed into the schema v2 array
          columns by the transformer.
        """
        # Check if we have node coordinates
        has_coordinates: IndexedCoordinatesField | Literal[False] = hasattr(problem, 'node_coords') and problem.node_coords
        if not has_coordinates:
            return []

        nodes = []

        # Extract demands if available (VRP)
        demands = {}
        if hasattr(problem, 'demands') and problem.demands:
            demands: DemandsField = problem.demands

        # Extract depot information (VRP)
        depots = set()
        if hasattr(problem, 'depots') and problem.depots:
            depots = set(problem.depots) if isinstance(problem.depots, list) else {problem.depots}

        # Extract display data if available
        display_data = {}
        if hasattr(problem, 'display_data') and problem.display_data:
            display_data = problem.display_data

        # Process coordinate-based problems (TSP with coordinates)
        # TSPLIB uses 1-based indexing, convert to 0-based for database
        for tsplib_node_id, coords in problem.node_coords.items():
            node_id = tsplib_node_id - 1  # Convert to 0-based

            node = {
                'node_id': node_id,
                'x': coords[0] if len(coords) > 0 else None,
                'y': coords[1] if len(coords) > 1 else None,
                'z': coords[2] if len(coords) > 2 else None,
                'demand': demands.get(tsplib_node_id, 0),
                'is_depot': tsplib_node_id in depots,
            }

            # Add display coordinates if available
            if tsplib_node_id in display_data:
                display_coords = display_data[tsplib_node_id]
                node['display_x'] = display_coords[0] if len(display_coords) > 0 else None
                node['display_y'] = display_coords[1] if len(display_coords) > 1 else None

            nodes.append(node)

        return nodes

    def _extract_demands_depots(
        self, problem: StandardProblem
    ) -> tuple[list[int], list[int]]:
        """Extract VRP demands and depots as schema v2 array columns.

        Exposes demands/depots independently of node extraction so coordinate-less EXPLICIT CVRP problems (which have no ``NODE_COORD_SECTION``) still populate ``cvrp_problems.demands`` and ``cvrp_problems.depots``.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        tuple of (list of int, list of int)
            - demands: list of length ``dimension``, 0-based node index ->
              demand (0 for nodes without an entry); empty list when the
              problem has no DEMAND_SECTION.
            - depots: sorted list of 0-based depot node ids; empty list when
              the problem has no DEPOT_SECTION.
        """
        dimension = int(getattr(problem, 'dimension', 0) or 0)

        demands_raw = {}
        if hasattr(problem, 'demands') and problem.demands:
            demands_raw = problem.demands
        if demands_raw:
            demands: list[int] = [int(demands_raw.get(i + 1, 0)) for i in range(dimension)]
        else:
            demands = []

        depots_raw: Any = []
        if hasattr(problem, 'depots') and problem.depots:
            depots_raw = problem.depots
        if isinstance(depots_raw, list):
            depots = sorted(int(d) - 1 for d in depots_raw)
        else:
            depots: list[int] = [int(depots_raw) - 1]
        return demands, depots


    def _extract_tours(self, problem: StandardProblem) -> list[dict[str, Any]]:
        """Extract solution tour data if available.

        Parses tour data from .tour files. Converts 1-based TSPLIB node IDs to
        0-based indices and removes -1 terminators.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        list of dict
            Tour dictionaries with:
            - tour_id : int - Sequential tour identifier
            - nodes : list of int - 0-based node indices in tour order

        Notes
        -----
        Returns empty list if no tours available (typical for .tsp files).
        Tours are commonly found in .tour solution files.
        """
        tours = []

        if hasattr(problem, 'tours') and problem.tours:
            for idx, tour in enumerate(iterable=problem.tours):
                # Remove -1 terminators if present
                tour_nodes = [node - 1 for node in tour if node != -1]  # Convert to 0-based
                tours.append({
                    'tour_id': idx,
                    'nodes': tour_nodes
                })

        return tours

    def _section_content(self, text: str, section_name: str) -> list[str]:
        """Return the raw lines belonging to a TSPLIB ``*_SECTION``.

        Collects the non-empty lines that follow the ``section_name`` header up to the next ``*_SECTION`` header or ``EOF`` marker. Returns an empty list if the section is absent.

        Parameters
        ----------
        text : str
            Raw TSPLIB file text.
        section_name : str
            Section header, e.g. ``EDGE_DATA_SECTION``.

        Returns
        -------
        list of str
            The trimmed content lines of the section.
        """
        lines: list[str] = text.split(sep='\n')
        in_section = False
        content: list[str] = []
        for line in lines:
            stripped: str = line.strip()
            if not in_section:
                if stripped == section_name:
                    in_section = True
                continue
            # Stop at end-of-file marker
            if stripped == 'EOF':
                break
            # Stop at the next *_SECTION header (other than the current one)
            if stripped.endswith('_SECTION') and stripped != section_name:
                break
            # Stop at a keyword header such as "FIXED_EDGES :" (all-uppercase
            # keyword, optionally followed by a colon). ADJ_LIST data lines like
            # "5: 1 2" have a numeric label and are NOT treated as headers.
            if ':' in stripped:
                header: str = stripped.split(sep=':', maxsplit=1)[0].strip()
                if header and any(c.isalpha() for c in header) and all(
                        c.isupper() or c.isdigit() or c == '_' for c in header):
                    break
            content.append(stripped)
        return content

    def _extract_edges(self, text: str, edge_data_format: str) -> list[list[int]]:
        """Extract graph edge data from ``EDGE_DATA_SECTION``.

        Parses HCP graph data (``EDGE_LIST`` or ``ADJ_LIST`` format) into 0-based
        ``[from, to]`` pairs. TSPLIB95 uses 1-based indices; this normalizes to
        0-based for database compatibility.

        Parameters
        ----------
        text : str
            Raw TSPLIB file text.
        edge_data_format : str
            Value of the ``EDGE_DATA_FORMAT`` header (``EDGE_LIST`` or ``ADJ_LIST``).
            Defaults to ``EDGE_LIST`` when empty/unknown.

        Returns
        -------
        list of list of int
            0-based ``[from, to]`` edge pairs.
        """
        fmt: str = (edge_data_format or 'EDGE_LIST').strip().upper()
        content: list[str] = self._section_content(text, section_name='EDGE_DATA_SECTION')
        edges: list[list[int]] = []

        if fmt == 'ADJ_LIST':
            # Format: "from: to1 to2 ... -1" per adjacency list; the whole
            # section is terminated by an extra "-1".
            for line in content:
                if not line or line == '-1':
                    continue
                if ':' in line:
                    from_part, to_part = line.split(sep=':', maxsplit=1)
                    try:
                        from_node = int(from_part.strip())
                    except ValueError:
                        continue
                    for token in to_part.split():
                        token: str = token.strip()
                        if not token or token == '-1':
                            continue
                        try:
                            edges.append([from_node - 1, int(token) - 1])
                        except ValueError:
                            continue
            return edges

        # EDGE_LIST format (default): one "from to" pair per line.
        for line in content:
            line: str = line.strip()
            if not line or line == '-1':
                continue
            parts: list[str] = line.split()
            if len(parts) >= 2:
                try:
                    edges.append([int(parts[0]) - 1, int(parts[1]) - 1])
                except ValueError:
                    continue
        return edges

    def _extract_fixed_edges(self, text: str) -> list[list[int]]:
        """Extract fixed edge data from ``FIXED_EDGES_SECTION``.

        Parses the ``from to`` pairs declared between ``FIXED_EDGES_SECTION`` and
        the ``-1`` terminator into 0-based ``[from, to]`` pairs. Returns ``[]``
        when the section is absent.

        Parameters
        ----------
        text : str
            Raw TSPLIB file text.

        Returns
        -------
        list of list of int
            0-based ``[from, to]`` fixed-edge pairs.
        """
        content: list[str] = self._section_content(text, section_name='FIXED_EDGES_SECTION')
        edges: list[list[int]] = []
        for line in content:
            line: str = line.strip()
            if not line or line == '-1':
                continue
            parts: list[str] = line.split()
            if len(parts) >= 2:
                try:
                    edges.append([int(parts[0]) - 1, int(parts[1]) - 1])
                except ValueError:
                    continue
        return edges

    def _extract_metadata(self, problem: StandardProblem, file_path: str) -> dict[str, Any]:
        """Extract file and processing metadata.

        Collects file information, problem characteristics, and VRP-specific
        metadata from preprocessing step.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance
        file_path : str
            Path to the original TSPLIB file

        Returns
        -------
        dict of str to any
            Metadata including file stats, symmetry info, weight source,
            and VRP extensions from preprocessing

        Notes
        -----
        Includes self._additional_vrp_fields populated during VRP preprocessing.
        """
        file_path_obj = Path(file_path)

        return {
            'file_path': str(file_path),
            'file_size': file_path_obj.stat().st_size if file_path_obj.exists() else 0,
            'file_name': file_path_obj.name,
            'problem_source': file_path_obj.parent.name,
            'has_coordinates': hasattr(problem, 'node_coords') and bool(problem.node_coords),
            'has_demands': hasattr(problem, 'demands') and bool(problem.demands),
            'has_depots': hasattr(problem, 'depots') and bool(problem.depots),
            'is_symmetric': self._check_symmetry(problem),
            'weight_source': self._identify_weight_source(problem)
        }

    def _check_symmetry(self, problem: StandardProblem) -> bool:
        """Determine if problem has symmetric distances.

        Checks problem type and edge weight format to detect symmetry.
        ATSP is always asymmetric, specific weight formats indicate symmetry.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        bool
            True if symmetric distances, False if asymmetric

        Notes
        -----
        Symmetric formats: LOWER_DIAG_ROW, UPPER_DIAG_ROW, LOWER_ROW, UPPER_ROW.
        ATSP problem_type is always asymmetric regardless of format.
        """
        # ATSP is explicitly asymmetric
        if hasattr(problem, 'problem_type') and problem.problem_type == 'ATSP':
            return False

        # Check edge weight format for symmetry indicators
        if hasattr(problem, 'edge_weight_format'):
            symmetric_formats: list[str] = ['LOWER_DIAG_ROW', 'UPPER_DIAG_ROW', 'LOWER_ROW', 'UPPER_ROW']
            if problem.edge_weight_format in symmetric_formats:
                return True

        # Most TSP, VRP, HCP, SOP are symmetric by default
        return True

    def _identify_weight_source(self, problem: StandardProblem) -> str:
        """Identify how edge weights are determined.

        Categorizes the edge weight calculation method based on EDGE_WEIGHT_TYPE field.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance

        Returns
        -------
        str
            One of: 'explicit_matrix', 'coordinate_based', 'special_function', or 'unknown'

        Notes
        -----
        - 'explicit_matrix': Full weight matrix provided (EXPLICIT type)
        - 'coordinate_based': Calculated from coordinates (EUC_2D, GEO, etc.)
        - 'special_function': Custom function required (SPECIAL type)
        - 'unknown': Type not recognized or missing
        """
        if hasattr(problem, 'edge_weight_type'):
            edge_type: StringField = problem.edge_weight_type

            if edge_type == 'EXPLICIT':
                return 'explicit_matrix'
            elif edge_type == 'SPECIAL':
                return 'special_function'
            elif edge_type in ['EUC_2D', 'EUC_3D', 'MAX_2D', 'MAX_3D', 'MAN_2D', 'MAN_3D',
                              'CEIL_2D', 'GEO', 'ATT', 'XRAY1', 'XRAY2']:
                return 'coordinate_based'

        return 'unknown'

    def validate_problem(self, problem: StandardProblem) -> None:
        """Validate parsed problem structure and data integrity.

        Performs comprehensive validation including field presence, data types,
        structural consistency, and coordinate/dimension matching.

        Parameters
        ----------
        problem : StandardProblem
            Parsed TSPLIB95 problem instance to validate

        Raises
        ------
        ValidationError
            If validation fails with detailed error messages

        Notes
        -----
        Validates:
        - Required fields (name, type, dimension)
        - Coordinate count vs dimension match
        - Normalized problem types
        - Field data types and ranges
        """
        if not isinstance(problem, StandardProblem):
            raise ValidationError("Not a valid StandardProblem")

        # Extract and normalize data for validation
        raw_data: dict[str, Any] = problem.as_name_dict()
        normalized_data: dict[str, Any] = raw_data.copy()
        if 'problem_type' in normalized_data:
            normalized_data['type'] = self._normalize_problem_type(raw_type=normalized_data['problem_type'])
            del normalized_data['problem_type']  # Remove to avoid confusion
        errors: list[str] = validate_problem_data(data=normalized_data)

        # Additional structural validation
        if hasattr(problem, 'dimension') and problem.dimension:
            if hasattr(problem, 'node_coords') and problem.node_coords:
                if len(problem.node_coords) != problem.dimension:
                    errors.append(f"Node coordinate count {len(problem.node_coords)} "
                                f"doesn't match dimension {problem.dimension}")

        if errors:
            raise ValidationError(f"Validation errors: {'; '.join(errors)}")

    def detect_special_distance_type(self, file_path: str) -> bool:
        """Detect if file requires custom distance function.

        Scans file content for EDGE_WEIGHT_TYPE: SPECIAL declaration, which
        indicates a custom distance function is needed for parsing.

        Parameters
        ----------
        file_path : str
            Path to TSPLIB file to check

        Returns
        -------
        bool
            True if SPECIAL distance type detected, False otherwise

        Examples
        --------
        >>> parser = FormatParser()
        >>> parser.detect_special_distance_type('problem.tsp')
        False
        >>> parser.detect_special_distance_type('special_problem.tsp')
        True

        Notes
        -----
        Used to determine if parse_file() requires a special_func parameter.
        """
        try:
            with open(file=file_path, mode='r') as f:
                content: str = f.read()
                return 'EDGE_WEIGHT_TYPE' in content and 'SPECIAL' in content
        except Exception:
            return False
