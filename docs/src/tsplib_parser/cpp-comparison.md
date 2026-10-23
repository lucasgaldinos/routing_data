---
title: The design in C++
description: >
  The C++ translation of the tsplib_parser design: the concept mapping, the template-for-cls structural analogue with compiled output, where C++ stops matching (operator new is not __new__, no metaclass hook), and the two details that bite in the comparison. Repo-specific companion to the python-logic series.
created: 2026-10-07
type: guide
scope: repo
status: draft
author:
  - Lucas Galdino
  - GitHub Copilot
modifications:
  - date_modified: 2026-10-07
    modifications:
      - description: >
          First version. Rewrote §7.1 of PARSER-DETAILS.MD: the concept mapping table, the Problem/StandardProblem structural analogue with its compile-and-run output, the three failure cases of the __new__ comparison, and the lazy-registry and map-ordering details. Snippets compiled with g++ 12.4.0, -std=c++17.
related_files:
  - [PARSER-DETAILS.MD](../../../src/tsplib_parser/PARSER-DETAILS.MD)
  - [models.md](./models.md)
  - [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md)
tags:
  - guide/cpp-comparison
  - guide/tsplib-parser
  - guide/metaclass
---

# The design in C++

## What this file is

A translation exercise, not a port plan: how far the `Problem`/`StandardProblem`/`FileMeta` design carries over to C++, where the idea lands cleanly, and where the language simply has no equivalent. The metaclass side it compares against is [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md); the classes themselves are [models.md](./models.md).

## The concept mapping

| python | C++ | Notes |
| --- | --- | --- |
| `struct` / `class` | identical | `struct` is a class with public default access |
| instance | object | same |
| `self` | implicit `this` | same |
| class | class | same |
| `type` | compiler machinery plus `std::type_info` | not first-class, not callable |
| metaclass, `FileMeta` | no equivalent | nearest tools are CRTP, macros or code generation |
| `__init__` | constructor | same role |
| `__new__` | `operator new` | not the same thing — see below |
| `cls()` | `std::make_unique<T>()` | `T` comes from a template parameter |
| classmethod `cls` | `template <typename T>` on a static member | `T` is the concrete class |
| `cls.fields_by_keyword` | a `static` member map | built before `main` |
| `__set_name__` | none | the name is passed explicitly |
| `as_name_dict()` | a DTO struct, or `std::map<std::string, std::variant<...>>` | — |

## The structural analogue

The `Problem` / `StandardProblem` split maps cleanly, with the template parameter standing in for `cls`:

```cpp
#include <functional>
#include <map>
#include <memory>
#include <string>

// "Field": a keyword plus the function that turns its text into a value
struct Field {
    std::string keyword;
    std::function<int(std::string)> parse;
};

struct Problem {                                          // = python's Problem
    std::map<std::string, int> data;                      // = the instance __dict__
    virtual const std::map<std::string, Field>& registry() const = 0;

    template <typename T>                                 // this IS the "cls" of C++
    static std::unique_ptr<T> parse(const std::map<std::string, std::string>& kv) {
        auto p = std::make_unique<T>();                   // this IS cls()
        for (const auto& [k, v] : kv) {
            auto it = p->registry().find(k);
            if (it != p->registry().end()) p->data[k] = it->second.parse(v);
        }
        return p;
    }
};

struct StandardProblem : Problem {                        // = python's StandardProblem
    static const std::map<std::string, Field>& fields() { // = fields_by_keyword
        static const std::map<std::string, Field> f = {
            {"NAME",      {"NAME",      [](std::string s) { return (int)s.size(); }}},
            {"DIMENSION", {"DIMENSION", [](std::string s) { return std::stoi(s); }}},
        };
        return f;
    }
    const std::map<std::string, Field>& registry() const override { return fields(); }
};

auto p = Problem::parse<StandardProblem>(kv);              // T = StandardProblem
```

```text
parse<StandardProblem> -> DIMENSION=3 NAME=4
p->data["DIMENSION"] = 3
```

`Problem::parse<StandardProblem>` is the counterpart of `StandardProblem.parse(text)`: the caller picks the type, and it flows into `make_unique<T>()`. It is the same polymorphism `cls` provides, resolved at compile time.

## Where C++ stops matching

`operator new` is not `__new__`. It allocates raw bytes on its own, the constructor runs afterwards, and there is no interception point between the two — the slot `__new__` occupies does not exist:

```cpp
void* mem = ::operator new(sizeof(Meters));   // allocation
new (mem) Meters(1.23456);                    // construction, no hook between
```

Taking the four examples from [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md) one at a time:

- Example 1 (normalize an immutable value) is **easier** in C++ — a constructor can transform before storing, because there is no after-construction immutability rule to work around:

  ```cpp
  struct Meters {
      double value;
      explicit Meters(double v) : value(std::round(v * 1000.0) / 1000.0) {}
  };
  // Meters(1.23456).value == 1.235
  ```

- Example 3 (return a different type) becomes a factory returning a base pointer — ordinary C++:

  ```cpp
  std::unique_ptr<Problem> make(const std::map<std::string, std::string>& raw) {
      if (raw.at("TYPE") == "XRAY") return std::make_unique<XRayProblem>();
      return std::make_unique<StandardProblem>();
  }
  ```

- Example 4 (the metaclass) has **no runtime hook**. The options are CRTP, macros and code generation. CRTP, where the derived class passes itself:

  ```cpp
  template <typename Derived>
  struct Registrable {
      Registrable() { (void)Derived::fields(); }   // "auto-register the derived class"
  };
  struct StandardProblem : Problem, private Registrable<StandardProblem> { };
  ```

  `Registrable<StandardProblem>` is conceptually `FileMeta(StandardProblem)`. The other option is code generation — protobuf, FlatBuffers and Qt's `moc` all write out the registration code a python metaclass would derive at import.

## Two C++ details that bite

- The registry in the snippet is a function-local `static`: built lazily on first call, immune to the static initialization order fiasco. A namespace-scope or static-data-member map would not be — that is the C++ counterpart of "when does the class body run at import", except C++ leaves the cross-translation-unit order undefined instead of fixing it.
- `std::map` iterates in sorted key order, which is why the demo prints `DIMENSION` before `NAME`; a python dict preserves insertion order.

## Bottom line

- The metaclass has no runtime equivalent; CRTP, macros or code generation stand in for it.
- Examples 1 and 3 are pedagogical only — neither exists in this repository, and neither needs a C++ mechanism, because a constructor and a factory cover them.

## Connections

### Links out

- [models.md](./models.md) — the class roles this translation mirrors.
- [metaclasses-new-mro.md](../../studies/python-logic/theoretical/metaclasses-new-mro.md) — the four examples and the metaclass mechanics referenced above.
- [factory-pattern.md](../../studies/python-logic/practical/factory-pattern.md) — the python factory the template analogue replaces.
- [README.md](../../studies/python-logic/README.md) — the series map of content.

### Backlinks

Files that link here:

- [README.md](../../studies/python-logic/README.md) — the map of content lists this file under repo-specific docs.
