"""Unit tests for codegraph find CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from codegraph.cli.main import app
from codegraph.core.graph.queries import NodeInfo

runner = CliRunner()


def test_find_command_invokes_search_symbols() -> None:
    """find should call search_symbols and print matches."""
    mock_dm = MagicMock()
    mock_dm.get_driver.return_value = MagicMock()
    node = NodeInfo(
        qualified_name="src/auth.py::AuthService",
        name="AuthService",
        label="Class",
        file_path="/project/src/auth.py",
    )
    with patch("codegraph.cli.main._initialize_db", return_value=mock_dm):
        with patch(
            "codegraph.core.graph.queries.search_symbols", return_value=[node]
        ) as mock_search:
            with patch(
                "codegraph.utils.config.load_raw_config",
                return_value={"project_root": "."},
            ):
                with patch(
                    "codegraph.utils.config.resolve_project_root",
                    return_value=Path("/project"),
                ):
                    result = runner.invoke(app, ["find", "Auth"])
    assert result.exit_code == 0
    mock_search.assert_called_once()
    assert "AuthService" in result.stdout
