"""Low-level tree-sitter node helpers."""

import sys

from tree_sitter import Node


def node_text(node: Node, source: bytes) -> str:
    """Return the UTF-8 text of a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def is_stdlib_module(module_name: str) -> bool:
    """Return True if module_name is a Python stdlib module (Python 3.10+)."""
    top_level = module_name.split(".")[0]
    return top_level in sys.stdlib_module_names


def get_docstring(body_node: Node, source: bytes) -> str | None:
    """Return the docstring text from a function/class body node, or None."""
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
    """Return the parameter list text for a function definition node."""
    for child in func_node.children:
        if child.type == "parameters":
            return node_text(child, source)
    return "()"


def get_class_bases(class_node: Node, source: bytes) -> tuple[str, ...]:
    """Return base class names from a class_definition node."""
    bases: list[str] = []
    for child in class_node.children:
        if child.type == "argument_list":
            for arg in child.children:
                if arg.type not in ("(", ")", ","):
                    bases.append(node_text(arg, source))
    return tuple(bases)


def find_enclosing_scope(node: Node, source: bytes) -> str:
    """Walk up the AST to find the enclosing function/method scope name.

    Returns 'ClassName.method_name' for methods or 'function_name' for
    top-level functions. Returns '<module>' if at module scope.
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
