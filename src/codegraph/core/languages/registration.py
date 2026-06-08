from codegraph.core.parser.registry import LanguageSpec, get_registry
from codegraph.core.languages.python.parser import PythonParser
from codegraph.core.languages.python.resolver import PythonResolver

def register_all_languages() -> None:
    """Register all available languages with the global parser registry."""
    registry = get_registry()
    
    # Register Python
    registry.register(LanguageSpec(
        name="python",
        extensions=(".py",),
        parser_cls=PythonParser,
        resolver_cls=PythonResolver
    ))
