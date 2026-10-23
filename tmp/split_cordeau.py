from pathlib import Path

path = Path("tests/tsplib_parser/test_unit_cordeau.py")
text = path.read_text()
marker = "class TestCordeauIntegration:"
idx = text.index(marker)
head = text[:idx].rstrip() + "\n"
integration_class = text[idx:]

old_imports = text[text.index("import json") : text.index("# Test files")]
new_imports = (
    "import logging\n"
    "from pathlib import Path\n\n"
    "import pytest\n\n"
    "from tsplib_parser.cordeau import CordeauConverter, CordeauParseError, CordeauParser\n"
    "from tsplib_parser.cordeau.cordeau_types import CordeauNode, CordeauProblem\n\n"
)
unit = head.replace(old_imports, new_imports)
format_parser_fixture = (
    '@pytest.fixture\n'
    'def format_parser() -> FormatParser:\n'
    '  """Create TSPLIB95 format parser instance."""\n'
    '  return FormatParser(logger=logging.getLogger(__name__))\n\n\n'
)
unit = unit.replace(format_parser_fixture, "")
path.write_text(unit)

fixtures_start = unit.index("@pytest.fixture\ndef cordeau_base_path")
fixtures_end = unit.index("class TestCordeauParser:")
fixtures = unit[fixtures_start:fixtures_end].rstrip() + "\n"

header = '''"""Integration tests for the Cordeau MDVRP adapter.

WHAT: Drive the Cordeau parse -> convert -> parse -> transform -> DB/JSON chain.
WHY: The adapter is only useful if the rest of the pipeline accepts its output.
EXPECTED: Converted problems parse, transform, persist, and serialize as v2 data.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from converter.api import merge_v2_payload
from converter.core.transformer import DataTransformer
from converter.database.operations import DatabaseManager
from converter.output.json_writer import JSONWriter
from tsplib_parser.cordeau import CordeauConverter, CordeauParser
from tsplib_parser.cordeau.cordeau_types import CordeauProblem
from tsplib_parser.parser import FormatParser

# Test files specified by user
TEST_FILES: list[str] = ["p01", "p03", "p08", "pr05", "p23"]

'''

Path("tests/tsplib_parser/test_integration_cordeau.py").write_text(
    header + "\n" + fixtures + "\n\n" + integration_class.rstrip() + "\n"
)
