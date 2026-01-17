#!/usr/bin/env python3
"""
Bridge module between backend analysis and UI
Converts backend report format to UI-compatible format
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Any

# Import backend analysis
from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors
from src.schematic_summary import generate_schematic_summary
from src.llm_analysis import LLMAnalyzer, LLMProvider
from src.checklist import generate_checklist
from src.component_analysis import analyze_component_interconnections
from src.findings import analyze_findings
from src.risk import compute_overall_risk


def run(schematic_path: str) -> Dict[str, Any]:
    """
    Main entry point for standalone UI.
    Analyzes schematic and returns UI-compatible report.
    
    Args:
        schematic_path: Path to .kicad_sch file
    
    Returns:
        Dictionary with report data for UI
    """
    print(f"[Bridge] Analyzing: {schematic_path}")
    
    print("[Bridge] Step 1: Parsing schematic...")
    tree = parse_kicad_sch(schematic_path)
    sch = parse_schematic(tree)
    
    print("[Bridge] Step 2: Building netlist...")
    net_build = build_nets(sch, label_tolerance=2)
    
    print("[Bridge] Step 3: Running detectors...")
    detected = run_detectors(sch, net_build.nets)
    
    print("[Bridge] Step 4: Analyzing component topology...")
    topology = analyze_component_interconnections(
        sch, 
        net_build, 
        detected.power_nets
    )
    
    print("[Bridge] Step 5: Generating bring-up checklist...")
    checklist_steps = generate_checklist(detected, topology, sch)
    
    print("[Bridge] Step 6: Analyzing design issues...")
    findings_list = analyze_findings(net_build, sch, detected.power_nets)
    
    print("[Bridge] Step 7: Computing overall risk...")
    findings_dicts = []
    for finding in findings_list:
        findings_dicts.append({
            'id': finding.id,
            'severity': finding.severity,
            'summary': finding.summary,
            'prevents_bringup': finding.prevents_bringup
        })
    
    overall_risk = compute_overall_risk(checklist_steps, findings_dicts)
    
    print("[Bridge] Step 8: Building final report...")
    report = build_ui_report(
        schematic_path=schematic_path,
        detected=detected,
        checklist_steps=checklist_steps,
        findings_list=findings_list,
        topology=topology,
        overall_risk=overall_risk
    )
    
    print(f"[Bridge] Analysis complete! Risk: {overall_risk['level']}")
    return report


def build_ui_report(
    schematic_path: str,
    detected,
    checklist_steps,
    findings_list,
    topology,
    overall_risk: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build UI-compatible report structure.
    
    The UI expects this structure:
    - file: str
    - detected: dict with power_nets, mcu_symbols, etc.
    - checklist: list of step dicts
    - findings: list of finding dicts
    - topology: dict with component info
    - overall_risk: dict with score, level, etc.
    - recommended_test_points: list (optional)
    - scope_config: dict (optional)
    - notes: list of strings
    """
    
    checklist_dicts = []
    for step in checklist_steps:
        step_dict = {
            'id': step.id,
            'sequence': step.sequence,
            'category': step.category,
            'title': step.title,
            'instruction': step.instruction,
            'expected': step.expected,
            'component': step.component,
            'pins': step.pins,
            'nets': step.nets,
            'likely_faults': step.likely_faults,
            'fix_suggestions': step.fix_suggestions if hasattr(step, 'fix_suggestions') else [],
            'risk': step.risk,
            'prevents_bringup': step.prevents_bringup
        }
        checklist_dicts.append(step_dict)
    
    findings_dicts = []
    for finding in findings_list:
        finding_dict = {
            'id': finding.id,
            'severity': finding.severity,
            'summary': finding.summary,
            'why': finding.why,
            'evidence': finding.evidence,
            'fix_suggestion': finding.fix_suggestion,
            'prevents_bringup': finding.prevents_bringup,
            'schematic_location': finding.schematic_location
        }
        findings_dicts.append(finding_dict)
    
    detected_dict = {
        'power_nets': detected.power_nets,
        'mcu_symbols': detected.mcu_symbols,
        'clock_sources': detected.clock_sources,
        'reset_nets': detected.reset_nets,
        'clock_nets': detected.clock_nets,
        'debug_ifaces': detected.debug_ifaces
    }
    
    topology_dict = {
        'total_components': len(topology.component_map),
        'ics': len([ref for ref in topology.component_map.keys() if ref.startswith('U')]),
        'missing_decoupling_caps': topology.missing_decoupling,
        'power_tree': topology.power_tree
    }
    
    test_points = generate_test_points(detected, topology)
    
    scope_config = generate_scope_config(detected, checklist_steps)
    
    report = {
        'file': str(schematic_path),
        'detected': detected_dict,
        'checklist': checklist_dicts,
        'findings': findings_dicts,
        'topology': topology_dict,
        'overall_risk': overall_risk,
        'recommended_test_points': test_points,
        'scope_config': scope_config,
        'notes': detected.notes
    }
    
    return report


def generate_test_points(detected, topology) -> list:
    """Generate recommended test points"""
    test_points = []
    
    for power_net in detected.power_nets:
        if 'GND' not in power_net.upper():
            test_points.append({
                'net': power_net,
                'why': 'Power rail voltage measurement',
                'measurement': f'DC voltage relative to GND (expected: per design spec)'
            })
    
    for clock_ref in detected.clock_sources:
        test_points.append({
            'net': f'{clock_ref} output',
            'why': 'Clock signal verification',
            'measurement': 'Frequency and waveform quality'
        })
    
    for reset_net in detected.reset_nets:
        test_points.append({
            'net': reset_net,
            'why': 'Reset signal behavior during power-up',
            'measurement': 'Pulse timing and voltage levels'
        })
    
    return test_points


def generate_scope_config(detected, checklist_steps) -> dict:
    """Generate oscilloscope configuration recommendations"""
    
    has_mcu = bool(detected.mcu_symbols)
    has_clock = bool(detected.clock_sources)
    
    if not (has_mcu or has_clock):
        return None
    
    channels = []
    
    if has_clock:
        channels.append({
            'ch': 1,
            'probe': f'{detected.clock_sources[0]} output' if detected.clock_sources else 'Clock output',
            'scale': '2V/div',
            'coupling': 'DC'
        })
    

    if detected.reset_nets:
        channels.append({
            'ch': 2,
            'probe': detected.reset_nets[0],
            'scale': '2V/div',
            'coupling': 'DC'
        })
    
    if detected.power_nets:
        power_rail = next((p for p in detected.power_nets if 'GND' not in p.upper()), None)
        if power_rail:
            channels.append({
                'ch': 3,
                'probe': power_rail,
                'scale': '1V/div',
                'coupling': 'DC'
            })
    
    config = {
        'circuit_type': 'microcontroller' if has_mcu else 'timer_circuit',
        'timebase': '10us/div' if has_clock else '100us/div',
        'channels': channels
    }
    
    if has_clock:
        config['expected_waveform'] = {
            'frequency_hz': 8000000,  
            'period_ms': 0.000125,
            'duty_cycle_pct': 50
        }
    
    return config


def run_full_analysis(schematic_path: str, use_llm: bool = False) -> Dict[str, Any]:
    """
    Full analysis with optional LLM integration.
    
    Args:
        schematic_path: Path to schematic file
        use_llm: Whether to use LLM for enhanced analysis
    
    Returns:
        Detailed analysis report
    """
    if use_llm:
        print("[Bridge] LLM analysis requested but running heuristic for now...")
        # TODO: Integrate LLM analysis if needed
    
    return run(schematic_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bridge.py <schematic.kicad_sch>")
        sys.exit(1)
    
    sch_path = sys.argv[1]
    report = run(sch_path)
    
    import json
    print("\n" + "="*80)
    print("ANALYSIS REPORT")
    print("="*80)
    print(json.dumps(report, indent=2))