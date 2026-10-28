---
trigger: model_decision
description: "Authority order, link style, table budget, register shapes, naming and corpus-independence rules for specs, TODOs, READMEs and architecture notes. Apply when creating or editing any markdown file in this repository, and when a format or design claim is written down."
globs: "docs/**/*.md, **/TODO.md, **/README.md, AGENTS.md"
---

# Documentation standards

Rules derived from measured defects, not preference. Each rule names the
measurement that put it here.

## Authority

- **A1. The TSPLIB95 spec is the source of truth.** For a keyword, section, field type or distance function, cite `spec §x.y` from [TSPLIB95 spec](../../docs/reference/tsplib95_format.md).
  A claim without a spec section or a corpus measurement is not a claim.

- **A2. LKH-3 is an inspiration, never an authority.** LKH-3 defines a format for its own solver and cannot read multi-depot files ([LKH-3 reference](../../docs/reference/LKH-3-Keld-Helsgaun.md) lists `MDMTSP`, not `MDVRP`).
  When LKH-3 and the spec differ, the spec wins and the difference goes to the spec-versus-code table.

- **A3. Never call project vocabulary "LKH-3".** Use "extended".
  Banned outside an artifact LKH-3 can actually read: `lkh` as a variable, parameter or local name; `as_lkh`; `to_lkh`; `LKHProblem`.
  A name that says LKH-3 for a file LKH-3 rejects is a false statement in code.

## Scope of a specification

- **S1. A spec states what the format is, not why it was chosen.** Rationale and alternatives belong in [architecture decisions](../../docs/reference/ARCHITECTURE_DECISIONS.md); the spec keeps a one-line pointer.

- **S2. An out-of-scope item gets exactly one mention.** One line in the rejection list.
  No provenance row, no warning block, no second entry in another section.
  `DEPOTS` currently has four mentions and is rejected everywhere.

- **S3. Every example must be runnable and traceable.** A corpus path that exists or a named test fixture. No invented keyword may appear in an example.

- **S4. One fact, one place.** When two keywords encode the same number, the spec names the winner and derives the other.
  `DEPOTS : t` beside a `DEPOT_SECTION` of length `t` is the number twice.

- **S5. Prefer the existing keyword.** If the TSPLIB95 spec already defines a section that carries the information, use it instead of inventing a parallel one.
  A new keyword needs a spec gap, not a preference.

## Links

- **L1. Inline links only:** `[§10.4](#104-...)`, `[ADR D3](./ARCHITECTURE_DECISIONS.md#d3--...)`.
  Reference-style definitions are banned: four `[lkh3-spec]` uses shipped with zero definitions, so every one of them rendered as literal text.

- **L2. Every `§x.y` in prose is a link to that heading.** Measured 2026-10-26: 28 of 155 section references were linked.
  An unlinked `§` is a review blocker.

- **L3. Anchors are the GitHub slug of the heading.** Lowercase, spaces to `-`, punctuation dropped, duplicates suffixed.
  Open the link; do not guess.

- **L4. A cross-file citation names file and heading**, never a bare `D3` or `P2`.
  Three files currently use `D` for three different decision sets.

## Structure

- **T1. Tables only for enumerable facts:** at least three comparable rows sharing at least three columns of short values. Rules, invariants, decisions and arguments are prose or bullets.

- **T2. Delete a sentence that restates a table row.** Repetition is a defect, not thoroughness.

- **T3. A register entry is `id | severity | claim | evidence | next action`.** One shape in every register.
  A rewritten entry replaces the old one; it is never appended after it.

## Corpus independence

- **C1. `datasets_raw/**` is an input, not a dependency.** `src/tsplib_parser` names no corpus path, not even in a docstring example.
  Tests obtain paths from fixtures in [conftest.py](../../tests/conftest.py), never from string literals.

- **C2. No code encodes a corpus directory shape.** `parent.parent / "tour"` and `VRP-set-XXX` are this corpus's layout, not this project's contract.
  Solution lookup is by suffix beside the problem file or by explicit argument.

- **C3. A configuration default pointing into `datasets_raw` is a defect.** The input path is required configuration supplied by the caller.

## Claiming work

- **W1. A claimed fix ships with the observation that fails without it.** A test that passes before the fix proves nothing.
