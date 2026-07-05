"""Unit tests for codegraph.mcp.server_config."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from codegraph.core.graph.database import DatabaseManager
from codegraph.core.graph.ppr import PPRConfig
from codegraph.mcp.server_config import (
    McpRuntimeSettings,
    ServerStateFactory,
    load_mcp_runtime_settings,
    resolve_config_path,
)


@pytest.fixture(autouse=True)
def reset_database_manager() -> None:
    DatabaseManager._instance = None
    yield
    DatabaseManager._instance = None


def test_resolve_config_path_cli_arg(tmp_path: Path) -> None:
    cfg = tmp_path / "custom.yaml"
    cfg.write_text("project_root: .\n", encoding="utf-8")
    assert resolve_config_path(str(cfg)) == cfg.resolve()


def test_resolve_config_path_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "from_env.yaml"
    cfg.write_text("project_root: .\n", encoding="utf-8")
    monkeypatch.setenv("CODEGRAPH_CONFIG", str(cfg))
    assert resolve_config_path() == cfg.resolve()


def test_resolve_config_path_default() -> None:
    path = resolve_config_path()
    assert path.name == "config.yaml"
    assert "codegraph" in str(path)


def test_load_mcp_runtime_settings_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({"project_root": "src"}), encoding="utf-8")

    settings = load_mcp_runtime_settings(config_path)

    assert isinstance(settings, McpRuntimeSettings)
    assert settings.config_path == config_path
    assert settings.project_root == str((tmp_path / "src").resolve())
    assert settings.ppr_config.damping_factor == 0.70
    assert settings.ppr_config.top_k == 30
    assert settings.default_token_budget == 6000
    assert settings.default_top_k == 30
    assert settings.exclude_seed_paths == []
    assert settings.default_include_explanations is True


def test_load_mcp_runtime_settings_custom_ppr_and_mcp(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump({
            "project_root": ".",
            "ppr": {
                "damping_factor": 0.55,
                "top_k": 50,
                "max_iterations": 30,
                "tolerance": 1e-6,
            },
            "mcp": {"default_token_budget": 8000, "default_top_k": 20},
            "seed_selection": {
                "entity_match_weight": 2.0,
                "bm25_weight": 1.5,
                "exclude_seed_paths": ["tests/", "test_"],
            },
        }),
        encoding="utf-8",
    )

    settings = load_mcp_runtime_settings(config_path)

    assert settings.ppr_config.damping_factor == 0.55
    assert settings.ppr_config.top_k == 50
    assert settings.default_token_budget == 8000
    assert settings.default_top_k == 20
    assert settings.exclude_seed_paths == ["tests/", "test_"]
    assert settings.signal_weights["entity_match"] == 2.0
    assert settings.signal_weights["bm25"] == 1.5


@patch("codegraph.mcp.server_config.ensure_graph_ready")
@patch("codegraph.mcp.server_config.create_gds_client")
@patch("codegraph.mcp.server_config.get_database_manager")
@patch("codegraph.mcp.server_config.load_mcp_runtime_settings")
def test_server_state_factory_create(
    mock_settings: MagicMock,
    mock_db_mgr: MagicMock,
    mock_gds_client: MagicMock,
    mock_ensure: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project_root: .\n", encoding="utf-8")

    mock_settings.return_value = McpRuntimeSettings(
        config_path=config_path,
        project_root=str(tmp_path),
        ppr_config=PPRConfig(),
        signal_weights={"bm25": 1.0},
        exclude_seed_paths=[],
        default_token_budget=6000,
        default_top_k=30,
        default_include_explanations=True,
    )

    db = MagicMock()
    db.is_connected.return_value = True
    mock_driver = MagicMock()
    db.get_driver.return_value = mock_driver
    mock_db_mgr.return_value = db

    mock_gds = MagicMock()
    mock_gds_client.return_value = mock_gds

    factory = ServerStateFactory(config_path)
    state = factory.create()

    db.initialize.assert_called_once_with(str(config_path))
    mock_gds_client.assert_called_once_with(mock_driver)
    mock_ensure.assert_called_once_with(mock_driver, mock_gds)
    assert state.driver is mock_driver
    assert state.gds is mock_gds
    assert state.project_root == str(tmp_path)
    assert state.default_token_budget == 6000
    assert state.exclude_seed_paths == []


@patch("codegraph.mcp.server_config.get_database_manager")
@patch("codegraph.mcp.server_config.load_mcp_runtime_settings")
def test_server_state_factory_raises_when_neo4j_unreachable(
    mock_settings: MagicMock,
    mock_db_mgr: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project_root: .\n", encoding="utf-8")
    mock_settings.return_value = McpRuntimeSettings(
        config_path=config_path,
        project_root=str(tmp_path),
        ppr_config=PPRConfig(),
        signal_weights={},
        exclude_seed_paths=[],
        default_token_budget=6000,
        default_top_k=30,
        default_include_explanations=True,
    )

    db = MagicMock()
    db.is_connected.return_value = False
    mock_db_mgr.return_value = db

    factory = ServerStateFactory(config_path)
    with pytest.raises(RuntimeError):
        factory.create()


@patch("codegraph.mcp.server_config.ensure_graph_ready", side_effect=RuntimeError("warmup"))
@patch("codegraph.mcp.server_config.create_gds_client")
@patch("codegraph.mcp.server_config.get_database_manager")
@patch("codegraph.mcp.server_config.load_mcp_runtime_settings")
def test_server_state_factory_continues_on_warmup_failure(
    mock_settings: MagicMock,
    mock_db_mgr: MagicMock,
    mock_gds_client: MagicMock,
    _mock_ensure: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project_root: .\n", encoding="utf-8")
    mock_settings.return_value = McpRuntimeSettings(
        config_path=config_path,
        project_root=str(tmp_path),
        ppr_config=PPRConfig(),
        signal_weights={},
        exclude_seed_paths=[],
        default_token_budget=6000,
        default_top_k=30,
        default_include_explanations=True,
    )

    db = MagicMock()
    db.is_connected.return_value = True
    db.get_driver.return_value = MagicMock()
    mock_db_mgr.return_value = db
    mock_gds_client.return_value = MagicMock()

    state = ServerStateFactory(config_path).create()
    assert state.config_path == config_path


@patch("codegraph.mcp.server_config.get_database_manager")
def test_server_state_factory_shutdown(mock_db_mgr: MagicMock) -> None:
    db = MagicMock()
    mock_db_mgr.return_value = db
    ServerStateFactory.shutdown()
    db.close_driver.assert_called_once()


def test_server_state_indexing_lock_is_per_instance() -> None:
    from codegraph.mcp.server_config import ServerState

    a = ServerState(
        driver=MagicMock(),
        gds=MagicMock(),
        project_root="/p",
        config_path=Path("/c.yaml"),
        ppr_config=PPRConfig(),
        signal_weights={},
        exclude_seed_paths=[],
        default_token_budget=6000,
        default_top_k=30,
        default_include_explanations=True,
    )
    b = ServerState(
        driver=MagicMock(),
        gds=MagicMock(),
        project_root="/p",
        config_path=Path("/c.yaml"),
        ppr_config=PPRConfig(),
        signal_weights={},
        exclude_seed_paths=[],
        default_token_budget=6000,
        default_top_k=30,
        default_include_explanations=True,
    )
    assert a.indexing_lock is not b.indexing_lock
