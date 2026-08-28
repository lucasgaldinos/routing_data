"""File discovery and scanning for TSPLIB files."""

from pathlib import Path
from typing import List, Dict, Any, Iterator, Optional
import logging


class FileScanner:
    """
    File discovery and scanning for TSPLIB conversion.

    Features:
    - Recursive directory traversal
    - Pattern matching for different TSPLIB file types
    - Batch processing support
    - File metadata collection
    """

    def __init__(
        self,
        batch_size: int = 100,
        max_workers: int = 4,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize file scanner.

        Args:
            batch_size: Number of files per batch
            max_workers: Maximum parallel workers (for future use)
            logger: Optional logger instance
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)

    def scan_directory(
        self,
        directory: str,
        patterns: List[str] = None,
        recursive: bool = True
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Scan directory for TSPLIB files and yield batches.

        Args:
            directory: Directory path to scan
            patterns: File patterns to match (e.g., ['*.tsp', '*.vrp'])
            recursive: Whether to scan subdirectories

        Yields:
            Batches of file information dictionaries
        """
        if patterns is None:
            patterns = ['*.tsp', '*.vrp', '*.atsp', '*.hcp', '*.sop']

        dir_path = Path(directory)

        if not dir_path.exists():
            self.logger.error(f"Directory not found: {directory}")
            return

        # Collect all matching files
        files = []
        for pattern in patterns:
            if recursive:
                found_files = list(dir_path.rglob(pattern))
            else:
                found_files = list(dir_path.glob(pattern))

            files.extend(found_files)

        self.logger.info(f"Found {len(files)} files matching patterns {patterns}")

        # Yield batches
        batch = []
        for file_path in files:
            file_info = self._get_file_info(file_path)
            batch.append(file_info)

            if len(batch) >= self.batch_size:
                yield batch
                batch = []

        # Yield remaining files
        if batch:
            yield batch

    def scan_files(
        self,
        directory: str,
        patterns: List[str] = None,
        recursive: bool = True
    ) -> List[str]:
        """
        Scan directory and return list of file paths.

        Args:
            directory: Directory path to scan
            patterns: File patterns to match
            recursive: Whether to scan subdirectories

            Returns:
            List of file paths as strings
        """
        if patterns is None:
            patterns = ['*.tsp', '*.vrp', '*.atsp', '*.hcp', '*.sop']

        dir_path = Path(directory)

        if not dir_path.exists():
            self.logger.error(f"Directory not found: {directory}")
            return []

        # Collect all matching files
        files = []
        for pattern in patterns:
            if recursive:
                found_files = list(dir_path.rglob(pattern))
            else:
                found_files = list(dir_path.glob(pattern))

            files.extend([str(f) for f in found_files])

        self.logger.info(f"Found {len(files)} files")
        return files

    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get file information and metadata.

        Args:
            file_path: Path object for file

        Returns:
            Dictionary with file information
        """
        stat = file_path.stat()

        return {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix,
            'file_size': stat.st_size,
            'problem_type': self._detect_problem_type(file_path.suffix),
            'parent_directory': file_path.parent.name,
        }

    def _detect_problem_type(self, extension: str) -> str:
        """
        Detect problem type from file extension.

        Args:
            extension: File extension (e.g., '.tsp')

        Returns:
            Problem type string
        """
        type_map = {
            '.tsp': 'TSP',
            '.vrp': 'VRP',
            '.atsp': 'ATSP',
            '.hcp': 'HCP',
            '.sop': 'SOP'
        }

        return type_map.get(extension.lower(), 'UNKNOWN')

    def get_file_count(self, directory: str, patterns: List[str] = None) -> int:
        """
        Get count of matching files without loading them.

        Args:
            directory: Directory path to scan
            patterns: File patterns to match

        Returns:
            Number of matching files
        """
        return len(self.scan_files(directory, patterns))
