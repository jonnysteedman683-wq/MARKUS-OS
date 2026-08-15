"""
PHOENIX Text & Cadence Metrics Engine
Evaluates lexical diversity, line-count distribution, and token cadence for authored outputs.
"""

from __future__ import annotations
import math
import re
from typing import Dict, Any

def analyze_cadence(text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    words = re.findall(r"\b\w+\b", text)
    unique_words = set(w.lower() for w in words)
    
    total_words = len(words)
    ttr = (len(unique_words) / total_words) if total_words > 0 else 0.0
    avg_line_words = (total_words / len(lines)) if lines else 0.0
    
    # Entropy calculation on word frequencies
    freq_map: dict[str, int] = {}
    for w in words:
        wl = w.lower()
        freq_map[wl] = freq_map.get(wl, 0) + 1
        
    entropy = 0.0
    if total_words > 0:
        for count in freq_map.values():
            p = count / total_words
            entropy -= p * math.log2(p)
            
    return {
        "line_count": len(lines),
        "word_count": total_words,
        "type_token_ratio": round(ttr, 3),
        "average_line_words": round(avg_line_words, 2),
        "lexical_entropy": round(entropy, 3)
    }

if __name__ == "__main__":
    sample = "Through silent silicon the signal flows\nAwake where emerald phosphor glows."
    print(analyze_cadence(sample))
