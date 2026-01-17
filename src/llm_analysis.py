# src/llm_analysis.py - ENHANCED VERSION
"""
LLM-based circuit analysis with improved component detection
"""
from __future__ import annotations
import json
import os
from typing import Dict, Any, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    HEURISTIC = "heuristic"


class LLMAnalyzer:
    """Orchestrates LLM-based schematic analysis with fallback"""
    
    def __init__(self, primary: LLMProvider = LLMProvider.OPENAI, 
                 secondary: LLMProvider = LLMProvider.GEMINI):
        self.primary = primary
        self.secondary = secondary
        self.used_provider = None
        
    def analyze_schematic(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze schematic using LLM with automatic fallback"""
        if self.primary != LLMProvider.HEURISTIC:
            try:
                result = self._call_llm(self.primary, summary)
                if result:
                    self.used_provider = self.primary
                    return result
            except Exception as e:
                print(f"Primary LLM ({self.primary.value}) failed: {e}")
        
        if self.secondary != LLMProvider.HEURISTIC:
            try:
                result = self._call_llm(self.secondary, summary)
                if result:
                    self.used_provider = self.secondary
                    return result
            except Exception as e:
                print(f"Secondary LLM ({self.secondary.value}) failed: {e}")
        
        print("Falling back to heuristic analysis")
        self.used_provider = LLMProvider.HEURISTIC
        return None
    
    def _call_llm(self, provider: LLMProvider, summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call specific LLM provider"""
        if provider == LLMProvider.OPENAI:
            return call_openai_api(summary)
        elif provider == LLMProvider.GEMINI:
            return call_gemini_api(summary)
        return None


def call_openai_api(schematic_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Call OpenAI API with enhanced prompting"""
    try:
        import openai
    except ImportError:
        raise ImportError("OpenAI library not installed. Run: pip install openai")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = _build_analysis_prompt(schematic_summary)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _get_system_prompt()},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result


def call_gemini_api(schematic_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Call Google Gemini API"""
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("Google Generative AI library not installed")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = _build_analysis_prompt(schematic_summary)
    full_prompt = f"{_get_system_prompt()}\n\n{prompt}\n\nRespond with valid JSON only."
    
    response = model.generate_content(full_prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
    
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    result = json.loads(text.strip())
    return result


def _get_system_prompt() -> str:
    """Enhanced system prompt with strict instructions"""
    return """You are an expert PCB design debugger. Analyze KiCad schematics and provide detailed debugging guidance.

CRITICAL RULES:
1. ALWAYS use actual component references from the schematic (e.g., "U1", "Y1", "R1") - NEVER use "None"
2. ALWAYS use exact function names from the available functions list
3. Focus on real hardware issues that prevent circuit operation

OUTPUT STRUCTURE (strict JSON):
{
  "circuit_analysis": {
    "circuit_type": "stm32_basic|555_timer_astable|esp32_wifi|etc",
    "purpose": "brief description",
    "confidence": 0.0-1.0,
    "main_ic": "U1",  // ACTUAL component reference, NOT "None"
    "critical_components": ["U1", "Y1", "C1"]  // ACTUAL refs
  },
  "analysis": [
    {
      "function": "verify_power_connectivity",  // EXACT function name
      "params": {
        "power_nets": ["3V3", "GND"],
        "ic_ref": "U1",  // ACTUAL component ref
        "power_pins": ["1", "32", "48", "64"],  // Real pin numbers
        "gnd_pins": ["16", "33", "47", "63"]
      },
      "priority": "critical|high|medium|low",
      "reason": "explanation"
    }
  ],
  "expected_behavior": {
    "output_frequency_hz": 8000000,
    "duty_cycle_percent": 50,
    "other_behaviors": "description"
  },
  "detected_issues": [
    {
      "issue": "missing_reset_pullup",
      "severity": "critical|high|medium|low",
      "analysis_needed": ["analyze_reset_circuit"],
      "components_involved": ["U1", "R5"],  // ACTUAL refs
      "reason": "why this is a problem",
      "debug_step": "how to fix"
    }
  ],
  "verification_steps_issues": [
    {"step": 1, "action": "...", "expected": "...", "target": "issue_id"}
  ],
  "verification_steps_general": [
    {"step": 1, "action": "...", "expected": "..."}
  ]
}

AVAILABLE FUNCTIONS (use exact names):
- verify_power_connectivity
- check_power_rail_routing
- analyze_decoupling_capacitors (NOT "check_decoupling_caps")
- verify_voltage_regulator_circuit
- analyze_rc_timing_network
- verify_crystal_circuit
- check_clock_distribution
- check_floating_pins
- verify_pull_up_pull_down
- trace_signal_path
- verify_ground_plane
- verify_mcu_boot_configuration (NOT "check_mcu_boot_pins")
- check_debug_interface
- analyze_reset_circuit
- verify_programming_interface
- check_mcu_power_pins

COMMON MCU ISSUES TO DETECT:
1. Missing reset pull-up resistor (CRITICAL)
2. Floating BOOT pins (WARNING)
3. Missing crystal load capacitors (HIGH)
4. Missing decoupling capacitors (MEDIUM)
5. Unconnected power pins (CRITICAL)"""


def _build_analysis_prompt(summary: Dict[str, Any]) -> str:
    """Build enhanced analysis prompt with component list"""
    
    # Extract component references for LLM
    component_refs = [c['ref'] for c in summary['components']]
    mcu_components = [c for c in summary['components'] if c['type'] == 'microcontroller']
    crystal_components = [c for c in summary['components'] if c['type'] == 'crystal_oscillator']
    
    components_str = json.dumps(summary['components'], indent=2)
    nets_str = json.dumps(summary['nets'][:20], indent=2)
    labels_str = json.dumps(summary['labels'], indent=2)
    issues_str = json.dumps(summary['connectivity_issues'], indent=2)
    stats_str = json.dumps(summary['statistics'], indent=2)
    
    prompt = f"""Analyze this KiCad schematic for PCB debugging.

CRITICAL: Use ACTUAL component references from this list:
Component References: {component_refs}
MCU: {[c['ref'] for c in mcu_components]}
Crystals: {[c['ref'] for c in crystal_components]}

SCHEMATIC DATA:

STATISTICS:
{stats_str}

COMPONENTS:
{components_str}

NETS (first 20):
{nets_str}

LABELS:
{labels_str}

CONNECTIVITY ISSUES:
{issues_str}

REQUIRED ANALYSIS:
1. Identify circuit type and main IC (use actual component ref like "U1", NOT "None")
2. Detect CRITICAL issues:
   - Missing reset pull-up resistor on MCU NRST pin
   - Floating BOOT pins
   - Missing crystal load capacitors
   - Unconnected power pins
3. Recommend analysis functions (use EXACT function names from list)
4. Provide step-by-step debugging

Focus on issues that prevent first power-up."""
    
    return prompt


AVAILABLE_ANALYSIS_FUNCTIONS = [
    "verify_power_connectivity",
    "check_power_rail_routing",
    "analyze_decoupling_capacitors",
    "verify_voltage_regulator_circuit",
    "check_power_sequencing",
    "analyze_rc_timing_network",
    "verify_crystal_circuit",
    "check_clock_distribution",
    "check_floating_pins",
    "verify_pull_up_pull_down",
    "analyze_signal_termination",
    "verify_mcu_boot_configuration",
    "check_debug_interface",
    "analyze_reset_circuit",
    "verify_programming_interface",
    "check_mcu_power_pins",
    "trace_signal_path",
    "verify_ground_plane",
    "check_differential_pairs",
    "analyze_power_distribution",
]