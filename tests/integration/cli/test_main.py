from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner
from codegraph.cli.main import app

runner = CliRunner()

@pytest.fixture
def mock_db_manager():
    """Mock get_database_manager for CLI tests."""
    with patch("codegraph.cli.main._initialize_db") as mock_init:
        with patch("codegraph.cli.cli_helpers.get_database_manager") as mock_get_dm:
            mock_dm = MagicMock()
            mock_get_dm.return_value = mock_dm
            mock_init.return_value = mock_dm
            
            # Default behavior: connected
            mock_dm.is_connected.return_value = True
            mock_driver = MagicMock()
            mock_dm.get_driver.return_value = mock_driver
            mock_dm._config = MagicMock()
            mock_dm._config.uri = "bolt://localhost:7687"
            yield mock_dm

def test_cli_help():
    """Test CLI help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CodeGraph" in result.stdout
    assert "rebuild" in result.stdout
    assert "stats" in result.stdout

def test_cli_rebuild_command(mock_db_manager):
    """Test the 'rebuild' command call."""
    with patch("codegraph.cli.main.rebuild_helper") as mock_rebuild:
        result = runner.invoke(app, ["rebuild"])
        assert result.exit_code == 0
        mock_rebuild.assert_called_once()

def test_cli_stats_command(mock_db_manager):
    """Test the 'stats' command call."""
    with patch("codegraph.cli.main.stats_helper") as mock_stats:
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        mock_stats.assert_called_once()

def test_cli_doctor_command(mock_db_manager):
    """Test the 'doctor' command call."""
    with patch("codegraph.cli.main.doctor_helper") as mock_doctor:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        mock_doctor.assert_called_once()

def test_cli_custom_config(mock_db_manager):
    """Test using a custom config path."""
    custom_config = "custom_config.yaml"
    with patch("codegraph.cli.main.rebuild_helper") as mock_rebuild:
        # Mock Path.exists to return True for the custom config
        with patch("pathlib.Path.exists", return_value=True):
            result = runner.invoke(app, ["--config", custom_config, "rebuild"])
            assert result.exit_code == 0
            mock_rebuild.assert_called_once()
            called_path = mock_rebuild.call_args[0][0]
            assert str(called_path).endswith(custom_config)

@patch("codegraph.cli.cli_helpers.setup_logging")
@patch("codegraph.cli.cli_helpers.load_raw_config")
@patch("codegraph.cli.cli_helpers.resolve_project_root")
@patch("codegraph.cli.cli_helpers.clear_database")
@patch("codegraph.cli.cli_helpers.create_parser")
@patch("codegraph.cli.cli_helpers.parse_directory")
@patch("codegraph.cli.cli_helpers.build_graph")
def test_rebuild_helper_logic(
    mock_build_graph,
    mock_parse_directory,
    mock_create_parser,
    mock_clear_database,
    mock_resolve_root,
    mock_load_raw,
    mock_setup_logging,
    mock_db_manager,
):
    """Test the logic flow inside rebuild_helper."""
    from codegraph.cli.cli_helpers import rebuild_helper

    config_path = Path("config.yaml")
    mock_load_raw.return_value = {"parser": {"exclude_patterns": ["ignored/"]}}
    mock_resolve_root.return_value = Path("/project/root")
    
    mock_driver = mock_db_manager.get_driver()
    mock_db_manager.is_connected.return_value = True
    
    mock_clear_database.return_value = 0
    mock_parse_directory.return_value = []
    mock_build_graph.return_value = {
        "File": 0, "Function": 0, "Class": 0, "Method": 0,
        "CONTAINS": 0, "CALLS": 0, "IMPORTS": 0, "INHERITS_FROM": 0,
    }

    rebuild_helper(config_path)

    mock_setup_logging.assert_called_once()
    mock_db_manager.is_connected.assert_called_once()
    mock_clear_database.assert_called_with(mock_driver)
    mock_create_parser.assert_called_once()
    mock_parse_directory.assert_called_once()
    mock_build_graph.assert_called_once()

@patch("codegraph.cli.cli_helpers.setup_logging")
def test_doctor_helper_logic_success(
    mock_setup_logging,
    mock_db_manager,
):
    """Test the logic flow inside doctor_helper when all checks pass."""
    from codegraph.cli.cli_helpers import doctor_helper
    
    mock_db_manager.is_connected.return_value = True
    
    # Mock GDS version call inside doctor_helper
    with patch("codegraph.core.graph.ppr.create_gds_client") as mock_gds_client:
        mock_gds = MagicMock()
        mock_gds.version.return_value = "2.6.0"
        mock_gds_client.return_value = mock_gds
        
        doctor_helper()
    
    mock_setup_logging.assert_called_once()
    mock_db_manager.is_connected.assert_called_once()
