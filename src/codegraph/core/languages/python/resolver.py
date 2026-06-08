# src/codegraph/core/languages/python/resolver.py
import builtins
import logging
from typing import Optional

from codegraph.core.parser.models import FileEntities
from codegraph.core.graph.utils import normalize_path
from codegraph.core.graph.resolver_interface import LanguageResolver

logger = logging.getLogger(__name__)

_PYTHON_BUILTINS: frozenset[str] = frozenset(dir(builtins))

class PythonResolver(LanguageResolver):
    def get_builtins(self) -> frozenset[str]:
        return _PYTHON_BUILTINS

    def build_import_map(self, fe: FileEntities, all_file_paths: list[str]) -> dict[str, str]:
        import_map: dict[str, str] = {}
        for imp in fe.imports:
            resolved_path = self._resolve_import_to_file_path(imp.module_path, all_file_paths)
            if not resolved_path:
                continue
            if imp.imported_names:
                for name in imp.imported_names:
                    import_map[name] = resolved_path
            else:
                last_segment = imp.module_path.rsplit(".", 1)[-1]
                import_map[last_segment] = resolved_path
        return import_map

    def resolve_caller(self, caller_name: str, file_path: str) -> Optional[str]:
        norm_fp = normalize_path(file_path)
        if caller_name == "<module>":
            return norm_fp
        if "." in caller_name:
            class_name, method_name = caller_name.split(".", 1)
            return f"{norm_fp}::{class_name}.{method_name}"
        return f"{norm_fp}::{caller_name}"

    def _resolve_symbol(self, symbol_name: str, lookup: dict[str, list[str]], file_path: str, import_map: dict[str, str]) -> Optional[str]:
        candidates = lookup.get(symbol_name, [])
        if not candidates:
            return None
            
        imported_file = import_map.get(symbol_name)
        if imported_file:
            for qname in candidates:
                if qname.startswith(imported_file + "::"):
                    return qname
                    
        norm_fp = normalize_path(file_path)
        same_file = [qname for qname in candidates if qname.startswith(norm_fp + "::")]
        
        if len(same_file) == 1:
            return same_file[0]
        if len(same_file) > 1:
            return None
            
        if len(candidates) == 1:
            return candidates[0]
            
        return None

    def resolve_callee(self, callee_name: str, lookup: dict[str, list[str]], file_path: str, import_map: dict[str, str]) -> Optional[str]:
        return self._resolve_symbol(callee_name, lookup, file_path, import_map)

    def resolve_base_class(self, base_name: str, lookup: dict[str, list[str]], file_path: str, import_map: dict[str, str]) -> Optional[str]:
        return self._resolve_symbol(base_name, lookup, file_path, import_map)

    def _resolve_import_to_file_path(self, module_path: str, all_file_paths: list[str]) -> Optional[str]:
        if not module_path:
            return None
        parts = module_path.lstrip(".").split(".")
        for skip in range(1, len(parts)):
            suffix = "/".join(parts[skip:]) + ".py"
            for fp in all_file_paths:
                if fp == suffix or fp.endswith("/" + suffix):
                    return fp
        suffix = "/".join(parts) + ".py"
        for fp in all_file_paths:
            if fp == suffix or fp.endswith("/" + suffix):
                return fp
        return None
