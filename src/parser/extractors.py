"""Entity extraction functions — take an AST root node and return entity dataclasses."""

from tree_sitter import Node

from src.parser.models import (
    CallEntity,
    ClassEntity,
    FunctionEntity,
    ImportEntity,
    MethodEntity,
)
from src.parser.node_utils import (
    find_enclosing_scope,
    get_class_bases,
    get_docstring,
    get_function_signature,
    is_stdlib_module,
    node_text,
)


def extract_functions(root: Node, source: bytes, file_path: str) -> list[FunctionEntity]:
    """Extract top-level function definitions (not methods inside classes)."""
    functions: list[FunctionEntity] = []
    for node in root.children:
        actual_node = node
        if node.type == "decorated_definition":
            for ch in node.children:
                if ch.type == "function_definition":
                    actual_node = ch
                    break
            else:
                continue
        if actual_node.type != "function_definition":
            continue
        name = ""
        body_node = None
        for ch in actual_node.children:
            if ch.type == "identifier":
                name = node_text(ch, source)
            elif ch.type == "block":
                body_node = ch
        if not name:
            continue
        functions.append(
            FunctionEntity(
                name=name,
                file_path=file_path,
                line_number=actual_node.start_point[0] + 1,
                end_line=actual_node.end_point[0] + 1,
                signature=get_function_signature(actual_node, source),
                docstring=get_docstring(body_node, source),
            )
        )
    return functions


def extract_classes(root: Node, source: bytes, file_path: str) -> list[ClassEntity]:
    """Extract class definitions from the module root."""
    classes: list[ClassEntity] = []
    for node in root.children:
        actual_node = node
        if node.type == "decorated_definition":
            for ch in node.children:
                if ch.type == "class_definition":
                    actual_node = ch
                    break
            else:
                continue
        if actual_node.type != "class_definition":
            continue
        name = ""
        for ch in actual_node.children:
            if ch.type == "identifier":
                name = node_text(ch, source)
                break
        if not name:
            continue
        classes.append(
            ClassEntity(
                name=name,
                file_path=file_path,
                line_number=actual_node.start_point[0] + 1,
                end_line=actual_node.end_point[0] + 1,
                bases=get_class_bases(actual_node, source),
            )
        )
    return classes


def extract_methods(root: Node, source: bytes, file_path: str) -> list[MethodEntity]:
    """Extract all methods from all classes in the module."""
    methods: list[MethodEntity] = []
    for node in root.children:
        actual_node = node
        if node.type == "decorated_definition":
            for ch in node.children:
                if ch.type == "class_definition":
                    actual_node = ch
                    break
            else:
                continue
        if actual_node.type != "class_definition":
            continue
        class_name = ""
        for ch in actual_node.children:
            if ch.type == "identifier":
                class_name = node_text(ch, source)
                break
        if not class_name:
            continue
        _collect_methods_from_class(actual_node, class_name, source, file_path, methods)
    return methods


def _collect_methods_from_class(
    class_node: Node,
    class_name: str,
    source: bytes,
    file_path: str,
    methods: list[MethodEntity],
) -> None:
    """Populate methods list with MethodEntity objects from a class body."""
    body_node = None
    for ch in class_node.children:
        if ch.type == "block":
            body_node = ch
            break
    if body_node is None:
        return

    for item in body_node.children:
        actual = item
        if item.type == "decorated_definition":
            for ch in item.children:
                if ch.type == "function_definition":
                    actual = ch
                    break
            else:
                continue
        if actual.type != "function_definition":
            continue
        name = ""
        body = None
        for ch in actual.children:
            if ch.type == "identifier":
                name = node_text(ch, source)
            elif ch.type == "block":
                body = ch
        if not name:
            continue
        methods.append(
            MethodEntity(
                name=name,
                class_name=class_name,
                file_path=file_path,
                line_number=actual.start_point[0] + 1,
                end_line=actual.end_point[0] + 1,
                signature=get_function_signature(actual, source),
                docstring=get_docstring(body, source),
            )
        )


def extract_imports(root: Node, source: bytes, _file_path: str) -> list[ImportEntity]:
    """Extract non-stdlib import statements from the module."""
    imports: list[ImportEntity] = []
    for node in root.children:
        if node.type == "import_from_statement":
            imports.extend(_parse_import_from(node, source))
        elif node.type == "import_statement":
            imports.extend(_parse_import(node, source))
    return imports


def _parse_import_from(node: Node, source: bytes) -> list[ImportEntity]:
    """Parse a 'from X import Y' statement."""
    results: list[ImportEntity] = []
    module_parts: list[str] = []
    imported_names: list[str] = []
    is_relative = False

    i = 0
    children = node.children

    while i < len(children) and children[i].type == "from":
        i += 1

    if i < len(children) and children[i].type == "relative_import":
        is_relative = True
        rel_node = children[i]
        for ch in rel_node.children:
            if ch.type == "dotted_name":
                module_parts.append(node_text(ch, source))
        i += 1
    else:
        while i < len(children) and children[i].type in (".", "..."):
            is_relative = True
            i += 1
        if i < len(children) and children[i].type in ("dotted_name", "identifier"):
            module_parts.append(node_text(children[i], source))
            i += 1

    while i < len(children) and children[i].type == "import":
        i += 1

    for j in range(i, len(children)):
        child = children[j]
        if child.type == "dotted_name":
            imported_names.append(node_text(child, source))
        elif child.type == "identifier":
            imported_names.append(node_text(child, source))
        elif child.type == "aliased_import":
            for ch in child.children:
                if ch.type in ("dotted_name", "identifier"):
                    imported_names.append(node_text(ch, source))
                    break
        elif child.type == "wildcard_import":
            imported_names.append("*")

    module_path = ".".join(module_parts) if module_parts else ""

    if module_path and is_stdlib_module(module_path):
        return []

    results.append(
        ImportEntity(
            module_path=module_path,
            imported_names=tuple(imported_names),
            is_relative=is_relative,
            line_number=node.start_point[0] + 1,
        )
    )
    return results


def _parse_import(node: Node, source: bytes) -> list[ImportEntity]:
    """Parse a plain 'import X' statement."""
    results: list[ImportEntity] = []
    for child in node.children:
        if child.type == "dotted_name":
            module_path = node_text(child, source)
            if is_stdlib_module(module_path):
                continue
            results.append(
                ImportEntity(
                    module_path=module_path,
                    imported_names=(),
                    is_relative=False,
                    line_number=node.start_point[0] + 1,
                )
            )
        elif child.type == "aliased_import":
            for ch in child.children:
                if ch.type in ("dotted_name", "identifier"):
                    module_path = node_text(ch, source)
                    if is_stdlib_module(module_path):
                        continue
                    results.append(
                        ImportEntity(
                            module_path=module_path,
                            imported_names=(),
                            is_relative=False,
                            line_number=node.start_point[0] + 1,
                        )
                    )
                    break
    return results


def extract_calls(root: Node, source: bytes, _file_path: str) -> list[CallEntity]:
    """Extract all call expressions and their enclosing scope."""
    calls: list[CallEntity] = []
    _walk_calls(root, source, calls)
    return calls


def _walk_calls(node: Node, source: bytes, calls: list[CallEntity]) -> None:
    """Recursively walk the AST collecting call nodes."""
    if node.type == "call":
        func_node = node.children[0] if node.children else None
        if func_node is not None:
            calls.append(
                CallEntity(
                    caller_name=find_enclosing_scope(node, source),
                    callee_name=node_text(func_node, source),
                    line_number=node.start_point[0] + 1,
                )
            )
    for child in node.children:
        _walk_calls(child, source, calls)
