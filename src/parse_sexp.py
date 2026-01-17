from __future__ import annotations
from pathlib import Path
from sexpdata import loads, Symbol

def _normalize(obj):
    """
    Convert sexpdata's Symbol to plain string, and recursively normalize lists.
    """
    if isinstance(obj, Symbol):
        return str(obj)
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj

def parse_kicad_sch(path: str | Path) -> list:
    """
    Returns the full schematic as a normalized S-expression tree (nested Python lists/strings/numbers).
    """
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    tree = loads(text)
    return _normalize(tree)
