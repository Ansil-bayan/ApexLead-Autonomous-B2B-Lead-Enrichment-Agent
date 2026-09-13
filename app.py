from __future__ import annotations
import asyncio
import json
import os
import pandas as pd
import streamlit as st

from core.agent import LeadEnrichmentAgent
from core.models import EnrichedLead

# Page configuration
st.set_page_config(
    page_title="ApexLead • Autonomous Lead Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Sleek Black-Themed CSS
st.markdown(
"""
<style>
    /* Dark Theme Core */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Gradual Light to Dark Background */
    .stApp {
        background: linear-gradient(
            180deg,
            #ffffff 0px,
            #f8fafc 80px,
            #eef2f6 200px,
            #cbd5e1 380px,
            #64748b 620px,
            #334155 900px,
            #1e293b 1250px,
            #0f172a 1650px,
            #07090e 2100px
        ) no-repeat !important;
        background-attachment: local !important;
        color: #0f172a;
    }
    
    /* Sidebar styling with matching gradual transition */
    section[data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #ffffff 0px,
            #f8fafc 100px,
            #e2e8f0 250px,
            #94a3b8 480px,
            #334155 750px,
            #1e293b 1050px,
            #0b0d14 100%
        ) !important;
        border-right: 1px solid rgba(203, 213, 225, 0.6);
    }
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: #0f172a !important;
        font-weight: 600;
    }

    /* Cards (in the dark lower zone) */
    .lead-card {
        background: linear-gradient(180deg, #0f131d 0%, #07090f 100%);
        border: 1px solid #232b3d;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
        transition: border-color 0.2s ease, transform 0.2s ease;
        color: #f1f5f9;
    }
    .lead-card:hover {
        border-color: #3b4661;
        transform: translateY(-2px);
    }
    
    /* Top glowing accent line */
    .top-accent-bar {
        height: 4px;
        width: 100%;
        background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 35%, #06b6d4 70%, #3b82f6 100%);
        border-radius: 9999px;
        margin-bottom: 20px;
        box-shadow: 0 2px 14px rgba(99, 102, 241, 0.4);
    }
    
    /* Top Header Container (Light zone) */
    .app-header-container {
        background: rgba(255, 255, 255, 0.92);
        backdrop-filter: blur(16px);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 28px;
        margin-bottom: 28px;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        position: relative;
        overflow: hidden;
    }
    .app-header-container::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #4f46e5, #7c3aed, #06b6d4);
    }

    /* Header typography */
    .app-title {
        font-size: 2.3rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #4338ca 75%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .app-subtitle {
        font-size: 0.92rem;
        color: #475569;
        font-family: 'JetBrains Mono', monospace;
    }
    .top-status-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(79, 70, 229, 0.1);
        border: 1px solid rgba(79, 70, 229, 0.35);
        color: #4338ca;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        margin-left: 12px;
        vertical-align: middle;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Badges */
    .badge-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
        margin-right: 8px;
    }
    .badge-confidence-high {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .badge-confidence-med {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .badge-tag {
        background: #151824;
        color: #94a3b8;
        border: 1px solid #262d40;
    }
    .badge-search {
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.4);
    }

    /* Section labels */
    .field-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
        color: #64748b;
        margin-bottom: 6px;
    }
    .field-value {
        font-size: 0.95rem;
        color: #f1f5f9;
        line-height: 1.5;
        margin-bottom: 16px;
    }

    /* Email chips */
    .email-chip {
        display: inline-block;
        background: #121622;
        border: 1px solid #232d45;
        color: #60a5fa;
        padding: 4px 10px;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }

    /* Terminal logs */
    .terminal-box {
        background-color: #07090e;
        border: 1px solid #1f2538;
        border-radius: 8px;
        padding: 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #a78bfa;
        max-height: 220px;
        overflow-y: auto;
        line-height: 1.6;
    }

    /* Leadership item */
    .leadership-item {
        background: #111420;
        border: 1px solid #1f273b;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* --- INPUT FORMS STYLING --- */
    .stTextInput > div > div > input,
    .stTextArea textarea,
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="input"] input {
        background-color: #0b0d14 !important;
        border: 1px solid #242c40 !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        padding: 10px 14px !important;
        transition: all 0.2s ease !important;
    }
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within,
    .stTextInput > div > div > input:focus,
    .stTextArea textarea:focus {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.25), 0 0 12px rgba(139, 92, 246, 0.2) !important;
        background-color: #0e111a !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #0b0d14 !important;
        border: 1px solid #242c40 !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    div[data-baseweb="select"]:focus-within {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.25) !important;
    }

    /* --- BUTTONS STYLING --- */
    div.stButton > button:first-child,
    .stDownloadButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #8b5cf6 50%, #a855f7 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.02em !important;
        border: 1px solid rgba(167, 139, 250, 0.4) !important;
        border-radius: 8px !important;
        padding: 10px 22px !important;
        box-shadow: 0 4px 18px rgba(99, 102, 241, 0.35) !important;
        transition: all 0.25s ease !important;
    }
    div.stButton > button:first-child:hover,
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #9333ea 100%) !important;
        box-shadow: 0 0 24px rgba(168, 85, 247, 0.6) !important;
        border-color: #c084fc !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
    }
    div.stButton > button:first-child:active,
    .stDownloadButton > button:active {
        transform: translateY(1px) !important;
        box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

# App Header Container (Top of the app)
st.markdown("""
<div class="top-accent-bar"></div>
<div class="app-header-container">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
        <div>
            <div class="app-title">⚡ ApexLead Intelligence <span class="top-status-badge">AI AGENT v2.0</span></div>
            <div class="app-subtitle">// Autonomous B2B Lead Enrichment Pipeline • Playwright Headless & LLM Structured Intelligence</div>
        </div>
        <div style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#818cf8; background:#16192b; border:1px solid #2d3559; padding:6px 12px; border-radius:8px; margin-top:8px;">
            ● ENGINE READY • PLAYWRIGHT ACTIVE
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Engine Settings")
    
    llm_provider = st.selectbox(
        "LLM Engine",
        options=["gemini", "openai", "groq"],
        index=0,
        help="Select the structured LLM provider to power extraction."
    )
    
    # Read env key only if present
    env_default = os.getenv(f"{llm_provider.upper()}_API_KEY", "").strip()
    api_key_input = st.text_input(
        f"{llm_provider.upper()} API Key",
        type="password",
        value=env_default,
        placeholder="Paste your API key here...",
        help=f"Enter your {llm_provider.upper()} API key. An API key is required to run."
    )

    # Strictly determine if API key is provided
    current_api_key = api_key_input.strip() if api_key_input else ""
    has_api_key = bool(current_api_key)

    # Clean os.environ if key is empty
    env_var_name = f"{llm_provider.upper()}_API_KEY"
    if current_api_key:
        os.environ[env_var_name] = current_api_key
    elif env_var_name in os.environ:
        del os.environ[env_var_name]

    st.markdown("---")
    st.markdown("### 🌐 Browser & Crawl")
    headless_mode = st.toggle("Headless Chromium", value=True, help="Run Playwright in background")
    max_subpages = 5  # Automatic optimal subpage discovery (about/team + contact)
    enable_search = st.toggle("External LinkedIn Search", value=True, help="Use search engine to discover missing founder/exec LinkedIn profiles")

    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.75rem; color:#ddd; font-family:'JetBrains Mono', monospace;">
    ✓ Headless Playwright (JS dynamic)<br>
    ✓ Context & Token Optimization<br>
    ✓ Pydantic Strict Schema<br>
    ✓ DuckDuckGo Search Fallback<br>
    ✓ Real-time Cost Tracking
    </div>
    """, unsafe_allow_html=True)

# Target Websites Input Form
st.markdown("<div class='field-label' style='font-size:0.88rem; color:#1e293b; font-weight:800; margin-bottom:8px; letter-spacing:0.04em;'>Target Websites</div>", unsafe_allow_html=True)
domains_input_text = st.text_area(
    "Target Websites",
    value="postman.com, supabase.com, vapi.ai",
    height=80,
    placeholder="Enter company domains separated by commas or line breaks (e.g. postman.com, supabase.com, vapi.ai)",
    label_visibility="collapsed"
)

run_targets_btn = st.button(
    "Run Targets", 
    use_container_width=True,
    help="Please enter an API key in the sidebar to run the agent" if not has_api_key else "Run lead enrichment pipeline"
)

# Parse targets (any number of websites)
domains_to_process = []
if run_targets_btn:
    if not has_api_key:
        st.session_state.results = []
        st.toast(f"🔑 Please provide an API key for {llm_provider.upper()} in the sidebar to run the agent!", icon="⚠️")
        st.stop()

    import re
    raw_entries = re.split(r'[\n,;]+', domains_input_text)
    cleaned = [d.strip().replace("https://", "").replace("http://", "").rstrip("/") for d in raw_entries if d.strip()]
    if not cleaned:
        st.toast("Please enter at least one target website domain.", icon="🌐")
        st.stop()
    else:
        domains_to_process = cleaned

if "results" not in st.session_state:
    st.session_state.results = []

# Execution Section
if domains_to_process:
    st.session_state.results = []
    
    st.markdown("---")
    progress_col, log_col = st.columns([1, 2])
    
    with progress_col:
        overall_progress = st.progress(0, text="Initializing autonomous agent...")
        status_metric = st.empty()
    
    with log_col:
        st.markdown("<div class='field-label'>Live Autonomous Agent Stream</div>", unsafe_allow_html=True)
        log_container = st.empty()
    
    logs = []
    
    def ui_progress_callback(step: str, msg: str):
        logs.append(f"[{step}] {msg}")
        log_container.markdown(
            f"<div class='terminal-box'>{'<br>'.join(logs[-8:])}</div>",
            unsafe_allow_html=True
        )

    agent = LeadEnrichmentAgent(
        headless=headless_mode,
        max_subpages=max_subpages,
        enable_search_fallback=enable_search,
        llm_provider=llm_provider,
        api_key=current_api_key
    )

    async def run_pipeline():
        total = len(domains_to_process)
        completed_leads = []
        for idx, dom in enumerate(domains_to_process):
            status_metric.markdown(f"**Processing:** `{dom}` ({idx+1}/{total})")
            overall_progress.progress(int((idx / total) * 100), text=f"Enriching {dom}...")
            lead = await agent.enrich_domain(dom, progress_callback=ui_progress_callback)
            completed_leads.append(lead)
        overall_progress.progress(100, text="Completed!")
        status_metric.markdown(f"**Done!** Processed {total} domains.")
        return completed_leads

    # Execute async pipeline in asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        leads_res = loop.run_until_complete(run_pipeline())
        st.session_state.results = leads_res
    finally:
        loop.close()

# Render Results
if st.session_state.results:
    leads = st.session_state.results
    st.markdown("---")
    
    # Global Metrics Bar
    total_tokens = sum(l.cost_metrics.total_tokens for l in leads)
    total_cost = sum(l.cost_metrics.estimated_cost_usd for l in leads)
    avg_conf = sum(l.data_confidence_score for l in leads) / max(1, len(leads))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Enriched Companies", len(leads))
    m2.metric("Avg Data Confidence", f"{avg_conf * 100:.0f}%")
    m3.metric("Total Tokens", f"{total_tokens:,}")
    m4.metric("Estimated Cost", f"${total_cost:.5f}")

    # Display any extraction failure warnings prominently
    errors = [l.error for l in leads if l.error]
    if errors:
        for err in set(errors):
            st.error(f"⚠️ **Extraction Issue:** {err}")

    # Tabs for Summary Table & Export Data
    tab_table, tab_export = st.tabs(["📊 Summary Table", "💾 Export Data"])

    with tab_table:
        table_rows = []
        for l in leads:
            leadership_display = []
            for m in l.key_leadership:
                if m.linkedin_url:
                    leadership_display.append(f"{m.name} ({m.role}) - {m.linkedin_url}")
                else:
                    leadership_display.append(f"{m.name} ({m.role})")

            table_rows.append({
                "Company": l.company_name,
                "Domain": l.domain,
                "Overview": l.company_overview,
                "Target Audience (ICP)": l.target_audience_icp,
                "Contacts": ", ".join(l.contact_points) if l.contact_points else "None",
                "Key Leadership": " | ".join(leadership_display) if leadership_display else "None",
                "Confidence": f"{int(l.data_confidence_score * 100)}%",
                "Tokens": f"{l.cost_metrics.total_tokens:,}",
                "Cost ($)": f"${l.cost_metrics.estimated_cost_usd:.5f}"
            })
        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_export:
        st.markdown("##### Download Enriched Intelligence")
        col_json, col_csv = st.columns(2)
        
        json_str = json.dumps([l.model_dump() for l in leads], indent=2)
        with col_json:
            st.download_button(
                label="📥 Download JSON Format",
                data=json_str,
                file_name="enriched_leads.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col_csv:
            csv_str = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV Format",
                data=csv_str,
                file_name="enriched_leads.csv",
                mime="text/csv",
                use_container_width=True
            )
