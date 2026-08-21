from __future__ import annotations

from typing import Final

PLANNER_VERSION: Final = "mafer-planner-v2.0"
INTENT_VERSION: Final = "mafer-intent-v2.0"
LATTICE_VERSION: Final = "mafer-lattice-v2.0"
ROUTER_VERSION: Final = "mafer-router-v2.0"
ENGINE_ROUTER_VERSION: Final = "mafer-engine-router-v2.0"
UNCERTAINTY_VERSION: Final = "mafer-uncertainty-v2.0"
STOP_MODEL_VERSION: Final = "mafer-stop-v2.0"
RANKING_VERSION: Final = "mirsad-hybrid-lex25-sem75-v1"
SEMANTIC_MODEL: Final = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEMANTIC_MODEL_VERSION: Final = "fastembed-mean-pooling-v1"
CLUSTERING_VERSION: Final = "mirsad-story-clustering-v2"

SHADOW_ROUTER_VERSION: Final = "mafer-shadow-router-v3.0"
SHADOW_UNCERTAINTY_VERSION: Final = "mafer-shadow-uncertainty-v3.0"
SHADOW_STOP_MODEL_VERSION: Final = "mafer-shadow-saturation-v3.0"
SHADOW_FUSION_VERSION: Final = "mafer-shadow-query-fusion-v3.0"
SHADOW_DIVERSITY_VERSION: Final = "mafer-shadow-near-tie-diversity-v3.0"
ARABIC_EXPERT_SHADOW_MODEL: Final = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
ARABIC_EXPERT_SHADOW_VERSION: Final = "not-promoted-shadow-v1"


def production_versions() -> dict[str, str]:
    return {
        "planner_version": PLANNER_VERSION,
        "intent_version": INTENT_VERSION,
        "lattice_version": LATTICE_VERSION,
        "router_version": ROUTER_VERSION,
        "engine_router_version": ENGINE_ROUTER_VERSION,
        "uncertainty_version": UNCERTAINTY_VERSION,
        "stop_model_version": STOP_MODEL_VERSION,
        "ranking_version": RANKING_VERSION,
        "semantic_model": SEMANTIC_MODEL,
        "semantic_model_version": SEMANTIC_MODEL_VERSION,
        "clustering_version": CLUSTERING_VERSION,
    }


def shadow_versions() -> dict[str, str]:
    return {
        "router_version": SHADOW_ROUTER_VERSION,
        "uncertainty_version": SHADOW_UNCERTAINTY_VERSION,
        "stop_model_version": SHADOW_STOP_MODEL_VERSION,
        "fusion_version": SHADOW_FUSION_VERSION,
        "diversity_version": SHADOW_DIVERSITY_VERSION,
        "arabic_expert_model": ARABIC_EXPERT_SHADOW_MODEL,
        "arabic_expert_version": ARABIC_EXPERT_SHADOW_VERSION,
    }
