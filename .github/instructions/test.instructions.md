---
applyTo: 'tests/**/*.py'
---
When writing new tests, ensure:

- [ ] **Comprehensive Coverage**: Test ALL elements, not samples
- [ ] **Value Validation**: Check actual values, not just structure
- [ ] **Boundary Testing**: Test at limits (min, max, boundaries)
- [ ] **Error Handling**: Test invalid inputs and edge cases
- [ ] **Clear Documentation**: WHAT/WHY/EXPECTED in docstring
- [ ] **Meaningful Assertions**: Assertions that actually validate properties
- [ ] **Multiple Test Cases**: Test with diverse inputs, not just one file
- [ ] **Informative Failures**: Error messages show what went wrong and why

**Anti-Patterns to Avoid**:

- ❌ Checking only a sample of data
- ❌ Only checking structure without values
- ❌ Documenting bugs instead of enforcing fixes
- ❌ Single test case for broad functionality
- ❌ Assertions without clear failure messages

Property-Based Testing: Hypothesis

```python
# Install
pip install hypothesis

# Example usage
from hypothesis import given, strategies as st

@given(st.integers(min_value=1, max_value=1000))
def test_property_holds_for_all_dimensions(dimension):
    """Test validates property for ALL generated dimensions."""
    result = function_under_test(dimension)
    assert invariant_holds(result)
```

Parametrized Testing: pytest.mark.parametrize

```python
@pytest.mark.parametrize("file,expected_dimension", [
    ('gr17.tsp', 17),
    ('berlin52.tsp', 52),
    ('att48.tsp', 48),
    ('kroA100.tsp', 100),
])
def test_multiple_files_with_expected_values(file, expected_dimension):
    """Test same property across multiple files."""
    result = parse_file(file)
    assert result['dimension'] == expected_dimension
```
