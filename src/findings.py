#src/findings_enhanced.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from src.netlist_build import NetBuildResult
from src.kicad_extract import Schematic

@dataclass
class Finding:
    id: str
    severity: str  # low/medium/high/critical
    summary: str
    why: str
    evidence: Dict[str, Any]
    fix_suggestion: Optional[str] = None
    prevents_bringup: bool = False
    schematic_location: Optional[str] = None

def analyze_power_connectivity(sch: Schematic, net_build: NetBuildResult, power_nets: List[str]) -> List[Finding]:
    """Analyze power distribution issues"""
    findings = []
    
    # Check if power labels are actually connected
    power_labels = [l for l in sch.labels if l.text in power_nets]
    
    for label in power_labels:
        if not label.at:
            continue
            
        # Check if label position is in label_attached mapping
        is_connected = label.at in net_build.label_attached
        
        if not is_connected:
            # Try to identify what this power net should connect to
            nearby_symbols = [s for s in sch.symbols 
                            if s.at and label.at and 
                            abs(s.at[0] - label.at[0]) < 50 and 
                            abs(s.at[1] - label.at[1]) < 50]
            
            location_hint = ""
            if nearby_symbols:
                refs = ', '.join([s.ref for s in nearby_symbols[:3]])
                location_hint = f"Near components: {refs}"
            
            findings.append(Finding(
                id="power_net_disconnected",
                severity="critical",
                summary=f'Power net "{label.text}" label is not connected to circuit',
                why=f"The {label.text} label at position {label.at} doesn't connect to any wire. "
                    "This means power won't reach components expecting this net.",
                evidence={
                    "label": label.text,
                    "position": label.at,
                    "nearby_components": [s.ref for s in nearby_symbols] if nearby_symbols else []
                },
                fix_suggestion=f"Draw a wire from the {label.text} label to the intended power source or IC pin. "
                              f"In KiCad, labels must physically touch a wire or junction point.",
                prevents_bringup=True,
                schematic_location=location_hint or f"Position ({label.at[0]}, {label.at[1]})"
            ))
    
    return findings

def analyze_ic_power_pins(sch: Schematic, net_build: NetBuildResult, power_nets: List[str]) -> List[Finding]:
    """Check if ICs have their power pins properly connected"""
    findings = []
    
    # Find all ICs (components starting with U)
    ics = [s for s in sch.symbols if s.ref.startswith('U') and '?' not in s.ref]
    
    for ic in ics:
        # Simplified check - in production, would parse actual pin connections
        # For now, check if there's a power net label near the IC
        
        if not ic.at:
            continue
        
        nearby_power_labels = [
            l for l in sch.labels 
            if l.text in power_nets and l.at and
            abs(l.at[0] - ic.at[0]) < 100 and 
            abs(l.at[1] - ic.at[1]) < 100
        ]
        
        if not nearby_power_labels:
            findings.append(Finding(
                id="ic_missing_power_connection",
                severity="high",
                summary=f"No visible power connection to {ic.ref} ({ic.value})",
                why=f"IC {ic.ref} doesn't have any power net labels nearby. "
                    "This might indicate missing VDD/GND connections.",
                evidence={
                    "component": ic.ref,
                    "value": ic.value,
                    "position": ic.at,
                    "expected_nets": power_nets
                },
                fix_suggestion=f"Connect {ic.ref} power pins to appropriate power rails. "
                              f"Check datasheet for VDD/VCC/GND pin numbers and wire them to {', '.join(power_nets[:2])}.",
                prevents_bringup=True,
                schematic_location=f"{ic.ref} at ({ic.at[0]}, {ic.at[1]})"
            ))
    
    return findings

def analyze_critical_signal_paths(sch: Schematic, net_build: NetBuildResult) -> List[Finding]:
    """Analyze critical signal connectivity issues"""
    findings = []
    
    # Check for floating output signals
    output_labels = [l for l in sch.labels if 'OUT' in l.text.upper()]
    
    for label in output_labels:
        if not label.at:
            continue
            
        is_connected = label.at in net_build.label_attached
        
        if not is_connected:
            findings.append(Finding(
                id="output_signal_floating",
                severity="high",
                summary=f'Output signal "{label.text}" is not connected',
                why="This output label doesn't connect to any wire, meaning the signal can't be measured or used.",
                evidence={
                    "label": label.text,
                    "position": label.at
                },
                fix_suggestion=f"Connect {label.text} label to the actual output pin of the driving component. "
                              "Add a test point or connector to access this signal.",
                prevents_bringup=False,
                schematic_location=f"Position ({label.at[0]}, {label.at[1]})"
            ))
    
    return findings

def analyze_findings(net_build: NetBuildResult, sch: Schematic = None, power_nets: List[str] = None) -> List[Finding]:
    """Enhanced findings analysis with root cause identification"""
    findings: List[Finding] = []
    
    # A) Unattached labels (enhanced version)
    for text, pos in net_build.label_unattached:
        severity = "high"
        prevents_bringup = False
        fix_suggestion = f'Ensure the "{text}" label touches a wire or junction point.'
        
        # Determine if this is critical
        if power_nets and text in power_nets:
            severity = "critical"
            prevents_bringup = True
            fix_suggestion = f'CRITICAL: Power net "{text}" must be connected! ' + fix_suggestion
        elif "OUT" in text.upper() or "CLK" in text.upper():
            severity = "high"
            fix_suggestion = f'Important signal "{text}" should be connected. ' + fix_suggestion
        
        findings.append(Finding(
            id="label_unattached",
            severity=severity,
            summary=f'Label "{text}" is not connected to any wire node',
            why="In KiCad, a label must physically touch a wire or junction. "
                "If it's floating, the net may be broken or misnamed, causing the signal to not propagate.",
            evidence={"label": text, "pos": pos},
            fix_suggestion=fix_suggestion,
            prevents_bringup=prevents_bringup,
            schematic_location=f"Position ({pos[0]}, {pos[1]})"
        ))
    
    # B) Too many unnamed nets
    unnamed = [n.name for n in net_build.nets if n.name.startswith("NET_UNNAMED_")]
    if len(unnamed) >= 5:
        findings.append(Finding(
            id="many_unnamed_nets",
            severity="medium",
            summary=f"{len(unnamed)} unnamed nets found",
            why="Usually indicates missing labels or fragmented wiring. "
                "During debugging, you won't be able to identify these nets by name, making troubleshooting harder.",
            evidence={"count": len(unnamed), "examples": unnamed[:5]},
            fix_suggestion="Add descriptive labels to signal nets. "
                          "Even simple names like 'SENSOR_OUT', 'LED_CTRL' help during debugging. "
                          "Use global labels for nets that cross multiple sheets.",
            prevents_bringup=False
        ))
    
    # C) Power connectivity analysis (if schematic and power nets provided)
    if sch and power_nets:
        findings.extend(analyze_power_connectivity(sch, net_build, power_nets))
        findings.extend(analyze_ic_power_pins(sch, net_build, power_nets))
        findings.extend(analyze_critical_signal_paths(sch, net_build))
    
    # D) Check for potential ERC violations
    # Look for nets with only one connection (likely broken)
    for net in net_build.nets:
        if len(net.nodes) == 1 and not net.name.startswith("NET_UNNAMED"):
            findings.append(Finding(
                id="single_node_net",
                severity="medium",
                summary=f'Net "{net.name}" has only one connection point',
                why="A net with only one node is likely incomplete - signals need at least a source and destination.",
                evidence={
                    "net": net.name,
                    "node_count": len(net.nodes),
                    "position": list(net.nodes)[0] if net.nodes else None
                },
                fix_suggestion=f"Verify {net.name} connects to both its source and destination. "
                              "Check for missing wires or disconnected pins.",
                prevents_bringup=False
            ))
    
    return findings