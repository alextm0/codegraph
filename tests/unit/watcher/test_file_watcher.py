from unittest.mock import MagicMock, patch, call
import pytest

from codegraph.watcher.file_watcher import CodeGraphHandler, CodeGraphWatcher


def _make_event(src_path: str, is_directory: bool = False):
    event = MagicMock()
    event.src_path = src_path
    event.is_directory = is_directory
    return event


class TestCodeGraphHandler:
    def test_py_file_added_on_modified(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_modified(_make_event("/project/auth.py"))
        assert "/project/auth.py" in handler.changed_files

    def test_py_file_added_on_created(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_created(_make_event("/project/models.py"))
        assert "/project/models.py" in handler.changed_files

    def test_py_file_added_on_deleted(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_deleted(_make_event("/project/old.py"))
        assert "/project/old.py" in handler.changed_files

    def test_non_py_file_ignored(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_modified(_make_event("/project/README.md"))
        assert len(handler.changed_files) == 0

    def test_directory_event_ignored_on_modified(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_modified(_make_event("/project/src", is_directory=True))
        assert len(handler.changed_files) == 0

    def test_directory_event_ignored_on_created(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_created(_make_event("/project/src", is_directory=True))
        assert len(handler.changed_files) == 0

    def test_excluded_path_ignored(self):
        handler = CodeGraphHandler(callback=MagicMock(), exclude_patterns=["__pycache__"])
        handler.on_modified(_make_event("/project/__pycache__/auth.cpython-312.pyc"))
        assert len(handler.changed_files) == 0

    def test_excluded_pattern_substring_match(self):
        handler = CodeGraphHandler(callback=MagicMock(), exclude_patterns=[".venv"])
        handler.on_modified(_make_event("/project/.venv/lib/site.py"))
        assert len(handler.changed_files) == 0

    def test_non_excluded_py_file_passes_through(self):
        handler = CodeGraphHandler(callback=MagicMock(), exclude_patterns=["__pycache__"])
        handler.on_modified(_make_event("/project/src/auth.py"))
        assert "/project/src/auth.py" in handler.changed_files

    def test_multiple_files_accumulated(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_modified(_make_event("/project/a.py"))
        handler.on_modified(_make_event("/project/b.py"))
        assert {"/project/a.py", "/project/b.py"} == handler.changed_files

    def test_same_file_added_only_once(self):
        handler = CodeGraphHandler(callback=MagicMock())
        handler.on_modified(_make_event("/project/auth.py"))
        handler.on_modified(_make_event("/project/auth.py"))
        assert len(handler.changed_files) == 1


class TestCodeGraphWatcher:
    def _make_watcher(self, callback=None, exclude_patterns=None):
        with patch("codegraph.watcher.file_watcher.Observer"):
            watcher = CodeGraphWatcher(
                project_root="/project",
                callback=callback or MagicMock(),
                exclude_patterns=exclude_patterns or [],
            )
        return watcher

    def test_check_for_changes_no_op_when_empty(self):
        callback = MagicMock()
        watcher = self._make_watcher(callback=callback)
        watcher.check_for_changes()
        callback.assert_not_called()

    def test_check_for_changes_no_op_within_debounce_window(self):
        callback = MagicMock()
        watcher = self._make_watcher(callback=callback)
        # Add a file and set last_event_time to now (debounce not elapsed)
        watcher.handler.changed_files.add("/project/auth.py")
        with patch("codegraph.watcher.file_watcher.time") as mock_time:
            # current time == last event time → within 1 second window
            mock_time.time.return_value = 100.0
            watcher.handler._last_event_time = 100.0
            watcher.check_for_changes()
        callback.assert_not_called()

    def test_check_for_changes_triggers_callback_after_debounce(self):
        callback = MagicMock()
        watcher = self._make_watcher(callback=callback)
        watcher.handler.changed_files.add("/project/auth.py")
        with patch("codegraph.watcher.file_watcher.time") as mock_time:
            # last event 2 seconds ago → debounce elapsed
            mock_time.time.return_value = 102.0
            watcher.handler._last_event_time = 100.0
            watcher.check_for_changes()
        callback.assert_called_once()
        paths = callback.call_args[0][0]
        assert "/project/auth.py" in paths

    def test_changed_files_cleared_after_callback(self):
        callback = MagicMock()
        watcher = self._make_watcher(callback=callback)
        watcher.handler.changed_files.add("/project/auth.py")
        with patch("codegraph.watcher.file_watcher.time") as mock_time:
            mock_time.time.return_value = 102.0
            watcher.handler._last_event_time = 100.0
            watcher.check_for_changes()
        assert len(watcher.handler.changed_files) == 0

    def test_start_calls_observer_schedule_and_start(self):
        callback = MagicMock()
        with patch("codegraph.watcher.file_watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher = CodeGraphWatcher("/project", callback)
            watcher.start()
            mock_obs.schedule.assert_called_once()
            mock_obs.start.assert_called_once()

    def test_stop_calls_observer_stop_and_join(self):
        callback = MagicMock()
        with patch("codegraph.watcher.file_watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher = CodeGraphWatcher("/project", callback)
            watcher.stop()
            mock_obs.stop.assert_called_once()
            mock_obs.join.assert_called_once()
