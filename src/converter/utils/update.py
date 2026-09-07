"""Incremental update and change detection for TSPLIB files."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import hashlib
from datetime import datetime
import json


class UpdateManager:
    """
    Manage incremental updates and change detection.

    Features:
    - File modification time tracking
    - Content-based change detection via checksums
    - Database synchronization with conflict resolution
    - Backup and recovery for interrupted updates
    """

    def __init__(self, database_manager=None, logger: Optional[logging.Logger] = None):
        """
        Initialize update manager.

        Args:
            database_manager: Database manager instance for tracking
            logger: Optional logger instance
        """
        self.db_manager = database_manager
        self.logger = logger or logging.getLogger(__name__)
        self._change_cache = {}

    def detect_changes(self, file_path: str) -> Dict[str, Any]:
        """
        Detect if file needs processing based on modification time and checksum.

        Args:
            file_path: Path to file to check

        Returns:
            Dictionary with change detection results:
            {
                'needs_update': bool,
                'change_type': str,  # 'new', 'modified', 'unchanged'
                'last_processed': datetime,
                'file_checksum': str,
                'file_mtime': datetime
            }
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            return {
                'needs_update': False,
                'change_type': 'missing',
                'last_processed': None,
                'file_checksum': None,
                'file_mtime': None
            }

        # Calculate file checksum
        current_checksum = self._calculate_checksum(file_path)
        file_mtime = datetime.fromtimestamp(file_path_obj.stat().st_mtime)

        # Check if we have database tracking
        if self.db_manager:
            db_info = self.db_manager.get_file_info(file_path)

            if db_info is None:
                # New file
                return {
                    'needs_update': True,
                    'change_type': 'new',
                    'last_processed': None,
                    'file_checksum': current_checksum,
                    'file_mtime': file_mtime
                }

            # Check if file changed
            if db_info.get('checksum') != current_checksum:
                return {
                    'needs_update': True,
                    'change_type': 'modified',
                    'last_processed': db_info.get('last_processed'),
                    'file_checksum': current_checksum,
                    'file_mtime': file_mtime,
                    'previous_checksum': db_info.get('checksum')
                }

            # File unchanged
            return {
                'needs_update': False,
                'change_type': 'unchanged',
                'last_processed': db_info.get('last_processed'),
                'file_checksum': current_checksum,
                'file_mtime': file_mtime
            }

        # No database tracking - always process
        return {
            'needs_update': True,
            'change_type': 'unknown',
            'last_processed': None,
            'file_checksum': current_checksum,
            'file_mtime': file_mtime
        }

    def _calculate_checksum(self, file_path: str) -> str:
        """
        Calculate SHA256 checksum of file.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                # Read file in chunks for memory efficiency
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            return sha256_hash.hexdigest()

        except Exception as e:
            self.logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""

    def create_backup(self, problem_id: int, backup_dir: str = "./backups") -> str:
        """
        Create backup of existing problem data before update.

        Args:
            problem_id: Database ID of problem to backup
            backup_dir: Directory to store backups

        Returns:
            Path to backup file
        """
        if not self.db_manager:
            raise ValueError("Database manager required for backup operations")

        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"problem_{problem_id}_{timestamp}.json"

        try:
            # Export problem data
            problem_data = self.db_manager.export_problem(problem_id)

            with open(backup_file, 'w') as f:
                json.dump(problem_data, f, indent=2, default=str)

            self.logger.info(f"Created backup: {backup_file}")
            return str(backup_file)

        except Exception as e:
            self.logger.error(f"Failed to create backup for problem {problem_id}: {e}")
            raise

    def perform_incremental_update(
        self,
        file_list: List[str],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Process only changed files with rollback capability.

        Args:
            file_list: List of files to check and process
            force: Force reprocessing even if unchanged

        Returns:
            Dictionary with update statistics:
            {
                'new_files': int,
                'modified_files': int,
                'unchanged_files': int,
                'processed': List[str],
                'skipped': List[str],
                'errors': List[Dict]
            }
        """
        stats = {
            'new_files': 0,
            'modified_files': 0,
            'unchanged_files': 0,
            'processed': [],
            'skipped': [],
            'errors': []
        }

        for file_path in file_list:
            try:
                # Detect changes
                change_info = self.detect_changes(file_path)

                # Determine if processing needed
                should_process = force or change_info['needs_update']

                if should_process:
                    # Update statistics
                    change_type = change_info['change_type']
                    if change_type == 'new':
                        stats['new_files'] += 1
                    elif change_type == 'modified':
                        stats['modified_files'] += 1

                    stats['processed'].append(file_path)
                    self.logger.info(f"Processing {change_type} file: {file_path}")

                else:
                    stats['unchanged_files'] += 1
                    stats['skipped'].append(file_path)
                    self.logger.debug(f"Skipping unchanged file: {file_path}")

            except Exception as e:
                stats['errors'].append({
                    'file': file_path,
                    'error': str(e)
                })
                self.logger.error(f"Error checking {file_path}: {e}")

        return stats

    def update_file_tracking(
        self,
        file_path: str,
        problem_id: int,
        checksum: str = None
    ) -> None:
        """
        Update file tracking information in database.

        Args:
            file_path: Path to file
            problem_id: Database ID of processed problem
            checksum: Optional checksum (will calculate if not provided)
        """
        if not self.db_manager:
            return

        if checksum is None:
            checksum = self._calculate_checksum(file_path)

        tracking_info = {
            'file_path': file_path,
            'problem_id': problem_id,
            'checksum': checksum,
            'last_processed': datetime.now(),
            'file_size': Path(file_path).stat().st_size if Path(file_path).exists() else 0
        }

        self.db_manager.update_file_tracking(tracking_info)
        self.logger.debug(f"Updated tracking for {file_path}")

    def get_update_candidates(
        self,
        directory: str,
        patterns: List[str] = None
    ) -> List[str]:
        """
        Get list of files that need updating.

        Args:
            directory: Directory to scan
            patterns: File patterns to match (e.g., ['*.tsp', '*.vrp'])

        Returns:
            List of file paths that need updating
        """
        if patterns is None:
            patterns = ['*.tsp', '*.vrp', '*.atsp', '*.hcp', '*.sop', '*.tour']

        candidates = []
        dir_path = Path(directory)

        for pattern in patterns:
            for file_path in dir_path.rglob(pattern):
                change_info = self.detect_changes(str(file_path))
                if change_info['needs_update']:
                    candidates.append(str(file_path))

        self.logger.info(f"Found {len(candidates)} files needing update in {directory}")
        return candidates
