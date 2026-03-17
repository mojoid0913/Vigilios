"""
engine/enricher.py — 기사 보강 (Enrichment)

- TopicClassifier: topics.json 키워드 매칭으로 도메인 분류
- DomainRouter: 기사의 primary_domain 결정 (wire 서비스는 여기서 라우팅)
- PMESIITagger: 도메인 → PMESII 카테고리 매핑
- NERExtractor: spaCy 개체명 인식 (설치된 경우에만)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.rules import VigiliosRules
from engine.utils import load_json

_CONFIG_DIR = Path(__file__).parent.parent / "config"

# PMESII 매핑: 도메인 → [카테고리]
_PMESII_MAP: Dict[str, List[str]] = {
    "politics": ["Political"],
    "military": ["Military"],
    "lawfare": ["Political"],
    "economics": ["Economic"],
    "trade_sanctions": ["Economic", "Political"],
    "energy_resources": ["Economic", "Infrastructure"],
    "religion_ideology": ["Social"],
    "social_unrest": ["Social", "Political"],
    "demography": ["Social"],
    "technology_cyber": ["Information", "Infrastructure"],
    "information_ops": ["Information"],
    "climate_env": ["Infrastructure", "Economic"],
    "health_pandemic": ["Social", "Infrastructure"],
}

# 행위자 중요도: 키워드 → 점수 (0–1)
_MAJOR_ACTORS = {
    "united states", "us ", " us ", "u.s.", "washington",
    "china", "chinese", "beijing",
    "russia", "russian", "moscow",
    "nato", "european union", "eu ", " eu ",
    "united nations", " un ", "u.n.",
    "uk ", "britain", "london",
}
_REGIONAL_ACTORS = {
    "iran", "india", "brazil", "turkey", "saudi arabia",
    "israel", "north korea", "dprk", "japan", "germany",
    "france", "south korea", "pakistan",
}

try:
    import spacy

    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False


class Enricher:
    """기사 목록에 도메인·PMESII·NER 등의 메타데이터를 추가한다."""

    def __init__(self, rules: Optional[VigiliosRules] = None):
        self.rules = rules or VigiliosRules()
        self._topics = self._load_topics()
        self._nlp = self._load_spacy()

    # ── 공개 API ──

    def enrich(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """기사 리스트를 보강해 반환한다."""
        enriched = []
        for article in articles:
            enriched.append(self._enrich_one(article))
        return enriched

    # ── 내부 메서드 ──

    def _enrich_one(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = self._article_text(article)
        text_lower = text.lower()

        # 도메인 분류
        domain_scores = self._classify_domains(text_lower)
        primary_domain = self._route_domain(article, domain_scores)
        matched_gdelt = self._match_gdelt_themes(primary_domain, text_lower)

        # PMESII 태깅
        pmesii_tags = _PMESII_MAP.get(primary_domain, [])

        # 행위자 중요도
        actor_significance = self._score_actor_significance(text_lower)

        # NER (선택적)
        ner_entities = self._extract_ner(text) if self._nlp else []

        article = dict(article)
        article.update(
            {
                "domain_scores": domain_scores,
                "primary_domain": primary_domain,
                "gdelt_themes": matched_gdelt,
                "pmesii_tags": pmesii_tags,
                "actor_significance": actor_significance,
                "ner_entities": ner_entities,
            }
        )
        return article

    def _article_text(self, article: Dict[str, Any]) -> str:
        title = article.get("title", "")
        body = article.get("body", "") or article.get("summary", "")
        return f"{title} {body}"

    def _classify_domains(self, text_lower: str) -> Dict[str, int]:
        """각 도메인의 키워드 매치 수를 반환한다."""
        scores: Dict[str, int] = {}
        for domain, cfg in self._topics.items():
            count = sum(1 for kw in cfg.get("keywords", []) if kw.lower() in text_lower)
            if count > 0:
                scores[domain] = count
        return scores

    def _route_domain(self, article: Dict[str, Any], domain_scores: Dict[str, int]) -> str:
        """
        기사의 primary_domain을 결정한다.
        - 소스 domain이 "all"이 아니면 소스 지정 domain을 사용한다.
        - "all"(와이어 서비스)이면 키워드 스코어 최고 도메인.
        - 매칭 없으면 "politics" 기본값.
        """
        source_domain = article.get("domain", "all")
        if source_domain and source_domain != "all":
            return source_domain

        if domain_scores:
            return max(domain_scores, key=lambda d: domain_scores[d])

        return "politics"

    def _match_gdelt_themes(self, domain: str, text_lower: str) -> List[str]:
        """도메인의 GDELT 테마 중 텍스트에 등장하는 것만 반환."""
        cfg = self._topics.get(domain, {})
        themes = cfg.get("gdelt_themes", [])
        return [t for t in themes if t.lower().replace("_", " ") in text_lower]

    def _score_actor_significance(self, text_lower: str) -> float:
        """텍스트 내 주요 행위자 등장 여부로 중요도 점수를 산정한다."""
        for actor in _MAJOR_ACTORS:
            if actor in text_lower:
                return 0.9
        for actor in _REGIONAL_ACTORS:
            if actor in text_lower:
                return 0.7
        return 0.5

    def _extract_ner(self, text: str) -> List[Dict[str, str]]:
        """spaCy NER: 국가·기관·인물 개체명 추출."""
        try:
            doc = self._nlp(text[:1000])  # 속도를 위해 앞부분만
            return [
                {"text": ent.text, "label": ent.label_}
                for ent in doc.ents
                if ent.label_ in {"GPE", "ORG", "PERSON", "NORP"}
            ]
        except Exception:
            return []

    def _load_topics(self) -> Dict[str, Any]:
        data = load_json(_CONFIG_DIR / "topics.json")
        return data.get("domains", {})

    def _load_spacy(self) -> Optional[Any]:
        if not _SPACY_AVAILABLE:
            return None
        try:
            import spacy

            return spacy.load("en_core_web_sm")
        except OSError:
            # 모델 미설치: python -m spacy download en_core_web_sm
            return None
