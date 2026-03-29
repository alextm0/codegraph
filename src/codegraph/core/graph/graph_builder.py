"""Batch graph creation: write nodes and edges into Neo4j via UNWIND."""

import logging
from collections.abc import Callable

from neo4j import Driver, ManagedTransaction

from codegraph.core.parser.models import FileEntities
from codegraph.core.graph.utils import normalize_path
from codegraph.core.graph.resolution import (
    _PYTHON_BUILTINS,
    _build_entity_lookup,
    _build_import_map,
    _resolve_caller,
    _resolve_callee,
    _resolve_base_class,
    _resolve_import_to_file_path,
)

logger = logging.getLogger(__name__)

# Base edge weights by relationship type.
# All values are intentionally 1.0 (uniform). IDF reweighting via apply_idf_weights()
# overwrites these before each GDS projection, so per-type differentiation here
# would be overwritten anyway. See DEC-007.
EDGE_WEIGHTS: dict[str, float] = {
    "INHERITS_FROM": 1.0,
    "CALLS": 1.0,
    "IMPORTS": 1.0,
    "CONTAINS": 1.0,
    "CO_LOCATED": 0.3,
}


def clear_database(driver: Driver) -> int:
    """Delete all nodes and edges. Returns the number of nodes deleted."""
    with driver.session() as session:
        result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
        record = result.single()
        count = record["deleted"] if record else 0
        logger.info("Cleared database: %d nodes deleted", count)
        return count


def ensure_constraints(driver: Driver) -> None:
    """Create uniqueness constraints/indexes for fast MERGE."""
    labels = ["File", "Function", "Class", "Method"]
    with driver.session() as session:
        for label in labels:
            try:
                session.run(
                    f"CREATE CONSTRAINT unique_{label.lower()}_qname "
                    f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.qualified_name IS UNIQUE"
                )
            except Exception as e:
                logger.warning("Failed to create constraint for %s: %s", label, e)
    logger.info("Constraints ensured.")


def build_graph(
    driver: Driver,
    all_entities: list[FileEntities],
    progress_callback: Callable[[str, int], None] | None = None,
    create_colocation_edges: bool = False,
) -> dict[str, int]:
    """Build the full code graph from parsed entities.

    Args:
        driver: Active Neo4j driver.
        all_entities: Parsed entities from parse_directory().
        progress_callback: Optional callable(stage_name, count) invoked after each
            write stage completes. stage_name is e.g. "File nodes", "CALLS edges".
        create_colocation_edges: When True, create File→File CO_LOCATED edges for
            files in the same directory (weight 0.3). Disabled by default — iteration 3
            benchmarks showed neutral/negative effect on R@10. See DEC-020.

    Returns:
        Dict with creation counts keyed by node/edge type.
    """
    def _report(stage: str, count: int) -> None:
        logger.debug("Graph build: %s → %d", stage, count)
        if progress_callback:
            progress_callback(stage, count)

    lookup = _build_entity_lookup(all_entities)
    all_file_paths = [normalize_path(fe.file_path) for fe in all_entities]
    counts: dict[str, int] = {"File": 0, "Function": 0, "Class": 0, "Method": 0,
                               "CONTAINS": 0, "CALLS": 0, "IMPORTS": 0, "INHERITS_FROM": 0,
                               "CO_LOCATED": 0}

    ensure_constraints(driver)

    with driver.session() as session:
        # --- Nodes ---
        counts["File"] = session.execute_write(_create_file_nodes, all_entities)
        _report("File nodes", counts["File"])
        counts["Function"] = session.execute_write(_create_function_nodes, all_entities)
        _report("Function nodes", counts["Function"])
        counts["Class"] = session.execute_write(_create_class_nodes, all_entities)
        _report("Class nodes", counts["Class"])
        counts["Method"] = session.execute_write(_create_method_nodes, all_entities)
        _report("Method nodes", counts["Method"])

        # --- Edges ---
        counts["CONTAINS"] += session.execute_write(_create_contains_function_edges, all_entities)
        counts["CONTAINS"] += session.execute_write(_create_contains_class_edges, all_entities)
        counts["CONTAINS"] += session.execute_write(_create_contains_method_edges, all_entities)
        _report("CONTAINS edges", counts["CONTAINS"])
        counts["INHERITS_FROM"] = session.execute_write(
            _create_inherits_edges, all_entities, lookup, all_file_paths,
        )
        _report("INHERITS_FROM edges", counts["INHERITS_FROM"])
        counts["CALLS"] = session.execute_write(
            _create_calls_edges, all_entities, lookup, all_file_paths,
        )
        _report("CALLS edges", counts["CALLS"])
        counts["IMPORTS"] = session.execute_write(_create_imports_edges, all_entities)
        _report("IMPORTS edges", counts["IMPORTS"])
        if create_colocation_edges:
            counts["CO_LOCATED"] = session.execute_write(_create_colocation_edges, all_entities)
            _report("CO_LOCATED edges", counts["CO_LOCATED"])

    logger.info("Graph built: %s", counts)
    return counts


# ---------------------------------------------------------------------------
# Private: node creation
# ---------------------------------------------------------------------------

def _create_file_nodes(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """Batch-create File nodes."""
    nodes = [{"qualified_name": normalize_path(fe.file_path), "name": normalize_path(fe.file_path), "file_path": normalize_path(fe.file_path)}
             for fe in all_entities]
    result = tx.run(
        """
        UNWIND $nodes AS n
        MERGE (f:File {qualified_name: n.qualified_name})
        SET f.name = n.name, f.file_path = n.file_path
        RETURN count(f) AS created
        """,
        nodes=nodes,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_function_nodes(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """Batch-create Function nodes."""
    nodes = [
        {
            "qualified_name": f"{normalize_path(fn.file_path)}::{fn.name}",
            "name": fn.name,
            "file_path": normalize_path(fn.file_path),
            "line_number": fn.line_number,
            "end_line": fn.end_line,
            "signature": fn.signature,
            "docstring": fn.docstring or "",
        }
        for fe in all_entities
        for fn in fe.functions
    ]
    if not nodes:
        return 0
    result = tx.run(
        """
        UNWIND $nodes AS n
        MERGE (f:Function {qualified_name: n.qualified_name})
        SET f.name = n.name, f.file_path = n.file_path,
            f.line_number = n.line_number, f.end_line = n.end_line,
            f.signature = n.signature, f.docstring = n.docstring
        RETURN count(f) AS created
        """,
        nodes=nodes,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_class_nodes(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """Batch-create Class nodes."""
    nodes = [
        {
            "qualified_name": f"{normalize_path(cls.file_path)}::{cls.name}",
            "name": cls.name,
            "file_path": normalize_path(cls.file_path),
            "line_number": cls.line_number,
            "end_line": cls.end_line,
            "bases": list(cls.bases),
        }
        for fe in all_entities
        for cls in fe.classes
    ]
    if not nodes:
        return 0
    result = tx.run(
        """
        UNWIND $nodes AS n
        MERGE (c:Class {qualified_name: n.qualified_name})
        SET c.name = n.name, c.file_path = n.file_path,
            c.line_number = n.line_number, c.end_line = n.end_line,
            c.bases = n.bases
        RETURN count(c) AS created
        """,
        nodes=nodes,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_method_nodes(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """Batch-create Method nodes."""
    nodes = [
        {
            "qualified_name": f"{normalize_path(m.file_path)}::{m.class_name}.{m.name}",
            "name": m.name,
            "class_name": m.class_name,
            "file_path": normalize_path(m.file_path),
            "line_number": m.line_number,
            "end_line": m.end_line,
            "signature": m.signature,
            "docstring": m.docstring or "",
        }
        for fe in all_entities
        for m in fe.methods
    ]
    if not nodes:
        return 0
    result = tx.run(
        """
        UNWIND $nodes AS n
        MERGE (m:Method {qualified_name: n.qualified_name})
        SET m.name = n.name, m.class_name = n.class_name, m.file_path = n.file_path,
            m.line_number = n.line_number, m.end_line = n.end_line,
            m.signature = n.signature, m.docstring = n.docstring
        RETURN count(m) AS created
        """,
        nodes=nodes,
    )
    record = result.single()
    return record["created"] if record else 0


# ---------------------------------------------------------------------------
# Private: edge creation
# ---------------------------------------------------------------------------

def _create_contains_function_edges(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """File -[CONTAINS]-> Function edges."""
    edges = [
        {"src": normalize_path(fe.file_path), "dst": f"{normalize_path(fn.file_path)}::{fn.name}", "weight": EDGE_WEIGHTS["CONTAINS"]}
        for fe in all_entities
        for fn in fe.functions
    ]
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src:File {qualified_name: e.src})
        MATCH (dst:Function {qualified_name: e.dst})
        MERGE (src)-[r:CONTAINS]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_contains_class_edges(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """File -[CONTAINS]-> Class edges."""
    edges = [
        {"src": normalize_path(fe.file_path), "dst": f"{normalize_path(cls.file_path)}::{cls.name}", "weight": EDGE_WEIGHTS["CONTAINS"]}
        for fe in all_entities
        for cls in fe.classes
    ]
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src:File {qualified_name: e.src})
        MATCH (dst:Class {qualified_name: e.dst})
        MERGE (src)-[r:CONTAINS]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_contains_method_edges(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """Class -[CONTAINS]-> Method edges."""
    edges = [
        {
            "src": f"{normalize_path(m.file_path)}::{m.class_name}",
            "dst": f"{normalize_path(m.file_path)}::{m.class_name}.{m.name}",
            "weight": EDGE_WEIGHTS["CONTAINS"],
        }
        for fe in all_entities
        for m in fe.methods
    ]
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src:Class {qualified_name: e.src})
        MATCH (dst:Method {qualified_name: e.dst})
        MERGE (src)-[r:CONTAINS]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_inherits_edges(
    tx: ManagedTransaction,
    all_entities: list[FileEntities],
    lookup: dict[str, list[str]],
    all_file_paths: list[str],
) -> int:
    """Class -[INHERITS_FROM]-> Class edges."""
    edges = []
    for fe in all_entities:
        import_map = _build_import_map(fe, all_file_paths)
        for cls in fe.classes:
            src_qname = f"{normalize_path(cls.file_path)}::{cls.name}"
            for base in cls.bases:
                dst_qname = _resolve_base_class(base, lookup, fe.file_path, import_map)
                if dst_qname:
                    edges.append({"src": src_qname, "dst": dst_qname, "weight": EDGE_WEIGHTS["INHERITS_FROM"]})
                else:
                    logger.debug("INHERITS_FROM: could not resolve base '%s' for class '%s'", base, cls.name)
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src:Class {qualified_name: e.src})
        MATCH (dst:Class {qualified_name: e.dst})
        MERGE (src)-[r:INHERITS_FROM]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_calls_edges(
    tx: ManagedTransaction,
    all_entities: list[FileEntities],
    lookup: dict[str, list[str]],
    all_file_paths: list[str],
) -> int:
    """Function/Method -[CALLS]-> Function/Method edges."""
    edges = []
    for fe in all_entities:
        import_map = _build_import_map(fe, all_file_paths)
        for call in fe.calls:
            # Skip calls to Python built-in functions, types, and exceptions
            # (e.g. len, print, frozenset, ValueError).  These are plain names
            # with no dot; dotted names like "obj.method" are never builtins.
            callee = call.callee_name
            if "." not in callee and callee in _PYTHON_BUILTINS:
                continue

            src_qname = _resolve_caller(call.caller_name, fe.file_path)
            dst_qname = _resolve_callee(callee, lookup, fe.file_path, import_map)
            if src_qname and dst_qname:
                edges.append({"src": src_qname, "dst": dst_qname, "weight": EDGE_WEIGHTS["CALLS"]})
            else:
                logger.debug(
                    "CALLS: could not resolve '%s' -> '%s'", call.caller_name, callee
                )
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src {qualified_name: e.src})
        WHERE src:File OR src:Function OR src:Method
        MATCH (dst {qualified_name: e.dst})
        WHERE dst:Function OR dst:Method OR dst:Class
        MERGE (src)-[r:CALLS]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_imports_edges(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """File -[IMPORTS]-> File edges (module path -> file path resolution)."""
    all_file_paths = [normalize_path(fe.file_path) for fe in all_entities]
    edges = []
    for fe in all_entities:
        src_path = normalize_path(fe.file_path)
        for imp in fe.imports:
            dst_path = _resolve_import_to_file_path(imp.module_path, all_file_paths)
            if dst_path:
                edges.append({"src": src_path, "dst": dst_path, "weight": EDGE_WEIGHTS["IMPORTS"]})
            else:
                logger.debug("IMPORTS: could not resolve module '%s' from '%s'", imp.module_path, fe.file_path)
    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS e
        MATCH (src:File {qualified_name: e.src})
        MATCH (dst:File {qualified_name: e.dst})
        MERGE (src)-[r:IMPORTS]->(dst)
        SET r.weight = e.weight
        RETURN count(r) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


def _create_colocation_edges(tx: ManagedTransaction, all_entities: list[FileEntities]) -> int:
    """File -[CO_LOCATED]-> File edges between files in the same directory.

    Directories with >50 files are skipped to avoid O(n^2) edge explosion in
    large repositories (e.g. django has directories with 100+ migration files).
    The CO_LOCATED weight (0.3) is intentionally lower than CALLS/IMPORTS (1.0)
    so co-location is a hint, not a dominant signal. See DEC-020.
    """
    _MAX_DIR_SIZE = 50

    # Group file paths by directory
    from posixpath import dirname
    dirs: dict[str, list[str]] = {}
    for fe in all_entities:
        fp = normalize_path(fe.file_path)
        directory = dirname(fp)
        dirs.setdefault(directory, []).append(fp)

    edges = []
    for directory, file_paths in dirs.items():
        if len(file_paths) > _MAX_DIR_SIZE:
            logger.debug(
                "CO_LOCATED: skipping directory '%s' (%d files > max %d)",
                directory, len(file_paths), _MAX_DIR_SIZE,
            )
            continue
        if len(file_paths) < 2:
            continue
        # Create directed edges between all ordered pairs (a→b and b→a via MERGE)
        weight = EDGE_WEIGHTS["CO_LOCATED"]
        for i, src in enumerate(file_paths):
            for dst in file_paths[i + 1:]:
                edges.append({"src": src, "dst": dst, "weight": weight})

    if not edges:
        return 0
    result = tx.run(
        """
        UNWIND $edges AS edge
        MATCH (a:File {file_path: edge.src})
        MATCH (b:File {file_path: edge.dst})
        MERGE (a)-[r1:CO_LOCATED]->(b)
        SET r1.weight = edge.weight
        MERGE (b)-[r2:CO_LOCATED]->(a)
        SET r2.weight = edge.weight
        RETURN count(r1) AS created
        """,
        edges=edges,
    )
    record = result.single()
    return record["created"] if record else 0


