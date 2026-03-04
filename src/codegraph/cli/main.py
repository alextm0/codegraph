"""Main CLI implementation."""

import argparse
import sys
import logging
from pathlib import Path

from codegraph.utils.config import load_raw_config, resolve_project_root
from codegraph.utils.logging import setup_logging
from codegraph.core.graph import create_driver, load_config, clear_database, build_graph
from codegraph.core.parser import create_parser, parse_directory

logger = logging.getLogger(__name__)

def cli():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="CodeGraph CLI")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # rebuild command
    rebuild_parser = subparsers.add_parser("rebuild", help="Clear and rebuild the code graph")
    
    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    
    args = parser.parse_args()
    
    # Resolve config path
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        # Try finding it in REPO_ROOT
        config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    
    if args.command == "rebuild":
        cmd_rebuild(config_path)
    elif args.command == "serve":
        cmd_serve()
    else:
        parser.print_help()

def cmd_rebuild(config_path: Path):
    """Rebuild the graph."""
    setup_logging()
    logger.info("Rebuilding graph using config: %s", config_path)
    
    raw_config = load_raw_config(config_path)
    project_root = resolve_project_root(raw_config, config_path)
    
    # Create driver
    neo4j_config = load_config(config_path)
    driver = create_driver(neo4j_config)
    
    try:
        # 1. Clear DB
        clear_database(driver)
        
        # 2. Parse directory
        parser = create_parser()
        logger.info("Parsing directory: %s", project_root)
        exclude = raw_config.get("parser", {}).get("exclude_patterns", [])
        all_entities = parse_directory(str(project_root), parser, exclude_patterns=exclude)
        
        # 3. Build graph
        build_graph(driver, all_entities)
        logger.info("Graph rebuild complete")
    finally:
        driver.close()

def cmd_serve():
    """Start MCP server."""
    from codegraph.mcp.server import main as serve_main
    serve_main()

if __name__ == "__main__":
    cli()
