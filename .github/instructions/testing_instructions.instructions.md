---
applyto: "**/tests/**", "when generating tests", "when refactoring tests"
type: quality-standards
author: Lucas Galdino (derived from AI critique)
---


## 📜 Pytest Quality Standards & Rules

You MUST adhere to the following standards when generating, analyzing, or refactoring any test code. These rules are based on prior testing critiques to prevent past failures.

### 1. 🎯 Test Philosophy: Enforce Behavior, Don't Document Bugs

Your primary goal is to **enforce correct behavior**.

- **DO:** Write tests that **fail** when behavior is incorrect.
- **DO NOT:** Use `@pytest.mark.skip` with a comment explaining a bug.
- **DO NOT:** Write tests that "document" a bug and pass anyway (e.g., `test_parse_file_att48_att_distance` accepting `null` coordinates).

### 2. ✅ Validation: Test Values, Not Just Structure

- **DO:** Validate the *actual content* of results.
- **DO NOT:** Write tests that only check if a dictionary key exists or if a list is not empty.
- **Good Example:**
    ```python
    # BAD: Checks structure only
    assert "dimension" in problem_data
    
    # GOOD: Checks structure AND value
    assert problem_data["dimension"] == 52
    ```

### 3. ⚙️ Fixtures: DRY (Don't Repeat Yourself)

- **DO:** Use shared fixtures from `conftest.py` (e.g., `temp_output_dir`, `in_memory_db`).
- **DO NOT:** Duplicate setup code (like creating temporary files) across multiple tests.
- **DO NOT:** Define local fixtures (e.g., `tmpdir`) that do the same job as an existing global fixture.

### 4. 📂 Organization & Naming

- **DO:** Maintain a clear separation:
  - Unit tests -> `tests/unit/`
  - Integration tests -> `tests/integration/`
- **DO NOT:** Mix unit tests (like matrix indexing) and integration tests (like full parsers) in the same file.
- **DO NOT:** Create empty test files (like `test_parser_basic.py`). Delete them.

### 5. 🚫 Banned Patterns

- **NO `print()` STATEMENTS:** Use `assert` statements for validation or the `logging` module for debugging output.
- **NO HARDCODED PATHS:**
  - **BAD:** `Path("datasets_raw/problems/tsp/gr17.tsp")`
  - **GOOD:** Use a fixture that provides the path to a test dataset.
- **USE `pathlib.Path`:** Prefer `pathlib` objects over string-based paths.

### 6. ⚠️ Error & Exception Testing

- **DO:** Use `pytest.raises` to check both the **type** and the **message content** of an exception.
- **Good Example:**
    ```python
    # BAD: Only checks type
    with pytest.raises(ValueError):
        my_function("bad-input")
        
    # GOOD: Checks type AND message
    with pytest.raises(ValueError, match="Invalid input format"):
        my_function("bad-input")
    ```

### 🔁 Test Generation Workflow

Regarding your question about diagrams, an ASCII flowchart is highly effective here to define the *process* I must follow. I will use this workflow when you ask me to generate new tests.

```ascii
          [START: User requests tests for "module_x.py"]
                       |
                       V
[1. THINK]  #sequentialthinking
            - Identify testable functions/classes.
            - Brainstorm test cases:
              - Happy Path (valid inputs)
              - Edge Cases (empty, null, zero, large)
              - Error Cases (invalid inputs)
                       |
                       V
[2. CHECK]  - Review "testing_standards.instructions.md" (THIS FILE)
            - Check "conftest.py" for existing fixtures to reuse.
                       |
                       V
[3. CODE]   - Write the `pytest` code.
            - Apply all rules (fixtures, `pytest.raises`, value asserts).
            - Add clear WHAT/WHY/EXPECTED docstrings.
                       |
                       V
[4. CRITIC] #actor-critic-thinking
            - **Actor:** "I generated 5 tests for module_x.py."
            - **Critic:** "Did I follow the standards?
                        - [ ] Did I use `print()`? (No)
                        - [ ] Did I hardcode paths? (No)
                        - [ ] Did I test values, not just structure? (Yes)
                        - [ ] Did I reuse fixtures? (Yes)
                        - [ ] Did I cover the edge cases? (Yes)"
                       |
                       V
          [END: Present plan, code, and critique to user]
```
