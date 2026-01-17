# src/export.py
"""Export functionality for bring-up checklists"""

import json
from pathlib import Path
from typing import Dict, Any


def export_checklist_markdown(report: Dict[str, Any], output_path: str) -> None:
    """Export checklist to Markdown format"""
    
    lines = []
    
    # Header
    lines.append(f"# PCB Bring-Up Checklist\n")
    lines.append(f"**Schematic:** {Path(report['file']).name}\n")
    lines.append(f"**Overall Risk:** {report['overall_risk']['level'].upper()} "
                f"(Score: {report['overall_risk']['score']}/100)\n")
    
    # Detection Summary
    lines.append("\n## Detection Summary\n")
    detected = report.get('detected', {})
    
    if detected.get('power_nets'):
        lines.append(f"**Power Nets:** {', '.join(detected['power_nets'])}\n")
    if detected.get('mcu_symbols'):
        lines.append(f"**MCU/Main IC:** {', '.join(detected['mcu_symbols'])}\n")
    if detected.get('clock_sources'):
        lines.append(f"**Clock Sources:** {', '.join(detected['clock_sources'])}\n")
    if detected.get('reset_nets'):
        lines.append(f"**Reset Nets:** {', '.join(detected['reset_nets'])}\n")
    if detected.get('debug_ifaces'):
        lines.append(f"**Debug Interfaces:** {', '.join(detected['debug_ifaces'])}\n")
    
    # Findings/Issues
    if report.get('findings'):
        lines.append("\n## ⚠️ Critical Findings\n")
        for finding in report['findings']:
            severity_icon = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(finding.get('severity', 'medium'), '⚪')
            
            lines.append(f"\n### {severity_icon} {finding['summary']}\n")
            lines.append(f"**Why:** {finding['why']}\n")
            if finding.get('fix_suggestion'):
                lines.append(f"**Fix:** {finding['fix_suggestion']}\n")
            if finding.get('prevents_bringup'):
                lines.append(f"**BLOCKS BRING-UP**\n")
    
    # Checklist Steps
    lines.append("\n## Bring-Up Checklist\n")
    lines.append("Follow these steps in order. Mark each as you complete it.\n")
    
    for step in report.get('checklist', []):
        risk_badge = {
            'low': '🟢 LOW',
            'medium': '🟡 MED',
            'high': '🔴 HIGH'
        }.get(step.get('risk', 'medium'), '⚪')
        
        lines.append(f"\n### [{step['sequence']}] {step['title']} - {risk_badge} RISK\n")
        lines.append(f"**Category:** {step['category'].upper()}\n")
        
        if step.get('component'):
            lines.append(f"**Component:** {step['component']}\n")
        
        lines.append(f"\n**Test Procedure:**\n{step['instruction']}\n")
        lines.append(f"\n**Expected Result:**\n{step['expected']}\n")
        
        # Checkbox for manual tracking
        lines.append(f"\n- [ ] Test Complete\n")
        lines.append(f"- [ ] Result: PASS / FAIL\n")
        
        if step.get('likely_faults'):
            lines.append(f"\n**If This Step Fails - Likely Causes:**\n")
            for fault in step['likely_faults']:
                lines.append(f"- {fault}\n")
        
        if step.get('fix_suggestions'):
            lines.append(f"\n**Troubleshooting Steps:**\n")
            for fix in step['fix_suggestions']:
                lines.append(f"1. {fix}\n")
        
        if step.get('prevents_bringup'):
            lines.append(f"\n> **CRITICAL**: This step must pass for the board to function.\n")
        
        lines.append("\n---\n")
    
    # Test Points Recommendations
    if report.get('recommended_test_points'):
        lines.append("\n## Recommended Test Points\n")
        for tp in report['recommended_test_points']:
            lines.append(f"\n**{tp['net']}**\n")
            lines.append(f"- Why: {tp['why']}\n")
            lines.append(f"- Measurement: {tp['measurement']}\n")
    
    # Oscilloscope Configuration
    if report.get('scope_config'):
        scope = report['scope_config']
        lines.append("\n##Oscilloscope Setup\n")
        lines.append(f"**Circuit Type:** {scope['circuit_type']}\n")
        lines.append(f"**Timebase:** {scope.get('timebase', 'Auto')}\n")
        
        for ch in scope.get('channels', []):
            lines.append(f"\n**Channel {ch['ch']}:**\n")
            lines.append(f"- Probe: {ch['probe']}\n")
            lines.append(f"- Scale: {ch['scale']}\n")
            lines.append(f"- Coupling: {ch['coupling']}\n")
        
        if scope.get('expected_waveform'):
            wf = scope['expected_waveform']
            lines.append(f"\n**Expected Waveform:**\n")
            lines.append(f"- Frequency: {wf['frequency_hz']} Hz\n")
            lines.append(f"- Period: {wf['period_ms']} ms\n")
            lines.append(f"- Duty Cycle: {wf['duty_cycle_pct']}%\n")
    
    # Notes
    if report.get('notes'):
        lines.append("\n## Additional Notes\n")
        for note in report['notes']:
            lines.append(f"- {note}\n")
    
    # Write to file
    Path(output_path).write_text(''.join(lines), encoding='utf-8')


def export_checklist_json(report: Dict[str, Any], output_path: str) -> None:
    """Export full report to JSON format"""
    Path(output_path).write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )