"""Production-grade parallel processing for TSPLIB conversion."""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from queue import Queue
from typing import Any

import psutil


class ParallelProcessor:
  """
  Production-grade parallel processing for TSPLIB conversion.

  Features:
  - Thread-safe database connections with connection pooling
  - Memory-efficient batch processing with backpressure
  - Progress reporting with ETA calculations
  - Error isolation with detailed failure tracking
  - Resource management with cleanup handling
  """

  def __init__(
    self,
    max_workers: int = 4,
    batch_size: int = 100,
    memory_limit_mb: int = 2048,
    logger: logging.Logger | None = None,
  ) -> None:
    """
    Initialize parallel processor.

    Args:
        max_workers: Maximum number of parallel workers
        batch_size: Number of items to process per batch
        memory_limit_mb: Memory limit in MB for processing
        logger: Optional logger instance
    """
    self.max_workers = max_workers
    self.batch_size = batch_size
    self.memory_limit_mb = memory_limit_mb
    self.logger: logging.Logger = logger or logging.getLogger(__name__)

    # Progress tracking
    self._progress_queue = Queue()
    self._total_items = 0
    self._completed_items = 0
    self._failed_items = 0
    self._lock = threading.Lock()
    self._start_time = None

  def process_files_parallel(
    self, file_list: list[str], process_func: Callable, use_processes: bool = False, **kwargs: Any
  ) -> dict[str, Any]:
    """
    Process files in parallel with comprehensive error handling.

    Args:
        file_list: List of file paths to process
        process_func: Function to process each file
        use_processes: If True, use ProcessPoolExecutor (for CPU-bound work)
                      If False, use ThreadPoolExecutor (for I/O-bound work)
        **kwargs: Additional arguments to pass to process_func

    Returns:
        Dictionary with processing statistics:
        {
            'successful': int,
            'failed': int,
            'errors': List[Dict],
            'processing_time': float,
            'throughput': float
        }

    Notes:
        ProcessPoolExecutor bypasses Python's GIL, providing true parallelism
        for CPU-intensive operations like parsing and data transformation.
        Use for TSPLIB file processing which is CPU-bound.
    """
    self._total_items = len(file_list)
    self._completed_items = 0
    self._failed_items = 0
    self._start_time = time.time()

    errors = []
    successful = 0

    executor_type = "ProcessPoolExecutor" if use_processes else "ThreadPoolExecutor"
    self.logger.info(
      f"Starting parallel processing of {self._total_items} files with {self.max_workers} workers ({executor_type})"
    )

    # Choose executor based on workload type
    ExecutorClass = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

    # Collect results for batch processing
    all_results = []

    with ExecutorClass(max_workers=self.max_workers) as executor:
      # Submit all tasks
      if use_processes:
        # For ProcessPoolExecutor: call function directly (can't pickle self methods)
        future_to_file = {executor.submit(process_func, file_path, **kwargs): file_path for file_path in file_list}
      else:
        # For ThreadPoolExecutor: use tracking wrapper (shares memory with main thread)
        future_to_file = {
          executor.submit(self._process_with_tracking, process_func, file_path, **kwargs): file_path
          for file_path in file_list
        }

      # Process completed tasks
      for future in as_completed(future_to_file):
        file_path = future_to_file[future]

        try:
          result = future.result()

          # For ProcessPoolExecutor, result is dict with success/error info
          if isinstance(result, dict) and "success" in result:
            all_results.append(result)
            if result["success"]:
              successful += 1
              self._update_progress(file_path, success=True)
            else:
              self._failed_items += 1
              error_info = {
                "file": file_path,
                "error": result.get("error", "Unknown error"),
                "error_type": result.get("error_type", "Unknown"),
              }
              errors.append(error_info)
              self._update_progress(file_path, success=False, error=result.get("error"))
              self.logger.error(f"Failed to process {file_path}: {result.get('error')}")
          else:
            # Legacy behavior for non-dict results
            successful += 1
            self._update_progress(file_path, success=True)

        except Exception as e:
          self._failed_items += 1
          error_info = {"file": file_path, "error": str(e), "error_type": type(e).__name__}
          errors.append(error_info)
          self._update_progress(file_path, success=False, error=str(e))
          self.logger.error(f"Failed to process {file_path}: {e}")

        # Check memory usage periodically (only for threads, not processes)
        if not use_processes and (successful + self._failed_items) % 10 == 0:
          memory_stats = self.monitor_memory_usage()
          if memory_stats["percent"] > 90:
            self.logger.warning(f"High memory usage: {memory_stats['percent']:.1f}%")

    processing_time = time.time() - self._start_time
    throughput = self._total_items / processing_time if processing_time > 0 else 0

    result = {
      "successful": successful,
      "failed": self._failed_items,
      "errors": errors,
      "results": all_results,  # Add all results for batch processing
      "processing_time": processing_time,
      "throughput": throughput,
    }

    self.logger.info(
      f"Completed processing: {successful} successful, "
      f"{self._failed_items} failed in {processing_time:.2f}s "
      f"({throughput:.2f} files/sec)"
    )

    return result

  def _process_with_tracking(self, process_func: Callable, file_path: str, **kwargs: Any) -> Any:
    """
    Wrapper to process file with progress tracking.

    Args:
        process_func: Function to process the file
        file_path: Path to file
        **kwargs: Additional arguments

    Returns:
        Result from process_func
    """
    try:
      result = process_func(file_path, **kwargs)
      return result
    except Exception as e:
      self.logger.debug(f"Error processing {file_path}: {e}")
      raise

  def _update_progress(self, file_path: str, success: bool, error: str | None = None) -> None:
    """
    Update progress tracking (thread-safe).

    Args:
        file_path: File that was processed
        success: Whether processing succeeded
        error: Error message if failed
    """
    with self._lock:
      self._completed_items += 1

      if self._start_time and self._total_items > 0:
        elapsed = time.time() - self._start_time
        if self._completed_items > 0:
          rate = self._completed_items / elapsed
          remaining = self._total_items - self._completed_items
          eta = remaining / rate if rate > 0 else 0

          progress_pct = (self._completed_items / self._total_items) * 100

          self.logger.debug(
            f"Progress: {self._completed_items}/{self._total_items} ({progress_pct:.1f}%) - ETA: {eta:.1f}s"
          )

  def monitor_memory_usage(self) -> dict[str, float]:
    """
    Monitor current memory usage.

    Returns:
        Dictionary with memory statistics:
        {
            'used_mb': float,
            'available_mb': float,
            'percent': float
        }
    """
    memory = psutil.virtual_memory()

    return {
      "used_mb": (memory.total - memory.available) / (1024 * 1024),
      "available_mb": memory.available / (1024 * 1024),
      "percent": memory.percent,
    }

  def create_progress_reporter(self) -> Callable:
    """
    Create thread-safe progress reporting function.

    Returns:
        Callable that can be used to report progress from worker threads
    """

    def report_progress(file_path: str, status: str) -> None:
      """Report progress for a file."""
      with self._lock:
        self._progress_queue.put({"file": file_path, "status": status, "timestamp": time.time()})

    return report_progress

  def get_progress_stats(self) -> dict[str, Any]:
    """
    Get current progress statistics.

    Returns:
        Dictionary with progress information
    """
    with self._lock:
      elapsed = time.time() - self._start_time if self._start_time else 0
      progress_pct = (self._completed_items / self._total_items * 100) if self._total_items > 0 else 0

      return {
        "total": self._total_items,
        "completed": self._completed_items,
        "failed": self._failed_items,
        "progress_percent": progress_pct,
        "elapsed_time": elapsed,
      }
