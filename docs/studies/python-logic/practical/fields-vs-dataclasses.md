---
title: Fields versus dataclasses
description: >
  Why the schema lives on the class as Field objects instead of dataclass-style instance attributes: the two declaration styles compared, why the instance style breaks parse silently, the "schema on the class, data on the instance" rule with its two footguns, and the feature-by-feature dataclass comparison with a measured membership demo. Part of the python-logic series.
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
          First version. Extracted and rewrote §4.1 of PARSER-DETAILS.MD: the class-body versus __init__ declaration comparison, the silent-empty failure of the instance style, the one-line schema/data rule and its footguns, and the dataclass conflict table with the membership-test demo and the CordeauProblem counterexample.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Restructure pass: shortened section names, nested ### subsections (schema on the class, silent failure, membership test, where a dataclass is right), broke the [!important] admonition into prose with source line links, verified and quoted the 18-field / 17-transformer count, the models.py:659 membership test, and the CordeauProblem dataclass location, and re-ran the membership demo. Expanded the Cordeau paragraph with the construction-order contrast: Cordeau builds the record at the end in one constructor call (cordeau_parser.py:92), StandardProblem is built empty and filled by rules on the class.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Added "Why not one approach for both": what each style would lose if forced onto the other parser, and the decision rule (fields when the class must exist before the data; dataclass when the data exists before the object).
related_files:
  - [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.py](../../../../src/tsplib_parser/models.py)
  - [factory-pattern.md](./factory-pattern.md)
  - [attribute-lookup.md](./../theoretical/attribute-lookup.md)
  - [descriptors-fields.md](./../theoretical/descriptors-fields.md)
tags:
  - guide/descriptors
  - guide/dataclasses
  - guide/python-oop
  - guide/tsplib-parser
---

# Fields versus dataclasses

- [Fields versus dataclasses](#fields-versus-dataclasses)
  + [What this file answers](#what-this-file-answers)
  + [The two declaration styles](#the-two-declaration-styles)
  + [Why the instance style breaks parse silently](#why-the-instance-style-breaks-parse-silently)
    - [The schema must exist on the class](#the-schema-must-exist-on-the-class)
    - [The failure is silent](#the-failure-is-silent)
  + [The rule and its two footguns](#the-rule-and-its-two-footguns)
  + [Why this is not a dataclass](#why-this-is-not-a-dataclass)
    - [The membership test](#the-membership-test)
    - [Where a dataclass is the right tool](#where-a-dataclass-is-the-right-tool)
    - [Why not use the same approach for both](#why-not-use-the-same-approach-for-both)
  + [Connections](#connections)

## What this file answers

The schema of a problem class is written as class attributes, not as assignments inside `__init__`. And it is not a dataclass, even though the syntax looks adjacent. This file shows what each choice would change:

- the two declaration styles and what differs between them;
- why the instance style breaks `parse`, and why it breaks it silently;
- the one-line rule the design follows, and the two footguns under it;
- the feature-by-feature comparison with a dataclass, and the place in this repository where a dataclass is the right tool.

## The two declaration styles

The current style declares fields in the class body, where they become class attributes:

```python
class StandardProblem(Problem):
    name = StringField("NAME")
    dimension = IntegerField("DIMENSION")
```

The alternative moves the same expressions into the constructor:

```python
class StandardProblem(Problem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = StringField("NAME")
        self.dimension = IntegerField("DIMENSION")
```

Both are valid python, and they differ in when the field objects exist and who can see them:

| | Class attributes, current | `self.x = ...` in `__init__` |
| --- | --- | --- |
| Field objects created | once, at class definition | once per instance |
| `__set_name__` fills `field.name` | automatically | never fires |
| Keyword-to-field index with zero instances | built by `FileMeta` | impossible |
| Schema introspectable before parsing | via `cls.fields_by_keyword` | only by scanning an instance |
| Default for an unset field | via `cls.fields_by_name` | needs a second registry |
| Where the declaration is written | once, in the class body | twice: create, then register |

## Why the instance style breaks parse silently

### The schema must exist on the class

The parser reads the schema from the class, because the class is where the schema lives:

```python
problem = cls()                                                     # models.py:851, the write target
acc = _SectionAccumulator(problem, cls.fields_by_keyword, errors)    # models.py:853, the schema
```

The argument is `cls.fields_by_keyword`, never `problem.fields_by_keyword`. That is not because reading through an instance is wrong — `p.fields_by_keyword` resolves upward to the class and works fine, as [factory-pattern.md](./factory-pattern.md) shows. It is because the instance style cannot provide a map that exists at class-creation time. `FileMeta` collects class-body attributes only ([`models.py:607-621`](../../../../src/tsplib_parser/models.py#L607-L621)); with fields assigned in `__init__`, the class body holds none, so the metaclass would build an empty index and the very first lookup would find nothing.

Rebuilding the index from a live object is possible in principle — construct a throwaway problem and scan its `vars()` for `Field` values — but every instance would then pay for the rebuild, and each instance would also pay for 18 field objects and 17 transformers (`StandardProblem` declares 18 fields; `ToursField` is a plain `Field`, the other 17 are `TransformerField` subclasses). The class-body style creates each of those objects exactly once.

### The failure is silent

The second cost of the instance style is that it fails without a sound. `__set_name__` fires only for class attributes, so with fields assigned in `__init__` the field's `name` stays `None`. The parser's guarded write would then quietly do nothing:

```python
if field.name:
    setattr(problem, field.name, parsed)      # models.py:872
```

A problem parsed under that design would come back empty rather than raising — the same silent-default class of bug discussed in [factory-pattern.md](./factory-pattern.md).

## The rule and its two footguns

The whole distinction fits in one line, and the parser shows both halves side by side ([`models.py:868-872`](../../../../src/tsplib_parser/models.py#L868-L872)):

```python
field = cls.fields_by_keyword[keyword]   # schema: class attribute, read-only
setattr(problem, field.name, parsed)     # data: instance attribute, per-object
```

**Schema on the class, data on the instance.**

Two footguns follow from that split, neither of which is live today:

- Shared mutable defaults. A literal mutable default would be one object shared by every problem ever constructed, because `default` lives on the field class; the codebase declares callables instead, and calls them on each lookup. The per-field table is in [descriptors-fields.md](./../theoretical/descriptors-fields.md).
- Shared transformers. One `self.tf` serves every instance of a problem, which is safe only while the transformer carries no mutable state; see [descriptors-fields.md](./../theoretical/descriptors-fields.md) for what `self.tf` builds and when.

## Why this is not a dataclass

The short version: a dataclass models a **record**, and this class models a **format**. `dimension = IntegerField("DIMENSION")` is not a defaulted value, it is a rule for reading text, and that rule has to stay one shared object on the class rather than becoming an attribute of every instance.

Taken one feature at a time, this is what a dataclass would bring and where each piece conflicts:

| Dataclass feature | What it gives | Why it does not fit |
| --- | --- | --- |
| `x: int = 0` becomes an instance attribute | every instance's `__dict__` starts full | destroys "unset", which `as_dict` depends on to decide what to emit |
| `default_factory` | a per-instance default value | the default must hang off the *field*, so `get_default_value()` can build a fresh one and `as_dict` can compare a value against it |
| generated `__init__` | values supplied at construction | the object is built **empty** by `cls()` and then filled by `parse`, line by line |
| generated `__repr__` / `__eq__` | value semantics | nothing in the package compares problems; the API is parse, validate, extract |
| no registry, no `__getattribute__` hook | — | `fields_by_name`, `fields_by_keyword` and the default lookup would all still have to be written by hand, and those are what `FileMeta` exists for |

### The membership test

The first row is the decisive one, and it is measurable. A dataclass instance always has every declared name in `__dict__`, and that membership test is exactly how `as_dict` decides whether a field counts as set ([`models.py:659`](../../../../src/tsplib_parser/models.py#L659)):

```python
if name in self.__dict__ or value != field.get_default_value():
```

<details name="demos">
<summary><h5>Demo: the membership test on both kinds of object (copy and run)</h5></summary>

```python
from dataclasses import dataclass, field as dc_field

from tsplib_parser.models import StandardProblem


@dataclass
class DataclassProblem:
  name: str = ""
  dimension: int = 0
  demands: list = dc_field(default_factory=list)


dp = DataclassProblem()
print("dataclass __dict__              ->", dp.__dict__)
print("'dimension' in __dict__         ->", "dimension" in dp.__dict__)
print("StandardProblem() __dict__      ->", StandardProblem().__dict__)
print("'dimension' in __dict__         ->", "dimension" in StandardProblem().__dict__)
print("StandardProblem().as_name_dict()->", StandardProblem().as_name_dict())
```

```text
dataclass __dict__              -> {'name': '', 'dimension': 0, 'demands': []}
'dimension' in __dict__         -> True
StandardProblem() __dict__      -> {}
'dimension' in __dict__         -> False
StandardProblem().as_name_dict()-> {}
```

The same three names are used on both sides so the comparison is direct. A dataclass-shaped object reports its fields as present; this design reports nothing until a parse has actually written a value.

</details>

So a dataclass shape would report its fields as present from the moment it exists, and the "unset versus default" distinction in that one-line test would be gone — the same distinction described in [attribute-lookup.md](./../theoretical/attribute-lookup.md).

### Where a dataclass is the right tool

The honest case for dataclasses, in this repository: where the object **is** the data, the repository already uses one. `CordeauProblem` ([`cordeau/cordeau_types.py:69-70`](../../../../src/tsplib_parser/cordeau/cordeau_types.py#L69-L70), the decorator and the class) is a plain `@dataclass`. It can be one because of a different construction order:

- `CordeauProblem` is built at the **end** of parsing, in a single constructor call ([`cordeau_parser.py:92`](../../../../src/tsplib_parser/cordeau/cordeau_parser.py#L92)). The parsing happens before that, outside the class: `_parse_header`, `_parse_depot_constraints` and `_parse_nodes` read the file and return plain values into the parser's local variables, and only when every value sits in a local is the object constructed. During parsing the class plays no part — nothing is written into a half-built instance, because no instance exists yet. Its attributes are plain values — `num_vehicles: int`, `nodes: list[CordeauNode]` — and `__post_init__` validates the finished record.
- `StandardProblem` is built **empty** at the start of parsing and filled line by line. Both styles have to parse the text; the difference is *who accumulates the parsed values while the parse runs*. Cordeau accumulates into the parser's local variables; `StandardProblem` accumulates into the instance itself — `setattr(problem, ...)` — so the instance must be born before the first value. Its class attributes are not values but rules — `IntegerField("DIMENSION")` — which must exist on the class before any instance so `FileMeta` can index them. Dataclass semantics would turn those rules into per-instance values and fill `__dict__` from birth, destroying the unset state that `as_dict` depends on.

Two shapes, two tools: a record is a dataclass, a schema is a field-backed class.

### Why not use the same approach for both

Each style pays off under different requirements, and each loses something if forced into the other:

- Forcing the field-backed schema onto Cordeau would drag in the whole machinery — `FileMeta`, descriptors, `__set_name__`, the two registries — to serve a fixed layout of three parts (header, depot constraints, nodes) and eight problem types. The machinery exists to answer questions Cordeau never asks: which keyword maps to which rule, what is unset, what does a subclass add.
- Forcing the record style onto StandardProblem is *possible but lossy*: read the text into plain local values, then construct once — the same two-phase shape the converter already uses after parsing. What it loses is everything the field layer provides: the incremental write target (`setattr(problem, ...)` needs the instance first), keyword-to-rule dispatch for a format where keywords vary by problem type and unknown ones must be tolerated, per-field defaults for `as_dict`, and subclass extension through `cls`. Those capabilities are exactly why the field framework was written at all.

Neither style is "better" in the abstract. The field-backed class is the heavier, general tool, worth its cost when the class is a **schema** — introspectable, extensible, filled while parsing. The dataclass is the lighter tool, right when the class is a **record** — built once, complete. A rule of thumb: reach for fields when the class must exist *before* the data does; reach for a dataclass when the data exists *before* the object does.

## Connections

### Links out

- [descriptors-fields.md](./../theoretical/descriptors-fields.md) — the field objects and their registries.
- [attribute-lookup.md](./../theoretical/attribute-lookup.md) — the unset-versus-default behaviour this design preserves.
- [factory-pattern.md](./factory-pattern.md) — the factory this design serves.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [classes-instances-cls.md](./../theoretical/classes-instances-cls.md) — "why the class-level field survives an instance-level write of the same name".
- [descriptors-fields.md](./../theoretical/descriptors-fields.md) — the `__set_name__` caveat for the instance-style design, and the footguns the split creates.
