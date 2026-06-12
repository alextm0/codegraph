"""Parser module: Tree-sitter based generic code extraction."""

from codegraph.core.parser.service import parse_directory, parse_file
from codegraph.core.parser.base import LanguageParser

__all__ = [
    "LanguageParser",
    "parse_directory",
    "parse_file",
]
