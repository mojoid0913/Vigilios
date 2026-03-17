"""
engine/utils.py — 공통 유틸리티
"""

import json
import re
from pathlib import Path
from typing import Union


def load_json(path: Union[str, Path]) -> dict:
    """JSON 파일 로더. // 한줄 주석을 허용한다."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return json.loads(text)
