---
title: Descriptors and the field system
description: >
  How Field objects act as descriptors: the keyword/options/default design, what self.tf builds, how FileMeta collects fields into two registries at class-creation time, why __set_name__ only fires for class attributes, and what the registries hold. Part of the python-logic series.
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
          First version. Extracted and rewrote §1.3, §3.5 and §4.2 of PARSER-DETAILS.MD: field options and defaults, the three self.tf demos, the wrong and right XRayProblem spellings, the import-time order of events, and the two registries.
related_files:
  - [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.py](../../../../src/tsplib_parser/models.py)
  - [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md)
  - [attribute-lookup.md](./attribute-lookup.md)
  - [metaclasses-new-mro.md](./metaclasses-new-mro.md)
tags:
  - guide/descriptors
  - guide/python-oop
  - guide/field-system
  - guide/import-time
  - guide/tsplib-parser
---

# Descriptors and the field system

## What this file answers

The schema of a `StandardProblem` is not a list of strings — it is a set of field *objects* that exist from import time. This file covers:

- what a `Field` object holds (keyword, options, default) and what `.tf` is;
- how `FileMeta` collects fields into the two registries while the class is being created;
- why `__set_name__` fills in the attribute name only for class attributes;
- what exactly the two registries hold and who reads them.

The metaclass mechanics themselves — `__new__`, `mcs`, the reversed-MRO loop — are in [metaclasses-new-mro.md](./metaclasses-new-mro.md). This file is about the objects that flow through them.

## The Field object: keyword, options, default

A field declaration such as `name = StringField("NAME")` evaluates a transformer-backed field object in the class body. Its constructor stores the keyword and then any extra options:

```python
def __init__(self, keyword: str, **options: Any) -> None:
    self.keyword = keyword
    self.name = None
    for key, value in options.items():
        setattr(self, key, value)
```

`**options` exists so a field declaration can carry its own configuration without every field class needing a bespoke signature. The declaration `IndexedCoordinatesField("NODE_COORD_SECTION", dimensions=(2, 3))` therefore ends with `self.dimensions == (2, 3)`, which its `validate()` later reads to reject a coordinate of the wrong arity. Two details to know about the pattern: `**options` are applied **after** `keyword` and `name`, so an option called `name` would overwrite the attribute name; and fields that take no options, such as `StringField`, simply leave the loop empty. This loop is also the reason an option can shadow a classmethod — the fact the `self.tf` demos below turn into a lesson.

`default` is a separate class attribute on `Field`, `None` unless a subclass overrides it, and it is the value an unset field answers with:

| Field class | `default` | Why |
| --- | --- | --- |
| `Field` | `None` | sensible "unset" for a plain value |
| `IntegerField` | `0` | arithmetic downstream does not need a null check |
| `IndexedCoordinatesField`, `DemandsField` | `dict`, a callable | a mutable default must be built per lookup, not shared |
| `DepotsField`, `MatrixField` | `list`, a callable | same reason, for lists |

`get_default_value()` calls the value when it is callable, which is what stops every instance from sharing one dictionary. How that value reaches the caller is covered in [attribute-lookup.md](./attribute-lookup.md).

## What self.tf does, and why the lookup is explicit

`self.tf = self.__class__.build_transformer()` reads a classmethod on the field's own class and stores the object it returns on the field instance. It does not set anything on the class — `build_transformer` is already there.

- `self.__class__` is the concrete field class (`IntegerField`, `IndexedCoordinatesField`, ...), so a subclass of a field gets its own transformer instead of the parent's.
- `build_transformer` is declared on `TransformerField`, where it raises `NotImplementedError`; every concrete field overrides it. `IntegerField` returns `FuncT(func=int)`, while `IndexedCoordinatesField` returns a map transformer that splits on newlines.
- The call happens per field object, not per problem: the class body creates exactly one field object per declaration, so `self.tf` is built once at class-definition time and then shared by every problem instance.

For a normal field the two spellings — `self.build_transformer()` and `self.__class__.build_transformer()` — are the same call. `build_transformer` is a classmethod, so reaching it through an instance binds it to the **class**, not to the instance:

<details name="demos">
<summary><h5>Demo: both spellings resolve to the same classmethod (copy and run)</h5></summary>

```python
from tsplib_parser.models import IntegerField

f = IntegerField("DIMENSION")
print(f.build_transformer())
print(f.__class__.build_transformer())
print("same type       ->", type(f.build_transformer()) is type(f.__class__.build_transformer()))
print("bound to class  ->", f.build_transformer.__self__ is IntegerField)
```

```text
<tsplib_parser.models.FuncT object at 0x…>
<tsplib_parser.models.FuncT object at 0x…>
same type       -> True
bound to class  -> True
```

The two objects are built at different call moments, so they are equal in type and not identical in address. `__self__` is `IntegerField` in both cases, which is the whole point: the instance `f` is not involved.

</details>

There is one case where the spellings differ, and it is not a case this codebase has: an *instance* attribute of the same name shadows the classmethod, because `Field.__init__` writes every option it is given with `setattr(self, key, value)`.

<details name="demos">
<summary><h5>Demo: an option named like the classmethod shadows it (copy and run)</h5></summary>

```python
from tsplib_parser.models import IntegerField

f = IntegerField("X", build_transformer=1)   # the option is stored as an instance attribute
print("instance attr    ->", f.build_transformer, "| callable:", callable(f.build_transformer))
print("class lookup     ->", f.__class__.build_transformer)
```

```text
instance attr    -> 1 | callable: False
class lookup     -> <bound method IntegerField.build_transformer of <class 'tsplib_parser.models.IntegerField'>>
```

The order inside the constructor is what makes this interesting: `super().__init__(*args, **kwargs)` stores the options **first**, and only then does the last line read `self.__class__.build_transformer()`. So by the time the transformer is built, the shadowing attribute is already there — and the explicit form survives it while the short one does not:

<details name="demos">
<summary><h5>Demo: the shadowing attribute breaks the short spelling only (copy and run)</h5></summary>

```python
from tsplib_parser.models import Field, IntegerField, TransformerField


class NaiveLookup(TransformerField):
  """Same intent as TransformerField, but reaching the classmethod through self."""

  def __init__(self, *args, **kwargs):
    Field.__init__(self, *args, **kwargs)     # the option loop only
    self.tf = self.build_transformer()        # the naive spelling


try:
  NaiveLookup("Z", build_transformer=1)
except TypeError as e:
  print("naive    ->", type(e).__name__ + ":", e)

ok = IntegerField("Z", build_transformer=1)
print("explicit -> built fine, tf =", type(ok.tf).__name__)
```

```text
naive    -> TypeError: 'int' object is not callable
explicit -> built fine, tf = FuncT
```

</details>

That is the difference, and it is why the explicit spelling earns its keep rather than being decoration: it always reads the **class-level** rule, even when an option name collides with it. `NaiveLookup` is not in the package; it exists only to make the failure observable.

</details>

Where the transformer sits in the wider design, and why the extension point is the field class rather than the problem class, is in [models.md](../../../src/tsplib_parser/models.md).

## How FileMeta builds the two dictionaries

`FileMeta.__new__` ([`models.py:607`](../../../../src/tsplib_parser/models.py#L607)) runs while the class is being created, before any instance exists. It walks `reversed(cls.__mro__)`, collects every attribute that is a `Field`, and stores two dictionaries on the class: `fields_by_name` and `fields_by_keyword` ([`models.py:618-619`](../../../../src/tsplib_parser/models.py#L618-L619)). Each class is processed on its own, which is why `Problem.fields_by_keyword` is empty and `StandardProblem.fields_by_keyword` holds the 18 keywords. The MRO walk details are in [metaclasses-new-mro.md](./metaclasses-new-mro.md).

Why there rather than in the class body? A class body does have its own namespace, so a comprehension over `locals()` would technically see the fields — that half is true and is often forgotten. What the body cannot do is *name the class it is still defining*, and it has no `self` or `cls`. Both halves are demonstrable:

<details name="demos">
<summary><h5>Demo: a class body can read its own namespace, but cannot name itself (copy and run)</h5></summary>

```python
class Demo:
  a = 1
  seen = sorted(k for k in locals() if not k.startswith("__"))
  try:
    me = Demo                      # the class does not exist under this name yet
  except NameError as e:
    err = str(e)

print(Demo.seen)
print(Demo.err)
```

```text
['a']
name 'Demo' is not defined
```

Note where the two results live: `seen` and `err` are **class attributes**, because the `except` block runs while the namespace is still being built. That detail is the reason the index is not computed in the body, and there are two more: a body cannot walk `cls.__mro__`, since it has no `cls`, and the merge has to happen *after* `type.__new__` has installed the namespace and fired `__set_name__` on every field. A body can produce values; it cannot do any of those three things.

</details>

The metaclass is handed both the finished namespace and the class object, which keeps the declarations and the index in one place. When a metaclass is the right tool versus `__init_subclass__` is discussed in [metaclasses-new-mro.md](./metaclasses-new-mro.md).

### The XRayProblem example without the mistake

The example that raised the question put a *transformer* in a problem class body. Two spellings of that mistake exist, and only one of them is silently useless:

```python
from tsplib_parser.models import Field, FuncT, StandardProblem, TransformerField


class XRayT:
  """a bare transformer, not a Field"""


class Wrong1(StandardProblem):
  intensity_tf = XRayT()                      # never registered: not a Field instance


class Wrong2(StandardProblem):
  intensity = Field("INTENSITY_SECTION")      # registered, but with no parsing rule


class XRayIntensityField(TransformerField):   # the rule belongs to the field class
  @classmethod
  def build_transformer(cls) -> FuncT[int]:
    return FuncT(func=lambda text: int(text, 8))


class Right(StandardProblem):
  intensity = XRayIntensityField("INTENSITY_SECTION")
```

The three classes fail differently, which is worth seeing once:

```text
'intensity_tf' in Wrong1.fields_by_name   -> False     ignored, no error anywhere
'intensity'    in Wrong2.fields_by_name   -> True      registered...
Wrong2.parse("...INTENSITY_SECTION: 8...") -> ParseError: TSPLIB parse errors: invalid value for INTENSITY_SECTION:
Right.parse("...INTENSITY_SECTION: 10...").intensity -> 8
```

`Wrong1` is the dangerous one: the attribute simply never reaches the index, and because unknown keywords are tolerated, nothing complains. `Wrong2` at least fails loudly, and the detail of *how* is worth knowing — the underlying failure is `Field.parse` raising `NotImplementedError` with no message, which `parse` collects as `invalid value for <keyword>: <the empty message>`, and the empty tail is why that error line ends in a colon. `Right` is the whole correction — the rule lives on a field class, and the problem class gets one declaration.

## When the field objects exist

The class body is executed statement by statement in a fresh namespace. Each declaration evaluates a transformer-backed field object:

```python
class StandardProblem(Problem):
    name = StringField("NAME")
#   └─ evaluates StringField("NAME")
#        → TransformerField.__init__ → Field.__init__ sets self.keyword = "NAME", self.name = None
#        → build_transformer() → FuncT(func=str)
#   → the result is bound as namespace["name"]
```

At the end of the body the namespace holds 18 fully constructed field objects. The full import-time sequence for `class StandardProblem(Problem):` is:

```ascii
1. a fresh namespace dict is opened for the class body
2. the body executes top to bottom:
     name = StringField("NAME")          ← field object 1 now exists
     dimension = IntegerField("DIMENSION")   ← object 2
     ... 16 more
3. FileMeta.__new__ is called with that namespace as attrs
4. type.__new__ installs the namespace and fires __set_name__ on each field
5. lines 618-619 build the two dictionaries from the installed fields
6. the finished class is bound to the name StandardProblem in the module
```

Step 4 is where the field learns its attribute name. CPython's `type_new_set_names()` runs from inside `type.__new__`, after the class `__dict__` is populated. It calls `__set_name__(owner, attribute_name)` on every descriptor it finds there, and [`Field.__set_name__`](../../../../src/tsplib_parser/models.py#L409) fills in the missing name:

```python
def __set_name__(self, cls: type, name: str) -> None:
    if self.name is None:
        self.name = name        # Field("NAME") → self.name = "name"
```

That is why the constructor takes the keyword `"NAME"` while the parser later writes `setattr(problem, field.name, ...)` with the attribute name `name`. It is a callback from the interpreter into the field class, not recursion.

The caveat matters elsewhere: `__set_name__` fires only for **class** attributes. The alternative design that assigns fields inside `__init__` would never trigger it, so `field.name` would stay `None` — see [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md).

Before step 3 the field objects exist but the index does not. A class body can see its own namespace, but it cannot name the class it is still defining:

```python
class StandardProblem(Problem):
    name = StringField("NAME")
    # possible but awkward here: {k: v for k, v in locals().items() if isinstance(v, Field)}
    # impossible here: naming StandardProblem, which does not exist yet
    fields_by_keyword = {f.keyword: f for f in ???}
```

The metaclass is handed both the complete namespace and the class object, which is why the index is built there rather than in the body. Upstream `tsplib95` uses the same hook; the difference in this port is that the fields stay as class attributes instead of being popped out of the namespace — see [models.md](../../../src/tsplib_parser/models.md).

One clarification, because the amount of import-time machinery can suggest otherwise: none of this makes the class self-instantiating. `FileMeta.__new__` runs once per class, at import, when the **class** is created. It does not run when a problem is created:

```python
import tsplib_parser.models      # FileMeta.__new__ runs HERE, once per class
problem = StandardProblem()      # FileMeta.__new__ does NOT run here
```

Nothing in `FileMeta` runs during parsing. It instantiates a class, not an object.

## The two registries

`registry` is not an attribute this package defines: no such name is assigned anywhere under `src/**/*.py`, and the only occurrences of the string are the pedagogical example and an unrelated comment in the converter. It is an arbitrary name for "the map the metaclass hangs on the class". The real equivalent is the pair of attributes assigned in [`FileMeta.__new__`](../../../../src/tsplib_parser/models.py#L618-L619):

```python
cls.fields_by_name = fields
cls.fields_by_keyword = {f.keyword: f for f in fields.values()}
```

Both maps hold the same 18 field objects, keyed differently:

| Map | Keyed by | Example key | Read by |
| --- | --- | --- | --- |
| `fields_by_name` | python attribute name | `dimension` | the default lookup in `__getattribute__`, and `as_dict` when enumerating the schema |
| `fields_by_keyword` | file keyword | `DIMENSION` | keyword lines in `parse`, and section headers in `_SectionAccumulator.close` |

Each class gets its own pair, which is why `Problem`'s map is empty while `StandardProblem`'s holds 18 entries — the same point demonstrated with the MRO walk in [metaclasses-new-mro.md](./metaclasses-new-mro.md). The upstream package ships four maps rather than two; which two it does not carry over is listed in [models.md](../../../src/tsplib_parser/models.md). How the arguments that trigger this assignment arrive is covered in [metaclasses-new-mro.md](./metaclasses-new-mro.md).

## Connections

### Links out

- [metaclasses-new-mro.md](./metaclasses-new-mro.md) — the class-creation machinery that fires this system.
- [attribute-lookup.md](./attribute-lookup.md) — how field defaults reach a caller.
- [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md) — why fields live on the class rather than in `__init__`.
- [models.md](../../../src/tsplib_parser/models.md) — the package overview.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [metaclasses-new-mro.md](./metaclasses-new-mro.md) — the field objects its machinery registers.
- [attribute-lookup.md](./attribute-lookup.md) — "the field objects whose defaults this hook returns".
- [factory-pattern.md](./../practical/factory-pattern.md) — the import-time half of the parse flow.
- [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md) — the default and transformer footguns discussed there.
- [typevars-pep695-cast.md](./typevars-pep695-cast.md) — the two generic-typing systems its `self.tf` transformer annotations assume.
