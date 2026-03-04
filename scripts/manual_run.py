
import logging
import sys
import json
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("manual_run")

# Resolve project paths
REPO_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = REPO_ROOT / "config.yaml"

from src.graph.connection import load_full_config, create_driver, verify_connectivity
from src.graph.ppr import PPRConfig, create_gds_client
from src.retrieval.pipeline import run_retrieval_pipeline

def main():
    # 1. Load configuration
    logger.info(f"Loading config from {_CONFIG_PATH}")
    raw_config = load_full_config(_CONFIG_PATH)
    
    neo4j_section = raw_config.get("neo4j", {})
    ppr_section = raw_config.get("ppr", {})
    mcp_section = raw_config.get("mcp", {})

    from src.graph.connection import Neo4jConfig
    neo4j_config = Neo4jConfig(
        uri=neo4j_section.get("uri", "neo4j://localhost:7687"),
        username=neo4j_section.get("username", "neo4j"),
        password=neo4j_section.get("password", ""),
        database=neo4j_section.get("database", "neo4j"),
    )
    
    # Resolve project_root relative to the config file location.
    raw_project_root = raw_config.get("project_root", ".")
    project_root = str(REPO_ROOT / raw_project_root)

    # 2. Connect to Neo4j
    driver = create_driver(neo4j_config)
    if not verify_connectivity(driver):
        logger.error("Neo4j is not reachable. Ensure it's running.")
        sys.exit(1)
    
    gds = create_gds_client(driver)
    
    # 3. Get input from user
    print("\n--- CodeGraph Retrieval Pipeline Manual Test ---")
    task_description = input("Enter a task description (e.g., 'fix auth timeout'): ")
    if not task_description:
        task_description = "fix authentication bug"
        print(f"Using default: '{task_description}'")
    
    # 4. Run the pipeline
    logger.info("Running retrieval pipeline...")
    try:
        results = run_retrieval_pipeline(
            driver=driver,
            gds=gds,
            task_description=task_description,
            project_root=project_root,
        )
        
        # 5. Display results
        if not results:
            print("\nNo results found. Did you build the graph first?")
            print("Try running: python -m scripts.demo_neo4j to populate some data.")
        else:
            print(f"\nFound {len(results)} results:")
            print("-" * 80)
            for i, result in enumerate(results, start=1):
                print(f"{i}. [{result.entity_name}] (Score: {result.relevance_score:.4f})")
                print(f"   File: {result.file_path}:{result.line_start}-{result.line_end}")
                print(f"   Tokens: {result.token_count}")
                snippet = result.source_code.splitlines()[:5]
                print("   Snippet:")
                for line in snippet:
                    print(f"     {line}")
                if len(result.source_code.splitlines()) > 5:
                    print("     ...")
                print("-" * 80)
    finally:
        driver.close()

if __name__ == "__main__":
    main()
