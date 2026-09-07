```mermaid
---
config:
  theme: base
  themeVariables:
    primaryColor: '#e8f4f8'
    primaryTextColor: '#0d47a1'
    primaryBorderColor: '#1565c0'
    lineColor: '#1976d2'
    fontFamily: 'Segoe UI, Arial, sans-serif'
    fontSize: 10px
    background: '#fafafa'
  flowchart:
    htmlLabels: true
    curve: basis
    useMaxWidth: true
    diagramPadding: 20
title: Complete Processing Pipeline Flow - TSPLIB95 ETL System
---
flowchart TD
    subgraph input_layer["📁 Input Layer"]
        file_discovery["🔍 File Discovery<br/>Scanner.scan_files()<br/>┌─ Recursive directory walk<br/>├─ Pattern matching: *.tsp, *.vrp, etc.<br/>├─ File size validation<br/>├─ Permission checks<br/>└─ Batch grouping by size"]
        
        change_detection["⏱️ Change Detection<br/>UpdateManager.detect_changes()<br/>┌─ File modification time check<br/>├─ Content hash comparison<br/>├─ Database record lookup<br/>└─ Skip unchanged files (unless --force)"]
        
        file_validation["✅ File Validation<br/>validate_file_size()<br/>┌─ Size limit check (default 100MB)<br/>├─ Read permission verification<br/>├─ Character encoding detection<br/>└─ Basic format sanity check"]
    end
    
    subgraph processing_layer["⚙️ Processing Layer"]
        subgraph parallel_coord["👥 Parallel Coordination"]
            batch_manager["📦 Batch Manager<br/>ParallelProcessor.process_batches()<br/>┌─ Group files by estimated processing time<br/>├─ Assign batches to available workers<br/>├─ Monitor memory usage per worker<br/>└─ Handle worker failures and recovery"]
            
            worker_pool["👷 Worker Pool<br/>Process Pool (configurable size)<br/>┌─ Independent parser instances<br/>├─ Local database connections<br/>├─ Memory limit enforcement<br/>└─ Progress reporting to coordinator"]
        end
        
        subgraph worker_process["🔧 Worker Process (Per File)"]
            parse_phase["📊 Phase 1: Parse<br/>TSPLIBParser.parse_file()<br/>┌─ Load file with tsplib95 library<br/>├─ Extract StandardProblem object<br/>├─ Validate TSPLIB format compliance<br/>├─ Handle SPECIAL distance types<br/>└─ Preserve 1-based indexing"]
            
            validate_phase["🔍 Phase 1.5: Validate<br/>validate_problem_data()<br/>┌─ Check dimension consistency<br/>├─ Validate coordinate ranges<br/>├─ Verify tour feasibility<br/>├─ Check capacity constraints (VRP)<br/>└─ Handle missing or invalid data"]
            
            transform_phase["🔄 Phase 2: Transform<br/>DataTransformer.transform_problem()<br/>┌─ Convert 1-based → 0-based indexing<br/>├─ Normalize node data structure<br/>├─ Process edges (EXPLICIT only)<br/>├─ Clean and validate coordinates<br/>└─ Structure for database insertion"]
            
            load_phase["💾 Phase 3: Load<br/>Parallel Database + JSON Output<br/>┌─ DatabaseManager.insert_problem()<br/>├─ JSONWriter.write_problem()<br/>├─ Update file tracking record<br/>└─ Commit transaction or rollback"]
        end
    end
    
    subgraph error_handling["🚨 Error Handling & Recovery"]
        error_classification["🏷️ Error Classification<br/>Exception Hierarchy<br/>┌─ ParsingError: TSPLIB format issues<br/>├─ ValidationError: Data integrity problems<br/>├─ DatabaseError: Storage/transaction issues<br/>├─ FileProcessingError: I/O problems<br/>└─ ConfigurationError: Setup issues"]
        
        recovery_strategies["🔄 Recovery Strategies<br/>Based on Error Type<br/>┌─ Retry with relaxed validation<br/>├─ Skip corrupted file sections<br/>├─ Fallback to partial data extraction<br/>├─ Continue processing other files<br/>└─ Detailed logging for manual review"]
        
        graceful_degradation["⚠️ Graceful Degradation<br/>When Errors Occur<br/>┌─ Preserve partial results<br/>├─ Update processing status<br/>├─ Generate detailed error report<br />├─ Continue with remaining files<br/>└─ Provide recovery recommendations"]
    end
    
    subgraph output_layer["📤 Output Layer"]
        subgraph database_output["🗄️ Database Output"]
            db_transaction["💼 Database Transaction<br/>ACID Compliance<br/>┌─ BEGIN TRANSACTION<br/>├─ Insert into problems table<br/>├─ Bulk insert nodes<br/>├─ Bulk insert edges (if EXPLICIT)<br/>├─ Insert tours (if available)<br/>├─ Update file_tracking<br/>└─ COMMIT or ROLLBACK"]
            
            db_optimization["⚡ Performance Optimization<br/>Bulk Operations<br/>┌─ Prepared statements<br/>├─ Batch inserts (100-1000 rows)<br/>├─ Index maintenance<br/>├─ Memory-mapped I/O<br/>└─ Connection pooling"]
        end
        
        subgraph json_output["📄 JSON Output"]
            json_structure["📋 JSON Structuring<br/>Flattened Format<br/>┌─ Problem metadata object<br/>├─ Nodes array (0-based indexing)<br/>├─ Solution data (if available)<br/>├─ Metadata (file info, timing)<br/>└─ Validation checksums"]
            
            json_writing["✍️ File Writing<br/>Atomic Operations<br/>┌─ Write to temporary file<br/>├─ Validate JSON structure<br/>├─ Atomic rename operation<br/>├─ Set appropriate permissions<br/>└─ Update directory index"]
        end
    end
    
    subgraph monitoring_layer["📊 Monitoring & Reporting"]
        progress_tracking["📈 Progress Tracking<br/>Real-time Monitoring<br/>┌─ Files processed / total<br/>├─ Processing rate (files/sec)<br/>├─ Estimated time remaining<br/>├─ Memory usage per worker<br/>└─ Error rate monitoring"]
        
        performance_metrics["⏱️ Performance Metrics<br/>Detailed Statistics<br/>┌─ Parse time per file<br/>├─ Transform time per file<br/>├─ Database insertion time<br/>├─ JSON writing time<br/>└─ End-to-end processing time"]
        
        result_summary["📋 Result Summary<br/>Processing Report<br/>┌─ Total files processed<br/>├─ Success/failure counts<br/>├─ Performance statistics<br/>├─ Error summary by type<br/>└─ Recommendations for failures"]
    end
    
    subgraph memory_management["🧠 Memory Management"]
        memory_monitoring["📊 Memory Monitoring<br/>Per-Worker Tracking<br/>┌─ RSS (Resident Set Size)<br/>├─ Peak memory usage<br/>├─ Memory growth rate<br/>└─ GC trigger thresholds"]
        
        memory_limits["🚫 Memory Limits<br/>Enforcement Strategy<br/>┌─ Configurable per-worker limit<br/>├─ Batch size adjustment<br/>├─ Emergency garbage collection<br/>├─ Process restart if needed<br/>└─ User notification on limits"]
        
        memory_optimization["⚡ Memory Optimization<br/>Efficiency Techniques<br/>┌─ Streaming large file processing<br/>├─ Lazy edge computation<br/>├─ Object pooling for frequent allocations<br/>├─ Reference cycle detection<br/>└─ Explicit cleanup after batch"]
    end
    
    %% Flow connections
    file_discovery --> change_detection
    change_detection --> file_validation
    file_validation --> batch_manager
    batch_manager --> worker_pool
    worker_pool --> parse_phase
    parse_phase --> validate_phase
    validate_phase --> transform_phase
    transform_phase --> load_phase
    
    %% Error handling connections
    parse_phase --> error_classification
    validate_phase --> error_classification
    transform_phase --> error_classification
    load_phase --> error_classification
    error_classification --> recovery_strategies
    recovery_strategies --> graceful_degradation
    
    %% Output connections
    load_phase --> db_transaction
    load_phase --> json_structure
    db_transaction --> db_optimization
    json_structure --> json_writing
    
    %% Monitoring connections
    worker_pool --> progress_tracking
    parse_phase --> performance_metrics
    transform_phase --> performance_metrics
    load_phase --> performance_metrics
    batch_manager --> result_summary
    
    %% Memory management connections
    worker_pool --> memory_monitoring
    memory_monitoring --> memory_limits
    memory_limits --> memory_optimization
    memory_optimization --> batch_manager
    
    classDef inputLayer fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef processingLayer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef errorHandling fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    classDef outputLayer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef monitoringLayer fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef memoryManagement fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    
    class file_discovery,change_detection,file_validation inputLayer
    class batch_manager,worker_pool,parse_phase,validate_phase,transform_phase,load_phase processingLayer
    class error_classification,recovery_strategies,graceful_degradation errorHandling
    class db_transaction,db_optimization,json_structure,json_writing outputLayer
    class progress_tracking,performance_metrics,result_summary monitoringLayer
    class memory_monitoring,memory_limits,memory_optimization memoryManagement```
