"""Ablation study configurations for CodeGraph evaluation.

Each AblationConfig overrides one or more pipeline parameters. Running the
benchmark with each config in ABLATIONS isolates the contribution of individual
design decisions (edge types, orientation, IDF weighting, PPR parameters).
"""

from dataclasses import dataclass, field

from codegraph.core.graph.ppr import PPRConfig


@dataclass(frozen=True)
class AblationConfig:
    """Override set for a single ablation study run.

    Attributes:
        name: Short identifier used in output filenames and summary JSON.
        relationship_types: Edge types included in the GDS projection. None means
            use all four (CONTAINS, CALLS, IMPORTS, INHERITS_FROM).
        orientation: GDS projection orientation — "UNDIRECTED", "NATURAL", or "REVERSE".
        apply_idf: When False, skip IDF weight recomputation before projection.
        ppr_config: PPRConfig override (damping_factor, top_k, etc.).
    """

    name: str
    relationship_types: list[str] | None = None
    orientation: str = "UNDIRECTED"
    apply_idf: bool = True
    ppr_config: PPRConfig = field(default_factory=PPRConfig)


# ---------------------------------------------------------------------------
# Edge-type ablations: drop one relationship type at a time
# ---------------------------------------------------------------------------

_ALL_TYPES = ["CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM"]

ABLATIONS: list[AblationConfig] = [
    # Full config — the default run; used as the reference point.
    AblationConfig(name="baseline"),

    # Edge-type ablations
    AblationConfig(
        name="no_calls",
        relationship_types=[t for t in _ALL_TYPES if t != "CALLS"],
    ),
    AblationConfig(
        name="no_imports",
        relationship_types=[t for t in _ALL_TYPES if t != "IMPORTS"],
    ),
    AblationConfig(
        name="no_inherits",
        relationship_types=[t for t in _ALL_TYPES if t != "INHERITS_FROM"],
    ),

    # Orientation sweep
    AblationConfig(name="directed_natural", orientation="NATURAL"),
    AblationConfig(name="directed_reverse", orientation="REVERSE"),

    # IDF weighting ablation
    AblationConfig(name="no_idf", apply_idf=False),

    # Weighted vs uniform PPR (isolates seed relevance scoring contribution)
    AblationConfig(name="ppr_uniform", ppr_config=PPRConfig(retrieval_mode="uniform")),

    # Damping factor sweep
    AblationConfig(name="alpha_010", ppr_config=PPRConfig(damping_factor=0.10)),
    AblationConfig(name="alpha_015", ppr_config=PPRConfig(damping_factor=0.15)),
    AblationConfig(name="alpha_020", ppr_config=PPRConfig(damping_factor=0.20)),
    AblationConfig(name="alpha_030", ppr_config=PPRConfig(damping_factor=0.30)),

    # top-k sweep
    AblationConfig(name="top_k_5",  ppr_config=PPRConfig(top_k=5)),
    AblationConfig(name="top_k_10", ppr_config=PPRConfig(top_k=10)),
    AblationConfig(name="top_k_50", ppr_config=PPRConfig(top_k=50)),
]
