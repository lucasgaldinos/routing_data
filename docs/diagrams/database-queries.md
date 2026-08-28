```mermaid
---
config:
  theme: forest
  themeVariables:
    primaryColor: '#e8f5e8'
    primaryTextColor: '#1b5e20'
    primaryBorderColor: '#2e7d32'
    lineColor: '#4caf50'
    fontFamily: 'Segoe UI, Arial, sans-serif'
    fontSize: 12px
    background: '#f9fff9'
  flowchart:
    htmlLabels: true
    curve: basis
    useMaxWidth: true
    diagramPadding: 20
title: Database Query Patterns and Organization
---
flowchart TB
    subgraph problem_types["Problem Type Organization"]
        tsp_probs["TSP Problems<br/>- Classic traveling salesman<br/>- Symmetric distances<br/>- Single tour optimization"]
        vrp_probs["VRP Problems<br/>- Vehicle routing variants<br/>- Capacity constraints<br/>- Depot-based routes"]
        atsp_probs["ATSP Problems<br/>- Asymmetric TSP<br/>- Directional distances<br/>- Matrix-based weights"]
        special_probs["Special Problems<br/>- HCP (Hamiltonian)<br/>- SOP (Sequential ordering)<br/>- Custom distance functions"]
    end
    
    subgraph query_patterns["Common Query Patterns"]
        subgraph basic_queries["Basic Queries"]
            q1["Problem Discovery<br/>SELECT * FROM problems<br/>WHERE type = 'TSP'<br/>AND dimension BETWEEN 50 AND 200<br/>ORDER BY dimension"]
            
            q2["Node Retrieval<br/>SELECT p.name, n.node_id, n.x, n.y<br/>FROM problems p<br/>JOIN nodes n ON p.id = n.problem_id<br/>WHERE p.name = 'gr17'<br/>ORDER BY n.node_id"]
            
            q3["Edge Analysis<br/>SELECT COUNT(*) as edge_count,<br/>AVG(weight) as avg_weight,<br/>MIN(weight) as min_weight,<br/>MAX(weight) as max_weight<br/>FROM edges WHERE problem_id = ?"]
        end
        
        subgraph advanced_queries["Advanced Analytics"]
            q4["Problem Statistics<br/>SELECT type,<br/>COUNT(*) as problem_count,<br/>AVG(dimension) as avg_size,<br/>MIN(dimension) as min_size,<br/>MAX(dimension) as max_size<br/>FROM problems<br/>GROUP BY type"]
            
            q5["Depot Analysis (VRP)<br/>SELECT p.name, COUNT(*) as depot_count<br/>FROM problems p<br/>JOIN nodes n ON p.id = n.problem_id<br/>WHERE p.type = 'VRP'<br/>AND n.is_depot = true<br/>GROUP BY p.id, p.name"]
            
            q6["Distance Distribution<br/>SELECT<br/>CASE<br/>  WHEN weight < 10 THEN '0-10'<br/>  WHEN weight < 50 THEN '10-50'<br/>  WHEN weight < 100 THEN '50-100'<br/>  ELSE '100+'<br/>END as distance_range,<br/>COUNT(*) as count<br/>FROM edges<br/>WHERE problem_id = ?<br/>GROUP BY distance_range"]
        end
    end
    
    subgraph data_organization["Data Organization Strategies"]
        subgraph indexing["Indexing Strategy"]
            idx1["Primary Indexes<br/>- problems.id (clustered)<br/>- nodes.id (clustered)<br/>- edges.id (clustered)"]
            
            idx2["Query Indexes<br/>- problems(type, dimension)<br/>- nodes(problem_id, node_id)<br/>- edges(problem_id, from_node, to_node)"]
            
            idx3["Analytical Indexes<br/>- problems(dimension)<br/>- nodes(problem_id, is_depot)<br/>- edges(problem_id, weight)"]
        end
        
        subgraph partitioning["Data Partitioning"]
            part1["By Problem Type<br/>- Separate tables/views<br/>- Type-specific optimizations<br/>- Specialized queries"]
            
            part2["By Size Category<br/>- Small (< 100 nodes)<br/>- Medium (100-1000 nodes)<br/>- Large (1000+ nodes)"]
            
            part3["By Source Dataset<br/>- TSPLIB original<br/>- VRP benchmark sets<br/>- Custom problems"]
        end
    end
    
    subgraph performance["Performance Considerations"]
        perf1["Bulk Operations<br/>- Batch inserts with transactions<br/>- Prepared statements<br/>- Bulk edge generation"]
        
        perf2["Query Optimization<br/>- Index usage analysis<br/>- Join order optimization<br/>- Materialized views for stats"]
        
        perf3["Storage Efficiency<br/>- Compression for large problems<br/>- Sparse matrix handling<br/>- Archive old datasets"]
    end
    
    %% Styling
    classDef problemType fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef queryBox fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef orgBox fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef perfBox fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    
    class tsp_probs,vrp_probs,atsp_probs,special_probs problemType
    class q1,q2,q3,q4,q5,q6 queryBox
    class idx1,idx2,idx3,part1,part2,part3 orgBox
    class perf1,perf2,perf3 perfBox```
