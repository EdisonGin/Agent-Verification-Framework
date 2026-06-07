"""Dependency-free deterministic text embedding utilities."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class DeterministicTextEmbedder:
    """Create reproducible sparse lexical vectors without external embedding APIs."""

    def embed(self, text: str) -> Dict[str, float]:
        if not isinstance(text, str) or not text:
            raise ValueError("DeterministicTextEmbedder text must be a non-empty string")

        counts = Counter(TOKEN_PATTERN.findall(text.lower()))
        if not counts:
            return {}

        norm = math.sqrt(sum(count * count for count in counts.values()))
        if norm == 0:
            return {}
        return {token: count / norm for token, count in sorted(counts.items())}
