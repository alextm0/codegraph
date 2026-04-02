from typing import Any
from tree_sitter import Node
from codegraph.core.parser.python_parser import create_parser

def calculate_complexity(node: Node) -> int:
    """Calculate cyclomatic complexity for a given AST node.
    
    Counts branching nodes: if, elif, for, while, except, with, and/or.
    Base complexity is 1.
    """
    count = 0
    
    # Nodes that increase cyclomatic complexity in Python
    branch_types = {
        'if_statement',
        'elif_clause',
        'for_statement',
        'while_statement',
        'except_clause',
        'with_statement',
        'conditional_expression', # ternary: x if y else z
    }
    
    # Operators that increase complexity
    operators = {'and', 'or'}

    def traverse(n: Node):
        nonlocal count
        if n.type in branch_types:
            count += 1
        elif n.type == 'boolean_operator':
            # Check children for 'and' or 'or'
            for i in range(n.child_count):
                child = n.child(i)
                if child and child.type in operators:
                    count += 1
        
        for i in range(n.child_count):
            child = n.child(i)
            if child:
                traverse(child)

    traverse(node)
    return count + 1

def analyze_file_complexity(file_path: str) -> list[dict[str, Any]]:
    """Analyze cyclomatic complexity of all functions/methods in a file."""
    parser = create_parser()
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    
    tree = parser.parse(bytes(code, "utf8"))
    results = []

    def find_functions(node: Node):
        if node.type in ('function_definition', 'method_definition'):
            # Get function name
            name_node = node.child_by_field_name('name')
            name = name_node.text.decode('utf8') if name_node else "anonymous"
            
            complexity = calculate_complexity(node)
            
            results.append({
                "name": name,
                "type": "Function" if node.type == 'function_definition' else "Method",
                "complexity": complexity,
                "line": node.start_point[0] + 1
            })
            
        for i in range(node.child_count):
            child = node.child(i)
            if child:
                find_functions(child)

    find_functions(tree.root_node)
    return results
