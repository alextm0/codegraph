import os
from pathlib import Path
from codegraph.core.graph.connection import create_driver, load_config
from codegraph.core.graph.ppr import create_gds_client, PPRConfig
from codegraph.core.retrieval.pipeline import run_retrieval_pipeline

def run_test_queries():
    config_path = Path("config.yaml").resolve()
    if not config_path.exists():
        print("Error: config.yaml not found in current directory.")
        return
    config = load_config(config_path)
    driver = create_driver(config)
    gds = create_gds_client(driver)
    
    project_root = os.getcwd()
    
    queries = [
        "Refactor the visualizer server to use the core retrieval pipeline",
        "Fix the bug where BM25 results are empty in the query response",
        "Add rate limiting to the FastAPI endpoints",
        "Implement a new parser for TypeScript files",
    ]
    
    ppr_config = PPRConfig(top_k=5)
    
    print(f"{'QUERY':<60} | {'TOP RESULTS'}")
    print("-" * 120)
    
    for q in queries:
        results = run_retrieval_pipeline(
            driver=driver,
            gds=gds,
            task_description=q,
            project_root=project_root,
            ppr_config=ppr_config
        )
        
        top_entities = [r.qualified_name for r in results[:3]]
        print(f"{q:<60} | {', '.join(top_entities)}")

if __name__ == "__main__":
    run_test_queries()
