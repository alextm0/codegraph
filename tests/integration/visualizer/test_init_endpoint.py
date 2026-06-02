from fastapi.testclient import TestClient
from codegraph.visualizer.server import create_app
from unittest.mock import MagicMock, patch

def test_api_init_endpoint():
    # Setup mock driver and config
    driver = MagicMock()
    raw_config = {}
    app = create_app(driver, raw_config, project_root=".")
    client = TestClient(app)
    
    with (
        patch("codegraph.cli.cli_helpers.rebuild_helper") as mock_build,
        patch("codegraph.utils.config.save_raw_config")
    ):
        response = client.post("/api/init", json={"target": "."})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert mock_build.called
