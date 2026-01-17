#!/usr/bin/env python3

import wx
import sys
import os
import traceback
from pathlib import Path

# ==========================================================
# Setup paths to find our modules
# ==========================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ==========================================================
# Import our analysis backend via BRIDGE
# ==========================================================
try:
    from bridge import run 
    from src.export import export_checklist_markdown, export_checklist_json
    BACKEND_AVAILABLE = True
except ImportError as e:
    BACKEND_AVAILABLE = False
    IMPORT_ERROR = str(e)
    print(f"ERROR: Could not import analysis backend: {e}")
    print("\nMake sure you have installed all dependencies:")
    print("  pip install sexpdata pydantic wxPython")
    print("\nAnd that bridge.py exists in the same directory")


# ==========================================================
# Main Dialog (Standalone Version)
# ==========================================================
class BringUpAssistantDialog(wx.Dialog):
    """Main dialog window for the bring-up assistant"""
    
    def __init__(self, parent, report, schematic_path):
        super().__init__(
            parent,
            title="PCB Bring-Up Assistant",
            size=(1100, 800),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )

        self.report = report
        self.schematic_path = schematic_path
        self.step_checkboxes = {}
        self.step_panels = {}

        self.SetMinSize((900, 650))
        self._build_ui()
        self.Centre()

    def _build_ui(self):
        """Build the main UI"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="PCB Schematic Bring-Up Assistant")
        font = title.GetFont()
        font.PointSize += 7
        font = font.Bold()
        title.SetFont(font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 12)

        # Subtitle with file info
        subtitle = wx.StaticText(
            self,
            label=f"Schematic: {Path(self.schematic_path).name}",
        )
        subtitle_font = subtitle.GetFont()
        subtitle_font.PointSize += 1
        subtitle.SetFont(subtitle_font)
        subtitle.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.CENTER, 10)

        # Risk indicator
        overall_risk = self.report.get('overall_risk', {})
        risk_level = overall_risk.get('level', 'unknown')
        risk_score = overall_risk.get('score', 0)
        
        risk_panel = self._create_risk_panel(risk_level, risk_score)
        main_sizer.Add(risk_panel, 0, wx.EXPAND | wx.ALL, 5)

        # Notebook with tabs
        notebook = wx.Notebook(self)
        notebook.AddPage(self._create_summary_tab(notebook), "Detection Summary")
        notebook.AddPage(self._create_findings_tab(notebook), "Issues & Warnings")
        notebook.AddPage(self._create_checklist_tab(notebook), "Bring-Up Checklist")
        notebook.AddPage(self._create_tools_tab(notebook), "Debug Tools")
        
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Button bar
        main_sizer.Add(self._create_button_bar(), 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _create_risk_panel(self, level, score):
        """Create the risk indicator panel"""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        colors = {
            'low': (76, 175, 80),
            'medium': (255, 152, 0),
            'high': (244, 67, 54),
            'unknown': (158, 158, 158)
        }
        color = wx.Colour(*colors.get(level, colors['unknown']))
        
        risk_label = wx.StaticText(panel, label=f"Overall Risk: {level.upper()}")
        font = risk_label.GetFont()
        font.PointSize += 2
        font = font.Bold()
        risk_label.SetFont(font)
        risk_label.SetForegroundColour(color)
        
        score_label = wx.StaticText(panel, label=f"  (Score: {score}/100)")
        score_label.SetForegroundColour(wx.Colour(120, 120, 120))
        
        sizer.Add(risk_label, 0, wx.ALL, 5)
        sizer.Add(score_label, 0, wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel

    def _create_summary_tab(self, parent):
        """Create the detection summary tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        detected = self.report.get("detected", {})

        def add_section(title, items):
            box = wx.StaticBox(panel, label=f"{title}")
            bs = wx.StaticBoxSizer(box, wx.VERTICAL)
            
            if items:
                for item in items:
                    text = wx.StaticText(panel, label=f"  • {item}")
                    bs.Add(text, 0, wx.ALL, 3)
            else:
                text = wx.StaticText(panel, label="  None detected")
                text.SetForegroundColour(wx.Colour(150, 150, 150))
                bs.Add(text, 0, wx.ALL, 3)
            
            sizer.Add(bs, 0, wx.EXPAND | wx.ALL, 5)

        add_section("Power Nets", detected.get("power_nets", []))
        add_section("MCU / Main IC", detected.get("mcu_symbols", []))
        add_section("Clock Sources", detected.get("clock_sources", []))
        add_section("Reset Nets", detected.get("reset_nets", []))
        add_section("Debug Interfaces", detected.get("debug_ifaces", []))

        if 'topology' in self.report:
            topo = self.report['topology']
            info_text = (
                f"Total Components: {topo.get('total_components', 0)}  |  "
                f"ICs: {topo.get('ics', 0)}  |  "
                f"Missing Decoupling: {len(topo.get('missing_decoupling_caps', []))}"
            )
            info_label = wx.StaticText(panel, label=info_text)
            info_label.SetForegroundColour(wx.Colour(100, 100, 100))
            sizer.Add(info_label, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        return panel

    def _create_findings_tab(self, parent):
        """Create the findings/issues tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        findings = self.report.get('findings', [])
        
        if not findings:
            no_issues = wx.StaticText(
                panel,
                label="No critical issues detected!\n\n"
                      "The schematic passed automated checks.\n"
                      "Proceed with the bring-up checklist."
            )
            font = no_issues.GetFont()
            font.PointSize += 2
            no_issues.SetFont(font)
            no_issues.SetForegroundColour(wx.Colour(76, 175, 80))
            sizer.Add(no_issues, 0, wx.ALL | wx.CENTER, 20)
        else:
            scroll = wx.ScrolledWindow(panel)
            scroll.SetScrollRate(10, 10)
            scroll_sizer = wx.BoxSizer(wx.VERTICAL)
            
            for finding in findings:
                finding_panel = self._create_finding_panel(scroll, finding)
                scroll_sizer.Add(finding_panel, 0, wx.EXPAND | wx.ALL, 5)
            
            scroll.SetSizer(scroll_sizer)
            sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_finding_panel(self, parent, finding):
        """Create a panel for a single finding"""
        panel = wx.Panel(parent, style=wx.BORDER_SIMPLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        severity_colors = {
            'critical': (244, 67, 54),
            'high': (255, 152, 0),
            'medium': (255, 193, 7),
            'low': (76, 175, 80)
        }
        severity = finding.get('severity', 'medium')
        color = wx.Colour(*severity_colors.get(severity, (150, 150, 150)))
        
        title = wx.StaticText(panel, label=f"{finding['summary']}")
        title_font = title.GetFont()
        title_font = title_font.Bold()
        title.SetFont(title_font)
        title.SetForegroundColour(color)
        sizer.Add(title, 0, wx.ALL, 5)
        
        why_text = wx.StaticText(panel, label=f"Why: {finding['why']}")
        why_text.Wrap(900)
        sizer.Add(why_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        if finding.get('fix_suggestion'):
            fix_text = wx.StaticText(panel, label=f"Fix: {finding['fix_suggestion']}")
            fix_text.Wrap(900)
            fix_text.SetForegroundColour(wx.Colour(33, 150, 243))
            sizer.Add(fix_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        if finding.get('prevents_bringup'):
            blocker = wx.StaticText(panel, label="BLOCKS BRING-UP")
            blocker.SetForegroundColour(wx.Colour(244, 67, 54))
            blocker_font = blocker.GetFont()
            blocker_font = blocker_font.Bold()
            blocker.SetFont(blocker_font)
            sizer.Add(blocker, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        panel.SetSizer(sizer)
        panel.SetBackgroundColour(wx.Colour(250, 250, 250))
        return panel

    def _create_checklist_tab(self, parent):
        """Create the bring-up checklist tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        instructions = wx.StaticText(
            panel,
            label="Follow these steps in order. Check each box as you complete it."
        )
        instructions.SetForegroundColour(wx.Colour(100, 100, 100))
        sizer.Add(instructions, 0, wx.ALL, 10)

        scroll = wx.ScrolledWindow(panel)
        scroll.SetScrollRate(10, 10)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        for step in self.report.get("checklist", []):
            step_panel = self._create_step_panel(scroll, step)
            scroll_sizer.Add(step_panel, 0, wx.EXPAND | wx.ALL, 5)

        scroll.SetSizer(scroll_sizer)
        sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel

    def _create_step_panel(self, parent, step):
        """Create a panel for a single checklist step"""
        panel = wx.Panel(parent, style=wx.BORDER_SIMPLE)
        panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        risk_colors = {
            'low': (76, 175, 80),
            'medium': (255, 152, 0),
            'high': (244, 67, 54)
        }
        risk_color = wx.Colour(*risk_colors.get(step.get('risk', 'medium'), (150, 150, 150)))
        
        checkbox = wx.CheckBox(panel, label=f"[{step['sequence']}] {step['title']}")
        checkbox_font = checkbox.GetFont()
        checkbox_font.PointSize += 1
        checkbox_font = checkbox_font.Bold()
        checkbox.SetFont(checkbox_font)
        checkbox.SetForegroundColour(risk_color)
        sizer.Add(checkbox, 0, wx.ALL, 5)
        
        self.step_checkboxes[step['id']] = checkbox
        
        meta_text = f"Category: {step['category'].upper()}"
        if step.get('component'):
            meta_text += f" | Component: {step['component']}"
        if step.get('pins'):
            meta_text += f" | Pins: {', '.join(step['pins'])}"
        
        meta = wx.StaticText(panel, label=meta_text)
        meta.SetForegroundColour(wx.Colour(120, 120, 120))
        sizer.Add(meta, 0, wx.LEFT | wx.RIGHT, 10)
        
        instr_label = wx.StaticText(panel, label="Test Procedure:")
        instr_label_font = instr_label.GetFont()
        instr_label_font = instr_label_font.Bold()
        instr_label.SetFont(instr_label_font)
        sizer.Add(instr_label, 0, wx.LEFT | wx.TOP, 10)
        
        instr = wx.StaticText(panel, label=step['instruction'])
        instr.Wrap(950)
        sizer.Add(instr, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        exp_label = wx.StaticText(panel, label="Expected Result:")
        exp_label_font = exp_label.GetFont()
        exp_label_font = exp_label_font.Bold()
        exp_label.SetFont(exp_label_font)
        sizer.Add(exp_label, 0, wx.LEFT, 10)
        
        exp = wx.StaticText(panel, label=step['expected'])
        exp.SetForegroundColour(wx.Colour(76, 175, 80))
        exp.Wrap(950)
        sizer.Add(exp, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        if step.get('likely_faults'):
            faults_text = "If this step fails:\n" + "\n".join(
                f"  • {fault}" for fault in step['likely_faults']
            )
            faults = wx.StaticText(panel, label=faults_text)
            faults.SetForegroundColour(wx.Colour(244, 67, 54))
            faults.Wrap(950)
            sizer.Add(faults, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        if step.get('prevents_bringup'):
            warning = wx.StaticText(panel, label="CRITICAL: This step must pass for the board to function")
            warning.SetForegroundColour(wx.Colour(244, 67, 54))
            warning_font = warning.GetFont()
            warning_font = warning_font.Bold()
            warning.SetFont(warning_font)
            sizer.Add(warning, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        panel.SetSizer(sizer)
        self.step_panels[step['id']] = panel
        return panel

    def _create_tools_tab(self, parent):
        """Create the debug tools tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        if self.report.get('recommended_test_points'):
            tp_box = wx.StaticBox(panel, label="Recommended Test Points")
            tp_sizer = wx.StaticBoxSizer(tp_box, wx.VERTICAL)
            
            for tp in self.report['recommended_test_points']:
                tp_text = f"• {tp['net']}: {tp['why']} (Measure: {tp['measurement']})"
                tp_label = wx.StaticText(panel, label=tp_text)
                tp_label.Wrap(950)
                tp_sizer.Add(tp_label, 0, wx.ALL, 3)
            
            sizer.Add(tp_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        if self.report.get('scope_config'):
            scope = self.report['scope_config']
            scope_box = wx.StaticBox(panel, label="Oscilloscope Configuration")
            scope_sizer = wx.StaticBoxSizer(scope_box, wx.VERTICAL)
            
            scope_text = f"Circuit Type: {scope.get('circuit_type', 'Unknown')}\n"
            scope_text += f"Timebase: {scope.get('timebase', 'Auto')}\n\n"
            
            for ch in scope.get('channels', []):
                scope_text += f"Channel {ch['ch']}: {ch['probe']}\n"
                scope_text += f"  Scale: {ch['scale']}, Coupling: {ch['coupling']}\n"
            
            if scope.get('expected_waveform'):
                wf = scope['expected_waveform']
                scope_text += f"\nExpected Waveform:\n"
                scope_text += f"  Frequency: {wf['frequency_hz']} Hz\n"
                scope_text += f"  Period: {wf['period_ms']} ms\n"
                scope_text += f"  Duty Cycle: {wf['duty_cycle_pct']}%\n"
            
            scope_label = wx.StaticText(panel, label=scope_text)
            scope_label.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            scope_sizer.Add(scope_label, 0, wx.ALL, 5)
            
            sizer.Add(scope_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        guide_box = wx.StaticBox(panel, label="General Bring-Up Guide")
        guide_sizer = wx.StaticBoxSizer(guide_box, wx.VERTICAL)
        
        guide_text = """Recommended Bring-Up Order:

1. Visual Inspection
   - Check for solder bridges, cold joints, tombstoned components
   - Verify component orientation (ICs, diodes, electrolytic caps)
   - Check for missing components

2. Power Rails (NO LOAD)
   - Measure power supply output before connecting to board
   - Check for shorts between power rails and ground
   - Verify voltage regulator outputs (if any)

3. First Power-On (CURRENT LIMITED)
   - Set current limit to 100mA initially
   - Monitor current draw
   - Check all power rail voltages

4. Sequential Verification
   - Reset signals
   - Clock sources
   - Communication interfaces

Use current limiting on first power-on to prevent damage!
"""
        
        guide_label = wx.StaticText(panel, label=guide_text)
        guide_sizer.Add(guide_label, 0, wx.ALL, 5)
        
        sizer.Add(guide_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        return panel

    def _create_button_bar(self):
        """Create the bottom button bar"""
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        export_btn = wx.Button(self, label="Export Checklist")
        export_btn.Bind(wx.EVT_BUTTON, self._on_export)
        sizer.Add(export_btn, 0, wx.ALL, 5)
        
        open_new_btn = wx.Button(self, label="Open Another Schematic")
        open_new_btn.Bind(wx.EVT_BUTTON, self._on_open_new)
        sizer.Add(open_new_btn, 0, wx.ALL, 5)
        
        help_btn = wx.Button(self, label="Help")
        help_btn.Bind(wx.EVT_BUTTON, self._on_help)
        sizer.Add(help_btn, 0, wx.ALL, 5)

        sizer.AddStretchSpacer()

        close_btn = wx.Button(self, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sizer.Add(close_btn, 0, wx.ALL, 5)

        return sizer

    def _on_export(self, event):
        """Handle export button click"""
        dlg = wx.FileDialog(
            self,
            "Export Checklist",
            defaultFile=f"{Path(self.schematic_path).stem}_bringup",
            wildcard="Markdown (*.md)|*.md|JSON (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            try:
                if path.endswith(".json"):
                    export_checklist_json(self.report, path)
                else:
                    if not path.endswith(".md"):
                        path += ".md"
                    export_checklist_markdown(self.report, path)
                
                wx.MessageBox(
                    f"Checklist exported successfully to:\n{path}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION
                )
            except Exception as e:
                wx.MessageBox(
                    f"Export failed:\n{str(e)}",
                    "Export Error",
                    wx.OK | wx.ICON_ERROR
                )

        dlg.Destroy()

    def _on_open_new(self, event):
        """Open a new schematic file"""
        wildcard = "KiCad Schematic (*.kicad_sch)|*.kicad_sch|All files (*.*)|*.*"
        dlg = wx.FileDialog(
            self,
            message="Select Another Schematic to Analyze",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            new_path = dlg.GetPath()
            dlg.Destroy()
            
            self.Close()
            analyze_and_show(new_path)
        else:
            dlg.Destroy()

    def _on_help(self, event):
        """Show help dialog"""
        help_text = """PCB Bring-Up Assistant - Help

This tool analyzes your KiCad schematic and generates an automated
bring-up checklist for debugging your PCB.

How to use:
1. Run this application
2. Select a .kicad_sch file to analyze
3. Review the detection summary and findings
4. Follow the checklist steps in order
5. Export the checklist for documentation

Tips:
• Start with power rails before anything else
• Use current limiting on first power-on
• Mark each step as you complete it
• Pay attention to CRITICAL warnings
• Export the checklist to share with your team

Command Line Usage:
  python bringup_plugin.py [schematic.kicad_sch]

For more information, visit:
https://github.com/evarexis/HnR2026_PCB_Debugger"""
        
        wx.MessageBox(help_text, "Help", wx.OK | wx.ICON_INFORMATION)


# ==========================================================
# Analysis Runner
# ==========================================================
def analyze_and_show(schematic_path):
    """Analyze a schematic and show the results dialog"""
    if not BACKEND_AVAILABLE:
        wx.MessageBox(
            f"Backend analysis module not available.\n\n"
            f"Error: {IMPORT_ERROR}\n\n"
            f"Please install required dependencies:\n"
            f"  pip install sexpdata pydantic wxPython\n\n"
            f"And make sure bridge.py exists",
            "Missing Dependencies",
            wx.OK | wx.ICON_ERROR
        )
        return False
    
    try:
        busy_info = wx.BusyInfo(f"Analyzing {Path(schematic_path).name}...")
        wx.SafeYield()
        
        report = run(schematic_path)
        
        del busy_info
        
        dlg = BringUpAssistantDialog(None, report, schematic_path)
        dlg.ShowModal()
        dlg.Destroy()
        
        return True
        
    except Exception as e:
        try:
            del busy_info
        except:
            pass
        
        error_msg = f"Error analyzing schematic:\n\n{str(e)}\n\n"
        error_msg += "Traceback:\n" + traceback.format_exc()
        
        wx.MessageBox(error_msg, "Analysis Error", wx.OK | wx.ICON_ERROR)
        return False


# ==========================================================
# Main Application
# ==========================================================
def main():
    """Main application entry point"""
    app = wx.App()
    
    if len(sys.argv) > 1:
        schematic_path = sys.argv[1]
        
        if not os.path.exists(schematic_path):
            wx.MessageBox(
                f"File not found:\n{schematic_path}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
            return 1
        
        analyze_and_show(schematic_path)
    
    else:
        wildcard = "KiCad Schematic (*.kicad_sch)|*.kicad_sch|All files (*.*)|*.*"
        dlg = wx.FileDialog(
            None,
            message="Select KiCad Schematic to Analyze",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            schematic_path = dlg.GetPath()
            dlg.Destroy()
            
            analyze_and_show(schematic_path)
        else:
            dlg.Destroy()
            return 0
    
    app.MainLoop()
    return 0


# ==========================================================
# Entry Point
# ==========================================================
if __name__ == "__main__":
    sys.exit(main())