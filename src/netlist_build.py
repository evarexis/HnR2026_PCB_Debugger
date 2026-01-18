#src/netlist_build.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from src.kicad_extract import Schematic, Point


@dataclass
class Net:
    name: str
    nodes: Set[Point]

@dataclass
class NetBuildResult:
    nets: List[Net]
    label_attached: Dict[Tuple[int,int], str]    # label position -> net name
    label_unattached: List[Tuple[str, Tuple[int,int]]]  # (text, pos)


def _neighbors_from_wires(wires) -> Dict[Point, Set[Point]]:
    g: Dict[Point, Set[Point]] = {}
    def add(a: Point, b: Point):
        g.setdefault(a, set()).add(b)
        g.setdefault(b, set()).add(a)

    for w in wires:
        # connect consecutive points
        pts = w.pts
        for i in range(len(pts) - 1):
            add(pts[i], pts[i+1])
    return g

def _nearest_node(point: Point, nodes: Set[Point], tol: int = 0) -> Point | None:
    # tolerance is optional if labels aren't exactly on endpoints
    x, y = point
    for nx, ny in nodes:
        if abs(nx - x) <= tol and abs(ny - y) <= tol:
            return (nx, ny)
    return None

def build_nets(sch: Schematic, label_tolerance: int = 0) -> NetBuildResult:
    graph = _neighbors_from_wires(sch.wires)
    all_nodes = set(graph.keys())

    # Assign label->node mapping
    node_to_name: Dict[Point, str] = {}
    label_attached: Dict[Tuple[int, int], str] = {}
    label_unattached: List[Tuple[str, Tuple[int, int]]] = []

    for lab in sch.labels:
        if not lab.at:
            continue
        n = _nearest_node(lab.at, all_nodes, tol=label_tolerance)
        if n:
            # Prefer global labels over local labels if conflict
            existing = node_to_name.get(n)
            if existing is None or lab.kind == "global_label":
                node_to_name[n] = lab.text
            label_attached[lab.at] = lab.text
        else:
            label_unattached.append((lab.text, lab.at))
    

    # Flood fill connected components
    visited: Set[Point] = set()
    nets: List[Net] = []
    unnamed_count = 0

    for start in all_nodes:
        if start in visited:
            continue
        stack = [start]
        comp: Set[Point] = set()
        names: Set[str] = set()

        while stack:
            u = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            comp.add(u)
            if u in node_to_name:
                names.add(node_to_name[u])
            for v in graph.get(u, ()):
                if v not in visited:
                    stack.append(v)

        if names:
            # If multiple labels, choose a stable "best" name
            name = sorted(names, key=lambda s: (len(s), s))[0]
        else:
            # Try to infer name from connected component pins
            pin_names = []
            
            # This is inefficient to do inside the loop, but robust for now
            # In a real system, we'd pre-calculate pin positions map
            for sym in sch.symbols:
                if not sym.at: continue
                # Simple transform: assume rot=0 for now (or minimal rot)
                # Correct full transform requires parsing transform matrix
                sx, sy = sym.at
                
                for pin in sym.pins:
                    if "at" not in pin: continue
                    px, py = pin["at"]
                    # Absolute pos: simplified (ignores rotation)
                    abs_x, abs_y = sx + px, sy + py
                    
                    # DEBUG: Print for critical components
                    if sym.ref.startswith('U') or 'SDA' in str(pin.get('name')):
                       print(f"DEBUG: {sym.ref} Pin {pin.get('name')} Rel({px},{py}) Abs({abs_x:.2f},{abs_y:.2f})")
                    
                    # Check if this point is in the net (with tolerance)
                    # Use _nearest_node which is already defined
                    # We need to check if (abs_x, abs_y) is in 'comp' set of nodes
                    
                    # Optimization: check exact match first
                    if (abs_x, abs_y) in comp:
                        if "name" in pin: pin_names.append(pin["name"])
                    else:
                        # Check close proximity (tolerance 2 units)
                        # KiCad units might be imperfect in float
                        matched = False
                        for cx, cy in comp:
                            if abs(cx - abs_x) <= 2.54 and abs(cy - abs_y) <= 2.54: # Increased tolerance to 2.54 (1 grid unit typically 1.27 or 2.54)
                                if "name" in pin: 
                                    pin_names.append(pin["name"])
                                    print(f"DEBUG: Match {sym.ref}.{pin['name']} to net node ({cx},{cy})")
                                matched = True
                                break
                        
                        # DEBUG
                        if not matched and (sym.ref.startswith('U') or 'SDA' in str(pin.get('name'))):
                           print(f"DEBUGGING NO MATCH: {sym.ref}.{pin.get('name')} at ({abs_x:.2f},{abs_y:.2f})")
                            
            # Filter and choose best pin name
            # Priority: Specific signals > Generic
            special_names = [n for n in pin_names if any(k in n.upper() for k in ['SDA', 'SCL', 'RST', 'BOOT', 'SWD', 'CLK', 'RX', 'TX', 'NRST'])]
            
            if special_names:
                name = sorted(special_names)[0] # Pick lexicographically first special name
            elif pin_names:
                # Avoid very generic names if possible, but better than UNNAMED
                # Maybe fallback to "Net-(Ref-PinName)"
                name = f"Net-{pin_names[0]}"
            else:
                unnamed_count += 1
                name = f"NET_UNNAMED_{unnamed_count}"

        nets.append(Net(name=name, nodes=comp))

    return NetBuildResult(nets=nets, label_attached=label_attached, label_unattached=label_unattached)
