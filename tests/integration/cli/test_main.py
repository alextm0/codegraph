from pathlib import Path
from unittest.mock import MagicMock, patch
import sys
import pytest
from codegraph.cli.main import cli

@pytest.fixture(autouse=True)
def mock_db_manager_singleton():
    """Mock get_database_manager to return a mock DM for all CLI tests."""
    with patch("codegraph.cli.main.get_database_manager") as mock_get_dm:
        mock_dm = MagicMock()
        mock_get_dm.return_value = mock_dm
        # Default behavior: connected
        mock_dm.is_connected.return_value = True
        mock_driver = MagicMock()
        mock_dm.get_driver.return_value = mock_driver
        mock_dm._config = MagicMock()
        mock_dm._config.uri = "bolt://localhost:7687"
        yield mock_dm

def test_cli_no_args():
    """Test CLI without any arguments should print help."""
    with patch("sys.argv", ["codegraph"]):
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            cli()
            mock_help.assert_called_once()

def test_cli_rebuild_command():
    """Test the 'rebuild' command call."""
    with patch("sys.argv", ["codegraph", "rebuild"]):
        with patch("codegraph.cli.main.cmd_rebuild") as mock_rebuild:
            # Mock Path.exists to return True so we don't worry about actual config.yaml
            with patch("pathlib.Path.exists", return_value=True):
                cli()
                mock_rebuild.assert_called_once()

def test_cli_serve_command():
    """Test the 'serve' command call."""
    with patch("sys.argv", ["codegraph", "serve"]):
        with patch("codegraph.cli.main.cmd_serve") as mock_serve:
            with patch("pathlib.Path.exists", return_value=True):
                cli()
                mock_serve.assert_called_once()

def test_cli_custom_config():
    """Test using a custom config path."""
    custom_config = "custom_config.yaml"
    with patch("sys.argv", ["codegraph", "--config", custom_config, "rebuild"]):
        with patch("codegraph.cli.main.cmd_rebuild") as mock_rebuild:
            with patch("pathlib.Path.exists", return_value=True):
                cli()
                mock_rebuild.assert_called_once()
                # Check that the first argument to cmd_rebuild is the custom config path
                called_path = mock_rebuild.call_args[0][0]
                assert str(called_path).endswith(custom_config)

@patch("codegraph.cli.main.setup_logging")
@patch("codegraph.cli.main.load_raw_config")
@patch("codegraph.cli.main.resolve_project_root")
@patch("codegraph.cli.main.clear_database")
@patch("codegraph.cli.main.create_parser")
@patch("codegraph.cli.main.parse_directory")
@patch("codegraph.cli.main.build_graph")
def test_cmd_rebuild_logic(
    mock_build_graph,
    mock_parse_directory,
    mock_create_parser,
    mock_clear_database,
    mock_resolve_root,
    mock_load_raw,
    mock_setup_logging,
    mock_db_manager_singleton,
):
    """Test the logic flow inside cmd_rebuild."""
    from codegraph.cli.main import cmd_rebuild

    config_path = Path("config.yaml")
    mock_load_raw.return_value = {"parser": {"exclude_patterns": ["ignored/"]}}
    mock_resolve_root.return_value = Path("/project/root")
    
    mock_driver = mock_db_manager_singleton.get_driver()
    mock_db_manager_singleton.is_connected.return_value = True
    
    mock_clear_database.return_value = 0
    mock_parse_directory.return_value = []
    mock_build_graph.return_value = {
        "File": 0, "Function": 0, "Class": 0, "Method": 0,
        "CONTAINS": 0, "CALLS": 0, "IMPORTS": 0, "INHERITS_FROM": 0,
    }

    cmd_rebuild(config_path)

    mock_setup_logging.assert_called_once()
    mock_db_manager_singleton.is_connected.assert_called_once()
    mock_clear_database.assert_called_with(mock_driver)
    mock_create_parser.assert_called_once()
    mock_parse_directory.assert_called_once()
    mock_build_graph.assert_called_once()

@patch("codegraph.cli.main.setup_logging")
def test_cmd_doctor_logic_success(
    mock_setup_logging,
    mock_db_manager_singleton,
):
    """Test the logic flow inside cmd_doctor when all checks pass."""
    from codegraph.cli.main import cmd_doctor
    
    mock_driver = mock_db_manager_singleton.get_driver()
    mock_db_manager_singleton.is_connected.return_value = True
    
    # Mock GDS version call inside cmd_doctor
    with patch("codegraph.core.graph.ppr.create_gds_client") as mock_gds_client:
        mock_gds = MagicMock()
        mock_gds.version.return_value = "2.6.0"
        mock_gds_client.return_value = mock_gds
        
        cmd_doctor()
    
    mock_setup_logging.assert_called_once()
    mock_db_manager_singleton.is_connected.assert_called_once()
