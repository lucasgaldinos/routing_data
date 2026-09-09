"""
TSPLIB95 Format Parsing Module

Unified parsing system for TSPLIB95 routing problem files.
Provides both high-level (FormatParser) and low-level (StandardProblem) APIs.

Architecture
------------
**Primary API** (Recommended):
    - parser.py: FormatParser class - High-level ETL parsing with validation

**Low-level API** (Internal/Advanced):
    - models.py: StandardProblem, Field system - Raw TSPLIB95 parsing
    - validation.py: Validation functions
    - matrix.py: Explicit edge-weight matrix reconstruction
    - cordeau/: Parser + converter for Cordeau MDVRP benchmark files

**Support Modules**:
    - exceptions.py: FormatError, ParseError, ValidationError hierarchy

Primary Usage (Recommended)
----------------------------
```python
from tsplib_parser.parser import FormatParser

parser = FormatParser(logger)
data = parser.parse_file("problem.vrp")
# Returns: {'problem_data': {...}, 'nodes': [...], 'tours': [...]}
```

Low-level Usage (Advanced)
--------------------------
Parsing directly to a ``StandardProblem`` model is supported for advanced
use (e.g. inspecting the field model). ETL pipelines should use
``FormatParser``.

```python
from tsplib_parser.models import StandardProblem

text = open("gr17.tsp", encoding="utf-8").read()
problem = StandardProblem.parse(text)
data_dict = problem.as_name_dict()
```

Version & Metadata
------------------
"""

from .exceptions import FormatError, ParseError, ValidationError
from .models import StandardProblem
from .validation import validate_coordinates, validate_problem_data

__version__ = "2.0.0"  # Updated for FormatParser refactoring
__author__ = "TCC Routing Data Project"

__all__: list[str] = [
  # ========================================================================
  # PRIMARY API (Recommended)
  # ========================================================================
  "FormatError",  # Base exception
  "ParseError",  # Parsing errors
  "StandardProblem",  # Core data structure
  "ValidationError",  # Validation errors
  # ========================================================================
  # VALIDATION (Public utilities)
  # ========================================================================
  "validate_coordinates",
  "validate_problem_data",
]

# Note: FormatParser is imported separately to avoid circular imports:
#   from tsplib_parser.parser import FormatParser
# This is the RECOMMENDED high-level API for ETL operations.
