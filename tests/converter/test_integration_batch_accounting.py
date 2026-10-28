"""Batch accounting: every input problem ends as inserted, failed, or skipped — visibly.

WHAT
----
Pins the relationship between what goes into ``insert_problems_batch`` and what
comes out: the happy path, the mixed batch where one file's type is refused, and
the payload that carries no ``problem_data`` at all.

WHY
---
``commands.py:161`` inserts the whole corpus in one transaction and then logs
``results['successful']`` / ``results['failed']``. If one refused type rolls back
everything, or a payload is dropped without a count, the log reports a run that
never happened — and JSON is still written for those problems afterwards. This is
B1/B3 in ``TODO.md`` and CV9 item 1 in ``src/converter/TODO.md``.

EXPECTED
--------
- A batch of valid problems accounts exactly (inserted == inputs, failed == 0).
- A mixed batch accounts exactly too, with the good problems stored: the three
  cases below are ``xfail(strict=True)`` until isolation lands, so an accidental
  fix turns the suite red instead of passing silently.
"""

from pathlib import Path

import duckdb
import pytest

from converter.database.operations import DatabaseManager
from converter.utils.worker_functions import process_file_for_parallel

GOOD_SAMPLES: tuple[str, ...] = ("problems/tsp/att48.tsp", "problems/atsp/br17.atsp")
REFUSED_SAMPLE = "zips/all_problems/tour/alb1000.opt.tour"


def _payload(datasets_raw_dir: Path, relative_path: str, tmp_path: Path) -> dict[str, object]:
  """Run the real worker for one corpus file."""
  payload = process_file_for_parallel(str(datasets_raw_dir / relative_path), output_dir=str(tmp_path))
  assert payload.get("success") is True, f"worker rejected {relative_path}: {payload.get('error')}"
  return payload


@pytest.mark.requires_dataset
@pytest.mark.database
def test_valid_batch_accounts_exactly(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: two storable problems, nothing refused.

  WHY: the happy path must stay boring; if this ever changes, the accounting
  invariant below is meaningless.

  EXPECTED: inserted == 2, failed == 0, and two hub rows.
  """
  payloads = [_payload(datasets_raw_dir, relative, tmp_path) for relative in GOOD_SAMPLES]
  db_path = tmp_path / "valid.duckdb"
  result = DatabaseManager(db_path=str(db_path)).insert_problems_batch(payloads)

  assert result["total_inserted"] == 2
  assert result["total_failed"] == 0
  with duckdb.connect(str(db_path), read_only=True) as conn:
    assert conn.execute("SELECT COUNT(*) FROM problems").fetchone() == (2,)


@pytest.mark.requires_dataset
@pytest.mark.xfail(
  strict=True,
  reason="B3/CV9: one refused type rolls back the whole batch and every row is blamed with the same message.",
)
@pytest.mark.database
def test_batch_accounting_adds_up_with_a_refused_file(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: two storable problems plus one ``TOUR`` file.

  WHY: ``failed`` must name the file that actually failed, and the count must
  explain every input — otherwise a corpus run cannot be audited.

  EXPECTED: inserted == 2, failed == 1, and the failed entry names ``alb1000.opt.tour``.
  """
  payloads = [_payload(datasets_raw_dir, relative, tmp_path) for relative in GOOD_SAMPLES]
  payloads.append(_payload(datasets_raw_dir, REFUSED_SAMPLE, tmp_path))
  result = DatabaseManager(db_path=str(tmp_path / "mixed.duckdb")).insert_problems_batch(payloads)

  assert result["total_inserted"] == 2
  assert result["total_failed"] == 1
  assert "alb1000" in result["failed"][0]["name"]


@pytest.mark.requires_dataset
@pytest.mark.xfail(
  strict=True,
  reason="B3: the failed-type error is attributed to every row in the batch, not to the offending one.",
)
@pytest.mark.database
def test_refused_file_does_not_lose_its_siblings(datasets_raw_dir: Path, tmp_path: Path) -> None:
  """WHAT: the good problems of a mixed batch.

  WHY: this is the user-visible failure — a full corpus run stores nothing
  because 82 tour files are in it.

  EXPECTED: both storable problems present in the hub after the batch.
  """
  payloads = [_payload(datasets_raw_dir, relative, tmp_path) for relative in GOOD_SAMPLES]
  payloads.append(_payload(datasets_raw_dir, REFUSED_SAMPLE, tmp_path))
  db_path = tmp_path / "siblings.duckdb"
  DatabaseManager(db_path=str(db_path)).insert_problems_batch(payloads)

  with duckdb.connect(str(db_path), read_only=True) as conn:
    stored = {row[0] for row in conn.execute("SELECT name FROM problems").fetchall()}
  assert stored == {"att48", "br17"}


@pytest.mark.xfail(
  strict=True,
  reason="B3: operations.py:473 skips a payload without problem_data without logging or counting it.",
)
@pytest.mark.database
def test_payload_without_problem_data_is_counted(tmp_path: Path) -> None:
  """WHAT: a worker result that carries no ``problem_data``.

  WHY: ``operations.py:473`` ``continue``s past it, so it is neither inserted nor
  counted — a silently vanished problem.

  EXPECTED: reported as one failure, not as an empty successful run.
  """
  result = DatabaseManager(db_path=str(tmp_path / "empty_payload.duckdb")).insert_problems_batch(
    [{"success": True, "file_path": "synthetic/empty.vrp"}]
  )

  assert result["total_inserted"] == 0
  assert result["total_failed"] == 1
