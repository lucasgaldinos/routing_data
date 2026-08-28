```mermaid
---
config:
  layout: elk
  theme: forest
  elk:
    mergeEdges: true
    nodePlacementStrategy: BRANDES_KOEPF
    nodeSpacing: 50
  themeVariables:
    primaryColor: '#e8f5e8'
    primaryTextColor: '#1b5e20'
    primaryBorderColor: '#2e7d32'
    lineColor: '#4caf50'
    fontFamily: arial
    fontSize: 12px
    background: '#f9fff9'
  flowchart:
    defaultRenderer: elk
    htmlLabels: true
    curve: basis
    useMaxWidth: true
    diagramPadding: 20
title: TSPLIB95 to JSON/DuckDB Converter Architecture
---
flowchart TB
    subgraph input["Input Layer"]
        raw["datasets_raw/problems/<br/>{tsp,vrp,atsp,hcp,sop,tour}/"]
        files["*.tsp, *.vrp, *.atsp,<br/>*.hcp, *.sop, *.tour"]
    end
    
    subgraph core["Core Processing Layer"]
        subgraph scanner_detail["File Scanner (src/converter/core/scanner.py)"]
            scan_walk["Directory Walker<br/>- Recursive traversal<br/>- File filtering<br/>- Path resolution"]
            scan_detect["Type Detector<br/>- Extension analysis<br/>- Content validation<br/>- Format classification"]
            scan_batch["Batch Manager<br/>- Parallel processing<br/>- Progress tracking<br/>- Error aggregation"]
        end
        
        subgraph parser_detail["TSPLIB95 Parser (src/converter/core/parser.py)"]
            parse_tsp["TSPLib95 Wrapper<br/>- loaders.load() integration<br/>- StandardProblem handling<br/>- Special distance functions"]
            parse_valid["Data Validator<br/>- Schema validation<br/>- Range checking<br/>- Consistency verification"]
            parse_error["Error Handler<br/>- Parsing exceptions<br/>- Recovery strategies<br/>- Detailed logging"]
        end
        
        subgraph transform_detail["Data Transformer (src/converter/core/transformer.py)"]
            trans_extract["Data Extractor<br/>- Node coordinates<br/>- Edge weights<br/>- Problem metadata"]
            trans_norm["Normalizer<br/>- Index standardization<br/>- Unit conversion<br/>- Data cleaning"]
            trans_format["Format Converter<br/>- JSON serialization<br/>- Database mapping<br/>- Type conversion"]
        end
    end
    
    subgraph database["Database Layer"]
        subgraph schema_detail["Schema Management (src/converter/database/schema.py)"]
            schema_def["Schema Definition<br/>- Table creation<br/>- Index management<br/>- Constraint validation"]
            schema_mig["Migration System<br/>- Version tracking<br/>- Schema updates<br/>- Data migration"]
        end
        
        subgraph crud_detail["CRUD Operations (src/converter/database/operations.py)"]
            crud_insert["Bulk Insert<br/>- Prepared statements<br/>- Batch processing<br/>- Transaction handling"]
            crud_update["Update Manager<br/>- Conflict resolution<br/>- Incremental updates<br/>- Change detection"]
            crud_query["Query Engine<br/>- Analysis functions<br/>- Statistics<br/>- Data export"]
        end
    end
    
    subgraph output["Output Layer"]
        subgraph json_detail["JSON Writer (src/converter/output/json_writer.py)"]
            json_format["Format Manager<br/>- Flattened structure<br/>- Schema validation<br/>- Pretty printing"]
            json_file["File Manager<br/>- Directory creation<br/>- Naming conventions<br/>- Compression options"]
        end
        
        subgraph db_detail["DuckDB Interface (src/converter/database/models.py)"]
            db_conn["Connection Pool<br/>- Thread safety<br/>- Connection reuse<br/>- Resource management"]
            db_opt["Query Optimizer<br/>- Index usage<br/>- Join optimization<br/>- Performance tuning"]
        end
    end
    
    raw --> scan_walk
    files --> scan_detect
    scan_walk --> scan_batch
    scan_detect --> scan_batch
    scan_batch --> parse_tsp
    parse_tsp --> parse_valid
    parse_valid --> parse_error
    parse_error --> trans_extract
    trans_extract --> trans_norm
    trans_norm --> trans_format
    trans_format --> json_format
    trans_format --> schema_def
    json_format --> json_file
    schema_def --> schema_mig
    schema_mig --> crud_insert
    crud_insert --> crud_update
    crud_update --> crud_query
    crud_query --> db_conn
    db_conn --> db_opt
    
    classDef input fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef scanner fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef parser fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef transform fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef schema fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef crud fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef json fill:#f1f8e9,stroke:#689f38,stroke-width:2px
    classDef database fill:#fff8e1,stroke:#fbc02d,stroke-width:2px
    
    class raw,files input
    class scan_walk,scan_detect,scan_batch scanner
    class parse_tsp,parse_valid,parse_error parser
    class trans_extract,trans_norm,trans_format transform
    class schema_def,schema_mig schema
    class crud_insert,crud_update,crud_query crud
    class json_format,json_file json
    class db_conn,db_opt database```
