"""Parser module: Tree-sitter based generic code extraction."""

from codegraph.core.parser.service import parse_directory, parse_file, create_parser
from codegraph.core.parser.base import LanguageParser

__all__ = [
    "LanguageParser",
    "create_parser",
    "parse_directory",
    "parse_file",
]
