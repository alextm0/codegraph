"""Low-level tree-sitter node helpers."""

import sys

from tree_sitter import Node


def node_text(node: Node, source: bytes) -> str:
    """
    Retrieve the UTF-8 text covered by a Tree-sitter node from the source bytes.
    
    Parameters:
        node (Node): The Tree-sitter node whose byte range will be extracted.
        source (bytes): The full source file as bytes.
    
    Returns:
        The decoded string of source[node.start_byte:node.end_byte]; invalid UTF-8 sequences are replaced.
    """
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def is_stdlib_module(module_name: str) -> bool:
    """
    Determine whether a module name refers to a top-level Python standard library module.
    
    Checks only the first segment of a possibly dotted module name against sys.stdlib_module_names (Python 3.10+).
    
    Parameters:
        module_name (str): Module import name (may be dotted, e.g. "xml.etree").
    
    Returns:
        `true` if the top-level name is in the Python standard library, `false` otherwise.
    """
    top_level = module_name.split(".")[0]
    return top_level in sys.stdlib_module_names


def get_docstring(body_node: Node, source: bytes) -> str | None:
    """
    Extract the first docstring text from a function or class body node.
    
    Parameters:
        body_node (Node | None): The Tree-sitter node representing the body block of a function or class. If None, no docstring is present.
        source (bytes): The original source bytes from which node text is extracted.
    
    Returns:
        str | None: The docstring content with surrounding quotes removed and whitespace trimmed, `""` for an explicitly empty docstring, or `None` if no docstring is found.
    """
    if body_node is None:
        return None

    for child in body_node.children:
        if child.type == "comment":
            continue

        if child.type != "expression_statement":
            return None

        for inner in child.children:
            if inner.type == "string":
                raw = node_text(inner, source)
                for prefix in ('"""', "'''", '"', "'"):
                    if raw.startswith(prefix) and raw.endswith(prefix) and len(raw) > 2 * len(prefix):
                        return raw[len(prefix):-len(prefix)].strip()
                    if raw.startswith(prefix) and raw.endswith(prefix) and len(raw) == 2 * len(prefix):
                        return ""
                return raw.strip()
        
        return None
        
    return None


def get_function_signature(func_node: Node, source: bytes) -> str:
    """
    Retrieve the parameter list text from a function definition node.
    
    Parameters:
        func_node (Node): A Tree-sitter `function_definition` node.
        source (bytes): The original source bytes used to extract node text.
    
    Returns:
        The parameter list text for the function (for example "(self, x=1)"), or "()" if no parameters node is present.
    """
    for child in func_node.children:
        if child.type == "parameters":
            return node_text(child, source)
    return "()"


def get_class_bases(class_node: Node, source: bytes) -> tuple[str, ...]:
    """
    Get base class names from a class_definition node.
    
    Returns:
    	tuple[str, ...]: Tuple of base class name strings in the order they appear; empty tuple if the class has no bases.
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
    Finds the nearest enclosing function or method scope name for the given AST node.
    
    Parameters:
        node (Node): The Tree-sitter node from which to begin searching up the tree.
        source (bytes): The original source bytes used to extract identifier text.
    
    Returns:
        str: "ClassName.method_name" for a method defined inside a class, "function_name" for a enclosing function, or "<module>" when no enclosing function or class is found.
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
