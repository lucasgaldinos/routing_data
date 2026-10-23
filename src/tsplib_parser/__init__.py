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
from tsplib_parser import FormatParser

parser = FormatParser()
data = parser.parse_file("problem.vrp")
# Returns: {'problem_data': {...}, 'nodes': [...], 'tours': [...], 'matrix': ...}
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
from .models import (
  PROBLEM_REGISTRY,
  LKHProblem,
  StandardProblem,
  get_problem_class_for_type,
  register_problem_class,
)
from .parser import FormatParser
from .validation import (
  check_symmetry,
  identify_weight_source,
  validate_coordinates,
  validate_parse_result,
  validate_problem_data,
)

__version__ = "2.0.0"  # Updated for FormatParser refactoring
__author__ = "TCC Routing Data Project"

__all__: list[str] = [
  "PROBLEM_REGISTRY",
  "FormatError",
  "FormatParser",
  "LKHProblem",
  "ParseError",
  "StandardProblem",
  "ValidationError",
  "check_symmetry",
  "get_problem_class_for_type",
  "identify_weight_source",
  "register_problem_class",
  "validate_coordinates",
  "validate_parse_result",
  "validate_problem_data",
]
