from __future__ import annotations
from typing import List

RISK_WEIGHT = {"low": 1, "medium": 3, "high": 7}

def compute_overall_risk(steps) -> dict:
    total = sum(RISK_WEIGHT.get(s.risk, 3) for s in steps)
    # Normalize to 0..100-ish
    score = min(100, int(total * 5))

    if score >= 70:
        level = "high"
    elif score >= 35:
        level = "medium"
    else:
        level = "low"

    return {"score": score, "level": level}
