"""
Comprehensive tests for FileScanner class.

Test Coverage:
- Initialization with different parameters
- Directory scanning (recursive/non-recursive)
- File pattern matching
- Batch processing
- File metadata extraction
- Problem type detection
- File counting
- Error handling
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from converter.core.scanner import FileScanner


@pytest.fixture
def temp_directory():
  """
  WHAT: Create temp directory with test files
  WHY: Need isolated test environment
  EXPECTED: Directory with various TSPLIB files
  DATA: .tsp, .vrp, .atsp, .hcp, .sop files + subdirectory
  """
  tmpdir = tempfile.mkdtemp(prefix="scanner_test_")

  # Create test files in root
  (Path(tmpdir) / "problem1.tsp").write_text("NAME: test1")
  (Path(tmpdir) / "problem2.vrp").write_text("NAME: test2")
  (Path(tmpdir) / "problem3.atsp").write_text("NAME: test3")
  (Path(tmpdir) / "ignored.txt").write_text("ignore me")

  # Create subdirectory with files
  subdir = Path(tmpdir) / "subdir"
  subdir.mkdir()
  (subdir / "problem4.hcp").write_text("NAME: test4")
  (subdir / "problem5.sop").write_text("NAME: test5")
  (subdir / "problem6.tour").write_text("NAME: test6")

  yield tmpdir

  # Cleanup
  shutil.rmtree(tmpdir)


class TestFileScannerInitialization:
  """Test FileScanner initialization and configuration."""

  def test_default_initialization(self):
    """
    WHAT: Test FileScanner with default parameters
    WHY: Should use sensible defaults
    EXPECTED: batch_size=100, max_workers=4
    DATA: No parameters
    """
    scanner = FileScanner()

    assert scanner.batch_size == 100
    assert scanner.max_workers == 4
    assert scanner.logger is not None

  def test_custom_initialization(self):
    """
    WHAT: Test FileScanner with custom parameters
    WHY: Should accept custom batch_size and max_workers
    EXPECTED: Uses provided values
    DATA: batch_size=50, max_workers=8
    """
    scanner = FileScanner(batch_size=50, max_workers=8)

    assert scanner.batch_size == 50
    assert scanner.max_workers == 8


class TestFileScannerScanFiles:
  """Test scan_files method."""

  def test_scan_files_recursive_all_patterns(self, temp_directory):
    """
    WHAT: Test recursive scan with all default patterns
    WHY: Should find all TSPLIB files in directory tree
    EXPECTED: 6 files (.tsp, .vrp, .atsp, .hcp, .sop, .tour)
    DATA: temp_directory with 6 TSPLIB files + 1 .txt
    """
    scanner = FileScanner()
    files = scanner.scan_files(temp_directory)

    # Should find 6 TSPLIB files (ignoring .txt)
    assert len(files) == 6

    # Check file names
    file_names = [Path(f).name for f in files]
    assert "problem1.tsp" in file_names
    assert "problem2.vrp" in file_names
    assert "problem3.atsp" in file_names
    assert "problem4.hcp" in file_names
    assert "problem5.sop" in file_names
    assert "problem6.tour" in file_names
    assert "ignored.txt" not in file_names

  def test_scan_files_non_recursive(self, temp_directory):
    """
    WHAT: Test non-recursive scan (root directory only)
    WHY: Should only find files in root, not subdirectories
    EXPECTED: 3 files (.tsp, .vrp, .atsp)
    DATA: temp_directory with files in root + subdir
    """
    scanner = FileScanner()
    files = scanner.scan_files(temp_directory, recursive=False)

    # Should find only 3 files in root
    assert len(files) == 3

    file_names = [Path(f).name for f in files]
    assert "problem1.tsp" in file_names
    assert "problem2.vrp" in file_names
    assert "problem3.atsp" in file_names
    # Files from subdir should NOT be found
    assert "problem4.hcp" not in file_names
    assert "problem5.sop" not in file_names

  def test_scan_files_specific_patterns(self, temp_directory):
    """
    WHAT: Test scan with specific file patterns
    WHY: Should only match specified patterns
    EXPECTED: 2 files (.tsp, .vrp)
    DATA: patterns=['*.tsp', '*.vrp']
    """
    scanner = FileScanner()
    files = scanner.scan_files(temp_directory, patterns=["*.tsp", "*.vrp"])

    # Should find only .tsp and .vrp files
    assert len(files) == 2

    file_names = [Path(f).name for f in files]
    assert "problem1.tsp" in file_names
    assert "problem2.vrp" in file_names
    assert "problem3.atsp" not in file_names

  def test_scan_files_single_pattern(self, temp_directory):
    """
    WHAT: Test scan with single pattern
    WHY: Should find only files matching that pattern
    EXPECTED: 1 file (.tsp)
    DATA: patterns=['*.tsp']
    """
    scanner = FileScanner()
    files = scanner.scan_files(temp_directory, patterns=["*.tsp"])

    assert len(files) == 1
    assert Path(files[0]).name == "problem1.tsp"

  def test_scan_files_nonexistent_directory(self):
    """
    WHAT: Test scan of nonexistent directory
    WHY: Should handle gracefully without errors
    EXPECTED: Empty list
    DATA: /nonexistent/dir
    """
    scanner = FileScanner()
    files = scanner.scan_files("/nonexistent/dir")

    assert files == []


class TestFileScannerScanDirectory:
  """Test scan_directory method (batched scanning)."""

  def test_scan_directory_batches(self, temp_directory):
    """
    WHAT: Test batched scanning with specific batch_size
    WHY: Should yield files in batches
    EXPECTED: 3 batches (2+2+2 for 6 files)
    DATA: batch_size=2, 6 files
    """
    scanner = FileScanner(batch_size=2)
    batches = list(scanner.scan_directory(temp_directory))

    # 6 files with batch_size=2 -> 3 batches
    assert len(batches) == 3
    assert len(batches[0]) == 2
    assert len(batches[1]) == 2
    assert len(batches[2]) == 2

  def test_scan_directory_partial_batch(self, temp_directory):
    """
    WHAT: Test batched scanning with partial last batch
    WHY: Should yield remaining files in last batch
    EXPECTED: 2 batches (4+2 for 6 files)
    DATA: batch_size=4, 6 files
    """
    scanner = FileScanner(batch_size=4)
    batches = list(scanner.scan_directory(temp_directory))

    # 6 files with batch_size=4 -> 2 batches (4+2)
    assert len(batches) == 2
    assert len(batches[0]) == 4
    assert len(batches[1]) == 2

  def test_scan_directory_file_info_structure(self, temp_directory):
    """
    WHAT: Test file_info dictionary structure
    WHY: Should contain all expected metadata fields
    EXPECTED: file_path, file_name, file_extension, file_size, problem_type, parent_directory
    DATA: Any file from scan_directory
    """
    scanner = FileScanner()
    batches = list(scanner.scan_directory(temp_directory))

    # Get first file_info
    file_info = batches[0][0]

    # Check all expected keys
    assert "file_path" in file_info
    assert "file_name" in file_info
    assert "file_extension" in file_info
    assert "file_size" in file_info
    assert "problem_type" in file_info
    assert "parent_directory" in file_info

  def test_scan_directory_problem_type_detection(self, temp_directory):
    """
    WHAT: Test problem type detection from file extension
    WHY: Should correctly identify problem types
    EXPECTED: TSP, VRP, ATSP, HCP, SOP, TOUR
    DATA: Files with various extensions
    """
    scanner = FileScanner()
    batches = list(scanner.scan_directory(temp_directory))

    # Flatten batches
    all_files = [f for batch in batches for f in batch]

    # Check problem types
    types = {f["file_name"]: f["problem_type"] for f in all_files}
    assert types["problem1.tsp"] == "TSP"
    assert types["problem2.vrp"] == "VRP"
    assert types["problem3.atsp"] == "ATSP"
    assert types["problem4.hcp"] == "HCP"
    assert types["problem5.sop"] == "SOP"
    assert types["problem6.tour"] == "TOUR"


class TestFileScannerFileCount:
  """Test get_file_count method."""

  def test_get_file_count_all_patterns(self, temp_directory):
    """
    WHAT: Test file counting with all patterns
    WHY: Should count all TSPLIB files
    EXPECTED: 6 files
    DATA: temp_directory with 6 TSPLIB files
    """
    scanner = FileScanner()
    count = scanner.get_file_count(temp_directory)

    assert count == 6

  def test_get_file_count_specific_patterns(self, temp_directory):
    """
    WHAT: Test file counting with specific patterns
    WHY: Should count only matching files
    EXPECTED: 2 files
    DATA: patterns=['*.tsp', '*.vrp']
    """
    scanner = FileScanner()
    count = scanner.get_file_count(temp_directory, patterns=["*.tsp", "*.vrp"])

    assert count == 2

  def test_get_file_count_empty_directory(self):
    """
    WHAT: Test file counting in empty directory
    WHY: Should return 0
    EXPECTED: 0 files
    DATA: Temp directory with no TSPLIB files
    """
    tmpdir = tempfile.mkdtemp(prefix="empty_")
    scanner = FileScanner()

    try:
      count = scanner.get_file_count(tmpdir)
      assert count == 0
    finally:
      shutil.rmtree(tmpdir)


class TestFileScannerMetadata:
  """Test file metadata extraction."""

  def test_file_size_metadata(self, temp_directory):
    """
    WHAT: Test file size in metadata
    WHY: Should report actual file size
    EXPECTED: file_size > 0
    DATA: temp_directory files
    """
    scanner = FileScanner()
    batches = list(scanner.scan_directory(temp_directory))

    # Check all files have size > 0
    for batch in batches:
      for file_info in batch:
        assert file_info["file_size"] > 0

  def test_parent_directory_metadata(self, temp_directory):
    """
    WHAT: Test parent directory name in metadata
    WHY: Should correctly identify parent directory
    EXPECTED: Root files have temp_dir name, subdir files have 'subdir'
    DATA: temp_directory with root and subdir files
    """
    scanner = FileScanner()
    batches = list(scanner.scan_directory(temp_directory))

    all_files = [f for batch in batches for f in batch]

    # Find a root file and subdir file
    root_file = next(f for f in all_files if f["file_name"] == "problem1.tsp")
    subdir_file = next(f for f in all_files if f["file_name"] == "problem4.hcp")

    # Root file should have temp directory name as parent
    assert Path(temp_directory).name in root_file["parent_directory"]

    # Subdir file should have 'subdir' as parent
    assert subdir_file["parent_directory"] == "subdir"


class TestFileScannerIntegration:
  """Integration tests for FileScanner."""

  def test_full_workflow_scan_and_process(self, temp_directory):
    """
    WHAT: Test complete scanning workflow
    WHY: Should scan, batch, and extract metadata correctly
    EXPECTED: All files found with correct metadata
    DATA: temp_directory with 6 files
    """
    scanner = FileScanner(batch_size=3)

    # Scan and collect all files
    all_files = []
    for batch in scanner.scan_directory(temp_directory):
      all_files.extend(batch)

    # Verify total count
    assert len(all_files) == 6

    # Verify all have required metadata
    for file_info in all_files:
      assert Path(file_info["file_path"]).exists()
      assert file_info["file_extension"] in [".tsp", ".vrp", ".atsp", ".hcp", ".sop", ".tour"]
      assert file_info["problem_type"] in ["TSP", "VRP", "ATSP", "HCP", "SOP", "TOUR"]
      assert file_info["file_size"] > 0
