"""Tree-sitter based Python source file parser"""

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
    """Create and return a tree-sitter Parser configured for Python."""
    return Parser(PY_LANGUAGE)


def parse_file(source: bytes, file_path: str, parser: Parser) -> FileEntities:
    """
    Parse a single Python source file and return the extracted entities.
    
    Returns:
        FileEntities: A FileEntities for the provided file_path populated with extracted functions, classes, methods, imports, and call sites. If parsing fails, returns an empty FileEntities for the given file_path.
    """
    entities = FileEntities(file_path=file_path)
    try:
        tree = parser.parse(source)
    except Exception as exc:
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
    Parse all Python files under a directory and produce a FileEntities for each successfully read file.
    
    Parameters:
        directory (str): Root directory to search for `.py` files.
        parser (Parser): Configured Tree-sitter parser for Python.
        exclude_patterns (list[str] | None): Substrings; any file path containing any of these will be skipped.
    
    Returns:
        list[FileEntities]: A list of FileEntities objects, one per successfully read and parsed Python file.
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


def _iter_python_files(directory: str, exclude_patterns: list[str]) -> Iterator[Path]:
    """
    Yield Path objects for every `.py` file under `directory` whose path does not contain any of the provided exclude patterns.
    
    Parameters:
        directory (str): Root directory to search for Python files.
        exclude_patterns (list[str]): Substrings to match against each file path; files containing any of these substrings are skipped.
    
    Returns:
        Iterator[Path]: An iterator that yields Path objects for matching Python files.
    """
    for path in Path(directory).rglob("*.py"):
        if not any(pattern in str(path) for pattern in exclude_patterns):
            yield path
