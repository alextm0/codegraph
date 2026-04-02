import logging
from pathlib import Path
from neo4j import Driver
from codegraph.core.parser import create_parser, parse_file
from codegraph.core.graph import delete_file_entities, build_graph
from codegraph.core.graph.utils import normalize_path

logger = logging.getLogger(__name__)

def update_file_in_graph(driver: Driver, project_root: str, file_path: str) -> dict:
    """Incrementally update a single file in the graph."""
    abs_path = Path(file_path)
    if not abs_path.is_absolute():
        abs_path = (Path(project_root) / file_path).resolve()
    
    rel_path = normalize_path(str(abs_path.relative_to(project_root)))
    
    logger.info("Incrementally updating: %s", rel_path)
    
    # 1. Delete old entities
    deleted = delete_file_entities(driver, rel_path)
    
    # 2. Re-parse
    if not abs_path.exists():
        logger.info("File %s deleted, removing from graph.", rel_path)
        return {"deleted": deleted, "created": 0}
        
    parser = create_parser()
    try:
        source = abs_path.read_bytes()
        entities = parse_file(source, rel_path, parser)
    except Exception as e:
        logger.error("Failed to parse %s: %s", rel_path, e)
        return {"deleted": deleted, "error": str(e)}
        
    # 3. Re-insert
    # build_graph takes a list of FileEntities
    counts = build_graph(driver, [entities])
    
    return {
        "deleted": deleted,
        "counts": counts
    }
