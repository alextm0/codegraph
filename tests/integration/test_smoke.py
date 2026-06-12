"""End-to-end smoke test: rebuild → query → explain → health → MCP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import neo4j_required

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "flask"


@neo4j_required
def test_stabilization_smoke(tmp_path, monkeypatch):
    """Gate: full pipeline on flask fixture must complete without error."""
    if not _FIXTURE.exists():
        pytest.skip("flask fixture missing")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
project_root: "{_FIXTURE}"
ppr:
  damping_factor: 0.50
  top_k: 10
seed_selection:
  entity_match_weight: 0.6
  bm25_weight: 0.3
"""
    )

    monkeypatch.setenv("CODEGRAPH_CONFIG", str(config_path))
    from codegraph.core.graph import clear_database, build_graph, get_database_manager
    from codegraph.core.parser import parse_directory

    db = get_database_manager()
    db.initialize(str(config_path))
    driver = db.get_driver()
    entities = parse_directory(str(_FIXTURE))
    clear_database(driver)
    build_graph(driver, entities)

    from codegraph.cli.commands.query import query_helper
    from codegraph.cli.commands.explain import explain_helper
    from codegraph.mcp.tools import get_relevant_context_impl
    from codegraph.mcp.server import ServerState
    from codegraph.core.graph.ppr import PPRConfig, create_gds_client
    from codegraph.utils.config import parse_signal_weights, load_raw_config

    query_helper(config_path, "routing blueprint", None, 5, 2000, trace=True)

    explain_helper(config_path, "routing blueprint", top_k=3)
    driver = db.get_driver()

    raw = load_raw_config(config_path)
    from codegraph.visualizer.server import create_app
    from fastapi.testclient import TestClient

    app = create_app(driver, raw, project_root=str(_FIXTURE), config_path=config_path)
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    gds = create_gds_client(driver)
    state = ServerState(
        driver=driver,
        gds=gds,
        project_root=str(_FIXTURE),
        config_path=config_path,
        ppr_config=PPRConfig(top_k=5),
        signal_weights=parse_signal_weights(raw.get("seed_selection", {})),
        exclude_seed_paths=raw.get("seed_selection", {}).get("exclude_seed_paths") or [],
        default_token_budget=2000,
        default_top_k=5,
        default_include_explanations=True,
    )
    out = get_relevant_context_impl(
        "routing blueprint", None, None, 5, 2000, state, include_explanations=True
    )
    payload = json.loads(out)
    assert payload["summary"]["result_count"] >= 0
