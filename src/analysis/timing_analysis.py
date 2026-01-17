# src/analysis_functions/timing_analysis.py
"""
Modular timing and clock analysis functions.
"""
from __future__ import annotations
import re
from typing import Dict, List, Any
from .power_analysis import AnalysisResult


def analyze_rc_timing_network(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Analyze RC timing network (e.g., for 555 timer).
    
    Params:
        ic_ref: str - Timer IC reference
        r1: str - First resistor reference
        r2: str - Second resistor reference (optional)
        c1: str - Timing capacitor reference
        pins: Dict[str, str] - Pin mapping (discharge, threshold, trigger)
    """
    ic_ref = params.get('ic_ref')
    r1_ref = params.get('r1')
    r2_ref = params.get('r2')
    c1_ref = params.get('c1')
    
    issues = []
    recommendations = []
    details = {}
    
    # Extract component values
    r1_val = _extract_resistance(sch, r1_ref)
    r2_val = _extract_resistance(sch, r2_ref) if r2_ref else None
    c1_val = _extract_capacitance(sch, c1_ref)
    
    details['component_values'] = {
        'r1': {'ref': r1_ref, 'value': r1_val},
        'r2': {'ref': r2_ref, 'value': r2_val} if r2_ref else None,
        'c1': {'ref': c1_ref, 'value': c1_val}
    }
    
    # Calculate timing if all values found
    if r1_val and c1_val:
        if r2_val:  # Astable mode (555)
            frequency = 1.44 / ((r1_val + 2*r2_val) * c1_val)
            duty_cycle = (r1_val + r2_val) / (r1_val + 2*r2_val) * 100
            period = 1 / frequency
            
            details['calculated_timing'] = {
                'mode': 'astable',
                'frequency_hz': round(frequency, 3),
                'period_s': round(period, 6),
                'period_ms': round(period * 1000, 3),
                'duty_cycle_percent': round(duty_cycle, 1)
            }
            
            # Validate timing
            if frequency > 500000:  # > 500kHz
                issues.append(f"Frequency {frequency:.0f}Hz may be too high for 555 timer")
                recommendations.append("Check if component values are correct")
            elif frequency < 0.01:  # < 0.01Hz
                issues.append(f"Frequency {frequency:.4f}Hz is very low - verify component values")
            
            # Check duty cycle
            if duty_cycle < 50 or duty_cycle > 95:
                recommendations.append(f"Duty cycle {duty_cycle:.1f}% - adjust R1/R2 ratio if needed")
        else:  # Monostable mode
            pulse_width = 1.1 * r1_val * c1_val
            details['calculated_timing'] = {
                'mode': 'monostable',
                'pulse_width_s': round(pulse_width, 6),
                'pulse_width_ms': round(pulse_width * 1000, 3)
            }
    else:
        missing = []
        if not r1_val: missing.append(r1_ref)
        if r2_ref and not r2_val: missing.append(r2_ref)
        if not c1_val: missing.append(c1_ref)
        
        issues.append(f"Could not extract values for: {', '.join(missing)}")
        recommendations.append("Verify component values are specified in schematic")
    
    status = "fail" if issues else "pass"
    severity = "medium" if issues else "low"
    
    return AnalysisResult(
        function_name="analyze_rc_timing_network",
        status=status,
        summary=f"RC timing analysis for {ic_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def verify_crystal_circuit(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Verify crystal oscillator circuit for MCU.
    
    Params:
        crystal_ref: str - Crystal reference (e.g., "Y1")
        mcu_ref: str - MCU reference
        load_caps: List[str] - Load capacitor references
        frequency_mhz: float - Expected frequency
    """
    crystal_ref = params.get('crystal_ref')
    mcu_ref = params.get('mcu_ref')
    load_caps = params.get('load_caps', [])
    freq = params.get('frequency_mhz')
    
    issues = []
    recommendations = []
    details = {}
    
    # Check crystal exists
    crystal = next((s for s in sch.symbols if s.ref == crystal_ref), None)
    if not crystal:
        issues.append(f"Crystal {crystal_ref} not found")
        status = "fail"
        severity = "critical"
    else:
        details['crystal'] = {
            'ref': crystal_ref,
            'value': crystal.value,
            'found': True
        }
        
        # Check load capacitors
        found_caps = []
        for cap_ref in load_caps:
            cap = next((s for s in sch.symbols if s.ref == cap_ref), None)
            if cap:
                cap_val = _extract_capacitance(sch, cap_ref)
                found_caps.append({
                    'ref': cap_ref,
                    'value': cap_val
                })
        
        details['load_capacitors'] = found_caps
        
        if len(found_caps) < 2:
            issues.append(f"Expected 2 load capacitors, found {len(found_caps)}")
            recommendations.append("Add load capacitors (typically 12-22pF) per MCU datasheet")
            severity = "high"
            status = "fail"
        else:
            # Check if capacitor values are reasonable
            for cap in found_caps:
                if cap['value']:
                    if cap['value'] > 50e-12:  # > 50pF
                        recommendations.append(f"{cap['ref']} value seems high for crystal load cap")
            
            status = "pass"
            severity = "low"
    
    return AnalysisResult(
        function_name="verify_crystal_circuit",
        status=status,
        summary=f"Crystal oscillator circuit for {mcu_ref}",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=(status == "fail")
    )


def check_clock_distribution(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Check clock signal distribution and routing.
    
    Params:
        clock_nets: List[str] - Clock signal net names
        max_fanout: int - Maximum allowed fanout
    """
    clock_nets = params.get('clock_nets', [])
    max_fanout = params.get('max_fanout', 10)
    
    issues = []
    recommendations = []
    details = {}
    
    for clock_net in clock_nets:
        net = next((n for n in net_build.nets if n.name == clock_net), None)
        
        if net:
            fanout = len(net.nodes)
            details[clock_net] = {
                'fanout': fanout,
                'exceeds_max': fanout > max_fanout
            }
            
            if fanout > max_fanout:
                issues.append(f"Clock net {clock_net} has high fanout ({fanout})")
                recommendations.append("Consider using clock buffer for high fanout")
            elif fanout == 1:
                recommendations.append(f"Clock net {clock_net} has only one connection - verify routing")
    
    status = "warning" if issues else "pass"
    severity = "medium" if issues else "low"
    
    return AnalysisResult(
        function_name="check_clock_distribution",
        status=status,
        summary=f"Clock distribution: {len(clock_nets)} nets analyzed",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity=severity,
        prevents_bringup=False
    )


def _extract_resistance(sch, ref: str) -> float:
    """Extract resistance value in ohms"""
    sym = next((s for s in sch.symbols if s.ref == ref), None)
    if not sym or not sym.value:
        return None
    
    try:
        # Handle formats: "10k", "10K", "4.7k", "1M", "100"
        val_str = sym.value.upper()
        val_str = val_str.replace('K', 'e3').replace('M', 'e6').replace('Ω', '').replace('OHM', '')
        val_str = re.sub(r'[^0-9.eE+-]', '', val_str)
        return float(val_str)
    except:
        return None


def _extract_capacitance(sch, ref: str) -> float:
    """Extract capacitance value in farads"""
    sym = next((s for s in sch.symbols if s.ref == ref), None)
    if not sym or not sym.value:
        return None
    
    try:
        # Handle formats: "10uF", "100nF", "22pF", "0.1µF"
        val_str = sym.value.upper()
        val_str = val_str.replace('µ', 'U').replace('U', 'e-6').replace('N', 'e-9').replace('P', 'e-12')
        val_str = val_str.replace('F', '')
        val_str = re.sub(r'[^0-9.eE+-]', '', val_str)
        return float(val_str)
    except:
        return None