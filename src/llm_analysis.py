# src/llm_analyzer.py
"""
LLM-based circuit analysis using OpenAI or Gemini APIs.
Provides structured analysis and function recommendations.
"""
from __future__ import annotations
import json
import os
from typing import Dict, Any, Optional, Literal
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
        """
        Analyze schematic using LLM with automatic fallback.
        Returns structured analysis or None if all methods fail.
        """
        # Try primary LLM
        if self.primary != LLMProvider.HEURISTIC:
            try:
                result = self._call_llm(self.primary, summary)
                if result:
                    self.used_provider = self.primary
                    return result
            except Exception as e:
                print(f"Primary LLM ({self.primary.value}) failed: {e}")
        
        # Try secondary LLM
        if self.secondary != LLMProvider.HEURISTIC:
            try:
                result = self._call_llm(self.secondary, summary)
                if result:
                    self.used_provider = self.secondary
                    return result
            except Exception as e:
                print(f"Secondary LLM ({self.secondary.value}) failed: {e}")
        
        # Fallback to heuristics
        print("Falling back to heuristic analysis")
        self.used_provider = LLMProvider.HEURISTIC
        return None  # Caller will use heuristics
    
    def _call_llm(self, provider: LLMProvider, summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call specific LLM provider"""
        if provider == LLMProvider.OPENAI:
            return call_openai_api(summary)
        elif provider == LLMProvider.GEMINI:
            return call_gemini_api(summary)
        return None


def call_openai_api(schematic_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call OpenAI API to analyze schematic and recommend analysis functions.
    Requires OPENAI_API_KEY environment variable.
    """
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
        model="gpt-4o",  # Use latest model
        messages=[
            {
                "role": "system",
                "content": _get_system_prompt()
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,  # Low temperature for consistent technical analysis
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result


def call_gemini_api(schematic_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call Google Gemini API to analyze schematic.
    Requires GEMINI_API_KEY environment variable.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("Google Generative AI library not installed. Run: pip install google-generativeai")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = _build_analysis_prompt(schematic_summary)
    full_prompt = f"{_get_system_prompt()}\n\n{prompt}\n\nRespond with valid JSON only."
    
    response = model.generate_content(
        full_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
        )
    )
    
    # Extract JSON from response
    text = response.text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    result = json.loads(text.strip())
    return result


def _get_system_prompt() -> str:
    """System prompt defining the LLM's role and output format"""
    return """You are an expert PCB design debugger analyzing KiCad schematics. Your job is to:

1. Identify the circuit type and purpose
2. Detect connectivity and design issues
3. Recommend specific analysis functions to run
4. Provide debugging verification steps

You must respond with valid JSON matching this EXACT structure:

{
  "circuit_analysis": {
    "circuit_type": "string (e.g., '555_timer_astable', 'stm32_basic', 'esp32_wifi')",
    "purpose": "string (brief description of what circuit does)",
    "confidence": 0.0-1.0,
    "main_ic": "string (reference like 'U1')",
    "critical_components": ["R1", "C2", "U1"]
  },
  "analysis": [
    {
      "function": "function_name",
      "params": {"key": "value"},
      "priority": "critical|high|medium|low",
      "reason": "why this analysis is needed"
    }
  ],
  "expected_behavior": {
    "output_frequency_hz": 5.5,
    "duty_cycle_percent": 61.5,
    "other_behaviors": "any other expected circuit behavior for debugging"
  },
  "detected_issues": [
    {
      "issue": "brief_issue_name",
      "severity": "critical|high|medium|low",
      "analysis_needed": ["function1", "function2"],
      "components_involved": ["U1", "R1"],
      "reason": "why this is an issue",
      "debug_step": "short explanation of how to fix"
    }
  ],
  "verification_steps_issues": [
    {"step": 1, "action": "what to do", "expected": "what should happen", "target": "specific issue"},
    {"step": 2, "action": "...", "expected": "...", "target": "..."}
  ],
  "verification_steps_general": [
    {"step": 1, "action": "general workability check", "expected": "expected result"},
    {"step": 2, "action": "...", "expected": "..."}
  ]
}

Be specific and technical. Focus on actual debugging steps a beginner would take."""


def _build_analysis_prompt(summary: Dict[str, Any]) -> str:
    """Build the user prompt with schematic data"""
    
    # Highlight critical information
    components_str = json.dumps(summary['components'], indent=2)
    nets_str = json.dumps(summary['nets'][:20], indent=2)  # Limit to first 20 nets
    labels_str = json.dumps(summary['labels'], indent=2)
    issues_str = json.dumps(summary['connectivity_issues'], indent=2)
    stats_str = json.dumps(summary['statistics'], indent=2)
    
    prompt = f"""Analyze this KiCad schematic and identify:
1. What type of circuit this is
2. Any connectivity or design issues
3. Which analysis functions should be executed
4. Debugging steps for a beginner

SCHEMATIC SUMMARY:

STATISTICS:
{stats_str}

COMPONENTS:
{components_str}

NETS (first 20):
{nets_str}

LABELS (with connectivity status):
{labels_str}

DETECTED CONNECTIVITY ISSUES:
{issues_str}

Based on this data:
1. Identify the circuit type and main IC
2. Detect any power, ground, or signal connectivity issues
3. Recommend specific analysis functions (use names like: verify_power_connectivity, analyze_rc_timing, check_decoupling_caps, verify_crystal_circuit, check_mcu_boot_pins, etc.)
4. Provide beginner-friendly debugging steps

Focus on issues that would prevent the PCB from working on first power-up."""
    
    return prompt


# Available analysis functions that LLM can recommend
AVAILABLE_ANALYSIS_FUNCTIONS = [
    # Power analysis
    "verify_power_connectivity",
    "check_power_rail_routing",
    "analyze_decoupling_capacitors",
    "verify_voltage_regulator_circuit",
    "check_power_sequencing",
    
    # Timing/Clock analysis
    "analyze_rc_timing_network",
    "verify_crystal_circuit",
    "check_clock_distribution",
    "analyze_pll_configuration",
    
    # Signal integrity
    "check_floating_pins",
    "verify_pull_up_pull_down",
    "analyze_signal_termination",
    "check_impedance_matching",
    
    # MCU specific
    "verify_mcu_boot_configuration",
    "check_debug_interface",
    "analyze_reset_circuit",
    "verify_programming_interface",
    
    # Component verification
    "verify_component_values",
    "check_component_ratings",
    "analyze_thermal_design",
    
    # Connectivity
    "trace_signal_path",
    "verify_ground_plane",
    "check_differential_pairs",
    "analyze_power_distribution",
    
    # Circuit-specific
    "analyze_555_timer_circuit",
    "verify_opamp_circuit",
    "check_motor_driver_circuit",
    "analyze_switching_converter"
]