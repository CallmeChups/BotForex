"""
Custom CSS theme injection for BotForex Streamlit app.
Provides fintech/trading dashboard aesthetic with:
- Card styling with subtle borders & shadows
- Color-coded sections (green/blue/amber/red)
- Responsive layout helpers
- Status badge styling
- Form element improvements
- Metric card improvements
- Better table/dataframe styling
- Sidebar improvements
"""
import streamlit as st


_CSS = """
<style>
/* ─── GLOBAL RESETS & BASE ─────────────────────────────────────────────────── */
:root {
    --color-primary:     #3B82F6;
    --color-primary-dim: #1D4ED8;
    --color-success:     #22C55E;
    --color-warning:     #F59E0B;
    --color-danger:      #EF4444;
    --color-info:        #3B82F6;
    --color-bg:          #0F1117;
    --color-card:        #1A1F2E;
    --color-card-hover:  #1E2438;
    --color-border:      #2D3548;
    --color-border-dim:  #232838;
    --color-text:        #E2E8F0;
    --color-text-dim:    #94A3B8;
    --color-text-muted:  #64748B;
    --radius-sm:         6px;
    --radius-md:         10px;
    --radius-lg:         14px;
    --shadow-card:       0 2px 12px rgba(0,0,0,0.35);
    --shadow-hover:      0 4px 20px rgba(59,130,246,0.15);
    --transition:        all 0.2s ease;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--color-bg); }
::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--color-primary); }

/* ─── MAIN CONTAINER ────────────────────────────────────────────────────────── */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* ─── SIDEBAR ───────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #111624 !important;
    border-right: 1px solid var(--color-border-dim);
}
[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}
[data-testid="stSidebarNav"] {
    padding-top: 0.5rem;
}
[data-testid="stSidebarNav"] a {
    border-radius: var(--radius-sm);
    transition: var(--transition);
}
[data-testid="stSidebarNav"] a:hover {
    background-color: rgba(59,130,246,0.12) !important;
    color: var(--color-primary) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background-color: rgba(59,130,246,0.18) !important;
    border-left: 3px solid var(--color-primary);
    color: var(--color-primary) !important;
    font-weight: 600;
}

/* ─── METRIC CARDS ──────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--color-card);
    border: 1px solid var(--color-border-dim);
    border-radius: var(--radius-md);
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow-card);
    transition: var(--transition);
}
[data-testid="metric-container"]:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-hover);
    transform: translateY(-1px);
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-dim) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: var(--color-text) !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}
[data-testid="stMetricDelta"] svg { width: 14px; height: 14px; }

/* ─── BUTTONS ───────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
    border-radius: var(--radius-sm);
    font-weight: 500;
    transition: var(--transition);
    border: 1px solid transparent;
}
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stButton"] > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #3B82F6, #1D4ED8);
    color: #fff;
    border: none;
    box-shadow: 0 2px 8px rgba(59,130,246,0.3);
}
[data-testid="stButton"] > button[kind="primary"]:hover,
[data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #2563EB, #1E40AF);
    box-shadow: 0 4px 14px rgba(59,130,246,0.45);
    transform: translateY(-1px);
}
[data-testid="stButton"] > button[kind="secondary"],
[data-testid="stButton"] > button[data-testid="baseButton-secondary"] {
    background: var(--color-card);
    border: 1px solid var(--color-border);
    color: var(--color-text);
}
[data-testid="stButton"] > button[kind="secondary"]:hover,
[data-testid="stButton"] > button[data-testid="baseButton-secondary"]:hover {
    background: var(--color-card-hover);
    border-color: var(--color-primary);
    color: var(--color-primary);
}

/* ─── INPUTS & FORM ELEMENTS ────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input {
    background-color: #12172200 !important;
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--color-text) !important;
    transition: var(--transition);
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--color-primary) !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-sm) !important;
    transition: var(--transition);
}
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stMultiSelect"] > div > div:focus-within {
    border-color: var(--color-primary) !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
/* Slider */
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    background: var(--color-primary) !important;
}

/* ─── DATAFRAME / TABLES ────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--color-border-dim) !important;
}
[data-testid="stDataFrame"] table {
    border-collapse: collapse;
    width: 100%;
}
[data-testid="stDataFrame"] thead tr th {
    background: #1E2438 !important;
    color: var(--color-text-dim) !important;
    font-size: 0.76rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.65rem 0.8rem !important;
    border-bottom: 1px solid var(--color-border) !important;
}
[data-testid="stDataFrame"] tbody tr {
    transition: var(--transition);
}
[data-testid="stDataFrame"] tbody tr:hover td {
    background: rgba(59,130,246,0.07) !important;
}
[data-testid="stDataFrame"] tbody tr:nth-child(even) td {
    background: rgba(255,255,255,0.02);
}

/* ─── EXPANDER ──────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--color-border-dim) !important;
    border-radius: var(--radius-md) !important;
    background: var(--color-card) !important;
    box-shadow: var(--shadow-card);
    margin-bottom: 0.75rem;
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: var(--color-text) !important;
    padding: 0.75rem 1rem;
    border-radius: var(--radius-md) !important;
    transition: var(--transition);
}
[data-testid="stExpander"] summary:hover {
    background: rgba(59,130,246,0.08) !important;
    color: var(--color-primary) !important;
}

/* ─── TABS ──────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-testid="stTabBar"] {
    background: var(--color-card);
    border-radius: var(--radius-md) var(--radius-md) 0 0;
    border-bottom: 1px solid var(--color-border);
    gap: 0;
    padding: 0 0.5rem;
}
[data-testid="stTabs"] button[role="tab"] {
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    font-size: 0.88rem;
    font-weight: 500;
    padding: 0.6rem 1rem;
    color: var(--color-text-dim);
    transition: var(--transition);
    border: none;
    background: transparent;
}
[data-testid="stTabs"] button[role="tab"]:hover {
    color: var(--color-primary);
    background: rgba(59,130,246,0.08);
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: var(--color-primary) !important;
    border-bottom: 2px solid var(--color-primary) !important;
    font-weight: 600;
    background: transparent;
}

/* ─── ALERTS / CALLOUTS ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius-md) !important;
    border: none !important;
    font-size: 0.9rem;
}
[data-testid="stAlert"][data-baseweb="notification"] {
    background: rgba(59,130,246,0.12) !important;
    border-left: 3px solid var(--color-info) !important;
}

/* ─── PROGRESS BAR ──────────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, var(--color-primary), #60A5FA) !important;
    border-radius: 4px;
}
[data-testid="stProgressBar"] > div {
    background: var(--color-border-dim) !important;
    border-radius: 4px;
}

/* ─── DIVIDER ───────────────────────────────────────────────────────────────── */
hr {
    border-color: var(--color-border-dim) !important;
    margin: 1rem 0 !important;
}

/* ─── HEADINGS ──────────────────────────────────────────────────────────────── */
h1 { font-size: 1.8rem !important; font-weight: 700 !important; letter-spacing: -0.01em; }
h2 { font-size: 1.4rem !important; font-weight: 600 !important; }
h3 { font-size: 1.15rem !important; font-weight: 600 !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    color: var(--color-text) !important;
}

/* ─── CAPTION / HELP TEXT ───────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"], .stCaption, small {
    color: var(--color-text-muted) !important;
    font-size: 0.8rem !important;
}

/* ─── SPINNER ───────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {
    border-top-color: var(--color-primary) !important;
}

/* ─── COLUMN GAPS ───────────────────────────────────────────────────────────── */
[data-testid="column"] { gap: 0.75rem; }

/* ─── CUSTOM CARD CLASSES ───────────────────────────────────────────────────── */
.bf-card {
    background: var(--color-card);
    border: 1px solid var(--color-border-dim);
    border-radius: var(--radius-md);
    padding: 1.1rem 1.3rem;
    box-shadow: var(--shadow-card);
    margin-bottom: 0.75rem;
    transition: var(--transition);
}
.bf-card:hover {
    border-color: var(--color-border);
    box-shadow: var(--shadow-hover);
}
.bf-card-blue  { border-left: 3px solid var(--color-primary) !important; }
.bf-card-green { border-left: 3px solid var(--color-success) !important; }
.bf-card-amber { border-left: 3px solid var(--color-warning) !important; }
.bf-card-red   { border-left: 3px solid var(--color-danger) !important; }

/* ─── SECTION HEADER ────────────────────────────────────────────────────────── */
.bf-section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 1.2rem 0 0.6rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--color-border-dim);
}
.bf-section-icon {
    font-size: 1.2rem;
    line-height: 1;
}
.bf-section-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--color-text);
    margin: 0;
}
.bf-section-desc {
    font-size: 0.8rem;
    color: var(--color-text-muted);
    margin-top: 0.15rem;
}

/* ─── STATUS BADGES ─────────────────────────────────────────────────────────── */
.bf-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.73rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    line-height: 1.4;
    white-space: nowrap;
}
.bf-badge::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.9;
}
.bf-badge-running {
    background: rgba(34,197,94,0.15);
    color: #4ADE80;
    border: 1px solid rgba(34,197,94,0.3);
}
.bf-badge-stopped {
    background: rgba(239,68,68,0.15);
    color: #F87171;
    border: 1px solid rgba(239,68,68,0.3);
}
.bf-badge-waiting {
    background: rgba(245,158,11,0.15);
    color: #FBB65B;
    border: 1px solid rgba(245,158,11,0.3);
}
.bf-badge-error {
    background: rgba(239,68,68,0.18);
    color: #FC8181;
    border: 1px solid rgba(239,68,68,0.4);
}
.bf-badge-success {
    background: rgba(34,197,94,0.15);
    color: #4ADE80;
    border: 1px solid rgba(34,197,94,0.3);
}
.bf-badge-info {
    background: rgba(59,130,246,0.15);
    color: #60A5FA;
    border: 1px solid rgba(59,130,246,0.3);
}
.bf-badge-live {
    background: rgba(239,68,68,0.15);
    color: #F87171;
    border: 1px solid rgba(239,68,68,0.3);
    animation: bf-pulse 2s infinite;
}
.bf-badge-test {
    background: rgba(245,158,11,0.15);
    color: #FBB65B;
    border: 1px solid rgba(245,158,11,0.3);
}

@keyframes bf-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.65; }
}

/* ─── INFO / METRIC CARD ────────────────────────────────────────────────────── */
.bf-info-card {
    background: var(--color-card);
    border: 1px solid var(--color-border-dim);
    border-radius: var(--radius-md);
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow-card);
    transition: var(--transition);
    text-align: center;
}
.bf-info-card:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-hover);
    transform: translateY(-1px);
}
.bf-info-card-icon { font-size: 1.5rem; margin-bottom: 0.3rem; display: block; }
.bf-info-card-label {
    font-size: 0.73rem;
    color: var(--color-text-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    margin-bottom: 0.3rem;
}
.bf-info-card-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text);
    line-height: 1.2;
}
.bf-info-card-delta {
    font-size: 0.78rem;
    margin-top: 0.2rem;
    font-weight: 500;
}
.bf-info-card-delta.positive { color: var(--color-success); }
.bf-info-card-delta.negative { color: var(--color-danger); }
.bf-info-card-delta.neutral  { color: var(--color-text-muted); }

/* Color variants for info card left border */
.bf-info-card-blue  { border-top: 2px solid var(--color-primary); }
.bf-info-card-green { border-top: 2px solid var(--color-success); }
.bf-info-card-amber { border-top: 2px solid var(--color-warning); }
.bf-info-card-red   { border-top: 2px solid var(--color-danger); }

/* ─── ALERT BOXES ───────────────────────────────────────────────────────────── */
.bf-alert {
    border-radius: var(--radius-md);
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.88rem;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
}
.bf-alert-icon { font-size: 1rem; flex-shrink: 0; margin-top: 0.05rem; }
.bf-alert-info {
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.3);
    color: #93C5FD;
}
.bf-alert-success {
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.3);
    color: #86EFAC;
}
.bf-alert-warning {
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.3);
    color: #FCD34D;
}
.bf-alert-error {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    color: #FCA5A5;
}

/* ─── SPACING UTILITIES ─────────────────────────────────────────────────────── */
.bf-mt-sm { margin-top: 0.5rem; }
.bf-mt-md { margin-top: 1rem; }
.bf-mt-lg { margin-top: 1.5rem; }
.bf-mb-sm { margin-bottom: 0.5rem; }
.bf-mb-md { margin-bottom: 1rem; }
.bf-mb-lg { margin-bottom: 1.5rem; }
.bf-p-sm  { padding: 0.5rem; }
.bf-p-md  { padding: 1rem; }
.bf-p-lg  { padding: 1.5rem; }

/* ─── RESPONSIVE HELPERS ────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .main .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
    .bf-info-card-value { font-size: 1.2rem; }
    h1 { font-size: 1.4rem !important; }
}

/* ─── CODE BLOCKS ───────────────────────────────────────────────────────────── */
code, pre {
    background: #0D1117 !important;
    border: 1px solid var(--color-border-dim) !important;
    border-radius: var(--radius-sm) !important;
}

/* ─── TOAST / SUCCESS MESSAGES ──────────────────────────────────────────────── */
[data-testid="stToastContainer"] {
    border-radius: var(--radius-md) !important;
}

/* ─── LOADING SPINNER OVERLAY ───────────────────────────────────────────────── */
.stSpinner > div {
    border-color: var(--color-primary) transparent transparent transparent !important;
}

/* ─── CHECKBOX & RADIO ──────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {
    color: var(--color-text) !important;
    font-size: 0.9rem;
}

/* ─── COLUMNS EQUAL HEIGHT FLEX ─────────────────────────────────────────────── */
[data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
}

/* ─── PLOTLY CHART BORDER ───────────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--color-border-dim);
}

/* ─── JSON VIEWER ───────────────────────────────────────────────────────────── */
[data-testid="stJson"] {
    background: #0D1117 !important;
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--color-border-dim) !important;
}

/* ─── MULTISELECT TAGS ──────────────────────────────────────────────────────── */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(59,130,246,0.2) !important;
    border: 1px solid rgba(59,130,246,0.4) !important;
    border-radius: 4px !important;
    color: #93C5FD !important;
    font-size: 0.78rem !important;
}

/* ─── NUMBER INPUT ARROWS ───────────────────────────────────────────────────── */
[data-testid="stNumberInput"] button {
    background: var(--color-card) !important;
    border-color: var(--color-border) !important;
    color: var(--color-text-dim) !important;
}
[data-testid="stNumberInput"] button:hover {
    background: var(--color-card-hover) !important;
    color: var(--color-primary) !important;
    border-color: var(--color-primary) !important;
}
</style>
"""


def apply_custom_theme() -> None:
    """
    Inject the BotForex custom CSS theme into the Streamlit page.
    Call once at the top of each page (after set_page_config).

    Usage:
        from src.custom_theme import apply_custom_theme
        apply_custom_theme()
    """
    st.markdown(_CSS, unsafe_allow_html=True)
