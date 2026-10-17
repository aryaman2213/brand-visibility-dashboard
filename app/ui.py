"""Look and feel: CSS, the Plotly template, and small layout helpers shared by every page."""
import re

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import config

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
INK, MUTED, GRID = "#0f172a", "#64748b", "#eef0f4"
ACCENT = config.SOURCE_COLORS["api"]
SOURCE_COLORS = {config.SOURCE_LABELS[k]: v for k, v in config.SOURCE_COLORS.items()}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, .stMarkdown, [data-testid="stMetric"], [data-testid="stWidgetLabel"], input, textarea,
[data-baseweb="select"], [data-testid="stSidebar"] p { font-family: %(font)s; }
/* keep Streamlit's icon font intact */
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: "Material Symbols Rounded" !important; }
.block-container { padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -0.02em; color: %(ink)s; }

/* page header */
.hero { padding: 0.25rem 0 1.1rem 0; }
.hero .eyebrow { color: %(accent)s; font-weight: 600; font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; }
.hero h1 { font-size: 2.05rem; font-weight: 800; margin: 0.15rem 0 0.35rem 0; padding: 0; }
.hero p { color: %(muted)s; font-size: 0.98rem; margin: 0; max-width: 60rem; }
.pills { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.8rem; }
.pill { background: #eef2ff; color: #3730a3; border-radius: 999px; padding: 0.22rem 0.7rem; font-size: 0.78rem; font-weight: 500; }
.pill.grey { background: #f1f5f9; color: #334155; }

/* KPI cards */
[data-testid="stMetric"] { background: #ffffff; border: 1px solid #e6e8ef; border-radius: 14px;
    padding: 0.9rem 1rem 0.8rem 1rem; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
[data-testid="stMetricLabel"] p { color: %(muted)s; font-size: 0.8rem; font-weight: 500; }
[data-testid="stMetricValue"] { color: %(ink)s; font-size: 1.55rem; font-weight: 700; }
[data-testid="stMetricValue"] > div { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* chart cards */
[class*="st-key-card-"] { background: #ffffff; border-radius: 14px !important; border-color: #e6e8ef !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); padding: 1rem 1.1rem 0.6rem 1.1rem !important; }
.card-title { font-weight: 650; font-size: 0.98rem; color: %(ink)s; margin: 0 0 0.1rem 0; }
.card-sub { color: %(muted)s; font-size: 0.8rem; margin: 0 0 0.2rem 0; }

/* insight cards */
.insight { background: #ffffff; border: 1px solid #e6e8ef; border-left: 4px solid %(accent)s; border-radius: 12px;
    padding: 0.85rem 1rem; height: 100%%; }
.insight .num { font-size: 1.35rem; font-weight: 750; color: %(ink)s; }
.insight .txt { color: #334155; font-size: 0.88rem; line-height: 1.45; margin-top: 0.15rem; }

/* sidebar */
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e6e8ef; }
/* wider sidebar on desktop only; on phones Streamlit collapses it into a drawer */
@media (min-width: 992px) {
  section[data-testid="stSidebar"][aria-expanded="true"] { width: 310px !important; min-width: 310px !important; }
}
@media (max-width: 640px) {
  .block-container { padding-top: 3.6rem; padding-left: 1rem; padding-right: 1rem; }
  .hero h1 { font-size: 1.6rem; }
  [data-testid="stMetricValue"] { font-size: 1.3rem; }
}
section[data-testid="stSidebar"] h2 { font-size: 1.05rem; }
.sidebar-note { color: %(muted)s; font-size: 0.78rem; line-height: 1.45; }
</style>
""" % {"font": FONT, "ink": INK, "muted": MUTED, "accent": ACCENT}


def install_theme():
    st.markdown(CSS, unsafe_allow_html=True)
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT, color=INK, size=12.5),
        colorway=config.CHART_COLORS,
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor="#d7dbe3", ticks=""),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor="#d7dbe3", ticks=""),
        hoverlabel=dict(bgcolor="white", bordercolor="#d7dbe3", font=dict(family=FONT, color=INK)),
        legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11.5)),
        bargap=0.25,
    )
    pio.templates["bvi"] = template
    pio.templates.default = "plotly_white+bvi"
    # Streamlit can reset pio's default when it first draws a chart; Plotly Express reads its own default first.
    px.defaults.template = "plotly_white+bvi"


def hero(eyebrow, title, subtitle, pills=()):
    pill_html = "".join(f'<span class="pill{" grey" if i else ""}">{p}</span>' for i, p in enumerate(pills))
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p>'
        f'{f"<div class=pills>{pill_html}</div>" if pills else ""}</div>',
        unsafe_allow_html=True,
    )


def kpi_row(items):
    """items: (label, value, help) tuples rendered as cards."""
    for col, (label, value, help_text) in zip(st.columns(len(items)), items):
        col.metric(label, value, help=help_text)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def card(title):
    """Bordered white panel; the key adds a CSS class (st-key-card-...) used for styling."""
    return st.container(border=True, key="card-" + slug(title))


def chart_card(fig, title, subtitle=None, height=360):
    with card(title):
        st.markdown(f'<p class="card-title">{title}</p>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<p class="card-sub">{subtitle}</p>', unsafe_allow_html=True)
        fig.update_xaxes(dtick=1, selector=dict(type="log"))
        fig.update_yaxes(dtick=1, selector=dict(type="log"))
        # Explicit backgrounds: otherwise Streamlit's frontend fills unset ones with its theme greys.
        fig.update_layout(template="plotly_white+bvi", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", height=height, margin=dict(l=4, r=8, t=34, b=4), title=None, legend_title_text="",
                          uniformtext_minsize=10, uniformtext_mode="hide")
        fig.update_xaxes(tickangle=0, automargin=True)
        st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False}, key="chart-" + slug(title))


def insight_cards(items):
    """items: (headline number, sentence) pairs."""
    for col, (number, text) in zip(st.columns(len(items)), items):
        col.markdown(f'<div class="insight"><div class="num">{number}</div><div class="txt">{text}</div></div>',
                     unsafe_allow_html=True)


def inr(value):
    return "–" if value is None or value != value else f"₹{value:,.0f}"


def num(value, digits=2):
    return "–" if value is None or value != value else f"{value:,.{digits}f}"


def pct(value):
    return "–" if value is None or value != value else f"{value:.1f}%"
