#src/component_analysis.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from src.kicad_extract import Schematic, SchSymbol, Point
from src.netlist_build import Net, NetBuildResult
import re

@dataclass
class PinConnection:
    """Represents a single pin connection"""
    component_ref: str
    pin_number: str
    pin_name: str
    net_name: str
    position: Optional[Point] = None

@dataclass
class ComponentAnalysis:
    """Detailed component-level analysis"""
    ref: str
    value: str
    lib_id: str
    position: Optional[Point]
    power_pins: List[PinConnection] = field(default_factory=list)
    ground_pins: List[PinConnection] = field(default_factory=list)
    signal_pins: List[PinConnection] = field(default_factory=list)
    unconnected_pins: List[str] = field(default_factory=list)
    nearby_caps: List[str] = field(default_factory=list)  # Decoupling caps
    issues: List[str] = field(default_factory=list)

@dataclass
class CircuitTopology:
    """High-level circuit topology analysis"""
    component_map: Dict[str, ComponentAnalysis]
    power_tree: Dict[str, List[str]]  # net -> components consuming it
    critical_paths: List[Dict[str, any]]
    missing_decoupling: List[str]  # Component refs missing decoupling caps
    floating_inputs: List[PinConnection]
    
def analyze_555_timer(comp: ComponentAnalysis, sch: Schematic, net_build: NetBuildResult) -> Dict:
    """Specific analysis for 555 timer circuits"""
    analysis = {
        "frequency_calc": None,
        "duty_cycle": None,
        "issues": [],
        "recommendations": []
    }
    
    # Find R and C values connected to 555
    r1 = r2 = c1 = None
    for sym in sch.symbols:
        if sym.ref.startswith('R') and sym.value:
            try:
                # Extract resistance value (handle k, K, M suffixes)
                val_str = sym.value.upper().replace('K', 'e3').replace('M', 'e6')
                val = float(re.sub(r'[^0-9.eE+-]', '', val_str))
                if 'R1' in sym.ref:
                    r1 = val
                elif 'R2' in sym.ref:
                    r2 = val
            except:
                pass
        elif sym.ref.startswith('C') and sym.value:
            try:
                val_str = sym.value.upper().replace('U', 'e-6').replace('N', 'e-9').replace('P', 'e-12')
                val = float(re.sub(r'[^0-9.eE+-]', '', val_str))
                if 'C1' in sym.ref:
                    c1 = val
            except:
                pass
    
    # Calculate expected frequency and duty cycle
    if r1 and r2 and c1:
        try:
            freq = 1.44 / ((r1 + 2*r2) * c1)
            duty = (r1 + r2) / (r1 + 2*r2) * 100
            analysis["frequency_calc"] = {
                "frequency_hz": round(freq, 3),
                "period_ms": round(1000/freq, 3),
                "duty_cycle_pct": round(duty, 1),
                "r1_ohms": r1,
                "r2_ohms": r2,
                "c1_farads": c1
            }
        except:
            analysis["issues"].append("Unable to calculate timing parameters")
    else:
        missing = []
        if not r1: missing.append("R1")
        if not r2: missing.append("R2")
        if not c1: missing.append("C1")
        analysis["issues"].append(f"Missing timing components: {', '.join(missing)}")
    
    # Check for control voltage filtering cap (pin 5)
    has_cv_cap = any(sym.ref.startswith('C') and sym.ref != comp.ref 
                     for sym in sch.symbols)
    if not has_cv_cap:
        analysis["recommendations"].append(
            "Add 0.01µF ceramic cap from pin 5 (CTRL) to GND for noise immunity"
        )
    
    return analysis

def analyze_component_interconnections(
    sch: Schematic,
    net_build: NetBuildResult,
    power_nets: List[str]
) -> CircuitTopology:
    """Build detailed component interconnection map"""
    
    component_map: Dict[str, ComponentAnalysis] = {}
    power_tree: Dict[str, List[str]] = {}
    missing_decoupling: List[str] = []
    floating_inputs: List[PinConnection] = []
    
    # First pass: analyze each component
    for sym in sch.symbols:
        if '?' in sym.ref:
            continue
            
        comp = ComponentAnalysis(
            ref=sym.ref,
            value=sym.value,
            lib_id=sym.lib_id,
            position=sym.at
        )
        
        # Categorize pins based on common naming patterns
        power_patterns = re.compile(r'(VDD|VCC|V\+|AVDD|DVDD|VBAT)', re.IGNORECASE)
        gnd_patterns = re.compile(r'(GND|VSS|V-|AGND|DGND)', re.IGNORECASE)
        
        # Simulate pin connections (in real implementation, parse from symbol definition)
        # For now, use heuristics based on component type
        if sym.ref.startswith('U'):  # ICs
            # Common IC power pin numbers
            for pin_num in ['1', '8', '4', '7']:  # Common DIP-8 power pins
                # This is simplified - real implementation would parse actual pins
                pass
        
        component_map[sym.ref] = comp
    
    # Second pass: find decoupling caps near ICs
    ics = [ref for ref in component_map.keys() if ref.startswith('U')]
    caps = [ref for ref in component_map.keys() if ref.startswith('C')]
    
    for ic_ref in ics:
        ic = component_map[ic_ref]
        nearby_caps = []
        
        if ic.position:
            for cap_ref in caps:
                cap = component_map[cap_ref]
                if cap.position:
                    # Check if cap is within 50 units (simplified distance check)
                    dx = abs(ic.position[0] - cap.position[0])
                    dy = abs(ic.position[1] - cap.position[1])
                    if dx < 50 and dy < 50:
                        nearby_caps.append(cap_ref)
        
        ic.nearby_caps = nearby_caps
        
        # Flag if major IC has no nearby decoupling
        if not nearby_caps and ic.lib_id and '555' not in ic.lib_id.lower():
            missing_decoupling.append(ic_ref)
    
    # Build power distribution tree
    for net in net_build.nets:
        if net.name in power_nets or 'GND' in net.name.upper():
            consumers = []
            for ref, comp in component_map.items():
                # Check if this component connects to this power net
                # (simplified - real implementation checks actual pin connections)
                if ref.startswith('U'):
                    consumers.append(ref)
            if consumers:
                power_tree[net.name] = consumers
    
    return CircuitTopology(
        component_map=component_map,
        power_tree=power_tree,
        critical_paths=[],
        missing_decoupling=missing_decoupling,
        floating_inputs=floating_inputs
    )

def get_pin_net_mapping(
    sym: SchSymbol,
    sch: Schematic,
    net_build: NetBuildResult
) -> Dict[str, str]:
    """Map each pin of a symbol to its net name"""
    pin_to_net: Dict[str, str] = {}
    
    # This is a simplified version - real implementation would:
    # 1. Parse pin locations from symbol library
    # 2. Find wires/junctions at those locations
    # 3. Look up which net contains those points
    
    # For 555 timer specifically (as example)
    if '555' in sym.lib_id.lower():
        # Hardcode known 555 pin functions for demo
        # Real version would parse from library
        pin_functions = {
            '1': 'GND',
            '2': 'TRIG',
            '3': 'OUT',
            '4': 'RESET',
            '5': 'CTRL',
            '6': 'THRES',
            '7': 'DISC',
            '8': 'VCC'
        }
        return pin_functions
    
    return pin_to_net