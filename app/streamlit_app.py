"""Brand Visibility Intelligence dashboard.

Run from the project root:
    streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import plotly.express as px
import streamlit as st

import config
import queries
from queries import Filters

st.set_page_config(page_title="Brand Visibility Intelligence", page_icon="📊", layout="wide")

PLOT_TEMPLATE = "plotly_white"
SOURCE_COLORS = {config.SOURCE_LABELS[k]: v for k, v in config.SOURCE_COLORS.items()}
ACCENT = config.SOURCE_COLORS["api"]


# ---------------------------------------------------------------- data access (cached)
@st.cache_data(show_spinner=False)
def options(column):
    return queries.distinct_values(column)


@st.cache_data(show_spinner=False)
def kpis(f, extra=()):
    return queries.kpis(f, extra)


@st.cache_data(show_spinner=False)
def products(f):
    df = queries.products(f)
    df["source"] = df["data_source"].map(config.SOURCE_LABELS)
    return df


@st.cache_data(show_spinner=False)
def group_stats(f, by, min_listings=1, extra=()):
    return queries.group_stats(f, by, min_listings, extra)


# ---------------------------------------------------------------- formatting helpers
def inr(value):
    return "–" if value is None or value != value else f"₹{value:,.0f}"


def num(value, digits=2):
    return "–" if value is None or value != value else f"{value:,.{digits}f}"


def pct(value):
    return "–" if value is None or value != value else f"{value:.1f}%"


def chart(fig, height=380):
    fig.update_xaxes(dtick=1, selector=dict(type="log"))
    fig.update_yaxes(dtick=1, selector=dict(type="log"))
    fig.update_layout(template=PLOT_TEMPLATE, height=height, margin=dict(l=10, r=10, t=80, b=10),
                      legend=dict(title_text="", orientation="h", yanchor="bottom", y=1.0, x=0))
    st.plotly_chart(fig, use_container_width=True)


def kpi_row(items):
    for col, (label, value, help_text) in zip(st.columns(len(items)), items):
        col.metric(label, value, help=help_text)


def best(frame, column, ascending=False, min_listings=config.MIN_LISTINGS_FOR_AVG):
    """Top group by `column`. Ratings need enough *rated* listings, not just listings."""
    count_column = "rated_listings" if column == "avg_rating" else "listings"
    eligible = frame[frame[count_column] >= min_listings].dropna(subset=[column])
    if eligible.empty:
        return "–"
    return eligible.sort_values(column, ascending=ascending).iloc[0]["name"]


def short_title(row, words=2):
    """Brand plus the next few title words, short enough for a KPI card."""
    title = str(row["title"]).split()
    if row["brand"] != "Unbranded" and title and title[0].lower() == str(row["brand"]).lower():
        title = title[1:]
    name = " ".join(title[:words])
    return name if row["brand"] == "Unbranded" else f"{row['brand']} {name}"


def empty_state():
    st.warning("No products match the current filters. Clear a filter in the sidebar.")


# ---------------------------------------------------------------- sidebar
def sidebar_filters():
    st.sidebar.header("Filters")
    st.sidebar.caption("Each filter changes the SQL query behind every chart. Leave one empty to include everything.")
    source_options = options("data_source")
    data_source = st.sidebar.multiselect(
        "Data source", source_options, default=source_options,
        format_func=config.SOURCE_LABELS.get,
        help="The provided CSV is synthetic: its brands are random and its 'positions' are row order. "
             "Choose Google Shopping only for real-market conclusions.",
    )
    keyword = st.sidebar.multiselect("Keyword", options("keyword"))
    brand = st.sidebar.multiselect("Brand", options("brand"))
    platform = st.sidebar.multiselect("Platform", options("platform"))
    price_range = st.sidebar.multiselect(
        "Price range", [p for p in queries.price_band_order() if p in options("price_range")])
    rating_range = st.sidebar.multiselect(
        "Rating range", [r for r in queries.rating_band_order() if r in options("rating_range")])
    st.sidebar.divider()
    st.sidebar.caption(
        "Data: SerpApi Google Shopping (India, 17 Oct 2026) + the provided CSV, stored in SQLite. "
        "Ratings shown are real ratings only; filled-in values are excluded from averages."
    )
    return Filters(tuple(data_source), tuple(keyword), tuple(brand), tuple(platform),
                   tuple(price_range), tuple(rating_range))


# ---------------------------------------------------------------- tabs
def tab_overview(f):
    k = kpis(f)
    kpi_row([
        ("Total products", f"{k['products']:,}", None),
        ("Avg price", inr(k["avg_price"]), None),
        ("Avg rating", num(k["avg_rating"]), "Real ratings only (filled-in values excluded)"),
        ("Total reviews", f"{k['total_reviews'] or 0:,.0f}", None),
        ("Avg visibility score", num(k["avg_visibility"], 1), "100 / log2(position + 1): 100 at #1, 29 at #10"),
    ])
    df = products(f)
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="price", color="source", nbins=60, barmode="overlay", histnorm="percent",
                           color_discrete_map=SOURCE_COLORS, title="Price distribution (% of each source)",
                           labels={"price": "Price (₹)"})
        fig.update_yaxes(title="% of products")
        fig.update_traces(opacity=0.75)
        chart(fig)
    with right:
        kw = df.groupby(["keyword", "source"]).size().reset_index(name="products")
        fig = px.bar(kw, y="keyword", x="products", color="source", orientation="h",
                     color_discrete_map=SOURCE_COLORS, title="Products per keyword",
                     labels={"keyword": ""})
        chart(fig)
    plat = df["platform"].value_counts()
    top = plat.head(8)
    if len(plat) > 8:
        top.loc["Other"] = plat.iloc[8:].sum()
    fig = px.pie(names=top.index, values=top.values, hole=0.45, title="Platform share of listings")
    fig.update_traces(textinfo="percent+label")
    chart(fig, height=420)


API = (queries.API_ONLY,)
API_NOTE = "Google Shopping only: the CSV has no real search positions."


def tab_brands(f):
    stats = group_stats(f, "brand")
    named = stats[stats["name"] != "Unbranded"]
    ranked = group_stats(f, "brand", 1, API)
    ranked = ranked[ranked["name"] != "Unbranded"]
    kpi_row([
        ("Total brands", f"{len(named):,}", "Excluding 'Unbranded'"),
        ("Top brand (by listings)", named.iloc[0]["name"] if len(named) else "–", None),
        ("Highest rated brand", best(named, "avg_rating"),
         f"Among brands with ≥ {config.MIN_LISTINGS_FOR_AVG} rated listings"),
        ("Best visibility brand", best(ranked, "avg_visibility"),
         f"Among brands with ≥ {config.MIN_LISTINGS_FOR_AVG} listings. {API_NOTE}"),
        ("Avg visibility score", num(kpis(f, API)["avg_visibility"], 1), API_NOTE),
    ])
    top = named.head(config.TOP_N_CHART)
    left, right = st.columns(2)
    with left:
        fig = px.bar(top.sort_values("listings"), x="listings", y="name", orientation="h",
                     title=f"Listings per brand (top {config.TOP_N_CHART})", labels={"name": ""},
                     color_discrete_sequence=[ACCENT])
        chart(fig, 460)
    with right:
        rated = named[named["rated_listings"] >= config.MIN_LISTINGS_FOR_AVG].nlargest(config.TOP_N_CHART, "avg_rating")
        fig = px.bar(rated.sort_values("avg_rating"), x="avg_rating", y="name", orientation="h",
                     title=f"Average rating by brand (≥ {config.MIN_LISTINGS_FOR_AVG} rated listings)",
                     labels={"name": "", "avg_rating": "Avg rating"}, color_discrete_sequence=[ACCENT],
                     hover_data=["rated_listings"])
        fig.update_xaxes(range=[max(0, rated["avg_rating"].min() - 0.3) if len(rated) else 0, 5.05])
        chart(fig, 460)
    left, right = st.columns(2)
    with left:
        t10 = ranked[ranked["top_10_listings"] > 0].nlargest(config.TOP_N_CHART, "top_10_listings")
        fig = px.bar(t10.sort_values("top_10_listings"), x="top_10_listings", y="name", orientation="h",
                     title="Brands with the most top-10 search positions (Google Shopping)", hover_data=["listings"],
                     labels={"name": "", "top_10_listings": "Listings in positions 1–10"},
                     color_discrete_sequence=[ACCENT])
        chart(fig, 460)
    with right:
        vis = ranked[ranked["listings"] >= config.MIN_LISTINGS_FOR_AVG].nlargest(config.TOP_N_CHART, "avg_visibility")
        fig = px.bar(vis.sort_values("avg_visibility"), x="avg_visibility", y="name", orientation="h",
                     title=f"Average visibility score by brand (Google Shopping, ≥ {config.MIN_LISTINGS_FOR_AVG} listings)",
                     labels={"name": "", "avg_visibility": "Avg visibility"}, color_discrete_sequence=[ACCENT])
        chart(fig, 460)


def tab_pricing(f):
    k = kpis(f)
    df = products(f)
    hi = df.loc[df["price"].idxmax()]
    lo = df.loc[df["price"].idxmin()]
    kpi_row([
        ("Avg price", inr(k["avg_price"]), None),
        ("Max price", inr(k["max_price"]), hi["title"]),
        ("Min price", inr(k["min_price"]), lo["title"]),
        ("% discounted products", pct(kpis(f, (queries.API_ONLY,))["pct_discounted"]),
         "Google Shopping listings showing an original price above the selling price. "
         "The CSV has no original prices, so it is left out of every discount figure."),
    ])
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="price", color="price_range", nbins=50, title="Price distribution",
                           category_orders={"price_range": queries.price_band_order()},
                           labels={"price": "Price (₹)", "price_range": "Price range"})
        chart(fig)
    with right:
        bands = df["price_range"].value_counts().reindex(queries.price_band_order()).fillna(0).reset_index()
        bands.columns = ["price_range", "products"]
        fig = px.bar(bands, x="price_range", y="products", title="Products per price range",
                     labels={"price_range": ""}, color_discrete_sequence=[ACCENT])
        chart(fig)
    left, right = st.columns(2)
    with left:
        fig = px.scatter(df, x="position", y="price", color="source", log_y=True, opacity=0.6,
                         color_discrete_map=SOURCE_COLORS, hover_name="title",
                         title="Price vs ranking", labels={"position": "Search position (1 = top)", "price": "Price (₹, log)"})
        chart(fig)
    with right:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="rating", y="price", color="source", log_y=True, opacity=0.6,
                         color_discrete_map=SOURCE_COLORS, hover_name="title",
                         title="Price vs rating (rated products)", labels={"price": "Price (₹, log)"})
        chart(fig)
    left, right = st.columns(2)
    for col, by in ((left, "brand"), (right, "platform")):
        with col:
            g = group_stats(f, by, config.MIN_LISTINGS_FOR_AVG, (queries.API_ONLY,))
            g = g[(g["avg_discount"] > 0) & (g["name"] != "Unbranded")].nlargest(config.TOP_N_CHART, "avg_discount")
            fig = px.bar(g.sort_values("avg_discount"), x="avg_discount", y="name", orientation="h",
                         title=f"Average discount % by {by} (Google Shopping, ≥ {config.MIN_LISTINGS_FOR_AVG} listings)", hover_data=["listings", "pct_discounted"],
                         labels={"name": "", "avg_discount": "Avg discount %"}, color_discrete_sequence=[ACCENT])
            chart(fig, 420)


def tab_platforms(f):
    stats = group_stats(f, "platform")
    kpi_row([
        ("Total platforms", f"{len(stats):,}", None),
        ("Best platform (avg rating)", best(stats, "avg_rating", min_listings=5), "Among platforms with ≥ 5 rated listings"),
        ("Cheapest platform (avg price)", best(stats, "avg_price", ascending=True, min_listings=5),
         "Among platforms with ≥ 5 listings. Raw averages mix categories: a shoe-only store looks cheap."),
        ("Most products", stats.iloc[0]["name"] if len(stats) else "–", None),
    ])
    top = stats.head(config.TOP_N_CHART)
    left, right = st.columns(2)
    with left:
        fig = px.bar(top.sort_values("listings"), x="listings", y="name", orientation="h",
                     title="Listings per platform", labels={"name": ""}, color_discrete_sequence=[ACCENT])
        chart(fig, 440)
    with right:
        fig = px.bar(top.sort_values("avg_price"), x="avg_price", y="name", orientation="h",
                     title="Average price per platform", labels={"name": "", "avg_price": "Avg price (₹)"},
                     color_discrete_sequence=[ACCENT])
        chart(fig, 440)
    left, right = st.columns(2)
    with left:
        r = stats[stats["rated_listings"] >= config.MIN_LISTINGS_FOR_AVG].head(config.TOP_N_CHART)
        fig = px.bar(r.sort_values("avg_rating", ascending=False), x="name", y="avg_rating",
                     title=f"Average rating per platform (≥ {config.MIN_LISTINGS_FOR_AVG} rated listings)",
                     hover_data=["rated_listings"], labels={"name": "", "avg_rating": "Avg rating"},
                     color_discrete_sequence=[ACCENT])
        fig.update_yaxes(range=[max(0, r["avg_rating"].min() - 0.3) if len(r) else 0, 5.05])
        chart(fig)
    with right:
        pos = group_stats(f, "platform", config.MIN_LISTINGS_FOR_AVG, API).head(config.TOP_N_CHART)
        fig = px.bar(pos.sort_values("avg_position"), x="name", y="avg_position", hover_data=["listings"],
                     title="Average search position per platform (Google Shopping, lower = better)",
                     labels={"name": "", "avg_position": "Avg position"}, color_discrete_sequence=[ACCENT])
        chart(fig)
    brands = [b for b in group_stats(f, "brand")["name"] if b != "Unbranded"][:10]
    matrix = queries.brand_platform_matrix(f, brands, top["name"].head(10).tolist())
    fig = px.bar(matrix, x="listings", y="platform", color="brand", orientation="h",
                 title="Brand distribution per platform (top 10 brands × top 10 platforms)", labels={"platform": ""})
    chart(fig, 460)


def tab_visibility(f):
    if f.data_source == ("csv",):
        st.warning("Only the provided CSV is selected. Ranking charts marked *Google Shopping* will be empty, "
                   "because the CSV has no real search positions.")
    elif not f.data_source or "csv" in f.data_source:
        st.info("The provided CSV has no real search positions (its 'position' is row order), so ranking "
                "patterns are only meaningful for Google Shopping data. Pick it alone under **Data source**.")
    k, k_api = kpis(f), kpis(f, API)
    df = products(f)
    ranked = df[df["data_source"] == "api"]
    best_ranked = ranked[ranked["position"] == 1].sort_values(["rating_imputed", "rating"], ascending=[True, False])
    top_pick = best_ranked.iloc[0] if len(best_ranked) else None
    kpi_row([
        ("Avg rating", num(k["avg_rating"]), "Real ratings only"),
        ("Avg visibility score", num(k_api["avg_visibility"], 1), API_NOTE),
        ("Products in top 10", pct(k_api["pct_top_10"]), "Share of products in search positions 1–10. " + API_NOTE),
        ("Best-ranked product (#1)", short_title(top_pick) if top_pick is not None else "–",
         f"{top_pick['title']} · {top_pick['platform']} · {inr(top_pick['price'])}. Highest-rated of the #1 results."
         if top_pick is not None else API_NOTE),
    ])
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="position", color="source", nbins=40, color_discrete_map=SOURCE_COLORS,
                           title="Ranking distribution", labels={"position": "Search position"})
        chart(fig)
    with right:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="position", y="rating", color="source", opacity=0.6, hover_name="title",
                         color_discrete_map=SOURCE_COLORS, title="Rating vs ranking",
                         labels={"position": "Search position (1 = top)"})
        chart(fig)
    left, right = st.columns(2)
    with left:
        bubbles = df.assign(bubble=df["rating"].clip(lower=1))
        fig = px.scatter(bubbles, x="position", y="reviews", size="bubble", color="source", opacity=0.55,
                         hover_name="title", color_discrete_map=SOURCE_COLORS, size_max=16,
                         title="Reviews vs ranking (bubble = rating)",
                         labels={"position": "Search position (1 = top)", "reviews": "Reviews"})
        chart(fig)
    with right:
        g = group_stats(f, "brand", config.MIN_LISTINGS_FOR_AVG, API)
        g = g[g["name"] != "Unbranded"].nlargest(config.TOP_N_CHART, "avg_visibility")
        fig = px.bar(g.sort_values("avg_visibility"), x="avg_visibility", y="name", orientation="h",
                     title="Visibility score by brand (Google Shopping)", labels={"name": "", "avg_visibility": "Avg visibility"},
                     color_discrete_sequence=[ACCENT])
        chart(fig)
    st.subheader("Highest-visibility products (Google Shopping)")
    st.dataframe(
        (ranked if len(ranked) else df).nlargest(10, "visibility_score")[["title", "brand", "platform", "keyword", "position", "price", "rating"]],
        hide_index=True, use_container_width=True,
        column_config={"price": st.column_config.NumberColumn("Price", format="₹%d")},
    )


def tab_explorer(f):
    search = st.text_input("Search product titles", placeholder="e.g. 28 L convection, 20000 mAh, Pegasus")
    fs = Filters(**{**f.__dict__, "search": search})
    k = kpis(fs)
    kpi_row([
        ("Total products (filtered)", f"{k['products']:,}", None),
        ("Avg price (filtered)", inr(k["avg_price"]), None),
        ("Avg rating (filtered)", num(k["avg_rating"]), "Real ratings only"),
    ])
    df = products(fs)
    if df.empty:
        empty_state()
        return
    table = df[["title", "brand", "price", "rating", "reviews", "platform", "discount_pct",
                "position", "visibility_score", "is_top_10", "keyword", "source"]].copy()
    table["is_top_10"] = table["is_top_10"].astype(bool)
    only_top = st.toggle("Show only top performers (search positions 1–10)")
    if only_top:
        table = table[table["is_top_10"]]
    styled = table.style.apply(
        lambda row: ["background-color: rgba(42,111,219,0.10)" if row["is_top_10"] else ""] * len(row), axis=1)
    st.caption("Click a column header to sort. Highlighted rows are in the top 10 search positions.")
    st.dataframe(
        styled, hide_index=True, use_container_width=True, height=520,
        column_config={
            "title": st.column_config.TextColumn("Title", width="large"),
            "brand": "Brand",
            "price": st.column_config.NumberColumn("Price", format="₹%d"),
            "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
            "reviews": "Reviews",
            "platform": "Platform",
            "discount_pct": st.column_config.NumberColumn("Discount", format="%.0f%%"),
            "position": "Position",
            "visibility_score": st.column_config.ProgressColumn("Visibility", min_value=0, max_value=100, format="%.0f"),
            "is_top_10": st.column_config.CheckboxColumn("Top 10"),
            "keyword": "Keyword",
            "source": "Source",
        },
    )
    left, right = st.columns(2)
    with left:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="price", y="rating", color="source", log_x=True, opacity=0.6, hover_name="title",
                         color_discrete_map=SOURCE_COLORS, title="Rating vs price", labels={"price": "Price (₹, log)"})
        chart(fig)
    with right:
        fig = px.scatter(df, x="position", y="reviews", size=df["rating"].clip(lower=1), color="source",
                         opacity=0.55, hover_name="title", color_discrete_map=SOURCE_COLORS, size_max=16,
                         title="Reviews vs ranking (bubble = rating)", labels={"position": "Search position"})
        chart(fig)
    st.download_button("Download filtered products (CSV)", df.to_csv(index=False).encode(),
                       "filtered_products.csv", "text/csv")


# ---------------------------------------------------------------- main
def main():
    st.title("Brand Visibility Intelligence")
    st.caption("How brands rank, price and discount in Google Shopping search results across five product keywords.")
    if not config.DB_PATH.exists():
        st.error("Database not found. Run `python pipeline.py` from the project root first.")
        st.stop()
    f = sidebar_filters()
    if kpis(f)["products"] == 0:
        empty_state()
        st.stop()
    tabs = st.tabs(["Overview", "Brand insights", "Pricing", "Platforms", "Visibility & ranking", "Product explorer"])
    for tab, render in zip(tabs, [tab_overview, tab_brands, tab_pricing, tab_platforms, tab_visibility, tab_explorer]):
        with tab:
            render(f)


main()
