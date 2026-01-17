#main.py
from __future__ import annotations
import json
import sys
from pathlib import Path

from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors
from src.checklist import generate_checklist
from src.risk import compute_overall_risk
from src.findings import analyze_findings
from src.component_analysis import analyze_component_interconnections, analyze_555_timer
from src.report import ReportModel, StepModel

def generate_visualization_data(sch, net_build, detected):
    """Generate data for visual debugging aids"""
    
    # Power distribution tree
    power_tree = {}
    for net in net_build.nets:
        if net.name in detected.power_nets or 'GND' in net.name.upper():
            # Find components connected to this net
            connected_comps = []
            for sym in sch.symbols:
                if '?' not in sym.ref:
                    connected_comps.append(sym.ref)
            if connected_comps:
                power_tree[net.name] = connected_comps[:5]  # Limit for readability
    
    # Signal flow (simplified)
    signal_flow = []
    for label in sch.labels:
        if label.at and label.at in net_build.label_attached:
            signal_flow.append(f"{label.text} → [connected]")
        else:
            signal_flow.append(f"{label.text} → [FLOATING!]")
    
    return {
        "power_tree": power_tree,
        "signal_flow": signal_flow[:10],  # Limit output
        "net_stats": {
            "total_nets": len(net_build.nets),
            "labeled_nets": len([n for n in net_build.nets if not n.name.startswith("NET_UNNAMED")]),
            "unnamed_nets": len([n for n in net_build.nets if n.name.startswith("NET_UNNAMED")])
        }
    }

def generate_test_points(detected, sch, net_build):
    """Recommend test point locations"""
    recommendations = []
    
    # Power rails
    for net in detected.power_nets:
        if 'GND' not in net.upper():
            recommendations.append({
                "net": net,
                "why": f"Critical power rail - verify voltage before IC power-on",
                "measurement": "DC voltage relative to GND"
            })
    
    # Output signals
    for label in sch.labels:
        if 'OUT' in label.text.upper():
            recommendations.append({
                "net": label.text,
                "why": "Primary output - needs oscilloscope probe for waveform",
                "measurement": "AC waveform / frequency"
            })
    
    # Clock signals
    for net in detected.clock_nets:
        recommendations.append({
            "net": net,
            "why": "Clock signal - critical for MCU operation",
            "measurement": "Frequency and stability"
        })
    
    return recommendations

def generate_scope_config(detected, topology):
    """Auto-generate oscilloscope setup for circuit"""
    
    # Check if this is a 555 circuit
    is_555 = False
    freq_data = None
    
    for ref, comp in topology.component_map.items():
        if '555' in comp.lib_id.lower():
            is_555 = True
            # Check if we calculated frequency
            if hasattr(comp, 'extra_analysis') and comp.extra_analysis:
                freq_data = comp.extra_analysis.get('frequency_calc')
            break
    
    if not is_555:
        return None
    
    config = {
        "circuit_type": "555 timer",
        "channels": [
            {
                "ch": 1,
                "probe": "U1 pin 3 (OUTPUT)",
                "scale": "5V/div",
                "coupling": "DC",
                "label": "OUTPUT"
            }
        ],
        "trigger": {
            "channel": 1,
            "edge": "rising",
            "level": "2.5V"
        }
    }
    
    if freq_data:
        period_ms = freq_data['period_ms']
        # Set timebase to show 2-3 cycles
        if period_ms < 1:
            timebase = "500µs/div"
        elif period_ms < 10:
            timebase = f"{int(period_ms * 0.4)}ms/div"
        elif period_ms < 100:
            timebase = f"{int(period_ms * 0.3)}ms/div"
        else:
            timebase = f"{int(period_ms * 0.2)}ms/div"
        
        config["timebase"] = timebase
        config["expected_waveform"] = {
            "frequency_hz": freq_data['frequency_hz'],
            "period_ms": freq_data['period_ms'],
            "duty_cycle_pct": freq_data['duty_cycle_pct']
        }
        
        # Add timing capacitor channel if useful
        if period_ms > 5:  # Only if slow enough to see
            config["channels"].append({
                "ch": 2,
                "probe": "U1 pin 2/6 (TIMING CAP)",
                "scale": "2V/div",
                "coupling": "DC",
                "label": "TIMING"
            })
    else:
        config["timebase"] = "1ms/div"  # Default
    
    return config

def run(path: str) -> dict:
    """Enhanced main entry point with full analysis"""
    tree = parse_kicad_sch(path)
    sch = parse_schematic(tree)
    net_build = build_nets(sch, label_tolerance=2)
    detected = run_detectors(sch, net_build.nets)
    
    # Component-level analysis
    topology = analyze_component_interconnections(sch, net_build, detected.power_nets)
    
    # Special analysis for specific circuit types
    for ref, comp in topology.component_map.items():
        if '555' in comp.lib_id.lower():
            comp.extra_analysis = analyze_555_timer(comp, sch, net_build)
    
    # Generate checklist with topology info
    steps = generate_checklist(detected, topology, sch)
    
    # Enhanced findings with schematic context
    findings = analyze_findings(net_build, sch, detected.power_nets)
    
    # Risk computation with findings
    overall = compute_overall_risk(steps, [f.__dict__ for f in findings])
    
    # Visualization and recommendations
    visualization = generate_visualization_data(sch, net_build, detected)
    test_points = generate_test_points(detected, sch, net_build)
    scope_config = generate_scope_config(detected, topology)
    
    # Build report
    report = {
        "file": str(path),
        "detected": {
            "power_nets": detected.power_nets,
            "reset_nets": detected.reset_nets,
            "clock_nets": detected.clock_nets,
            "mcu_symbols": detected.mcu_symbols,
            "clock_sources": detected.clock_sources,
            "debug_ifaces": detected.debug_ifaces,
        },
        "checklist": [
            {
                "id": s.id,
                "sequence": s.sequence,
                "category": s.category,
                "title": s.title,
                "instruction": s.instruction,
                "expected": s.expected,
                "component": s.component,
                "pins": s.pins if s.pins else [],
                "nets": s.nets if s.nets else [],
                "pass_fail": s.pass_fail,
                "likely_faults": s.likely_faults,
                "fix_suggestions": s.fix_suggestions if s.fix_suggestions else [],
                "risk": s.risk,
                "prevents_bringup": s.prevents_bringup,
                "measurement": s.measurement.__dict__ if s.measurement else None,
                "automation_ready": s.automation_ready
            }
            for s in steps
        ],
        "overall_risk": overall,
        "notes": detected.notes,
        "findings": [f.__dict__ for f in findings],
        "visualization": visualization,
        "recommended_test_points": test_points,
        "scope_config": scope_config,
        "topology": {
            "total_components": len(topology.component_map),
            "ics": len([r for r in topology.component_map.keys() if r.startswith('U')]),
            "missing_decoupling_caps": topology.missing_decoupling,
            "power_distribution": len(topology.power_tree)
        }
    }
    
    return report

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main_enhanced.py path/to/file.kicad_sch", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    out = run(path)
    print(json.dumps(out, indent=2))