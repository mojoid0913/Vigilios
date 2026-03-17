"""
engine/scorer.py — ImportanceScore + RiskScore 산정

ImportanceScore = credibility×0.35 + corroboration×0.25
               + actor_significance×0.25 + novelty×0.15

RiskScore = PMESII 도메인별 가중치 × 개별 위험도 평균

BiasAdjustedScore = ImportanceScore × (1 - single_source_penalty)
                    (단일 소스 기사에만 패널티 적용)
"""

from typing import Any, Dict, List, Optional

from engine.rules import VigiliosRules

# PMESII 위험도 가중치 (risk_weights의 키 → pmesii_tags 매핑)
_PMESII_TO_RISK_KEY: Dict[str, str] = {
    "Political": "political",
    "Military": "military",
    "Economic": "economic",
    "Social": "social",
    "Information": "information",
    "Infrastructure": "infrastructure",
}


def _normalize(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class Scorer:
    """기사 목록에 중요도·위험도 점수를 추가한다."""

    def __init__(self, rules: Optional[VigiliosRules] = None):
        self.rules = rules or VigiliosRules()
        self._importance_w = self.rules.importance_weights
        self._risk_w = self.rules.risk_weights
        self._penalty = self.rules.single_source_penalty

    # ── 공개 API ──

    def score(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """각 기사에 importance_score, risk_score, bias_adjusted_score를 추가한다."""
        return [self._score_one(a) for a in articles]

    # ── 내부 메서드 ──

    def _score_one(self, article: Dict[str, Any]) -> Dict[str, Any]:
        article = dict(article)

        importance = self._importance_score(article)
        risk = self._risk_score(article)
        corroboration_count = article.get("corroboration_count", 1)
        bias_adjusted = importance * (1 - self._penalty) if corroboration_count == 1 else importance

        article["importance_score"] = round(_normalize(importance), 4)
        article["risk_score"] = round(_normalize(risk), 4)
        article["bias_adjusted_score"] = round(_normalize(bias_adjusted), 4)
        return article

    def _importance_score(self, article: Dict[str, Any]) -> float:
        w = self._importance_w

        credibility = _normalize(article.get("credibility_score", 0.5))

        corroboration_count = article.get("corroboration_count", 1)
        corroboration = _normalize(min(corroboration_count / 5.0, 1.0))  # 5개 소스 = 1.0

        actor_significance = _normalize(article.get("actor_significance", 0.5))

        # novelty: Phase 2에서는 기본값 사용, Phase 3 VDB 저장 후 실제 계산
        novelty = _normalize(article.get("novelty", 0.7))

        return (
            w.get("credibility", 0.35) * credibility
            + w.get("corroboration", 0.25) * corroboration
            + w.get("actor_significance", 0.25) * actor_significance
            + w.get("novelty", 0.15) * novelty
        )

    def _risk_score(self, article: Dict[str, Any]) -> float:
        pmesii_tags = article.get("pmesii_tags", [])
        if not pmesii_tags:
            return 0.3  # 기본 위험도

        w = self._risk_w
        total = 0.0
        weight_sum = 0.0

        for tag in pmesii_tags:
            risk_key = _PMESII_TO_RISK_KEY.get(tag)
            if risk_key and risk_key in w:
                weight = w[risk_key]
                total += weight
                weight_sum += weight

        if weight_sum == 0:
            return 0.3

        # 위험도: 활성화된 PMESII 카테고리 가중치 합 / 전체 가중치 합
        all_weights_sum = sum(w.values()) or 1.0
        return _normalize(total / all_weights_sum)
