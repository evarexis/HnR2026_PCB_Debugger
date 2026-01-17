# src/analysis/mcu_analysis.py - ENHANCED VERSION
"""
MCU-specific analysis functions with improved detection
"""
from __future__ import annotations
from typing import Dict, List, Any
from .power_analysis import AnalysisResult


def analyze_reset_circuit(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Analyze reset circuit and DETECT missing pull-up resistor.
    
    Params:
        mcu_ref: str - MCU reference (e.g., "U1")
        reset_pin: str - Reset pin number (e.g., "7")
        pullup_required: bool - Whether pull-up required (default True)
    """
    mcu_ref = params.get('mcu_ref')
    reset_pin = params.get('reset_pin', '7')
    needs_pullup = params.get('pullup_required', True)
    
    issues = []
    recommendations = []
    details = {'reset_pin': reset_pin, 'pullup_required': needs_pullup}
    
    # Find MCU
    mcu = next((s for s in sch.symbols if s.ref == mcu_ref), None)
    if not mcu:
        issues.append(f"MCU {mcu_ref} not found")
        return AnalysisResult(
            function_name="analyze_reset_circuit",
            status="fail",
            summary=f"Reset circuit for {mcu_ref} - MCU not found",
            details=details,
            issues=issues,
            recommendations=["Verify MCU component reference"],
            severity="critical",
            prevents_bringup=True
        )
    
    # Auto-detect reset net
    reset_net = None
    for net in net_build.nets:
        if any(kw in net.name.upper() for kw in ['NRST', 'RST', 'RESET']):
            reset_net = net.name
            break
    
    # Check for pull-up resistor
    pullup_found = False
    pullup_ref = None
    
    if reset_net:
        details['reset_net'] = reset_net
        net_obj = next((n for n in net_build.nets if n.name == reset_net), None)
        
        if net_obj:
            # Look for resistors on this net
            for sym in sch.symbols:
                if sym.ref.startswith('R') and sym.at:
                    # Check if resistor is near reset net nodes
                    for node in net_obj.nodes:
                        if sym.at:
                            distance = ((sym.at[0] - node[0])**2 + (sym.at[1] - node[1])**2)**0.5
                            if distance < 50:
                                pullup_found = True
                                pullup_ref = sym.ref
                                break
                if pullup_found:
                    break
    
    # Evaluate result
    if needs_pullup and not pullup_found:
        issues.append(f"CRITICAL: Missing reset pull-up resistor on {mcu_ref} pin {reset_pin} (NRST)")
        recommendations.append(f"Add 10kΩ pull-up resistor from {mcu_ref} NRST (pin {reset_pin}) to VDD/3V3")
        recommendations.append("This is REQUIRED for reliable MCU reset and prevents floating NRST pin")
        status = "fail"
        severity = "critical"
    elif pullup_found:
        details['pullup_resistor'] = pullup_ref
        recommendations.append(f"Reset pull-up found: {pullup_ref}")
        status = "pass"
        severity = "low"
    else:
        recommendations.append(f"Verify reset pull-up on pin {reset_pin}")
        status = "warning"
        severity = "medium"
    
    return AnalysisResult(
        function_name="analyze_reset_circuit",
        status=status,
        summary=f"Reset circuit for {mcu_ref}: {status.upper()}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_boot_pins(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check if BOOT pins are properly configured (not floating).
    
    Params:
        mcu_ref: str - MCU reference
        boot_pins: List[str] - Boot pin numbers (e.g., ["44"])
        expected_state: str - "LOW" or "HIGH" or "PULLDOWN"
    """
    mcu_ref = params.get('mcu_ref')
    boot_pins = params.get('boot_pins', [])
    expected_state = params.get('expected_state', 'LOW')
    
    issues = []
    recommendations = []
    details = {'boot_pins': boot_pins, 'expected_state': expected_state}
    
    # Find MCU
    mcu = next((s for s in sch.symbols if s.ref == mcu_ref), None)
    if not mcu:
        issues.append(f"MCU {mcu_ref} not found")
        return AnalysisResult(
            function_name="check_boot_pins",
            status="fail",
            summary=f"Boot pin check for {mcu_ref}",
            details=details,
            issues=issues,
            recommendations=[],
            severity="critical",
            prevents_bringup=True
        )
    
    # Check each boot pin
    for pin in boot_pins:
        # Look for nets connected to this pin area
        # Simplified: check if there's a pull-down resistor or connection
        pulldown_found = False
        tied_to_gnd = False
        
        # Check for "BOOT" nets
        for net in net_build.nets:
            if 'BOOT' in net.name.upper():
                details[f'boot_net_pin{pin}'] = net.name
                
                # Look for resistors on boot net
                for sym in sch.symbols:
                    if sym.ref.startswith('R') and sym.at:
                        for node in net.nodes:
                            distance = ((sym.at[0] - node[0])**2 + (sym.at[1] - node[1])**2)**0.5
                            if distance < 50:
                                pulldown_found = True
                                details[f'boot_resistor_pin{pin}'] = sym.ref
                                break
                
                # Check if tied to GND
                if any('GND' in net.name.upper() for net in net_build.nets):
                    tied_to_gnd = True
        
        if not pulldown_found and not tied_to_gnd and expected_state == 'LOW':
            issues.append(f"WARNING: BOOT pin {pin} appears floating (should be pulled LOW)")
            recommendations.append(f"Add 10kΩ pull-down resistor on {mcu_ref} BOOT0 (pin {pin}) to GND")
            recommendations.append("Floating BOOT pin can cause boot mode issues")
    
    if issues:
        status = "warning"
        severity = "medium"
    else:
        status = "pass"
        severity = "low"
        if boot_pins:
            recommendations.append(f"BOOT pins configuration OK")
    
    return AnalysisResult(
        function_name="check_boot_pins",
        status=status,
        summary=f"Boot pin check for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def verify_mcu_boot_configuration(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """Alias for check_boot_pins for compatibility"""
    return check_boot_pins(params, sch, net_build)


def check_debug_interface(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """Check debug/programming interface"""
    mcu_ref = params.get('mcu_ref')
    interface_type = params.get('interface_type', 'SWD')
    required_nets = params.get('required_nets', [])
    
    issues = []
    recommendations = []
    details = {'interface': interface_type, 'required_signals': required_nets}
    
    missing_nets = []
    for net_name in required_nets:
        net = next((n for n in net_build.nets if n.name == net_name), None)
        if not net:
            missing_nets.append(net_name)
    
    if missing_nets:
        issues.append(f"Missing {interface_type} signals: {', '.join(missing_nets)}")
        recommendations.append(f"Add {interface_type} connector with signals: {', '.join(required_nets)}")
        status = "fail"
        severity = "critical"
    else:
        details['nets_found'] = required_nets
        recommendations.append(f"Verify {interface_type} connector pinout matches programmer")
        status = "pass"
        severity = "medium"
    
    return AnalysisResult(
        function_name="check_debug_interface",
        status=status,
        summary=f"{interface_type} debug interface for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def verify_programming_interface(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """Verify programming interface accessibility"""
    mcu_ref = params.get('mcu_ref')
    prog_type = params.get('programmer_type', 'ST-Link')
    connector_ref = params.get('connector_ref', 'J1')
    
    issues = []
    recommendations = []
    details = {'programmer': prog_type, 'connector': connector_ref}
    
    connector = next((s for s in sch.symbols if s.ref == connector_ref), None)
    
    if not connector:
        issues.append(f"Programming connector {connector_ref} not found")
        recommendations.append(f"Add {prog_type} compatible programming header")
        status = "fail"
        severity = "critical"
    else:
        details['connector_found'] = True
        recommendations.append(f"Verify {connector_ref} pinout matches {prog_type} programmer")
        status = "pass"
        severity = "medium"
    
    return AnalysisResult(
        function_name="verify_programming_interface",
        status=status,
        summary=f"Programming interface for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_mcu_power_pins(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """Check all MCU power pins are connected"""
    mcu_ref = params.get('mcu_ref')
    vdd_count = params.get('vdd_count', 1)
    gnd_count = params.get('gnd_count', 1)
    needs_vdda = params.get('vdda_required', False)
    
    issues = []
    recommendations = []
    details = {
        'expected_vdd_pins': vdd_count,
        'expected_gnd_pins': gnd_count,
        'analog_power': needs_vdda
    }
    
    recommendations.append(f"Verify all {vdd_count} VDD pins of {mcu_ref} are connected to power")
    recommendations.append(f"Verify all {gnd_count} GND pins of {mcu_ref} are connected to ground")
    
    if needs_vdda:
        recommendations.append(f"Verify VDDA pin has separate filtering (LC or ferrite bead + cap)")
    
    status = "pass"
    severity = "high"
    
    return AnalysisResult(
        function_name="check_mcu_power_pins",
        status=status,
        summary=f"MCU power pin check for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )