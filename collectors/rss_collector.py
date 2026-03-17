"""
collectors/rss_collector.py — RSS 피드 수집기

feedparser: 피드 항목 파싱
trafilatura: 기사 원문 추출
"""

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser

try:
    import trafilatura

    _TRAFILATURA_AVAILABLE = True
except ImportError:
    _TRAFILATURA_AVAILABLE = False

try:
    from dateutil import parser as dateutil_parser

    _DATEUTIL_AVAILABLE = True
except ImportError:
    _DATEUTIL_AVAILABLE = False

from collectors.base_collector import fetch_parallel
from engine.rules import VigiliosRules
from engine.utils import load_json

_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _canonical_url(url: str) -> str:
    """URL 정규화: 쿼리스트링 제거 없이 소문자 strip만 적용."""
    return url.strip().lower()


def _url_id(url: str) -> str:
    """기사 ID: canonical URL의 SHA-256."""
    return hashlib.sha256(_canonical_url(url).encode("utf-8")).hexdigest()


def _parse_published_at(entry: Any) -> datetime:
    """feedparser 항목에서 published_at (UTC datetime) 추출."""
    # feedparser는 published_parsed (time.struct_time) 제공
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = time.mktime(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError):
            pass

    # 문자열 폴백
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw and _DATEUTIL_AVAILABLE:
        try:
            dt = dateutil_parser.parse(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, OverflowError):
            pass

    return datetime.now(tz=timezone.utc)


def _fetch_body(url: str, timeout: int) -> str:
    """trafilatura로 기사 원문 추출. 실패 시 빈 문자열 반환."""
    if not _TRAFILATURA_AVAILABLE:
        return ""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return text or ""
    except Exception:
        pass
    return ""


class RSSCollector:
    """설정된 RSS 소스에서 기사를 병렬 수집한다."""

    def __init__(self, rules: Optional[VigiliosRules] = None):
        self.rules = rules or VigiliosRules()
        self._sources: List[Dict[str, Any]] = self._load_active_sources()

    # ── 공개 API ──

    def collect(self) -> List[Dict[str, Any]]:
        """
        모든 활성 RSS 소스에서 기사를 수집한다.

        Returns:
            list[dict]: 수집된 기사 리스트 (중복 미제거 원본)
        """
        articles = fetch_parallel(
            items=self._sources,
            fetch_fn=self._fetch_source,
            max_workers=10,
            label="rss",
        )
        print(f"  [rss] 총 {len(articles)} 기사 수집 완료")
        return articles

    # ── 내부 메서드 ──

    def _load_active_sources(self) -> List[Dict[str, Any]]:
        data = load_json(_CONFIG_DIR / "sources.json")
        return [s for s in data.get("sources", []) if s.get("active", True)]

    def _fetch_source(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """단일 RSS 소스에서 기사 목록을 수집한다."""
        try:
            feed = feedparser.parse(
                source["url"],
                request_headers={"User-Agent": "Vigilios/1.0"},
            )
        except Exception:
            return []

        if feed.bozo and not feed.entries:
            return []

        cutoff = self._age_cutoff_timestamp()
        articles = []

        for entry in feed.entries[: self.rules.max_articles_per_feed]:
            url = self._entry_url(entry)
            if not url:
                continue

            published_at = _parse_published_at(entry)
            if published_at.timestamp() < cutoff:
                continue

            summary = getattr(entry, "summary", "") or ""
            body = _fetch_body(url, self.rules.request_timeout_seconds)

            # 본문이 너무 짧으면 건너뜀
            effective_text = body if body else summary
            if len(effective_text) < self.rules.min_article_length_chars:
                continue

            articles.append(
                {
                    "id": _url_id(url),
                    "url": url,
                    "title": getattr(entry, "title", "").strip(),
                    "body": body,
                    "summary": summary,
                    "published_at": published_at.isoformat(),
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "domain": source["domain"],
                    "bias_rating": source.get("bias_rating", "unknown"),
                    "factual_rating": source.get("factual_rating", "unknown"),
                    "credibility_score": source.get("credibility_score", 0.5),
                    "language": source.get("language", "en"),
                }
            )

        return articles

    def _entry_url(self, entry: Any) -> str:
        """feedparser 항목에서 URL 추출."""
        url = getattr(entry, "link", "") or ""
        if not url:
            links = getattr(entry, "links", [])
            if links:
                url = links[0].get("href", "")
        return url.strip()

    def _age_cutoff_timestamp(self) -> float:
        """수집 가능한 가장 오래된 기사의 Unix timestamp."""
        now = datetime.now(tz=timezone.utc).timestamp()
        return now - self.rules.max_age_hours * 3600
