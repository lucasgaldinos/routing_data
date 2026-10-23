---
title: python-logic — map of content
description: >
  Index of the python-logic series: theoretical and practical python guides extracted from the tsplib_parser question index, with the reading paths between them. Each file carries Links out and Backlinks sections, so the graph can be walked in both directions.
created: 2026-10-06
type: index
scope: global
status: draft
author:
  - Lucas Galdino
  - GitHub Copilot
modifications:
  - date_modified: 2026-10-06
    modifications:
      - description: >
          First version. Map of content for the python-logic series with the two reading paths and cross-links to the repo-specific docs.
  - date_modified: 2026-10-08
    modifications:
      - description: >
          Added the theoretical primer typevars-pep695-cast.md to the index and related files: the legacy TypeVar system versus PEP 695 inline syntax, and the cast() escape hatch.
related_files:
  - [classes-instances-cls.md](./theoretical/classes-instances-cls.md)
  - [metaclasses-new-mro.md](./theoretical/metaclasses-new-mro.md)
  - [descriptors-fields.md](./theoretical/descriptors-fields.md)
  - [attribute-lookup.md](./theoretical/attribute-lookup.md)
  - [typevars-pep695-cast.md](./theoretical/typevars-pep695-cast.md)
  - [factory-pattern.md](./practical/factory-pattern.md)
  - [fields-vs-dataclasses.md](./practical/fields-vs-dataclasses.md)
tags:
  - guide/learning-path
  - guide/map-of-content
  - guide/tsplib-parser
  - guide/python-oop
---

# python-logic — map of content

The python concepts behind the `tsplib_parser` package, split as this series intends: theory in `theoretical/`, applied patterns in `practical/`, and repo specifics in [`docs/src/tsplib_parser/`](../../src/tsplib_parser). Every file ends with **Links out** and **Backlinks** sections — walk the graph in either direction.

## theoretical/

- [classes-instances-cls.md](./theoretical/classes-instances-cls.md) — a class is an object, a class is a factory, `cls` versus `self`, what inheritance inherits, and when a problem object comes into existence.
- [metaclasses-new-mro.md](./theoretical/metaclasses-new-mro.md) — the `__new__`/`__init__` lifecycle, the four-strength example ladder, the `mcs` parameter and the two class objects in scope, the five metaclass hooks, and the merge rule behind the reversed-MRO loop.
- [descriptors-fields.md](./theoretical/descriptors-fields.md) — `Field` objects as class attributes: options, defaults, `self.tf`, how `FileMeta` builds the two registries, and `__set_name__`.
- [attribute-lookup.md](./theoretical/attribute-lookup.md) — why `Problem` overrides `__getattribute__`, the three answers it tries, and the recursion constraint that shapes the code.
- [typevars-pep695-cast.md](./theoretical/typevars-pep695-cast.md) — the two generic-typing systems (legacy `TypeVar` versus PEP 695 inline syntax), who creates the type parameter in each, and the `cast()` escape hatch the identity default needs.

## practical/

- [factory-pattern.md](./practical/factory-pattern.md) — the factory applied: who instantiates a problem, why the object is created inside `parse`, the rejected mutating-instance design, and the full execution flow of one call.
- [fields-vs-dataclasses.md](./practical/fields-vs-dataclasses.md) — class-body declarations versus `__init__` assignments, the "schema on the class, data on the instance" rule, and the feature-by-feature dataclass comparison.

## repo-specific

These live in [docs/src/tsplib_parser/](../../src/tsplib_parser):

- [models.md](../../src/tsplib_parser/models.md) — the package overview: `Problem`, `StandardProblem`, `FileMeta`, and their roles.
- [parser-pipeline.md](../../src/tsplib_parser/parser-pipeline.md) — parsing versus validation, the two parsers plus the transformer, the VRP extras, distance dispatch, and the pipeline design questions.
- [cpp-comparison.md](../../src/tsplib_parser/cpp-comparison.md) — the C++ translation of the design: concept mapping, template analogue, and where C++ stops matching.
- solver-notes.md *(planned)* — LKH-3 and MDVRP notes for downstream consumers.

## Reading paths

**Top down (the concepts first):** [classes-instances-cls.md](./theoretical/classes-instances-cls.md) → [factory-pattern.md](./practical/factory-pattern.md) → [descriptors-fields.md](./theoretical/descriptors-fields.md) → [metaclasses-new-mro.md](./theoretical/metaclasses-new-mro.md) → [attribute-lookup.md](./theoretical/attribute-lookup.md) → [fields-vs-dataclasses.md](./practical/fields-vs-dataclasses.md).

**Bottom up (the code first):** [models.md](../../src/tsplib_parser/models.md) → [descriptors-fields.md](./theoretical/descriptors-fields.md) → [metaclasses-new-mro.md](./theoretical/metaclasses-new-mro.md) → [factory-pattern.md](./practical/factory-pattern.md) → [attribute-lookup.md](./theoretical/attribute-lookup.md).

The full question index these files were distilled from stays at [PARSER-DETAILS.MD](../../../src/tsplib_parser/PARSER-DETAILS.MD).
