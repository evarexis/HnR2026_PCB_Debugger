#!/usr/bin/env python3
import streamlit as st
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import os


from src.parse_sexp import parse_kicad_sch
from src.kicad_extract import parse_schematic
from src.netlist_build import build_nets
from src.indicators import run_detectors
from src.schematic_summary import generate_schematic_summary
from src.llm_analysis import LLMAnalyzer, LLMProvider
from src.analysis import execute_analysis_function

from main import run_heuristic_analysis, run_analysis_pipeline, generate_final_report



st.set_page_config(
    page_title="PreFab",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.markdown("""
<style>
    .risk-critical {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .risk-high {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .risk-medium {
        background-color: #fff9c4;
        border-left: 5px solid #fdd835;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .risk-low {
        background-color: #e8f5e9;
        border-left: 5px solid #4caf50;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .issue-card {
        background-color: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid #ddd;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .step-completed {
        background-color: #e8f5e9;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .step-pending {
        background-color: #fff;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'report' not in st.session_state:
        st.session_state.report = None
    if 'analysis_done' not in st.session_state:
        st.session_state.analysis_done = False
    if 'checklist_state' not in st.session_state:
        st.session_state.checklist_state = {}


def display_risk_banner(risk_data: Dict[str, Any]):
    """Display risk level banner"""
    level = risk_data.get('level', 'unknown')
    score = risk_data.get('score', 0)
    
    risk_colors = {
        'critical': ('🔴', '#f44336', '#ffebee'),
        'high': ('🟠', '#ff9800', '#fff3e0'),
        'medium': ('🟡', '#fdd835', '#fff9c4'),
        'low': ('🟢', '#4caf50', '#e8f5e9')
    }
    
    icon, color, bg_color = risk_colors.get(level, ('⚪', '#757575', '#f5f5f5'))
    
    st.markdown(f"""
    <div style="background-color: {bg_color}; border-left: 5px solid {color}; padding: 20px; border-radius: 10px; margin: 20px 0 10px 0;">
        <h2 style="margin: 0; color: {color}; text-align: center;">{icon} Overall Risk: {level.upper()}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="text-align: center; margin: 10px 0 20px 0;">
        <h1 style="font-size: 30px; font-weight: bold; color: #FFFFFF; margin: 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">Risk Score: {score}/100</h1>
    </div>
    """, unsafe_allow_html=True)


def display_metrics(report: Dict[str, Any]):
    """Display key metrics in cards"""
    overall_risk = report.get('overall_risk', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Issues",
            value=overall_risk.get('total_issues', 0),
            delta=None
        )
    
    with col2:
        st.metric(
            label="Critical Issues",
            value=overall_risk.get('critical_issues', 0),
            delta=None,
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            label="High Priority",
            value=overall_risk.get('high_priority_issues', 0),
            delta=None,
            delta_color="inverse"
        )
    
    with col4:
        can_bringup = overall_risk.get('can_attempt_bringup', False)
        st.metric(
            label="Bringup Ready",
            value="✅ YES" if can_bringup else "❌ NO"
        )


def display_circuit_analysis(report: Dict[str, Any]):
    """Display circuit analysis section"""
    st.header("Circuit Analysis")
    
    circuit_analysis = report.get('circuit_analysis', {})
    metadata = report.get('metadata', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Detected Circuit Type")
        circuit_type = circuit_analysis.get('circuit_type', 'unknown')
        confidence = circuit_analysis.get('confidence', 0)
        st.write(f"**Type:** `{circuit_type}`")
        st.write(f"**Confidence:** {confidence:.0%}")
        st.write(f"**Analysis Method:** {metadata.get('analysis_method', 'unknown')}")
        
        if circuit_analysis.get('main_ic'):
            st.write(f"**Main IC:** {circuit_analysis['main_ic']}")
    
    with col2:
        st.subheader("Expected Behavior")
        expected = report.get('expected_behavior', {})
        
        if expected.get('output_frequency_hz'):
            st.write(f"**Output Frequency:** {expected['output_frequency_hz']:.2f} Hz")
        
        if expected.get('duty_cycle_percent'):
            st.write(f"**Duty Cycle:** {expected['duty_cycle_percent']:.1f}%")
        
        if expected.get('other_behaviors'):
            st.write(f"**Notes:** {expected['other_behaviors']}")
    
    if circuit_analysis.get('purpose'):
        st.info(f"**Circuit Purpose:** {circuit_analysis['purpose']}")


def display_issues(report: Dict[str, Any]):
    """Display detected issues"""
    st.header("Detected Issues")
    
    detected_issues = report.get('detected_issues', [])
    
    if not detected_issues:
        st.success("No issues detected! Your schematic looks good.")
        return
    
    critical_issues = [i for i in detected_issues if i.get('severity') == 'critical']
    high_issues = [i for i in detected_issues if i.get('severity') == 'high']
    medium_issues = [i for i in detected_issues if i.get('severity') == 'medium']
    low_issues = [i for i in detected_issues if i.get('severity') == 'low']
    
    # Critical issues
    if critical_issues:
        st.error(f"Critical Issues ({len(critical_issues)})")
        for idx, issue in enumerate(critical_issues, 1):
            with st.expander(f"Critical #{idx}: {issue.get('issue', 'Unknown')}"):
                st.write(f"**Reason:** {issue.get('reason', 'N/A')}")
                if issue.get('debug_step'):
                    st.write(f"**Fix:** {issue['debug_step']}")
                if issue.get('components_involved'):
                    st.write(f"**Components:** {', '.join(issue['components_involved'])}")
    
    # High priority issues
    if high_issues:
        st.warning(f"High Priority Issues ({len(high_issues)})")
        for idx, issue in enumerate(high_issues, 1):
            with st.expander(f"High #{idx}: {issue.get('issue', 'Unknown')}"):
                st.write(f"**Reason:** {issue.get('reason', 'N/A')}")
                if issue.get('debug_step'):
                    st.write(f"**Fix:** {issue['debug_step']}")
    
    # Medium priority issues
    if medium_issues:
        st.info(f"Medium Priority Issues ({len(medium_issues)})")
        for idx, issue in enumerate(medium_issues, 1):
            with st.expander(f"Medium #{idx}: {issue.get('issue', 'Unknown')}", expanded=False):
                st.write(f"**Reason:** {issue.get('reason', 'N/A')}")
                if issue.get('debug_step'):
                    st.write(f"**Fix:** {issue['debug_step']}")
    
    # Low priority issues
    if low_issues:
        with st.expander(f"ℹLow Priority Issues ({len(low_issues)})", expanded=False):
            for idx, issue in enumerate(low_issues, 1):
                st.write(f"{idx}. {issue.get('reason', 'N/A')}")


def display_checklist(report: Dict[str, Any]):
    """Display interactive bring-up checklist"""
    st.header("Bring-Up Checklist")
    
    verification_steps = report.get('verification_steps', {})
    issue_steps = verification_steps.get('for_issues', [])
    general_steps = verification_steps.get('for_general_workability', [])
    
    if issue_steps:
        st.subheader("Fix Issues First")
        for step_data in issue_steps:
            step_num = step_data.get('step', 0)
            key = f"issue_step_{step_num}"
            
            if key not in st.session_state.checklist_state:
                st.session_state.checklist_state[key] = False
            
            checked = st.checkbox(
                f"**Step {step_num}:** {step_data.get('action', 'N/A')}",
                value=st.session_state.checklist_state[key],
                key=key
            )
            
            if checked:
                st.success(f"✓ Expected: {step_data.get('expected', 'Completed')}")
    
    if general_steps:
        st.subheader("General Bring-Up Steps")
        for step_data in general_steps:
            step_num = step_data.get('step', 0)
            key = f"general_step_{step_num}"
            
            if key not in st.session_state.checklist_state:
                st.session_state.checklist_state[key] = False
            
            checked = st.checkbox(
                f"**Step {step_num}:** {step_data.get('action', 'N/A')}",
                value=st.session_state.checklist_state[key],
                key=key
            )
            
            if checked:
                st.success(f"✓ Expected: {step_data.get('expected', 'Completed')}")


def display_analysis_results(report: Dict[str, Any]):
    """Display detailed analysis results"""
    st.header("Detailed Analysis Results")
    
    analysis_results = report.get('analysis_results', [])
    
    if not analysis_results:
        st.info("No detailed analysis results available.")
        return
    
    for result in analysis_results:
        status_icon = {
            'pass': '✅',
            'fail': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }.get(result.get('status', 'info'), 'ℹ️')
        
        with st.expander(f"{status_icon} {result.get('function', 'Unknown Function')} - {result.get('summary', '')}"):
            st.write(f"**Status:** {result.get('status', 'unknown').upper()}")
            st.write(f"**Severity:** {result.get('severity', 'N/A')}")
            
            if result.get('issues'):
                st.error("**Issues Found:**")
                for issue in result['issues']:
                    st.write(f"- {issue}")
            
            if result.get('recommendations'):
                st.info("**Recommendations:**")
                for rec in result['recommendations']:
                    st.write(f"- {rec}")
            
            if result.get('details'):
                with st.expander("Technical Details", expanded=False):
                    st.json(result['details'])


def run_schematic_analysis(uploaded_file, llm_choice: str, fallback_choice: str):
    """Run the complete analysis pipeline"""
    
    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.kicad_sch') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        schematic_path = Path(tmp_file.name)
    
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Parse schematic
        status_text.text("Step 1/7: Parsing schematic...")
        progress_bar.progress(14)
        tree = parse_kicad_sch(schematic_path)
        sch = parse_schematic(tree)
        
        # Step 2: Build netlist
        status_text.text("Step 2/7: Building netlist...")
        progress_bar.progress(28)
        net_build = build_nets(sch, label_tolerance=2)
        
        # Step 3: Run detectors
        status_text.text("Step 3/7: Running component detectors...")
        progress_bar.progress(42)
        detected = run_detectors(sch, net_build.nets)
        
        # Step 4: Generate summary
        status_text.text("Step 4/7: Generating schematic summary...")
        progress_bar.progress(56)
        summary = generate_schematic_summary(sch, net_build)
        
        # Step 5: LLM Analysis
        status_text.text(f"Step 5/7: Analyzing circuit with {llm_choice}...")
        progress_bar.progress(70)
        
        llm_provider_map = {
            'OpenAI': LLMProvider.OPENAI,
            'Gemini': LLMProvider.GEMINI,
            'Heuristic': LLMProvider.HEURISTIC
        }
        
        primary = llm_provider_map[llm_choice]
        fallback = llm_provider_map[fallback_choice]
        
        analyzer = LLMAnalyzer(primary=primary, secondary=fallback)
        llm_analysis = analyzer.analyze_schematic(summary)
        
        analysis_method = analyzer.used_provider.value if analyzer.used_provider else "unknown"
        
        if llm_analysis is None:
            llm_analysis = run_heuristic_analysis(sch, net_build, detected)
            analysis_method = "heuristic"
        
        # Step 6: Execute analysis pipeline
        status_text.text("Step 6/7: Executing analysis functions...")
        progress_bar.progress(84)
        analysis_results = run_analysis_pipeline(llm_analysis, sch, net_build)
        
        # Step 7: Generate final report
        status_text.text("Step 7/7: Generating final report...")
        progress_bar.progress(98)
        report = generate_final_report(
            schematic_path,
            llm_analysis,
            analysis_results,
            detected,
            analysis_method
        )
        
        progress_bar.progress(100)
        status_text.text("Analysis complete!")
        
        return report
        
    finally:
        if schematic_path.exists():
            schematic_path.unlink()


def main():
    """Main Streamlit application"""
    
    initialize_session_state()
    
    with st.sidebar:
        st.image("icon.png", width=100)
        st.title("PreLab")
        st.markdown("---")
        
        st.header("Settings")
        
        # LLM Provider Selection
        llm_choice = st.selectbox(
            "Primary Analysis Engine",
            ["OpenAI", "Gemini", "Heuristic"],
            index=0,
            help="Choose the AI engine for circuit analysis"
        )
        
        fallback_choice = st.selectbox(
            "Fallback Engine",
            ["Gemini", "Heuristic", "OpenAI"],
            index=0,
            help="Backup engine if primary fails"
        )
        
        st.markdown("---")
        
        # API Key Configuration
        if llm_choice == "OpenAI" or fallback_choice == "OpenAI":
            openai_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="Enter your OpenAI API key (optional, uses env var if not provided)"
            )
            if openai_key:
                os.environ['OPENAI_API_KEY'] = openai_key
        
        if llm_choice == "Gemini" or fallback_choice == "Gemini":
            gemini_key = st.text_input(
                "Gemini API Key",
                type="password",
                help="Enter your Gemini API key (optional, uses env var if not provided)"
            )
            if gemini_key:
                os.environ['GEMINI_API_KEY'] = gemini_key
        
        st.markdown("---")
        st.markdown("###About")
        st.markdown("""
        Prelab analyzes KiCad schematics before fabrication to catch errors 
        and generate debugging checklists.
        
        **Features:**
        - AI-powered circuit analysis
        - Automatic issue detection
        - Step-by-step debugging guide
        - Risk assessment
        """)
    
    st.title("PreLab")
    st.markdown("Upload your KiCad schematic file to analyze for potential issues before PCB fabrication.")
    
    uploaded_file = st.file_uploader(
        "Choose a .kicad_sch file",
        type=['kicad_sch'],
        help="Upload your KiCad schematic file for analysis"
    )
    
    if uploaded_file is not None:
        st.success(f"File uploaded: {uploaded_file.name}")
        
        if st.button("Run Analysis", type="primary"):
            with st.spinner("Analyzing schematic..."):
                try:
                    report = run_schematic_analysis(uploaded_file, llm_choice, fallback_choice)
                    st.session_state.report = report
                    st.session_state.analysis_done = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
                    st.exception(e)
    
    if st.session_state.analysis_done and st.session_state.report:
        report = st.session_state.report
        
        st.markdown("---")
        
        display_risk_banner(report.get('overall_risk', {}))
        
        display_metrics(report)
        
        st.markdown("---")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Summary",
            "Issues",
            "Checklist",
            "Detailed Analysis",
            "Export"
        ])
        
        with tab1:
            display_circuit_analysis(report)
            
            st.markdown("---")
            st.subheader("Component Summary")
            summary_data = report.get('summary', {})
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Components", summary_data.get('total_components', 0))
            with col2:
                power_nets = summary_data.get('power_nets_detected', [])
                st.write("**Power Nets:**")
                st.write(", ".join(power_nets) if power_nets else "None detected")
            with col3:
                clock_sources = summary_data.get('clock_sources_detected', [])
                st.write("**Clock Sources:**")
                st.write(", ".join(clock_sources) if clock_sources else "None detected")
        
        with tab2:
            display_issues(report)
        
        with tab3:
            display_checklist(report)
        
        with tab4:
            display_analysis_results(report)
        
        with tab5:
            st.header("Export Report")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("JSON Format")
                json_str = json.dumps(report, indent=2)
                st.download_button(
                    label="Download JSON Report",
                    data=json_str,
                    file_name=f"pcb_analysis_{uploaded_file.name}.json",
                    mime="application/json"
                )
            
            with col2:
                st.subheader("Summary Report")
                summary_text = f"""# PCB Analysis Report

**Schematic:** {report['metadata']['schematic_file']}
**Circuit Type:** {report['circuit_analysis']['circuit_type']}
**Analysis Method:** {report['metadata']['analysis_method']}

## Risk Assessment
- **Level:** {report['overall_risk']['level'].upper()}
- **Score:** {report['overall_risk']['score']}/100
- **Total Issues:** {report['overall_risk']['total_issues']}
- **Critical Issues:** {report['overall_risk']['critical_issues']}
- **Can Attempt Bringup:** {'YES' if report['overall_risk']['can_attempt_bringup'] else 'NO'}

## Critical Issues
{chr(10).join(f"- {blocker}" for blocker in report['overall_risk'].get('blockers', []))}
"""
                st.download_button(
                    label="Download Summary (Markdown)",
                    data=summary_text,
                    file_name=f"pcb_summary_{uploaded_file.name}.md",
                    mime="text/markdown"
                )

            with st.expander("Preview Full JSON Report"):
                st.json(report)


if __name__ == "__main__":
    main()