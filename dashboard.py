"""
dashboard.py — Streamlit UI for Trust-Aware Memory Intelligence System
-----------------------------------------------------------------------
Tabs:
  1. 🎬 Live Demo        — step-by-step claim walkthrough with agent reasoning
  2. 🧠 Memory Explorer  — filterable table of all memory entries
  3. 📜 Change Log       — timeline of all decisions
  4. 🔍 Provenance Viewer— click a subject → full belief evolution
  5. 📊 Analytics        — action distribution, confidence histogram
  6. 💡 Explain Belief   — natural language explanation for any fact
"""

import json
import os
from collections import Counter
from datetime import datetime

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trust-Aware Memory Intelligence System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Styling ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main { background: #0d1117; }

/* ── Gradient header ── */
.hero-header {
    background: linear-gradient(135deg, #0f3460 0%, #16213e 40%, #0f3460 100%);
    border: 1px solid #1f4e79;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 40%, rgba(99,179,237,0.08) 0%, transparent 60%);
}
.hero-title {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #63b3ed, #90cdf4, #bee3f8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 0.3rem 0;
}
.hero-sub {
    color: #718096;
    font-size: 0.95rem;
    font-weight: 400;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.badge-active       { background: #1a4731; color: #68d391; border: 1px solid #276749; }
.badge-outdated     { background: #2d2a1e; color: #f6ad55; border: 1px solid #744210; }
.badge-rejected     { background: #2d1515; color: #fc8181; border: 1px solid #742a2a; }
.badge-low_confidence { background: #1a1a2e; color: #90cdf4; border: 1px solid #2c5282; }
.badge-forgotten    { background: #1a1a1a; color: #718096; border: 1px solid #4a5568; }

/* ── Action badges ── */
.action-ACCEPTED    { background:#1a4731; color:#68d391; border:1px solid #276749; }
.action-MERGED      { background:#162f42; color:#63b3ed; border:1px solid #2b6cb0; }
.action-UPDATED     { background:#1e3a5f; color:#90cdf4; border:1px solid #2c5282; }
.action-DOWNGRADED  { background:#2d2a1e; color:#f6ad55; border:1px solid #744210; }
.action-REJECTED    { background:#2d1515; color:#fc8181; border:1px solid #742a2a; }
.action-FORGOTTEN   { background:#1a1a1a; color:#718096; border:1px solid #4a5568; }

/* ── Metric cards ── */
.metric-card {
    background: linear-gradient(135deg, #161b22, #0d1117);
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    transition: border-color 0.2s;
}
.metric-card:hover { border-color: #3d8bcd; }
.metric-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #63b3ed;
    font-family: 'JetBrains Mono', monospace;
}
.metric-label {
    font-size: 0.78rem;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

/* ── Confidence bar ── */
.conf-bar-wrap { width: 100%; background: #21262d; border-radius: 4px; height: 8px; }
.conf-bar-fill { height: 8px; border-radius: 4px; transition: width 0.3s; }

/* ── Timeline entry ── */
.timeline-item {
    border-left: 3px solid #21262d;
    padding: 0.5rem 0 0.5rem 1rem;
    margin-bottom: 0.4rem;
    position: relative;
}
.timeline-item::before {
    content: '';
    position: absolute;
    left: -6px; top: 14px;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #21262d;
}
.tl-ACCEPTED::before   { background: #68d391; }
.tl-MERGED::before     { background: #63b3ed; }
.tl-UPDATED::before    { background: #90cdf4; }
.tl-DOWNGRADED::before { background: #f6ad55; }
.tl-REJECTED::before   { background: #fc8181; }
.tl-FORGOTTEN::before  { background: #718096; }

/* ── Expander / cards ── */
.stExpander { border: 1px solid #21262d !important; border-radius: 10px !important; }

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 6px 18px;
    border: 1px solid #21262d;
    color: #718096;
    background: #161b22;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0f3460, #1a4e8a) !important;
    color: #bee3f8 !important;
    border-color: #3d8bcd !important;
}

/* Scrollable table */
.scroll-table { max-height: 480px; overflow-y: auto; }

div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def load_data():
    store, log, trace = {}, [], []
    if os.path.exists("memory_store.json"):
        with open("memory_store.json", encoding="utf-8") as f:
            store = json.load(f)
    if os.path.exists("change_log.json"):
        with open("change_log.json", encoding="utf-8") as f:
            log = json.load(f)
    if os.path.exists("pipeline_trace.json"):
        with open("pipeline_trace.json", encoding="utf-8") as f:
            trace = json.load(f)
    return store, log, trace


def flatten_store(store: dict) -> list[dict]:
    rows = []
    for key, entries in store.items():
        for e in entries:
            rows.append({**e, "_key": key})
    return rows


# ── Colour helpers ────────────────────────────────────────────────────────────

STATUS_COLOR = {
    "active":         "#68d391",
    "outdated":       "#f6ad55",
    "rejected":       "#fc8181",
    "low_confidence": "#90cdf4",
    "forgotten":      "#718096",
}
ACTION_COLOR = {
    "ACCEPTED":   "#68d391",
    "MERGED":     "#63b3ed",
    "UPDATED":    "#90cdf4",
    "DOWNGRADED": "#f6ad55",
    "REJECTED":   "#fc8181",
    "FORGOTTEN":  "#718096",
}

def conf_bar(conf: float) -> str:
    pct = int(conf * 100)
    if conf >= 0.7:   clr = "#68d391"
    elif conf >= 0.4: clr = "#f6ad55"
    else:             clr = "#fc8181"
    return (
        f'<div class="conf-bar-wrap">'
        f'<div class="conf-bar-fill" style="width:{pct}%;background:{clr}"></div>'
        f'</div><small style="color:#718096">{conf:.3f}</small>'
    )

def status_badge(status: str) -> str:
    return f'<span class="badge badge-{status}">{status}</span>'

def action_badge(action: str) -> str:
    return f'<span class="badge action-{action}">{action}</span>'


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Controls")
    if st.button("🔄 Reload Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 🚀 Run Pipeline")
    if st.button("▶ Run main.py", use_container_width=True):
        import subprocess, sys
        with st.spinner("Running pipeline…"):
            result = subprocess.run(
                [sys.executable, "main.py"],
                capture_output=True, text=True
            )
        if result.returncode == 0:
            st.success("Pipeline complete!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Pipeline failed!")
            st.code(result.stderr, language="text")

    st.markdown("---")
    st.caption("Trust-Aware Memory Intelligence System\nGenAI Hackathon 2024")


# ── Load data ─────────────────────────────────────────────────────────────────
store, log, trace = load_data()
all_entries = flatten_store(store)

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
  <div class="hero-title">🧠 Trust-Aware Memory Intelligence System</div>
  <div class="hero-sub">
    Multi-agent pipeline · Provenance tracking · Belief evolution · Explainable memory
  </div>
</div>
""", unsafe_allow_html=True)

# ── Top-level metrics ─────────────────────────────────────────────────────────
status_counts = Counter(e.get("status") for e in all_entries)
action_counts = Counter(lg.get("action") for lg in log)

c1, c2, c3, c4, c5, c6 = st.columns(6)
metrics = [
    (c1, "Total Entries",      len(all_entries),                    "📦"),
    (c2, "Active",             status_counts.get("active", 0),      "✅"),
    (c3, "Outdated",           status_counts.get("outdated", 0),    "📅"),
    (c4, "Rejected",           action_counts.get("REJECTED", 0),    "❌"),
    (c5, "Low Confidence",     status_counts.get("low_confidence", 0), "⚠️"),
    (c6, "Change Log Events",  len(log),                            "📜"),
]
for col, label, value, icon in metrics:
    with col:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-value">{icon} {value}</div>
          <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎬 Live Demo",
    "🧠 Memory Explorer",
    "📜 Change Log",
    "🔍 Provenance Viewer",
    "📊 Analytics",
    "💡 Explain Belief",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 0 — LIVE DEMO
# ════════════════════════════════════════════════════════════════════════════
with tab0:
    import pandas as pd
    import time

    st.markdown("#### 🎬 Live Demo — Step Through the Pipeline")
    st.caption(
        "Use the slider (or Auto-Play) to feed claims one by one. "
        "Watch each agent reason and the memory evolve in real time."
    )

    if not trace:
        st.warning("No pipeline trace found. Click **▶ Run main.py** in the sidebar first.")
    else:
        # Initialize custom state for step tracking
        if "step_tracker" not in st.session_state:
            st.session_state["step_tracker"] = 1

        # ── Controls row ─────────────────────────────────────────────────
        demo_col1, demo_col2, demo_col3 = st.columns([3, 1, 1])
        with demo_col1:
            step = st.slider(
                "Claim step",
                min_value=1,
                max_value=len(trace),
                value=st.session_state["step_tracker"],
                help="Drag to walk through claims one by one",
            )
            # Capture manual sliding interaction back to our state variable
            st.session_state["step_tracker"] = step

        with demo_col2:
            auto_play = st.toggle("⏩ Auto-Play", value=False, key="auto_play")
        with demo_col3:
            play_speed = st.select_slider(
                "Speed",
                options=["Slow", "Medium", "Fast"],
                value="Medium",
                key="play_speed",
            )

        speed_map = {"Slow": 1.8, "Medium": 0.9, "Fast": 0.35}

        # Auto-play: advance step then rerun
        if auto_play and step < len(trace):
            time.sleep(speed_map[play_speed])
            st.session_state["step_tracker"] = step + 1
            st.rerun()

        # Current and previous claims
        current = trace[step - 1]
        history_so_far = trace[:step]

        # ── Pipeline flow visualiser ──────────────────────────────────────
        action       = current.get("action", "?")
        verdict      = current.get("verification_verdict", "?")
        conflict_rel = current.get("conflict_relationship", "?")
        action_color = ACTION_COLOR.get(action, "#718096")

        AGENT_COLORS = {
            "extract":   "#3d8bcd",
            "verify":    "#9f7aea",
            "conflict":  "#f6ad55",
            "curate":    action_color,
        }

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0;margin:1.2rem 0 0.5rem 0;flex-wrap:wrap">
          <div style="background:#161b22;border:1px solid {AGENT_COLORS['extract']};
                      border-radius:10px;padding:0.6rem 1rem;min-width:140px;text-align:center">
            <div style="color:{AGENT_COLORS['extract']};font-weight:700;font-size:0.8rem">① EXTRACTOR</div>
            <div style="color:#e2e8f0;font-size:0.75rem;margin-top:4px">
              <code style="color:#63b3ed">{current.get('claim_id')}</code><br>
              {current.get('source_id','?')}<br>
              <span style="color:#718096">{current.get('verifiable','?')}</span>
            </div>
          </div>
          <div style="color:#4a5568;font-size:1.2rem;padding:0 6px">→</div>
          <div style="background:#161b22;border:1px solid {AGENT_COLORS['verify']};
                      border-radius:10px;padding:0.6rem 1rem;min-width:150px;text-align:center">
            <div style="color:{AGENT_COLORS['verify']};font-weight:700;font-size:0.8rem">② VERIFIER</div>
            <div style="color:#e2e8f0;font-size:0.75rem;margin-top:4px">
              Reliability: <b style="color:#9f7aea">{current.get('source_reliability',0):.2f}</b><br>
              Conf: <b style="color:#9f7aea">{current.get('adjusted_confidence',0):.3f}</b><br>
              <span style="color:#718096">{verdict}</span>
            </div>
          </div>
          <div style="color:#4a5568;font-size:1.2rem;padding:0 6px">→</div>
          <div style="background:#161b22;border:1px solid {AGENT_COLORS['conflict']};
                      border-radius:10px;padding:0.6rem 1rem;min-width:150px;text-align:center">
            <div style="color:{AGENT_COLORS['conflict']};font-weight:700;font-size:0.8rem">③ DETECTOR</div>
            <div style="color:#e2e8f0;font-size:0.75rem;margin-top:4px">
              {conflict_rel}<br>
              <span style="color:#718096;font-size:0.7rem">
                {current.get('existing_best_object','—')[:30] or 'No prior memory'}
              </span>
            </div>
          </div>
          <div style="color:#4a5568;font-size:1.2rem;padding:0 6px">→</div>
          <div style="background:#161b22;border:2px solid {action_color};
                      border-radius:10px;padding:0.6rem 1rem;min-width:130px;text-align:center;
                      box-shadow:0 0 12px {action_color}44">
            <div style="color:{action_color};font-weight:700;font-size:0.8rem">④ CURATOR</div>
            <div style="color:{action_color};font-size:1.1rem;font-weight:700;margin-top:4px">
              {action}
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Current claim card ────────────────────────────────────────────
        label_color = {"SUPPORTS": "#68d391", "REFUTES": "#fc8181", "NOT ENOUGH INFO": "#f6ad55"}
        lc = label_color.get(current.get("label", ""), "#718096")
        conf_now = current.get("adjusted_confidence", 0)
        conf_pct = int(conf_now * 100)
        conf_clr = "#68d391" if conf_now >= 0.7 else ("#f6ad55" if conf_now >= 0.4 else "#fc8181")

        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.markdown("##### 📋 Incoming Claim")
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#161b22,#0d1117);
                        border:1px solid #21262d;border-radius:12px;padding:1.2rem 1.5rem">
              <div style="color:#bee3f8;font-size:1rem;font-weight:600;margin-bottom:0.8rem">
                "{current.get('claim_text','')}"
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.82rem">
                <div><span style="color:#718096">Subject:</span>
                  <span style="color:#e2e8f0"> {current.get('subject','')}</span></div>
                <div><span style="color:#718096">Predicate:</span>
                  <span style="color:#e2e8f0"> {current.get('predicate','')}</span></div>
                <div><span style="color:#718096">Object:</span>
                  <span style="color:#e2e8f0"> {current.get('object','')}</span></div>
                <div><span style="color:#718096">Source:</span>
                  <span style="color:#e2e8f0"> {current.get('source_id','')}</span></div>
                <div><span style="color:#718096">Label:</span>
                  <span style="color:{lc};font-weight:600"> {current.get('label','')}</span></div>
                <div><span style="color:#718096">Timestamp:</span>
                  <span style="color:#e2e8f0"> {str(current.get('timestamp',''))[:10]}
                  {'⚠️ missing' if current.get('timestamp_missing') else ''}</span></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Conflict details box
            if current.get("conflict_details"):
                st.markdown(f"""
                <div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;
                            padding:0.8rem 1rem;margin-top:0.6rem;font-size:0.82rem">
                  <span style="color:#718096">🔍 Conflict: </span>
                  <span style="color:#a0aec0">{current.get('conflict_details','')}</span>
                </div>
                """, unsafe_allow_html=True)

        with right_col:
            st.markdown("##### ⚖️ Agent Decision")
            flags = current.get("verification_flags", [])
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0f1923,#0d1117);
                        border:2px solid {action_color};border-radius:12px;
                        padding:1.2rem 1.5rem;box-shadow:0 0 20px {action_color}22">
              <div style="font-size:1.6rem;font-weight:800;color:{action_color};text-align:center">
                {action}
              </div>
              <div style="margin:0.8rem 0">
                <div style="color:#718096;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em">Confidence</div>
                <div style="background:#21262d;border-radius:6px;height:12px;margin-top:4px">
                  <div style="width:{conf_pct}%;height:12px;border-radius:6px;
                              background:{conf_clr};transition:width 0.4s"></div>
                </div>
                <div style="color:{conf_clr};font-family:'JetBrains Mono',monospace;
                            font-size:1rem;font-weight:700;margin-top:4px">{conf_now:.3f}</div>
              </div>
              <div style="color:#718096;font-size:0.78rem">
                Flags: {' · '.join(flags) if flags else 'none'}
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # ── Live memory state (up to this step) ───────────────────────────
        bottom_left, bottom_right = st.columns([3, 2])

        with bottom_left:
            st.markdown(f"##### 🧠 Memory State after Step {step}/{len(trace)}")

            # Build a mini memory from trace so far
            seen_subjects: dict = {}
            action_tally: dict = {}
            for t in history_so_far:
                key2 = f"{t.get('subject','')} | {t.get('predicate','')}"
                act  = t.get("action", "?")
                action_tally[act] = action_tally.get(act, 0) + 1
                if act in ("ACCEPTED", "MERGED", "UPDATED"):
                    seen_subjects[key2] = {
                        "object": t.get("object", ""),
                        "conf":   t.get("adjusted_confidence", 0),
                        "action": act,
                        "source": t.get("source_id", ""),
                    }
                elif act == "DOWNGRADED" and key2 in seen_subjects:
                    seen_subjects[key2]["conf"] = max(
                        seen_subjects[key2]["conf"] - 0.08, 0
                    )

            if seen_subjects:
                rows_html = ""
                for k, v in sorted(seen_subjects.items(),
                                   key=lambda x: -x[1]["conf"])[:12]:
                    c2 = v["conf"]
                    pct2 = int(c2 * 100)
                    clr2 = "#68d391" if c2 >= 0.7 else ("#f6ad55" if c2 >= 0.4 else "#fc8181")
                    ac   = v["action"]
                    aclr = ACTION_COLOR.get(ac, "#718096")
                    rows_html += f"""
                    <div style="display:grid;grid-template-columns:2fr 1.5fr 80px;
                                gap:8px;align-items:center;padding:5px 0;
                                border-bottom:1px solid #21262d;font-size:0.78rem">
                      <div style="color:#e2e8f0">{k[:45]}</div>
                      <div style="color:#a0aec0;font-size:0.72rem">{v['object'][:30]}</div>
                      <div>
                        <div style="background:#21262d;border-radius:3px;height:6px">
                          <div style="width:{pct2}%;height:6px;border-radius:3px;background:{clr2}"></div>
                        </div>
                        <span style="color:{clr2};font-size:0.7rem">{c2:.2f}</span>
                      </div>
                    </div>"""
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid #21262d;'
                    f'border-radius:10px;padding:0.8rem 1rem">{rows_html}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No memory entries yet.")

        with bottom_right:
            st.markdown("##### 📊 Running Tally")
            tally_items = [
                ("ACCEPTED",   "#68d391"),
                ("MERGED",     "#63b3ed"),
                ("UPDATED",    "#90cdf4"),
                ("DOWNGRADED", "#f6ad55"),
                ("REJECTED",   "#fc8181"),
                ("FORGOTTEN",  "#718096"),
            ]
            total_so_far = len(history_so_far)
            tally_html = ""
            for tact, tclr in tally_items:
                cnt = action_tally.get(tact, 0)
                pct_t = int(cnt / max(total_so_far, 1) * 100)
                tally_html += f"""
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <span style="color:{tclr};font-family:'JetBrains Mono',monospace;
                               font-size:0.78rem;width:90px">{tact}</span>
                  <div style="flex:1;background:#21262d;border-radius:4px;height:10px">
                    <div style="width:{pct_t}%;height:10px;border-radius:4px;background:{tclr}"></div>
                  </div>
                  <span style="color:{tclr};font-family:'JetBrains Mono',monospace;
                               font-size:0.85rem;font-weight:700;width:24px;text-align:right">{cnt}</span>
                </div>"""
            st.markdown(
                f'<div style="background:#0d1117;border:1px solid #21262d;'
                f'border-radius:10px;padding:1rem 1.2rem">{tally_html}</div>',
                unsafe_allow_html=True,
            )

            # Progress indicator
            st.markdown(f"""
            <div style="margin-top:1rem;text-align:center">
              <div style="background:#21262d;border-radius:6px;height:8px">
                <div style="width:{int(step/len(trace)*100)}%;height:8px;border-radius:6px;
                            background:linear-gradient(90deg,#3d8bcd,#63b3ed)"></div>
              </div>
              <div style="color:#718096;font-size:0.78rem;margin-top:4px">
                {step} / {len(trace)} claims processed
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Recent decision feed ──────────────────────────────────────────
        st.markdown("---")
        st.markdown("##### 🔄 Recent Decisions (last 8)")
        recent = history_so_far[-8:][::-1]
        feed_html = ""
        for t in recent:
            a   = t.get("action", "?")
            ac  = ACTION_COLOR.get(a, "#718096")
            isc = "★ " if t.get("claim_id") == current.get("claim_id") else ""
            feed_html += f"""
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0;
                        border-bottom:1px solid #1a1f27">
              <span style="color:{ac};font-family:'JetBrains Mono',monospace;
                           font-size:0.75rem;width:80px;flex-shrink:0">{isc}{a}</span>
              <span style="color:#718096;font-family:'JetBrains Mono',monospace;
                           font-size:0.72rem;width:40px;flex-shrink:0">{t.get('claim_id','')}</span>
              <span style="color:#a0aec0;font-size:0.78rem">
                <b>{t.get('subject','')[:20]}</b> — {t.get('object','')[:40]}
              </span>
              <span style="color:{ac};font-family:'JetBrains Mono',monospace;
                           font-size:0.75rem;margin-left:auto">{t.get('adjusted_confidence',0):.3f}</span>
            </div>"""
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;'
            f'border-radius:10px;padding:0.8rem 1.2rem">{feed_html}</div>',
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Memory Explorer
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("#### Memory Store — All Entries")

    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        search_text = st.text_input("🔎 Search subject / object", placeholder="e.g. Startup A")
    with col_f2:
        status_filter = st.multiselect(
            "Filter by status",
            options=["active", "outdated", "rejected", "low_confidence", "forgotten"],
            default=["active", "outdated", "rejected", "low_confidence", "forgotten"],
        )
    with col_f3:
        min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

    filtered = [
        e for e in all_entries
        if e.get("status", "") in status_filter
        and e.get("confidence", 0) >= min_conf
        and (
            not search_text
            or search_text.lower() in e.get("subject", "").lower()
            or search_text.lower() in e.get("object", "").lower()
        )
    ]

    if not filtered:
        st.info("No entries match the current filters. Run the pipeline first if the store is empty.")
    else:
        for entry in sorted(filtered, key=lambda x: -x.get("confidence", 0)):
            status = entry.get("status", "unknown")
            conf   = entry.get("confidence", 0.0)
            color  = STATUS_COLOR.get(status, "#718096")
            with st.expander(
                f"{entry.get('subject')}  ·  {entry.get('predicate')}  →  {entry.get('object', '')[:60]}",
                expanded=False,
            ):
                r1, r2 = st.columns([3, 2])
                with r1:
                    st.markdown(f"**Subject:** `{entry.get('subject')}`")
                    st.markdown(f"**Predicate:** `{entry.get('predicate')}`")
                    st.markdown(f"**Object:** `{entry.get('object')}`")
                    st.markdown(
                        f"**Status:** {status_badge(status)}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Sources:** {', '.join(entry.get('sources', []))}")
                    st.markdown(f"**Corroborated:** {entry.get('corroboration_count', 1)}×")
                with r2:
                    st.markdown("**Confidence:**")
                    st.markdown(conf_bar(conf), unsafe_allow_html=True)
                    st.markdown(f"**First seen:** `{entry.get('first_seen', '?')[:19]}`")
                    st.markdown(f"**Last updated:** `{entry.get('last_updated', '?')[:19]}`")
                    st.markdown(f"**Claim ID:** `{entry.get('claim_id', '?')}`")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Change Log
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### Change Log — Full Decision Timeline")

    action_filter = st.multiselect(
        "Filter by action",
        options=["ACCEPTED", "MERGED", "UPDATED", "DOWNGRADED", "REJECTED", "FORGOTTEN"],
        default=["ACCEPTED", "MERGED", "UPDATED", "DOWNGRADED", "REJECTED", "FORGOTTEN"],
        key="log_action_filter",
    )

    filtered_log = [lg for lg in log if lg.get("action") in action_filter]

    if not filtered_log:
        st.info("No log entries yet. Run the pipeline first.")
    else:
        for lg in filtered_log:
            action = lg.get("action", "?")
            color  = ACTION_COLOR.get(action, "#718096")
            ts     = str(lg.get("timestamp", ""))[:19]
            delta  = lg.get("confidence_delta", 0.0)
            delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
            delta_color = "#68d391" if delta > 0 else ("#fc8181" if delta < 0 else "#718096")

            st.markdown(f"""
            <div class="timeline-item tl-{action}">
              <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                <span style="font-family:'JetBrains Mono',monospace; color:#718096; font-size:0.78rem">{ts}</span>
                {action_badge(action)}
                <span style="font-family:'JetBrains Mono',monospace; color:#718096; font-size:0.8rem">{lg.get('claim_id','?')}</span>
                <span style="color:{delta_color}; font-size:0.8rem; font-family:'JetBrains Mono',monospace">Δ {delta_str}</span>
              </div>
              <div style="color:#a0aec0; font-size:0.85rem; margin-top:4px">{lg.get('reason','')}</div>
              <div style="color:#4a5568; font-size:0.78rem; margin-top:2px">
                <b>Old:</b> {lg.get('old_value') or '—'} &nbsp;→&nbsp; <b>New:</b> {lg.get('new_value') or '—'}
              </div>
            </div>
            """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Provenance Viewer
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### Provenance Viewer — Belief Evolution")

    subjects = sorted({e.get("subject", "") for e in all_entries if e.get("subject")})
    if not subjects:
        st.info("Run the pipeline to populate memory entries.")
    else:
        sel_subject = st.selectbox("Select Subject", subjects)
        predicates = sorted({
            e.get("predicate", "")
            for e in all_entries
            if e.get("subject") == sel_subject
        })
        sel_predicate = st.selectbox("Select Predicate", predicates)

        if sel_subject and sel_predicate:
            key = f"{sel_subject.lower()}||{sel_predicate.lower()}"
            entries_for_key = store.get(key, [])

            st.markdown(f"##### All memory entries for: `{sel_subject}` → `{sel_predicate}`")
            for e in entries_for_key:
                status = e.get("status", "?")
                conf   = e.get("confidence", 0.0)
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.markdown(
                        f"{status_badge(status)} **{e.get('object', '')}**  "
                        f"— Sources: *{', '.join(e.get('sources', []))}*",
                        unsafe_allow_html=True,
                    )
                with cols[1]:
                    st.markdown(conf_bar(conf), unsafe_allow_html=True)
                with cols[2]:
                    st.caption(e.get("last_updated", "")[:19])

            # History from change log
            claim_ids = {e.get("claim_id") for e in entries_for_key}
            history = [lg for lg in log if lg.get("claim_id") in claim_ids]

            if history:
                st.markdown("---")
                st.markdown("##### 📜 Belief Change History")

                # Mini confidence timeline using native streamlit chart
                conf_over_time = []
                running = 0.0
                for lg in history:
                    running = max(running + lg.get("confidence_delta", 0), 0)
                    conf_over_time.append({
                        "Step": lg.get("claim_id", "?"),
                        "Confidence": round(running, 3),
                    })
                if conf_over_time:
                    import pandas as pd
                    df_chart = pd.DataFrame(conf_over_time)
                    st.line_chart(df_chart.set_index("Step"), color="#63b3ed")

                for lg in history:
                    action = lg.get("action", "?")
                    st.markdown(
                        f"{action_badge(action)} &nbsp; "
                        f"<span style='color:#718096;font-size:0.8rem'>{str(lg.get('timestamp',''))[:19]}</span>&nbsp;"
                        f"<span style='color:#a0aec0;font-size:0.85rem'>{lg.get('reason','')}</span>",
                        unsafe_allow_html=True,
                    )


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Analytics
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("#### Analytics Dashboard")

    import pandas as pd

    if not log:
        st.info("Run the pipeline to see analytics.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("##### Action Distribution")
            action_df = pd.DataFrame(
                list(action_counts.items()), columns=["Action", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(action_df.set_index("Action"), color="#63b3ed")

        with col_b:
            st.markdown("##### Status Distribution")
            status_df = pd.DataFrame(
                list(status_counts.items()), columns=["Status", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(status_df.set_index("Status"), color="#f6ad55")

        st.markdown("---")
        st.markdown("##### Confidence Distribution (active entries)")
        active = [e for e in all_entries if e.get("status") == "active"]
        if active:
            conf_df = pd.DataFrame([{"Confidence": e.get("confidence", 0)} for e in active])
            st.histogram_chart = st.bar_chart(
                conf_df["Confidence"].value_counts(bins=10, sort=False).sort_index(),
                color="#68d391",
            )

        st.markdown("---")
        st.markdown("##### Pipeline Trace — All Claims")
        if trace:
            trace_df = pd.DataFrame(trace)[[
                "claim_id", "source_id", "source_reliability",
                "label", "verification_verdict", "conflict_relationship", "action",
                "adjusted_confidence",
            ]].rename(columns={
                "claim_id": "ID",
                "source_id": "Source",
                "source_reliability": "Reliability",
                "label": "Label",
                "verification_verdict": "Verdict",
                "conflict_relationship": "Conflict",
                "action": "Action",
                "adjusted_confidence": "Confidence",
            })
            st.dataframe(
                trace_df,
                use_container_width=True,
                height=420,
            )

        st.markdown("---")
        st.markdown("##### Source Reliability vs Actions")
        if trace:
            src_df = pd.DataFrame(trace)[["source_id", "source_reliability", "action"]]
            pivot = src_df.groupby(["source_id", "action"]).size().unstack(fill_value=0)
            st.dataframe(pivot, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — Explain Belief
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("#### 💡 Explain Belief — Why do I believe this?")
    st.caption(
        "Select a subject and predicate to get a full natural-language explanation "
        "of the current belief and its provenance history."
    )

    subjects2 = sorted({e.get("subject", "") for e in all_entries if e.get("subject")})
    if not subjects2:
        st.info("Run the pipeline first to populate memory.")
    else:
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            exp_subject = st.selectbox("Subject", subjects2, key="exp_subj")
        with exp_col2:
            exp_predicates = sorted({
                e.get("predicate", "")
                for e in all_entries
                if e.get("subject") == exp_subject
            })
            exp_predicate = st.selectbox("Predicate", exp_predicates, key="exp_pred")

        if exp_subject and exp_predicate:
            key = f"{exp_subject.lower()}||{exp_predicate.lower()}"
            entries_exp = store.get(key, [])
            active_exp  = [e for e in entries_exp if e.get("status") == "active"]
            best_exp    = max(active_exp, key=lambda e: e.get("confidence", 0)) if active_exp else \
                          (max(entries_exp, key=lambda e: e.get("confidence", 0)) if entries_exp else None)

            if best_exp:
                conf = best_exp.get("confidence", 0)
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#0f3460,#16213e);border:1px solid #1f4e79;
                            border-radius:12px;padding:1.5rem 2rem;margin:1rem 0;">
                  <div style="font-size:1.3rem;font-weight:700;color:#bee3f8;margin-bottom:0.5rem">
                    "{exp_subject}" {exp_predicate} "{best_exp.get('object')}"
                  </div>
                  <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.5rem">
                    {status_badge(best_exp.get('status','?'))}
                    <span style="color:#718096;font-size:0.85rem">Confidence: <b style="color:#63b3ed">{conf:.3f}</b></span>
                    <span style="color:#718096;font-size:0.85rem">Sources: <b style="color:#a0aec0">{', '.join(best_exp.get('sources',[]))}</b></span>
                    <span style="color:#718096;font-size:0.85rem">Corroborated: <b style="color:#a0aec0">{best_exp.get('corroboration_count',1)}×</b></span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("**📜 Belief Change History:**")
                claim_ids_exp = {e.get("claim_id") for e in entries_exp}
                history_exp   = [lg for lg in log if lg.get("claim_id") in claim_ids_exp]

                if not history_exp:
                    st.caption("No history entries found.")
                else:
                    for i, h in enumerate(history_exp, 1):
                        action = h.get("action", "?")
                        delta  = h.get("confidence_delta", 0)
                        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
                        delta_col = "#68d391" if delta > 0 else ("#fc8181" if delta < 0 else "#718096")
                        st.markdown(f"""
                        <div style="border-left:3px solid {ACTION_COLOR.get(action,'#333')};
                                    padding:0.6rem 1rem; margin-bottom:0.5rem;
                                    background:#0d1117; border-radius:0 8px 8px 0">
                          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                            <span style="color:#718096;font-size:0.75rem;font-family:'JetBrains Mono',monospace">
                              Step {i} · {str(h.get('timestamp',''))[:19]}
                            </span>
                            {action_badge(action)}
                            <span style="color:{delta_col};font-size:0.8rem;font-family:'JetBrains Mono',monospace">
                              Δ {delta_str}
                            </span>
                          </div>
                          <div style="color:#a0aec0;font-size:0.85rem;margin-top:6px">
                            {h.get('reason','')}
                          </div>
                          <div style="color:#4a5568;font-size:0.78rem;margin-top:4px">
                            <b>Old:</b> {h.get('old_value') or '—'} &nbsp;→&nbsp;
                            <b>New:</b> {h.get('new_value') or '—'}
                          </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.warning("No memory entries found for this combination.")
