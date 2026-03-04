
import logging
import os
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

from codegraph.core.graph import (
    Neo4jConfig,
    create_driver,
    verify_connectivity,
    clear_database,
    build_graph,
)
from codegraph.core.parser import create_parser, parse_directory
from codegraph.utils.logging import setup_logging
from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.ignore import load_ignore_patterns

def main():
    setup_logging()
    
    # 1. Load configuration
    logger.info(f"Loading config from {_CONFIG_PATH}")
    raw_config = load_raw_config(_CONFIG_PATH)
    project_root = resolve_project_root(raw_config, _CONFIG_PATH)
    
    # 2. Connect to Neo4j
    # Construct Neo4jConfig preferring environment variables
    neo4j_section = raw_config.get("neo4j", {})
    
    # Read password, ensuring it is provided
    password = os.environ.get("NEO4J_PASSWORD", neo4j_section.get("password"))
    if not password:
        logger.error("Missing mandatory Neo4j configuration: NEO4J_PASSWORD must be set in environment or config.yaml")
        sys.exit(1)

    neo4j_config = Neo4jConfig(
        uri=os.environ.get("NEO4J_URI", neo4j_section.get("uri", "bolt://localhost:7687")),
        username=os.environ.get("NEO4J_USERNAME", neo4j_section.get("username", "neo4j")),
        password=password,
        database=os.environ.get("NEO4J_DATABASE", neo4j_section.get("database", "neo4j")),
    )
    
    driver = create_driver(neo4j_config)
    try:
        if not verify_connectivity(driver):
            logger.error("Neo4j is not reachable. Ensure it's running.")
            sys.exit(1)
            
        # 3. Parse project
        logger.info(f"Parsing project at {project_root}...")
        parser = create_parser()
        
        # Load ignore patterns from .cgignore and merge with config
        ignore_file = project_root / ".cgignore"
        exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
        # Also check top-level exclude_patterns as seen in config.yaml
        if not exclude:
            exclude = raw_config.get("exclude_patterns", [])
            
        if ignore_file.exists():
            logger.info("Loading ignore patterns from %s", ignore_file)
            exclude.extend(load_ignore_patterns(ignore_file))
            
        all_entities = parse_directory(str(project_root), parser, exclude_patterns=exclude)
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
