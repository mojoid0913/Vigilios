"""
collectors/base_collector.py — 병렬 수집 공통 래퍼
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, List, Optional


def fetch_parallel(
    items: List[Any],
    fetch_fn: Callable[[Any], Optional[Any]],
    max_workers: int = 10,
    label: str = "sources",
) -> List[Any]:
    """
    범용 병렬 수집 함수.

    Args:
        items: 수집 대상 항목 리스트 (각 항목을 fetch_fn에 전달)
        fetch_fn: 단일 항목을 받아 결과(list/dict) 또는 None을 반환하는 함수
        max_workers: 동시 실행 스레드 수
        label: 진행 로그 라벨

    Returns:
        list: None 제외, list 결과는 평탄화된 통합 리스트
    """
    results: List[Any] = []
    failed = 0
    total = len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(fetch_fn, item): item for item in items}

        for future in as_completed(future_to_item):
            try:
                result = future.result()
                if result is None:
                    failed += 1
                elif isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)
            except Exception:
                failed += 1

    print(f"  [{label}] {total} 소스 → {len(results)} 결과 ({failed} 실패)")
    return results
