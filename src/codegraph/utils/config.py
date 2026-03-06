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


def parse_signal_weights(seed_section: dict) -> dict[str, float]:
    """Parse signal weights from the seed_selection config section.

    Returns a dict with keys: entity_match, bm25, current_file, bm25_top_n.
    Only keys present in seed_section are included; callers merge with defaults.
    """
    signal_weights: dict[str, float] = {}
    if seed_section.get("entity_match_weight") is not None:
        signal_weights["entity_match"] = float(seed_section["entity_match_weight"])
    if seed_section.get("bm25_weight") is not None:
        signal_weights["bm25"] = float(seed_section["bm25_weight"])
    if seed_section.get("current_file_weight") is not None:
        signal_weights["current_file"] = float(seed_section["current_file_weight"])
    if seed_section.get("bm25_top_n") is not None:
        signal_weights["bm25_top_n"] = int(seed_section["bm25_top_n"])
    return signal_weights
