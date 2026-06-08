import logging
from pathlib import Path
from collections.abc import Callable, Iterator
from codegraph.utils.ignore import is_ignored
from codegraph.core.parser.models import FileEntities
from codegraph.core.parser.registry import get_registry
from codegraph.core.languages.registration import register_all_languages

logger = logging.getLogger(__name__)

# Register supported languages when the service module is loaded
register_all_languages()

def parse_directory(
    directory: str,
    exclude_patterns: list[str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[FileEntities]:
    root = Path(directory)
    registry = get_registry()
    parsers = {}
    all_paths = []
    
    for path in root.rglob("*"):
        if not path.is_file(): continue
        try:
            rel_path = path.relative_to(root)
            if not is_ignored(str(rel_path), exclude_patterns or []):
                all_paths.append(path)
        except ValueError:
            if not is_ignored(str(path), exclude_patterns or []):
                all_paths.append(path)

    total = len(all_paths)
    results = []
    
    for idx, path in enumerate(all_paths, start=1):
        rel_path = path.relative_to(root).as_posix()
        ext = path.suffix
        
        try:
            spec = registry.get_spec_by_extension(ext)
        except KeyError:
            if progress_callback: progress_callback(idx, total, rel_path)
            continue
            
        if ext not in parsers:
            parsers[ext] = spec.parser_cls()
            
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("Cannot read %s: %s", rel_path, exc)
            if progress_callback: progress_callback(idx, total, rel_path)
            continue
            
        results.append(parsers[ext].parse_file(source, rel_path))
        if progress_callback: progress_callback(idx, total, rel_path)
        
    return results
