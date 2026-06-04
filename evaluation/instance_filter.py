"""Resolve benchmark instance subsets for fast iteration tiers."""

from __future__ import annotations

import json
from pathlib import Path


def load_weak_spot_tier(path: Path, tier_key: str) -> list[str]:
    """Load instance_ids for a named tier from a JSON object keyed by tier name."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if tier_key not in data:
        raise KeyError(
            f"Unknown tier {tier_key!r} in {path}. "
            f"Available: {sorted(data.keys())}"
        )
    tier = data[tier_key]
    ids = tier.get("instance_ids") or []
    if not ids:
        raise ValueError(f"Tier {tier_key!r} has no instance_ids in {path}")
    return list(ids)


def resolve_instance_ids_arg(spec: str) -> tuple[set[str], str | None]:
    """Parse ``--instance-ids-file`` value.

    Formats:
        - ``path/to/ids.json`` — JSON list of instance_id strings
        - ``path/to/subset.json:tier_key`` — named tier in a JSON object

    Returns:
        (instance_id set, subset label for summary metadata)
    """
    spec = spec.strip()
    if ":" in spec:
        path_str, tier_key = spec.rsplit(":", 1)
        path = Path(path_str)
        ids = load_weak_spot_tier(path, tier_key)
        return set(ids), tier_key

    path = Path(spec)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return set(str(x) for x in raw), path.stem
    if isinstance(raw, dict) and "instance_ids" in raw:
        return set(str(x) for x in raw["instance_ids"]), path.stem
    raise ValueError(
        f"Expected JSON list or {{instance_ids: [...]}} in {path}, got {type(raw)}"
    )
