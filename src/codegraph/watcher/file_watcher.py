import time
import logging
from typing import Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class CodeGraphHandler(FileSystemEventHandler):
    """Handles file system events for CodeGraph."""

    def __init__(
        self, callback: Callable[[Set[str]], None], exclude_patterns: list[str] = None
    ):
        super().__init__()
        self.callback = callback
        self.exclude_patterns = exclude_patterns or []
        self.changed_files: Set[str] = set()
        self._last_event_time = 0

    def on_modified(self, event):
        if not event.is_directory:
            self._add_change(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._add_change(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._add_change(event.src_path)

    def _add_change(self, path: str):
        if not path.endswith(".py"):
            return

        # Simple exclusion check
        if any(ex in path for ex in self.exclude_patterns):
            return

        self.changed_files.add(path)
        self._last_event_time = time.time()


class CodeGraphWatcher:
    """Watches a directory for changes and triggers a callback."""

    def __init__(
        self,
        project_root: str,
        callback: Callable[[Set[str]], None],
        exclude_patterns: list[str] = None,
    ):
        self.project_root = project_root
        self.callback = callback
        self.exclude_patterns = exclude_patterns or []
        self.handler = CodeGraphHandler(callback, exclude_patterns)
        self.observer = Observer()

    def start(self):
        logger.info("Starting file watcher for: %s", self.project_root)
        self.observer.schedule(self.handler, self.project_root, recursive=True)
        self.observer.start()

    def stop(self):
        logger.info("Stopping file watcher.")
        self.observer.stop()
        self.observer.join()

    def check_for_changes(self):
        """Debounced check for changes. Should be called periodically."""
        if self.handler.changed_files and (
            time.time() - self.handler._last_event_time > 1.0
        ):
            changes = self.handler.changed_files.copy()
            self.handler.changed_files.clear()
            self.callback(changes)
