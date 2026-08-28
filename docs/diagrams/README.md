---
title: Technical Diagrams — Index
description: >
  Index of the diagram documents (rendered as .md files) visualizing the
  TSPLIB95 ETL System architecture, database schema, processing flows, and
  performance characteristics.
created: 2026-08-25
modifications:
  - date_modified: 2026-08-25
    modifications:
      - description: >
          Fixed stale diagram-extension references to .md and repointed the
          architecture details link to the architecture decisions log.
related_files:
  - "[Architecture Decisions](../reference/ARCHITECTURE_DECISIONS.md)"
  - "[User Guide](../guides/USER_GUIDE.md)"
tags: [notes/diagrams, analysis/architecture, analysis/schema, analysis/performance, notes/overview, guide/etl, analysis/database, analysis/design, notes/er-diagram, guide/reference]
---
# Technical Diagrams

This folder contains Mermaid diagrams that visualize various aspects of the TSPLIB95 ETL System.

## 📊 Available Diagrams

### System Architecture

- `converter-architecture.md` - Overall system flow and component relationships
- `processing-pipeline-flow.md` - Complete ETL workflow with error handling

### Database & Data

- `database-schema.md` - Database tables, relationships, and indexes  
- `database-queries.md` - Example queries and performance patterns

### Technical Internals

- `data-structures-algorithms.md` - Memory layout, algorithmic complexity, parallel processing
- `performance-scalability.md` - Performance metrics, memory analysis, scalability limits

### Error Handling & Edge Cases

- `error-handling-edge-cases.md` - Comprehensive error scenarios and recovery strategies

## 🎯 Usage Guide

### Viewing Diagrams

These are Mermaid diagrams that can be viewed:

- **In VS Code**: Use the Mermaid Preview extension
- **In GitHub**: Automatically rendered in markdown files
- **Online**: Copy content to [mermaid.live](https://mermaid.live)

### Diagram Categories

**System Overview** → `converter-architecture.md`, `processing-pipeline-flow.md`  
**Database Design** → `database-schema.md`, `database-queries.md`  
**Performance Analysis** → `data-structures-algorithms.md`, `performance-scalability.md`  
**Error Handling** → `error-handling-edge-cases.md`

## 🔗 Related Documentation

- **Architecture Details**: See `../reference/ARCHITECTURE_DECISIONS.md`
- **User Examples**: See `../guides/USER_GUIDE.md`
