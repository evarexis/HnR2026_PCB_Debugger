from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ChecklistStep:
    id: str
    title: str
    instruction: str
    expected: str
    pass_fail: Optional[bool] = None
    likely_faults: List[str] = None
    risk: str = "medium"  # low/medium/high

def generate_checklist(detected) -> List[ChecklistStep]:
    real_mcus = [r for r in detected.mcu_symbols if "?" not in r]
    is_mcu_board = bool(real_mcus) or bool(detected.debug_ifaces)


    steps: List[ChecklistStep] = []

    # POWER
    if detected.power_nets:
        steps.append(ChecklistStep(
            id="power-rails-present",
            title="Verify power rails are present",
            instruction=f"Measure rails: {', '.join(detected.power_nets)} at key IC pins and regulators.",
            expected="Each rail measures within tolerance (e.g., 3.3V ±5%).",
            likely_faults=["Short to GND", "Wrong regulator footprint/part", "Missing enable pull-up", "Reverse polarity input"],
            risk="high",
        ))
    else:
        steps.append(ChecklistStep(
            id="power-rails-unknown",
            title="Identify power rails",
            instruction="No standard power nets detected. Manually identify intended rails and measurement points.",
            expected="At least one primary rail is identified and measurable.",
            likely_faults=["Power net not labeled", "Power symbols missing", "Net connectivity broken"],
            risk="high",
        ))

    if is_mcu_board:
    # existing reset/clock/programming checks
        # RESET
        if detected.reset_nets:
            steps.append(ChecklistStep(
                id="reset-behavior",
                title="Check reset behavior",
                instruction=f"Probe reset net(s): {', '.join(detected.reset_nets)} during power-up.",
                expected="Reset asserts then de-asserts cleanly; no constant low unless intended.",
                likely_faults=["Missing pull-up", "Wrong reset supervisor wiring", "Button shorting", "MCU held in reset by debugger"],
                risk="medium",
            ))
        else:
            steps.append(ChecklistStep(
                id="reset-net-missing",
                title="Confirm reset net exists",
                instruction="No reset nets detected by name. Confirm MCU reset pin wiring and whether it needs pull-up/supervisor.",
                expected="MCU reset pin is not floating and has defined behavior.",
                likely_faults=["Reset pin floating", "No pull-up", "Incorrect pin mapping"],
                risk="medium",
            ))

        # CLOCK
        if detected.clock_sources or detected.clock_nets:
            steps.append(ChecklistStep(
                id="clock-present",
                title="Verify clock source is oscillating",
                instruction="Check crystal/oscillator and clock nets with scope (small probe capacitance).",
                expected="Stable oscillation at expected frequency; no stuck low/high.",
                likely_faults=["Wrong load capacitors", "Wrong crystal footprint", "Bad routing/grounding", "Wrong MCU clock config straps"],
                risk="high",
            ))
        else:
            steps.append(ChecklistStep(
                id="clock-unknown",
                title="Determine clock configuration",
                instruction="No clock symbols/nets detected. Confirm if MCU uses internal oscillator or external clock source.",
                expected="Clock source type is confirmed and matches firmware config.",
                likely_faults=["Firmware expects external crystal", "Clock pins miswired"],
                risk="medium",
            ))

        # PROGRAMMING / DEBUG
        if detected.debug_ifaces:
            steps.append(ChecklistStep(
                id="program-interface",
                title="Validate programming/debug interface",
                instruction=f"Confirm {', '.join(detected.debug_ifaces)} pins are reachable, correctly pinned, and have proper voltage reference.",
                expected="Debugger connects reliably; IDCODE/target detect works.",
                likely_faults=["Swapped pins", "Missing GND/VREF", "No pull-ups", "Wrong header footprint/orientation"],
                risk="high",
            ))
        else:
            steps.append(ChecklistStep(
                id="program-interface-missing",
                title="Provide a programming/debug path",
                instruction="No SWD/JTAG/UART nets detected. Ensure the design exposes a usable programming/debug header.",
                expected="There is a defined method to flash firmware and observe boot logs.",
                likely_faults=["No header", "Debug pins reused without mux", "Only test pads with no access plan"],
                risk="high",
            ))
    else:
        steps.append(ChecklistStep(
            id="basic-ic-functional",
            title="Verify IC functional behavior",
            instruction="For non-MCU designs, validate expected signals (e.g., 555 output waveform) at key pins.",
            expected="Waveform/levels match expected behavior from circuit topology.",
            likely_faults=["Wrong pin mapping", "Incorrect RC values", "Cap polarity reversed", "Missing pull-ups/downs"],
            risk="medium",
        ))

    return steps
