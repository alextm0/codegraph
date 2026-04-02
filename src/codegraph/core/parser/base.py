"""Abstract base class for language-specific parsers.

Design notes:
- LanguageParser defines the contract every language parser must satisfy.
  Implement it when adding a new language (e.g. JavaScriptParser, JavaParser).
- The ABC enforces two methods: parse_file() for single-file extraction and
  supported_extensions() for file routing in parse_directory().
- The existing module-level parse_file() / parse_directory() functions in
  python_parser.py remain the public API; LanguageParser is the extension point.
"""

from abc import ABC, abstractmethod

from codegraph.core.parser.models import FileEntities


class LanguageParser(ABC):
    """Contract for language-specific parsers.

    Each implementation handles one language family. parse_directory() dispatches
    to the correct implementation based on file extension via supported_extensions().
    """

    @abstractmethod
    def parse_file(self, source: bytes, file_path: str) -> FileEntities:
        """Parse source bytes and return all extracted entities for the file."""
        ...

    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """Return the file extensions this parser handles, e.g. ('.py',)."""
        ...
