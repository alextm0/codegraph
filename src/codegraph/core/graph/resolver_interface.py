# src/codegraph/core/graph/resolver_interface.py
from abc import ABC, abstractmethod
from typing import Optional
from codegraph.core.parser.models import FileEntities

class LanguageResolver(ABC):
    @abstractmethod
    def build_import_map(self, fe: FileEntities, all_file_paths: list[str]) -> dict[str, str]:
        ...

    @abstractmethod
    def resolve_caller(self, caller_name: str, file_path: str) -> Optional[str]:
        ...

    @abstractmethod
    def resolve_callee(self, callee_name: str, lookup: dict[str, list[str]], file_path: str, import_map: dict[str, str]) -> Optional[str]:
        ...

    @abstractmethod
    def resolve_base_class(self, base_name: str, lookup: dict[str, list[str]], file_path: str, import_map: dict[str, str]) -> Optional[str]:
        ...

    @abstractmethod
    def get_builtins(self) -> frozenset[str]:
        ...
