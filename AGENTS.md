# AGENTS.md — Agent & Contributor Guidelines for `routing_data`

Welcome to `routing_data`. This repository provides high-performance parsers and data converters for vehicle routing problems (TSPLIB95, CVRPLIB, and LKH-3 extended specifications).

These instructions define the mandatory development workflow, testing policies, and architectural standards for all AI coding agents and human contributors working on this codebase.

---

## 1. Project Overview & Architecture

* **`src/tsplib_parser/`**: Fast, robust parser for TSPLIB95 and LKH-3 problem files (`.tsp`, `.vrp`, `.sop`, `.atsp`). Pure two-pass parsing architecture:
  - Pass 1: Tokenization and header metadata extraction.
  - Pass 2: Section field deserialization via registered `Field` subclasses.
* **`src/tsplib_parser/validation.py`**: Semantic validation layer (dimensions, coordinates, demands, matrix symmetry).
* **`src/tsplib_parser/types.py`**: Single source of truth for problem types, format definitions, and fallback rules.
* **`src/converter/`**: Downstream transformation pipeline converting parsed TSPLIB structures into normalized formats and parquet/duckdb storage.
* **`datasets_raw/`**: Benchmark corpus (CVRPLIB, TSPLIB95) used for integration and contract verification.

---

## 2. Environment & Tooling Setup

* **Interpreter**: Run tests and scripts only through the project virtual environment (`.venv/bin/python -m pytest ...`). `pytest.ini` is the single pytest configuration. System Python lacks `click`/`duckdb` and cannot even collect the suite (`tests/conftest.py` imports `click`).
* **Agent sandbox**: `.venv/bin/python` resolves to `~/.local/share/uv/...`. If a sandboxed command cannot see it, ask for permission or re-run only that single command outside the sandbox. Never fall back to system Python, module mocks, or `PYTHONPATH` hacks.
* **Verify checks really ran**: a `cmd || echo fallback` that fires because the interpreter is missing is not evidence about the package.
* **CLI proxies (`rtk`)**: If `rtk` is available, prefix shell commands with `rtk`. If not in PATH, execute commands directly without failing.
* **Shell scripting**: Use heredoc scripts (`python - <<'EOF'`) instead of escaped inline `python -c` one-liners; keep `find`/`grep` bounded to the repository.

> [!NOTE]
> **Pending observation:** `pytest.ini` has `pythonpath = src`. The `.venv` editable install already puts `src/` on `sys.path`, so this line is redundant there. It was added as a sandbox workaround and is kept for now; remove it later once confirmed unnecessary.

---

## 3. Collaboration & Process Invariants (Staff Engineer Pairing Protocol)

1. **Architectural Plan Gate** (for design decisions and non-trivial changes):
   - Present a plan containing **Problem Description** (root cause and impact), **Explanation** (technical mechanism), and **Suggestions with Pros & Cons** for each option.
   - Wait for Staff Engineer alignment before implementing the design.
2. **Decision Questions**:
   - Each option is atomic: never "X **or** Y" inside a single option.
   - Every option states its pros and cons; a recommendation states **why**.
   - Define jargon with a concrete example. When the Staff Engineer does not understand, re-explain with `file:line` evidence instead of repeating.
3. **Spec First**: Before proposing parser/format changes, read `docs/reference/tsplib95_format.md`, `docs/reference/LKH-3-Keld-Helsgaun.md`, and the upstream `tsplib95` / `pylkh` patterns. Cite sections (e.g. §1.1.7).
4. **Extension-Ready, Subtractive Design**:
   - Prefer root-cause fixes that delete branches and duplication over adding layers that hide the problem.
   - Avoid interim shapes that must be rewritten for planned extensions (Cordeau, CVRPLIB → LKH-3 specs).
   - Ask before hardcoding policy or adding attributes to a base class.
5. **Change Sizing**: Cap changes at **~100–200 lines** per step, with targeted verification after each step.
6. **Review After Implementation (within an approved scope)**:
   - While implementing an approved change, you may edit the module and the tests directly related to the changed function/behavior, then present the diff for review.
   - **Stop and ask** when changes start cascading: many files affected, unexpected failures outside the touched behavior, or areas that may already have planned changes (check the `TODO.md` files).
7. **Strict Scope Guard**: When working on a designated module (e.g. `src/tsplib_parser/`), do not touch downstream or unrelated modules (e.g. `src/converter/`, `tests/converter/`). Report out-of-scope failures as findings instead of patching them.
8. **Findings Register**: Report errors and findings as soon as they appear (what, where, why). Keep a running list of open findings and show what is still open at each step boundary.
9. **Dead Code & Test Deletion**: Never silently delete, disable, or comment out code or tests. List dead helpers or obsolete tests and ask before removal; remove confirmed dead code once approved.

---

## 4. Testing Discipline

**Source of truth:** [`tests/README.md`](tests/README.md) (layout, `test_<level>_<module>[_<concern>].py` naming, filename-derived level markers, orthogonal tags, parser file boundaries, command map) and [`.github/instructions/testing_instructions.instructions.md`](.github/instructions/testing_instructions.instructions.md). Read them before adding, moving, or retagging a test. Repository conventions override generic skills (e.g. never hand-write `unit`/`integration`/`e2e` markers; no parallel `tests/unit/` tree).

Agent-specific rules:

1. **Targeted tests during development**: Run the narrowest gate that covers the change: one file, `-k`, a package folder, or `-m "not slow and not requires_dataset"`. Do not run the full suite after every change or as a reflex before finishing, especially while other major changes are planned. A broader run is a deliberate, agreed checkpoint.

   ```bash
   .venv/bin/python -m pytest tests/tsplib_parser/test_unit_parser_contract.py -q
   .venv/bin/python -m pytest tests/tsplib_parser/test_unit_parser_validation.py -k "dimension" -q
   .venv/bin/python -m pytest tests/tsplib_parser -m "not slow and not requires_dataset" -q
   ```

2. **Test behavior, not instances**: Use synthetic in-memory fixtures that reproduce real-world quirks (e.g. omitted matrix diagonal, display-only coordinates). Real corpus files are allowed when the behavior under test *is* file parsing: tag them `requires_dataset` and use the `conftest.py` fixtures (no hardcoded `datasets_raw/**` paths).
3. **Order of work**: Change the source first, then update the related tests.
4. **README after changes**: After a code or test change (or a batch of them), update `tests/README.md` (tree, counts, `slow` timings) so it reflects the final state.

---

## 5. Architectural Standards

1. **Separation of Parsing and Validation**:
   - **Parsers (`src/tsplib_parser/parser.py`, `models.py`)**: Responsible strictly for grammar, syntax tokenization, and deserializing text into typed fields.
   - **Validation (`src/tsplib_parser/validation.py`)**: Responsible for semantic invariants (weight matrix symmetry, demand bounds `1..dimension`, coordinate dimension checks, node indexing).
   - Parsers must never execute semantic domain validation internally.
2. **Single Source of Truth**:
   - Shared constants, type aliases, problem type sets (`VALID_PROBLEM_TYPES`, `LKH_PROBLEM_TYPES`), and matrix fallback rules (`NO_DIAG_FORMAT_FALLBACK`) must be defined exclusively in `src/tsplib_parser/types.py`.
3. **Polymorphic Format Extension**:
   - Keep `StandardProblem` clean and faithful to TSPLIB95.
   - Model extended specifications (e.g. LKH-3 CVRPTW, TSPTW, PDPTW, mTSP) via dedicated subclasses (`LKHProblem`) with registered fields, avoiding ad-hoc regex stripping or polluting the base model.
4. **Clean In-Memory Stream Processing**:
   - Parsers must avoid disk-backed temporary files (`tempfile.NamedTemporaryFile`). Ingest text from strings or file streams directly to preserve determinism and eliminate I/O side effects.

---

## 6. The 5-Axis Code Review Gate

Before considering any refactoring phase complete, evaluate the changeset across the 5 axes from `code-review-and-quality`:

| Axis | Guiding Question | Presumptive Blockers |
| :--- | :--- | :--- |
| **1. Correctness** | Does the code do what it claims and pass targeted invariant tests? | Off-by-one errors, unhandled boundary cases, broken matrix diagonal logic. |
| **2. Readability** | Is control flow simple and immediately understandable? | >1000 lines per file without decomposition, nested conditional chains, clever tricks. |
| **3. Architecture** | Does it maintain clear boundaries and single responsibility? | Relocating complexity instead of eliminating it; feature logic leaking into shared modules. |
| **4. Security** | Are boundary inputs and file paths validated and safe? | Unsanitized external path traversal, arbitrary execution. |
| **5. Performance** | Are memory allocations and parsing passes minimal? | Repeated string scans, disk I/O for temporary transforms, unbounded memory copies. |
