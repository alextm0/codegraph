"""Batch graph creation: write nodes and edges into Neo4j via UNWIND."""

import builtins
import logging

from neo4j import Driver, ManagedTransaction

from src.parser.models import FileEntities
from src.graph.utils import normalize_path

logger = logging.getLogger(__name__)

# All names exported by the Python builtins module: built-in functions (len,
# print, range, …), built-in types (list, dict, int, …), built-in exceptions
# (ValueError, TypeError, …), and constants (True, False, None, …).
# Calls to any of these are intentionally excluded from CALLS edges because
# they refer to language primitives that are not part of the project graph.
_PYTHON_BUILTINS: frozenset[str] = frozenset(dir(builtins))

# Edge weights by relationship type
EDGE_WEIGHTS: dict[str, float] = {
    "INHERITS_FROM": 1.0,
    "CALLS": 1.0,
    "IMPORTS": 1.0,
    "CONTAINS": 1.0,
}


def clear_database(driver: Driver) -> int:
    """Delete all nodes and edges. Returns the number of nodes deleted."""
    with driver.session() as session:
        result = session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
        record = result.single()
        count = record["deleted"] if record else 0
        logger.info("Cleared database: %d nodes deleted", count)
        return count


def build_graph(driver: Driver, all_entities: list[FileEntities]) -> dict[str, int]:
    """Build the full code graph from parsed entities.

    Returns a dict with creation counts: nodes_created, edges_created.
    """
    lookup = _build_entity_lookup(all_entities)
    all_file_paths = [normalize_path(fe.file_path) for fe in all_entities]
    counts: dict[str, int] = {"File": 0, "Function": 0, "Class": 0, "Method": 0,
                               "CONTAINS": 0, "CALLS": 0, "IMPORTS": 0, "INHERITS_FROM": 0}

    with driver.session() as session:
        # --- Nodes ---
        counts["File"] = session.execute_write(_create_file_nodes, all_entities)
        counts["Function"] = session.execute_write(_create_function_nodes, all_entities)
        counts["Class"] = session.execute_write(_create_class_nodes, all_entities)
        counts["Method"] = session.execute_write(_create_method_nodes, all_entities)

        # --- Edges ---
        counts["CONTAINS"] += session.execute_write(_create_contains_function_edges, all_entities)
        counts["CONTAINS"] += session.execute_write(_create_contains_class_edges, all_entities)
        counts["CONTAINS"] += session.execute_write(_create_contains_method_edges, all_entities)
        counts["INHERITS_FROM"] = session.execute_write(
            _create_inherits_edges, all_entities, lookup, all_file_paths,
        )
        counts["CALLS"] = session.execute_write(
            _create_calls_edges, all_entities, lookup, all_file_paths,
        )
        counts["IMPORTS"] = session.execute_write(_create_imports_edges, all_entities)

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


# ---------------------------------------------------------------------------
# Private: resolution helpers
# ---------------------------------------------------------------------------

def _build_entity_lookup(all_entities: list[FileEntities]) -> dict[str, list[str]]:
    """Map simple name -> list of qualified_names for all classes, functions, and methods."""
    lookup: dict[str, list[str]] = {}
    for fe in all_entities:
        for fn in fe.functions:
            qname = f"{normalize_path(fn.file_path)}::{fn.name}"
            lookup.setdefault(fn.name, []).append(qname)
        for cls in fe.classes:
            qname = f"{normalize_path(cls.file_path)}::{cls.name}"
            lookup.setdefault(cls.name, []).append(qname)
        for m in fe.methods:
            dotted = f"{m.class_name}.{m.name}"
            qname = f"{normalize_path(m.file_path)}::{dotted}"
            lookup.setdefault(dotted, []).append(qname)
            lookup.setdefault(m.name, []).append(qname)
    return lookup


def _build_import_map(fe: FileEntities, all_file_paths: list[str]) -> dict[str, str]:
    """Map imported names -> resolved file path for a single file's imports.

    E.g. if auth_service.py has `from src.utils.crypto import hash_password`,
    returns {"hash_password": "src/utils/crypto.py"}.
    """
    import_map: dict[str, str] = {}
    for imp in fe.imports:
        resolved_path = _resolve_import_to_file_path(imp.module_path, all_file_paths)
        if not resolved_path:
            continue
        if imp.imported_names:
            for name in imp.imported_names:
                import_map[name] = resolved_path
        else:
            # `import foo.bar` — the module itself (no specific names)
            last_segment = imp.module_path.rsplit(".", 1)[-1]
            import_map[last_segment] = resolved_path
    return import_map


def _resolve_caller(caller_name: str, file_path: str) -> str | None:
    """Resolve caller_name to a qualified_name using the file context."""
    norm_fp = normalize_path(file_path)
    if caller_name == "<module>":
        return norm_fp  # File node
    # Try "ClassName.method_name" pattern
    if "." in caller_name:
        class_name, method_name = caller_name.split(".", 1)
        return f"{norm_fp}::{class_name}.{method_name}"
    # Top-level function
    return f"{norm_fp}::{caller_name}"


def _resolve_callee(
    callee_name: str,
    lookup: dict[str, list[str]],
    file_path: str,
    import_map: dict[str, str],
) -> str | None:
    """Resolve callee_name to a qualified_name using import context and entity lookup.

    Priority: imported definition > same-file definition > unique global match.
    """
    candidates = lookup.get(callee_name, [])
    if not candidates:
        return None

    # 1. Was callee_name imported? Check the file's import map.
    imported_file = import_map.get(callee_name)
    if imported_file:
        for qname in candidates:
            if qname.startswith(imported_file + "::"):
                return qname

    # 2. Is callee_name defined in the same file?
    norm_fp = normalize_path(file_path)
    for qname in candidates:
        if qname.startswith(norm_fp + "::"):
            return qname

    # 3. Only one candidate globally — safe to use.
    if len(candidates) == 1:
        return candidates[0]

    # Ambiguous — log and skip rather than guess wrong.
    logger.debug(
        "Ambiguous callee '%s': %d candidates, skipping", callee_name, len(candidates),
    )
    return None


def _resolve_base_class(
    base_name: str,
    lookup: dict[str, list[str]],
    file_path: str,
    import_map: dict[str, str],
) -> str | None:
    """Resolve a base class name using the same priority as _resolve_callee.

    Priority: imported definition > same-file definition > unique global match.
    """
    candidates = lookup.get(base_name, [])
    if not candidates:
        return None

    imported_file = import_map.get(base_name)
    if imported_file:
        for qname in candidates:
            if qname.startswith(imported_file + "::"):
                return qname

    norm_fp = normalize_path(file_path)
    for qname in candidates:
        if qname.startswith(norm_fp + "::"):
            return qname

    if len(candidates) == 1:
        return candidates[0]

    logger.debug("Ambiguous base class '%s': %d candidates, skipping", base_name, len(candidates))
    return None


def _resolve_import_to_file_path(module_path: str, all_file_paths: list[str]) -> str | None:
    """Find a known file path that corresponds to the given dotted module path.

    Strategy: convert 'user_auth.models.user' to 'models/user.py' by progressively
    stripping leading package segments and checking whether any normalized file path
    ends with the resulting suffix. For example, given file paths like
    ['user_auth/models/user.py'], the suffix 'models/user.py' will match.

    Args:
        module_path: Dotted module path, e.g. 'user_auth.services.auth_service'.
        all_file_paths: Pre-normalized (forward-slash) file paths from the parsed repo.

    Returns:
        The matching file path, or None if no match is found.
    """
    if not module_path:
        return None
    parts = module_path.lstrip(".").split(".")
    # Try progressively fewer leading segments stripped (handles different package depths)
    for skip in range(1, len(parts)):
        suffix = "/".join(parts[skip:]) + ".py"
        for fp in all_file_paths:
            if fp == suffix or fp.endswith("/" + suffix):
                return fp
    # Fallback: try matching the full module path as a suffix
    suffix = "/".join(parts) + ".py"
    for fp in all_file_paths:
        if fp == suffix or fp.endswith("/" + suffix):
            return fp
    return None
