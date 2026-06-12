from dataclasses import dataclass
from typing import Type, Any

@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    parser_cls: Type[Any]
    resolver_cls: Type[Any]

class LanguageRegistry:
    def __init__(self):
        self._by_ext: dict[str, LanguageSpec] = {}
        self._by_name: dict[str, LanguageSpec] = {}

    def register(self, spec: LanguageSpec) -> None:
        self._by_name[spec.name] = spec
        for ext in spec.extensions:
            self._by_ext[ext] = spec

    def get_spec_by_extension(self, ext: str) -> LanguageSpec:
        if ext not in self._by_ext:
            raise KeyError(f"No language registered for extension {ext}")
        return self._by_ext[ext]

    def get_spec_by_name(self, name: str) -> LanguageSpec:
        if name not in self._by_name:
            raise KeyError(f"No language registered for name {name}")
        return self._by_name[name]

# Global singleton
_registry = LanguageRegistry()

def get_registry() -> LanguageRegistry:
    return _registry

# Removed hardcoded registration to maintain separation of concerns
