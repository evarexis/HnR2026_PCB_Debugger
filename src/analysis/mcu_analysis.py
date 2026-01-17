# src/analysis_functions/mcu_analysis.py
"""
MCU-specific analysis functions.
"""
from __future__ import annotations
from typing import Dict, List, Any
from .power_analysis import AnalysisResult


def verify_mcu_boot_configuration(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify MCU boot configuration pins.
    
    Params:
        mcu_ref: str - MCU reference
        boot_pins: Dict[str, str] - Pin number to expected state mapping
        boot_mode: str - Expected boot mode
    """
    mcu_ref = params.get('mcu_ref')
    boot_pins = params.get('boot_pins', {})
    boot_mode = params.get('boot_mode', 'flash')
    
    issues = []
    recommendations = []
    details = {
        'mcu': mcu_ref,
        'boot_mode': boot_mode,
        'boot_pins': boot_pins
    }
    
    mcu = next((s for s in sch.symbols if s.ref == mcu_ref), None)
    
    if not mcu:
        issues.append(f"MCU {mcu_ref} not found")
        status = "fail"
        severity = "critical"
    else:
        for pin, expected_state in boot_pins.items():
            if expected_state == "LOW":
                recommendations.append(f"Verify {mcu_ref} pin {pin} (BOOT) is tied to GND for {boot_mode} boot mode")
            elif expected_state == "HIGH":
                recommendations.append(f"Verify {mcu_ref} pin {pin} (BOOT) is tied to VDD for {boot_mode} boot mode")
            else:
                recommendations.append(f"Verify {mcu_ref} pin {pin} (BOOT) configuration")
        
        status = "pass"
        severity = "high"
    
    return AnalysisResult(
        function_name="verify_mcu_boot_configuration",
        status=status,
        summary=f"Boot configuration for {mcu_ref} ({boot_mode} mode)",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_debug_interface(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check debug/programming interface (SWD, JTAG, UART).
    
    Params:
        mcu_ref: str - MCU reference
        interface_type: str - "SWD", "JTAG", or "UART"
        required_nets: List[str] - Required signal nets
    """
    mcu_ref = params.get('mcu_ref')
    interface_type = params.get('interface_type', 'SWD')
    required_nets = params.get('required_nets', [])
    
    issues = []
    recommendations = []
    details = {
        'interface': interface_type,
        'required_signals': required_nets
    }
    
    # Check if required nets exist
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


def analyze_reset_circuit(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Analyze reset circuit configuration.
    
    Params:
        mcu_ref: str - MCU reference
        reset_net: str - Reset net name
        has_external_reset: bool - Whether external reset button exists
        pullup_required: bool - Whether pull-up resistor required
    """
    mcu_ref = params.get('mcu_ref')
    reset_net = params.get('reset_net', 'NRST')
    has_button = params.get('has_external_reset', False)
    needs_pullup = params.get('pullup_required', True)
    
    issues = []
    recommendations = []
    details = {
        'reset_net': reset_net,
        'external_button': has_button,
        'pullup_required': needs_pullup
    }
    
    # Check if reset net exists
    net = next((n for n in net_build.nets if n.name == reset_net), None)
    
    if not net:
        issues.append(f"Reset net {reset_net} not found")
        recommendations.append(f"Add reset circuit with pull-up resistor and optional button")
        status = "fail"
        severity = "high"
    else:
        if needs_pullup:
            recommendations.append(f"Verify 10kΩ pull-up resistor on {reset_net}")
        
        if has_button:
            recommendations.append(f"Verify reset button pulls {reset_net} to GND when pressed")
        
        status = "pass"
        severity = "medium"
    
    return AnalysisResult(
        function_name="analyze_reset_circuit",
        status=status,
        summary=f"Reset circuit for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def verify_programming_interface(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify programming interface accessibility.
    
    Params:
        mcu_ref: str - MCU reference
        programmer_type: str - Type of programmer
        connector_ref: str - Programming connector reference
    """
    mcu_ref = params.get('mcu_ref')
    prog_type = params.get('programmer_type', 'ST-Link')
    connector_ref = params.get('connector_ref', 'J1')
    
    issues = []
    recommendations = []
    details = {
        'programmer': prog_type,
        'connector': connector_ref
    }
    
    # Check if connector exists
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
    """
    Check all MCU power pins are properly connected.
    
    Params:
        mcu_ref: str - MCU reference
        vdd_count: int - Number of VDD pins
        gnd_count: int - Number of GND pins
        vdda_required: bool - Whether analog power is required
    """
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