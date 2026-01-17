# src/analysis_functions/power_analysis.py
"""
Modular power analysis functions for PCB debugging.
Each function is granular and can be called independently.
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """Standardized result from analysis functions"""
    function_name: str
    status: str  # "pass", "fail", "warning", "info"
    summary: str
    details: Dict[str, Any]
    issues: List[str]
    recommendations: List[str]
    severity: str  # "critical", "high", "medium", "low"
    prevents_bringup: bool


def verify_power_connectivity(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify that power nets are properly connected to IC power pins.
    
    Params:
        power_nets: List[str] - Names of power nets (e.g., ["VDD", "POWER"])
        ic_ref: str - IC reference (e.g., "U1")
        power_pins: List[str] - Power pin numbers
        gnd_pins: List[str] - Ground pin numbers
    """
    power_nets = params.get('power_nets', [])
    ic_ref = params.get('ic_ref')
    
    issues = []
    recommendations = []
    details = {}
    
    # Check if power net labels are connected
    unconnected_power = []
    for label in sch.labels:
        if label.text in power_nets:
            if label.at and label.at not in net_build.label_attached:
                unconnected_power.append(label.text)
                issues.append(f"Power net '{label.text}' label not connected to any wire at position ({label.at[0]}, {label.at[1]})")
    
    details['unconnected_power_labels'] = unconnected_power
    
    # Check if IC exists
    ic = next((s for s in sch.symbols if s.ref == ic_ref), None)
    if not ic:
        issues.append(f"IC {ic_ref} not found in schematic")
        status = "fail"
        severity = "critical"
    elif unconnected_power:
        status = "fail"
        severity = "critical"
        recommendations.append(f"Connect {', '.join(unconnected_power)} labels to wires")
        recommendations.append(f"Verify continuity from power source to {ic_ref}")
    else:
        status = "pass"
        severity = "low"
        details['power_nets_connected'] = power_nets
    
    # Check for nearby decoupling caps
    if ic and ic.at:
        nearby_caps = [
            s for s in sch.symbols 
            if s.ref.startswith('C') and s.at and
            abs(s.at[0] - ic.at[0]) < 50 and abs(s.at[1] - ic.at[1]) < 50
        ]
        details['nearby_decoupling_caps'] = [c.ref for c in nearby_caps]
        
        if not nearby_caps:
            recommendations.append(f"Add decoupling capacitor near {ic_ref} power pins")
            if status == "pass":
                status = "warning"
    
    summary = f"Power connectivity check for {ic_ref}: {status.upper()}"
    if issues:
        summary += f" - {len(issues)} issue(s) found"
    
    return AnalysisResult(
        function_name="verify_power_connectivity",
        status=status,
        summary=summary,
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_power_rail_routing(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Analyze power rail routing and distribution.
    
    Params:
        power_nets: List[str] - Power net names
        min_node_count: int - Minimum nodes for a valid power net
    """
    power_nets = params.get('power_nets', [])
    min_nodes = params.get('min_node_count', 2)
    
    issues = []
    recommendations = []
    details = {}
    
    for power_net_name in power_nets:
        # Find the net
        net = next((n for n in net_build.nets if n.name == power_net_name), None)
        
        if not net:
            issues.append(f"Power net '{power_net_name}' not found in netlist")
            continue
        
        node_count = len(net.nodes)
        details[power_net_name] = {
            'node_count': node_count,
            'is_valid': node_count >= min_nodes
        }
        
        if node_count < min_nodes:
            issues.append(f"Power net '{power_net_name}' has only {node_count} node(s) - may be disconnected")
            recommendations.append(f"Verify {power_net_name} connects to power source and all consumers")
    
    status = "fail" if issues else "pass"
    severity = "critical" if issues else "low"
    
    return AnalysisResult(
        function_name="check_power_rail_routing",
        status=status,
        summary=f"Power rail routing: {len(power_nets)} nets analyzed, {len(issues)} issues",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def analyze_decoupling_capacitors(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check for proper decoupling capacitors near ICs.
    
    Params:
        ic_refs: List[str] - ICs to check (e.g., ["U1", "U2"])
        proximity_threshold: int - Max distance for "nearby" cap
    """
    ic_refs = params.get('ic_refs', [])
    threshold = params.get('proximity_threshold', 50)
    
    issues = []
    recommendations = []
    details = {}
    
    for ic_ref in ic_refs:
        ic = next((s for s in sch.symbols if s.ref == ic_ref), None)
        
        if not ic or not ic.at:
            continue
        
        # Find nearby capacitors
        nearby_caps = []
        for sym in sch.symbols:
            if not sym.ref.startswith('C') or not sym.at:
                continue
            
            distance = ((ic.at[0] - sym.at[0])**2 + (ic.at[1] - sym.at[1])**2)**0.5
            if distance < threshold:
                nearby_caps.append({
                    'ref': sym.ref,
                    'value': sym.value,
                    'distance': round(distance, 1)
                })
        
        details[ic_ref] = {
            'nearby_caps': nearby_caps,
            'cap_count': len(nearby_caps)
        }
        
        if not nearby_caps:
            issues.append(f"No decoupling capacitor found near {ic_ref}")
            recommendations.append(f"Add 0.1µF ceramic cap close to {ic_ref} power pins")
        elif len(nearby_caps) == 1:
            recommendations.append(f"Consider adding bulk capacitor (10µF) in addition to {nearby_caps[0]['ref']}")
    
    status = "warning" if issues else "pass"
    severity = "medium" if issues else "low"
    
    return AnalysisResult(
        function_name="analyze_decoupling_capacitors",
        status=status,
        summary=f"Decoupling capacitor check: {len(ic_refs)} ICs analyzed",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def verify_voltage_regulator_circuit(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify voltage regulator circuit configuration.
    
    Params:
        regulator_ref: str - Regulator IC reference
        input_cap_required: bool - Whether input cap is required
        output_cap_required: bool - Whether output cap is required
    """
    reg_ref = params.get('regulator_ref')
    need_input_cap = params.get('input_cap_required', True)
    need_output_cap = params.get('output_cap_required', True)
    
    issues = []
    recommendations = []
    details = {}
    
    regulator = next((s for s in sch.symbols if s.ref == reg_ref), None)
    
    if not regulator:
        issues.append(f"Regulator {reg_ref} not found")
        status = "fail"
        severity = "critical"
    else:
        # This is simplified - real implementation would check actual pin connections
        status = "pass"
        severity = "low"
        details['regulator_found'] = True
        
        if need_input_cap or need_output_cap:
            recommendations.append(f"Verify input/output capacitors per {reg_ref} datasheet")
    
    return AnalysisResult(
        function_name="verify_voltage_regulator_circuit",
        status=status,
        summary=f"Voltage regulator {reg_ref} circuit check",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_power_sequencing(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check if power sequencing is properly implemented (for multi-rail systems).
    
    Params:
        power_rails: List[str] - Ordered list of power rails
        sequencing_required: bool - Whether sequencing is critical
    """
    rails = params.get('power_rails', [])
    required = params.get('sequencing_required', False)
    
    issues = []
    recommendations = []
    details = {'power_rails': rails}
    
    if required and len(rails) > 1:
        recommendations.append("Verify power-on sequence matches IC requirements")
        recommendations.append("Consider adding enable signals or sequencing circuit")
    
    status = "info"
    severity = "low"
    
    return AnalysisResult(
        function_name="check_power_sequencing",
        status=status,
        summary=f"Power sequencing check: {len(rails)} rails",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )