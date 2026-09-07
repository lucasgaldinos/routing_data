---
title: TSPLIB95 ETL System — Documentation Index
description: >
  Index of the TSPLIB95 ETL System documentation: user guides, technical
  references, development resources, and visual diagram links.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Repointed dangling links (API reference, architecture guide, developer
          workflow, performance benchmarks), removed the dead archive section,
          repointed external resources to the TSPLIB95 format reference, fixed
          stale diagram-extension links in the diagrams index, and updated
          output paths to datasets_processed/.
related_files:
  - "[Getting Started](./guides/GETTING_STARTED.md)"
  - "[User Guide](./guides/USER_GUIDE.md)"
  - "[Architecture Decisions](./reference/ARCHITECTURE_DECISIONS.md)"
  - "[Contributing](./reference/CONTRIBUTING.md)"
tags: [guide/documentation, notes/index, guide/setup, guide/cli, guide/database, analysis/architecture, notes/overview, guide/etl, analysis/testing, guide/development, notes/documentation]
---
# TSPLIB95 ETL System - Documentation

> **Complete documentation for the TSPLIB95 ETL System** - A 3-phase pipeline for converting TSPLIB95/VRP routing problems into JSON and DuckDB formats.

---

## 📖 Documentation Structure

### 🚀 **User Guides** (`guides/`)

*Get started and learn to use the system effectively*

| Document | Purpose | Audience |
| ---------- | --------- | ---------- |
| **[Getting Started](guides/GETTING_STARTED.md)** | 3-step quick start guide | New users |
| **[User Guide](guides/USER_GUIDE.md)** | Complete usage reference | All users |
| **[Troubleshooting](guides/TROUBLESHOOTING.md)** | Issue resolution & edge cases | All users |

### 📚 **Technical Reference** (`reference/`)

*Deep technical documentation for developers and architects*

| Document | Purpose | Audience |
| ---------- | --------- | ---------- |
| **[API Reference](guides/USER_GUIDE.md)** | Complete programmatic interface | Developers |
| **[Architecture Guide](reference/ARCHITECTURE_DECISIONS.md)** | System design & technical decisions | Architects, developers |

### 🛠️ **Development** (`development/`)

*Resources for contributors and maintainers*

| Document | Purpose | Audience |
| ---------- | --------- | ---------- |
| **[Contributing](reference/CONTRIBUTING.md)** | Essential development patterns | Contributors |

### 🎨 **Visual Documentation** (`diagrams/`)

*Technical diagrams and system visualizations*

| Diagram | Purpose | Content |
| --------- | --------- | --------- |
| `converter-architecture.md` | System overview | Component relationships & data flow |
| `database-schema.md` | Database design | Tables, relationships, indexes |
| `database-queries.md` | Query patterns | Example queries & performance tips |
| `data-structures-algorithms.md` | Technical internals | Memory layout, algorithms, complexity |
| `processing-pipeline-flow.md` | Workflow visualization | Complete ETL process flow |
| `error-handling-edge-cases.md` | Error scenarios | Comprehensive error handling |
| `performance-scalability.md` | Performance analysis | Metrics, limits, optimization |

### 📦 **External Resources** (`reference/tsplib95_format.md`)

*TSPLIB95 format specification and reference*

---

## 🎯 Quick Start Navigation

### New to the System?

1. **[Getting Started Guide](guides/GETTING_STARTED.md)** - 3 steps to success
2. **[User Guide](guides/USER_GUIDE.md)** - Complete usage documentation
3. **[Troubleshooting](guides/TROUBLESHOOTING.md)** - When things go wrong

### Want to Use the API?

1. **[API Reference](guides/USER_GUIDE.md)** - All functions with examples
2. **[Architecture Guide](reference/ARCHITECTURE_DECISIONS.md)** - Understand the design

### Contributing to Development?

1. **[Contributing](reference/CONTRIBUTING.md)** - Essential setup & patterns

### Need Visual Understanding?

- **System Overview**: `diagrams/converter-architecture.md`
- **Database Design**: `diagrams/database-schema.md`
- **Performance**: `diagrams/performance-scalability.md`
- **Error Handling**: `diagrams/error-handling-edge-cases.md`

---

## 📊 System Overview

### What is the TSPLIB95 ETL System?

A **3-phase Extract-Transform-Load pipeline** that converts TSPLIB95 and VRP problem instances into modern, queryable formats:

```text
TSPLIB Files → Parser → Transformer → [JSON + DuckDB Database]
```

### Key Capabilities

- **File Processing**: Parse TSP, VRP, ATSP, HCP, SOP, TOUR formats
- **Data Transformation**: Convert 1-based TSPLIB indexing to 0-based database format
- **Dual Output**: Generate both JSON files and DuckDB database
- **Parallel Processing**: Multi-worker processing for large datasets
- **Change Detection**: Incremental updates based on file content
- **Query Interface**: SQL queries on routing problem characteristics

### Technology Stack

- **Language**: python 3.11+
- **Dependencies**: DuckDB, tsplib95 (vendored)
- **Package Manager**: uv (modern python packaging)
- **Database**: DuckDB (embedded analytics)
- **Testing**: pytest with comprehensive coverage

---

## 💡 Common Use Cases

### Research & Analysis

```bash
# Process academic datasets
uv run converter process -i datasets_raw/problems -o datasets_processed/

# Query database for specific problem types
duckdb datasets_processed/db/routing.duckdb "SELECT * FROM problems WHERE type='TSP' AND dimension > 1000"
```

### Integration & Development

```python
# python API usage
import converter

# Parse single file
data = converter.parse_file("problem.tsp")
converter.to_json(data, "output.json")
converter.to_database(data, "routing.duckdb")
```

### Batch Processing & Automation

```bash
# Parallel processing with progress tracking
uv run converter process --workers 8 --batch-size 200 --progress
```

---

## 🔗 External Resources

- **TSPLIB95 Specification**: See `tsplib95.pdf` in project root
- **Academic Papers**: Research citations in code comments
- **GitHub Repository**: Source code and issue tracking

---

## 📞 Support & Contributing

### Getting Help

- **Issues**: Check [Troubleshooting Guide](guides/TROUBLESHOOTING.md) first
- **Questions**: Open GitHub discussions
- **Bug Reports**: Use GitHub issues with error details

### Contributing

- **Code**: Follow [Contributing](reference/CONTRIBUTING.md)
- **Documentation**: Improve guides based on user feedback
- **Testing**: Add test cases for edge cases

### Documentation Updates

- **User Feedback**: Update troubleshooting based on common issues
- **API Changes**: Keep API reference synchronized with code
- **Performance**: Update benchmarks with new optimizations

---

*This documentation is organized for maximum accessibility - from quick-start newcomers to deep-diving system architects. Each section serves specific needs while maintaining comprehensive cross-references.*
