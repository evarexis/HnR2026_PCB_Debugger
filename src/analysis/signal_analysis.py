# src/analysis_functions/signal_analysis.py
"""
Signal integrity and connectivity analysis functions.
"""
from __future__ import annotations
from typing import Dict, List, Any
from .power_analysis import AnalysisResult


def _is_pin_connected(at, net_build) -> bool:
    """Check if a coordinate is connected to any net node."""
    if not at: return False
    x, y = at
    # Tolerance for connection (2.54 units = 100 mil)
    TOLERANCE = 3.0 
    for net in net_build.nets:
        for nx, ny in net.nodes:
            if abs(x - nx) <= TOLERANCE and abs(y - ny) <= TOLERANCE:
                return True
    return False

def check_floating_pins(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check for floating pins that should be tied high or low.
    """
    ic_ref = params.get('ic_ref')
    critical_pins = params.get('critical_pins', [])
    exclude_pins = params.get('exclude_pins', ["NC", "NB"])
    expected_state = params.get('expected_state', 'HIGH')
    
    issues = []
    recommendations = []
    details = {}
    
    ic = next((s for s in sch.symbols if s.ref == ic_ref), None)
    
    if not ic:
        issues.append(f"IC {ic_ref} not found")
        status = "fail"
        severity = "critical"
    else:
        details['ic'] = ic_ref
        details['checked_pins'] = []
        
        floating = []
        
        # Determine absolute position of IC
        if not ic.at:
            issues.append(f"IC {ic_ref} has no position data")
            status = "fail"
        else:
            ix, iy = ic.at
            
            # Check pins
            for pin in ic.pins:
                p_name = pin.get('name', '??')
                p_num = pin.get('number', '?')
                
                # Filter info
                if p_name in exclude_pins or p_num in exclude_pins:
                    continue
                if critical_pins and p_num not in critical_pins:
                    continue
                
                # Check connection
                if 'at' in pin:
                    px, py = pin['at']
                    abs_at = (ix + px, iy + py)
                    
                    if not _is_pin_connected(abs_at, net_build):
                        floating.append(f"{p_num}({p_name})")
                        
            if floating:
                status = "warning"
                severity = "medium"
                issues.append(f"Pins floating: {', '.join(floating)}")
                recommendations.append(f"Verify {ic_ref} pins {', '.join(floating)} are connected")
            else:
                status = "pass"
                severity = "low"

    return AnalysisResult(
        function_name="check_floating_pins",
        status=status,
        summary=f"Floating pin check for {ic_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )



def verify_pull_up_pull_down(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify pull-up/pull-down resistors on appropriate nets.
    
    Params:
        nets: List[str] - Net names to check
        pull_type: str - "up" or "down"
        resistor_range: Tuple[float, float] - Valid resistance range in ohms
    """
    nets_to_check = params.get('nets', [])
    pull_type = params.get('pull_type', 'up')
    res_range = params.get('resistor_range', (1000, 100000))  # 1k to 100k default
    
    issues = []
    recommendations = []
    details = {}
    
    for net_name in nets_to_check:
        # Find resistors connected to this net
        # This is simplified - real implementation would trace actual connections
        details[net_name] = {
            'pull_type_required': pull_type,
            'resistance_range': res_range
        }
        
        recommendations.append(f"Verify {net_name} has {res_range[0]/1000:.1f}k-{res_range[1]/1000:.0f}k pull-{pull_type} resistor")
    
    status = "info"
    severity = "low"
    
    return AnalysisResult(
        function_name="verify_pull_up_pull_down",
        status=status,
        summary=f"Pull-{pull_type} verification: {len(nets_to_check)} nets",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def trace_signal_path(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Trace a signal path from source to destination.
    
    Params:
        net_name: str - Net to trace
        expected_source: str - Expected source component
        expected_destinations: List[str] - Expected destination components
    """
    net_name = params.get('net_name')
    source = params.get('expected_source')
    destinations = params.get('expected_destinations', [])
    
    issues = []
    recommendations = []
    details = {}
    
    net = next((n for n in net_build.nets if n.name == net_name), None)
    
    if not net:
        issues.append(f"Net {net_name} not found in netlist")
        status = "fail"
        severity = "high"
    else:
        details['net'] = net_name
        details['node_count'] = len(net.nodes)
        
        if len(net.nodes) == 1:
            issues.append(f"Net {net_name} has only one connection - likely broken")
            recommendations.append(f"Verify {net_name} connects from {source} to destination(s)")
            status = "fail"
            severity = "high"
        else:
            status = "pass"
            severity = "low"
            details['path_valid'] = True
    
    return AnalysisResult(
        function_name="trace_signal_path",
        status=status,
        summary=f"Signal path trace for {net_name}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def verify_ground_plane(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify ground plane connectivity and coverage.
    
    Params:
        ground_nets: List[str] - Ground net names
        min_connections: int - Minimum connection points required
    """
    ground_nets = params.get('ground_nets', ['GND'])
    min_conn = params.get('min_connections', 3)
    
    issues = []
    recommendations = []
    details = {}
    
    for gnd_net in ground_nets:
        net = next((n for n in net_build.nets if n.name == gnd_net), None)
        
        if not net:
            issues.append(f"Ground net {gnd_net} not found")
            continue
        
        conn_count = len(net.nodes)
        details[gnd_net] = {
            'connections': conn_count,
            'sufficient': conn_count >= min_conn
        }
        
        if conn_count < min_conn:
            issues.append(f"Ground net {gnd_net} has only {conn_count} connections")
            recommendations.append(f"Verify all ground pins connect to {gnd_net}")
    
    status = "fail" if issues else "pass"
    severity = "high" if issues else "low"
    
    return AnalysisResult(
        function_name="verify_ground_plane",
        status=status,
        summary=f"Ground plane connectivity: {len(ground_nets)} nets checked",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_differential_pairs(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check differential pair routing (USB, LVDS, etc.).
    
    Params:
        pair_nets: List[Tuple[str, str]] - Pairs of net names
        tolerance: float - Acceptable length mismatch (mm)
    """
    pairs = params.get('pair_nets', [])
    tolerance = params.get('tolerance', 0.5)
    
    issues = []
    recommendations = []
    details = {}
    
    for pos_net, neg_net in pairs:
        details[f"{pos_net}_{neg_net}"] = {
            'pair': [pos_net, neg_net],
            'tolerance_mm': tolerance
        }
        
        recommendations.append(f"Verify {pos_net}/{neg_net} differential pair length matching within {tolerance}mm")
        recommendations.append(f"Keep {pos_net}/{neg_net} traces parallel and equal length")
    
    status = "info"
    severity = "low"
    
    return AnalysisResult(
        function_name="check_differential_pairs",
        status=status,
        summary=f"Differential pair check: {len(pairs)} pairs",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def analyze_signal_termination(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Analyze signal termination for high-speed signals.
    
    Params:
        signal_nets: List[str] - High-speed signal nets
        termination_type: str - "series", "parallel", or "none"
    """
    signals = params.get('signal_nets', [])
    term_type = params.get('termination_type', 'none')
    
    issues = []
    recommendations = []
    details = {'termination_type': term_type}
    
    if term_type != 'none':
        for net in signals:
            recommendations.append(f"Verify {net} has {term_type} termination resistor")
    
    status = "info"
    severity = "low"
    
    return AnalysisResult(
        function_name="analyze_signal_termination",
        status=status,
        summary=f"Signal termination: {len(signals)} nets, type={term_type}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def verify_i2c_bus(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check for I2C configuration (Pull-ups).
    """
    # 1. Find I2C nets
    i2c_nets = []
    for net in net_build.nets:
        if 'SDA' in net.name.upper() or 'SCL' in net.name.upper():
            i2c_nets.append(net)
            
    # 2. Fallback: Find I2C pins on components if no nets named SDA/SCL
    found_i2c_pins = False
    floating_i2c_pins = []
    
    if not i2c_nets:
        # Scan symbols for SDA/SCL pins
        for sym in sch.symbols:
            if not sym.at: continue
            sx, sy = sym.at
            for pin in sym.pins:
                name = pin.get('name', '').upper()
                if 'SDA' in name or 'SCL' in name:
                    found_i2c_pins = True
                    # Check if connected
                    if 'at' in pin:
                        px, py = pin['at']
                        abs_at = (sx + px, sy + py)
                        if not _is_pin_connected(abs_at, net_build):
                            floating_i2c_pins.append(f"{sym.ref}.{name}")

    issues = []
    recommendations = []
    details = {'i2c_nets': [n.name for n in i2c_nets]}
    status = "pass"
    severity = "low"
    
    if i2c_nets:
        summary = f"I2C bus detected: {', '.join(n.name for n in i2c_nets)}"
        status = "pass"
        # Check for pull-ups (resistors connected to these nets AND power)
        # Simplified: just look for Resistors on the net
        for net in i2c_nets:
            has_resistor = False
            for node in net.nodes:
                # Find component at node
                # Heuristic: iterate symbols, check IF resistor, check IF pin at node
                for sym in sch.symbols:
                    if sym.ref.startswith('R') and sym.at:
                        # Check pins
                        r_sx, r_sy = sym.at
                        for r_pin in sym.pins:
                            if 'at' in r_pin:
                                rx, ry = r_pin['at']
                                r_abs = (r_sx + rx, r_sy + ry)
                                # Distance check
                                if abs(r_abs[0] - node[0]) < 3.0 and abs(r_abs[1] - node[1]) < 3.0:
                                    has_resistor = True
                                    break
                    if has_resistor: break
            
            if not has_resistor:
                issues.append(f"No pull-up resistor detected on I2C net {net.name}")
                recommendations.append(f"Add 2.2k-10k pull-up resistor on {net.name}")
                status = "warning"
                severity = "medium"
                
    elif found_i2c_pins:
        summary = "I2C pins detected but no bus formed"
        if floating_i2c_pins:
            issues.append(f"I2C pins found floating: {', '.join(floating_i2c_pins)}")
            recommendations.append("Connect I2C pins to bus and add pull-up resistors")
            status = "fail"
            severity = "high"
        else:
            # Pins found, connected, but nets not named SDA/SCL?
            summary += " (Nets unnamed)"
            status = "info"
            recommendations.append("Verify I2C nets are connected and named properly")
            
    else:
        summary = "No I2C bus detected"

    if issues and status == "pass":
        status = "warning"

    return AnalysisResult(
        function_name="verify_i2c_bus",
        status=status,
        summary=summary,
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )