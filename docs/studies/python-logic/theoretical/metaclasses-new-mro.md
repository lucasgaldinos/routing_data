---
title: Metaclasses and __new__
description: >
  The class-creation machinery behind FileMeta: the __new__-then-__init__ lifecycle, the four-strength example ladder (value, identity, class dispatch, the class itself), the mcs parameter and the two class objects in scope, the five metaclass hooks, the merge rule behind the reversed-MRO loop, and who supplies which argument. Part of the python-logic series.
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
          First version. Extracted and rewrote §3.1, §3.2, §3.3, §3.4 and §3.6 of PARSER-DETAILS.MD: the __new__ lifecycle with the super() proxy demos, the four-example ladder with all runnable outputs, the mcs parameter and the two-class-objects demo, the metaclass hook table and order demo, the MRO reversal as a merge rule with the both-ways demo, and the metaclass argument chain.
related_files:
  - [PARSER-DETAILS.MD](../../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.py](../../../../src/tsplib_parser/models.py)
  - [classes-instances-cls.md](./classes-instances-cls.md)
  - [descriptors-fields.md](./descriptors-fields.md)
  - [factory-pattern.md](./../practical/factory-pattern.md)
tags:
  - guide/metaclass
  - guide/python-oop
  - guide/class-creation
  - guide/mro
  - guide/tsplib-parser
---

# Metaclasses and `__new__`

- [Metaclasses and `__new__`](#metaclasses-and-__new__)
  + [What this file answers](#what-this-file-answers)
  + [The two hooks: `__new__` and `__init__`](#the-two-hooks-__new__-and-__init__)
  + [When to implement `__new__` in ordinary code](#when-to-implement-__new__-in-ordinary-code)
  + [The four examples: one question, four strengths](#the-four-examples-one-question-four-strengths)
    - [Example 1: deciding the value](#example-1-deciding-the-value)
    - [Example 2: deciding the identity](#example-2-deciding-the-identity)
    - [Example 3: deciding which class](#example-3-deciding-which-class)
    - [Example 4: deciding the class itself](#example-4-deciding-the-class-itself)
  + [One correction: they are not a family](#one-correction-they-are-not-a-family)
  + [Examples 3 and 4 side by side](#examples-3-and-4-side-by-side)
  + [The mcs parameter](#the-mcs-parameter)
    - [Two class objects are in scope at once](#two-class-objects-are-in-scope-at-once)
  + [Metaclass hooks beyond `__new__`](#metaclass-hooks-beyond-__new__)
  + [When to reverse the MRO](#when-to-reverse-the-mro)
  + [The call chain and the reversal are independent](#the-call-chain-and-the-reversal-are-independent)
  + [Reading the metaclass body](#reading-the-metaclass-body)
    - [Why two loops rather than a comprehension](#why-two-loops-rather-than-a-comprehension)
    - [What `super().__new__` is doing](#what-super__new__-is-doing)
    - [Why bases has to be passed](#why-bases-has-to-be-passed)
    - [The class attribute is not immutable](#the-class-attribute-is-not-immutable)
  + [Who supplies the metaclass arguments](#who-supplies-the-metaclass-arguments)
    - [Whether the class defines those parameter names](#whether-the-class-defines-those-parameter-names)
    - [Whether super() is calling type](#whether-super-is-calling-type)
    - [Whether `__new__` is calling itself](#whether-__new__-is-calling-itself)
    - [Whether FileMeta sets the attributes](#whether-filemeta-sets-the-attributes)
  + [Creating a class versus instantiating it](#creating-a-class-versus-instantiating-it)
    - [When it is necessary to make a class](#when-it-is-necessary-to-make-a-class)
    - [When a metaclass is the right tool](#when-a-metaclass-is-the-right-tool)
  + [Why the loop reverses the MRO](#why-the-loop-reverses-the-mro)
    - [Why the ordinary MRO order would not work here](#why-the-ordinary-mro-order-would-not-work-here)
  + [Connections](#connections)

## What this file answers

`FileMeta` is a short class — its `__new__` runs once per class, at import. To read them, this file builds up from ordinary `__new__` usage to the metaclass case:

- how `__new__` and `__init__` divide the work, and what `super()` really is;
- the four examples of "who decides what `Something(...)` returns", from value to class;
- what the `mcs` parameter is, and which two class objects are in scope at once;
- the five hooks a metaclass can use, and their fixed order;
- when the reversed-MRO loop is needed and what breaks without it;
- who supplies `name`, `bases` and `attrs`, and how the class statement chains to `type.__new__`.

> [!note]
> Claims verified against [`FileMeta`](../../../../src/tsplib_parser/models.py#L607-L621) and the whole of `models.py`, and every demo was run with its real output pasted. The field objects themselves are covered in [descriptors-fields.md](./descriptors-fields.md); the per-call side is [factory-pattern.md](./../practical/factory-pattern.md).

## The two hooks: `__new__` and `__init__`

Instantiating a class runs two calls, in this order:

```python
p = StandardProblem()
#  1. StandardProblem.__new__(StandardProblem)  → allocates, returns the instance
#  2. instance.__init__()                       → fills it in, returns None
```

So `__new__` **creates** the object and `__init__` **fills** an object that already exists. `__new__` is implicitly a static method, and its first parameter is the class.

The pairing on one call, including the rule for when `__init__` runs at all:

```python
p = C(1)
# C.__new__(C, 1)  → allocates, returns instance
# p.__init__(1)    → runs only if isinstance(p, C)
```

One wrong assumption is worth killing here, because it makes the examples further down look magical: `super()` does not return the parent's `__init__`, and it is not a synonym for the parent class. It returns a proxy that resolves attributes against the next class in the MRO, so inside `Meters.__new__`, `super().__new__(cls, round(value, 3))` is really `float.__new__(Meters, 1.235)`.

<details name="demos">
<summary><h5>Demo: super() is a proxy, not the parent method (copy and run)</h5></summary>

```python
class A:
    def m(self): return "A.m"

class B(A):
    def m(self):
        s = super()
        print("B.__mro__   ->", [c.__name__ for c in B.__mro__])
        print("super()     ->", s, "| type:", type(s).__name__)
        print("super().m   ->", s.m)
        return "B.m + " + s.m()

print("B().m()     ->", B().m())
```

```text
B.__mro__   -> ['B', 'A', 'object']
super()     -> <super: <class 'B'>, <B object>> | type: super
super().m   -> <bound method A.m of <__main__.B object at 0x…>>
B().m()     -> B.m + A.m
```

That first printed line is what usually confuses people, so read it in two halves:

- `<class 'B'>` is the class you were standing in when you called `super()`. It is where the search **starts**, not where the method comes **from**.
- `<B object>` is the object the proxy is bound to, so whatever method it finds is still called with that same `self`.
- The search then continues after `B` in the MRO, which is `['B', 'A', 'object']`, so `s.m` lands on `A.m`. That is why the repr names `B` while the method it returns belongs to `A`.

And what `super()` does **not** do: it does not create, initialize or copy anything, and it does not call `__init__` or `__new__`. It is only a lookup object. Something happens when you call a method on it — `super().__init__(…)` finds and calls the next `__init__`, `super().__new__(cls, …)` finds and calls the next `__new__` — which is why `type(s)` is `super` rather than `A` or `B`.

</details>

The second half of the mechanic matters just as much: the first argument passed to `super().__new__` decides the type of the object that comes back, and that argument has to be a subtype of the class whose `__new__` is running.

<details name="demos">
<summary><h5>Demo: the first argument must be a subtype of the class being constructed (copy and run)</h5></summary>

```python
class Meters(float):
    def __new__(cls, value):
        return super().__new__(cls)     # cls here is Meters

try:
    float.__new__(int, 1)               # int is not a subtype of float
except TypeError as e:
    print("TypeError:", e)
```

```text
TypeError: float.__new__(int): int is not a subtype of float
```

The rounding variant of this same idea is [Example 1](#example-1-deciding-the-value) further down.

</details>

## When to implement `__new__` in ordinary code

Only when the question is "how is this object made", not "what does it hold":

- immutable built-in subclasses (`int`, `str`, `tuple`), where the value is frozen before `__init__` runs;
- singletons, caches or flyweights, where an existing instance may be returned instead of a new one;
- factories that return a different type than the class being called;
- metaclasses, which is the case in this module.

Rule of thumb: default to `__init__`; reach for `__new__` only when creation itself needs control.

## The four examples: one question, four strengths

All four examples answer one question — *when `Something(...)` is called, who decides what comes back?* — and they differ only in **when** they get to decide and **what** they are allowed to change. Read them in that order:

| # | Example | The decision it makes | Runs |
| --- | --- | --- | --- |
| 1 | `Meters(float)` | the **value** the object carries | once per instance |
| 2 | `Single` | whether a new object exists at all — its **identity** | once per call, and the later calls create nothing |
| 3 | `Base.__new__` dispatch | which **class** the object belongs to | once per instance |
| 4 | `MiniMeta.__new__` | what the **class itself** contains | once per class, at import |

The first three are the same hook used at three different strengths; the fourth is a different hook acting on a different object. Every block below is runnable on its own.

### Example 1: deciding the value

`__new__` runs before the value is copied into the object, so it can still choose that value. `__init__` runs after, which is why it cannot:

```python
class Meters(float):
  def __new__(cls, value: float) -> "Meters":
    return super().__new__(cls, round(value, 3))    # super() is float here


class Bad(float):
  def __init__(self, value):
    self.value = round(value, 3)                    # the value is already copied


print(Meters(1.23456), "|", float(Meters(1.23456)))
print(Bad(1.23456), "| .value attr:", Bad(1.23456).value)
```

```text
1.235 | 1.235
1.23456 | .value attr: 1.235
```

`Bad` ends up with two sources of truth: `1.23456` as the number itself and `1.235` as a separate attribute, because `__init__` runs after the value has been copied into an immutable object. `__new__` runs before that copy, so it can still choose the value.

### Example 2: deciding the identity

The same hook, used to refuse to create a second object. Nothing is mutated; the existing instance is simply returned again:

```python
class Single:
  _instance = None

  def __new__(cls):
    if cls._instance is None:
      print("  built a new one")
      cls._instance = super().__new__(cls)
    else:
      print("  reused the existing one")
    return cls._instance


a = Single()
b = Single()
print("a is b ->", a is b)
```

```text
  built a new one
  reused the existing one
a is b -> True
```

### Example 3: deciding which class

Here the hook does not just decorate the object being built, it returns an instance of a **different** class than the one that was called:

```python
class Base:
  def __new__(cls, raw):
    target = Special if raw.get("TYPE") == "XRAY" else cls
    print(f"  __new__ got cls={cls.__name__}, choosing {target.__name__}")
    return super().__new__(target)

  def __init__(self, raw):
    self.raw = raw
    print(f"  __init__ ran with self of type {type(self).__name__}")


class Special(Base):
  pass


x = Base({"TYPE": "XRAY"})
y = Base({"TYPE": "TSP"})
print("x is a", type(x).__name__, "| y is a", type(y).__name__)
```

```text
  __new__ got cls=Base, choosing Special
  __init__ ran with self of type Special
  __new__ got cls=Base, choosing Base
  __init__ ran with self of type Base
x is a Special | y is a Base
```

Two details make this one work, and both are easy to get wrong. `super().__new__(target)` is `object.__new__(target)` — the class passed in decides the type of what comes back. And `__init__` still runs, because the object returned *is* an instance of `Base` (`Special` inherits from it), so the interpreter's rule "call `__init__` when the result is an instance of `cls`" is satisfied.

### Example 4: deciding the class itself

This is the case used in this module, and the only one that acts on a class rather than an instance. `MiniMeta` below is `FileMeta` reduced to its shape:

```python
from tsplib_parser.models import Field, IntegerField


class MiniMeta(type):
  def __new__(mcs, name, bases, attrs, **kw):
    cls = super().__new__(mcs, name, bases, attrs)      # builds a CLASS, not an instance
    cls.registry = {k: v for k, v in vars(cls).items() if isinstance(v, Field)}
    return cls


class MiniProblem(metaclass=MiniMeta):
  a = IntegerField("A")


print({k: type(v).__name__ for k, v in MiniProblem.registry.items()})
```

```text
{'a': 'IntegerField'}
```

The print runs with no instance in existence anywhere in the program — the dictionary was built while the `class` statement executed. Where the parameters come from, and in which order they arrive, is [later in this file](#who-supplies-the-metaclass-arguments).

## One correction: they are not a family

`enum.EnumMeta`, `abc.ABCMeta` and `FileMeta` are **not** a family in any formal sense — no shared base, no shared ancestor beyond `type`. What they share is the hook and the kind of work: `EnumMeta` builds the member table at class-creation time, `ABCMeta` records which methods are still abstract, `FileMeta` records which attributes are fields. The `typing` internals also use metaclasses, but for caching and `X | Y` subscripting, so that comparison was the weakest of the three and is dropped.

## Examples 3 and 4 side by side

No, they are not used together. They are different levels with unrelated mechanisms:

| | Example 3, on `Base` | Example 4, on `MiniMeta` |
| --- | --- | --- |
| Fires | on every `Problem(raw)` call | once, when the `class` statement executes |
| First parameter is | the class you called | the metaclass |
| Can return | an instance of any class | a class |
| Purpose | pick the concrete type per input | decorate the class at definition |

They never interact — one lives in the class body and fires per instance, the other lives on the metaclass and fires once per class definition — so both can be defined on the same class without conflict. Neither is used in this repository: `src/` has exactly one `__new__` ([`FileMeta.__new__`, models.py:607](../../../../src/tsplib_parser/models.py#L607)); Examples 1, 2 and 3 are pedagogy, not repo code. `StandardProblem.parse` is a third pattern — a classmethod factory — described in [factory-pattern.md](./../practical/factory-pattern.md).

## The mcs parameter

```python
def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type:
```

`mcs` is to a metaclass what `self` is to an instance. The twist is that a metaclass builds classes, so its "instances" are classes:

| Layer | First parameter | At call time it is |
| --- | --- | --- |
| `def method(self, x)` | `self` | an instance of the class |
| `@classmethod def cmethod(cls, x)` | `cls` | the class |
| `class Meta(type): def __new__(mcs, ...)` | `mcs` | the metaclass, a class that makes classes |

It is called `mcs` and not `cls` because inside `FileMeta.__new__` the name `cls` is needed for a different object: the class being built, which is the return value of `super().__new__` at line 608. Two objects, two names.

### Two class objects are in scope at once

This is the part that makes the parameter list feel arbitrary, so separate the two objects from the three inputs:

```text
mcs    the metaclass — the object whose method is running        (FileMeta)
cls    the class being built — return of super().__new__         (StandardProblem)
name   a string: "StandardProblem"             — an input, not a class
bases  a tuple of classes: (Problem,)           — an input
attrs  a plain dict: the body's namespace       — an input
```

Only `mcs` and `cls` are classes. `name`, `bases` and `attrs` are the raw material that `super().__new__` turns into `cls`:

<details name="demos">
<summary><h5>Demo: mcs is the metaclass, cls is a different class (copy and run)</h5></summary>

```python
class Meta(type):
  def __new__(mcs, name, bases, attrs, **kw):
    print("mcs is Meta        ->", mcs is Meta)
    print("mcs.__name__       ->", mcs.__name__)
    return super().__new__(mcs, name, bases, attrs)


class Thing(metaclass=Meta):
  pass


print("type(Thing) is Meta     ->", type(Thing) is Meta)
print("type(Thing()) is Thing  ->", type(Thing()) is Thing)
```

```text
mcs is Meta        -> True
mcs.__name__       -> Meta
type(Thing) is Meta     -> True
type(Thing()) is Thing  -> True
```

The last two lines hold the whole confusion in one place: `type` answers two different questions depending on what it is given. A **class** gives you its metaclass; an **instance** gives you its class.

</details>

## Metaclass hooks beyond `__new__`

No, a metaclass does not always use `__new__`. `__new__` on the metaclass is where the **class object** is built, which is why it is the hook this module needs, but it is one of five places a metaclass can act, and only the first two run at class-creation time:

| Hook | Runs | What it is for |
| --- | --- | --- |
| `__prepare__` (classmethod) | before the body executes | supplying the namespace dict the class body writes into |
| `__new__` | at class creation | building the class object, then adding attributes to it |
| `__init__` | at class creation, right after | post-processing a class that already exists |
| `__call__` | on every instantiation | controlling what `SomeClass(...)` returns |
| `__set_name__` / `__init_subclass__` | on the class or its children | the lighter alternatives that need no metaclass |

The order is fixed by the interpreter, and it is visible in one run:

<details name="demos">
<summary><h5>Demo: the hook order, and the lighter alternative (copy and run)</h5></summary>

```python
class Watch(type):
  @classmethod
  def __prepare__(mcs, name, bases, **kw):
    print(f"  __prepare__({name})")
    return {}

  def __new__(mcs, name, bases, attrs, **kw):
    print(f"  __new__({name})")
    return super().__new__(mcs, name, bases, attrs)

  def __init__(cls, name, bases, attrs, **kw):
    print(f"  __init__({name})")

  def __call__(cls, *a, **kw):
    print(f"  __call__({cls.__name__})")
    return super().__call__(*a, **kw)


class Watched(metaclass=Watch):      # the class statement
  pass

Watched()                            # instantiation


class Base:
  def __init_subclass__(cls, **kw):
    print(f"  __init_subclass__ fired for {cls.__name__}, kw={kw}")


class Child(Base, tag="x"):
  pass
```

```text
  __prepare__(Watched)
  __new__(Watched)
  __init__(Watched)
  __call__(Watched)
  __init_subclass__ fired for Child, kw={'tag': 'x'}
```

Note that `__prepare__` receives the class **name** and not the class, because the class does not exist yet; and that `Base.__init_subclass__` fires for `Child` only. That last line is the reason a metaclass is not the only option — see [When a metaclass is the right tool](#when-a-metaclass-is-the-right-tool).

</details>

## When to reverse the MRO

The reversal is not a metaclass rule, it is a **merge** rule, and it is needed only when two conditions hold at once:

1. you are collecting contributions from more than one class in the hierarchy; and
2. a subclass may redefine something a base class also defines.

When both hold, walking base-to-subclass and letting each write overwrite the last gives "most derived wins" for free. When only one holds, the reversal buys nothing:

| Situation | Reverse? | Why |
| --- | --- | --- |
| build a registry from `cls.__dict__` only | no | one class, no competition between classes |
| collect fields across the hierarchy, subclasses may override | yes | this is `FileMeta`, and it is what the next section covers |
| call a parent implementation | no | that is `super()`, which walks the MRO forward |
| copy base-class settings that children never override | either | the result is identical; the reverse just costs one call to `reversed` |

This module needs both conditions, so it reverses. `Problem` and `StandardProblem` alone would not need it; the loop is there for the `XRayProblem` case, where a child re-declares a parent's field.

Who calls it: `FileMeta` is itself a class, so `Meta(...)` goes `type(Meta).__call__` → `Meta.__new__(Meta, ...)`. That is interpreter bootstrapping; it is never written by hand in application code.

## The call chain and the reversal are independent

Neither affects the other, in both halves of the question. Both the name of that first argument and the reversal inside the loop belong to `FileMeta`, but they are otherwise unrelated:

- the `Meta.__new__(Meta, ...)` shape is how **CPython creates any class**, with or without a metaclass. With no metaclass the metaclass is `type` and the same call happens with `type` in that first slot; with `class Meta(type)` it is `Meta`. It has nothing to do with `FileMeta` or with this module.
- the reversed MRO loop runs *inside* `__new__`, after the class already exists, and only decides which field declarations win. Writing that loop, deleting it, or reversing the other way changes nothing about who calls `__new__`.

The proof is a metaclass with no loop at all, which still receives `name`, `bases` and `attrs`:

<details name="demos">
<summary><h5>Demo: a metaclass with no MRO work still gets the arguments (copy and run)</h5></summary>

```python
class Plain(type):
  def __new__(mcs, name, bases, attrs, **kw):
    print(f"  Plain.__new__  mcs={mcs.__name__} name={name} bases={bases} kw={kw}")
    return super().__new__(mcs, name, bases, attrs)

  def __init__(cls, name, bases, attrs, **kw):
    print(f"  Plain.__init__ cls={cls.__name__}")
    super().__init__(name, bases, attrs)


class Alpha(metaclass=Plain, tag="hello"):    # the class statement
  x = 1

Beta = Plain("Beta", (), {"y": 2})            # the same constructor, by hand
print("Alpha.x ->", Alpha.x, "| Beta.y ->", Beta.y, "| Beta() ->", Beta())
```

```text
  Plain.__new__  mcs=Plain name=Alpha bases=() kw={'tag': 'hello'}
  Plain.__init__ cls=Alpha
  Plain.__new__  mcs=Plain name=Beta bases=() kw={}
  Plain.__init__ cls=Beta
Alpha.x -> 1 | Beta.y -> 2 | Beta() -> <__main__.Beta object at 0x…>
```

</details>

The last three lines are the direct answer: the same `Plain.__new__` that the class statement called is callable by hand, with a name, a bases tuple and a namespace dict — and the class it returns is fully usable, since `Beta.y` reads and `Beta()` instantiates. Nothing about the first argument depends on the hierarchy, and the reversed loop never enters the picture.

`name`, `bases` and `attrs` mirror the `class` statement:

| Parameter | Value for `class StandardProblem(Problem):` |
| --- | --- |
| `name` | `"StandardProblem"` |
| `bases` | `(Problem,)` |
| `attrs` | the namespace the class body just filled: the 18 field objects, `parse`, `create_explicit_matrix` |

## Reading the metaclass body

### Why two loops rather than a comprehension

A comprehension gives the identical result — the same 18 field objects, not copies:

<details name="demos">
<summary><h5>Demo: the comprehension and the nested loops agree (copy and run)</h5></summary>

```python
from tsplib_parser.models import Field, StandardProblem

loops: dict[str, Field] = {}
for klass in reversed(StandardProblem.__mro__):
  for key, value in vars(klass).items():
    if isinstance(value, Field):
      loops[key] = value

comp: dict[str, Field] = {
  key: value
  for klass in reversed(StandardProblem.__mro__)
  for key, value in vars(klass).items()
  if isinstance(value, Field)
}

print("two loops     ->", len(loops), "fields")
print("comprehension ->", len(comp), "fields")
print("identical     ->", loops == comp, "| same objects:", all(loops[k] is comp[k] for k in loops))
```

```text
two loops     -> 18 fields
comprehension -> 18 fields
identical     -> True | same objects: True
```

</details>

The loops are kept separate because they do different jobs: the **outer** loop walks the hierarchy, the **inner** loop walks one class's namespace. Nested, the reading order is "for each class from base to child, for each attribute in it, keep the fields" — and the nesting is exactly what shows that the *hierarchy* is where the precedence is decided. Collapsing both into one comprehension hides which part is doing the work. Nothing here is a performance choice: this runs once per class, at import.

### What `super().__new__` is doing

Nothing is being initialized, and nothing exists yet. Inside `FileMeta.__new__`, `super()` resolves to `type` — the MRO is `FileMeta → type → object` — so the call is `type.__new__(mcs, name, bases, attrs)`, the C routine that **allocates the class object** and installs the namespace into it. Its return value is `cls`, which is why the assignment is the first line of the body.

- It is not "initializing the parent". `__new__` builds; `__init__` initializes. `FileMeta` defines no `__init__`, so the inherited `type.__init__` runs at the end of class creation and does nothing.
- `super().__new__` reads `__new__` from the next class **after** `FileMeta`, not from `FileMeta` itself — so it cannot recurse into the same function.

### Why bases has to be passed

Because `type.__new__` cannot build a class without knowing what it inherits from. That tuple becomes `__bases__`, and from it CPython computes `__mro__` — the list that makes attribute lookup, `super()` and `isinstance` work at all. Passing an empty tuple is legal and produces a class with no bases beyond `object`; passing the wrong one produces a class with the wrong hierarchy.

On "are they automatically passed through?" — the **values** are automatic, the **names** are yours. CPython supplies three positional values when the `class` statement runs, in the order fixed by `type.__new__`'s signature. The names `mcs`, `name`, `bases`, `attrs` are the author's choice, and renaming them changes nothing:

<details name="demos">
<summary><h5>Demo: what CPython hands the metaclass, with arbitrary parameter names (copy and run)</h5></summary>

```python
class Spy(type):
  def __new__(mcs, whatever, these, are, **kwargs):
    print("mcs is Spy     ->", mcs is Spy)
    print("arg 1 (name)   ->", whatever)
    print("arg 2 (bases)  ->", these)
    print("arg 3 (attrs)  ->", sorted(are))
    print("class kwargs   ->", kwargs)
    return super().__new__(mcs, whatever, these, are)


class Base:
  pass


class Child(Base, metaclass=Spy, label="x"):
  dimension = 14

print("Child.dimension ->", Child.dimension)
print("type(Child)     ->", type(Child).__name__)
```

```text
mcs is Spy     -> True
arg 1 (name)   -> Child
arg 2 (bases)  -> (<class '__main__.Base'>,)
arg 3 (attrs)  -> ['__module__', '__qualname__', 'dimension']
class kwargs   -> {'label': 'x'}
Child.dimension -> 14
type(Child)     -> Spy
```

</details>

Two details in that output are worth keeping. First, `attrs` is an ordinary `dict` and it holds only what the body wrote: `__module__`, `__qualname__` and the declared names, plus anything else the author put there. Second, the `label="x"` reaches the metaclass as a **keyword** argument, because `class Child(Base, metaclass=Spy, label="x")` forwards everything after the bases; `FileMeta` accepts `**kwargs` for exactly this reason, so class keyword arguments do not raise.

### The class attribute is not immutable

The field is a rule, not a frozen value: one shared object on the class, while each instance keeps its data in its own `__dict__`.

| | Example | Shared between instances? |
| --- | --- | --- |
| the field, a class attribute | `dimension = IntegerField("DIMENSION")` | yes — one object on the class |
| the value, an instance attribute | `{'name': 'a', 'dimension': 2}` in `a.__dict__` | no — each instance owns its own dict |

Assignment on an instance shadows the class attribute **for that one object** and leaves the class untouched; the class-level `Field` stays intact. The runnable check for this lives in [classes-instances-cls.md](./classes-instances-cls.md), and [fields-vs-dataclasses.md](./../practical/fields-vs-dataclasses.md) explains why the declaration has to stay on the class.

## Who supplies the metaclass arguments

CPython does, positionally. The parameter names belong to the author; the order is fixed by the signature of `type.__new__`, so renaming `name` to anything else changes nothing.

The exact chain for the line `class StandardProblem(Problem):`

```ascii
1. CPython executes the class body in a fresh dict                      → attrs
2. it determines the metaclass: the most derived metaclass of the bases
      type(Problem) is FileMeta  →  so StandardProblem uses FileMeta
3. the class statement is equivalent to:
      StandardProblem = FileMeta("StandardProblem", (Problem,), attrs)
4. FileMeta(...) → type(FileMeta).__call__ → FileMeta.__new__(FileMeta, name, bases, attrs)
                                                  mcs   name    bases   attrs
5. line 608 → type.__new__(mcs, name, bases, attrs)  → the class object
6. lines 618-619 → two attributes assigned on that class:
      fields_by_name, fields_by_keyword
7. FileMeta.__init__(cls, name, bases, attrs) — type.__init__, a no-op here
```

This chain is the same sequence seen from other angles: the per-call view of the machinery is [factory-pattern.md](./../practical/factory-pattern.md); why the parse method takes the class rather than an instance is [classes-instances-cls.md](./classes-instances-cls.md); where `__set_name__` sits inside step 4 is [descriptors-fields.md](./descriptors-fields.md); and the registry the last two steps produce is covered there too.

### Whether the class defines those parameter names

No. They are the author's choice, matching the order that `type.__new__` will pass them in.

### Whether super() is calling type

Yes. `FileMeta(type)`, so `super()` inside its `__new__` resolves to `type`, and `super().__new__(mcs, name, bases, attrs)` is `type.__new__(...)` — CPython's C routine that allocates the class object and installs its `__dict__`.

### Whether `__new__` is calling itself

No. Three different `__new__` functions are involved, and none is recursive:

| Call | Which function | When |
| --- | --- | --- |
| `FileMeta.__new__(...)` | this module's code, models.py:607 | class creation, at import |
| `super().__new__(...)` | `type.__new__`, in C | once, inside the call above |
| `StandardProblem.__new__` | `object.__new__`, in C | on every `StandardProblem()` |

`super().__new__` looks `__new__` up on `type` — the next entry in the MRO after `FileMeta` — not on `FileMeta`.

### Whether FileMeta sets the attributes

Not the field attributes. Those were already installed by `type.__new__`, which copied them out of `attrs`. Lines 618-619 add **two new** attributes, `fields_by_name` and `fields_by_keyword`, which point at the same field objects. No field object is created inside `FileMeta`, and no problem instance is touched — see [descriptors-fields.md](./descriptors-fields.md) for how the field objects themselves come into existence.

## Creating a class versus instantiating it

Yes — creating a class **is** instantiating it: a class is an instance of its metaclass. Verified on this module:

```text
type(Problem)                            -> FileMeta
type(StandardProblem)                    -> FileMeta
FileMeta.__mro__                         -> ['FileMeta', 'type', 'object']
isinstance(Problem, FileMeta)            -> True
isinstance(StandardProblem(), FileMeta)  -> False
```

<details name="demos">
<summary><h5>Demo: a class is an instance of its metaclass (copy and run)</h5></summary>

```python
class Meta(type):
    pass

class Point(metaclass=Meta):
    x = 1

print("type(Point)                ->", type(Point).__name__)
print("type(Point())              ->", type(Point()).__name__)
print("isinstance(Point, Meta)    ->", isinstance(Point, Meta))
print("isinstance(Point(), Meta)  ->", isinstance(Point(), Meta))
print("Meta.__mro__               ->", [c.__name__ for c in Meta.__mro__])
```

```text
type(Point)                -> Meta
type(Point())              -> Point
isinstance(Point, Meta)    -> True
isinstance(Point(), Meta)  -> False
Meta.__mro__               -> ['Meta', 'type', 'object']
```

</details>

Two rules explain all five lines, and mixing them up is what makes metaclasses feel strange:

- `type(x)` answers "what built x". For an ordinary object that is its class; for a class it is its metaclass. So `type(Point())` is `Point`, while `type(Point)` is `Meta`.
- `isinstance(x, C)` is `True` when `type(x)` is `C` or a subclass of `C`. A `Point()` has type `Point`, and `Meta` is not in `Point.__mro__`, so `isinstance(Point(), Meta)` is `False`. `Point` itself has type `Meta`, so `isinstance(Point, Meta)` is `True`.
- The two checks never cross levels: being a class does not make `Point` an instance of `type` through its constructor. It is still worth knowing that `Meta` inherits from `type`, so `isinstance(Point, type)` is also `True` — every class is an instance of `type` or of a subclass of it.

There is no separate "class creation" mechanism, only the same operation at two levels:

| Expression | Instantiates | Result |
| --- | --- | --- |
| `FileMeta("X", bases, attrs)` | `FileMeta` | a **class** |
| `StandardProblem()` | `StandardProblem` | a **problem** |

A class was created by calling `type.__new__`: `super()` inside `FileMeta` is `type`, so that call is what allocates the class. The two assignments that follow add attributes to the brand-new class object, and those attributes then live on the class for the rest of the process — which is why every later `parse` call can read `fields_by_keyword` without recomputing anything.

### When it is necessary to make a class

There are exactly two ways to make a class, and only the second is manual:

```python
class Point:                          # 1. the class statement — the metaclass hook fires
    x = 1

Point = type("Point", (), {"x": 1})   # 2. the three-argument type()
```

In this codebase nothing calls `FileMeta.__new__` directly. The metaclass is a hook into class creation that was going to happen anyway, so "making a class" is not something opted into at parse time.

### When a metaclass is the right tool

You reach for a metaclass when every class in a family must derive something from its own body at definition time:

| System | Derived at class creation |
| --- | --- |
| Django ORM | `class Meta` options, field list |
| pydantic, v1 and v2 | validators and the generated `__init__` signature, through `ModelMetaclass` |
| attrs | not a metaclass — a class decorator that rewrites the class at decoration time and fills the same role |
| `tsplib95` and this port's `FileMeta` | the keyword-to-field index |
| plugin systems | auto-registration of subclasses |

The lighter alternative is `__init_subclass__` on `Problem`: it fires once for `StandardProblem` and could build the same registry with no metaclass plumbing. Its trade-off is that it does not fire for `Problem` itself, so the base class would have no registry and every lookup site would need a fallback. This repository uses neither — there is no `__init_subclass__` in `src/`.

The honest summary, spelled out with the failure it prevents: the index is never written by hand — declaring a keyword makes `FileMeta` add it to `fields_by_keyword` and `fields_by_name` in the same pass. What that prevents is a silent failure rather than a loud one: unknown keywords are tolerated by design, so a keyword that never reached the map would not raise — its value would simply not be parsed into the object.

That tolerance is deliberate and one-sided, which is worth stating plainly because from the outside it can look like a missing check:

- **Unknown keywords are ignored.** The spec allows extensions, so a line naming a keyword the parser does not know is skipped rather than reported. This is the tolerant half.
- **Known keywords and known section bodies are not tolerated.** If a value the parser recognizes cannot be converted, the failure is recorded together with its line context and raised as one `ParseError` at the end of the pass, so nothing known is lost quietly. This is the strict half, audited in [parser-pipeline.md](../../../src/tsplib_parser/parser-pipeline.md).
- **An unknown `*_SECTION` body is dropped without error**, which is the same tolerance applied to whole sections instead of single keywords.

So the parser is deliberately intolerant of malformed *known* data and deliberately tolerant of *unknown* extensions. Only the unknown path is silent, and that is exactly what makes a hand-written index dangerous rather than merely untidy: a field that never reaches the map would lose its value without raising.

## Why the loop reverses the MRO

The reversed MRO is **not** what builds `StandardProblem`. That loop builds nothing, and it runs after the class already exists — `type.__new__` returned it at line 608. The loop only reads:

```python
for klass in reversed(cls.__mro__):        # cls is the ALREADY-BUILT StandardProblem
    for key, value in vars(klass).items(): # vars() reads each class's dict
        if isinstance(value, Field):       # keep only Field objects
            fields[key] = value
```

For `StandardProblem` the traversal is:

```text
cls.__mro__            = (StandardProblem, Problem, object)
reversed(...)          = (object, Problem, StandardProblem)
vars(object)           → no Field
vars(Problem)          → no Field  (line 629 is an annotation, not a value)
vars(StandardProblem)  → 18 Field objects
```

The reversal is what makes a subclass override win, and there are two distinct failure modes:

```text
Child.__mro__                  -> ['Child', 'Base', 'object']
reversed  (base first)         -> {'a': 'A2', 'b': 'B'}      correct
not reversed (child first)     -> {'a': 'A',  'b': 'B'}      Child's override LOST
vars(cls) only, no MRO loop    -> {'a': 'A2'}                Base's 'b' LOST
```

Processing `Child` first and `Base` second lets the parent overwrite the child, so the index would disagree with normal attribute lookup, where the most derived class wins. Dropping the MRO loop entirely — reading only `vars(cls)` — loses every field the subclass inherits, since a subclass that adds one keyword would no longer see the parent's 18.

`reversed(mro)` walks base to subclass, so later writes override earlier ones and the result is exactly "most derived wins", the same ordering rule attribute lookup uses. The loop over the MRO rather than just `attrs` is also what lets a subclass add one field and still inherit the parent's registry.

### Why the ordinary MRO order would not work here

The ordinary order is the *right* rule and the wrong *loop shape*. Normal attribute lookup walks the MRO forward and **stops at the first hit**, so the most derived class wins. A forward walk that merges every class cannot stop — it has to keep visiting — and that is the difference: it overwrites instead of stopping, so the parent's later visit erases the child's override.

```text
reversed + overwrite   -> {'a': 'A2', 'b': 'B'}    correct
forward  + overwrite   -> {'a': 'A',  'b': 'B'}    child's override lost
forward  + first wins  -> {'a': 'A2', 'b': 'B'}    correct, with a membership test
```

<details name="demos">
<summary><h5>Demo: the same precedence rule, written both ways (copy and run)</h5></summary>

```python
from tsplib_parser.models import Field, IntegerField


class Base:
  a = IntegerField("A")
  b = IntegerField("B")


class Child(Base):
  a = IntegerField("A2")      # overrides Base.a


def reversed_overwrite(cls):
  out = {}
  for klass in reversed(cls.__mro__):
    for key, value in vars(klass).items():
      if isinstance(value, Field):          # swap for a narrower type to see fewer entries
        out[key] = value
  return out


def forward_first_wins(cls):
  out = {}
  for klass in cls.__mro__:
    for key, value in vars(klass).items():
      if isinstance(value, Field) and key not in out:
        out[key] = value
  return out


print({k: v.keyword for k, v in reversed_overwrite(Child).items()})
print({k: v.keyword for k, v in forward_first_wins(Child).items()})
print("normal lookup Child.a ->", Child.a.keyword)
```

```text
{'a': 'A2', 'b': 'B'}
{'a': 'A2', 'b': 'B'}
normal lookup Child.a -> A2
```

</details>

The two functions return equal registries, and both agree with what `Child.a` resolves to. So the answer to "why is the standard way not the reversed MRO" is that it *is* the standard rule — most derived wins — and the reversal is only how it is expressed without an `if key not in out` test on every attribute. Both loops still visit both classes; the question is which visit is allowed to overwrite.

This is not a local peculiarity either: upstream `tsplib95` merges its maps across `reversed(new_class.__mro__)` as well — see [models.md](../../../src/tsplib_parser/models.md).

## Connections

### Links out

- [classes-instances-cls.md](./classes-instances-cls.md) — the class/instance theory this file extends: `cls`, binding, instantiation.
- [descriptors-fields.md](./descriptors-fields.md) — the field objects this machinery registers, and where `__set_name__` fires inside `type.__new__`.
- [factory-pattern.md](./../practical/factory-pattern.md) — the per-call flow that reads the registries this file builds.
- [models.md](../../../src/tsplib_parser/models.md) — the package overview.
- [README.md](./../README.md) — the map of content for this series.

### Backlinks

Files that link here:

- [classes-instances-cls.md](./classes-instances-cls.md) — "the neighbouring hook: what happens when the class itself is created".
- [descriptors-fields.md](./descriptors-fields.md) — the metaclass mechanics behind the registries and the reversed-MRO walk.
- [factory-pattern.md](./../practical/factory-pattern.md) — what happens at import time, next to the execution flow of one call.
