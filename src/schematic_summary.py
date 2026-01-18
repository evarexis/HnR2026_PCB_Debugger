# src/schematic_summary.py
"""
Generate a comprehensive but concise summary of schematic for LLM analysis.
Includes all information useful for debugging while removing noise.
"""
from __future__ import annotations
from typing import Dict, List, Any
from src.kicad_extract import Schematic
from src.netlist_build import NetBuildResult


def generate_schematic_summary(sch: Schematic, net_build: NetBuildResult) -> Dict[str, Any]:
    """
    Create a structured summary containing all debugging-relevant information.
    Removes UIDs and redundant positioning but keeps connectivity data.
    """
    
    # 1. Component inventory with values and types
    components = []
    for sym in sch.symbols:
        if '?' in sym.ref:
            continue
        
        comp_data = {
            "ref": sym.ref,
            "value": sym.value,
            "lib_id": sym.lib_id,
            "type": _classify_component(sym.ref, sym.lib_id)
        }
      
        if sym.at:
            comp_data["position"] = {"x": sym.at[0], "y": sym.at[1]}
        
        components.append(comp_data)
    
    # 2. Net connectivity map (critical for finding broken connections)
    nets_info = []
    for net in net_build.nets:
        net_info = {
            "name": net.name,
            "node_count": len(net.nodes),
            "is_unnamed": net.name.startswith("NET_UNNAMED_")
        }
        
        if net.nodes:
            xs = [n[0] for n in net.nodes]
            ys = [n[1] for n in net.nodes]
            net_info["extent"] = {
                "x_range": [min(xs), max(xs)],
                "y_range": [min(ys), max(ys)]
            }
        
        nets_info.append(net_info)
    
    # 3. Label connectivity status (critical for finding floating labels)
    labels_info = []
    for label in sch.labels:
        label_info = {
            "text": label.text,
            "type": label.kind,
            "connected": label.at in net_build.label_attached if label.at else False,
            "position": {"x": label.at[0], "y": label.at[1]} if label.at else None
        }
        
        if label.at and label.at in net_build.label_attached:
            label_info["net_name"] = net_build.label_attached[label.at]
        
        labels_info.append(label_info)
    
    # 4. Wire topology (for detecting broken traces)
    wire_segments = []
    for wire in sch.wires:
        if len(wire.pts) >= 2:
            wire_segments.append({
                "start": {"x": wire.pts[0][0], "y": wire.pts[0][1]},
                "end": {"x": wire.pts[-1][0], "y": wire.pts[-1][1]},
                "segment_count": len(wire.pts) - 1
            })
    
    # 5. Junction points (important for multi-way connections)
    junctions = [
        {"x": j.at[0], "y": j.at[1]} 
        for j in sch.junctions
    ]
    
    # 6. Component proximity map (for finding decoupling caps, etc)
    proximity_map = _build_proximity_map(components)
    
    # 7. Connectivity issues detected by netlist builder
    connectivity_issues = {
        "unattached_labels": [
            {"label": text, "position": {"x": pos[0], "y": pos[1]}}
            for text, pos in net_build.label_unattached
        ],
        "unnamed_net_count": len([n for n in net_build.nets if n.name.startswith("NET_UNNAMED_")]),
        "single_node_nets": [
            n.name for n in net_build.nets if len(n.nodes) == 1
        ]
    }
    
    # 8. Circuit statistics
    statistics = {
        "total_components": len(components),
        "total_nets": len(nets_info),
        "total_labels": len(labels_info),
        "total_wires": len(wire_segments),
        "total_junctions": len(junctions),
        "component_breakdown": _count_component_types(components)
    }
    
    return {
        "components": components,
        "nets": nets_info,
        "labels": labels_info,
        "wires": wire_segments,
        "junctions": junctions,
        "proximity_map": proximity_map,
        "connectivity_issues": connectivity_issues,
        "statistics": statistics
    }


def _classify_component(ref: str, lib_id: str) -> str:
    """Classify component type from reference and library ID"""
    ref_upper = ref.upper()
    lib_lower = lib_id.lower()
    
    if ref_upper.startswith('U'):
        if any(kw in lib_lower for kw in ['555', 'timer']):
            return "timer_ic"
        elif any(kw in lib_lower for kw in ['stm32', 'esp32', 'atmega', 'pic', 'mcu']):
            return "microcontroller"
        elif any(kw in lib_lower for kw in ['regulator', 'ldo']):
            return "voltage_regulator"
        elif any(kw in lib_lower for kw in ['opamp', 'amplifier']):
            return "opamp"
        else:
            return "ic"
    elif ref_upper.startswith('R'):
        return "resistor"
    elif ref_upper.startswith('C'):
        return "capacitor"
    elif ref_upper.startswith('L'):
        return "inductor"
    elif ref_upper.startswith('D'):
        return "diode"
    elif ref_upper.startswith('Q'):
        return "transistor"
    elif ref_upper.startswith(('Y', 'X')):
        return "crystal_oscillator"
    elif ref_upper.startswith('J'):
        return "connector"
    elif ref_upper.startswith('SW'):
        return "switch"
    elif ref_upper.startswith('LED'):
        return "led"
    elif ref_upper.startswith('TP'):
        return "test_point"
    else:
        return "unknown"


def _build_proximity_map(components: List[Dict]) -> Dict[str, List[str]]:
    """
    Build map of nearby components (useful for finding decoupling caps near ICs).
    Distance threshold: 50 units
    """
    proximity_map = {}
    PROXIMITY_THRESHOLD = 50
    
    for comp in components:
        if 'position' not in comp:
            continue
        
        nearby = []
        comp_x, comp_y = comp['position']['x'], comp['position']['y']
        
        for other in components:
            if other['ref'] == comp['ref'] or 'position' not in other:
                continue
            
            other_x, other_y = other['position']['x'], other['position']['y']
            distance = ((comp_x - other_x)**2 + (comp_y - comp_y)**2)**0.5
            
            if distance < PROXIMITY_THRESHOLD:
                nearby.append(other['ref'])
        
        if nearby:
            proximity_map[comp['ref']] = nearby
    
    return proximity_map


def _count_component_types(components: List[Dict]) -> Dict[str, int]:
    """Count components by type"""
    counts = {}
    for comp in components:
        comp_type = comp.get('type', 'unknown')
        counts[comp_type] = counts.get(comp_type, 0) + 1
    return counts