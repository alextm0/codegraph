from typer.testing import CliRunner
from codegraph.cli.main import app
from unittest.mock import patch

runner = CliRunner()

@patch("codegraph.cli.cli_helpers.Prompt.ask")
@patch("codegraph.cli.cli_helpers.Confirm.ask")
@patch("codegraph.core.graph.database.DatabaseManager")
@patch("codegraph.cli.cli_helpers.rebuild_helper")
@patch("codegraph.cli.cli_helpers.save_raw_config")
def test_init_prompts_when_no_args(mock_save, mock_rebuild, mock_db, mock_confirm, mock_ask):
    # Setup mocks
    mock_ask.side_effect = [".", "neo4j://test", "neo4j", "pass", "."]
    mock_confirm.return_value = True
    
    # Run the init command with no arguments
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"], catch_exceptions=False)
        
        # Assert
        assert mock_ask.called
        assert result.exit_code == 0
        mock_save.assert_called_once()
        mock_rebuild.assert_called_once()
