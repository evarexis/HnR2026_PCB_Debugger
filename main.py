from __future__ import annotations
import json
import sys
from pathlib import Path

from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors
from src.checklist import generate_checklist
from src.risk import compute_overall_risk
from src.report import ReportModel, StepModel

def run(path: str) -> dict:
    tree = parse_kicad_sch(path)
    sch = parse_schematic(tree)
    nets = build_nets(sch, label_tolerance=2)
    detected = run_detectors(sch, nets)
    steps = generate_checklist(detected)
    overall = compute_overall_risk(steps)

    report = ReportModel(
        file=str(path),
        detected={
            "power_nets": detected.power_nets,
            "reset_nets": detected.reset_nets,
            "clock_nets": detected.clock_nets,
            "mcu_symbols": detected.mcu_symbols,
            "clock_sources": detected.clock_sources,
            "debug_ifaces": detected.debug_ifaces,
        },
        checklist=[StepModel(**s.__dict__) for s in steps],
        overall_risk=overall,
        notes=detected.notes,
    )
    return report.model_dump()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py path/to/file.kicad_sch", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    out = run(path)
    print(json.dumps(out, indent=2))
