#!/usr/bin/env python3
"""
PCB Debugger - AI-Powered Schematic Analysis (+ optional PCB layout analysis)

- Parses .kicad_sch (Eeschema S-expression)
- Builds connectivity nets
- Detects power/reset/clock/debug/MCU heuristics
- Builds a schematic summary for LLM
- Uses LLM (or heuristics fallback) to propose an analysis pipeline
- Executes analysis functions (rule-based checks)
- Generates a final report JSON
- Optionally analyzes .kicad_pcb if provided (and module exists)
"""
from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

# --- Core modules ---
from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors

# --- LLM / summary / analysis pipeline ---
from src.schematic_summary import generate_schematic_summary
from src.llm_analysis import LLMAnalyzer, LLMProvider
from src.analysis import execute_analysis_function

# --- OPTIONAL PCB analysis ---
try:
    from src.pcb_layout_analysis import analyze_pcb_layout, format_pcb_analysis_report
    PCB_ANALYSIS_AVAILABLE = True
except ImportError:
    PCB_ANALYSIS_AVAILABLE = False


def run_heuristic_analysis(sch, net_build, detected) -> Dict[str, Any]:
    """
    Fallback heuristic analysis when LLM is unavailable.
    Returns same structure as LLM but with simpler logic.
    """
    print("Running heuristic-based analysis...")

    circuit_type = "unknown"
    main_ic = None
    critical_components: List[str] = []

    for sym in sch.symbols:
        if '?' in sym.ref:
            continue

        if sym.ref.startswith('U'):
            main_ic = sym.ref
            critical_components.append(sym.ref)

            if '555' in sym.lib_id.lower():
                circuit_type = "555_timer_astable"
            elif any(kw in sym.lib_id.lower() for kw in ['stm32', 'esp32', 'atmega', 'attiny', 'nrf', 'rp2040']):
                circuit_type = "microcontroller_basic"

        if circuit_type == "555_timer_astable":
            if sym.ref.startswith('R') or sym.ref.startswith('C'):
                critical_components.append(sym.ref)

    analysis_pipeline: List[Dict[str, Any]] = []

    analysis_pipeline = []
    
    main_ic = None
    if detected.mcu_symbols:
        main_ic = detected.mcu_symbols[0]
    else:
        u_comps = sorted([s.ref for s in sch.symbols if s.ref.upper().startswith('U')])
        if u_comps:
             main_ic = u_comps[0]
             
    # 1. Power Analysis (Universal)
    if detected.power_nets:
        analysis_pipeline.append({
            "function": "verify_power_connectivity",
            "params": {
                "power_nets": detected.power_nets,
                "ic_ref": main_ic 
            },
            "priority": "critical",
            "reason": "Power must be connected"
        })
        
        analysis_pipeline.append({
            "function": "detect_multi_voltage_system",
            "params": {},
            "priority": "medium",
            "reason": "Identify voltage domains"
        })

    # 2. Main IC Checks (Generic)
    if main_ic:
        analysis_pipeline.append({
            "function": "check_floating_pins",
            "params": {
                "ic_ref": main_ic,
                "critical_pins": [],
                "exclude_pins": ["NC", "NB"]
            },
            "priority": "high",
            "reason": "Floating pins can cause undefined behavior"
        })
        

        analysis_pipeline.append({
            "function": "analyze_decoupling_capacitors",
            "params": {
                "ic_refs": [main_ic],
                "proximity_threshold": 50
            },
            "priority": "medium",
            "reason": "Decoupling caps reduce power noise"
        })

    # 3. MCU Specific Checks
    if detected.mcu_symbols:
        if detected.reset_nets:
             analysis_pipeline.append({
                "function": "analyze_reset_circuit",
                "params": {
                    "mcu_ref": main_ic,
                    "reset_net": detected.reset_nets[0],
                    "pullup_required": True
                },
                "priority": "high",
                "reason": "Reset circuit check"
            })
            
        analysis_pipeline.append({
            "function": "check_boot_pins",
            "params": {
                "mcu_ref": main_ic,
                "boot_pins": ["44", "BOOT0"],
                "expected_state": "LOW"
            },
            "priority": "high",
            "reason": "Boot configuration"
        })
        
        if detected.clock_sources:
             analysis_pipeline.append({
                "function": "verify_crystal_circuit",
                "params": {
                    "crystal_ref": detected.clock_sources[0],
                    "mcu_ref": main_ic,
                    "load_caps": ["C1", "C2"],
                    "frequency_mhz": 8.0
                },
                "priority": "critical",
                 "reason": "Clock source verification"
            })

    # 4. Bus/Interface Analysis
    has_i2c_nets = any('SDA' in n.name.upper() or 'SCL' in n.name.upper() for n in net_build.nets)
    if has_i2c_nets:
        analysis_pipeline.append({
            "function": "verify_i2c_bus",
            "params": {},
            "priority": "medium",
            "reason": "I2C Bus detected"
        })
    else:
        # Check if we should check I2C anyway (e.g. if we have a Sensor)
        # But verify_i2c_bus mainly checks nets. 
        # If we want to catch floating pins, we rely on check_floating_pins above!
        # Re-adding verify_i2c_bus unconditionally as "medium" might be noisy if no I2C exists.
        # But user wants "I2C Pull-Up Missing" even if nets are messed up.
        # Let's add it if we have ANY nets or if we are desperate.
        # Safest: Add it if we have > 0 nets.
        analysis_pipeline.append({
            "function": "verify_i2c_bus",
            "params": {},
            "priority": "low",
            "reason": "Check for I2C configuration"
        })

    detected_issues: List[Dict[str, Any]] = []
    for label_text, label_pos in net_build.label_unattached:
        severity = "critical" if label_text in detected.power_nets else "high"
        detected_issues.append({
            "issue": f"label_{label_text}_unattached",
            "severity": severity,
            "analysis_needed": ["trace_signal_path"],
            "components_involved": [label_text],
            "reason": f"Label {label_text} not connected to any wire",
            "debug_step": f"Connect label {label_text} at ({label_pos[0]}, {label_pos[1]}) to a wire/junction"
        })

    verification_steps_issues = []
    for i, issue in enumerate(detected_issues, 1):
        verification_steps_issues.append({
            "step": i,
            "action": f"Fix {issue['issue']}",
            "expected": "Label connected to circuit",
            "target": issue['issue']
        })

    verification_steps_general = [
        {"step": 1, "action": "Apply power to circuit", "expected": "No smoke, correct voltage on power rails"},
        {"step": 2, "action": "Measure key outputs/signals", "expected": "Expected waveform/behavior observed"},
    ]

    return {
        "circuit_analysis": {
            "circuit_type": circuit_type,
            "purpose": "Generate output based on components detected",
            "confidence": 0.6,
            "main_ic": main_ic,
            "critical_components": sorted(set(critical_components)),
        },
        "analysis": analysis_pipeline,
        "expected_behavior": {
            "output_frequency_hz": None,
            "duty_cycle_percent": None,
            "other_behaviors": "Circuit should power on and operate as designed"
        },
        "detected_issues": detected_issues,
        "verification_steps_issues": verification_steps_issues,
        "verification_steps_general": verification_steps_general
    }


def run_analysis_pipeline(llm_analysis: Dict[str, Any], sch, net_build) -> List[Dict[str, Any]]:
    """
    Execute all analysis functions recommended by LLM or heuristics.
    Returns list of analysis results (serializable dicts).
    """
    analysis_pipeline = llm_analysis.get('analysis', [])
    results: List[Dict[str, Any]] = []

    print(f"\nExecuting {len(analysis_pipeline)} analysis functions...")

    for i, task in enumerate(analysis_pipeline, 1):
        function_name = task.get('function')
        params = task.get('params', {})
        priority = task.get('priority', 'medium')

        print(f"  [{i}/{len(analysis_pipeline)}] {function_name} (priority: {priority})")

        result = execute_analysis_function(function_name, params, sch, net_build)

        results.append({
            "function": function_name,
            "priority": priority,
            "reason": task.get('reason', ''),
            "status": result.status,
            "summary": result.summary,
            "details": result.details,
            "issues": result.issues,
            "recommendations": result.recommendations,
            "severity": result.severity,
            "prevents_bringup": result.prevents_bringup
        })

    return results


def generate_final_report(
    schematic_path: str,
    llm_analysis: Dict[str, Any],
    analysis_results: List[Dict[str, Any]],
    detected,
    analysis_method: str,
    pcb_analysis_report: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Generate comprehensive debugging report (+ optional pcb_layout_analysis).
    """
    all_issues = list(llm_analysis.get('detected_issues', []))

    for result in analysis_results:
        if result.get('issues'):
            for issue in result['issues']:
                all_issues.append({
                    "issue": f"{result['function']}_issue",
                    "severity": result.get('severity', 'medium'),
                    "analysis_needed": [result['function']],
                    "components_involved": [],
                    "reason": issue,
                    "debug_step": " | ".join(result.get('recommendations', [])) if result.get('recommendations') else ""
                })

    critical_count = sum(1 for issue in all_issues if issue.get('severity') == 'critical')
    high_count = sum(1 for issue in all_issues if issue.get('severity') == 'high')

    blockers = [issue for issue in all_issues if issue.get('severity') == 'critical']
    can_attempt_bringup = (len(blockers) == 0)

    if critical_count > 0:
        risk_level = "critical"
        risk_score = 90 + min(10, critical_count * 2)
    elif high_count > 2:
        risk_level = "high"
        risk_score = 70 + min(20, high_count * 5)
    elif high_count > 0:
        risk_level = "medium"
        risk_score = 50 + high_count * 10
    else:
        risk_level = "low"
        risk_score = 20

    report: Dict[str, Any] = {
        "metadata": {
            "schematic_file": str(schematic_path),
            "analysis_method": analysis_method,
            "circuit_type": llm_analysis['circuit_analysis']['circuit_type'],
            "confidence": llm_analysis['circuit_analysis']['confidence']
        },
        "circuit_analysis": llm_analysis['circuit_analysis'],
        "expected_behavior": llm_analysis['expected_behavior'],
        "detected_issues": all_issues,
        "analysis_results": analysis_results,
        "verification_steps": {
            "for_issues": llm_analysis.get('verification_steps_issues', []),
            "for_general_workability": llm_analysis.get('verification_steps_general', [])
        },
        "overall_risk": {
            "score": min(100, risk_score),
            "level": risk_level,
            "critical_issues": critical_count,
            "high_priority_issues": high_count,
            "total_issues": len(all_issues),
            "blockers": [b.get('reason', '') for b in blockers[:5]],
            "can_attempt_bringup": can_attempt_bringup
        },
        "summary": {
            "total_mcus_detected": len(detected.mcu_symbols) if detected.mcu_symbols else 0,
            "power_nets_detected": detected.power_nets,
            "clock_sources_detected": detected.clock_sources,
            "debug_interfaces": detected.debug_ifaces
        }
    }

    if pcb_analysis_report:
        report["pcb_layout_analysis"] = pcb_analysis_report

        drc = pcb_analysis_report.get("drc_violations") or []
        pcb_critical = len([v for v in drc if v.get("severity") == "critical"])
        if pcb_critical:
            report["overall_risk"]["score"] = min(100, report["overall_risk"]["score"] + pcb_critical * 5)
            report["overall_risk"]["pcb_critical_violations"] = pcb_critical

    return report


def main():
    parser = argparse.ArgumentParser(
        description="PCB Debugger - Analyze KiCad schematics and optionally PCB layouts"
    )
    parser.add_argument('schematic', type=str, help='Path to .kicad_sch file')
    parser.add_argument('--pcb', type=str, default=None, help='Optional path to .kicad_pcb file')
    parser.add_argument('--llm', type=str, choices=['openai', 'gemini', 'heuristic'], default='openai',
                        help='Primary LLM provider (default: openai)')
    parser.add_argument('--fallback', type=str, choices=['openai', 'gemini', 'heuristic'], default='gemini',
                        help='Fallback LLM provider (default: gemini)')
    parser.add_argument('--output', type=str, help='Output JSON file path (default: stdout)')

    args = parser.parse_args()

    schematic_path = Path(args.schematic)
    if not schematic_path.exists():
        print(f"Error: File not found: {schematic_path}", file=sys.stderr)
        sys.exit(1)

    pcb_path = None
    if args.pcb:
        pcb_path = Path(args.pcb)
        if not pcb_path.exists():
            print(f"Warning: PCB file not found: {pcb_path}")
            pcb_path = None
        elif not PCB_ANALYSIS_AVAILABLE:
            print("Warning: pcb_layout_analysis module not available; skipping PCB analysis.")
            pcb_path = None

    print(f"Analyzing schematic: {schematic_path}")
    print(f"Primary LLM: {args.llm}, Fallback: {args.fallback}")
    if pcb_path:
        print(f"PCB Layout file: {pcb_path}")
    print()

    # Step 1: Parse schematic
    print("Step 1: Parsing schematic...")
    tree = parse_kicad_sch(schematic_path)
    sch = parse_schematic(tree)
    print(f"  Found {len(sch.symbols)} components, {len(sch.wires)} wires, {len(sch.labels)} labels")

    # Step 2: Build netlist
    print("\nStep 2: Building netlist...")
    net_build = build_nets(sch, label_tolerance=2)
    print(f"  Generated {len(net_build.nets)} nets")
    print(f"  Unattached labels: {len(net_build.label_unattached)}")

    # Step 3: Run detectors
    print("\nStep 3: Running component detectors...")
    detected = run_detectors(sch, net_build.nets)
    print(f"  Power nets: {detected.power_nets}")
    print(f"  Main ICs: {detected.mcu_symbols if detected.mcu_symbols else 'None detected'}")

    # Step 4: Schematic summary
    print("\nStep 4: Generating schematic summary for LLM...")
    summary = generate_schematic_summary(sch, net_build)
    print(f"  Summary size: {len(json.dumps(summary))} characters")

    # Step 5: LLM analysis
    llm_provider_map = {
        'openai': LLMProvider.OPENAI,
        'gemini': LLMProvider.GEMINI,
        'heuristic': LLMProvider.HEURISTIC
    }
    primary = llm_provider_map[args.llm]
    fallback = llm_provider_map[args.fallback]
    analyzer = LLMAnalyzer(primary=primary, secondary=fallback)

    print(f"\nStep 5: Analyzing circuit with {args.llm}...")
    llm_analysis = analyzer.analyze_schematic(summary)
    analysis_method = analyzer.used_provider.value if analyzer.used_provider else "unknown"

    if llm_analysis is None:
        llm_analysis = run_heuristic_analysis(sch, net_build, detected)
        analysis_method = "heuristic"

    print(f"  Analysis method: {analysis_method}")
    print(f"  Circuit type: {llm_analysis['circuit_analysis']['circuit_type']}")
    print(f"  Confidence: {llm_analysis['circuit_analysis']['confidence']}")

    # Step 6: Execute analysis pipeline
    print("\nStep 6: Executing analysis functions...")
    analysis_results = run_analysis_pipeline(llm_analysis, sch, net_build)

    # Step 7 (optional): PCB analysis
    pcb_analysis_report = None
    if pcb_path and PCB_ANALYSIS_AVAILABLE:
        print("\nStep 7: Analyzing PCB layout...")
        try:
            pcb_analysis = analyze_pcb_layout(pcb_path, summary)
            pcb_analysis_report = format_pcb_analysis_report(pcb_analysis)
            print(f"  DRC violations: {pcb_analysis_report.get('summary', {}).get('total_violations', 'unknown')}")
        except Exception as e:
            print(f"  PCB analysis failed: {e}")

    # Final report
    step_num = 8 if pcb_analysis_report else 7
    print(f"\nStep {step_num}: Generating final report...")
    report = generate_final_report(
        str(schematic_path),
        llm_analysis,
        analysis_results,
        detected,
        analysis_method,
        pcb_analysis_report=pcb_analysis_report
    )

    output_json = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"\nReport saved to: {args.output}")
    else:
        print("\n" + "=" * 80)
        print("ANALYSIS REPORT")
        print("=" * 80)
        print(output_json)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Circuit Type: {report['circuit_analysis']['circuit_type']}")
    print(f"Analysis Method: {analysis_method}")
    print(f"Overall Risk: {report['overall_risk']['level'].upper()} ({report['overall_risk']['score']}/100)")
    print(f"Total Issues: {report['overall_risk']['total_issues']}")
    print(f"Critical Issues: {report['overall_risk']['critical_issues']}")
    print(f"Can Attempt Bringup: {'YES' if report['overall_risk']['can_attempt_bringup'] else 'NO'}")

    if pcb_analysis_report:
        print("\nPCB Layout Summary:")
        bi = pcb_analysis_report.get("board_info", {}).get("size_mm", {})
        print(f"  Size: {bi.get('width','?')}x{bi.get('height','?')} mm")
        print(f"  DRC Violations: {pcb_analysis_report.get('summary', {}).get('total_violations','?')}")

    if not report['overall_risk']['can_attempt_bringup']:
        print("\nBLOCKERS:")
        for blocker in report['overall_risk']['blockers']:
            print(f"  - {blocker}")


if __name__ == "__main__":
    main()
