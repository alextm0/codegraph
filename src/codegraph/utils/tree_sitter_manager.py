"""Centralized tree-sitter language grammar loading and caching.

Design notes:
- Role: This manager handles the low-level loading of tree-sitter shared libraries (grammars).
- Contrast: While `core.parser.registry.LanguageRegistry` routes file extensions to high-level
  Parser/Resolver classes, this manager is used by those Parsers to obtain the underlying
  tree-sitter Language object for syntax tree construction.
- Grammars are loaded once per language and cached; repeated calls to get_language()
  are cheap after the first load.
- No thread locks: parsing is single-threaded per the project's design.
- LANGUAGE_ALIASES maps common shorthand names to canonical names ("py" → "python").
- SUPPORTED_EXTENSIONS maps file extensions to canonical language names.
  Update both dicts when adding a new language grammar loader.
"""

import tree_sitter_python as tspython
from tree_sitter import Language


# Maps shorthand and alternate names to canonical language names.
# To add a new language alias: add an entry here ("js" → "javascript").
LANGUAGE_ALIASES: dict[str, str] = {
    "py": "python",
}

# Maps file extensions to canonical language names.
# To add a new language: add its extension(s) here and register a loader in TreeSitterManager.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
}


class TreeSitterManager:
    """Loads and caches tree-sitter Language objects.

    Use get_tree_sitter_manager() to obtain the shared instance rather than
    constructing this class directly.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Language] = {}

    def get_language(self, lang: str) -> Language:
        """Return the Language object for the given canonical language name.

        Loads from the installed tree-sitter grammar package on first call,
        then serves from cache on subsequent calls.

        Raises:
            ValueError: If the language is not supported.
        """
        canonical = LANGUAGE_ALIASES.get(lang, lang)
        if canonical in self._cache:
            return self._cache[canonical]

        language = self._load(canonical)
        self._cache[canonical] = language
        return language

    def _load(self, lang: str) -> Language:
        # To add a new language: add an elif branch here that imports the
        # corresponding tree-sitter-* package and returns Language(...).
        if lang == "python":
            return Language(tspython.language())
        raise ValueError(
            f"Unsupported language: {lang!r}. Supported: {list(self._cache) or ['python']}"
        )


_manager: TreeSitterManager | None = None


def get_tree_sitter_manager() -> TreeSitterManager:
    """Return the shared TreeSitterManager instance, creating it on first call."""
    global _manager
    if _manager is None:
        _manager = TreeSitterManager()
    return _manager
