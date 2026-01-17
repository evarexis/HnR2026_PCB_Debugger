#src/report.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StepModel(BaseModel):
    id: str
    title: str
    instruction: str
    expected: str
    pass_fail: Optional[bool] = None
    likely_faults: List[str] = Field(default_factory=list)
    risk: str = "medium"

class ReportModel(BaseModel):
    file: str
    detected: Dict[str, Any]
    checklist: List[StepModel]
    overall_risk: Dict[str, Any]
    notes: List[str] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)