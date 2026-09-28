"""Shannon entropy: how unpredictable the characters in a string are."""

from __future__ import annotations

import math
from collections import Counter


def shannon_entropy(text: str) -> float:
    """Average bits of information per character.

    English words score about 3; random hex about 4; random base64 about 5 or more
    (for strings of a few dozen characters). A high score on a value assigned to
    something named like a key is a strong hint it's a real credential.
    """
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum(c / n * math.log2(c / n) for c in counts.values())
