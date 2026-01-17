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
            unnamed_count += 1
            name = f"NET_UNNAMED_{unnamed_count}"

        nets.append(Net(name=name, nodes=comp))

    return NetBuildResult(nets=nets, label_attached=label_attached, label_unattached=label_unattached)
