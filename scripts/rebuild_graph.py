
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("rebuild_graph")

REPO_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = REPO_ROOT / "config.yaml"

from src.graph.connection import load_full_config, create_driver, verify_connectivity
from src.parser.python_parser import create_parser, parse_directory
from src.graph.graph_builder import clear_database, build_graph

def main():
    # 1. Load configuration
    logger.info(f"Loading config from {_CONFIG_PATH}")
    raw_config = load_full_config(_CONFIG_PATH)
    
    neo4j_section = raw_config.get("neo4j", {})
    from src.graph.connection import Neo4jConfig
    neo4j_config = Neo4jConfig(
        uri=neo4j_section.get("uri", "neo4j://localhost:7687"),
        username=neo4j_section.get("username", "neo4j"),
        password=neo4j_section.get("password", ""),
        database=neo4j_section.get("database", "neo4j"),
    )
    
    # Resolve project_root relative to the config file location.
    raw_project_root = raw_config.get("project_root", ".")
    project_root = REPO_ROOT / raw_project_root
    
    # 2. Connect to Neo4j
    driver = create_driver(neo4j_config)
    if not verify_connectivity(driver):
        logger.error("Neo4j is not reachable. Ensure it's running.")
        sys.exit(1)
    
    try:
        # 3. Parse project
        logger.info(f"Parsing project at {project_root}...")
        parser = create_parser()
        all_entities = parse_directory(str(project_root), parser)
        logger.info(f"Parsed {len(all_entities)} files.")
        
        # 4. Rebuild graph
        logger.info("Clearing database and building fresh graph...")
        clear_database(driver)
        counts = build_graph(driver, all_entities)
        
        logger.info("Graph rebuild complete!")
        for key, val in sorted(counts.items()):
            logger.info(f"  {key:16} {val}")
            
    finally:
        driver.close()

if __name__ == "__main__":
    main()
