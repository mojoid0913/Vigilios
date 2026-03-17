"""
engine/selector.py — 도메인별 Top N 선정

규칙:
  1. min_importance_score 미만 기사 제외
  2. 도메인별 bias_adjusted_score 상위 top_n_per_domain 선정
  3. 국가/지역별 max_per_country 초과 시 스코어 낮은 것 제거
  4. include_fringe_if_kernel_confirmed=True 이면 corroboration_count==1 기사 중
     스코어 최고 1건 추가 (이미 선정된 기사와 도메인 중복 허용)
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from engine.rules import VigiliosRules
from engine.enricher import _PMESII_MAP  # 도메인→PMESII 참조용

# GPE NER 레이블에서 국가/지역을 추출하기 위한 단순 매핑
# NER 없는 환경에서는 대문자 고유명사 단어 2개 이하 추출
_FALLBACK_COUNTRY_KEYWORDS: Dict[str, str] = {
    "united states": "US", "u.s.": "US", "us ": "US",
    "china": "China", "chinese": "China", "beijing": "China",
    "russia": "Russia", "russian": "Russia", "moscow": "Russia",
    "europe": "Europe", "european union": "Europe",
    "iran": "Iran", "india": "India", "north korea": "North Korea",
    "ukraine": "Ukraine", "israel": "Israel", "taiwan": "Taiwan",
    "saudi arabia": "Saudi Arabia", "turkey": "Turkey",
}


def _primary_country(article: Dict[str, Any]) -> str:
    """기사의 주 국가/지역 식별. NER GPE 우선, 없으면 키워드 fallback."""
    ner = article.get("ner_entities", [])
    for ent in ner:
        if ent.get("label") == "GPE":
            return ent["text"].title()

    text_lower = (article.get("title", "") + " " + (article.get("body", "") or "")[:200]).lower()
    for keyword, country in _FALLBACK_COUNTRY_KEYWORDS.items():
        if keyword in text_lower:
            return country
    return "Other"


class Selector:
    """스코어링된 기사에서 보고서에 포함할 기사를 선정한다."""

    def __init__(self, rules: Optional[VigiliosRules] = None):
        self.rules = rules or VigiliosRules()

    # ── 공개 API ──

    def select(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        규칙 기반으로 기사를 선정한다.

        Returns:
            선정된 기사 리스트 (bias_adjusted_score 내림차순)
        """
        min_score = self.rules.min_importance_score
        top_n = self.rules.top_n_per_domain
        max_country = self.rules.max_per_country
        include_fringe = self.rules.include_fringe_if_kernel_confirmed

        # 1. 최소 점수 필터
        candidates = [a for a in articles if a.get("bias_adjusted_score", 0) >= min_score]

        # 2. 도메인별 Top N
        selected = self._top_n_per_domain(candidates, top_n)

        # 3. 국가별 상한 적용
        selected = self._apply_country_cap(selected, max_country)

        # 4. fringe 기사 추가 (선택적)
        if include_fringe:
            fringe = self._best_fringe(candidates, selected)
            if fringe:
                selected.append(fringe)

        selected.sort(key=lambda a: a.get("bias_adjusted_score", 0), reverse=True)
        print(f"  [selector] {len(articles)} → {len(selected)} 기사 선정")
        return selected

    # ── 내부 메서드 ──

    def _top_n_per_domain(self, articles: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for a in articles:
            domain = a.get("primary_domain", "politics")
            by_domain[domain].append(a)

        selected = []
        for domain_articles in by_domain.values():
            sorted_articles = sorted(
                domain_articles,
                key=lambda a: a.get("bias_adjusted_score", 0),
                reverse=True,
            )
            selected.extend(sorted_articles[:top_n])
        return selected

    def _apply_country_cap(
        self, articles: List[Dict[str, Any]], max_country: int
    ) -> List[Dict[str, Any]]:
        country_count: Dict[str, int] = defaultdict(int)
        result = []

        for article in sorted(articles, key=lambda a: a.get("bias_adjusted_score", 0), reverse=True):
            country = _primary_country(article)
            if country == "Other" or country_count[country] < max_country:
                country_count[country] += 1
                result.append(article)

        return result

    def _best_fringe(
        self,
        candidates: List[Dict[str, Any]],
        already_selected: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """corroboration_count==1 (단일 소스) 기사 중 스코어 최고를 반환한다."""
        selected_ids = {a["id"] for a in already_selected}
        fringe_candidates = [
            a
            for a in candidates
            if a.get("corroboration_count", 1) == 1 and a["id"] not in selected_ids
        ]
        if not fringe_candidates:
            return None
        return max(fringe_candidates, key=lambda a: a.get("bias_adjusted_score", 0))
