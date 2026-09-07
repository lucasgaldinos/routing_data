```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: '#ffebee'
    primaryTextColor: '#b71c1c'
    primaryBorderColor: '#d32f2f'
    lineColor: '#f44336'
    fontFamily: 'Segoe UI, Arial, sans-serif'
    fontSize: 10px
    background: '#fafafa'
  flowchart:
    htmlLabels: true
    curve: basis
    useMaxWidth: true
    diagramPadding: 20
title: Error Handling and Edge Cases - TSPLIB95 ETL System
---
flowchart TD
    subgraph input_errors["📁 Input-Level Errors"]
        file_system_errors["🚫 File System Issues<br/>Common Scenarios<br/>┌─ File not found or moved<br/>├─ Permission denied (read access)<br/>├─ Network drive disconnection<br/>├─ Disk full during processing<br/>├─ File locked by another process<br/>└─ Corrupted file system metadata<br/><br/>🔧 Recovery Strategy:<br/>• Retry with exponential backoff<br/>• Skip and continue with other files<br/>• Detailed logging for manual intervention<br/>• Graceful degradation to available files"]
        
        encoding_errors["📝 Character Encoding Issues<br/>Edge Cases<br/>┌─ Non-UTF8 encoded files (legacy)<br/>├─ Mixed encoding within single file<br/>├─ Byte order mark (BOM) handling<br/>├─ NULL bytes in text files<br/>├─ Line ending inconsistencies<br/>└─ Special characters in problem names<br/><br/>🔧 Recovery Strategy:<br/>• Auto-detect encoding (chardet)<br/>• Fallback encoding sequence<br/>• Sanitize invalid characters<br/>• Preserve original with warnings"]
        
        size_limit_errors["📏 File Size Limitations<br/>Boundary Conditions<br/>┌─ Empty files (0 bytes)<br/>├─ Extremely large files (>1GB)<br/>├─ Files with many small sections<br/>├─ Dense edge weight matrices<br/>├─ Files with excessive comments<br/>└─ Malformed size declarations<br/><br/>🔧 Recovery Strategy:<br/>• Configurable size limits<br/>• Streaming processing for large files<br/>• Memory-mapped file access<br/>• Chunked processing with progress"]
    end
    
    subgraph parsing_errors["📊 Parsing-Level Errors"]
        format_errors["📋 TSPLIB Format Violations<br/>Specification Deviations<br/>┌─ Missing required sections (NAME, TYPE)<br/>├─ Invalid section keywords<br/>├─ Malformed section headers<br/>├─ Inconsistent field separators<br/>├─ Missing EOF marker<br/>├─ Sections in wrong order<br/>└─ Duplicate section definitions<br/><br/>🔧 Recovery Strategy:<br/>• Relaxed parsing mode<br/>• Section auto-detection<br/>• Default value substitution<br/>• Partial data extraction<br/>• Format migration suggestions"]
        
        data_consistency_errors["🔍 Data Consistency Issues<br/>Internal Contradictions<br/>┌─ DIMENSION != actual node count<br/>├─ Node IDs not sequential (1,2,3...)<br/>├─ Missing nodes in coordinate section<br/>├─ Coordinate dimension mismatch<br/>├─ Edge weight matrix size wrong<br/>├─ Tour references non-existent nodes<br/>├─ Capacity specified but no demands<br/>├─ SOP files include dimension in EDGE_WEIGHT_SECTION<br/>└─ EDGE_WEIGHT_SECTION first element = dimension<br/><br/>🔧 Recovery Strategy:<br/>• Auto-correct dimension from data<br/>• Fill missing nodes with interpolation<br/>• Validate and repair node sequences<br/>• Dimension consistency enforcement<br/>• Warning generation for conflicts<br/>• Strip first element if equals dimension (SOP)"]
        
        edge_weight_errors["⚖️ Edge Weight Computation Errors<br/>Distance Calculation Issues<br/>┌─ Invalid coordinates (NaN, Inf)<br/>├─ Coordinates outside valid ranges<br/>├─ Geographic coordinate errors<br/>├─ Missing distance function for type<br/>├─ Precision overflow/underflow<br/>├─ SPECIAL type without custom function<br/>└─ EXPLICIT matrix incomplete<br/><br/>🔧 Recovery Strategy:<br/>• Coordinate validation and clamping<br/>• Fallback distance functions<br/>• Precision safeguards<br/>• Matrix completion algorithms<br/>• Custom distance function registration"]
    end
    
    subgraph transformation_errors["🔄 Transformation-Level Errors"]
        index_conversion_errors["🔢 Index Conversion Issues<br/>1-based → 0-based Problems<br/>┌─ Zero-based indices in TSPLIB file<br/>├─ Negative node indices<br/>├─ Non-sequential node numbering<br/>├─ Index gaps in node sequences<br/>├─ Tour indices outside valid range<br/>├─ Edge references to missing nodes<br/>└─ Depot indices inconsistencies<br/><br/>🔧 Recovery Strategy:<br/>• Smart index detection (0 vs 1 based)<br/>• Index remapping for gaps<br/>• Tour validation and repair<br/>• Edge reference validation<br/>• Consistent depot index handling"]
        
        matrix_format_errors["📐 Matrix Format Conversion Errors<br/>TSPLIB Matrix Format Issues<br/>┌─ Incorrect element count for format type<br/>├─ FULL_MATRIX size validation (dimension²)<br/>├─ LOWER_ROW expected: dimension×(dimension-1)/2<br/>├─ LOWER_DIAG_ROW expected: dimension×(dimension+1)/2<br/>├─ UPPER_ROW/UPPER_DIAG_ROW symmetry<br/>├─ Column-variant formats (UPPER_COL, LOWER_COL)<br/>├─ Matrix reconstruction from triangular formats<br/>└─ Asymmetric vs symmetric matrix validation<br/><br/>🔧 Recovery Strategy:<br/>• Precise element count validation per format<br/>• Matrix class for each format type<br/>• Full matrix reconstruction with bounds checking<br/>• Symmetry property validation for TSP<br/>• Asymmetry detection for ATSP (check ALL pairs)<br/>• Format-specific parsing with fallback"]
        
        namespace_consistency_errors["🔧 Import Namespace Consistency Issues<br/>Module Import Problems<br/>┌─ isinstance() fails due to namespace mismatch<br/>├─ Parser creates objects from one module path<br/>├─ Transformer imports from different path<br/>├─ Type checking fails on identical classes<br/>├─ Matrix class namespace inconsistency<br/>├─ StandardProblem type validation failures<br/>└─ Field class import path divergence<br/><br/>🔧 Recovery Strategy:<br/>• Consistent import paths across all modules<br/>• Use canonical module path (src.tsplib_parser)<br/>• Avoid relative imports for type checking<br/>• Duck typing as fallback for validation<br/>• Explicit type conversion when needed<br/>• Module reload for testing scenarios"]
        
        vrp_specific_errors["🚛 VRP-Specific Transformation Errors<br/>Vehicle Routing Edge Cases<br/>┌─ Multiple depot handling ambiguity<br/>├─ Zero or negative demands<br/>├─ Demand exceeds vehicle capacity<br/>├─ No depot specified in VRP<br/>├─ Time window format variations<br/>├─ Service time inconsistencies<br/>├─ Route feasibility violations<br/>├─ VRP DIMENSION includes depot, matrix excludes it<br/>└─ Customer-only matrix: expected size = (dimension-1)²<br/><br/>🔧 Recovery Strategy:<br/>• Default depot assignment<br/>• Demand normalization<br/>• Capacity scaling warnings<br/>• Route feasibility checks<br/>• Time window standardization<br/>• Service time default values<br/>• Auto-detect customer-only matrices by element count<br/>• Use dimension-1 for VRP EXPLICIT matrix parsing"]
        
        memory_overflow_errors["💾 Memory Overflow Scenarios<br/>Large Dataset Handling<br/>┌─ Dense edge matrices (n² storage)<br/>├─ Very large coordinate datasets<br/>├─ Multiple concurrent large files<br/>├─ Excessive tour data storage<br/>├─ Memory fragmentation issues<br/>└─ Out-of-memory during batch processing<br/><br/>🔧 Recovery Strategy:<br/>• Streaming large file processing<br/>• Sparse matrix representations<br/>• Memory pool management<br/>• Garbage collection optimization<br/>• Batch size dynamic adjustment<br/>• Emergency cleanup procedures"]
    end
    
    subgraph database_errors["🗄️ Database-Level Errors"]
        transaction_errors["💼 Transaction Management Issues<br/>ACID Compliance Failures<br/>┌─ Database lock timeout<br/>├─ Transaction deadlock detection<br/>├─ Connection pool exhaustion<br/>├─ Disk space exhaustion<br/>├─ Concurrent write conflicts<br/>├─ Foreign key constraint violations<br/>└─ Rollback recovery failures<br/><br/>🔧 Recovery Strategy:<br/>• Retry with exponential backoff<br/>• Connection pool monitoring<br/>• Disk space pre-checks<br/>• Conflict resolution strategies<br/>• Partial transaction salvage<br/>• Graceful degradation modes"]
        
        schema_migration_errors["🔄 Schema Evolution Issues<br/>Database Structure Changes<br/>┌─ Missing migration scripts<br/>├─ Incompatible schema versions<br/>├─ Migration rollback failures<br/>├─ Data type conversion errors<br/>├─ Index corruption during migration<br/>├─ Constraint violation during upgrade<br/>└─ Migration partial completion<br/><br/>🔧 Recovery Strategy:<br/>• Backup before migration<br/>• Schema version validation<br/>• Incremental migration steps<br/>• Data preservation strategies<br/>• Rollback procedures<br/>• Migration status tracking"]
        
        query_performance_errors["⚡ Query Performance Issues<br/>Scalability Problems<br/>┌─ Missing or outdated statistics<br/>├─ Query plan regression<br/>├─ Index fragmentation<br/>├─ Memory pressure on queries<br/>├─ Concurrent query interference<br/>├─ Large result set memory issues<br/>└─ Join operation optimization failures<br/><br/>🔧 Recovery Strategy:<br/>• Query plan analysis and hints<br/>• Index maintenance scheduling<br/>• Result set pagination<br/>• Query timeout enforcement<br/>• Resource monitoring and limits<br/>• Alternative query strategies"]
    end
    
    subgraph parallel_processing_errors["👥 Parallel Processing Errors"]
        worker_failures["👷 Worker Process Failures<br/>Multi-Process Issues<br/>┌─ Worker process crash/segfault<br/>├─ Inter-process communication failure<br/>├─ Shared resource contention<br/>├─ Load balancing inefficiencies<br/>├─ Worker hanging/infinite loops<br/>├─ Resource cleanup after failure<br/>└─ Progress reporting inconsistencies<br/><br/>🔧 Recovery Strategy:<br/>• Worker health monitoring<br/>• Automatic worker restart<br/>• Task redistribution<br/>• Resource isolation<br/>• Timeout enforcement<br/>• Progress state recovery"]
        
        resource_contention_errors["🔒 Resource Contention Issues<br/>Concurrent Access Problems<br/>┌─ Database connection limits<br/>├─ File system lock conflicts<br/>├─ Memory allocation competition<br/>├─ CPU core over-subscription<br/>├─ I/O bandwidth saturation<br/>├─ Network resource exhaustion<br/>└─ Temporary file space conflicts<br/><br/>🔧 Recovery Strategy:<br/>• Resource pooling and queueing<br/>• Dynamic resource allocation<br/>• Priority-based scheduling<br/>• Resource usage monitoring<br/>• Graceful degradation modes<br/>• Adaptive concurrency limits"]
        
        synchronization_errors["🔄 Synchronization Issues<br/>Coordination Failures<br/>┌─ Race conditions in file processing<br/>├─ Inconsistent progress reporting<br/>├─ Result aggregation failures<br/>├─ Partial result handling<br/>├─ Worker coordination timeouts<br/>├─ State consistency violations<br/>└─ Cleanup synchronization failures<br/><br/>🔧 Recovery Strategy:<br/>• Atomic operations for critical sections<br/>• State machine for coordination<br/>• Timeout-based recovery<br/>• Partial result preservation<br/>• Coordination health checks<br/>• Emergency stop procedures"]
    end
    
    subgraph edge_case_scenarios["🎯 Specific Edge Case Scenarios"]
        extreme_datasets["📊 Extreme Dataset Characteristics<br/>Boundary Value Testing<br/>┌─ Single-node problems (dimension=1)<br/>├─ Massive problems (dimension>100,000)<br/>├─ Zero-capacity VRP problems<br/>├─ Problems with all nodes at same location<br/>├─ Infinite or NaN coordinate values<br/>├─ Problems with negative coordinates<br/>└─ Degenerate tour solutions<br/><br/>🔧 Handling Strategy:<br/>• Boundary value validation<br/>• Special case detection<br/>• Alternative processing modes<br/>• Graceful handling warnings<br/>• Performance scaling tests"]
        
        malicious_inputs["🛡️ Malicious/Adversarial Inputs<br/>Security Considerations<br/>┌─ Extremely deep file paths<br/>├─ Files with zip bombs (compression)<br/>├─ Symlink attacks and path traversal<br/>├─ Files designed to cause crashes<br/>├─ Resource exhaustion attacks<br/>├─ Injection through file names<br/>└─ Memory exhaustion patterns<br/><br/>🔧 Security Measures:<br/>• Path sanitization and validation<br/>• Resource limit enforcement<br/>• Input validation and sanitization<br/>• Sandboxed processing environment<br/>• Anomaly detection<br/>• Rate limiting and throttling"]
        
        legacy_compatibility["🕰️ Legacy Format Compatibility<br/>Historical TSPLIB Variants<br/>┌─ Old TSPLIB format variations<br/>├─ Non-standard section extensions<br/>├─ Vendor-specific format modifications<br/>├─ Academic format experiments<br/>├─ Encoding variations across regions<br/>├─ Different comment conventions<br/>└─ Missing or implied specifications<br/><br/>🔧 Compatibility Strategy:<br/>• Format version detection<br/>• Progressive parsing fallbacks<br/>• Migration path suggestions<br/>• Legacy format documentation<br/>• Backward compatibility modes<br/>• Format normalization tools"]
    end
    
    %% Error flow connections
    file_system_errors --> format_errors
    encoding_errors --> format_errors
    size_limit_errors --> memory_overflow_errors
    
    format_errors --> data_consistency_errors
    data_consistency_errors --> edge_weight_errors
    edge_weight_errors --> index_conversion_errors
    
    index_conversion_errors --> matrix_format_errors
    matrix_format_errors --> namespace_consistency_errors
    namespace_consistency_errors --> vrp_specific_errors
    vrp_specific_errors --> memory_overflow_errors
    memory_overflow_errors --> transaction_errors
    
    transaction_errors --> schema_migration_errors
    schema_migration_errors --> query_performance_errors
    
    worker_failures --> resource_contention_errors
    resource_contention_errors --> synchronization_errors
    
    query_performance_errors --> worker_failures
    synchronization_errors --> extreme_datasets
    extreme_datasets --> malicious_inputs
    malicious_inputs --> legacy_compatibility
    
    classDef inputError fill:#ffcdd2,stroke:#d32f2f,stroke-width:2px
    classDef parsingError fill:#f8bbd9,stroke:#c2185b,stroke-width:2px
    classDef transformError fill:#e1bee7,stroke:#7b1fa2,stroke-width:2px
    classDef databaseError fill:#c5cae9,stroke:#3f51b5,stroke-width:2px
    classDef parallelError fill:#b3e5fc,stroke:#0288d1,stroke-width:2px
    classDef edgeCase fill:#b2dfdb,stroke:#00695c,stroke-width:2px
    
    class file_system_errors,encoding_errors,size_limit_errors inputError
    class format_errors,data_consistency_errors,edge_weight_errors parsingError
    class index_conversion_errors,matrix_format_errors,namespace_consistency_errors,vrp_specific_errors,memory_overflow_errors transformError
    class transaction_errors,schema_migration_errors,query_performance_errors databaseError
    class worker_failures,resource_contention_errors,synchronization_errors parallelError
    class extreme_datasets,malicious_inputs,legacy_compatibility edgeCase```
