"""Python source parser using tree-sitter.

Design notes:
- Single-language module: only Python (.py) files. Multi-language support
  will be added via the LanguageParser ABC (see base.py) when needed.
"""

import logging
from codegraph.utils.tree_sitter_manager import get_tree_sitter_manager

from codegraph.core.languages.python.extractors import (
    extract_calls,
    extract_classes,
    extract_functions,
    extract_imports,
    extract_methods,
)
from codegraph.core.parser.models import FileEntities
from codegraph.core.parser.base import LanguageParser
from tree_sitter import Parser as TSParser

logger = logging.getLogger(__name__)

PY_LANGUAGE = get_tree_sitter_manager().get_language("python")

class PythonParser(LanguageParser):
    def __init__(self):
        self._ts_parser = TSParser(PY_LANGUAGE)

    def parse_file(self, source: bytes, file_path: str) -> FileEntities:
        entities = FileEntities(file_path=file_path)
        try:
            tree = self._ts_parser.parse(source)
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

    def supported_extensions(self) -> tuple[str, ...]:
        return (".py",)
