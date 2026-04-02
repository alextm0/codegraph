"""PythonParser: LanguageParser implementation for Python source files."""

import logging

from tree_sitter import Parser

from codegraph.core.parser.base import LanguageParser
from codegraph.core.parser.extractors import (
    extract_calls,
    extract_classes,
    extract_functions,
    extract_imports,
    extract_methods,
)
from codegraph.core.parser.models import FileEntities
from codegraph.utils.tree_sitter_manager import get_tree_sitter_manager

logger = logging.getLogger(__name__)


class PythonParser(LanguageParser):
    """Parses Python (.py) source files using tree-sitter."""

    def __init__(self) -> None:
        language = get_tree_sitter_manager().get_language("python")
        self._parser = Parser(language)

    def supported_extensions(self) -> tuple[str, ...]:
        """Return the file extensions handled by this parser."""
        return (".py",)

    def parse_file(self, source: bytes, file_path: str) -> FileEntities:
        """Extract all code entities from Python source bytes."""
        entities = FileEntities(file_path=file_path)
        try:
            tree = self._parser.parse(source)
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
