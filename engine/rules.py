"""
engine/rules.py — VigiliosRules
파이프라인 전체 임계값·가중치의 단일 진실 공급원.
config/vigilios_rules.json을 읽으며, 값을 코드에 하드코딩하지 않는다.
"""

from pathlib import Path
from typing import Optional, Union

from engine.utils import load_json

_REQUIRED_SECTIONS = {
    "collection": "rss_poll_interval_minutes",
    "dedup": "simhash_hamming_threshold",
    "credibility": "mbfc_minimum_factual_score",
    "scoring": "importance_weights",
    "selection": "top_n_per_domain",
    "vdb": "embedding_model",
    "ontology": "causal_chain_min_confidence",
    "ai": "model",
}


class VigiliosRules:
    """파이프라인 설정 컨테이너.

    Usage:
        rules = VigiliosRules()
        rules.validate()
        threshold = rules.simhash_hamming_threshold
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent / "config" / "vigilios_rules.json"
            )
        self._raw = load_json(config_path)
        self.version: str = self._raw.get("version", "unknown")

    # ── Collection ──

    @property
    def rss_poll_interval_minutes(self) -> int:
        return self._raw["collection"]["rss_poll_interval_minutes"]

    @property
    def max_age_hours(self) -> int:
        return self._raw["collection"]["max_age_hours"]

    @property
    def min_article_length_chars(self) -> int:
        return self._raw["collection"]["min_article_length_chars"]

    @property
    def max_articles_per_feed(self) -> int:
        return self._raw["collection"]["max_articles_per_feed"]

    @property
    def request_timeout_seconds(self) -> int:
        return self._raw["collection"]["request_timeout_seconds"]

    # ── Dedup ──

    @property
    def simhash_hamming_threshold(self) -> int:
        return self._raw["dedup"]["simhash_hamming_threshold"]

    @property
    def semantic_cosine_threshold(self) -> float:
        return self._raw["dedup"]["semantic_cosine_threshold"]

    @property
    def story_cluster_window_hours(self) -> int:
        return self._raw["dedup"]["story_cluster_window_hours"]

    # ── Credibility ──

    @property
    def mbfc_minimum_factual_score(self) -> float:
        return self._raw["credibility"]["mbfc_minimum_factual_score"]

    @property
    def corroboration_minimum_sources(self) -> int:
        return self._raw["credibility"]["corroboration_minimum_sources"]

    @property
    def domain_age_minimum_days(self) -> int:
        return self._raw["credibility"]["domain_age_minimum_days"]

    @property
    def credibility_score_mapping(self) -> dict[str, float]:
        return self._raw["credibility"]["score_mapping"]

    # ── Scoring ──

    @property
    def importance_weights(self) -> dict[str, float]:
        return self._raw["scoring"]["importance_weights"]

    @property
    def risk_weights(self) -> dict[str, float]:
        return self._raw["scoring"]["risk_weights"]

    @property
    def single_source_penalty(self) -> float:
        return self._raw["scoring"]["single_source_penalty"]

    # ── Selection ──

    @property
    def top_n_per_domain(self) -> int:
        return self._raw["selection"]["top_n_per_domain"]

    @property
    def max_per_country(self) -> int:
        return self._raw["selection"]["max_per_country"]

    @property
    def include_fringe_if_kernel_confirmed(self) -> bool:
        return self._raw["selection"]["include_fringe_if_kernel_confirmed"]

    @property
    def min_importance_score(self) -> float:
        return self._raw["selection"]["min_importance_score"]

    # ── VDB ──

    @property
    def domains(self) -> list[str]:
        return self._raw["vdb"]["domains"]

    @property
    def hot_layer_days(self) -> int:
        return self._raw["vdb"]["hot_layer_days"]

    @property
    def cold_layer_days(self) -> int:
        return self._raw["vdb"]["cold_layer_days"]

    @property
    def cross_domain_top_k(self) -> int:
        return self._raw["vdb"]["cross_domain_top_k"]

    @property
    def embedding_model(self) -> str:
        return self._raw["vdb"]["embedding_model"]

    @property
    def vdb_persist_directory(self) -> str:
        return self._raw["vdb"]["persist_directory"]

    @property
    def chunk_size_chars(self) -> int:
        return self._raw["vdb"]["chunk_size_chars"]

    @property
    def chunk_overlap_chars(self) -> int:
        return self._raw["vdb"]["chunk_overlap_chars"]

    # ── Ontology ──

    @property
    def wikidata_refresh_interval_days(self) -> int:
        return self._raw["ontology"]["wikidata_refresh_interval_days"]

    @property
    def causal_chain_min_confidence(self) -> float:
        return self._raw["ontology"]["causal_chain_min_confidence"]

    @property
    def sparql_endpoint(self) -> str:
        return self._raw["ontology"]["sparql_endpoint"]

    @property
    def sparql_timeout_seconds(self) -> int:
        return self._raw["ontology"]["sparql_timeout_seconds"]

    # ── AI ──

    @property
    def ai_model(self) -> str:
        return self._raw["ai"]["model"]

    @property
    def grounding_enabled(self) -> bool:
        return self._raw["ai"]["grounding_enabled"]

    @property
    def grounding_max_calls_per_run(self) -> int:
        return self._raw["ai"]["grounding_max_calls_per_run"]

    @property
    def ai_temperature(self) -> float:
        return self._raw["ai"]["temperature"]

    @property
    def ai_max_output_tokens(self) -> int:
        return self._raw["ai"]["max_output_tokens"]

    # ── Validation ──

    def validate(self) -> None:
        """설정 무결성 검사. 누락된 섹션·키가 있으면 KeyError를 발생시킨다."""
        for section, sample_key in _REQUIRED_SECTIONS.items():
            if section not in self._raw:
                raise KeyError(f"vigilios_rules.json 섹션 누락: '{section}'")
            if sample_key not in self._raw[section]:
                raise KeyError(
                    f"vigilios_rules.json['{section}'] 키 누락: '{sample_key}'"
                )

        weights = self.importance_weights
        total = sum(weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"importance_weights 합계가 1.0이어야 합니다. 현재: {total:.4f}"
            )
