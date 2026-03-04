import logging
from collections.abc import Callable, Iterator
from pathlib import Path

from codegraph.utils.ignore import is_ignored

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from codegraph.core.parser.extractors import (
    extract_calls,
    extract_classes,
    extract_functions,
    extract_imports,
    extract_methods,
)
from codegraph.core.parser.models import FileEntities

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
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[FileEntities]:
    """Parse all Python files under a directory and collect their FileEntities.

    Parameters:
        directory: Root directory to search for `.py` files.
        parser: Tree-sitter Parser configured for Python.
        exclude_patterns: Optional list of glob or substring patterns to skip.
        progress_callback: Optional callable(current, total, file_path) called
            after each file is parsed. Useful for progress reporting.

    Returns:
        List of FileEntities objects, one per successfully parsed Python file.
        Files that cannot be read are skipped with a warning log.
    """
    all_paths = list(_iter_python_files(directory, exclude_patterns or []))
    total = len(all_paths)
    results: list[FileEntities] = []
    for idx, path in enumerate(all_paths, start=1):
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("Cannot read %s: %s", str(path), exc)
            if progress_callback:
                progress_callback(idx, total, str(path))
            continue
        results.append(parse_file(source, str(path), parser))
        if progress_callback:
            progress_callback(idx, total, str(path))
    return results


def _iter_python_files(directory: str, exclude_patterns: list[str]) -> Iterator[Path]:
    """
    Generate Path objects for Python (.py) files under the given directory, excluding any that match the provided patterns.
    
    Parameters:
        directory (str): Root directory to search for Python files.
        exclude_patterns (list[str]): Patterns used to skip files; patterns may be wildcards or substrings.
    
    Returns:
        Iterator[Path]: An iterator of Path objects for .py files under `directory` that do not match any exclude pattern.
    """
    root = Path(directory)
    for path in root.rglob("*.py"):
        try:
            # Use relative path for easier matching against ignore patterns
            rel_path = path.relative_to(root)
            if not is_ignored(str(rel_path), exclude_patterns):
                yield path
        except ValueError:
            # Fallback to absolute path string if relative_to fails
            if not is_ignored(str(path), exclude_patterns):
                yield path
