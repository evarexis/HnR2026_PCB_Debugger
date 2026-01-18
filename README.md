# PCB Debugger - Schematic Analysis

Analyze KiCad schematics before PCB fabrication to catch errors and generate beginner-friendly debugging checklists.

## Features

- **AI-Powered Analysis**: Uses OpenAI or Gemini to understand your circuit
- **Modern Web Interface**: Streamlit-based UI accessible from any browser
- **Modular Function Library**: 20+ granular analysis functions for detailed debugging
- **Automatic Fallback**: OpenAI → Gemini → Heuristics (never fails completely)
- **Beginner-Friendly**: Step-by-step debugging instructions
- **Interactive Checklist**: Track your bring-up progress with checkboxes
- **Mobile Responsive**: Works on desktop, tablet, and mobile devices
- **Cloud-Ready**: Deploy to web or share on local network
- **Comprehensive Reports**: Detailed JSON output with all findings


## Installation
For Web Interface (Recommended)
```bash
# Clone repository
git clone <your-repo>
cd pcb-debugger

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies for web interface
pip install -r requirements_streamlit.txt
```

For Command Line Iterface
```bash
# Install CLI dependencies (lighter, no web interface)
pip install -r requirements.txt
```

## API Keys (Optional)

For AI-powered analysis, API keys can be set up in 2 ways:
Web Interface
- Start the web app and enter your API keys in the sidebar
- Keys are stored only for the current session

Environment Variables (Persistent)
```bash
# For OpenAI (recommended)
export OPENAI_API_KEY="sk-..."

# For Gemini (free tier available)
export GEMINI_API_KEY="..."
```

Without API keys, the tool automatically falls back to heuristic analysis.

## Usage

### Web Interface (Recommended)

Start the web application:

```bash
streamlit run app_streamlit.py
```

The app will automatically open in your browser at `http://localhost:8501`

**Web Interface Features:**
1. **Upload**: Drag and drop your `.kicad_sch` file
2. **Configure**: Choose LLM provider in sidebar (OpenAI, Gemini, or Heuristic)
3. **Analyze**: Click "Run Analysis" button
4. **Review**: Navigate through tabs to see:
   - 📊 Summary: Circuit analysis and component inventory
   - ⚠️ Issues: Detected problems grouped by severity
   - ✅ Checklist: Interactive bring-up steps with checkboxes
   - 🔬 Detailed Analysis: Full results from all analysis functions
   - 📄 Export: Download JSON or Markdown reports
5. **Track Progress**: Check off completed steps in the bring-up checklist

### Command Line Interface

#### Basic Usage

```bash
python main.py path/to/your_schematic.kicad_sch
```

#### Choose LLM Provider

```bash
# Use OpenAI as primary, Gemini as fallback (default)
python main.py schematic.kicad_sch --llm openai --fallback gemini

# Use Gemini as primary
python main.py schematic.kicad_sch --llm gemini --fallback heuristic

# Use only heuristics (no API required)
python main.py schematic.kicad_sch --llm heuristic

### Save Output

```bash
python main.py schematic.kicad_sch --output report.json
```

## Deployment Options

### Share on Local Network

```bash
# Allow access from other devices on your network
streamlit run app_streamlit.py --server.address 0.0.0.0 --server.port 8501
```

Access from any device at `http://your-ip:8501`

### Deploy to Streamlit Cloud (Free)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Click "Deploy"
5. Share your public URL: `https://your-app.streamlit.app`

### Docker Container

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements_streamlit.txt
EXPOSE 8501
CMD ["streamlit", "run", "app_streamlit.py", "--server.address", "0.0.0.0"]
```

```bash
docker build -t pcb-debugger .
docker run -p 8501:8501 pcb-debugger
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
- `check_power_sequencing`: Verify power-on sequence

**Timing Analysis**
- `analyze_rc_timing_network`: Calculate 555 timer frequency
- `verify_crystal_circuit`: Check MCU crystal + load caps
- `check_clock_distribution`: Verify clock routing

**Signal Analysis**
- `check_floating_pins`: Find unconnected inputs
- `verify_pull_up_pull_down`: Check pull resistors
- `trace_signal_path`: Verify signal connectivity
- `verify_ground_plane`: Check ground connections
- `check_differential_pairs`: Validate differential pair routing
- `analyze_signal_termination`: Check termination resistors

**MCU Analysis**
- `verify_mcu_boot_configuration`: Check BOOT pins
- `check_debug_interface`: Verify SWD/JTAG
- `analyze_reset_circuit`: Check reset configuration
- `verify_programming_interface`: Check programmer access
- `check_mcu_power_pins`: Verify all power pins connected

### 4. Web Interface (`app_streamlit.py`)

Modern Streamlit-based web application:
- File upload with drag-and-drop
- Real-time progress indication (7-step pipeline)
- Interactive dashboard with risk assessment
- Tabbed interface for organized results
- Interactive checklist with persistent state
- Export to JSON and Markdown formats
- Responsive design for mobile devices

### 5. Report Generation

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
│  (Web/CLI)      │
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
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Display in     │
│  Web UI or      │
│  Export JSON    │
└─────────────────┘

Web Interface Flow:

1. User uploads .kicad_sch file via web interface
   
2. Parse schematic file → Extract components, wires, labels
   
3. Build netlist → Identify which components connect where
   
4. Generate summary → Create compact JSON with all debug-relevant info
   
5. Send to LLM → "What circuit is this? What functions should I run?"
   
6. LLM responds → JSON with circuit type, issues, and function list
   
7. Execute functions → Run each recommended analysis function
   
8. Compile report → Combine all results into final JSON
   
9. Display in web UI → Interactive tabs, charts, and checklists
   
10. Export → Download JSON/Markdown reports

Command Line Flow:

1. User runs: python main.py circuit.kicad_sch --llm openai
   
2-8. [Same as above]
   
9. Output → JSON file + console summary
```

## Troubleshooting

**Q: "Port 8501 is already in use"**  
A: Run `streamlit run app_streamlit.py --server.port 8502` to use a different port

**Q: "OPENAI_API_KEY environment variable not set"**  
A: Either set the API key in the web interface sidebar, set an environment variable, or use `--llm heuristic` for offline analysis

**Q: Analysis takes a long time**  
A: LLM calls can take 5-15 seconds. Use "Heuristic" mode in the web interface or `--llm heuristic` in CLI for instant results.

**Q: Report says "unknown circuit type"**  
A: The heuristic fallback has limited circuit recognition. Consider using LLM analysis with OpenAI or Gemini.

**Q: Function 'xyz' not found**  
A: The LLM suggested a function that doesn't exist. This is safe - it's logged as an error result.

**Q: File upload fails in web interface**  
A: Ensure the file is a valid `.kicad_sch` format and under 200MB (default Streamlit limit)

**Q: Web interface not loading**  
A: Check that Streamlit is installed (`pip install streamlit`) and that port 8501 is not blocked by firewall

## Project Structure

```
pcb-debugger/
├── app_streamlit.py          # Streamlit web interface
├── main.py                    # CLI interface
├── requirements_streamlit.txt # Web app dependencies
├── requirements.txt           # CLI dependencies
├── src/
│   ├── analysis/             # Analysis function modules
│   │   ├── __init__.py
│   │   ├── power_analysis.py
│   │   ├── signal_analysis.py
│   │   ├── timing_analysis.py
│   │   └── mcu_analysis.py
│   ├── parse_sexp.py         # KiCad file parser
│   ├── kicad_extract.py      # Schematic extractor
│   ├── netlist_build.py      # Netlist builder
│   ├── indicators.py         # Component detectors
│   ├── schematic_summary.py  # Summary generator
│   ├── llm_analysis.py       # LLM integration
│   ├── export.py             # Report exporters
│   └── __init__.py
├── icon.png                  # Application icon
└── README.md                 # This file
```

## License

MIT License