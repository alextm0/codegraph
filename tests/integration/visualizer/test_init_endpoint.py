import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from codegraph.visualizer.server import create_app


def test_api_init_endpoint_starts_background_rebuild():
    driver = MagicMock()
    raw_config = {}
    config_path = MagicMock()
    config_path.exists.return_value = False
    app = create_app(driver, raw_config, project_root=".", config_path=config_path)
    client = TestClient(app)

    with (
        patch("codegraph.cli.cli_helpers.rebuild_helper") as mock_build,
        patch("codegraph.utils.config.save_raw_config"),
    ):
        response = client.post("/api/init", json={"target": "."})
        assert response.status_code == 200
        assert response.json()["status"] == "started"
        time.sleep(0.05)
        assert mock_build.called
