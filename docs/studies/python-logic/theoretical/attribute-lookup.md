---
title: Attribute lookup and __getattribute__
description: >
  Why Problem overrides __getattribute__: the two __dict__s it must keep apart, what object.__getattribute__ means, the three answers tried in order, the hard constraint that the hook cannot read self.__dict__, the measured recursion limit, and what the default-returning behaviour costs. Part of the python-logic series.
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
          First version. Extracted and rewrote §5.1 of PARSER-DETAILS.MD as a standalone lesson: the three-answer table with a runnable demo, the recursion constraint with the naive counterexample and the measured 199 re-entries, the swallowed KeyError trace, the cost of the hook, and the callable-default rule.
  - date_modified: 2026-10-08
    modifications:
      - description: >
          Clarified that only the instance __dict__ is empty (a new "two __dict__s" section contrasting it with the class dict's 24 entries), added a section explaining object.__getattribute__ (root class, un-overridden lookup, and the plain lookup returning the Field object), expanded the demo to show class-attribute access, corrected the models.py line references to L634-L651, and rewrote Connections to name the section each link targets.
      - description: >
          Second pass: separated the default lookup from the module's three-stage lookup, added the "root of the tree equals last in the MRO" and "not reverting the MRO" clarifications, added a section on which creation event fills which dict, replaced bare line citations with a link to the code block, and switched connections to section-anchor links.
      - description: >
          Third pass: answered "is __getattribute__ a classmethod?" (instance method and descriptor binding: class access leaves no receiver, so self is passed by hand), explained why the instance __dict__ is read before the field registry (with a class-first counter-demo), and sharpened "empty dict" and cls-vs-problem wording in parse.
      - description: >
          Fourth pass: added the function-versus-method binding note, a section on calling a base implementation on purpose (object. versus super() and the forward-MRO rule), per-stage traces in "When the third answer is reached", and the note that cls is a convention rather than a keyword.
      - description: >
          Fifth pass: corrected the reversed-MRO note (reversing does hit object first, since object is last; the objection is that it re-implements a nameable lookup with the wrong rule for ordinary lookup), added the measured forward/reversed first-hit demo, and rewrote "When the third answer is reached" around the method's two try blocks with a merged-try counter-demo.
related_files:
  - [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.py](../../../../src/tsplib_parser/models.py)
  - [factory-pattern.md](./../practical/factory-pattern.md)
  - [descriptors-fields.md](./descriptors-fields.md)
  - [classes-instances-cls.md](./classes-instances-cls.md)
  - [metaclasses-new-mro.md](./metaclasses-new-mro.md)
tags:
  - guide/attribute-lookup
  - guide/python-oop
  - guide/recursion
  - guide/tsplib-parser
---

# Attribute lookup and `__getattribute__`

## What this file answers

`Problem.__getattribute__` answers one question: *what should `problem.dimension` do when nothing was parsed for it?* Instead of raising, it answers with the field's default. This file covers:

- why the hook lives on `Problem` and not on `StandardProblem`;
- which `__dict__` it consults, and how the instance dict differs from the class's;
- what `object.__getattribute__` means and why the code calls it that way;
- the three answers it tries, in order, and the fall-through at each step;
- the constraint that makes the obvious implementation loop forever;
- what the behaviour costs and why a default may be a callable.

> [!note]
> Every claim was verified against [`Problem.__getattribute__`](../../../../src/tsplib_parser/models.py#L634-L651) and by running the demos shown, whose output is pasted verbatim.

## Why it is defined on Problem rather than on StandardProblem

Because `Problem` is the only class where the implementation can be generic.
The hook needs a field registry, and every field-bearing class has one through `FileMeta`, so defining it on the base means `StandardProblem` inherits it without a line of its own code. Putting it on `StandardProblem` would mean copying it into every future problem class — the same argument that keeps `as_dict` on the base.

## What it does, and why it is written that way

Everything in the code follows from the goal — unset fields answer instead of raising — plus one hard constraint about how such a method may be written.

Three answers, tried in order, and the fall-through is deliberate at each step — [`Problem.__getattribute__`](../../../../src/tsplib_parser/models.py#L634-L651) in full:

| # | Where it looks | Found | Not found |
| --- | --- | --- | --- |
| 1 | the instance's own `__dict__` | the parsed value | fall through |
| 2 | `cls.fields_by_name[name]` | that field's default | fall through |
| 3 | `object.__getattribute__(self, name)` | ordinary attribute or method | `AttributeError` |

### Two `__dict__`s: the instance's and the class's

Before reading that table, keep the two storage places apart — "nothing is in `__dict__`" is only true of the **instance** one:

| Storage | Owner | For a fresh `StandardProblem()` |
| --- | --- | --- |
| `p.__dict__` | the object `p` | `{}` — empty until parsing writes into it |
| `StandardProblem.__dict__` | the class | 24 entries: the `Field` objects, `fields_by_name`, `fields_by_keyword`, the methods, and the usual dunders |

> [!important]
> The empty one is the instance dict, never the class's.
> `StandardProblem.__dict__` is full, and it is exactly where step 2 finds the field whose default it returns.
> Read "nothing is in `__dict__`" as "nothing is in *the instance's* `__dict__`" — the class dict is the source of the answer, not part of the problem.

### Which event fills which dict

The two dicts are filled by two different events, at two different times:

| Event | What runs | Dict it fills |
| --- | --- | --- |
| the class statement `class StandardProblem(Problem): ...`, at import | `FileMeta.__new__` → `type.__new__` | the **class** dict — the field objects, `fields_by_name`, `fields_by_keyword` |
| an instance `p = StandardProblem()` | `type.__call__` → `object.__new__` → `Problem.__init__` | the **instance** dict — one entry per keyword argument, and empty when none are passed |
| a later `p.dimension = 3` | `setattr` on `p` | the **instance** dict again; the class attribute is untouched |

> [!important]
> Creating an *instance* never writes to the class dict.
> `StandardProblem()` starts `p.__dict__` empty and only `__init__`/`parse` write into it; `StandardProblem.__dict__` was already filled at import and stays as it is.
> "Empty" here means **no keys at all** (`{}`), not "keys holding empty values": the empty *values* (`0`, `None`, …) belong to the field objects on the class and are never copied into the instance.
> Measured: `StandardProblem(name="demo")` → `{'name': 'demo'}`, while the class keeps its `StringField` in the class dict.
>
> One naming trap in `parse`: `cls` is the **class** (`StandardProblem`), not an instance. The instance is `problem = cls()`, and it is `setattr(problem, field.name, parsed_value)` — never `setattr(cls, …)` — that fills that one object's dict as the lines are parsed.

The proof for the plain case is in [classes-instances-cls.md](./classes-instances-cls.md#whether-calling-the-class-changes-the-class-itself) — "class `__dict__` identical after `Thing(5)? -> True`" next to "instance `__dict__` -> `{'v': 5}`".
The `parse` path applies the same rule one layer later, calling `setattr(problem, ...)` on the object it created — see [factory-pattern.md](./../practical/factory-pattern.md#why-the-object-is-created-inside-parse-rather-than-outside).

### What `object.__getattribute__` means

`object` here **is not an instance** — it is the class at the **root** of the inheritance tree: every class descends from it, directly or through others.

> [!note]
> "Root of the tree" and "last in the MRO" are the same fact seen from opposite ends. `object` is the ancestor every class shares — so it is the root — and an MRO is written from the most derived class down to that shared ancestor, so the root comes **last**:
>
> ```text
> StandardProblem.__mro__ -> ['StandardProblem', 'Problem', 'object']
> ```
>
> Yes: `object` is the last entry precisely *because* it is the root.

`object.__getattribute__` is the default, un-overridden attribute lookup the language ships with. Its algorithm, in full:

1. look the name up in the object's own `__dict__`;
2. otherwise look it up along the MRO of the object's class;
3. otherwise raise `AttributeError`.

That is what a plain `p.dimension` runs — *unless* a class in the MRO replaces `__getattribute__`, as `Problem` does.

> [!important]
> Two questions are easy to merge here, and merging them causes most of the confusion:
>
> - **What is the default behaviour?** The three steps above, nothing more. The default knows nothing about "fields" or "defaults".
> - **What does this code do?** It wraps that default with one extra step in the middle. The order becomes: instance `__dict__` → the field's default from `fields_by_name` → the default lookup (ordinary attributes and methods) → `AttributeError`.
>
> The last stage *is* the default behaviour, called on purpose because the first stage's own read — `self.__dict__` — would otherwise re-enter the hook.

**Is this "reverting the MRO"?** No. The MRO still reads `StandardProblem → Problem → object`; it is neither reordered nor walked backwards. What changes is only the *starting point of one lookup*: the name `__getattribute__` is looked up **on the class `object`** instead of on the instance. Written on the instance it would find `Problem`'s override; written on the class it finds the plain function stored in `object`'s own `__dict__`. That function is then called with `self` handed in explicitly:

| Written | What it does | Re-enters the hook? |
| --- | --- | --- |
| `self.__getattribute__(name)` | looks the name up on the instance | yes — it *is* the override |
| `object.__getattribute__(self, name)` | the function found on `object`, called with `self` | no — runs the default |
| `object.__getattribute__(self, "__dict__")` | the same trick, for the instance's own dict | no |

> [!note]
> The trick works because `object` sits at the end of the MRO, so nothing between `Problem` and `object` can intercept the call. The same "call it on the base class" pattern appears in class creation, where `FileMeta.__mro__ -> ['FileMeta', 'type', 'object']` also ends in `object` — see [*Whether super() is calling type*](./metaclasses-new-mro.md#whether-super-is-calling-type) and [*Creating a class versus instantiating it*](./metaclasses-new-mro.md#creating-a-class-versus-instantiating-it).

### Is `__getattribute__` a class method?

No — it is an ordinary **instance method**: a descriptor kept on the class, whose first parameter is the receiver.
What makes `object.__getattribute__(self, name)` look odd is not a method kind, but *how the name was reached*:

- reached through an **instance** (`p.__getattribute__`), the descriptor binds, `self` is filled in for you, and the result is a bound method;
- reached through a **class** (`object.__getattribute__`, `Problem.__getattribute__`), nothing is bound — you get the plain function/descriptor, so **you** pass the receiver.

Because the hook is written as `object.__getattribute__(…)`, it takes the second route: the name is fetched from the class `object`, and the receiver is supplied by the call itself.
That receiver is `self` — the problem object — never `object`. `object` is only *where the function was fetched from*.

> [!tip]
> Two roles, easy to merge: the class you fetch *from* (`object`) and the object you hand *in* (`self`).
> `super()` works the same way — it is a place to look, not the object you operate on.

Demo (real output):

```python
from tsplib_parser.models import StandardProblem, Problem

p = StandardProblem()

print("type(object.__getattribute__)       ->", type(object.__getattribute__).__name__)
print("classmethod?                        ->", isinstance(object.__dict__["__getattribute__"], classmethod))
print("type(Problem.__getattribute__)      ->", type(Problem.__getattribute__).__name__)
print("type(p.__getattribute__)            ->", type(p.__getattribute__).__name__)
print("p.__getattribute__.__self__ is p    ->", p.__getattribute__.__self__ is p)
print("Problem.__getattribute__(p, '__class__') ->", Problem.__getattribute__(p, "__class__").__name__)
print("object.__getattribute__(p, '__class__')  ->", object.__getattribute__(p, "__class__").__name__)
```

```text
type(object.__getattribute__)       -> wrapper_descriptor
classmethod?                        -> False
type(Problem.__getattribute__)      -> function
type(p.__getattribute__)            -> method
p.__getattribute__.__self__ is p    -> True
Problem.__getattribute__(p, '__class__') -> StandardProblem
object.__getattribute__(p, '__class__')  -> StandardProblem
```

The `method` line is the bound case (`__self__` is `p`); the last two lines are the unbound case, where the receiver is written out by hand.

> [!note]
> Why the two names differ: `Problem.__getattribute__` reaches the **function** stored on the class — nothing is bound, which is why it prints as `function`. `p.__getattribute__` reaches that same function through an *instance*, so the descriptor protocol binds it and returns a `method` whose `__self__` is `p`.
> Only the bound form pre-fills `self`; the unbound form needs it passed in by hand — which is exactly what `object.__getattribute__(self, name)` does. `object`'s version is written in C, so the same two cases print as `wrapper_descriptor` (on the class) and `method-wrapper` (bound on an instance); the rule is the same.

### Is reaching for a base implementation an antipattern?

No. `Base.method(self, …)` is an ordinary, documented pattern, not a back door: it calls one specific implementation with the receiver written out.
It is safe here because `object` sits in **every** class's MRO, so the attribute is always found and the call always fits any `self`.

| Written | Means | Which implementation |
| --- | --- | --- |
| `Base.method(self, …)` | the function stored on `Base`, receiver passed in | always `Base`'s, whatever the MRO |
| `super().method(…)` | resume the MRO *after* the current class | the next class that defines it |

`super()` would also work inside this hook — and would dodge the recursion too, because it resolves through the MRO rather than through `self.__getattribute__`.
The explicit `object.` is preferred for two reasons: the intent is *exactly* the language default, not "whoever happens to be next" (a subclass that mixed in its own `__getattribute__` would move where `super()` lands, but not where `object.` lands); and it names the target instead of making the reader reconstruct the MRO.

> [!note]
> Does reversing the MRO reach `object`? Yes — and that is the point: `object` is last, so reversing puts it **first**.
> Measured below: the first hit is `Problem` forwards and `object` in reverse.
>
> But a reverse walk re-implements something you can just name: `object.__getattribute__` **is** "the last MRO entry, taken directly". Two reasons not to loop for it — you would have to bind the function yourself (`getattr(klass, name).__get__(self, type(self))`), and the reversed order is the *wrong* rule for ordinary lookup, which walks **forward** and stops at the most derived hit. The reversed walk belongs to `FileMeta`'s field merge, where the goal is the opposite: let the child overwrite the parent — see [metaclasses-new-mro.md — *Why the loop reverses the MRO*](./metaclasses-new-mro.md#why-the-loop-reverses-the-mro).

Demo (real output) — the base call, `super()` inside a `__getattribute__`, the keyword check, and the MRO:

```python
import keyword
from tsplib_parser.models import StandardProblem, Problem

print("iskeyword('cls' / 'self' / 'mcs') ->",
      keyword.iskeyword("cls"), keyword.iskeyword("self"), keyword.iskeyword("mcs"))

class Base:
  def greet(self): return "Base"
class Child(Base):
  def greet(self): return "Child+" + Base.greet(self)
print("Child().greet()                   ->", Child().greet())

class A:
  def __getattribute__(self, name):
    return super().__getattribute__(name)
class B(A): pass

b = B()
b.z = 1

print("super() inside the hook           ->", b.z)

print("Problem.__mro__                   ->", [c.__name__ for c in Problem.__mro__])
print("type(object().__getattribute__)   ->", type(object().__getattribute__).__name__)

def first_hit(order, name):
  for klass in order:
    if name in klass.__dict__:
      return klass.__name__

mro = StandardProblem.__mro__
print("first hit, forward  MRO           ->", first_hit(mro, "__getattribute__"))
print("first hit, reversed MRO           ->", first_hit(reversed(mro), "__getattribute__"))
```

```text
iskeyword('cls' / 'self' / 'mcs') -> False False False
Child().greet()                   -> Child+Base
super() inside the hook           -> 1
Problem.__mro__                   -> ['Problem', 'object']
type(object().__getattribute__)   -> method-wrapper
first hit, forward  MRO           -> Problem
first hit, reversed MRO           -> object
```

The `iskeyword` line is the answer to "is `cls` reserved?": no — `cls`, `self` and `mcs` are conventions, not language keywords.
The language reserves `class`, `def`, `return` and the like. `FileMeta` already renames the slot: there it is `mcs`, because the class being built *is* a metaclass.
The two `first hit` lines answer the MRO question directly: forwards the walk stops at `Problem`, reversed it stops at `object` — because `object` is last, reversing puts it first.

### Why the instance `__dict__` is checked first

Because that is where the parsed data lives, and instance data must beat class data.
The class holds one shared `Field` object per keyword — the same object for every instance — while each instance holds its own parsed values.
Checking the class first would answer with the field's default and hide the parsed value:

```python
from tsplib_parser.models import StandardProblem

p = StandardProblem()
p.dimension = 14

def class_first(self, name):
  cls = object.__getattribute__(self, "__class__")
  try:
    field = cls.fields_by_name[name]
  except KeyError:
    return object.__getattribute__(self, name)
  return field.get_default_value()

print("instance __dict__            ->", p.__dict__)
print("p.dimension (real hook)      ->", p.dimension)
print("class_first(p, 'dimension')  ->", class_first(p, "dimension"))
```

```text
instance __dict__            -> {'dimension': 14}
p.dimension (real hook)      -> 14
class_first(p, 'dimension')  -> 0
```

The hand-written `class_first` reaches the field registry without touching `self.__dict__`, and pays for it: `14` is lost and `0` comes out.
Reading the instance dict first is what keeps a parsed value visible; the field registry is only the fallback.

The contrast is measurable, and it is what the override is buying.
The plain lookup on a field name does not return the default — it returns the `Field` object sitting on the class:

```text
p.dimension (through the override)        -> 0
object.__getattribute__(p, "dimension")   -> <tsplib_parser.models.IntegerField object at 0x7f...>
```

`Field` defines `__set_name__` but no `__get__`, so the class attribute really is the `Field` object itself; nothing turns it into a value except the hook.
That is the job `Problem.__getattribute__` does.

<details name="demos">
<summary><h5>Demo: the two dictionaries and the three answers, on a real object (copy and run)</h5></summary>

```python
from tsplib_parser.models import StandardProblem

p = StandardProblem()

# The two __dict__s are different objects.
print("instance __dict__           ->", p.__dict__)
print("class    __dict__ (size)    ->", len(StandardProblem.__dict__))
print("'dimension' in instance p   ->", "dimension" in p.__dict__)
print("'dimension' in class StandardProblem        ->", "dimension" in StandardProblem.__dict__)

# A class attribute is reachable from the instance through the class.
cls = p.__class__
print("p.__class__ is the class StandardProblem    ->", cls is StandardProblem)
print("class entry is the Field    ->", type(cls.__dict__["dimension"]).__name__)
print("registry is a class attr    ->", cls.fields_by_name is cls.__dict__["fields_by_name"])

# The three answers the hook tries, in order.
print("1. attrs = p.__dict__       ->", object.__getattribute__(p, "__dict__"))
try:
  object.__getattribute__(p, "__dict__")["dimension"]
except KeyError as e:
  print("2. attrs['dimension']       -> KeyError:", e)
field = cls.fields_by_name["dimension"]
print("3. cls.fields_by_name[...]  ->", type(field).__name__, "| keyword:", field.keyword)
print("4. field.get_default_value()->", field.get_default_value())
print("5. p.dimension              ->", p.dimension)

p.dimension = 14
print("6. after it is set          ->", p.__dict__, "| p.dimension ->", p.dimension)
```

```text
instance __dict__           -> {}
class    __dict__ (size)    -> 24
'dimension' in instance p   -> False
'dimension' in class StandardProblem        -> True
p.__class__ is the class StandardProblem    -> True
class entry is the Field    -> IntegerField
registry is a class attr    -> True
1. attrs = p.__dict__       -> {}
2. attrs['dimension']       -> KeyError: 'dimension'
3. cls.fields_by_name[...]  -> IntegerField | keyword: DIMENSION
4. field.get_default_value()-> 0
5. p.dimension              -> 0
6. after it is set          -> {'dimension': 14} | p.dimension -> 14
```

Step 5 is the payoff: nothing was parsed and *the instance's* `__dict__` is empty, yet reading the attribute still answers `0` — drawn from the class-level field, not from the object.
Step 6 shows the first answer taking over as soon as real data exists.

</details>

> [!tip]
> Because the instance dict starts empty, every field read on a fresh problem lands on step 2.
> Names that are *not* fields — `p.__class__`, `p.__dict__`, `p.as_dict` — fall through to step 3 and reach the class or the object's own storage normally.

### The constraint: it cannot read `self.__dict__`

Every attribute read on the instance goes through this method — including the reads *inside* it.
Writing the obvious version therefore loops forever:

```python
class Naive:
  def __getattribute__(self, name):
    return self.__dict__[name]      # reading self.__dict__ re-enters this same method
```

```text
Naive().whatever -> RecursionError: maximum recursion depth exceeded
```

> [!warning]
> This is the reason for the `object.` prefix in the real code.
> `self.__dict__` inside the hook is not a plain read — it is a call to the hook again.

That is why the code spells every internal read as `object.__getattribute__(self, ...)` rather than the short `self.…` form: looking the name up on the class `object` skips the override and reaches the real thing.
The same applies to reading `self.__class__` — written the short way it re-enters the hook as well, because the nested call needs `self.__class__` too.
Measured, with the recursion limit lowered to make it visible: `RecursionError: maximum recursion depth exceeded` after 199 re-entries.

### When the third answer is reached

The whole method is two `try` blocks in a row, and the split is not cosmetic:

```python
  def __getattribute__(self, name: str) -> Any:
    # check for a value like normal
    try:
      attrs: dict[str, Any] = object.__getattribute__(self, "__dict__")
      return attrs[name]
    except KeyError:
      pass

    # value missing, so try to return the default
    # for the corresponding field
    try:
      cls = object.__getattribute__(self, "__class__")
      field = cls.fields_by_name[name]
    except KeyError:
      # no field, so get the attribute normally (will raise AttributeError)
      return object.__getattribute__(self, name)
    else:
      return field.get_default_value()
```

Each stage lives in its own block because the same exception means two different things:

| Block | `KeyError` means | What happens next |
| --- | --- | --- |
| first `try` | the name was not parsed into this instance | `pass` — fall through to the field default (stage 2) |
| second `try` | the name is not a field of this class | return the ordinary lookup (stage 3) |

Merging them into a single `try/except` collapses those two reactions into one, and stage 2 disappears — a miss on the instance dict jumps straight to the ordinary lookup:

```python
from tsplib_parser.models import StandardProblem

def merged(self, name):          # WRONG: one try for both questions
  try:
    return object.__getattribute__(self, "__dict__")[name]
  except KeyError:
    return object.__getattribute__(self, name)

p = StandardProblem()
print("merged(p, 'dimension') ->", merged(p, "dimension"))
print("p.dimension (real)     ->", p.dimension)
```

```text
merged(p, 'dimension') -> <tsplib_parser.models.IntegerField object at 0x7f...>
p.dimension (real)     -> 0
```

The merged version never returns the *default*; worse, it hands the caller the class-level `Field` object itself, because the ordinary lookup finds `dimension` on the class and stops there. The second `try` is what makes the default reachable at all.

With the real method, the same code stops at a different stage per object:

```text
Problem().dimension                 # no fields at all
  1. attrs = {}                     -> KeyError: 'dimension'       caught, continue
  2. fields_by_name = {}            -> KeyError: 'dimension'       caught, continue
  3. object.__getattribute__(self,…) -> AttributeError: 'Problem' object has no attribute 'dimension'

StandardProblem().dimension         # a field exists, nothing parsed
  1. attrs = {}                     -> KeyError: 'dimension'       caught, continue
  2. fields_by_name['dimension']    -> found (IntegerField)        return its default, 0

StandardProblem.parse('…DIMENSION: 3…').dimension
  1. attrs['dimension']             -> 3                          return 3
```

A `KeyError` never leaves the method: each one is caught by the block that understands it.
The only exception a caller can see is the `AttributeError` from stage 3 — and only for a name that is neither parsed, nor a field, nor an ordinary attribute.

Stage 3 serves every attribute that is *not* a field — `as_dict`, `parse`, `__class__`, `__dict__`.
A parsed field value is answered by stage 1, long before stage 3 is considered.

> [!note]
> `cls` is not a keyword — just the conventional name for "the class". The same slot is spelled `mcs` in `FileMeta.__new__`, where the class being built is a metaclass.

## What the behaviour looks like and what it costs

Live values on the real class:

```text
empty instance __dict__            -> {}
p.dimension (never set)            -> 0        the default, not an entry in __dict__
'default' defined on IntegerField  -> 0
'default' defined on Field         -> None
```

The buy is that an unset field reads as its type's empty value instead of raising. That single decision is what makes the mutating-instance design dangerous — [factory-pattern.md](./../practical/factory-pattern.md#alternative-design-with-a-mutating-instance-method) — and it is also what lets `as_dict` compare a value against `field.get_default_value()` to decide whether to include it.

The cost is that the hook runs on every attribute access on every problem object, including `problem.dimension` after parsing has set it. That is the price of "unset fields answer instead of raising".

## Why a default may be a callable

Several field classes declare `default` as a callable rather than as a literal value, and `get_default_value()` calls it, so each lookup builds a fresh container instead of handing out one object shared by every instance. Which field uses which default is tabulated in [descriptors-fields.md](./descriptors-fields.md#the-field-object-keyword-options-default).

## Connections

### Links out

- [descriptors-fields.md](./descriptors-fields.md#the-field-object-keyword-options-default) — the field objects whose defaults this hook returns.
- [descriptors-fields.md](./descriptors-fields.md#the-two-registries) — the `fields_by_name` map step 2 reads.
- [factory-pattern.md](./../practical/factory-pattern.md#alternative-design-with-a-mutating-instance-method) — the design decision this behaviour makes dangerous.
- [classes-instances-cls.md](./classes-instances-cls.md#whether-calling-the-class-changes-the-class-itself) — which dict instantiation fills, and proof the class dict stays put.
- [metaclasses-new-mro.md](./metaclasses-new-mro.md#creating-a-class-versus-instantiating-it) — who fills the class dict, at import.
- [models.md](../../../src/tsplib_parser/models.md#the-four-event-creation-chain) — the package overview.
- [README.md](./../README.md) — the map of content for this series.

> [!tip]
> Links here point at the exact section (`file.md#section-slug`), not just the file — follow the anchor to land on the paragraph that carries the explanation.

### Backlinks

Files that link here:

- [descriptors-fields.md](./descriptors-fields.md#the-field-object-keyword-options-default) — "how that value reaches the caller".
- [factory-pattern.md](./../practical/factory-pattern.md#alternative-design-with-a-mutating-instance-method) — "the default-returning lookup that makes the mutating design dangerous".
- [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md#the-membership-test) — the unset-versus-default distinction its membership test depends on.
- [classes-instances-cls.md](./classes-instances-cls.md#whether-calling-the-class-changes-the-class-itself) — "what that shadowing does to reading".
