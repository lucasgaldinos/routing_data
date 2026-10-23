---
title: TypeVars, PEP 695, and cast
description: >
  A guided explanation of python's two generic-typing systems — the legacy TypeVar/Generic pair and the PEP 695 inline syntax — and of cast(), the escape hatch both still need. Part of the python-logic series; the worked examples come from the tsplib_parser transformers.
created: 2026-10-08
type: guide
scope: global
status: draft
author:
  - Lucas Galdino
  - GitHub Copilot
modifications:
  - date_modified: 2026-10-08
    modifications:
      - description: >
          First version. Written from the reader exchange around the PEP 695 conversion of FuncT in models.py: the two systems side by side, who creates the type parameter in each, the scoping difference, the runtime fingerprints, and why the identity default forced a cast().
related_files:
  - "[PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)"
  - "[models.py](../../../../src/tsplib_parser/models.py)"
  - "[descriptors-fields.md](./descriptors-fields.md)"
  - "[cpp-comparison.md](../../../src/tsplib_parser/cpp-comparison.md)"
  - "[README.md](./../README.md)"
tags:
  - guide/python-typing
  - guide/generics
  - guide/pep695
  - guide/typevar
  - guide/cast
  - guide/tsplib-parser
  - guide/learning-path
---

# TypeVars, PEP 695, and cast

- [What this file answers](#what-this-file-answers)
- [The same class, two systems](#the-same-class-two-systems)
- [Who creates the type parameter and where it lives](#who-creates-the-type-parameter-and-where-it-lives)
- [Reading the conversion](#reading-the-conversion)
- [The identity default no TypeVar can express](#the-identity-default-no-typevar-can-express)
- [cast, an assertion aimed at the checker](#cast-an-assertion-aimed-at-the-checker)
- [Choosing a system in this repo](#choosing-a-system-in-this-repo)
- [Connections](#connections)

## What this file answers

Five questions that came out of reading the transformer classes in [`models.py`](../../../../src/tsplib_parser/models.py):

- What are the two ways to spell a generic class in python, and what exactly changed in python 3.12?
- Where did `T = TypeVar("T")` go, and who creates the type parameter now?
- Why did the reach of `T` shrink from "usable anywhere in the module" to "alive only inside one class body"?
- Why does the identity default in `FuncT` need `cast()`, when the type parameter itself was just modernized?
- Does `cast()` belong to the new system at all — and when is "lying to the checker" acceptable?

This file is the typing primer for the series. [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD) covers the parser's behaviour, not its typing systems, so the two renderings of a generic are explained here — with the `FuncT` family as the running example.

> [!note]
> Claims in this file were verified against [`models.py`](../../../../src/tsplib_parser/models.py) and by running every demo shown, on the project interpreter (3.12+). The older shape of `FuncT` appears only as the "before" rendering of the same idea.

## The same class, two systems

A generic class is a class with type knobs. What changes between the systems is not the knobs — it is who creates the knob object and where its name lives.

The legacy rendering (python < 3.12, and still valid today) creates the knob by hand, as a module-level value:

```python
from typing import Callable, Generic, TypeVar

T = TypeVar("T")                    # the knob: created by you, on its own line

class Transformer(Generic[T]):      # the class subscribes to the knob
  def parse(self, text: str) -> T: ...

class FuncT(Transformer[T]):        # reuse the SAME knob in the parent slot
  def __init__(self, *, func: Callable[[str], T] | None = None) -> None: ...
```

The [PEP 695](https://peps.python.org/pep-0695/) rendering declares the knob inline, and the compiler creates it:

```python src/tsplib_parser/models.py#L115-L133
class Transformer[T]:
  """Base transformer class for parsing text into structured data."""

  def parse(self, text: str) -> T:
    """Parse text into a value."""
    raise NotImplementedError()

  def validate(self, value: T) -> None:
    """Validate a value."""
    pass


class FuncT[T](Transformer[T]):
  """Transformer that applies a function to parse text."""

  def __init__(self, *, func: Callable[[str], T] | None = None) -> None:
    # Default is a no-op pass-through, only sound when T is str; cast needed
    # because the identity lambda cannot be expressed as returning an arbitrary T.
    self.func: Callable[[str], T] = func or cast("Callable[[str], T]", lambda x: x)
```

One sentence is enough to hold the difference: **the legacy system makes you build the knob and pass it around by name; PEP 695 lets you write the declaration and never see the knob object at all.**

> [!tip]
> PEP 695 is syntax, not a library. It needs python 3.12 at import time — a file using it cannot even be parsed by 3.11. That is why the repo's metadata carries `requires-python = ">=3.12"` and ruff's `target-version = "py312"`: the typing style and the version floor moved together.

## Who creates the type parameter and where it lives

The table behind the whole file:

| Question | Legacy `TypeVar` + `Generic` | PEP 695 inline |
| --- | --- | --- |
| Who creates the knob? | you, explicitly | the compiler, implicitly |
| Where is it declared? | its own assignment, usually module level | inside the class/function/alias brackets |
| What is its scope? | the assigned name is a module variable — anything can use it | the class body only — invisible outside |
| Runtime fingerprint | `__parameters__` (set by `Generic.__class_getitem__`) | `__type_params__` (set by the compiler) |
| Default variance | invariant, unless `covariant=`/`contravariant=` given | inferred from usage (`infer_variance=True`) |
| Function shorthand | module TypeVar plus `def f(x: T) -> T` | `def f[T](x: T) -> T` |
| Type alias | `X = list[T]` | `type X[T] = list[T]` |

The row that caused real confusion in this codebase is **scope**. Under the legacy system, `T = TypeVar("T")` is an ordinary module-level name: every class in the file that writes `Transformer[T]` is reaching for the *same object*, and two classes can silently share a knob without anyone noticing. Under PEP 695, the `[T]` in `class FuncT[T]` creates a parameter owned by exactly that class body; the name `T` outside the brackets resolves to whatever the module says it means — and the earlier module-level `T` no longer exists.

That single difference explains a naming choice visible in the file: `ContainerT[T_Container]` could have called its knob `T` — the name is arbitrary — but then, in the mixed-era file, the class-local `T` and the module-level `T` would have been two different objects with the same spelling. A distinct name kept the two reachable knobs apart. With a single system, one class, one declaration, and the name collision is harmless.

## Reading the conversion

The conversion of `FuncT` is a two-line story, best seen with both states side by side.

Before — the class borrowed the module-level knob, written as a plain subscript on the parent:

```python
# models.py, before the conversion
T = TypeVar("T")  # Generic output type for transformers

class Transformer[T]:           # already PEP 695: declares its own T
  ...

class FuncT(Transformer[T]):    # this T is the line-115 TypeVar, NOT Transformer's
  def __init__(self, *, func: Callable[[str], T] | None = None) -> None:
    self.func: Callable[[str], T] = func or (lambda x: x)
```

After — the class declares its own knob in the header, exactly like `Transformer` and `ContainerT` already did:

```python src/tsplib_parser/models.py#L127-L130
class FuncT[T](Transformer[T]):
  """Transformer that applies a function to parse text."""

  def __init__(self, *, func: Callable[[str], T] | None = None) -> None:
```

The bracket walkthrough for `class FuncT[T](Transformer[T])`:

- the first `[T]` **declares** the class's type parameter — the part that did not exist in the old rendering;
- `Transformer[T]` **parameterizes** the parent with that same knob — the shorthand for the legacy base made explicit;
- the body then annotates with plain `T`, which now resolves to the class's own parameter, no module lookup involved.

The module-level assignment and the `TypeVar` import were deleted with it — the import line now reads `from typing import Any, cast` ([`models.py:43`](../../../../src/tsplib_parser/models.py#L43)). Nothing observable changed at runtime: annotations were never enforced, and both renderings produce a class whose `parse` returns whatever the knob says. Only the bookkeeping moved.

The runtime fingerprints are still there to inspect:

<details name="demos">
<summary><h5>Demo: the compiler's knobs are real objects (copy and run)</h5></summary>

```python
from typing import Generic, TypeVar

from tsplib_parser.models import ContainerT, FuncT, Transformer

for cls in (Transformer, FuncT, ContainerT):
  print(cls.__name__, [p.__name__ for p in cls.__type_params__])

print("same knob object?", Transformer.__type_params__[0] is FuncT.__type_params__[0])
print("FuncT parses     ->", FuncT(func=int).parse("7"))

TLegacy = TypeVar("TLegacy")

class LegacyBox(Generic[TLegacy]):
  pass

print("legacy knob      ->", [p.__name__ for p in LegacyBox.__parameters__])
```

```text
Transformer ['T']
FuncT ['T']
ContainerT ['T_Container']
same knob object? False
FuncT parses     -> 7
legacy knob      -> ['TLegacy']
```

</details>

Two things to notice in the output. `Transformer` and `FuncT` both call their knob `T`, and the identity check prints `False` — same name, different objects, each owned by its class body. And the legacy class answers with `__parameters__` where the PEP 695 classes answer with `__type_params__`: the checkpoint moved from the `Generic` machinery to the compiler, which is why the two systems can coexist in one file without either noticing the other.

## The identity default no TypeVar can express

The name `cast` enters the file on one line, and it is not a typing-system feature — it is a concession, because there is one local problem that neither `TypeVar` rendering can state honestly:

```python
self.func: Callable[[str], T] = func or cast("Callable[[str], T]", lambda x: x)
```

The declared contract is `Callable[[str], T]` — "give me text, I give you a `T`", for whatever single `T` the instance was parameterized with. The fallback is `lambda x: x`, which concretely returns a `str`. Strict mypy, correctly, refuses the assignment without help:

```text
Incompatible types in assignment (expression has type
  "Callable[[str], T] | Callable[[str], str]", variable has type
  "Callable[[str], T]")
Function return type "str" is incompatible with type "T@FuncT"
```

Read the error carefully, because it explains why no `TypeVar` can fix it. A `TypeVar` says *"one type, consistent everywhere it appears"*. The fallback lambda satisfies the contract `Callable[[str], T]` only for the single case `T = str` — for `T = int` it returns the wrong type. The default is a deliberate pass-through that is only sound for string transformers, which is exactly what the comment above the line records. This is not a regression of the PEP 695 conversion: the same line existed before it in legacy style, and strict mypy flags it under both systems, because inference limits and typing systems are independent things.

> [!important]
> A cast does not create the mismatch and cannot remove it — it flags it as reviewed. The line above now carries two pieces of evidence for a reader: the intended type in code (`cast("Callable[[str], T]", ...)`) and the rationale in a comment. Removing the cast without changing the default would bring the checker error back; removing the default (or allowing the no-arg form only for `FuncT[str]` via overloads) would remove the need for the cast. The project chose the documented exception.

## cast, an assertion aimed at the checker

`typing.cast(typ, value)` is the least magical tool in the typing toolbox: at runtime it returns `value` unchanged and ignores `typ` entirely ([docs](https://docs.python.org/3/library/typing.html#typing.cast)). Its whole job is the other audience — it tells mypy/pylance "assume this value has this type from here on", with no verification whatsoever.

<details name="demos">
<summary><h5>Demo: cast changes nothing at runtime (copy and run)</h5></summary>

```python
from typing import cast

raw = "seven"
as_integer = cast(int, raw)

print(as_integer is raw, type(as_integer).__name__)
print(as_integer + 1)
```

```text
True str
Traceback (most recent call last):
TypeError: can only concatenate str (not "int") to str
```

</details>

The first line is the one that matters: the object is untouched — same identity, still a `str`. The crash afterwards is the fine print of every cast: the checker now believes `as_integer + 1` is arithmetic, and nothing will contradict it — not at import, not at call, not ever. The string form used in `models.py`, `cast("Callable[[str], T]", ...)`, exists so the checker can resolve a type expression (including forward references) that the runtime would not even evaluate.

Both systems use this escape hatch, in the same way: legacy and PEP 695 differ on how knobs are declared and scoped, not on whether the checker can always prove what the programmer knows. Where that gap appears, the options in order of preference are:

- express the invariant in the annotations (best — no cast needed);
- `cast()` with the intended type named explicitly (a typed, greppable lie — the middleware of last resort);
- `# type: ignore` (silences the whole line, states no intent — the last resort).

A cast is acceptable when the invariant exists in the design but is inexpressible in the type system at that spot — and should always be paired with a comment, as the `FuncT` line is, so the next reader knows which side is right when the two disagree.

## Choosing a system in this repo

The decision table in practice:

- **New generic classes and functions** use PEP 695 (`Transformer[T]`, `FuncT[T](Transformer[T])`, `ContainerT[T_Container]`) — the repo is 3.12+, and ruff's `UP` rules prefer it.
- **Classes that are not generic themselves** are unchanged by the systems: `NumberT(Transformer[int | float])` and `ListT(ContainerT[list[Any]])` just hand a concrete type to the parent; there is no knob of their own to declare in either style.
- **Legacy spellings survive for things PEP 695 does not cover**: type-parameter defaults ([PEP 696](https://peps.python.org/pep-0696/)), variadic parameters ([PEP 646](https://peps.python.org/pep-0646/)), and explicit variance flags when inference guesses wrong.
- **One style per file.** `models.py` now contains zero manual `TypeVar` calls; the manual style only appears there as history. The two systems can coexist (they did for a while), but mixing is exactly what produced the "which `T` is this?" confusion this file just explained.

The C++ reader's translation table lives in [cpp-comparison.md](../../../src/tsplib_parser/cpp-comparison.md): PEP 695's inline brackets read like a template parameter list, and `cast` has no C++ counterpart because C++'s casts are runtime operations while this one is not — but that is the next file's story.

## Connections

### Links out

- [descriptors-fields.md](./descriptors-fields.md) — the field machinery whose `self.tf` attributes these transformer annotations describe.
- [cpp-comparison.md](../../../src/tsplib_parser/cpp-comparison.md) — the C++ template analogue of both type-knob systems.
- [models.py](../../../../src/tsplib_parser/models.py) — the file this guide's examples are read from.
- [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD) — the question index behind the series; it covers parser behaviour, not typing.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [descriptors-fields.md](./descriptors-fields.md) — the typing systems behind the transformer annotations its field story reads.
- [README.md](./../README.md) — the series index that files this guide under theoretical/.
