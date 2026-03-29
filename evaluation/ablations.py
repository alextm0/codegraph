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
            use all five (CONTAINS, CALLS, IMPORTS, INHERITS_FROM, CO_LOCATED).
        orientation: GDS projection orientation — "UNDIRECTED", "NATURAL", or "REVERSE".
        apply_idf: When False, skip IDF weight recomputation before projection.
        expand_neighbors: When False, skip SpIDER-inspired structural neighborhood
            expansion after PPR (useful for isolating its contribution).
        inject_directory_files: When False, skip directory-based file injection
            after PPR (useful for isolating its contribution). See DEC-021.
        ppr_config: PPRConfig override (damping_factor, top_k, etc.).
    """

    name: str
    relationship_types: list[str] | None = None
    orientation: str = "UNDIRECTED"
    apply_idf: bool = True
    expand_neighbors: bool = False
    inject_directory_files: bool = False
    create_colocation_edges: bool = False
    ppr_config: PPRConfig = field(default_factory=PPRConfig)


# ---------------------------------------------------------------------------
# Edge-type ablations: drop one relationship type at a time
# ---------------------------------------------------------------------------

_ALL_TYPES = ["CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM"]
_ALL_TYPES_WITH_COLOCATION = ["CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM", "CO_LOCATED"]

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
    # Weighted PPR — kept for ablation regression tracking (was former default, now outperformed by uniform)
    AblationConfig(name="ppr_weighted", ppr_config=PPRConfig(retrieval_mode="weighted")),

    # Damping factor sweep
    AblationConfig(name="alpha_010", ppr_config=PPRConfig(damping_factor=0.10)),
    AblationConfig(name="alpha_015", ppr_config=PPRConfig(damping_factor=0.15)),
    AblationConfig(name="alpha_020", ppr_config=PPRConfig(damping_factor=0.20)),
    AblationConfig(name="alpha_030", ppr_config=PPRConfig(damping_factor=0.30)),

    # top-k sweep
    AblationConfig(name="top_k_5",  ppr_config=PPRConfig(top_k=5)),
    AblationConfig(name="top_k_10", ppr_config=PPRConfig(top_k=10)),
    AblationConfig(name="top_k_50", ppr_config=PPRConfig(top_k=50)),

    # Structural expansion ablations — isolate SpIDER-inspired neighborhood expansion
    AblationConfig(name="no_structural_expansion", expand_neighbors=False),

    # CO_LOCATED edge + directory injection ablations (iteration 3)
    # Iteration 3 result: CO_LOCATED + injection was net-neutral on R@10 (74.0% → 73.33%).
    # These ablations are retained for reproducibility and negative result documentation.
    # See DEC-020, DEC-021, DEC-022.

    # no_colocation_edges: CO_LOCATED edges built but excluded from GDS projection; injection enabled
    AblationConfig(
        name="no_colocation_edges",
        relationship_types=_ALL_TYPES,
        inject_directory_files=True,
        create_colocation_edges=True,
    ),
    # no_directory_injection: CO_LOCATED edges in PPR but no post-hoc injection
    AblationConfig(
        name="no_directory_injection",
        inject_directory_files=False,
        create_colocation_edges=True,
    ),
    # no_colocation_no_injection: pure iter-2 PPR; baseline for iter-3 comparison
    AblationConfig(
        name="no_colocation_no_injection",
        relationship_types=_ALL_TYPES,
        inject_directory_files=False,
        create_colocation_edges=False,
    ),
    # colocation_only: CO_LOCATED edges in PPR, no post-hoc injection
    AblationConfig(
        name="colocation_only",
        inject_directory_files=False,
        create_colocation_edges=True,
    ),
    # injection_only: post-hoc injection, CO_LOCATED edges excluded from graph and GDS
    AblationConfig(
        name="injection_only",
        relationship_types=_ALL_TYPES,
        inject_directory_files=True,
        create_colocation_edges=False,
    ),

    # Uniform PPR parameter sweep — combined configurations for further tuning
    # Uniform PPR + damping factor sweep — find optimal alpha for uniform mode
    AblationConfig(
        name="uniform_alpha_050",
        ppr_config=PPRConfig(retrieval_mode="uniform", damping_factor=0.50),
    ),
    AblationConfig(
        name="uniform_alpha_070",
        ppr_config=PPRConfig(retrieval_mode="uniform", damping_factor=0.70),
    ),

    # Uniform PPR without IDF — test if IDF still has no effect with uniform mode
    AblationConfig(
        name="uniform_no_idf",
        apply_idf=False,
        ppr_config=PPRConfig(retrieval_mode="uniform"),
    ),

    # Uniform PPR with larger top-k — test if more results improve recall
    AblationConfig(
        name="uniform_top_k_30",
        ppr_config=PPRConfig(retrieval_mode="uniform", top_k=30),
    ),
]
