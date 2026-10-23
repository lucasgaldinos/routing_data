from pathlib import Path

cli = Path("tests/converter/test_integration_cli_commands.py")
text = cli.read_text()
blocks = [
'''@pytest.fixture
def cli_runner() -> CliRunner:
  """
  WHAT: Create Click CLI runner
  WHY: Need runner to test CLI commands
  EXPECTED: CliRunner instance
  DATA: Click's test runner
  """
  return CliRunner()


''',
'''@pytest.fixture
def test_data_dir() -> str:
  """
  WHAT: Use actual test data directory
  WHY: Need real TSPLIB files for testing
  EXPECTED: Path to test data
  DATA: datasets_raw/problems/tsp/gr17.tsp
  """
  base_path = Path(__file__).parent.parent.parent
  return str(base_path / "datasets_raw" / "problems" / "tsp")


''',
'''@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
  """
  WHAT: Create temp directory for CLI outputs
  WHY: Need isolated output location
  EXPECTED: Temp directory with cleanup
  DATA: Temporary directory
  """
  tmpdir = tempfile.mkdtemp(prefix="cli_test_")
  yield tmpdir
  shutil.rmtree(tmpdir)


''',
'''@pytest.fixture
def temp_input_with_file(test_data_dir: str) -> Generator[str, None, None]:
  """
  WHAT: Create temp input directory with gr17.tsp
  WHY: Need controlled input for CLI testing
  EXPECTED: Temp dir with single test file
  DATA: Copy of gr17.tsp
  """
  tmpdir = tempfile.mkdtemp(prefix="cli_input_")

  # Copy gr17.tsp to temp directory
  source_file = Path(test_data_dir) / "gr17.tsp"
  dest_file = Path(tmpdir) / "gr17.tsp"
  shutil.copy(source_file, dest_file)

  yield tmpdir
  shutil.rmtree(tmpdir)
''',
]
for block in blocks:
    if block not in text:
        raise SystemExit(f"block not found:\n{block[:60]}")
    text = text.replace(block, "", 1)

text = text.replace(
    "from collections.abc import Generator\n",
    "",
).replace("import tempfile\n", "")
text = text.replace(
    "from click.testing import CliRunner\n\nfrom converter.cli.commands import cli\n",
    "from click.testing import CliRunner\n\nfrom converter.cli.commands import cli\n",
)
replacement = '''@pytest.fixture
def temp_input_with_file(tsp_dir: Path, tmp_path: Path) -> str:
  """Create a temporary input directory containing a copy of gr17.tsp."""
  input_dir: Path = tmp_path / "input"
  input_dir.mkdir()
  shutil.copy(tsp_dir / "gr17.tsp", input_dir / "gr17.tsp")
  return str(input_dir)
'''
anchor = "class TestCLIBasic:"
text = text.replace(anchor, replacement + "\n\n" + anchor, 1)
cli.write_text(text)

inspect = Path("tests/converter/test_integration_cli_inspect.py")
text = inspect.read_text()
runner = '''@pytest.fixture
def cli_runner() -> CliRunner:
  """
  WHAT: Create Click CLI runner
  WHY: Need runner to test CLI commands
  EXPECTED: CliRunner instance
  DATA: Click's test runner
  """
  return CliRunner()


'''
if runner not in text:
    raise SystemExit("inspect runner block not found")
inspect.write_text(text.replace(runner, "", 1))

for name in ("tests/tsplib_parser/test_unit_cordeau.py", "tests/tsplib_parser/test_integration_cordeau.py"):
    path = Path(name)
    text = path.read_text()
    block = '''@pytest.fixture
def cordeau_base_path() -> Path:
  """Base path for Cordeau MDVRP test files."""
  return Path("datasets_raw/umalaga/mdvrp/C-mdvrp")


'''
    if block not in text:
        raise SystemExit(f"cordeau block not found in {name}")
    text = text.replace(block, "", 1)
    text = text.replace("cordeau_base_path", "cordeau_mdvrp_dir")
    path.write_text(text)
