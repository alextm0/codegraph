import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

def load_raw_config(config_path: str | Path) -> dict:
    """Load the entire config.yaml as a dictionary."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def resolve_project_root(config: dict, config_path: Path) -> Path:
    """Resolve the absolute project root path."""
    raw_root = config.get("project_root", ".")
    if os.path.isabs(raw_root):
        return Path(raw_root)
    # Resolve relative to config file's directory
    return (config_path.parent / raw_root).resolve()
