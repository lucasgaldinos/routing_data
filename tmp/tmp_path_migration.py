import re
from pathlib import Path

# --- json writer: drop repeated tmpdir fixtures, use tmp_path -----------------
path = Path("tests/converter/test_unit_json_writer.py")
text = path.read_text()
text = re.sub(
    r"  @pytest\.fixture\n  def tmpdir\(self\)[^\n]*\n(?:.*\n)*?    shutil\.rmtree\(tmpdir\)\n\n",
    "",
    text,
)
text = re.sub(r"\btmpdir\b", "tmp_path", text)
text = text.replace("(self, tmp_path,", "(self, tmp_path: Path,")
text = text.replace("(self, tmp_path)", "(self, tmp_path: Path)")
path.write_text(text)

# --- database: drop tmpdir fixture, base db fixtures on tmp_path --------------
path = Path("tests/converter/test_unit_database.py")
text = path.read_text()
text = re.sub(
    r"  @pytest\.fixture\n  def tmpdir\(self\)[^\n]*\n(?:.*\n)*?    shutil\.rmtree\(tmpdir\)\n\n",
    "",
    text,
)
text = text.replace(
    "    tmpdir: str = tempfile.mkdtemp()\n    db_path: Path = Path(tmpdir) / \"test.duckdb\"",
    "    db_path: Path = tmp_path / \"test.duckdb\"",
)
text = re.sub(r"\n *shutil\.rmtree\(tmpdir\)", "", text)
text = re.sub(r"\btmpdir\b", "tmp_path", text)
# every fixture/function that now references tmp_path receives the builtin fixture
text = re.sub(r"def (db|db_with_data|test_[a-z_]+)\(self\)", r"def \1(self, tmp_path: Path)", text)
text = text.replace("def db(self) -> Generator", "def db(self, tmp_path: Path) -> Generator")
text = text.replace("def db_with_data(self) -> Generator", "def db_with_data(self, tmp_path: Path) -> Generator")
text = text.replace("tmp_path: str", "tmp_path: Path")
path.write_text(text)

# --- scanner: build fixtures on tmp_path -------------------------------------
path = Path("tests/converter/test_unit_scanner.py")
text = path.read_text()
old = '''@pytest.fixture
def temp_directory():
'''
new = '''@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
'''
if old not in text:
    raise SystemExit("scanner fixture not found")
text = text.replace(old, new, 1)
text = text.replace('  tmpdir = tempfile.mkdtemp(prefix="scanner_test_")\n', "  tmpdir: Path = tmp_path\n")
text = text.replace('  yield tmpdir\n', "  return tmpdir\n")
text = text.replace("    shutil.rmtree(tmpdir)\n", "")
text = text.replace("(Path(tmpdir) /", "(tmpdir /")
text = text.replace("subdir = Path(tmpdir) / \"subdir\"", "subdir = tmpdir / \"subdir\"")
path.write_text(text)
