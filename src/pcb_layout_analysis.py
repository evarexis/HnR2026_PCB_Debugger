# src/pcb_layout_analysis.py
"""
PCB Layout Analysis - Analyzes .kicad_pcb files for layout issues
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import re


@dataclass
class TraceAnalysis:
    """Analysis of trace routing"""
    net_name: str
    trace_count: int
    min_width: float  # mm
    max_width: float  # mm
    total_length: float  # mm
    layer: str
    issues: List[str] = field(default_factory=list)


@dataclass
class ViaAnalysis:
    """Analysis of vias"""
    total_count: int
    size_distribution: Dict[float, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class ClearanceIssue:
    """Clearance violation"""
    severity: str  # critical, high, medium, low
    item1: str
    item2: str
    actual_clearance: float  # mm
    required_clearance: float  # mm
    location: Optional[Tuple[float, float]] = None


@dataclass
class PCBLayoutAnalysis:
    """Complete PCB layout analysis results"""
    board_size: Tuple[float, float]  # width, height in mm
    layer_count: int
    trace_analysis: List[TraceAnalysis] = field(default_factory=list)
    via_analysis: Optional[ViaAnalysis] = None
    clearance_issues: List[ClearanceIssue] = field(default_factory=list)
    drc_violations: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


def parse_kicad_pcb(pcb_path: str | Path) -> Dict[str, Any]:
    """
    Parse KiCad PCB file (.kicad_pcb) S-expression format.
    Returns structured data about the PCB layout.
    """
    try:
        from sexpdata import loads, Symbol
    except ImportError:
        raise ImportError("sexpdata required for PCB parsing. Run: pip install sexpdata")
    
    pcb_path = Path(pcb_path)
    if not pcb_path.exists():
        raise FileNotFoundError(f"PCB file not found: {pcb_path}")
    
    text = pcb_path.read_text(encoding='utf-8', errors='ignore')
    tree = loads(text)
    
    # Normalize symbols to strings
    def normalize(obj):
        if isinstance(obj, Symbol):
            return str(obj)
        if isinstance(obj, list):
            return [normalize(x) for x in obj]
        return obj
    
    return normalize(tree)


def analyze_pcb_layout(pcb_path: str | Path, schematic_summary: Optional[Dict] = None) -> PCBLayoutAnalysis:
    """
    Analyze PCB layout for common issues and design rule violations.
    
    Args:
        pcb_path: Path to .kicad_pcb file
        schematic_summary: Optional schematic data for cross-checking
    
    Returns:
        PCBLayoutAnalysis with all findings
    """
    print(f"Analyzing PCB layout: {pcb_path}")
    
    try:
        tree = parse_kicad_pcb(pcb_path)
    except Exception as e:
        print(f"Error parsing PCB file: {e}")
        return PCBLayoutAnalysis(
            board_size=(0, 0),
            layer_count=0,
            recommendations=[f"Failed to parse PCB file: {e}"]
        )
    
    analysis = PCBLayoutAnalysis(
        board_size=(0, 0),
        layer_count=2  # Default
    )
    
    # Extract board dimensions
    board_size = _extract_board_size(tree)
    analysis.board_size = board_size
    
    # Extract layer count
    layer_count = _extract_layer_count(tree)
    analysis.layer_count = layer_count
    
    # Analyze traces
    trace_analysis = _analyze_traces(tree)
    analysis.trace_analysis = trace_analysis
    
    # Analyze vias
    via_analysis = _analyze_vias(tree)
    analysis.via_analysis = via_analysis
    
    # Check clearances
    clearance_issues = _check_clearances(tree)
    analysis.clearance_issues = clearance_issues
    
    # Run DRC checks
    drc_violations = _run_drc_checks(tree, analysis)
    analysis.drc_violations = drc_violations
    
    # Generate statistics
    stats = {
        "board_area_mm2": board_size[0] * board_size[1],
        "total_traces": sum(t.trace_count for t in trace_analysis),
        "total_vias": via_analysis.total_count if via_analysis else 0,
        "clearance_violations": len(clearance_issues),
        "drc_violations": len(drc_violations),
        "layers": layer_count
    }
    analysis.statistics = stats
    
    # Generate recommendations
    recommendations = _generate_recommendations(analysis)
    analysis.recommendations = recommendations
    
    return analysis


def _extract_board_size(tree: list) -> Tuple[float, float]:
    """Extract board dimensions from edge cuts"""
    # Look for edge.cuts layer drawings
    width, height = 100.0, 100.0  # Default
    
    try:
        # Find all segments on Edge.Cuts layer
        x_coords, y_coords = [], []
        
        def find_coords(node):
            if isinstance(node, list) and len(node) > 0:
                if node[0] == 'gr_line' or node[0] == 'segment':
                    # Check if on Edge.Cuts
                    for item in node:
                        if isinstance(item, list) and item[0] == 'layer' and 'Edge.Cuts' in str(item):
                            # Extract start and end points
                            for sub in node:
                                if isinstance(sub, list) and sub[0] == 'start':
                                    x_coords.append(float(sub[1]))
                                    y_coords.append(float(sub[2]))
                                elif isinstance(sub, list) and sub[0] == 'end':
                                    x_coords.append(float(sub[1]))
                                    y_coords.append(float(sub[2]))
                
                for item in node:
                    if isinstance(item, list):
                        find_coords(item)
        
        find_coords(tree)
        
        if x_coords and y_coords:
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
    except:
        pass
    
    return (round(width, 2), round(height, 2))


def _extract_layer_count(tree: list) -> int:
    """Extract number of copper layers"""
    layer_count = 2  # Default to 2-layer
    
    try:
        def find_layers(node):
            if isinstance(node, list) and len(node) > 0:
                if node[0] == 'layers':
                    # Count copper layers
                    copper_layers = [item for item in node if isinstance(item, list) 
                                   and len(item) > 1 and '.Cu' in str(item[1])]
                    return len(copper_layers)
                
                for item in node:
                    if isinstance(item, list):
                        result = find_layers(item)
                        if result:
                            return result
            return None
        
        result = find_layers(tree)
        if result:
            layer_count = result
    except:
        pass
    
    return layer_count


def _analyze_traces(tree: list) -> List[TraceAnalysis]:
    """Analyze PCB traces by net"""
    trace_map = {}
    
    try:
        def find_segments(node):
            if isinstance(node, list) and len(node) > 0:
                if node[0] == 'segment':
                    net_name = "unknown"
                    width = 0.2  # Default
                    layer = "F.Cu"
                    
                    for item in node:
                        if isinstance(item, list):
                            if item[0] == 'net' and len(item) > 1:
                                net_name = str(item[1])
                            elif item[0] == 'width' and len(item) > 1:
                                width = float(item[1])
                            elif item[0] == 'layer' and len(item) > 1:
                                layer = str(item[1])
                    
                    if net_name not in trace_map:
                        trace_map[net_name] = {
                            'count': 0,
                            'widths': [],
                            'layers': set(),
                            'issues': []
                        }
                    
                    trace_map[net_name]['count'] += 1
                    trace_map[net_name]['widths'].append(width)
                    trace_map[net_name]['layers'].add(layer)
                
                for item in node:
                    if isinstance(item, list):
                        find_segments(item)
        
        find_segments(tree)
    except:
        pass
    
    # Convert to TraceAnalysis objects
    analyses = []
    for net_name, data in trace_map.items():
        if data['widths']:
            issues = []
            min_width = min(data['widths'])
            max_width = max(data['widths'])
            
            # Check for very thin traces (< 0.15mm)
            if min_width < 0.15:
                issues.append(f"Trace width {min_width}mm is very thin (< 0.15mm), may be hard to manufacture")
            
            # Check for power traces that are too thin
            if any(kw in net_name.upper() for kw in ['VDD', 'VCC', 'GND', 'POWER', '3V3', '5V']):
                if max_width < 0.3:
                    issues.append(f"Power trace '{net_name}' width {max_width}mm may be too thin, recommend >= 0.3mm")
            
            analyses.append(TraceAnalysis(
                net_name=net_name,
                trace_count=data['count'],
                min_width=round(min_width, 3),
                max_width=round(max_width, 3),
                total_length=0,  # Would need to calculate from coordinates
                layer=', '.join(data['layers']),
                issues=issues
            ))
    
    return analyses


def _analyze_vias(tree: list) -> ViaAnalysis:
    """Analyze vias in the PCB"""
    via_count = 0
    via_sizes = []
    issues = []
    
    try:
        def find_vias(node):
            nonlocal via_count
            if isinstance(node, list) and len(node) > 0:
                if node[0] == 'via':
                    via_count += 1
                    size = 0.8  # Default
                    
                    for item in node:
                        if isinstance(item, list) and item[0] == 'size' and len(item) > 1:
                            size = float(item[1])
                            via_sizes.append(size)
                
                for item in node:
                    if isinstance(item, list):
                        find_vias(item)
        
        find_vias(tree)
        
        # Check for very small vias
        if via_sizes and min(via_sizes) < 0.3:
            issues.append(f"Very small via detected ({min(via_sizes)}mm), may be difficult to manufacture")
    except:
        pass
    
    size_dist = {}
    for size in via_sizes:
        size_dist[size] = size_dist.get(size, 0) + 1
    
    return ViaAnalysis(
        total_count=via_count,
        size_distribution=size_dist,
        issues=issues
    )


def _check_clearances(tree: list) -> List[ClearanceIssue]:
    """Check for clearance violations"""
    issues = []
    
    # This is simplified - full implementation would check actual distances
    # between all copper features
    
    # For now, we can check if traces are very close based on design rules
    # Real implementation would parse coordinates and calculate distances
    
    return issues


def _run_drc_checks(tree: list, analysis: PCBLayoutAnalysis) -> List[Dict[str, Any]]:
    """
    Run Design Rule Checks on the PCB.
    Returns list of DRC violations.
    """
    violations = []
    
    # Check 1: Minimum trace width
    for trace in analysis.trace_analysis:
        if trace.min_width < 0.127:  # 5 mil minimum for most fabs
            violations.append({
                "type": "trace_width",
                "severity": "critical",
                "description": f"Trace '{trace.net_name}' width {trace.min_width}mm below minimum (0.127mm)",
                "location": trace.net_name,
                "recommendation": "Increase trace width to at least 0.127mm (5 mil)"
            })
    
    # Check 2: Board size
    if analysis.board_size[0] > 300 or analysis.board_size[1] > 300:
        violations.append({
            "type": "board_size",
            "severity": "medium",
            "description": f"Board size {analysis.board_size[0]}x{analysis.board_size[1]}mm is quite large",
            "recommendation": "Consider splitting into smaller boards if possible to reduce cost"
        })
    
    # Check 3: Via size
    if analysis.via_analysis and analysis.via_analysis.size_distribution:
        min_via = min(analysis.via_analysis.size_distribution.keys())
        if min_via < 0.3:
            violations.append({
                "type": "via_size",
                "severity": "high",
                "description": f"Via size {min_via}mm is very small, may increase manufacturing cost",
                "recommendation": "Use vias >= 0.3mm diameter for standard manufacturing"
            })
    
    # Check 4: Power trace width
    for trace in analysis.trace_analysis:
        if any(kw in trace.net_name.upper() for kw in ['VDD', 'VCC', 'GND', 'POWER', '3V3', '5V']):
            if trace.max_width < 0.254:  # 10 mil
                violations.append({
                    "type": "power_trace",
                    "severity": "high",
                    "description": f"Power trace '{trace.net_name}' width {trace.max_width}mm may be insufficient",
                    "recommendation": "Power/ground traces should be >= 0.254mm (10 mil) wide"
                })
    
    return violations


def _generate_recommendations(analysis: PCBLayoutAnalysis) -> List[str]:
    """Generate layout improvement recommendations"""
    recommendations = []
    
    # Board size recommendations
    area = analysis.board_size[0] * analysis.board_size[1]
    if area < 100:
        recommendations.append("Small board - good for prototyping")
    elif area > 10000:
        recommendations.append("Large board - consider panelization for production")
    
    # Layer recommendations
    if analysis.layer_count == 2:
        recommendations.append("2-layer board - adequate for simple designs")
    elif analysis.layer_count >= 4:
        recommendations.append(f"{analysis.layer_count}-layer board - good for complex designs with controlled impedance")
    
    # Trace recommendations
    power_traces = [t for t in analysis.trace_analysis 
                   if any(kw in t.net_name.upper() for kw in ['VDD', 'VCC', 'GND', 'POWER'])]
    if power_traces:
        max_power_width = max(t.max_width for t in power_traces)
        if max_power_width >= 0.5:
            recommendations.append("Power traces are adequately sized")
        else:
            recommendations.append("Consider widening power traces to >= 0.5mm for better current handling")
    
    # Via recommendations
    if analysis.via_analysis and analysis.via_analysis.total_count > 100:
        recommendations.append(f"High via count ({analysis.via_analysis.total_count}) - may increase manufacturing time")
    
    # DRC recommendations
    if analysis.drc_violations:
        critical = [v for v in analysis.drc_violations if v['severity'] == 'critical']
        if critical:
            recommendations.append(f"Fix {len(critical)} critical DRC violations before manufacturing")
    
    return recommendations


def format_pcb_analysis_report(analysis: PCBLayoutAnalysis) -> Dict[str, Any]:
    """Format PCB analysis into structured report"""
    return {
        "board_info": {
            "size_mm": {
                "width": analysis.board_size[0],
                "height": analysis.board_size[1],
                "area": round(analysis.board_size[0] * analysis.board_size[1], 2)
            },
            "layers": analysis.layer_count
        },
        "trace_statistics": {
            "total_nets": len(analysis.trace_analysis),
            "total_segments": sum(t.trace_count for t in analysis.trace_analysis),
            "power_nets": [
                {
                    "net": t.net_name,
                    "min_width_mm": t.min_width,
                    "max_width_mm": t.max_width,
                    "issues": t.issues
                }
                for t in analysis.trace_analysis 
                if any(kw in t.net_name.upper() for kw in ['VDD', 'VCC', 'GND', 'POWER', '3V3', '5V'])
            ]
        },
        "via_statistics": {
            "total_count": analysis.via_analysis.total_count if analysis.via_analysis else 0,
            "size_distribution": analysis.via_analysis.size_distribution if analysis.via_analysis else {},
            "issues": analysis.via_analysis.issues if analysis.via_analysis else []
        },
        "drc_violations": analysis.drc_violations,
        "clearance_issues": [
            {
                "severity": issue.severity,
                "description": f"{issue.item1} to {issue.item2}: {issue.actual_clearance}mm (required: {issue.required_clearance}mm)"
            }
            for issue in analysis.clearance_issues
        ],
        "recommendations": analysis.recommendations,
        "summary": {
            "total_violations": len(analysis.drc_violations),
            "critical_violations": len([v for v in analysis.drc_violations if v['severity'] == 'critical']),
            "manufacturing_ready": len([v for v in analysis.drc_violations if v['severity'] == 'critical']) == 0
        }
    }