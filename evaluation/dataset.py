"""SWE-bench dataset loading and instance grouping."""

from __future__ import annotations

from dataclasses import dataclass, field

SWE_BENCH_LITE = "princeton-nlp/SWE-bench_Lite"

GroupKey = tuple[str, str]  # (repo, base_commit)


def load_dataset(dataset_id: str, split: str = "test"):
    """Load a Hugging Face dataset split (module-level hook for tests and ``DatasetManager``)."""
    try:
        from datasets import load_dataset as hf_load_dataset  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Install bench extras: pip install 'codegraph[bench]'"
        ) from exc
    return hf_load_dataset(dataset_id, split=split)


@dataclass
class InstanceGroup:
    """Instances sharing the same (repo, base_commit)."""

    key: GroupKey
    instances: list[tuple[int, dict]] = field(default_factory=list)


def group_instances(indexed_instances: list[tuple[int, dict]]) -> list[InstanceGroup]:
    """Group indexed instances by (repo, base_commit).

    Returns groups sorted by the smallest original index in each group so that
    execution order is deterministic and matches dataset order.
    """
    groups: dict[GroupKey, InstanceGroup] = {}
    for idx, inst in indexed_instances:
        key: GroupKey = (inst["repo"], inst["base_commit"])
        if key not in groups:
            groups[key] = InstanceGroup(key=key)
        groups[key].instances.append((idx, inst))

    return sorted(groups.values(), key=lambda g: min(i for i, _ in g.instances))


class DatasetManager:
    """Load SWE-bench Lite and prepare instance groups for the runner."""

    def __init__(self, dataset_id: str = SWE_BENCH_LITE) -> None:
        self.dataset_id = dataset_id

    def load(self, split: str = "test") -> list[dict]:
        """Load instances from Hugging Face datasets."""
        return list(load_dataset(self.dataset_id, split=split))

    def load_limited(self, split: str = "test", limit: int = 0) -> list[dict]:
        """Load instances, optionally truncating to the first ``limit`` rows."""
        instances = self.load(split=split)
        if limit > 0:
            return instances[:limit]
        return instances

    @staticmethod
    def group(indexed_instances: list[tuple[int, dict]]) -> list[InstanceGroup]:
        """Group indexed instances by (repo, base_commit)."""
        return group_instances(indexed_instances)
