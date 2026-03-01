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
    """Create and return a tree-sitter Parser configured for Python."""
    return Parser(PY_LANGUAGE)


def parse_file(source: bytes, file_path: str, parser: Parser) -> FileEntities:
    """Parse a single Python source file and return all extracted entities."""
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
    """Walk a directory and parse every .py file, returning one FileEntities per file."""
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
    """Check if a path matches any of the exclude patterns."""
    for pattern in patterns:
        if any(char in pattern for char in "*?[]"):
            if fnmatch.fnmatch(path_str, pattern):
                return True
        elif pattern in path_str:
            return True
    return False


def _iter_python_files(directory: str, exclude_patterns: list[str]) -> Iterator[Path]:
    """Yield all .py files under directory that don't match any exclude pattern."""
    for path in Path(directory).rglob("*.py"):
        if not _is_excluded(str(path), exclude_patterns):
            yield path
