# AGENTS.md — Agent & Contributor Guidelines for `routing_data`

Welcome to `routing_data`. This repository provides high-performance parsers and data converters for vehicle routing problems (TSPLIB95, CVRPLIB, and LKH-3 extended specifications).

These instructions define the mandatory development workflow, testing policies, and architectural standards for all AI coding agents and human contributors working on this codebase.

---

## 0. Working agreement

Applies to every task in this repository. Numbered `0` so the existing `§1`–`§7` cross-references stay valid.

1. **Plan before writes.** A change touching more than one file starts with a numbered plan: what, why in business terms, the observation that fails today, and the blast radius. No file is written until the plan is approved. Approval of the plan is not approval to batch every item. Extends §3.1 to every multi-file change, not only architectural ones.
2. **Bound the reads.** `grep_search` before `read_file`; read line ranges, not whole files; no unprompted whole-file read of files over ~400 lines, binaries, PDFs, or spilled `chat-session-resources/*.txt` tool output. Every read serves the current item.
3. **Announce skills.** The first line of a task names the skills loaded (or `skills: none`) and the step each one covers. If no skill matches, say so instead of proceeding silently.
4. **Executable anchors.** An explanation is incomplete without a runnable snippet, the exact `path:line`, and the expected output. A concept explained a third time becomes a knowledge-base note, not another chat answer.
5. **Verification that can fail.** A fix ships with the observation that fails without it — §3.11 defines the evidence standard.
6. **Session handoff.** At the end of a work item, write the `## Handoff` block into the active plan file: state, last verified observation, next item, open decisions, files to read first. Bridge sessions with the handoff, never with the transcript.
7. **File edits use built-in tools.** Create and edit files with `create_file`, `replace_string_in_file`, or `multi_replace_string_in_file` so every change is reviewable as a diff. The terminal is for exploration and commands, never for writing file contents.

---

## 1. Project Overview & Architecture

The repository serves four core objectives:

1. **Problem format conversion**: Convert third-party routing problem formats (Cordeau, Solomon, Homberger) into a parseable TSPLIB-extended format, with an API to access and generate them.
2. **Solution format conversion**: Convert third-party routing solution formats (`.opt.tour`, `.sol`, `.res`) into a parseable TSPLIB-extended solution format (`TYPE : TOUR`), with an API to access and generate them.
3. **Unified TSPLIB95 & TSPLIB-extended parsing**: Provide a parser (`src/tsplib_parser/`) that accepts core TSPLIB95 (`StandardProblem`) and extended keywords/sections (`ExtendedProblem`).
4. **Analytical storage transformation**: Transform parsed TSPLIB-extended problem and solution instances into normalized `json`, DuckDB (`db`), and `parquet` storage (`src/converter/`).

Key modules:

* **`src/tsplib_parser/`**: Fast, robust parser for TSPLIB95 and TSPLIB-extended problem files (`.tsp`, `.vrp`, `.sop`, `.atsp`, `.hcp`, `.tour`). Pure two-pass parsing architecture:
  - Pass 1: Tokenization and header metadata extraction.
  - Pass 2: Section field deserialization via registered `Field` subclasses.
* **`src/tsplib_parser/validation.py`**: Semantic validation layer (dimensions, coordinates, demands, matrix symmetry).
* **`src/tsplib_parser/types.py`**: Single source of truth for problem types, format definitions, section grammars, and fallback rules.
* **`src/converter/`**: Downstream transformation pipeline converting parsed TSPLIB structures into normalized formats and parquet/duckdb storage.
* **`datasets_raw/`**: Benchmark corpus (CVRPLIB, TSPLIB95) used for integration and contract verification.

---

## 2. Environment & Tooling Setup

* **Interpreter**: Run tests and scripts only through the project virtual environment (`.venv/bin/python -m pytest ...`). `pyproject.toml`'s `[tool.pytest.ini_options]` is the single pytest configuration. System python lacks `click`/`duckdb` and cannot even collect the suite (`tests/conftest.py` imports `click`).
* **Agent sandbox**: `.venv/bin/python` resolves to `~/.local/share/uv/...`. If a sandboxed command cannot see it, ask for permission or re-run only that single command outside the sandbox. Never fall back to system python, module mocks, or `PYTHONPATH` hacks.
* **Verify checks really ran**: a `cmd || echo fallback` that fires because the interpreter is missing is not evidence about the package.
* **CLI proxies (`rtk`)**: If `rtk` is available, prefix shell commands with `rtk`. If not in PATH, execute commands directly without failing.
* **shell scripting**: Use heredoc scripts (`python - <<'EOF'`) instead of escaped inline `python -c` one-liners; keep `find`/`grep` bounded to the repository.
* **Type checker**: `.venv/bin/python -m mypy src` (strict, configured in `pyproject.toml`). `mypy` is installed in `.venv` since 2026-10-23. The recorded baseline lives in [`TODO.md`](TODO.md) §"Verification baseline"; it may only go down.
* **Dependency groups**: tools that only run in development (`mypy`, `pytest`, `ruff`) belong to the `dev` group (`uv add --dev <tool>`), never to runtime `dependencies`. A plain `uv add` puts them in the main group — that already happened three times (`pyproject.toml`, findings **T6**/**m20**).

> [!NOTE]
> **Pending observation:** `[tool.pytest.ini_options]` has `pythonpath = src`. The `.venv` editable install already puts `src/` on `sys.path`, so this line is redundant there. It was added as a sandbox workaround and is kept for now; remove it later once confirmed unnecessary.

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
10. **Decision Requests**:
    - A decision is answerable only when the request carries: the problem in one sentence with `path:line` evidence, atomic options (never "X or Y" inside a single option), pros and cons per option, one worked example, and a recommendation with its reason.
    - Define the facts a question depends on before asking it. A question about behaviour that has not been described yet cannot be answered.
11. **Claimed Fixes**: A fix ships with the observation that fails without it. "Tests pass" is not evidence when the test passed before the change.

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
   - Shared constants, type aliases, problem type sets (`VALID_PROBLEM_TYPES`, `EXTENDED_PROBLEM_TYPES`), and matrix fallback rules (`NO_DIAG_FORMAT_FALLBACK`) must be defined exclusively in `src/tsplib_parser/types.py`.
3. **Polymorphic Format Extension**:
   - Keep `StandardProblem` clean and faithful to TSPLIB95.
   - Model extended specifications (e.g. `CVRPTW`, `TSPTW`, `PDPTW`, `MDVRP`, `MTSP`) via dedicated subclasses (`ExtendedProblem`) with registered fields, avoiding ad-hoc regex stripping or polluting the base model.
4. **Clean In-Memory Stream Processing**:
   - Parsers must avoid disk-backed temporary files (`tempfile.NamedTemporaryFile`). Ingest text from strings or file streams directly to preserve determinism and eliminate I/O side effects.
5. **Typed Contracts at Every Boundary**:
   - Every value crossing a package, module or process boundary has a **named** type: a `TypedDict`, a `dataclass` or a `Protocol`. Never a `dict[str, Any]` the caller has to interpret.
   - Never let one dict carry two shapes discriminated by a `"success"` key. Model it as a union of two named types (`WorkerSuccess | WorkerFailure`).
   - A producer's return type is the consumer's input type: when a producer's contract changes, the consumer annotations change **in the same step**.
6. **No Unparameterized Generics, No Implicit `Any`**:
   - `Callable[[str], T]`, `dict[str, X]`, `Queue[Event]` — never a bare `Callable`, never a bare `dict`.
   - Annotate instance attributes (`self.x: T`). A value that is `None` until a later call is `T | None`, never inferred-as-`None`-then-assigned.
   - `Any` is legal only where a third-party library forces it (e.g. `tsplib95` transformers, `getattr` on a foreign object). It must be narrowed (`isinstance`, `TypeGuard`, `cast`) before it reaches our own structures.
   - A `cast` requires a comment naming the invariant that makes it true (`EdgeDataField` in `fields.py` is the model).
   - Type-only imports live under `if TYPE_CHECKING:` (ruff `TCH`).
7. **Typing Is a Gate, Not a Style**:
   - `mypy src` must stay at or below the recorded baseline. A change that adds errors is **not done**, even when tests pass.
   - The per-module debt table is the **typing register** (T1–T7) in [`TODO.md`](TODO.md); update the register in the same step that changes the number.
   - Editor diagnostics count as evidence: a touched file must gain none, and pyright-strict-only items are tracked (T7) rather than dismissed as "pre-existing".
8. **Validation Must Be Executable**:
   - A validation that cannot fail is not validation: no no-op hooks, no `validate` command that only prints statistics, no check that merely logs.
   - Validation owns semantic invariants; parsers own grammar (§5.1). A producer never silently "fixes up" data to satisfy the validator.
   - Every fixed defect gets a regression test that fails without the fix. When the defect has a register ID (PB*/M*/B*/T*), name that ID in the test docstring.

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
| **6. Type & Contract Safety** | Do the annotations describe the real payload, and does the checker agree? | Unparameterized generics, `Any` escaping a boundary, `cast` without a justifying invariant, producer/consumer type drift, untyped dict bags standing in for a contract. |

---

## 7. Documentation Protocol

The full rule set is [`documentation.instructions.md`](.github/instructions/documentation.instructions.md). Non-negotiables:

* **Authority**: the [TSPLIB95 spec](docs/reference/tsplib95_format.md) governs keywords, sections, field types and distances. LKH-3 is an inspiration, never an authority, and project vocabulary is never labelled "LKH-3".
* **Links**: inline only, and every `§x.y` reference is a link to its heading anchor. A bare `§` or a reference-style label is a review blocker.
* **Registers**: one `id | severity | claim | evidence | next action` shape, one ID namespace per file. A resolved entry is rewritten in place, never appended after the old one.
* **Corpus**: [`datasets_raw/`](datasets_raw) is an input. Library code, docstring examples and config defaults name no corpus path.
