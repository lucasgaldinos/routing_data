---
title: The parse factory pattern
description: >
  The factory design of StandardProblem.parse applied in practice: who instantiates the problem, what cls() creates, why the object is born inside parse instead of outside, the rejected mutating-instance alternative, and the full execution flow of one parse call with a recorded stack trace. Part of the python-logic series.
created: 2026-10-06
type: guide
scope: global
status: draft
author:
  - Lucas Galdino
  - GitHub Copilot
modifications:
  - date_modified: 2026-10-06
    modifications:
      - description: >
          First version. Extracted and rewrote §2.1, §2.4 and §2.5 of PARSER-DETAILS.MD as the practical companion to classes-instances-cls.md: the factory contract, the cls()-versus-metaclass table, the alternatives comparison, the mutating-instance design and why it loses, the three OOP facts primer, and the execution flow with a real recorded stack trace.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          De-duplication pass against classes-instances-cls.md: the pattern-in-one-line now links to the class/instance split explanation there, and the caller-instantiates section links to the lifecycle/evaluation-order explanation instead of restating it.
related_files:
  - [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.py](../../../../src/tsplib_parser/models.py)
  - [classes-instances-cls.md](./../theoretical/classes-instances-cls.md)
  - [metaclasses-new-mro.md](./../theoretical/metaclasses-new-mro.md)
tags:
  - guide/factory-pattern
  - guide/python-oop
  - guide/object-lifecycle
  - guide/tsplib-parser
  - guide/learning-path
---

# The parse factory pattern

- [The parse factory pattern](#the-parse-factory-pattern)
  + [What this file answers](#what-this-file-answers)
  + [The pattern in one line](#the-pattern-in-one-line)
  + [Whether the caller instantiates the problem](#whether-the-caller-instantiates-the-problem)
  + [What cls() creates, and what creates a class](#what-cls-creates-and-what-creates-a-class)
  + [Why parse is written as a factory](#why-parse-is-written-as-a-factory)
  + [Why the object is created inside parse rather than outside](#why-the-object-is-created-inside-parse-rather-than-outside)
  + [The three OOP facts this design leans on](#the-three-oop-facts-this-design-leans-on)
  + [Alternative design with a mutating instance method](#alternative-design-with-a-mutating-instance-method)
  + [Execution flow of one parse call](#execution-flow-of-one-parse-call)
    - [The stack trace at the moment a field is parsed](#the-stack-trace-at-the-moment-a-field-is-parsed)
  + [Connections](#connections)

## What this file answers

This is the practical side of the factory design: how `StandardProblem.parse` actually works, call by call. The explanation of `cls`, binding and instantiation lives in [classes-instances-cls.md](./../theoretical/classes-instances-cls.md); this file applies it:

- who creates the problem object — you, or the method;
- what `cls()` creates, and why that differs from creating a class;
- why the object is born *inside* `parse` rather than outside;
- why the alternative — a mutating instance method — was rejected;
- the full flow of one call, with a recorded stack trace.

> [!note]
> Claims verified against [`StandardProblem.parse`](../../../../src/tsplib_parser/models.py#L832-L920) and its production caller, [`parser.py:142`](../../../../src/tsplib_parser/parser.py#L142); the test suite also calls `parse` directly.
> Every demo was run and its output pasted.

## The pattern in one line

Schema read from the class, data written to the instance. `parse` reads `cls.fields_by_keyword` to decide what a keyword means, and writes every parsed value into the one instance it created at the top. The class/instance split behind that sentence — why the write lands in the instance `__dict__` and only shadows the class-level `Field` — is worked through in [classes-instances-cls.md](./../theoretical/classes-instances-cls.md).

## Whether the caller instantiates the problem

No. The call is made on the class, and the class method does the instantiating:

```python
problem = StandardProblem.parse(text)   # you call it on the CLASS
#         ^^^^^^^^^^^^^^^ no instance exists yet
#                 ^^^^^ this method creates one
```

Inside, the first statement is the instantiation ([`models.py:851`](../../../../src/tsplib_parser/models.py#L851)):

```python
problem = cls()
```

`parse` is a named alternate constructor, not a mutation of something the caller already holds — the step-by-step lifecycle, including the left-to-right reading of the assignment, is in [classes-instances-cls.md](./../theoretical/classes-instances-cls.md#what-changes-if-the-methods-were-bound-to-an-instance).

## What cls() creates, and what creates a class

`cls()` creates an **object**, not a class. The two acts differ in which object is being called:

| Expression | You are calling | You get |
| --- | --- | --- |
| `cls(...)` | a class | an instance of that class |
| `type(cls)(...)` or `FileMeta(...)` | a metaclass | a new class |

Inside `parse`, `cls` is already a finished class object, so `cls()` is the first row. The class was built earlier, by the metaclass, when the `class` statement ran at import. Calling `cls()` never runs `FileMeta.__new__` again — the metaclass has nothing to do with instantiation here.

The "on itself" part is the confusing bit, and it is a category error worth naming: a class is *not* an instance of itself. It is an instance of its metaclass.

<details name="demos">
<summary><h5>Demo: the class and the object are instances of different things (copy and run)</h5></summary>

```python
from tsplib_parser.models import StandardProblem

cls = StandardProblem
print("cls                     ->", cls)
print("type(cls)               ->", type(cls).__name__, "(the metaclass)")
print("isinstance(cls, type)   ->", isinstance(cls, type))
print("cls()                   ->", cls())
print("type(cls())             ->", type(cls()).__name__, "(a problem object)")
print("isinstance(cls(), type) ->", isinstance(cls(), type))
print("isinstance(cls(), cls)  ->", isinstance(cls(), cls))
```

```text
cls                     -> <class 'tsplib_parser.models.StandardProblem'>
type(cls)               -> FileMeta (the metaclass)
isinstance(cls, type)   -> True
cls()                   -> <tsplib_parser.models.StandardProblem object at 0x…>
type(cls())             -> StandardProblem (a problem object)
isinstance(cls(), type) -> False
isinstance(cls(), cls)  -> True
```

> [!tip]
> Read the last three lines together: the object `cls()` returns is an instance of `cls`, while `cls` itself is an instance of `FileMeta`. Nothing is ever an instance of itself.

</details>

## Why parse is written as a factory

Its contract is "text in, problem out", and something has to create the object. The accumulator — `_SectionAccumulator`, the helper that collects data-section lines and feeds the whole body to the matching field — needs a target to write into before the line loop starts, so creation is the first thing that must happen rather than a side effect of it. Written as a classmethod factory it also returns a fully-built object, keeps multi-step logic outI also would like if yuo inserted the explanation of `__init__`, and stays overridable per subclass through `cls`.

## Why the object is created inside parse rather than outside

Each alternative was considered and loses something:

| Alternative | Why it was not chosen |
| --- | --- |
| `StandardProblem(text)`, parsing inside `__init__` | `Problem.__init__(**kwargs)` currently means "set these attributes"; accepting a text argument would overload it ambiguously, and an exception inside `__init__` still leaves a half-built object reachable through `__new__` |
| `parse(problem, text)`, caller passes the target | the caller can pass an empty or reused object, which is the silently default-filled failure mode described in [the mutating-instance design](#alternative-design-with-a-mutating-instance-method) |
| a module-level `parse_tsplib(text)` | it works, and a stale docstring at [`exceptions.py:34`](../../../../src/tsplib_parser/exceptions.py#L34) suggests it once existed, but it loses `cls`, so no subclass polymorphism, and it splits the API across two entry points |

So `cls()` inside `parse` is the design, not an artifact of it.

One detail in the same signature: `parse(cls, text, **options)` accepts `**options` and never reads it. It exists only so `parse_file` — the file-level entry point on `FormatParser` — can pass `special=special_func` without a `TypeError`; what happens to that value is covered in [parser-pipeline.md](../../../src/tsplib_parser/parser-pipeline.md).

## The three OOP facts this design leans on

`cls()` is not special syntax. It is three ordinary facts of python object orientation stacked on top of each other. Run the demo, then map each fact onto the real code:

1. **A class is an object too.** `StandardProblem` is a value you can name and pass around, exactly like a string. When you call `StandardProblem.parse(...)`, python hands that object to the method as `cls` — no magic, just an argument.
2. **A class is a factory.** Calling the class object — `cls()` — is *asking the factory for one instance*. The class itself is not modified by the call; that is checked in [classes-instances-cls.md](./../theoretical/classes-instances-cls.md#whether-calling-the-class-changes-the-class-itself).
3. **Class attributes vs instance attributes.** `registered` below lives on the class and is shared by every instance; `name` lives on one instance only. In the real code, the registry `fields_by_keyword` is a class attribute, while parsed values like `dimension` are instance attributes.

<details name="demos">
<summary><h5>Demo: the three facts, runnable (copy and run)</h5></summary>

```python
# Fact 1: a class is an ordinary object — it can be stored in a variable
class StandardProblem:
  registered = 0                 # class attribute: lives on the CLASS object

  def __init__(self, name):      # instance attribute: lives on each built object
    self.name = name

  @classmethod
  def parse(cls, text):          # 'cls' is just the class object, passed in
    print("cls  ->", cls)
    print("same ->", cls is StandardProblem)
    StandardProblem.registered += 1     # class attribute, shared by everyone — this is the method body writing, not cls()
    return cls(text.split(":")[0])      # Fact 2: cls() = ask the factory for one

p = StandardProblem.parse("demo")
print("p.name          ->", p.name)
print("p.registered    ->", p.registered)
print("class registered->", StandardProblem.registered)
print("isinstance check->", isinstance(p, StandardProblem))

# bonus: even the factory is an object — its type is 'type'
print("type of the class object ->", type(StandardProblem).__name__)
```

```text
cls  -> <class '__main__.StandardProblem'>
same -> True
p.name          -> demo
p.registered    -> 1
class registered-> 1
isinstance check-> True
type of the class object -> type
```

</details>

Each fact is visible in `StandardProblem.parse` ([`models.py:851`](../../../../src/tsplib_parser/models.py#L851)):

| Primer fact | Where it appears in `parse` |
| --- | --- |
| a class is an object | `cls` is a parameter; `cls.fields_by_keyword` ([`:853`](../../../../src/tsplib_parser/models.py#L853)) reads from that object |
| a class is a factory | `problem = cls()` — the very first line of the method body ([`:851`](../../../../src/tsplib_parser/models.py#L851)) |
| class vs instance attributes | `fields_by_keyword` on the class; `setattr(problem, ...)` ([`:872`](../../../../src/tsplib_parser/models.py#L872)) writes onto the one instance |

## Alternative design with a mutating instance method

The proposed design is legal and readable:

```python
p = StandardProblem()                                       # empty object
acc = _SectionAccumulator(p, p.fields_by_keyword, errors)    # self-based lookup works
p.parse(text)                                                # fills itself in
```

`p.fields_by_keyword` works because attribute lookup falls through to the class. It still loses, on one codebase-specific point and several smaller ones:

| | Current design, `cls.parse(text)` | Mutating design, `p.parse(text)` |
| --- | --- | --- |
| Call site | one expression | two statements |
| Half-built object reachable | no | yes, and silently |
| If the caller forgets step two | not applicable | `p` looks fine and answers with defaults — `dimension` is `0`, `name` is `None` — with no error |
| State if parsing raises | nothing leaks; the exception fires before any return | a live, partially populated object stays in the caller's scope |
| Can `parse` return a different type | yes, factory freedom | no |
| Subclass-aware | automatic through `cls` | needs the correct instance to exist already |

The decisive row is the silent-default one, and it is specific to this pipeline: because `Problem.__getattribute__` returns field defaults for unset attributes, an empty `StandardProblem()` does not explode. It answers `dimension → 0` and `name → None` as if it were real, which downstream becomes garbage rows with no error raised anywhere. The factory makes that state unreachable.

Two smaller differences. `parse` aggregates every error and raises once at the end ([`models.py:918`](../../../../src/tsplib_parser/models.py#L918)) — a single `ParseError`, the module's aggregated exception, whose message joins every collected failure — so the mutating design would leave a live object that just failed validation, usable by any caller wrapping the call in `try`/`except`. And the mutating design requires the caller to know that a separate parse step exists at all, whereas with the factory the only sane way to obtain a problem is to obtain a correct one. See [attribute-lookup.md](./../theoretical/attribute-lookup.md) for the default-returning lookup that makes this matter.

## Execution flow of one parse call

Import-time work happens once and is covered in [metaclasses-new-mro.md](./../theoretical/metaclasses-new-mro.md); what follows is per call.

```text
StandardProblem.parse(text)                                   models.py:832
│  cls = StandardProblem                                       ← the class, not an object
│
├─ problem = cls()                                             models.py:851
│    └─ type.__call__ → object.__new__ → Problem.__init__(**{}) → no-op (no kwargs)
│       result: an empty instance; every field still at its default
│
├─ errors = []
├─ acc = _SectionAccumulator(problem, cls.fields_by_keyword, errors)   models.py:853
│
├─ loop over text.split("\n")                                  models.py:855
│   │
│   ├─ "NAME: demo"       (has ":" and no section open)
│   │    field = cls.fields_by_keyword["NAME"]                 ← read the class dict
│   │    parsed = field.parse("demo")                          ← instance method on the field
│   │    setattr(problem, "name", "demo")                      ← write the instance dict
│   │
│   ├─ "NODE_COORD_SECTION"   (ends with _SECTION)
│   │    acc.close()   → nothing open, no-op
│   │    acc.open("NODE_COORD_SECTION")
│   │
│   ├─ "1 0.0 0.0" ...    (data lines)
│   │    acc.add("1 0.0 0.0")
│   │
│   └─ "EOF"
│        acc.close()                              models.py:785 (def), 797 (field.parse)
│          field = fields_by_keyword["NODE_COORD_SECTION"]
│          parsed = field.parse("\n".join(lines))   ← the whole body is parsed at once
│          setattr(problem, "node_coords", parsed)
│
├─ acc.close()                                                 models.py:916  (trailing section)
├─ if errors: raise ParseError(...)                            models.py:918
└─ return problem                                              models.py:920
```

The split this diagram makes obvious is the whole design in one line: schema read from the class, data written to the instance.

### The stack trace at the moment a field is parsed

A monkeypatch of `TransformerField.parse` records the real stack without touching the source:

```bash
cd /home/lucas_galdino/chimera/routing_data
PYTHONPATH=src python3 - <<'py'
import traceback
from tsplib_parser import models

orig = models.TransformerField.parse
shown = False
def traced(self, text):
    global shown
    if not shown and self.keyword == "DIMENSION":
        shown = True
        print("=== STACK at the moment a field is parsed ===")
        traceback.print_stack()
        print()
    print(f"  [field.parse] keyword={self.keyword!r} text={text!r}")
    return orig(self, text)
models.TransformerField.parse = traced

text = "NAME: demo\nTYPE: TSP\nDIMENSION: 3\nEDGE_WEIGHT_TYPE: EUC_2D\nNODE_COORD_SECTION\n1 0.0 0.0\n2 1.0 0.0\n3 0.0 1.0\nEOF\n"
p = models.StandardProblem.parse(text)
print("as_name_dict:", p.as_name_dict())
print("instance __dict__:", sorted(p.__dict__))
py
```

```text
  [field.parse] keyword='NAME' text='demo'
  [field.parse] keyword='TYPE' text='TSP'
=== STACK at the moment a field is parsed ===
  File "<stdin>", line 18, in <module>
  File "/home/lucas_galdino/chimera/routing_data/src/tsplib_parser/models.py", line 870, in parse
    parsed_value: Any = field.parse(value)
  File "<stdin>", line 11, in traced

  [field.parse] keyword='DIMENSION' text='3'
  [field.parse] keyword='EDGE_WEIGHT_TYPE' text='EUC_2D'
  [field.parse] keyword='NODE_COORD_SECTION' text='1 0.0 0.0\n2 1.0 0.0\n3 0.0 1.0'
as_name_dict: {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3, 'edge_weight_type': 'EUC_2D', 'node_coords': {1: [0.0, 0.0], 2: [1.0, 0.0], 3: [0.0, 1.0]}}
instance __dict__: ['dimension', 'edge_weight_type', 'name', 'node_coords', 'problem_type']
```

The captured frame is the keyword path ([`models.py:870`](../../../../src/tsplib_parser/models.py#L870)): `StandardProblem.parse` → `field.parse(value)`. Section fields take the other branch — `_SectionAccumulator.close` ([`models.py:785`](../../../../src/tsplib_parser/models.py#L785)) calls `field.parse` on the whole collected body at once, which is why `NODE_COORD_SECTION` arrives as one multi-line text.

Two things that trace makes obvious: the `self` inside `TransformerField.parse` is a **field**, not a problem, and `setattr(problem, ...)` writes to the instance while the schema stays on the class. For the import-time half of the picture, see [descriptors-fields.md](./../theoretical/descriptors-fields.md) and [metaclasses-new-mro.md](./../theoretical/metaclasses-new-mro.md).

## Connections

### Links out

- [classes-instances-cls.md](./../theoretical/classes-instances-cls.md) — the theory this pattern stands on.
- [metaclasses-new-mro.md](./../theoretical/metaclasses-new-mro.md) — what happens when the class itself is created.
- [attribute-lookup.md](./../theoretical/attribute-lookup.md) — why the default-returning lookup makes the mutating design dangerous.
- [descriptors-fields.md](./../theoretical/descriptors-fields.md) — the field objects the flow diagram parses values with.
- [parser-pipeline.md](../../../src/tsplib_parser/parser-pipeline.md) — the parser that wraps this factory.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [classes-instances-cls.md](./../theoretical/classes-instances-cls.md) — "the factory pattern the whole design hangs on".
- [metaclasses-new-mro.md](./../theoretical/metaclasses-new-mro.md) — the per-call flow next to its class-creation story, and "a third pattern: a classmethod factory".
- [attribute-lookup.md](./../theoretical/attribute-lookup.md) — the mutating-instance danger its hook creates.
- [fields-vs-dataclasses.md](./fields-vs-dataclasses.md) — "the factory this design serves".
