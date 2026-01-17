#src/risk_enhanced.py
from __future__ import annotations
from typing import List, Dict

RISK_WEIGHT = {"low": 1, "medium": 3, "high": 7}
SEVERITY_WEIGHT = {"low": 1, "medium": 5, "high": 10, "critical": 20}

def compute_overall_risk(steps, findings=None) -> dict:
    """Enhanced risk computation with breakdown and blockers"""
    
    # Calculate risk from checklist steps
    checklist_risk = sum(RISK_WEIGHT.get(s.risk, 3) for s in steps)
    max_checklist = len(steps) * 7  # Max if all steps were "high"
    checklist_score = min(100, int((checklist_risk / max_checklist * 100) if max_checklist > 0 else 0))
    
    # Calculate risk from findings
    findings_risk = 0
    if findings:
        findings_risk = sum(SEVERITY_WEIGHT.get(f.get('severity', 'medium'), 5) for f in findings)
        max_findings = len(findings) * 20
        findings_score = min(100, int((findings_risk / max_findings * 100) if max_findings > 0 else 0))
    else:
        findings_score = 0
    
    # Weighted combination (findings are more critical than theoretical checklist)
    overall_score = int(findings_score * 0.6 + checklist_score * 0.4)
    
    # Risk level determination
    if overall_score >= 70 or any(f.get('severity') == 'critical' for f in (findings or [])):
        level = "high"
    elif overall_score >= 40:
        level = "medium"
    else:
        level = "low"
    
    # Identify blockers (critical findings or prevent_bringup steps)
    blockers = []
    if findings:
        blockers.extend([
            f['summary'] for f in findings 
            if f.get('severity') == 'critical' or f.get('prevents_bringup', False)
        ])
    
    blocker_steps = [s for s in steps if getattr(s, 'prevents_bringup', False)]
    if blocker_steps:
        blockers.extend([
            f"[Step {s.sequence}] {s.title}" for s in blocker_steps
        ])
    
    # Categorize risks
    category_scores = {
        "power": 0,
        "connectivity": 0,
        "design": 0,
        "functional": 0
    }
    
    # Power issues from findings
    if findings:
        power_findings = [f for f in findings if 'power' in f.get('id', '').lower()]
        category_scores["power"] = min(100, len(power_findings) * 25)
        
        connectivity_findings = [f for f in findings if any(
            kw in f.get('id', '').lower() for kw in ['unattached', 'disconnect', 'floating', 'unnamed']
        )]
        category_scores["connectivity"] = min(100, len(connectivity_findings) * 15)
    
    # Add checklist step risks
    for step in steps:
        weight = RISK_WEIGHT.get(step.risk, 3)
        if step.category == "power":
            category_scores["power"] += weight * 5
        elif step.category in ["reset", "clock", "programming"]:
            category_scores["functional"] += weight * 5
        else:
            category_scores["design"] += weight * 3
    
    # Normalize category scores
    for cat in category_scores:
        category_scores[cat] = min(100, category_scores[cat])
    
    return {
        "score": overall_score,
        "level": level,
        "breakdown": {
            "power": category_scores["power"],
            "connectivity": category_scores["connectivity"],
            "design": category_scores["design"],
            "functional": category_scores["functional"]
        },
        "blockers": blockers if blockers else None,
        "can_attempt_bringup": len(blockers) == 0,
        "confidence": calculate_detection_confidence(findings or [])
    }

def calculate_detection_confidence(findings: List[Dict]) -> Dict[str, float]:
    """Estimate confidence in our detection algorithms"""
    
    confidence = {
        "power_nets": 0.95,  # High confidence in power net detection (regex based)
        "connectivity": 0.90 if findings else 0.95,  # Lower if we found issues
        "component_analysis": 0.70,  # Medium - heuristic based
        "timing_calculations": 0.85,  # High for simple circuits
        "overall": 0.85
    }
    
    # Reduce confidence if we detected many issues
    critical_count = sum(1 for f in findings if f.get('severity') == 'critical')
    if critical_count > 2:
        confidence["overall"] -= 0.15
    
    return confidence
