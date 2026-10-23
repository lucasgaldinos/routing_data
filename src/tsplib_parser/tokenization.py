"""Tokenization and section stream splitting for TSPLIB95 and LKH-3 files.

This module splits raw file text into normalized keyword-value headers and
section bodies before any field deserialization begins.
"""


def _looks_like_keyword_header(line: str) -> bool:
  """Return True when ``line`` starts with an all-caps TSPLIB keyword + colon.

  Used to detect keyword lines that legally follow a data section without a
  ``*_SECTION`` boundary (e.g. ``FIXED_EDGES :`` in some HCP files). ADJ_LIST
  data lines like ``"5: 1 2"`` start with a numeric label and are not headers.
  """
  prefix: str = line.split(":", 1)[0].strip()
  return (
    bool(prefix) and any(c.isalpha() for c in prefix) and all(c.isupper() or c.isdigit() or c == "_" for c in prefix)
  )


def _fixed_inline_pairs(value: str, errors: list[str]) -> list[str]:
  """Split an inline ``FIXED_EDGES :`` value into ``'<from> <to>'`` pseudo-lines.

  The keyword value is a flat, ``-1``-terminated token stream of ``(from, to)``
  pairs; the pseudo-lines let it reuse the fixed-edge line parser.
  """
  tokens: list[str] = value.split()
  out: list[str] = []
  i: int = 0
  while i < len(tokens):
    if tokens[i] == "-1":
      i += 1
      break
    if i + 1 >= len(tokens):
      errors.append(f"FIXED_EDGES: dangling edge endpoint {tokens[i]!r} (missing '-1' terminator)")
      i += 1
      continue
    out.append(f"{tokens[i]} {tokens[i + 1]}")
    i += 2
  if i < len(tokens):
    errors.append(f"FIXED_EDGES: unexpected tokens after '-1': {tokens[i:]}")
  return out


def _split_tsplib_text(
  text: str,
  errors: list[str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
  """Split raw TSPLIB text into ``(raw_headers, raw_sections)`` in a single pass.

  Separating line splitting from field parsing ensures all header keywords
  (such as ``DIMENSION`` and ``EDGE_DATA_FORMAT``) are parsed before any
  ``*_SECTION`` body is evaluated, regardless of where the keywords appear in
  the file. Blank lines and ``#`` comments are skipped everywhere.
  """
  raw_headers: list[tuple[str, str]] = []
  raw_sections: list[tuple[str, str]] = []
  current_section: str | None = None
  current_lines: list[str] = []

  def _close_section() -> None:
    nonlocal current_section, current_lines
    if current_section is not None:
      raw_sections.append((current_section, "\n".join(current_lines)))
    current_section = None
    current_lines = []

  for line in text.split("\n"):
    line_stripped: str = line.strip()
    if not line_stripped or line_stripped.startswith("#"):
      continue

    if line_stripped.endswith("_SECTION") or line_stripped == "EOF":
      _close_section()
      if line_stripped != "EOF":
        current_section = line_stripped
    elif ":" in line_stripped and (current_section is None or _looks_like_keyword_header(line_stripped)):
      _close_section()
      header_keyword, header_value = (part.strip() for part in line_stripped.split(":", 1))
      if header_keyword == "FIXED_EDGES":
        current_section = "FIXED_EDGES_SECTION"
        current_lines = list(_fixed_inline_pairs(header_value, errors)) if header_value else []
        if header_value and header_value.split()[-1] == "-1":
          current_lines.append("-1")
          _close_section()
      else:
        raw_headers.append((header_keyword, header_value))
    elif current_section is not None:
      current_lines.append(line_stripped)

  _close_section()
  return raw_headers, raw_sections


__all__: list[str] = [
  "_fixed_inline_pairs",
  "_looks_like_keyword_header",
  "_split_tsplib_text",
]

