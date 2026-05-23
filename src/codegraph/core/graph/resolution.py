"""Import-aware entity resolution helpers for the code graph.

Design notes:
- All functions are pure: inputs are parsed entity lists, outputs are qualified_name strings.
  No Neo4j dependency — the entire module is testable without a running database.
- Resolution strategy: build a lookup table (simple_name → qualified_names list) from all
  parsed files, then walk each file's import map to disambiguate ambiguous names.
- Python builtins (len, print, int, …) are filtered out here to avoid polluting the graph
  with edges to names that are not part of the project.
"""

import builtins
import logging

from codegraph.core.parser.models import FileEntities
from codegraph.core.graph.utils import normalize_path

logger = logging.getLogger(__name__)

# All names exported by the Python builtins module: built-in functions (len,
# print, range, …), built-in types (list, dict, int, …), built-in exceptions
# (ValueError, TypeError, …), and constants (True, False, None, …).
# Calls to any of these are intentionally excluded from CALLS edges because
# they refer to language primitives that are not part of the project graph.
_PYTHON_BUILTINS: frozenset[str] = frozenset(dir(builtins))


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
    same_file = [qname for qname in candidates if qname.startswith(norm_fp + "::")]
    if len(same_file) == 1:
        return same_file[0]
    if len(same_file) > 1:
        # Multiple same-file candidates (e.g. ClassA.fit and ClassB.fit) — ambiguous.
        logger.debug(
            "Ambiguous callee '%s' in same file: %d candidates, skipping",
            callee_name,
            len(same_file),
        )
        return None

    # 3. Only one candidate globally — safe to use.
    if len(candidates) == 1:
        return candidates[0]

    # Ambiguous globally — log and skip rather than guess wrong.
    logger.debug(
        "Ambiguous callee '%s': %d candidates, skipping",
        callee_name,
        len(candidates),
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
    same_file = [qname for qname in candidates if qname.startswith(norm_fp + "::")]
    if len(same_file) == 1:
        return same_file[0]
    if len(same_file) > 1:
        logger.debug(
            "Ambiguous base class '%s' in same file: %d candidates, skipping",
            base_name,
            len(same_file),
        )
        return None

    if len(candidates) == 1:
        return candidates[0]

    logger.debug(
        "Ambiguous base class '%s': %d candidates, skipping", base_name, len(candidates)
    )
    return None


def _resolve_import_to_file_path(
    module_path: str, all_file_paths: list[str]
) -> str | None:
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
