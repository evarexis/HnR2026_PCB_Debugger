#src/kicad_extract.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Point = Tuple[int, int]

@dataclass
class SchSymbol:
    ref: str
    value: str
    lib_id: str
    at: Optional[Point] = None
    properties: Dict[str, str] = field(default_factory=dict)
    pins: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class SchLabel:
    text: str
    at: Optional[Point] = None
    kind: str = "label"  # label, global_label, hierarchical_label

@dataclass
class SchWire:
    pts: List[Point]

@dataclass
class SchJunction:
    at: Point

@dataclass
class Schematic:
    symbols: List[SchSymbol] = field(default_factory=list)
    labels: List[SchLabel] = field(default_factory=list)
    wires: List[SchWire] = field(default_factory=list)
    junctions: List[SchJunction] = field(default_factory=list)

def _find_all(node: Any, head: str) -> List[Any]:
    out = []
    if isinstance(node, list) and node:
        if node[0] == head:
            out.append(node)
        for c in node[1:]:
            out.extend(_find_all(c, head))
    return out

def _get_kv(props: List[Any]) -> Dict[str, str]:
    """
    KiCad properties appear like: (property "Reference" "U1" (...))
    We'll extract property "X" "Y".
    """
    d = {}
    for p in props:
        if isinstance(p, list) and len(p) >= 3 and p[0] == "property":
            k = p[1].strip('"') if isinstance(p[1], str) else str(p[1])
            v = p[2].strip('"') if isinstance(p[2], str) else str(p[2])
            d[k] = v
    return d

def parse_schematic(tree: list) -> Schematic:
    sch = Schematic()

    # Symbols
    for sym in _find_all(tree, "symbol"):
        # Common pattern: (symbol (lib_id "...") (at x y ...) (property "Reference" "U1") ...)
        lib_id = ""
        at = None
        props = []
        for item in sym[1:]:
            if isinstance(item, list) and item:
                if item[0] == "lib_id" and len(item) >= 2:
                    lib_id = str(item[1]).strip('"')
                elif item[0] == "at" and len(item) >= 3:
                    at = (int(float(item[1])), int(float(item[2])))
                elif item[0] == "property":
                    props.append(item)

        prop_map = _get_kv(props)
        ref = prop_map.get("Reference", prop_map.get("Ref", ""))
        # If reference looks incomplete (e.g., "U"), try other common keys
        if ref and ref.isalpha():
           ref = f"{ref}?"

        value = prop_map.get("Value", prop_map.get("Val", ""))

        sch.symbols.append(
            SchSymbol(ref=ref, value=value, lib_id=lib_id, at=at, properties=prop_map)
        )

    # Labels (local/global)
    for head, kind in [("label", "label"), ("global_label", "global_label"), ("hierarchical_label", "hierarchical_label")]:
        for lab in _find_all(tree, head):
            text = ""
            at = None
            for item in lab[1:]:
                if isinstance(item, str) and text == "":
                    text = item.strip('"')
                if isinstance(item, list) and item and item[0] == "at" and len(item) >= 3:
                    at = (int(float(item[1])), int(float(item[2])))
            if text:
                sch.labels.append(SchLabel(text=text, at=at, kind=kind))

    # Wires
    for w in _find_all(tree, "wire"):
        pts = []
        for item in w[1:]:
            if isinstance(item, list) and item and item[0] == "pts":
                # (pts (xy x y) (xy x y) ...)
                for xy in item[1:]:
                    if isinstance(xy, list) and len(xy) >= 3 and xy[0] == "xy":
                        pts.append((int(float(xy[1])), int(float(xy[2]))))
        if pts:
            sch.wires.append(SchWire(pts=pts))

    # Junctions
    for j in _find_all(tree, "junction"):
        at = None
        for item in j[1:]:
            if isinstance(item, list) and item and item[0] == "at" and len(item) >= 3:
                at = (int(float(item[1])), int(float(item[2])))
        if at:
            sch.junctions.append(SchJunction(at=at))

    return sch
