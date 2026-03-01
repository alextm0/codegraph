"""Tree-sitter based Python source file parser"""

import fnmatch
import logging
from collections.abc import Iterator
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from src.parser.extractors import (
    extract_calls,
    extract_classes,
    extract_functions,
    extract_imports,
    extract_methods,
)
from src.parser.models import FileEntities

logger = logging.getLogger(__name__)

PY_LANGUAGE = Language(tspython.language())


def create_parser() -> Parser:
    """
    Create a Parser configured to parse Python source using the module's Python language binding.
    
    Returns:
        parser (Parser): A tree-sitter Parser instance configured with the Python Language.
    """
    return Parser(PY_LANGUAGE)


def parse_file(source: bytes, file_path: str, parser: Parser) -> FileEntities:
    """
    Extract code entities from a Python source byte string and return them as a FileEntities.
    
    If the parser fails (e.g., raises TypeError or ValueError), an empty FileEntities for the given file_path is returned.
    
    Returns:
        FileEntities: A FileEntities instance populated with functions, classes, methods, imports, and calls found in the source.
    """
    entities = FileEntities(file_path=file_path)
    try:
        tree = parser.parse(source)
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return entities

    root = tree.root_node
    entities.functions = extract_functions(root, source, file_path)
    entities.classes = extract_classes(root, source, file_path)
    entities.methods = extract_methods(root, source, file_path)
    entities.imports = extract_imports(root, source, file_path)
    entities.calls = extract_calls(root, source, file_path)
    return entities


def parse_directory(
    directory: str,
    parser: Parser,
    exclude_patterns: list[str] | None = None,
) -> list[FileEntities]:
    """
    Parse all Python files under a directory and collect their FileEntities.
    
    Parameters:
        directory (str): Root directory to search for `.py` files.
        parser (Parser): Tree-sitter Parser configured for Python.
        exclude_patterns (list[str] | None): Optional list of glob or substring patterns; any path matching a pattern will be skipped.
    
    Returns:
        list[FileEntities]: List of FileEntities objects, one for each successfully parsed Python file found under `directory`. Files that cannot be read are skipped.
    """
    results: list[FileEntities] = []
    for path in _iter_python_files(directory, exclude_patterns or []):
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("Cannot read %s: %s", str(path), exc)
            continue
        results.append(parse_file(source, str(path), parser))
    return results


def _is_excluded(path_str: str, patterns: list[str]) -> bool:
    """
    Determine whether a filepath matches any of the provided exclude patterns.
    
    Patterns containing wildcard characters (*, ?, [, ]) are treated as shell-style glob patterns; other patterns are matched by simple substring containment.
    
    Parameters:
        path_str (str): Filesystem path to test.
        patterns (list[str]): Exclude patterns to check against.
    
    Returns:
        bool: `True` if `path_str` matches any pattern, `False` otherwise.
    """
    for pattern in patterns:
        if any(char in pattern for char in "*?[]"):
            if fnmatch.fnmatch(path_str, pattern):
                return True
        elif pattern in path_str:
            return True
    return False


def _iter_python_files(directory: str, exclude_patterns: list[str]) -> Iterator[Path]:
    """
    Generate Path objects for Python (.py) files under the given directory, excluding any that match the provided patterns.
    
    Parameters:
        directory (str): Root directory to search for Python files.
        exclude_patterns (list[str]): Patterns used to skip files; patterns may be wildcards or substrings.
    
    Returns:
        Iterator[Path]: An iterator of Path objects for .py files under `directory` that do not match any exclude pattern.
    """
    for path in Path(directory).rglob("*.py"):
        if not _is_excluded(str(path), exclude_patterns):
            yield path
