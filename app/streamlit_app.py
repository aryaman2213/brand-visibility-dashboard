"""Brand Visibility Intelligence dashboard (entry point).

Run from the project root:
    streamlit run app/streamlit_app.py

This file sets up the theme, the sidebar filters (shared by every page) and the
page navigation. Pages live in views.py; all SQL lives in queries.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib

import streamlit as st

import config
import src.db

# Streamlit only hot-reloads modules inside app/. config.py and src/ live at the project root, so after
# a redeploy (Streamlit Cloud pulls new code without restarting) they could be stale; reload them each run.
importlib.reload(config)
importlib.reload(src.db)

import queries  # noqa: E402
import ui  # noqa: E402
import views  # noqa: E402
from queries import Filters  # noqa: E402

st.set_page_config(page_title="Brand Visibility Intelligence", page_icon=":material/insights:", layout="wide")
ui.install_theme()


@st.cache_data(show_spinner=False)
def options(column):
    return queries.distinct_values(column)


def sidebar_filters():
    with st.sidebar:
        st.markdown("## Filters")
        st.markdown('<p class="sidebar-note">Every filter is added to the SQL query behind each chart. '
                    'Leave a filter empty to include everything.</p>', unsafe_allow_html=True)
        sources = options("data_source")
        data_source = st.multiselect(
            "Data source", sources, default=sources, format_func=config.SOURCE_LABELS.get, key="f_source",
            help="The provided CSV is synthetic. Choose Google Shopping alone for real-market conclusions.")
        keyword = st.multiselect("Keyword", options("keyword"), key="f_keyword")
        brand = st.multiselect("Brand", options("brand"), key="f_brand")
        platform = st.multiselect("Platform", options("platform"), key="f_platform")
        price_range = st.multiselect(
            "Price range", [p for p in queries.price_band_order() if p in options("price_range")], key="f_price")
        rating_range = st.multiselect(
            "Rating range", [r for r in queries.rating_band_order() if r in options("rating_range")], key="f_rating")
        st.divider()
        st.markdown(f'<p class="sidebar-note">Google Shopping data via SerpApi (India, {config.SNAPSHOT_DATE}) '
                    'merged with the provided CSV and stored in SQLite.</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sidebar-note"><a href="{config.GITHUB_URL}" target="_blank">Source code</a> · '
                    f'<a href="{config.REPORT_URL}" target="_blank">Project report (PDF)</a></p>', unsafe_allow_html=True)
    return Filters(tuple(data_source), tuple(keyword), tuple(brand), tuple(platform),
                   tuple(price_range), tuple(rating_range))


if not config.DB_PATH.exists():
    st.error("Database not found. Run `python pipeline.py` from the project root first.")
    st.stop()

st.session_state["filters"] = sidebar_filters()

pages = [
    st.Page(views.overview, title="Overview", icon=":material/dashboard:", default=True),
    st.Page(views.brands, title="Brands", icon=":material/sell:", url_path="brands"),
    st.Page(views.pricing, title="Pricing", icon=":material/payments:", url_path="pricing"),
    st.Page(views.platforms, title="Platforms", icon=":material/storefront:", url_path="platforms"),
    st.Page(views.visibility, title="Visibility & ranking", icon=":material/trending_up:", url_path="visibility"),
    st.Page(views.explorer, title="Product explorer", icon=":material/search:", url_path="explorer"),
    st.Page(views.about, title="About", icon=":material/info:", url_path="about"),
]
page = st.navigation(pages, position="top")

if page.title != "About" and views.kpis(st.session_state["filters"])["products"] == 0:
    st.warning("No products match the current filters. Clear a filter in the sidebar.", icon=":material/filter_alt_off:")
    st.stop()
page.run()
