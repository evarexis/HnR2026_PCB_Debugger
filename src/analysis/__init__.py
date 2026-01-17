# src/analysis_functions/__init__.py
"""
Analysis function registry and executor.
Maps function names to actual implementations.
"""
from __future__ import annotations
from typing import Dict, Any, Callable
from .power_analysis import (
    verify_power_connectivity,
    check_power_rail_routing,
    analyze_decoupling_capacitors,
    verify_voltage_regulator_circuit,
    check_power_sequencing,
    AnalysisResult
)
from .timing_analysis import (
    analyze_rc_timing_network,
    verify_crystal_circuit,
    check_clock_distribution,
)
from .signal_analysis import (
    check_floating_pins,
    verify_pull_up_pull_down,
    trace_signal_path,
    verify_ground_plane,
    check_differential_pairs,
    analyze_signal_termination,
)
from .mcu_analysis import (
    verify_mcu_boot_configuration,
    check_debug_interface,
    analyze_reset_circuit,
    verify_programming_interface,
    check_mcu_power_pins,
)


# Function registry
ANALYSIS_FUNCTIONS: Dict[str, Callable] = {
    # Power analysis
    "verify_power_connectivity": verify_power_connectivity,
    "check_power_rail_routing": check_power_rail_routing,
    "analyze_decoupling_capacitors": analyze_decoupling_capacitors,
    "verify_voltage_regulator_circuit": verify_voltage_regulator_circuit,
    "check_power_sequencing": check_power_sequencing,
    
    # Timing/clock analysis
    "analyze_rc_timing_network": analyze_rc_timing_network,
    "verify_crystal_circuit": verify_crystal_circuit,
    "check_clock_distribution": check_clock_distribution,
    
    # Signal integrity
    "check_floating_pins": check_floating_pins,
    "verify_pull_up_pull_down": verify_pull_up_pull_down,
    "trace_signal_path": trace_signal_path,
    "verify_ground_plane": verify_ground_plane,
    "check_differential_pairs": check_differential_pairs,
    "analyze_signal_termination": analyze_signal_termination,
    
    # MCU specific
    "verify_mcu_boot_configuration": verify_mcu_boot_configuration,
    "check_debug_interface": check_debug_interface,
    "analyze_reset_circuit": analyze_reset_circuit,
    "verify_programming_interface": verify_programming_interface,
    "check_mcu_power_pins": check_mcu_power_pins,
}


def execute_analysis_function(
    function_name: str,
    params: Dict[str, Any],
    sch,
    net_build
) -> AnalysisResult:
    """
    Execute an analysis function by name.
    
    Args:
        function_name: Name of the function to execute
        params: Parameters to pass to the function
        sch: Schematic object
        net_build: NetBuildResult object
    
    Returns:
        AnalysisResult object
    
    Raises:
        ValueError: If function name not found
    """
    if function_name not in ANALYSIS_FUNCTIONS:
        # Return error result instead of raising
        return AnalysisResult(
            function_name=function_name,
            status="error",
            summary=f"Unknown analysis function: {function_name}",
            details={"error": "Function not found in registry"},
            issues=[f"Function '{function_name}' is not implemented"],
            recommendations=["Check function name spelling", "Verify function is registered"],
            severity="low",
            prevents_bringup=False
        )
    
    func = ANALYSIS_FUNCTIONS[function_name]
    
    try:
        result = func(params, sch, net_build)
        return result
    except Exception as e:
        # Return error result instead of crashing
        return AnalysisResult(
            function_name=function_name,
            status="error",
            summary=f"Error executing {function_name}: {str(e)}",
            details={"error": str(e), "params": params},
            issues=[f"Function crashed: {str(e)}"],
            recommendations=["Check function parameters", "Review error details"],
            severity="low",
            prevents_bringup=False
        )


def get_available_functions() -> list[str]:
    """Get list of all available analysis function names"""
    return sorted(ANALYSIS_FUNCTIONS.keys())


__all__ = [
    'ANALYSIS_FUNCTIONS',
    'execute_analysis_function',
    'get_available_functions',
    'AnalysisResult'
]