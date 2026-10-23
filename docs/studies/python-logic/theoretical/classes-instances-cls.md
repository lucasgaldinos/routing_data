---
title: Classes, instances, and cls
description: >
  A guided explanation of the class/instance split that the parse factory relies on: why classmethods receive cls instead of self, what inheritance actually inherits, and what happens when a class is called. Part of the python-logic series that teaches the concepts the tsplib_parser package uses.
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
          First version. Extracted and rewrote §2.2 and §2.3 of PARSER-DETAILS.MD as a standalone didactical file: cls binding, inheritance of function versus binding, instantiation without class mutation, self-versus-cls, object lifecycle, and the classmethod decision table. Demos carried over with their executed outputs.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Reader pass. Answered four open questions inline: why the method binds to the class rather than the instance (nothing exists yet at the call site), added a demo of the same factory written without @classmethod and its failure at the class call site; explained that setattr lands wherever its target object is, so parse's setattr(problem, ...) writes the instance __dict__ while the class Field is only shadowed; explained why parse_file strips VRP extension sections before the core parse; and defined "class-definition time" with a demo showing the field object exists before any problem does.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Second reader pass. Clarified evaluation order of problem_instance = StandardProblem.parse(text) (lookup, call, cls() inside, bind after return — no instance before the call); rebuilt the without-@classmethod demo so the comparison is equivalent (same one-argument call shape on the class, then the throwaway-instance workaround); answered why VRP extras live in parser.py instead of a StandardProblem subclass (a subclass is an option — FileMeta proves it — but the preprocessor wins on scale and ownership, and the warning marks it as MVP debt); updated the intro to six questions and fixed the wrap-step count and a typo.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          Rewrote the "what changes if the method were bound to an instance" demo. Gave Plain a real __init__ and printed that it defines one, so the failure of Plain.parse(text) is visibly about binding, not construction; added the p.ready line to show the constructed instance works; replaced the observations with three points that separate construction from binding.
  - date_modified: 2026-10-06
    modifications:
      - description: >
          De-duplication pass against factory-pattern.md: the object-lifecycle section now points to the full per-call flow and stack trace there instead of carrying the details alone.
related_files:
  - "[PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)"
  - "[models.py](../../../../src/tsplib_parser/models.py)"
  - "[factory-pattern.md](./../practical/factory-pattern.md)"
  - "[fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md)"
  - "[metaclasses-new-mro.md](./metaclasses-new-mro.md)"
tags:
  - guide/python-oop
  - guide/classmethod
  - guide/object-lifecycle
  - guide/attribute-binding
  - guide/parse-factory
  - guide/tsplib-parser
  - guide/learning-path
---

# Classes, instances, and cls

- [Classes, instances, and cls](#classes-instances-and-cls)
  + [What this file answers](#what-this-file-answers)
  + [The one idea underneath everything here](#the-one-idea-underneath-everything-here)
  + [Why cls and not the literal class name](#why-cls-and-not-the-literal-class-name)
  + [What inheritance actually inherits](#what-inheritance-actually-inherits)
    - [What changes if the methods were bound to an instance](#what-changes-if-the-methods-were-bound-to-an-instance)
  + [Whether calling the class changes the class itself](#whether-calling-the-class-changes-the-class-itself)
  + [Why parse receives cls instead of self](#why-parse-receives-cls-instead-of-self)
    - [When the object comes into existence](#when-the-object-comes-into-existence)
    - [Why not a StandardProblem subclass instead](#why-not-a-standardproblem-subclass-instead)
  + [When to use a class method instead of an instance method](#when-to-use-a-class-method-instead-of-an-instance-method)
  + [The correction worth keeping](#the-correction-worth-keeping)
  + [Connections](#connections)

## What this file answers

Six questions keep coming back while reading `StandardProblem.parse`:

- why the method is called `parse(cls, text, ...)` instead of `parse(self, text, ...)`;
- why the method spells `cls()` instead of the literal class name `StandardProblem()`;
- why the method binds to the class at all, and what would break if it bound to an instance;
- whether calling a class changes the class itself;
- when exactly the problem object comes into existence;
- why `setattr` inside the method writes the instance rather than the class.

All of them have one answer underneath them, which is the next section. After that, each question gets its own section, and the last section lists where to go next.

> [!note]
> Claims in this file were verified against [`models.py`](../../../../src/tsplib_parser/models.py) and by running every demo shown.
> The package itself is described in [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD) and, in its final form, in [`models.md`](../../../src/tsplib_parser/models.md).

## The one idea underneath everything here

A class is an ordinary value. `StandardProblem` is an object you can name, pass to a function, store in a list, and ask questions of — exactly like a string is. The word "class" describes what the value *does* (build instances), not some other kind of thing that it *is*.

From that one fact the rest follows:

- When a method receives `cls`, it is receiving this value — the same object you would have spelled `StandardProblem`.
- "Calling" the class — `cls()` — is asking this value to build one instance and hand it back.
- The method is `parse(cls, text)` rather than `parse(self, text)` because the value the method needs to talk to is the factory itself, not one of its products.

> [!tip]
> The mechanical reason a `@classmethod` receives the class is binding: `StandardProblem.parse` stores `__func__` (the plain function) and `__self__` (the class).
> Accessing it on a subclass rebinds `__self__` to the subclass.
> A `@classmethod` is a method marked with that decorator so it binds to the class instead of to an instance; `__dict__` is the dictionary where an object stores its own attributes.
> The demo in the next section makes both observable.

## Why cls and not the literal class name

Because `cls` **is** the class — the same object, handed to the method rather than spelled out:

```python
StandardProblem.parse(text)   # cls is StandardProblem
SubClass.parse(text)          # cls is SubClass — a literal name would break this
```

Inside the method, `cls.fields_by_keyword` reads the class registry and `cls()` builds exactly that class. A hardcoded `StandardProblem()` would return the parent type for any subclass and silently ignore the subclass's extra fields.

> [!important] how instantiation works
> Read `problem_instance = StandardProblem.parse(text)` from left to right, and nothing is built until the very last moment:
>
> 1. `StandardProblem.parse` — attribute access. Returns a bound method (function + `cls`). No instance is created here.
> 2. `(text)` — the call. The method body starts running, still with no instance.
> 3. `problem = cls()` inside the body ([`models.py:851`](../../../../src/tsplib_parser/models.py#L851)) — only now is the instance created.
> 4. The method returns it, and only then does the assignment bind the name `problem_instance`.
>
> So the line does not build an instance "before calling `parse`": the left side is only a lookup of the method, and the name binds after the call has finished and returned.

## What inheritance actually inherits

One word makes this precise: what a subclass inherits is the **function**, while what changes is the **binding**. `SubClass.parse` is the very same function object as `StandardProblem.parse`, but asking the subclass for it binds `cls` to the subclass.

> [!note]
> At the moment `parse` is called, no problem object exists yet — creating one is exactly the job of the call.
>
> - Binding to the class means the call site is `SubProblem.parse(text)`, with nothing pre-built.
> - Binding to an instance would require a `SubProblem` in hand *before* building a `SubProblem`.
>
> Inheritance is not what changes between the two designs — it works in both. What changes is what the call site must already hold.

<details name="demos">
<summary><h5>Demo: one function, two bindings (copy and run)</h5></summary>

```python
from tsplib_parser.models import IntegerField, StandardProblem


class SubProblem(StandardProblem):
  intensity = IntegerField("INTENSITY_SECTION")


text = "NAME: demo\nTYPE: TSP\nDIMENSION: 3\nINTENSITY_SECTION: 7\n"
r1 = StandardProblem.parse(text)
r2 = SubProblem.parse(text)

print("same function  ->", SubProblem.parse.__func__ is StandardProblem.parse.__func__)
print("cls bound to   ->", StandardProblem.parse.__self__.__name__, "/", SubProblem.parse.__self__.__name__)
print("parent result  ->", type(r1).__name__, r1.__dict__)
print("child result   ->", type(r2).__name__, r2.__dict__)
```

```text
same function  -> True
cls bound to   -> StandardProblem / SubProblem
parent result  -> StandardProblem {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3}
child result   -> SubProblem {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3, 'intensity': 7}
```

</details>

So the inherited method does produce the subclass, and the `intensity` keyword is parsed into it because `FileMeta` registered that field on `SubProblem` as well. The same text parsed by the parent produces the parent and drops the keyword, with no error — the tolerant-unknown-keyword behaviour that [models.md](../../../src/tsplib_parser/models.md) document.

> [!tip]
> `parse.__func__` and `parse.__self__` expose the binding directly: `__func__` is the plain function, `__self__` is the object it got bound to.
> Instance methods have the same pair, with the instance as `__self__`.

### What changes if the methods were bound to an instance

The obstacle is binding, not construction. `Plain` below defines a normal `__init__` and constructs instances perfectly well — and the plain call on the class still fails, for the same one-argument call shape that the classmethod handles:

<details name="demos">
<summary><h5>Demo: the same factory without @classmethod (copy and run)</h5></summary>

```python
from tsplib_parser.models import IntegerField, StandardProblem

class SubProblem(StandardProblem):
  intensity = IntegerField("INTENSITY_SECTION")

text = "NAME: demo\nTYPE: TSP\nDIMENSION: 3\nINTENSITY_SECTION: 7"

class Plain:
  def __init__(self):                       # same construction machinery as any class
    self.ready = True
  def parse(self, t):
    return self.__class__.__name__ + ":" + t

print("Plain defines __init__ ->", "__init__" in Plain.__dict__)

# classmethod: the call on the class works, one argument
r2 = SubProblem.parse(text)
print("classmethod       ->", type(r2).__name__, r2.__dict__)

# plain method: the SAME call shape on the class fails — __init__ does not help
try:
  r3 = Plain.parse(text)
except TypeError as e:
  print("plain on class    -> TypeError:", e)

# plain method: works only when a throwaway instance exists first
p = Plain()
r3 = p.parse(text)
print("plain on instance ->", r3)
print("p.ready           ->", p.ready)
```

```text
Plain defines __init__ -> True
classmethod       -> SubProblem {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3, 'intensity': 7}
plain on class    -> TypeError: Plain.parse() missing 1 required positional argument: 't'
plain on instance -> Plain:NAME: demo
TYPE: TSP
DIMENSION: 3
INTENSITY_SECTION: 7
p.ready           -> True
```

</details>

What the output shows:

- `Plain` defines `__init__` (`True` on the first line), and the split is unchanged — the failure has nothing to do with construction. A class that constructs instances perfectly well still cannot answer a plain-method call made *on the class*.
- The classmethod succeeds because `cls` is injected automatically; the plain method fails because nothing is injected, so `text` lands in `self` and `t` is missing.
- The workaround needs a throwaway `p = Plain()` first, then `p.parse(text)`. A real factory would then have to build its product from `self.__class__`, which is the classmethod's job done by hand.

So the `@classmethod` is not about inheritance, and not about `__init__` — it is about which object the method can bind to before anything has been built.

## Whether calling the class changes the class itself

No. `cls()` runs the ordinary instantiation path:

```text
type.__call__(cls)
  ├─ cls.__new__(cls)     → object.__new__ → a new object with a new, empty __dict__
  ├─ obj.__init__(**kw)   → Problem.__init__ → setattr on THAT object's __dict__
  └─ return obj
```

Two namespaces that never touch, and the checks behind that claim are runnable:

<details name="demos">
<summary><h5>Demo: instantiating a class does not modify it (copy and run)</h5></summary>

```python
class Thing:
    x = "class-attr"
    def __init__(self, v): self.v = v

before = dict(Thing.__dict__)
t = Thing(5)
after = dict(Thing.__dict__)
print("class __dict__ identical after Thing(5)? ->", before == after)
print("instance __dict__                        ->", t.__dict__)
t.v = 99
print("'v' in Thing.__dict__ after t.v = 99     ->", "v" in Thing.__dict__)
print("Thing.x (class attr)                     ->", Thing.x)

print("--- contrast: assignment on the CLASS does mutate it ---")
Thing.y = "added"
print("'y' in Thing.__dict__ now                ->", "y" in Thing.__dict__)
```

```text
class __dict__ identical after Thing(5)? -> True
instance __dict__                        -> {'v': 5}
'v' in Thing.__dict__ after t.v = 99     -> False
Thing.x (class attr)                     -> class-attr
--- contrast: assignment on the CLASS does mutate it ---
'y' in Thing.__dict__ now                -> True
```

The same check against the real classes, where the instance attribute shadows the class-level `Field` for that one object:

```python
from tsplib_parser import models as m

q = m.StandardProblem.parse("NAME: demo\nTYPE: TSP\nDIMENSION: 3\n")
print("instance __dict__            ->", q.__dict__)
print("type(q.dimension)            ->", type(q.dimension).__name__)
print("type(StandardProblem.dimension) ->", type(m.StandardProblem.dimension).__name__)
print("class field intact           ->", m.StandardProblem.dimension.keyword, m.StandardProblem.dimension.name)
```

```text
instance __dict__            -> {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3}
type(q.dimension)            -> int
type(StandardProblem.dimension) -> IntegerField
class field intact           -> DIMENSION dimension
```

</details>

Only direct assignment on the class object mutates a class, and in this module it happens in exactly one place — `FileMeta.__new__` ([`models.py:618-619`](../../../../src/tsplib_parser/models.py#L618-L619)), at import, where `fields_by_name` and `fields_by_keyword` are assigned.

`setattr(obj, name, value)` is exactly `obj.name = value` — where the attribute lands is decided by `obj`, nothing else. It is not inherently instance-only: `setattr(StandardProblem, "x", 1)` would set a class attribute. Every `setattr` call in this module targets an instance because the object being passed is always an instance: `parse` holds `problem`, so `setattr(problem, "dimension", 3)` writes `"dimension"` into that one instance's `__dict__`. The class-level `Field` object stays untouched and merely gets shadowed *for that instance* — see [attribute-lookup.md](./attribute-lookup.md) for what that shadowing does to reading.

One more subtlety: a classmethod never receives the instance. `q.parse(text)` is legal, but `cls` is still `StandardProblem`, never `q`.

See [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md) for why the class-level field survives the instance-level write.

## Why parse receives cls instead of self

The one-line version: `self` is the cookie in your hand, `cls` is the cookie cutter. `parse` produces a problem, and the problem does not exist yet, so the method has to ask the cutter. Taking `self` would require a problem in order to build a problem.

### When the object comes into existence

Half yes, half no, and the halves matter.

- **Yes**: by the time anything is handed back to you, it is complete. There is no window in which you hold a partly-filled problem, and no `parse` step you perform yourself.
- **No**: handing over text does not create anything. A `str` is inert; creating the object is an action of the method body, which runs when the method is called — the text argument itself never builds anything.

The order inside one call, with the source locations:

```text
StandardProblem.parse(text)
  1. problem = cls()                       models.py:851   ← the object exists, empty
  2. acc = _SectionAccumulator(...)        models.py:853
  3. line loop: setattr(problem, field.name, parsed)       ← it is filled here
  4. errors raised, if any, at the end of the loop
```

So the object is created *by* `parse`, first line, and filled afterwards. `parse_file` ([`parser.py:82`](../../../../src/tsplib_parser/parser.py#L82)) wraps that with five more steps that also run before you see anything:

```text
FormatParser.parse_file(path)
  1. _preprocess_vrp_file(path)        → may write a temp file, strips VRP extensions
  2. open(...).read()                  → text
  3. StandardProblem.parse(text, ...)  → the four steps above
  4. temp file removed, if one was written
  5. validate_problem(problem)         → may raise
  6. _extract_*                        → plain dict result
```

> [!warning] Problem that must be solved in this parser. This was done as a way to make a quick MVP, not the intended design.
> VRP extensions should not be st
> Why strip VRP extensions first? `StandardProblem.parse` implements the TSPLIB95 core, and that is deliberate: it knows nothing about VRP extras such as `TIME_WINDOW_SECTION`, `PICKUP_SECTION` or `SERVICE_TIME_SECTION`.
> Left in the text, those section headers would open an accumulator whose body lines match no field — the data would be silently swallowed, or worse, misread as something else.
> `_preprocess_vrp_file` removes those sections into a temporary file; the most important ones are also recorded — `TIME_WINDOW_SECTION` and `PICKUP_SECTION` set flags in `self._additional_vrp_fields`, parser-instance state that the metadata extractors read later.
> The remaining extended sections, such as `SERVICE_TIME_SECTION`, are dropped without a flag — `StandardProblem` has no field to hold them. The core parse therefore sees clean TSPLIB text, while the VRP information still reaches the output wherever a field for it exists.
> The full layer split is covered in [parser-pipeline.md](../../../src/tsplib_parser/parser-pipeline.md).

All of it happens before the caller regains control, which is why a returned problem is never half-built. What is *not* true is that the object predates the call: it is a local variable born at line 851 and returned at the end. The full per-call flow, including a recorded stack trace of a field being parsed, is in [factory-pattern.md](./../practical/factory-pattern.md).

### Why not a StandardProblem subclass instead

A subclass with its own fields *is* an option — `FileMeta` registers the fields of every subclass, and the `SubProblem` demo above proves the mechanism end to end. The design questions are scale and ownership:

- One parser serves TSP, ATSP, HCP, SOP, TOUR and the CVRP/VRP variants; MDVRP goes through a separate parser (`tsplib_parser/cordeau`) and the converter CLI excludes it. A subclass per variant means a class zoo — `CvrpProblem`, `CvrpTwProblem`, `MdvrpProblem`, and so on — each needing its own maintenance, plus a way to pick the right class before parsing.
- `StandardProblem` is the strict TSPLIB core; VRP semantics (time windows, demands, depots) are owned by `FormatParser` and the converter, which turn them into the flat dicts the database expects. The preprocessor keeps that ownership in one place.
- **The trade-off is the one the warning above names: the preprocessor route was the quick MVP path, and that is where the design debt sits.** A `CvrpProblem` subclass with real fields — `TIME_WINDOW_SECTION` and friends registered by `FileMeta` — is a legitimate evolution, and the machinery for it is already in place; it just was not the shortest path to a working ETL.

The full layer split, including what would change under a subclass design, is covered in [parser-pipeline.md](../../../src/tsplib_parser/parser-pipeline.md).

## When to use a class method instead of an instance method

| | Instance method | Class method |
| --- | --- | --- |
| First argument | `self`, an object that already exists | `cls`, the class itself |
| Called as | `dog.bark()` | `Dog.from_json(text)` |
| Can do | read and write this object's data | `cls()` to create a new one, read class-level configuration |
| Role | operate on an existing thing | factory, alternate constructor |

The same module uses both, for their correct purposes:

| Line | Owner | First argument |
| --- | --- | --- |
| [`models.py:121`](../../../../src/tsplib_parser/models.py#L121), [`420`](../../../../src/tsplib_parser/models.py#L420), [`441`](../../../../src/tsplib_parser/models.py#L441) | transformer (121), field (420, 441) | `self`, the transformer or field object |
| [`models.py:673`](../../../../src/tsplib_parser/models.py#L673) | `Problem.parse`, the lenient base | `cls` |
| [`models.py:832`](../../../../src/tsplib_parser/models.py#L832) | `StandardProblem.parse`, the strict override | `cls` |

**`Field.parse(self, text)` is an instance method because the field object was created at class-definition time and already exists. `StandardProblem.parse(cls, text)` is a classmethod because no problem exists yet.**

"Class-definition time" means the moment the `class StandardProblem:` block executes — once, at import. A class body is code that runs: the line `dimension = IntegerField("DIMENSION")` *calls* `IntegerField`, and the field object that call returns is stored on the class. From then on, parsing a hundred files reuses that one object; nothing creates a new field per problem.

<details name="demos">
<summary><h5>Demo: the field exists before any problem does (copy and run)</h5></summary>

```python
from tsplib_parser import models as m

f_before = m.StandardProblem.dimension          # no problem object exists yet
print("field exists before any parse ->", f_before.keyword, f_before.name)

q = m.StandardProblem.parse("NAME: demo\nTYPE: TSP\nDIMENSION: 3\n")
f_after = m.StandardProblem.dimension
print("same field object after parse ->", f_before is f_after)
print("q.__dict__                     ->", q.__dict__)
```

```text
field exists before any parse -> DIMENSION dimension
same field object after parse -> True
q.__dict__                     -> {'name': 'demo', 'problem_type': 'TSP', 'dimension': 3}
```

</details>

Fields predate problems, so `Field.parse` naturally binds to the field (`self`). Problems do not predate parsing, so `StandardProblem.parse` must bind to the class (`cls`). How the field object gets its `name` at class-definition time is the `__set_name__` story in [descriptors-fields.md](./descriptors-fields.md).

## The correction worth keeping

Each problem is indeed an object — but a classmethod is not applied to it. An earlier draft of these notes claimed a classmethod was *required* to read class-level state. That is false. An instance reads class state perfectly well, because `self.fields_by_keyword` resolves upward to the class. The real and only reason for `@classmethod` is that at call time there is no object to bind to `self`. The hook that runs before any of this — class creation itself — is the neighbouring story in [metaclasses-new-mro.md](./metaclasses-new-mro.md).

## Connections

### Links out

- [factory-pattern.md](./../practical/factory-pattern.md) — the factory pattern built on this file's `cls`, binding and instantiation facts.
- [metaclasses-new-mro.md](./metaclasses-new-mro.md) — the neighbouring hook: what happens when the class itself is created.
- [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md) — why the class-level field survives an instance-level write of the same name.
- [models.md](../../../src/tsplib_parser/models.md) — the package overview.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [factory-pattern.md](./../practical/factory-pattern.md) — "the theory this pattern stands on" (also the class-vs-factory primer).
- [metaclasses-new-mro.md](./metaclasses-new-mro.md) — the class/instance/`cls` theory its class-creation story extends.
