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
    """
    Collects top-level (module-level) function definitions from a Tree-sitter AST root.
    
    Parameters:
        root (Node): The Tree-sitter root node of the parsed Python module.
        source (bytes): The source file contents used to extract names, signatures, and docstrings.
        file_path (str): The path of the source file associated with the AST.
    
    Returns:
        list[FunctionEntity]: A list of FunctionEntity objects for each module-level function found. Each entity includes the function name, file_path, starting and ending line numbers, signature, and docstring.
    """
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
    """
    Collects class definitions declared at the module level.
    
    Returns:
        classes (list[ClassEntity]): A list of ClassEntity objects representing each top-level class found, with name, file path, start and end line numbers, and base classes.
    """
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
    """
    Collects all methods defined on classes in the given module AST.
    
    Scans top-level class definitions (including those wrapped by decorators) and returns a list of MethodEntity objects linking each method to its declaring class, file path, and source positions.
    
    Returns:
        list[MethodEntity]: A list of method entities found in the module.
    """
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
    """
    Populate the provided list with MethodEntity objects for each method defined in the given class node.
    
    Parameters:
        class_node (Node): Tree-sitter node representing the class definition.
        class_name (str): Name of the class that methods belong to.
        source (bytes): Source file bytes used to extract names, signatures, and docstrings.
        file_path (str): Path of the source file to record in each MethodEntity.
        methods (list[MethodEntity]): List to append MethodEntity instances to (mutated in place).
    
    Notes:
        Only function definitions found directly in the class body are converted into MethodEntity objects; other class-level members are ignored.
    """
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


def extract_imports(root: Node, source: bytes, file_path: str) -> list[ImportEntity]:
    """
    Collect non-standard-library import statements present at the module top level.
    
    Parses both `from ... import ...` and `import ...` forms and excludes imports that resolve to the Python standard library.
    
    Returns:
        list[ImportEntity]: A list of ImportEntity objects describing each non-stdlib import (module path, imported names, whether it is relative, and the statement line number).
    """
    imports: list[ImportEntity] = []
    for node in root.children:
        if node.type == "import_from_statement":
            imports.extend(_parse_import_from(node, source))
        elif node.type == "import_statement":
            imports.extend(_parse_import(node, source))
    return imports


def _parse_import_from(node: Node, source: bytes) -> list[ImportEntity]:
    """
    Extract import information from a `from X import Y` statement.
    
    Parameters:
        node (Node): A `import_from_statement` node from the Tree-sitter AST.
        source (bytes): The module source bytes used to extract identifier and dotted-name text.
    
    Returns:
        results (list[ImportEntity]): A list with a single ImportEntity describing the imported module path, the tuple of imported names (or `"*"` for wildcard), whether the import is relative, and the statement's line number. Returns an empty list when the module path resolves to a Python standard-library module.
    """
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
    """
    Extract import entries from a plain `import X` statement node.
    
    Parameters:
        node (Node): A Tree-sitter `import_statement` node.
        source (bytes): The source file content used to extract module text.
    
    Returns:
        list[ImportEntity]: A list of ImportEntity objects for each imported module that is not part of the standard library. The list is empty if no non-stdlib modules are found.
    """
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


def extract_calls(root: Node, source: bytes, file_path: str) -> list[CallEntity]:
    """
    Extract all call expressions in the AST and record their enclosing scope.
    
    Returns:
        calls (list[CallEntity]): A list of CallEntity objects, each containing the enclosing scope name (`caller_name`), the callee text (`callee_name`), and the call's `line_number`.
    """
    calls: list[CallEntity] = []
    _walk_calls(root, source, calls)
    return calls


def _walk_calls(node: Node, source: bytes, calls: list[CallEntity]) -> None:
    """
    Traverse the AST recursively and append call-expression metadata to the provided list.
    
    Parameters:
        node (Node): The current AST node to inspect.
        source (bytes): The original source bytes used to extract node text.
        calls (list[CallEntity]): Mutable list that will be extended with CallEntity instances for each call expression found. Each appended entity contains the enclosing scope name as `caller_name`, the textual callee expression as `callee_name`, and a 1-based `line_number`.
    """
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
