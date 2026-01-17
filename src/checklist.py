#src/checklist_enhanced.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class MeasurementSpec:
    """Specification for automated measurements"""
    type: str  # voltage, frequency, resistance, waveform
    probes: Dict[str, Any]
    expected_range: Optional[List[float]] = None
    tolerance: float = 0.05
    
@dataclass
class ChecklistStep:
    id: str
    sequence: int  # Execution order (1=first, 2=second, etc)
    category: str  # power, reset, clock, programming, functional
    title: str
    instruction: str
    expected: str
    component: Optional[str] = None  # U1, R1, etc
    pins: List[str] = field(default_factory=list)
    nets: List[str] = field(default_factory=list)
    pass_fail: Optional[bool] = None
    likely_faults: List[str] = field(default_factory=list)
    fix_suggestions: List[str] = field(default_factory=list)
    risk: str = "medium"  # low/medium/high
    prevents_bringup: bool = False  # Critical for board to function
    measurement: Optional[MeasurementSpec] = None
    automation_ready: bool = False

def generate_555_checklist(detected, topology) -> List[ChecklistStep]:
    """Generate specific checklist for 555 timer circuits"""
    steps = []
    
    # Find the 555 IC
    u1 = next((c for ref, c in topology.component_map.items() 
              if '555' in c.lib_id.lower()), None)
    
    if not u1:
        return []
    
    # STEP 1: Power rails
    steps.append(ChecklistStep(
        id="555-power-vdd",
        sequence=1,
        category="power",
        title="Verify VDD rail (Pin 8)",
        instruction=f"Measure {u1.ref} pin 8 (VDD) relative to GND",
        expected="4.5V to 16V DC (or 2V to 18V for TLC555)",
        component=u1.ref,
        pins=["8"],
        nets=["VDD", "POWER"],
        likely_faults=[
            "No power source connected",
            "Reverse polarity on power supply",
            "Short circuit to GND",
            "Broken trace from power source"
        ],
        fix_suggestions=[
            "Check power supply connector polarity",
            "Verify continuity from Vin to pin 8",
            "Check for solder bridges near power pins"
        ],
        risk="high",
        prevents_bringup=True,
        measurement=MeasurementSpec(
            type="voltage",
            probes={
                "positive": {"component": u1.ref, "pin": "8"},
                "negative": {"net": "GND"}
            },
            expected_range=[4.5, 16.0],
            tolerance=0.05
        ),
        automation_ready=True
    ))
    
    # STEP 2: Ground connection
    steps.append(ChecklistStep(
        id="555-ground",
        sequence=2,
        category="power",
        title="Verify ground connection (Pin 1)",
        instruction=f"Measure resistance between {u1.ref} pin 1 and GND reference point",
        expected="< 1Ω (essentially 0Ω)",
        component=u1.ref,
        pins=["1"],
        nets=["GND"],
        likely_faults=[
            "Cold solder joint",
            "Broken ground trace",
            "Missing ground plane connection"
        ],
        fix_suggestions=[
            "Reflow solder on pin 1",
            "Check ground plane vias",
            "Verify continuity to power supply ground"
        ],
        risk="high",
        prevents_bringup=True,
        measurement=MeasurementSpec(
            type="resistance",
            probes={
                "probe1": {"component": u1.ref, "pin": "1"},
                "probe2": {"net": "GND"}
            },
            expected_range=[0, 1.0]
        ),
        automation_ready=True
    ))
    
    # STEP 3: Reset pin
    steps.append(ChecklistStep(
        id="555-reset-high",
        sequence=3,
        category="reset",
        title="Verify RESET pin is high (Pin 4)",
        instruction=f"Measure {u1.ref} pin 4 (RESET). Should be tied to VDD or >0.7*VDD",
        expected="Same voltage as VDD (or >70% of VDD)",
        component=u1.ref,
        pins=["4"],
        likely_faults=[
            "Reset pin floating (unstable operation)",
            "Reset tied to GND (IC disabled)",
            "Weak pull-up (noise susceptibility)"
        ],
        fix_suggestions=[
            "Connect pin 4 directly to VDD if unused",
            "Add 10kΩ pull-up resistor if reset button used",
            "Check for shorts to GND"
        ],
        risk="high",
        prevents_bringup=True,
        measurement=MeasurementSpec(
            type="voltage",
            probes={
                "positive": {"component": u1.ref, "pin": "4"},
                "negative": {"net": "GND"}
            },
            expected_range=[3.15, 16.0]  # Assuming 4.5V min * 0.7
        ),
        automation_ready=True
    ))
    
    # STEP 4: Timing network
    steps.append(ChecklistStep(
        id="555-timing-network",
        sequence=4,
        category="functional",
        title="Verify RC timing components",
        instruction="Measure R1, R2, C1 values and check connections to pins 6, 7, 2",
        expected="Components match design values within tolerance (±5% for R, ±10% for C)",
        component=u1.ref,
        pins=["6", "7", "2"],
        likely_faults=[
            "Wrong resistor values (color code misread)",
            "Capacitor polarity reversed (if electrolytic)",
            "Capacitor shorted or open",
            "Poor solder joint on timing components"
        ],
        fix_suggestions=[
            "Use multimeter to verify R values out of circuit",
            "Check capacitor ESR if available",
            "Verify pin 6 and 7 are connected together",
            "Ensure pin 2 connects to timing capacitor"
        ],
        risk="medium",
        prevents_bringup=False
    ))
    
    # STEP 5: Output waveform
    freq_info = ""
    if topology.component_map.get(u1.ref):
        comp_analysis = topology.component_map[u1.ref]
        if hasattr(comp_analysis, 'extra_analysis') and comp_analysis.extra_analysis:
            fc = comp_analysis.extra_analysis.get('frequency_calc')
            if fc:
                freq_info = f" Expected: ~{fc['frequency_hz']} Hz, {fc['duty_cycle_pct']}% duty cycle"
    
    steps.append(ChecklistStep(
        id="555-output-waveform",
        sequence=5,
        category="functional",
        title="Verify output waveform (Pin 3)",
        instruction=f"Connect oscilloscope to {u1.ref} pin 3. Check for square wave.{freq_info}",
        expected="Clean square wave oscillating between ~0V and VDD",
        component=u1.ref,
        pins=["3"],
        nets=["OUTPUT"],
        likely_faults=[
            "No oscillation (check timing components)",
            "Distorted waveform (load too heavy)",
            "Stuck high or low (IC damaged or power issue)",
            "Wrong frequency (incorrect R/C values)"
        ],
        fix_suggestions=[
            "Verify timing network from Step 4",
            "Reduce load on output if present",
            "Check for solder bridges on IC pins",
            "Measure trigger voltage at pin 2 (should toggle)"
        ],
        risk="medium",
        prevents_bringup=False,
        measurement=MeasurementSpec(
            type="waveform",
            probes={
                "channel1": {"component": u1.ref, "pin": "3"},
                "reference": {"net": "GND"}
            }
        ) if freq_info else None,
        automation_ready=bool(freq_info)
    ))
    
    # STEP 6: Control voltage bypass
    steps.append(ChecklistStep(
        id="555-ctrl-bypass",
        sequence=6,
        category="functional",
        title="Check control voltage bypass (Pin 5)",
        instruction="Verify 0.01µF capacitor from pin 5 to GND for noise filtering",
        expected="Capacitor present and properly connected",
        component=u1.ref,
        pins=["5"],
        likely_faults=[
            "Missing bypass cap (noise susceptibility)",
            "Wrong capacitor value (reduced filtering)",
            "Poor ground connection"
        ],
        fix_suggestions=[
            "Add 0.01µF ceramic cap if missing",
            "Place cap physically close to IC",
            "Use short, direct trace to ground"
        ],
        risk="low",
        prevents_bringup=False
    ))
    
    return steps

def generate_mcu_checklist(detected, topology, sch) -> List[ChecklistStep]:
    """Generate checklist for MCU-based boards"""
    steps = []
    
    mcu_ref = detected.mcu_symbols[0] if detected.mcu_symbols else "U1"
    
    # POWER
    if detected.power_nets:
        gnd_nets = [n for n in detected.power_nets if n.upper() in {"GND", "AGND", "DGND", "VSS"}]
        rail_nets = [n for n in detected.power_nets if n not in gnd_nets]
        
        for i, rail in enumerate(rail_nets, start=1):
            steps.append(ChecklistStep(
                id=f"mcu-power-rail-{i}",
                sequence=i,
                category="power",
                title=f"Verify {rail} power rail",
                instruction=f"Measure {rail} at {mcu_ref} power pins relative to {gnd_nets[0] if gnd_nets else 'GND'}",
                expected=f"{rail} voltage within spec (e.g., 3.3V ±5% = 3.135V to 3.465V)",
                component=mcu_ref,
                nets=[rail] + gnd_nets,
                likely_faults=[
                    f"Regulator not enabled (check EN pin)",
                    f"Short to GND on {rail} net",
                    f"Wrong regulator output voltage",
                    f"Insufficient input voltage to regulator"
                ],
                fix_suggestions=[
                    "Check regulator enable pin state (should be HIGH)",
                    "Verify input voltage to regulator is sufficient",
                    "Look for solder bridges shorting power to ground",
                    "Check regulator feedback network if adjustable"
                ],
                risk="high",
                prevents_bringup=True,
                measurement=MeasurementSpec(
                    type="voltage",
                    probes={
                        "positive": {"net": rail},
                        "negative": {"net": gnd_nets[0] if gnd_nets else "GND"}
                    },
                    expected_range=[3.135, 3.465] if "3" in rail else [4.75, 5.25],
                    tolerance=0.05
                ),
                automation_ready=True
            ))
    
    # RESET
    seq = len(steps) + 1
    if detected.reset_nets:
        steps.append(ChecklistStep(
            id="mcu-reset-behavior",
            sequence=seq,
            category="reset",
            title="Check reset behavior during power-up",
            instruction=f"Power cycle board while monitoring {detected.reset_nets[0]} with oscilloscope",
            expected="Reset pulse LOW then HIGH, stays HIGH >100ms after power stable",
            component=mcu_ref,
            nets=detected.reset_nets,
            likely_faults=[
                "Missing pull-up resistor (reset floating)",
                "Reset supervisor not functioning",
                "Wrong reset polarity (active high vs low)",
                "Reset capacitor too large (slow release)"
            ],
            fix_suggestions=[
                "Add 10kΩ pull-up to VDD if missing",
                "Check reset supervisor IC power and ground",
                "Verify reset timing matches MCU datasheet",
                "Reduce reset capacitor if release too slow"
            ],
            risk="high",
            prevents_bringup=True
        ))
    else:
        steps.append(ChecklistStep(
            id="mcu-reset-missing",
            sequence=seq,
            category="reset",
            title="Locate and verify MCU reset pin",
            instruction=f"Find {mcu_ref} NRST/RESET pin in datasheet, measure voltage",
            expected="Reset pin at VDD level (not floating at ~1.5V)",
            component=mcu_ref,
            likely_faults=[
                "Reset pin completely unconnected",
                "Reset pin floating (no pull-up)",
                "Reset tied to GND permanently"
            ],
            fix_suggestions=[
                "Add 10kΩ pull-up resistor to VDD",
                "If using reset button, add RC network",
                "Check MCU datasheet for internal pull-up availability"
            ],
            risk="high",
            prevents_bringup=True
        ))
    
    # CLOCK
    seq = len(steps) + 1
    if detected.clock_sources or detected.clock_nets:
        crystal_ref = detected.clock_sources[0] if detected.clock_sources else "Y1"
        
        steps.append(ChecklistStep(
            id="mcu-clock-oscillating",
            sequence=seq,
            category="clock",
            title="Verify clock source oscillation",
            instruction=f"Probe {crystal_ref} pins with scope (10x probe, <10pF capacitance)",
            expected="Clean sine/square wave at crystal frequency (e.g., 8MHz, 16MHz)",
            component=crystal_ref,
            nets=detected.clock_nets if detected.clock_nets else ["HSE_IN", "HSE_OUT"],
            likely_faults=[
                "Wrong load capacitors (not matching crystal spec)",
                "Load caps too far from MCU pins",
                "Crystal footprint wrong (HC-49 vs SMD)",
                "MCU clock pins not configured correctly",
                "Poor ground return path for crystal"
            ],
            fix_suggestions=[
                "Calculate correct load caps: CL = 2*(Ctrace + Cpin) - Cboard",
                "Place load caps within 5mm of MCU crystal pins",
                "Verify crystal frequency matches firmware config",
                "Check MCU datasheet for required HSEBYP/HSE_ON settings",
                "Add ground pour under crystal for stability"
            ],
            risk="high",
            prevents_bringup=True,
            measurement=MeasurementSpec(
                type="frequency",
                probes={
                    "probe": {"component": mcu_ref, "pin": "OSC_IN"}
                }
            ),
            automation_ready=True
        ))
    else:
        steps.append(ChecklistStep(
            id="mcu-clock-config",
            sequence=seq,
            category="clock",
            title="Determine MCU clock source",
            instruction=f"Check {mcu_ref} datasheet - using internal RC or external crystal?",
            expected="Clock configuration matches firmware initialization code",
            component=mcu_ref,
            likely_faults=[
                "Firmware configured for external crystal but none present",
                "Internal RC oscillator not accurate enough for peripherals (USB, CAN)",
                "Clock select pins (BOOT, CONFIG) in wrong state"
            ],
            fix_suggestions=[
                "Modify firmware to use internal RC if no crystal",
                "Add external crystal if precision timing needed",
                "Check MCU option bytes / configuration fuses"
            ],
            risk="medium",
            prevents_bringup=False
        ))
    
    # PROGRAMMING INTERFACE
    seq = len(steps) + 1
    if detected.debug_ifaces:
        iface = detected.debug_ifaces[0]
        
        if iface == "SWD":
            pins_required = ["SWDIO", "SWCLK", "GND", "VDD"]
            expected_connections = "SWDIO, SWCLK properly connected; VDD reference present"
        elif iface == "JTAG":
            pins_required = ["TMS", "TCK", "TDI", "TDO", "GND", "VDD"]
            expected_connections = "All JTAG pins connected; VDD reference present"
        else:  # UART
            pins_required = ["TX", "RX", "GND"]
            expected_connections = "TX/RX not swapped; GND common with programmer"
        
        steps.append(ChecklistStep(
            id="mcu-programming-interface",
            sequence=seq,
            category="programming",
            title=f"Validate {iface} programming interface",
            instruction=f"Connect {iface} debugger, attempt to read device ID",
            expected=f"Debugger detects {mcu_ref}, reads correct IDCODE/device signature",
            component=mcu_ref,
            nets=pins_required,
            likely_faults=[
                "SWDIO/SWCLK pins swapped",
                "No VDD reference to debugger (VTREF floating)",
                "Debug pins reassigned in firmware without release",
                "Wrong header pinout (2x5 vs 1x10)",
                "Series resistors too high (>1kΩ on SWD lines)"
            ],
            fix_suggestions=[
                "Verify pinout matches debugger (ST-Link, J-Link, etc)",
                "Connect VTREF to board VDD",
                "Add 10kΩ pull-up on SWDIO if unreliable",
                "Check for firmware that disables debug pins",
                "Ensure clean power during connection"
            ],
            risk="high",
            prevents_bringup=True
        ))
    else:
        steps.append(ChecklistStep(
            id="mcu-programming-missing",
            sequence=seq,
            category="programming",
            title="Add programming interface",
            instruction="Identify SWD/JTAG pins on MCU, provide test points or header",
            expected="Accessible connection points for debugging",
            component=mcu_ref,
            likely_faults=[
                "No debug header in design",
                "Debug pins only on BGA balls (no fanout)",
                "Pins repurposed without way to recover"
            ],
            fix_suggestions=[
                "Add 2x5 0.1\" header for SWD",
                "At minimum, provide test points for SWDIO/SWCLK/GND/VDD",
                "Document programming procedure if non-standard"
            ],
            risk="high",
            prevents_bringup=True
        ))
    
    # DECOUPLING CAPS
    seq = len(steps) + 1
    if topology.missing_decoupling:
        steps.append(ChecklistStep(
            id="mcu-decoupling-caps",
            sequence=seq,
            category="power",
            title="Verify decoupling capacitors",
            instruction=f"Check for 100nF caps within 5mm of each VDD pin on {mcu_ref}",
            expected="One 100nF ceramic cap per power pin, close placement",
            component=mcu_ref,
            likely_faults=[
                "Missing decoupling caps",
                "Caps too far from IC (>10mm)",
                "Wrong capacitor type (electrolytic instead of ceramic)",
                "Shared cap between multiple power pins"
            ],
            fix_suggestions=[
                "Add 100nF X7R/X5R ceramic caps at each VDD pin",
                "Place caps on same side of board as IC",
                "Use short, wide traces to power planes",
                "Add 10µF bulk cap near MCU for transient loads"
            ],
            risk="medium",
            prevents_bringup=False
        ))
    
    return steps

def generate_checklist(detected, topology=None, sch=None) -> List[ChecklistStep]:
    """Main checklist generation with automatic circuit type detection"""
    
    # Determine circuit type
    is_mcu = bool(detected.mcu_symbols) or bool(detected.debug_ifaces)
    is_555 = any('555' in sym for sym in [s.lib_id for s in (sch.symbols if sch else [])])
    
    if is_555 and topology:
        steps = generate_555_checklist(detected, topology)
    elif is_mcu and topology:
        steps = generate_mcu_checklist(detected, topology, sch)
    else:
        # Generic fallback checklist
        steps = generate_generic_checklist(detected)
    
    # Sort by sequence number
    steps.sort(key=lambda s: s.sequence)
    
    return steps

def generate_generic_checklist(detected) -> List[ChecklistStep]:
    """Fallback for unknown circuit types"""
    steps = []
    
    if detected.power_nets:
        gnd_nets = [n for n in detected.power_nets if n.upper() in {"GND", "AGND", "DGND", "VSS"}]
        rail_nets = [n for n in detected.power_nets if n not in gnd_nets]
        
        steps.append(ChecklistStep(
            id="power-rails-present",
            sequence=1,
            category="power",
            title="Verify power and reference ground",
            instruction=f"Set multimeter reference to {', '.join(gnd_nets) if gnd_nets else 'GND'}. "
                       f"Measure these rails at IC power pins/regulators: {', '.join(rail_nets)}.",
            expected="Each rail measures within tolerance (e.g., 3.3V ±5%).",
            nets=detected.power_nets,
            likely_faults=[
                "Short to GND",
                "Wrong regulator footprint/part",
                "Missing enable pull-up",
                "Reverse polarity input"
            ],
            fix_suggestions=[
                "Check for solder bridges with multimeter continuity test",
                "Verify regulator part number matches BOM",
                "Measure regulator input voltage first"
            ],
            risk="high",
            prevents_bringup=True
        ))
    
    steps.append(ChecklistStep(
        id="basic-ic-functional",
        sequence=2,
        category="functional",
        title="Verify IC functional behavior",
        instruction="For non-MCU designs, validate expected signals (e.g., 555 output waveform) at key pins.",
        expected="Waveform/levels match expected behavior from circuit topology.",
        likely_faults=[
            "Wrong pin mapping",
            "Incorrect RC values",
            "Cap polarity reversed",
            "Missing pull-ups/downs"
        ],
        fix_suggestions=[
            "Compare actual component values to schematic",
            "Check IC orientation (pin 1 marker)",
            "Verify power is stable before checking function"
        ],
        risk="medium",
        prevents_bringup=False
    ))
    
    return steps