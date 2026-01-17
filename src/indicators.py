#src/indicators.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.netlist_build import Net
from src.kicad_extract import Schematic, SchSymbol

POWER_NAME_RE = re.compile(
    r"^(?:"
    r"GND|AGND|DGND|VSS|"
    r"VBAT|VIN|VCC|"
    r"VDD(?:[A-Z0-9_]+)?|AVDD|DVDD|"
    r"VREF(?:[A-Z0-9_]+)?|"
    r"PWR|POWER|"
    r"\+?\d+(?:\.\d+)?V"          # matches +5V, 5V, 1.8V, 12V
    r")$",
    re.IGNORECASE
)

RESET_RE = re.compile(r"(RST|RESET|NRST)\b", re.IGNORECASE)
CLOCK_NET_RE = re.compile(r"(HSE|LSE|XTAL|OSC|CLK|MCO)\b", re.IGNORECASE)

SWD_RE = re.compile(r"\b(SWDIO|SWCLK|SWO)\b", re.IGNORECASE)
JTAG_RE = re.compile(r"\b(TMS|TCK|TDI|TDO|TRST)\b", re.IGNORECASE)
UART_RE = re.compile(r"\b(TX|RX|UART)\b", re.IGNORECASE)

CRYSTAL_RE = re.compile(r"(crystal|xtal|oscillator)", re.IGNORECASE)

@dataclass
class Detected:
    power_nets: List[str]
    reset_nets: List[str]
    clock_nets: List[str]
    mcu_symbols: List[str]          # refs
    clock_sources: List[str]        # refs
    debug_ifaces: List[str]         # e.g. ["SWD", "JTAG", "UART"]
    notes: List[str]

def detect_nets(nets: List[Net]) -> Dict[str, List[str]]:
    power, reset, clock = [], [], []
    for n in nets:
        name = n.name.strip()
        if POWER_NAME_RE.match(name):
            power.append(name)
        if RESET_RE.search(name):
            reset.append(name)
        if CLOCK_NET_RE.search(name):
            clock.append(name)
    return {"power": sorted(set(power)), "reset": sorted(set(reset)), "clock": sorted(set(clock))}

def detect_mcu(symbols: List[SchSymbol]) -> List[str]:
    # Heuristic: reference starts with U and value/lib contains common MCU hints
    mcu_hints = re.compile(r"(stm32|esp32|nrf|atmega|attiny|rp2040|pic|msp430|samd|imx|kinetis|gd32)", re.IGNORECASE)
    out = []
    for s in symbols:
        if "?" in s.ref:
            continue
        blob = f"{s.ref} {s.value} {s.lib_id} " + " ".join([f"{k}:{v}" for k, v in s.properties.items()])
        if s.ref.upper().startswith("U") and mcu_hints.search(blob):
            out.append(s.ref)
    return sorted(set(out))

def detect_clock_sources(symbols: List[SchSymbol]) -> List[str]:
    out = []
    for s in symbols:
        blob = f"{s.value} {s.lib_id}"
        if CRYSTAL_RE.search(blob) or s.ref.upper().startswith(("Y", "X")):
            out.append(s.ref)
    return sorted(set(out))

def detect_debug_ifaces(nets: List[Net]) -> List[str]:
    names = [n.name for n in nets]
    if any(SWD_RE.search(x) for x in names):
        return ["SWD"]
    if any(JTAG_RE.search(x) for x in names):
        return ["JTAG"]
    if any(UART_RE.search(x) for x in names):
        return ["UART"]
    return []

def run_detectors(sch: Schematic, nets: List[Net]) -> Detected:
    net_hits = detect_nets(nets)
    mcu = detect_mcu(sch.symbols)
    clocks = detect_clock_sources(sch.symbols)
    dbg = detect_debug_ifaces(nets)

    notes = []
    if not mcu:
        notes.append("No MCU/main IC detected (heuristic).")
    if not net_hits["power"]:
        notes.append("No obvious power nets detected (3V3/VDD/5V/VBAT etc).")
    if not clocks:
        notes.append("No crystal/oscillator symbols detected.")
    if not dbg:
        notes.append("No programming/debug interface nets detected (SWD/JTAG/UART heuristics).")

    return Detected(
        power_nets=net_hits["power"],
        reset_nets=net_hits["reset"],
        clock_nets=net_hits["clock"],
        mcu_symbols=mcu,
        clock_sources=clocks,
        debug_ifaces=dbg,
        notes=notes
    )
