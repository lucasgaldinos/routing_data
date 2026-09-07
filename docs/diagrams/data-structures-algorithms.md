```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: '#e3f2fd'
    primaryTextColor: '#1565c0'
    primaryBorderColor: '#1976d2'
    lineColor: '#42a5f5'
    fontFamily: 'JetBrains Mono, Monaco, Consolas, monospace'
    fontSize: 10px
    background: '#fafafa'
  flowchart:
    htmlLabels: true
    curve: basis
    useMaxWidth: true
    diagramPadding: 25
title: Data Structures and Memory Layout - TSPLIB95 ETL System
---
flowchart TB
    subgraph memory_layout["Memory Layout & Data Structures"]
        subgraph tsplib_raw["Raw TSPLIB95 Data (Phase 1)"]
            raw_problem["📋 StandardProblem Object<br/>┌─ name: str<br/>├─ type: str (TSP|VRP|ATSP|...)<br/>├─ dimension: int<br/>├─ capacity: int | None<br/>├─ edge_weight_type: str<br/>├─ node_coords: Dict[int, Tuple]<br/>├─ demands: Dict[int, int]<br/>├─ depots: List[int]<br/>├─ edge_weights: Dict[Tuple, float]<br/>└─ tours: List[List[int]]"]
            
            raw_memory["Memory Characteristics:<br/>• 1-based indexing (TSPLIB standard)<br/>• O(n) for coordinates<br/>• O(n²) for explicit edges (avoided)<br/>• Dict-based sparse storage<br/>• Lazy edge computation"]
        end
        
        subgraph transformed_data["Transformed Data (Phase 2)"]
            norm_structure["🔄 Normalized Structure<br/>┌─ problem_data: Dict<br/>│  ├─ id: int (auto-generated)<br/>│  ├─ name: str<br/>│  ├─ type: str<br/>│  ├─ dimension: int<br/>│  └─ metadata: Dict<br/>├─ nodes: List[Dict]<br/>│  ├─ node_id: int (0-based)<br/>│  ├─ x, y, z: float | None<br/>│  ├─ demand: int<br/>│  └─ is_depot: bool<br/>├─ edges: List[Dict] (EXPLICIT only)<br/>│  ├─ from_node: int (0-based)<br/>│  ├─ to_node: int (0-based)<br/>│  └─ weight: float<br/>└─ tours: List[List[int]] (0-based)"]
            
            transform_memory["Memory Optimization:<br/>• 0-based indexing (database-friendly)<br/>• List-based for fast iteration<br/>• Only store edges for EXPLICIT types<br/>• Coordinate-based distance on-demand<br/>• Batch processing for large files"]
        end
        
        subgraph db_storage["Database Storage (Phase 3)"]
            db_tables["💾 DuckDB Tables<br/>┌─ problems: Row-oriented<br/>│  └─ Clustered by ID<br/>├─ nodes: Column-optimized<br/>│  ├─ Indexed by (problem_id, node_id)<br/>│  └─ Spatial index for coordinates<br/>├─ edges: Compressed storage<br/>│  ├─ Indexed by (problem_id, from_node)<br/>│  └─ Only for EXPLICIT weights<br/>├─ tours: JSON column storage<br/>│  └─ Indexed by problem_id<br/>└─ file_tracking: Metadata<br/>     ├─ File hash for change detection<br/>     └─ Processing status tracking"]
            
            db_perf["Performance Characteristics:<br/>• Columnar compression (5-10x)<br/>• Parallel query execution<br/>• Memory-mapped I/O<br/>• Automatic index optimization<br/>• Sub-second analytics queries"]
        end
    end
    
    subgraph algorithms["Core Algorithms & Complexity"]
        subgraph parsing_algo["Parsing Algorithm"]
            parse_steps["📊 Parsing Process<br/>┌─ 1. File validation: O(1)<br/>├─ 2. Header parsing: O(k) k=fields<br/>├─ 3. Section parsing: O(n+e)<br/>│   ├─ COORD_SECTION: O(n)<br/>│   ├─ DEMAND_SECTION: O(n)<br/>│   ├─ DEPOT_SECTION: O(d)<br />│   └─ EDGE_WEIGHT_SECTION: O(e)<br/>├─ 4. Data validation: O(n)<br/>└─ 5. Structure creation: O(n)"]
            
            parse_complex["Overall Complexity:<br/>• Time: O(n + e) where n=nodes, e=edges<br/>• Space: O(n + e)<br/>• Critical: Avoid O(n²) edge generation<br/>• Memory-efficient streaming for large files"]
        end
        
        subgraph transform_algo["Transformation Algorithm"]
            transform_steps["⚡ Transform Process<br/>┌─ 1. Index conversion: O(n)<br/>│   └─ Map: i → i-1 (1-based to 0-based)<br/>├─ 2. Node normalization: O(n)<br/>│   ├─ Coordinate validation<br/>│   ├─ Demand assignment<br/>│   └─ Depot flag setting<br/>├─ 3. Edge processing: O(e) or O(1)<br/>│   ├─ EXPLICIT: Store provided edges<br/>│   └─ COORDINATE: Skip (compute on-demand)<br/>└─ 4. Tour normalization: O(t×m)<br/>     └─ t=tours, m=avg_tour_length"]
            
            transform_memory["Memory Management:<br/>• Streaming transformation<br/>• Batch processing (configurable)<br/>• Garbage collection friendly<br/>• Copy-on-write for large structures"]
        end
        
        subgraph distance_algo["Distance Computation"]
            distance_types["📐 Distance Functions<br/>┌─ EUC_2D: √[(x₂-x₁)² + (y₂-y₁)²]<br/>├─ MAN_2D: |x₂-x₁| + |y₂-y₁|<br/>├─ CEIL_2D: ⌈EUC_2D⌉<br/>├─ GEO: Haversine formula<br/>│   └─ 6378.388 × arccos(sin(φ₁)sin(φ₂) +<br/>│       cos(φ₁)cos(φ₂)cos(Δλ))<br/>├─ ATT: √[(x₂-x₁)² + (y₂-y₁)²]/10<br/>└─ EXPLICIT: Pre-stored matrix lookup"]
            
            distance_perf["Performance:<br/>• EUC_2D/MAN_2D: ~100ns per calculation<br/>• GEO: ~500ns (trigonometric functions)<br/>• EXPLICIT: ~50ns (array lookup)<br/>• Vectorization possible for batch calculations"]
        end
    end
    
    subgraph parallel_arch["Parallel Processing Architecture"]
        subgraph worker_model["Worker Process Model"]
            worker_design["👥 Multi-Process Design<br/>┌─ Main Process:<br/>│  ├─ File discovery & batching<br/>│  ├─ Result aggregation<br/>│  └─ Progress monitoring<br/>├─ Worker Processes (N):<br/>│  ├─ Independent parser instances<br/>│  ├─ Local database connections<br/>│  ├─ Memory limit monitoring<br/>│  └─ Error isolation<br/>└─ Batch Coordinator:<br/>   ├─ Load balancing<br/>   ├─ Failure recovery<br/>   └─ Resource management"]
            
            worker_sync["Synchronization:<br/>• File-level locking (filesystem)<br/>• Database connection pooling<br/>• Shared progress counter (atomic)<br/>• Result queue (thread-safe)<br/>• Graceful shutdown handling"]
        end
        
        subgraph batch_strategy["Batch Processing Strategy"]
            batch_logic["📦 Batching Logic<br/>┌─ File Size Estimation:<br/>│  ├─ Small files (<1MB): batch=200<br/>│  ├─ Medium files (1-10MB): batch=50<br/>│  └─ Large files (>10MB): batch=10<br/>├─ Memory-Based Batching:<br/>│  ├─ Monitor RSS per worker<br/>│  ├─ Reduce batch size if memory high<br/>│  └─ Emergency GC if limit exceeded<br/>└─ Dynamic Adjustment:<br/>   ├─ Performance feedback loop<br/>   ├─ Error rate monitoring<br/>   └─ Optimal batch size learning"]
            
            batch_perf["Batch Performance:<br/>• I/O amortization: ~50% reduction<br/>• Memory locality: Better cache usage<br/>• Error isolation: Batch-level recovery<br/>• Progress tracking: Smoother updates"]
        end
    end
    
    subgraph edge_cases["Edge Case Handling"]
        subgraph data_quality["Data Quality Issues"]
            quality_checks["🔍 Quality Validation<br/>┌─ File Format Issues:<br/>│  ├─ Missing required sections<br/>│  ├─ Malformed coordinates<br/>│  ├─ Inconsistent dimensions<br/>│  └─ Invalid character encoding<br/>├─ Data Consistency:<br/>│  ├─ Node ID gaps or duplicates<br/>│  ├─ Coordinate range validation<br/>│  ├─ Demand/capacity consistency<br/>│  └─ Tour feasibility checks<br/>└─ Performance Issues:<br/>   ├─ Extremely large files (>1GB)<br/>   ├─ Dense edge matrices<br/>   └─ Memory exhaustion scenarios"]
            
            error_recovery["Error Recovery:<br/>• Graceful degradation<br/>• Partial data preservation<br/>• Detailed error logging<br/>• Retry with relaxed validation<br/>• Skip corrupted sections"]
        end
        
        subgraph memory_management["Memory Management"]
            memory_strategy["💾 Memory Strategy<br/>┌─ File Size Limits:<br/>│  ├─ Default: 100MB per file<br/>│  ├─ Configurable via settings<br/>│  └─ Automatic chunking for larger files<br/>├─ Worker Memory Limits:<br/>│  ├─ RSS monitoring per process<br/>│  ├─ Configurable limit (default: 2GB)<br/>│  └─ Emergency cleanup procedures<br/>└─ Garbage Collection:<br/>   ├─ Explicit GC after batch<br/>   ├─ Reference cycle detection<br/>   └─ Memory pool optimization"]
            
            oom_handling["OOM Prevention:<br/>• Pre-allocation checks<br/>• Streaming for large datasets<br/>• Temporary file spillover<br/>• Process restart on memory limit<br/>• User warnings for large files"]
        end
    end
    
    raw_problem --> norm_structure
    norm_structure --> db_tables
    parse_steps --> transform_steps
    transform_steps --> worker_design
    worker_design --> batch_logic
    quality_checks --> error_recovery
    memory_strategy --> oom_handling
    
    classDef rawData fill:#ffecb3,stroke:#ff8f00,stroke-width:2px
    classDef transformedData fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef dbStorage fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef algorithm fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef parallel fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef edgeCase fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    
    class raw_problem,raw_memory rawData
    class norm_structure,transform_memory transformedData
    class db_tables,db_perf dbStorage
    class parse_steps,parse_complex,transform_steps,transform_memory,distance_types,distance_perf algorithm
    class worker_design,worker_sync,batch_logic,batch_perf parallel
    class quality_checks,error_recovery,memory_strategy,oom_handling edgeCase```
