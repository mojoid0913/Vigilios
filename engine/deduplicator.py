"""
engine/deduplicator.py — 3단계 중복 제거
  L1: URL SHA-256 해시 (정확한 URL 중복)
  L2: SimHash 해밍거리 ≤ threshold (제목+본문 근사 중복)
  L3: 문장 임베딩 코사인 유사도 ≥ threshold (동일 사건 클러스터)

L3는 sentence-transformers가 설치된 경우에만 활성화된다.
"""

import hashlib
from typing import Dict, List, Optional, Tuple

from engine.rules import VigiliosRules

try:
    from simhash import Simhash

    _SIMHASH_AVAILABLE = True
except ImportError:
    _SIMHASH_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()


def _simhash_distance(a: "Simhash", b: "Simhash") -> int:
    return bin(a.value ^ b.value).count("1")


def _text_for_simhash(article: dict) -> str:
    title = article.get("title", "")
    body = article.get("body", "") or article.get("summary", "")
    return f"{title} {body[:500]}"


def _text_for_embedding(article: dict) -> str:
    title = article.get("title", "")
    body = article.get("body", "") or article.get("summary", "")
    return f"{title}. {body[:300]}"


class Deduplicator:
    """3단계 중복 제거기. 상태를 유지하므로 실행당 1개 인스턴스를 사용한다."""

    def __init__(self, rules: Optional[VigiliosRules] = None):
        self.rules = rules or VigiliosRules()
        self._seen_url_hashes: set = set()
        self._simhash_entries: List[Tuple[str, "Simhash"]] = []  # (article_id, simhash)
        self._embedding_model: Optional[SentenceTransformer] = None
        self._embedding_entries: List[Tuple[str, List[float]]] = []  # (article_id, vector)

        if _ST_AVAILABLE:
            self._embedding_model = SentenceTransformer(self.rules.embedding_model)

    # ── 공개 API ──

    def deduplicate(self, articles: List[dict]) -> List[dict]:
        """
        기사 리스트에서 중복을 제거한다.
        각 생존 기사에 corroboration_count 필드를 설정한다.
        """
        # 클러스터 추적: article_id → story_id (동일 사건이면 같은 story_id)
        story_clusters: Dict[str, str] = {}

        after_l1 = self._l1_url_dedup(articles, story_clusters)
        after_l2 = self._l2_simhash_dedup(after_l1, story_clusters)
        after_l3 = self._l3_embedding_dedup(after_l2, story_clusters)

        # corroboration_count: 같은 story_id로 묶인 원본 기사 수
        story_count: Dict[str, int] = {}
        for sid in story_clusters.values():
            story_count[sid] = story_count.get(sid, 0) + 1

        for article in after_l3:
            sid = story_clusters.get(article["id"], article["id"])
            article["corroboration_count"] = story_count.get(sid, 1)

        removed = len(articles) - len(after_l3)
        print(f"  [dedup] {len(articles)} → {len(after_l3)} 기사 (제거: {removed})")
        return after_l3

    # ── 내부 단계 ──

    def _l1_url_dedup(self, articles: List[dict], story_clusters: Dict[str, str]) -> List[dict]:
        unique = []
        for article in articles:
            url_hash = _url_hash(article.get("url", ""))
            if url_hash in self._seen_url_hashes:
                story_clusters[article["id"]] = url_hash
            else:
                self._seen_url_hashes.add(url_hash)
                story_clusters[article["id"]] = article["id"]
                unique.append(article)
        return unique

    def _l2_simhash_dedup(self, articles: List[dict], story_clusters: Dict[str, str]) -> List[dict]:
        if not _SIMHASH_AVAILABLE:
            return articles

        threshold = self.rules.simhash_hamming_threshold
        unique = []

        for article in articles:
            text = _text_for_simhash(article)
            sh = Simhash(text)
            duplicate_id = None

            for existing_id, existing_sh in self._simhash_entries:
                if _simhash_distance(sh, existing_sh) <= threshold:
                    duplicate_id = existing_id
                    break

            if duplicate_id:
                story_clusters[article["id"]] = story_clusters.get(duplicate_id, duplicate_id)
            else:
                self._simhash_entries.append((article["id"], sh))
                unique.append(article)

        return unique

    def _l3_embedding_dedup(self, articles: List[dict], story_clusters: Dict[str, str]) -> List[dict]:
        if not _ST_AVAILABLE or self._embedding_model is None or not articles:
            return articles

        threshold = self.rules.semantic_cosine_threshold
        texts = [_text_for_embedding(a) for a in articles]
        vectors = self._embedding_model.encode(texts, normalize_embeddings=True).tolist()

        unique = []
        for article, vec in zip(articles, vectors):
            duplicate_id = None

            for existing_id, existing_vec in self._embedding_entries:
                cosine = float(np.dot(vec, existing_vec))
                if cosine >= threshold:
                    duplicate_id = existing_id
                    break

            if duplicate_id:
                story_clusters[article["id"]] = story_clusters.get(duplicate_id, duplicate_id)
            else:
                self._embedding_entries.append((article["id"], vec))
                unique.append(article)

        return unique
