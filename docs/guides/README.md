---
title: "User Guides — Index"
description: >
  Index of the user-facing guides for the TSPLIB95 ETL converter: getting
  started, full user guide, Parquet export, and troubleshooting.
created: 2025-10-28
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Added YAML frontmatter per repository markdown standards.
related_files:
  - [USER_GUIDE.md](./USER_GUIDE.md)
  - [GETTING_STARTED.md](./GETTING_STARTED.md)
  - [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
  - [PARQUET_EXPORT.md](./PARQUET_EXPORT.md)
tags:
  - guide/index
  - guide/usage
  - guide/quickstart
  - guide/cli
  - guide/python-api
  - guide/database
  - guide/troubleshooting
  - analysis/etl
  - notes/converter
  - notes/parquet
---
# User Guides

This folder contains documentation for users of the TSPLIB95 ETL System.

## 📚 Available Guides

### [Getting Started](GETTING_STARTED.md)

**Purpose**: 3-step quick start guide
**Audience**: New users
**Contents**: Installation, basic usage, first steps

### [User Guide](USER_GUIDE.md)

**Purpose**: Complete usage reference
**Audience**: All users
**Contents**: CLI commands, python API, configuration, examples

### [Parquet Export Guide](PARQUET_EXPORT.md) ⭐ NEW

**Purpose**: Export database to columnar Parquet format
**Audience**: Data scientists, ML engineers, analytics users
**Contents**:

- Why Parquet? (Compression, performance benefits)
- CLI and python API usage
- Reading with pandas, polars, DuckDB
- Compression options (snappy, gzip, zstd)
- Integration examples (Jupyter, Streamlit, FastAPI)
- Performance optimization tips

### [Troubleshooting](TROUBLESHOOTING.md)

**Purpose**: Issue resolution and edge case handling
**Audience**: All users
**Contents**: Common problems, diagnostic procedures, performance issues

## 🚀 Recommended Reading Order

1. **New to the system?** Start with [Getting Started](GETTING_STARTED.md)
2. **Need detailed reference?** See [User Guide](USER_GUIDE.md)
3. **Want columnar analytics?** Read [Parquet Export Guide](PARQUET_EXPORT.md)
4. **Having problems?** Check [Troubleshooting](TROUBLESHOOTING.md)

## 🎯 Quick Navigation by Use Case

| Use Case | Recommended Guide |
| ---------- | ------------------- |
| First-time setup | [Getting Started](GETTING_STARTED.md) |
| CLI reference | [User Guide](USER_GUIDE.md) |
| Data science/ML workflows | [Parquet Export Guide](PARQUET_EXPORT.md) |
| python automation | [User Guide](USER_GUIDE.md) → python API section |
| Performance issues | [Troubleshooting](TROUBLESHOOTING.md) |
| Database queries | [User Guide](USER_GUIDE.md) → Database section |

## 🔗 Related Documentation

- **Technical Details**: See `../reference/` for API and architecture docs
- **Development**: See `../development/` for contributor guides
- **Visual Diagrams**: See `../diagrams/` for system visualizations
