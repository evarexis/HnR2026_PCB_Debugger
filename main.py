#!/usr/bin/env python3
"""
PCB Debugger - AI-Powered Schematic Analysis
Analyzes KiCad schematics and generates debugging checklists
"""
from __future__ import annotations
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Import existing modules
from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors

# Import new modules
from src.schematic_summary import generate_schematic_summary
from src.llm_analysis import LLMAnalyzer, LLMProvider
from src.analysis import execute_analysis_function, AnalysisResult


def run_heuristic_analysis(sch, net_build, detected) -> Dict[str, Any]:
    """
    Fallback heuristic analysis when LLM is unavailable.
    Returns same structure as LLM but with simpler logic.
    """
    print("Running heuristic-based analysis...")
    
    # Determine circuit type based on components
    circuit_type = "unknown"
    main_ic = None
    critical_components = []
    
    for sym in sch.symbols:
        if '?' in sym.ref:
            continue
        
        if sym.ref.startswith('U'):
            main_ic = sym.ref
            critical_components.append(sym.ref)
            
            if '555' in sym.lib_id.lower():
                circuit_type = "555_timer_astable"
            elif any(kw in sym.lib_id.lower() for kw in ['stm32', 'esp32', 'atmega']):
                circuit_type = "microcontroller_basic"
        
        # Add timing components for 555
        if circuit_type == "555_timer_astable":
            if sym.ref.startswith('R') or sym.ref.startswith('C'):
                critical_components.append(sym.ref)
    
    # Build analysis pipeline based on circuit type
    analysis_pipeline = []
    
    # Always check power first
    if detected.power_nets:
        analysis_pipeline.append({
            "function": "verify_power_connectivity",
            "params": {
                "power_nets": detected.power_nets,
                "ic_ref": main_ic,
                "power_pins": ["8"] if circuit_type == "555_timer_astable" else [],
                "gnd_pins": ["1"] if circuit_type == "555_timer_astable" else []
            },
            "priority": "critical",
            "reason": "Power must be connected for any circuit to function"
        })
    
    # Circuit-specific analysis
    if circuit_type == "555_timer_astable":
        # Look for R1, R2, C1 components
        r1 = next((s.ref for s in sch.symbols if 'R1' in s.ref), None)
        r2 = next((s.ref for s in sch.symbols if 'R2' in s.ref), None)
        c1 = next((s.ref for s in sch.symbols if 'C1' in s.ref), None)
        
        if r1 and r2 and c1:
            analysis_pipeline.append({
                "function": "analyze_rc_timing_network",
                "params": {
                    "ic_ref": main_ic,
                    "r1": r1,
                    "r2": r2,
                    "c1": c1,
                    "pins": {"discharge": "7", "threshold": "6", "trigger": "2"}
                },
                "priority": "high",
                "reason": "RC timing network determines output frequency"
            })
        
        # Check reset pin
        analysis_pipeline.append({
            "function": "check_floating_pins",
            "params": {
                "ic_ref": main_ic,
                "critical_pins": ["4"],
                "expected_state": "HIGH"
            },
            "priority": "critical",
            "reason": "Reset pin must be high for timer to operate"
        })
    
    elif circuit_type == "microcontroller_basic":
        # MCU-specific checks
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
                "reason": "External crystal required for MCU clock"
            })
        
        if detected.reset_nets:
            analysis_pipeline.append({
                "function": "analyze_reset_circuit",
                "params": {
                    "mcu_ref": main_ic,
                    "reset_net": detected.reset_nets[0],
                    "has_external_reset": True,
                    "pullup_required": True
                },
                "priority": "high",
                "reason": "Reset circuit needed for MCU programming and operation"
            })
    
    # Always check decoupling caps
    if main_ic:
        analysis_pipeline.append({
            "function": "analyze_decoupling_capacitors",
            "params": {
                "ic_refs": [main_ic],
                "proximity_threshold": 50
            },
            "priority": "medium",
            "reason": "Decoupling caps reduce power noise"
        })
    
    # Detect issues from netlist
    detected_issues = []
    
    for label_text, label_pos in net_build.label_unattached:
        severity = "critical" if label_text in detected.power_nets else "high"
        detected_issues.append({
            "issue": f"label_{label_text}_unattached",
            "severity": severity,
            "analysis_needed": ["trace_signal_path"],
            "components_involved": [label_text],
            "reason": f"Label {label_text} not connected to any wire",
            "debug_step": f"Draw wire to connect {label_text} label at position ({label_pos[0]}, {label_pos[1]})"
        })
    
    # Build verification steps
    verification_steps_issues = []
    verification_steps_general = []
    
    step_num = 1
    for issue in detected_issues:
        verification_steps_issues.append({
            "step": step_num,
            "action": f"Fix {issue['issue']}",
            "expected": "Label connected to circuit",
            "target": issue['issue']
        })
        step_num += 1
    
    # General workability steps
    verification_steps_general = [
        {
            "step": 1,
            "action": "Apply power to circuit",
            "expected": "No smoke, correct voltage on power rails"
        },
        {
            "step": 2,
            "action": "Measure output signal",
            "expected": "Expected waveform/behavior observed"
        }
    ]
    
    return {
        "circuit_analysis": {
            "circuit_type": circuit_type,
            "purpose": "Generate output based on components detected",
            "confidence": 0.6,  # Lower confidence for heuristics
            "main_ic": main_ic,
            "critical_components": critical_components
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


def run_analysis_pipeline(
    llm_analysis: Dict[str, Any],
    sch,
    net_build
) -> List[Dict[str, Any]]:
    """
    Execute all analysis functions recommended by LLM or heuristics.
    Returns list of analysis results.
    """
    analysis_pipeline = llm_analysis.get('analysis', [])
    results = []
    
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
    analysis_method: str
) -> Dict[str, Any]:
    """
    Generate comprehensive debugging report.
    """
    # Compile all issues
    all_issues = list(llm_analysis.get('detected_issues', []))
    
    # Add issues from analysis results
    for result in analysis_results:
        if result['issues']:
            for issue in result['issues']:
                all_issues.append({
                    "issue": f"{result['function']}_issue",
                    "severity": result['severity'],
                    "analysis_needed": [result['function']],
                    "components_involved": [],
                    "reason": issue,
                    "debug_step": " | ".join(result['recommendations']) if result['recommendations'] else ""
                })
    
    # Calculate overall risk
    critical_count = sum(1 for issue in all_issues if issue['severity'] == 'critical')
    high_count = sum(1 for issue in all_issues if issue['severity'] == 'high')
    
    blockers = [issue for issue in all_issues if issue['severity'] == 'critical']
    blocker_count = len(blockers)
    
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
    
    can_attempt_bringup = (blocker_count == 0)
    
    # Build comprehensive report
    report = {
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
            "blockers": [b['reason'] for b in blockers[:5]],  # Top 5 blockers
            "can_attempt_bringup": can_attempt_bringup
        },
        
        "summary": {
            "total_components": len([s for s in detected.mcu_symbols]) if detected.mcu_symbols else 0,
            "power_nets_detected": detected.power_nets,
            "clock_sources_detected": detected.clock_sources,
            "debug_interfaces": detected.debug_ifaces
        }
    }
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description="PCB Debugger - Analyze KiCad schematics and generate debugging checklists"
    )
    parser.add_argument(
        'schematic',
        type=str,
        help='Path to .kicad_sch file'
    )
    parser.add_argument(
        '--llm',
        type=str,
        choices=['openai', 'gemini', 'heuristic'],
        default='openai',
        help='Primary LLM provider (default: openai)'
    )
    parser.add_argument(
        '--fallback',
        type=str,
        choices=['openai', 'gemini', 'heuristic'],
        default='gemini',
        help='Fallback LLM provider (default: gemini)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON file path (default: stdout)'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    schematic_path = Path(args.schematic)
    if not schematic_path.exists():
        print(f"Error: File not found: {schematic_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Analyzing schematic: {schematic_path}")
    print(f"Primary LLM: {args.llm}, Fallback: {args.fallback}\n")
    
    # Parse schematic
    print("Step 1: Parsing schematic...")
    tree = parse_kicad_sch(schematic_path)
    sch = parse_schematic(tree)
    print(f"  Found {len(sch.symbols)} components, {len(sch.wires)} wires, {len(sch.labels)} labels")
    
    # Build netlist
    print("\nStep 2: Building netlist...")
    net_build = build_nets(sch, label_tolerance=2)
    print(f"  Generated {len(net_build.nets)} nets")
    print(f"  Unattached labels: {len(net_build.label_unattached)}")
    
    # Run detectors
    print("\nStep 3: Running component detectors...")
    detected = run_detectors(sch, net_build.nets)
    print(f"  Power nets: {detected.power_nets}")
    print(f"  Main ICs: {detected.mcu_symbols if detected.mcu_symbols else 'None detected'}")
    
    # Generate schematic summary
    print("\nStep 4: Generating schematic summary for LLM...")
    summary = generate_schematic_summary(sch, net_build)
    print(f"  Summary size: {len(json.dumps(summary))} characters")
    
    # Initialize LLM analyzer with user's choices
    llm_provider_map = {
        'openai': LLMProvider.OPENAI,
        'gemini': LLMProvider.GEMINI,
        'heuristic': LLMProvider.HEURISTIC
    }
    
    primary = llm_provider_map[args.llm]
    fallback = llm_provider_map[args.fallback]
    
    analyzer = LLMAnalyzer(primary=primary, secondary=fallback)
    
    # Analyze with LLM or fallback to heuristics
    print(f"\nStep 5: Analyzing circuit with {args.llm}...")
    llm_analysis = analyzer.analyze_schematic(summary)
    
    analysis_method = analyzer.used_provider.value if analyzer.used_provider else "unknown"
    
    if llm_analysis is None:
        # Complete fallback to heuristics
        llm_analysis = run_heuristic_analysis(sch, net_build, detected)
        analysis_method = "heuristic"
    
    print(f"  Analysis method: {analysis_method}")
    print(f"  Circuit type: {llm_analysis['circuit_analysis']['circuit_type']}")
    print(f"  Confidence: {llm_analysis['circuit_analysis']['confidence']}")
    
    # Execute analysis pipeline
    print("\nStep 6: Executing analysis functions...")
    analysis_results = run_analysis_pipeline(llm_analysis, sch, net_build)
    
    # Generate final report
    print("\nStep 7: Generating final report...")
    report = generate_final_report(
        schematic_path,
        llm_analysis,
        analysis_results,
        detected,
        analysis_method
    )
    
    # Output results
    output_json = json.dumps(report, indent=2)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json)
        print(f"\nReport saved to: {output_path}")
    else:
        print("\n" + "="*80)
        print("ANALYSIS REPORT")
        print("="*80)
        print(output_json)
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Circuit Type: {report['circuit_analysis']['circuit_type']}")
    print(f"Analysis Method: {analysis_method}")
    print(f"Overall Risk: {report['overall_risk']['level'].upper()} ({report['overall_risk']['score']}/100)")
    print(f"Total Issues: {report['overall_risk']['total_issues']}")
    print(f"Critical Issues: {report['overall_risk']['critical_issues']}")
    print(f"Can Attempt Bringup: {'YES' if report['overall_risk']['can_attempt_bringup'] else 'NO'}")
    
    if not report['overall_risk']['can_attempt_bringup']:
        print("\nBLOCKERS:")
        for blocker in report['overall_risk']['blockers']:
            print(f"  - {blocker}")


if __name__ == "__main__":
    main()