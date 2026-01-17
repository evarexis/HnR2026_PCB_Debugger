# PCB Debugger - Schematic Analysis

Analyze KiCad schematics before PCB fabrication to catch errors and generate beginner-friendly debugging checklists.

## Features

- **AI-Powered Analysis**: Uses OpenAI or Gemini to understand your circuit
- **Modular Function Library**: 20+ granular analysis functions for detailed debugging
- **Automatic Fallback**: OpenAI → Gemini → Heuristics (never fails completely)
- **Beginner-Friendly**: Step-by-step debugging instructions
- **Comprehensive Reports**: Detailed JSON output with all findings

## Installation

```bash
# Clone repository
git clone <your-repo>
cd pcb-debugger

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## API Keys (Optional)

For AI-powered analysis, set up API keys:

```bash
# For OpenAI (recommended)
export OPENAI_API_KEY="sk-..."

# For Gemini (free tier available)
export GEMINI_API_KEY="..."
```

Without API keys, the tool automatically falls back to heuristic analysis.

## Usage

### Basic Usage

```bash
python main.py path/to/your_schematic.kicad_sch
```

### Choose LLM Provider

```bash
# Use OpenAI as primary, Gemini as fallback (default)
python main.py schematic.kicad_sch --llm openai --fallback gemini

# Use Gemini as primary
python main.py schematic.kicad_sch --llm gemini --fallback heuristic

# Use only heuristics (no API required)
python main.py schematic.kicad_sch --llm heuristic
```

### Save Output

```bash
python main.py schematic.kicad_sch --output report.json
```

## Example Output

```json
{
  "metadata": {
    "schematic_file": "555/555.kicad_sch",
    "analysis_method": "openai",
    "circuit_type": "555_timer_astable",
    "confidence": 0.95
  },
  "circuit_analysis": {
    "circuit_type": "555_timer_astable",
    "purpose": "Generate square wave oscillator",
    "confidence": 0.95,
    "main_ic": "U1",
    "critical_components": ["U1", "R1", "R2", "C1"]
  },
  "expected_behavior": {
    "output_frequency_hz": 5.538,
    "duty_cycle_percent": 61.5,
    "other_behaviors": "Square wave on pin 3"
  },
  "detected_issues": [
    {
      "issue": "power_label_floating",
      "severity": "critical",
      "reason": "POWER label not connected to wire",
      "debug_step": "Draw wire from POWER label to pin 8"
    }
  ],
  "verification_steps": {
    "for_issues": [
      {
        "step": 1,
        "action": "Connect POWER label to circuit",
        "expected": "Label touches wire",
        "target": "power_label_floating"
      }
    ],
    "for_general_workability": [
      {
        "step": 1,
        "action": "Apply 5-12V power",
        "expected": "No smoke, correct voltage on pin 8"
      },
      {
        "step": 2,
        "action": "Probe pin 3 with oscilloscope",
        "expected": "5.5Hz square wave, 61.5% duty cycle"
      }
    ]
  },
  "overall_risk": {
    "score": 92,
    "level": "critical",
    "critical_issues": 2,
    "can_attempt_bringup": false,
    "blockers": [
      "POWER label not connected to wire"
    ]
  }
}
```

## Architecture

### 1. Schematic Summary Generation (`src/schematic_summary.py`)

Extracts debugging-relevant information:
- Component inventory with types and positions
- Net connectivity (for tracing broken connections)
- Label attachment status (floating labels are bugs!)
- Wire topology and junction points
- Component proximity (for finding decoupling caps)

### 2. LLM Analysis (`src/llm_analysis.py`)

Sends summary to LLM with specialized prompt:
- Identifies circuit type (555 timer, STM32, ESP32, etc.)
- Detects connectivity issues
- Recommends specific analysis functions
- Provides debugging steps

### 3. Analysis Functions (`src/analysis/`) [20+ functions]

Modular, granular functions:

**Power Analysis**
- `verify_power_connectivity`: Check power rails connect to ICs
- `check_power_rail_routing`: Verify power distribution
- `analyze_decoupling_capacitors`: Find missing bypass caps
- `verify_voltage_regulator_circuit`: Check regulator config
- `check_power_sequencing`: 

**Timing Analysis**
- `analyze_rc_timing_network`: Calculate 555 timer frequency
- `verify_crystal_circuit`: Check MCU crystal + load caps
- `check_clock_distribution`: Verify clock routing

**Signal Analysis**
- `check_floating_pins`: Find unconnected inputs
- `verify_pull_up_pull_down`: Check pull resistors
- `trace_signal_path`: Verify signal connectivity
- `verify_ground_plane`: Check ground connections
- `check_differential_pairs`: 
- `analyze_signal_termination`: 

**MCU Analysis**
- `verify_mcu_boot_configuration`: Check BOOT pins
- `check_debug_interface`: Verify SWD/JTAG
- `analyze_reset_circuit`: Check reset configuration
- `verify_programming_interface`: Check programmer access
- `check_mcu_power_pin`: 

### 4. Report Generation

Combines all results into comprehensive report:
- Circuit analysis and expected behavior
- All detected issues with severity
- Step-by-step verification procedures
- Overall risk assessment
- Bringup feasibility

## Adding New Analysis Functions

The system is designed to be extensible:

1. Add Analysis Function: Create new function in analysis_functions/
2. Register Function: Add to ANALYSIS_FUNCTIONS dict
3. Update LLM Prompt: LLM will automatically use it
4. No Code Changes: LLM picks functions dynamically

Create new function in `src/analysis/`:

```python
def my_custom_analysis(params: Dict[str, Any], sch, net_build) -> AnalysisResult:
    """
    Your custom analysis logic.
    
    Params:
        custom_param: str - Description
    """
    issues = []
    recommendations = []
    details = {}
    
    # Your analysis logic here
    
    return AnalysisResult(
        function_name="my_custom_analysis",
        status="pass",  # or "fail", "warning", "info"
        summary="Short summary",
        details=details,
        issues=issues,
        recommendations=recommendations,
        severity="medium",  # critical, high, medium, low
        prevents_bringup=False
    )
```

Register in `src/analysis/__init__.py`:

```python
from .my_module import my_custom_analysis

ANALYSIS_FUNCTIONS = {
    # ... existing functions ...
    "my_custom_analysis": my_custom_analysis,
}
```

## Workflow

```
┌─────────────────┐
│  .kicad_sch     │
│  File Upload    │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Parse & Build  │
│  Netlist        │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Generate       │
│  Summary        │
└────────┬────────┘
         │
         v
┌─────────────────┐       ┌──────────────┐
│  LLM Analysis   │──────>│   OpenAI     │
│  (Primary)      │       └──────────────┘
└────────┬────────┘
         │ (if fails)
         v
┌─────────────────┐       ┌──────────────┐
│  LLM Analysis   │──────>│   Gemini     │
│  (Fallback)     │       └──────────────┘
└────────┬────────┘
         │ (if fails)
         v
┌─────────────────┐
│  Heuristic      │
│  Analysis       │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Execute        │
│  Analysis       │
│  Functions      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Generate       │
│  Final Report   │
└─────────────────┘

User runs: python main_enhanced.py circuit.kicad_sch --llm openai

1. Parse schematic file → Extract components, wires, labels
   
2. Build netlist → Identify which components connect where
   
3. Generate summary → Create compact JSON with all debug-relevant info
   
4. Send to LLM → "What circuit is this? What functions should I run?"
   
5. LLM responds → JSON with circuit type, issues, and function list
   
6. Execute functions → Run each recommended analysis function
   
7. Compile report → Combine all results into final JSON
   
8. Output → JSON file + console summary

```

## Troubleshooting

**Q: "OPENAI_API_KEY environment variable not set"**  
A: Either set the API key or use `--llm heuristic` for offline analysis

**Q: Analysis takes a long time**  
A: LLM calls can take 5-15 seconds. Use `--llm heuristic` for instant results.

**Q: Report says "unknown circuit type"**  
A: The heuristic fallback has limited circuit recognition. Consider using LLM analysis.

**Q: Function 'xyz' not found**  
A: The LLM suggested a function that doesn't exist. This is safe - it's logged as an error result.

## License

MIT License

## Contributing

Pull requests welcome! To add support for new circuit types:
1. Add analysis functions for that circuit
2. Update heuristic detector in `src/indicators.py`
3. Update LLM prompt examples in `src/llm_analysis.py`