"""
Backend analysis modules for KiCad Bring-Up Assistant
"""

# Core parsing and extraction
from .parse_sexp import parse_kicad_sch
from .kicad_extract import parse_schematic
from .netlist_build import build_nets
from .indicators import run_detectors

# Analysis and reporting
from .schematic_summary import generate_schematic_summary
from .llm_analysis import LLMAnalyzer, LLMProvider
from .export import export_checklist_markdown, export_checklist_json

# Make key functions available at package level
__all__ = [
    'parse_kicad_sch',
    'parse_schematic',
    'build_nets',
    'run_detectors',
    'generate_schematic_summary',
    'LLMAnalyzer',
    'LLMProvider',
    'export_checklist_markdown',
    'export_checklist_json',
]

__version__ = "1.0.0"