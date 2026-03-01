"""Low-level tree-sitter node helpers."""

import sys

from tree_sitter import Node


def node_text(node: Node, source: bytes) -> str:
    """
    Get the UTF-8 text for the given tree-sitter node.
    
    Parameters:
        node (Node): The tree-sitter node whose byte range will be extracted.
        source (bytes): The full source bytes to slice from.
    
    Returns:
        str: The decoded text for the node; invalid UTF-8 sequences are replaced.
    """
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def is_stdlib_module(module_name: str) -> bool:
    """
    Determine whether a module name refers to a Python standard library module.
    
    Parameters:
        module_name (str): A module name (may be dotted, e.g. "os.path"); only the top-level segment before the first dot is checked.
    
    Returns:
        `True` if the top-level module name is present in `sys.stdlib_module_names` (Python 3.10+), `False` otherwise.
    """
    top_level = module_name.split(".")[0]
    return top_level in sys.stdlib_module_names


def get_docstring(body_node: Node, source: bytes) -> str | None:
    """
    Extract the first docstring text from a function or class body node.
    
    Parameters:
        body_node (Node | None): The body node of a function or class, or None.
        source (bytes): The full source bytes from which node text is extracted.
    
    Returns:
        str | None: The docstring content with surrounding quotes removed and whitespace stripped,
        an empty string for an explicit empty docstring (e.g., """"""""), or `None` if no docstring
        is present or `body_node` is `None`.
    """
    if body_node is None:
        return None

    for child in body_node.children:
        if child.type == "expression_statement":
            for inner in child.children:
                if inner.type == "string":
                    raw = node_text(inner, source)
                    for prefix in ('"""', "'''", '"', "'"):
                        if raw.startswith(prefix) and raw.endswith(prefix) and len(raw) > 2 * len(prefix):
                            return raw[len(prefix):-len(prefix)].strip()
                        if raw.startswith(prefix) and raw.endswith(prefix) and len(raw) == 2 * len(prefix):
                            return ""
                    return raw.strip()
        if child.type not in ("comment", "expression_statement"):
            break
    return None


def get_function_signature(func_node: Node, source: bytes) -> str:
    """
    Extract the parameter list text from a function definition node.
    
    Parameters:
        func_node (Node): A tree-sitter function_definition node to inspect.
        source (bytes): The source file contents as bytes used to extract text.
    
    Returns:
        str: The parameters text including surrounding parentheses (e.g., "(a, b=1)"); returns "()" if no parameters node is present.
    """
    for child in func_node.children:
        if child.type == "parameters":
            return node_text(child, source)
    return "()"


def get_class_bases(class_node: Node, source: bytes) -> tuple[str, ...]:
    """
    Collect the base class names from a class_definition node.
    
    Parameters:
        class_node (Node): A Tree-sitter `class_definition` node to inspect.
        source (bytes): Source file contents as bytes used to extract text for each base.
    
    Returns:
        tuple[str, ...]: A tuple of base class name strings in the order they appear.
    """
    bases: list[str] = []
    for child in class_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type not in ("(", ")", ","):
                    bases.append(node_text(arg, source))
    return tuple(bases)


def find_enclosing_scope(node: Node, source: bytes) -> str:
    """
    Determine the closest enclosing function or method scope for the given AST node.
    
    Searches parent nodes and returns "ClassName.method_name" for methods, "function_name" for functions, or "<module>" if no enclosing function is found.
    
    Parameters:
        node (Node): The tree-sitter node whose enclosing scope to locate.
        source (bytes): The source bytes used to extract identifier text.
    
    Returns:
        scope_name (str): The enclosing scope name: "ClassName.method_name", "function_name", or "<module>".
    """
    current = node.parent
    func_name: str | None = None
    class_name: str | None = None

    while current is not None:
        if current.type in ("function_definition", "decorated_definition"):
            actual = current
            if current.type == "decorated_definition":
                for ch in current.children:
                    if ch.type == "function_definition":
                        actual = ch
                        break
            if func_name is None:
                for ch in actual.children:
                    if ch.type == "identifier":
                        func_name = node_text(ch, source)
                        break
        elif current.type == "class_definition":
            if class_name is None:
                for ch in current.children:
                    if ch.type == "identifier":
                        class_name = node_text(ch, source)
                        break
        current = current.parent

    if func_name and class_name:
        return f"{class_name}.{func_name}"
    if func_name:
        return func_name
    return "<module>"
