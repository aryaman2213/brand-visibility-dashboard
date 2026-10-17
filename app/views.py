"""One function per dashboard page. Each reads the sidebar Filters from session state
and renders KPIs and charts from SQL queries in queries.py."""
import plotly.express as px
import streamlit as st

import config
import queries
from queries import Filters
from ui import ACCENT, SOURCE_COLORS, card, chart_card, compact, hero, inr, insight_cards, kpi_row, num, pct

API = (queries.API_ONLY,)
API_NOTE = "Google Shopping only: the CSV has no real search positions or original prices."
MIN = config.MIN_LISTINGS_FOR_AVG
MIN_PLATFORM = config.MIN_PLATFORM_LISTINGS
TOP_N = config.TOP_N_CHART


# ---------------------------------------------------------------- cached data access
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


@st.cache_data(show_spinner=False)
def market_facts():
    return queries.market_facts()


def filters():
    return st.session_state.get("filters", Filters())


def best(frame, column, ascending=False, min_listings=MIN):
    """Top group by `column`. Ratings need enough *rated* listings, not just listings."""
    count_column = "rated_listings" if column == "avg_rating" else "listings"
    eligible = frame[frame[count_column] >= min_listings].dropna(subset=[column])
    if eligible.empty:
        return "–"
    return eligible.sort_values([column, "name"], ascending=[ascending, True]).iloc[0]["name"]


def short_title(row, words=2):
    """Brand plus the next few title words, short enough for a KPI card."""
    title = str(row["title"]).split()
    if row["brand"] != "Unbranded" and title and title[0].lower() == str(row["brand"]).lower():
        title = title[1:]
    name = " ".join(title[:words])
    return name if row["brand"] == "Unbranded" else f"{row['brand']} {name}"


def hbar(frame, x, y, hover=None, labels=None):
    # Largest bar on top; ties are broken alphabetically, matching the SQL ordering behind the KPI cards.
    ordered = frame.sort_values([x, y], ascending=[True, False])
    fig = px.bar(ordered, x=x, y=y, orientation="h", hover_data=hover,
                 labels=labels or {}, color_discrete_sequence=[ACCENT])
    fig.update_yaxes(title=None)
    return fig


def source_note(f):
    if f.data_source == ("csv",):
        st.warning("Only the provided CSV is selected. Charts marked **Google Shopping** stay empty, "
                   "because the CSV has no real search positions or original prices.", icon=":material/info:")
    elif "csv" in f.data_source or not f.data_source:
        st.info("The provided CSV is synthetic (random brands, row-order 'positions'). Ranking and discount "
                "charts use Google Shopping rows only; choose it alone under **Data source** for a pure real-market view.",
                icon=":material/info:")


# ---------------------------------------------------------------- pages
def overview():
    f = filters()
    k = kpis(f)
    hero("Executive overview", "How brands show up in search",
         "Product listings from Google Shopping search results (via SerpApi) merged with the provided dataset, "
         "cleaned and stored in SQLite. Use the filters in the sidebar; every number on every page is re-queried.",
         [f"{k['products']:,} products in view", f"{k['brands']} brands", f"{k['platforms']} platforms",
          f"Snapshot {config.SNAPSHOT_DATE}"])
    kpi_row([
        ("Total products", f"{k['products']:,}", None),
        ("Average price", inr(k["avg_price"]), None),
        ("Average rating", num(k["avg_rating"]), "Real ratings only; filled-in values are excluded"),
        ("Total reviews", compact(k["total_reviews"] or 0), f"{k['total_reviews'] or 0:,.0f} reviews (real counts only)"),
        ("Avg visibility score", num(k["avg_visibility"], 1), "100 / log2(position + 1): 100 at #1, 63 at #2, 29 at #10"),
    ])

    m = market_facts()
    st.markdown("#### What the real market says")
    insight_cards([
        (f"{m['pct_under_15k']:.0f}%", "of Google Shopping products cost under ₹15,000: the market is budget-led."),
        (f"{m['pct_discounted']:.0f}%", f"of real listings show a discount, averaging {m['avg_discount']:.0f}% off, "
                                        "but discounted products don't rank higher."),
        (f"{m['amazon_share']:.0f}% → {m['amazon_top10_rate']:.0f}%",
         "Amazon's share of listings vs. the share of its listings in the top 10. Having more listings isn't the same as ranking higher."),
        (f"{m['pct_no_reviews']:.0f}%", "of real products have no reviews yet; a handful hold most of the social proof."),
    ])
    st.write("")

    df = products(f)
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="price", color="source", nbins=60, barmode="overlay", histnorm="percent",
                           color_discrete_map=SOURCE_COLORS, labels={"price": "Price (₹)"}, opacity=0.8)
        fig.update_yaxes(title="% of products")
        chart_card(fig, "Price distribution", "Share of each source's products per price bucket")
    with right:
        kw = df.groupby(["keyword", "source"]).size().reset_index(name="products")
        fig = px.bar(kw, y="keyword", x="products", color="source", orientation="h",
                     color_discrete_map=SOURCE_COLORS, labels={"keyword": "", "products": "Products"})
        chart_card(fig, "Products per keyword", "Listings found for each search term")
    left, right = st.columns([1, 1])
    with left:
        plat = df["platform"].value_counts()
        top = plat.head(config.PIE_TOP_N)
        if len(plat) > config.PIE_TOP_N:
            top.loc["Other"] = plat.iloc[config.PIE_TOP_N:].sum()
        fig = px.pie(names=top.index, values=top.values, hole=0.55)
        fig.update_traces(textinfo="percent", textposition="inside", sort=False)
        chart_card(fig, "Platform share", f"Top {config.PIE_TOP_N} platforms by listings; the rest grouped as Other")
    with right:
        bands = df["price_range"].value_counts().reindex(queries.price_band_order()).fillna(0).reset_index()
        bands.columns = ["price_range", "products"]
        bands["price_range"] = bands["price_range"].str.replace(" (", "<br>(", regex=False)
        fig = px.bar(bands, x="price_range", y="products", labels={"price_range": "", "products": "Products"},
                     color_discrete_sequence=[ACCENT])
        chart_card(fig, "Products per price range", "Budget < ₹5k · Mid-range ₹5k–15k · Premium ₹15k–35k · Luxury ₹35k+")


def brands():
    f = filters()
    hero("Brand insights", "Who leads, who's rated, who's seen",
         "Brand is extracted from each product title. 'Best' rankings need at least "
         f"{MIN} listings so a single product can't top a chart.")
    source_note(f)
    stats = group_stats(f, "brand")
    named = stats[stats["name"] != "Unbranded"]
    ranked = group_stats(f, "brand", 1, API)
    ranked = ranked[ranked["name"] != "Unbranded"]
    kpi_row([
        ("Total brands", f"{len(named):,}", "Excluding 'Unbranded'"),
        ("Top brand (by listings)", named.iloc[0]["name"] if len(named) else "–", None),
        ("Highest-rated brand", best(named, "avg_rating"), f"Among brands with ≥ {MIN} rated listings"),
        ("Best visibility brand", best(ranked, "avg_visibility"), f"Among brands with ≥ {MIN} listings. {API_NOTE}"),
        ("Avg visibility score", num(kpis(f, API)["avg_visibility"], 1), API_NOTE),
    ])
    left, right = st.columns(2)
    with left:
        chart_card(hbar(named.head(TOP_N), "listings", "name", labels={"listings": "Listings"}),
                   "Brand vs product count", f"Top {TOP_N} brands by number of listings", height=430)
    with right:
        rated = named[named["rated_listings"] >= MIN].nlargest(TOP_N, "avg_rating")
        fig = hbar(rated, "avg_rating", "name", hover=["rated_listings"], labels={"avg_rating": "Avg rating"})
        fig.update_xaxes(range=[max(0, rated["avg_rating"].min() - 0.3) if len(rated) else 0, 5.05])
        chart_card(fig, "Brand vs average rating", f"Brands with ≥ {MIN} rated listings", height=430)
    left, right = st.columns(2)
    with left:
        t10 = ranked[ranked["top_10_listings"] > 0].nlargest(TOP_N, "top_10_listings")
        chart_card(hbar(t10, "top_10_listings", "name", hover=["listings"],
                        labels={"top_10_listings": "Listings in positions 1–10"}),
                   "Top brands in top-10 positions", "Google Shopping · listings ranked 1–10 for their keyword", height=430)
    with right:
        vis = ranked[ranked["listings"] >= MIN].nlargest(TOP_N, "avg_visibility")
        chart_card(hbar(vis, "avg_visibility", "name", hover=["listings"], labels={"avg_visibility": "Avg visibility"}),
                   "Visibility score by brand", f"Google Shopping · brands with ≥ {MIN} listings", height=430)


def pricing():
    f = filters()
    hero("Pricing analysis", "Where products are priced and discounted",
         "Discount = (original price − selling price) / original price. Only Google Shopping listings carry an "
         "original price, so discount figures use those rows.")
    source_note(f)
    k = kpis(f)
    df = products(f)
    hi, lo = df.loc[df["price"].idxmax()], df.loc[df["price"].idxmin()]
    kpi_row([
        ("Average price", inr(k["avg_price"]), None),
        ("Highest price", inr(k["max_price"]), f"{hi['title']} · {hi['platform']}"),
        ("Lowest price", inr(k["min_price"]), f"{lo['title']} · {lo['platform']}"),
        ("% discounted products", pct(kpis(f, API)["pct_discounted"]), API_NOTE),
    ])
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="price", color="price_range", nbins=50,
                           category_orders={"price_range": queries.price_band_order()},
                           labels={"price": "Price (₹)", "price_range": ""})
        fig.update_yaxes(title="Products")
        chart_card(fig, "Price distribution", "Coloured by price range")
    with right:
        fig = px.box(df, x="price", y="keyword", color="source", log_x=True, color_discrete_map=SOURCE_COLORS,
                     labels={"price": "Price (₹, log)", "keyword": ""}, points=False)
        chart_card(fig, "Price spread by keyword", "Median, quartiles and range per search term")
    left, right = st.columns(2)
    with left:
        fig = px.scatter(df, x="position", y="price", color="source", log_y=True, opacity=0.65,
                         color_discrete_map=SOURCE_COLORS, hover_name="title",
                         labels={"position": "Search position (1 = top)", "price": "Price (₹, log)"})
        chart_card(fig, "Price vs ranking", "Does a higher price change where a product ranks?")
    with right:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="rating", y="price", color="source", log_y=True, opacity=0.65,
                         color_discrete_map=SOURCE_COLORS, hover_name="title",
                         labels={"price": "Price (₹, log)", "rating": "Rating"})
        chart_card(fig, "Price vs rating", "Rated products only")
    left, right = st.columns(2)
    for col, by in ((left, "brand"), (right, "platform")):
        with col:
            minimum = MIN if by == "brand" else MIN_PLATFORM
            g = group_stats(f, by, minimum, API)
            g = g[(g["avg_discount"] > 0) & (g["name"] != "Unbranded")].nlargest(TOP_N, "avg_discount")
            chart_card(hbar(g, "avg_discount", "name", hover=["listings", "pct_discounted"],
                            labels={"avg_discount": "Avg discount %"}),
                       f"Discount % by {by}", f"Google Shopping · {by}s with ≥ {minimum} listings", height=420)


def platforms():
    f = filters()
    hero("Platform comparison", "Marketplaces, specialists and brand stores",
         "Raw average prices mix categories (a shoe-only store looks cheap), so read price charts alongside the keyword filter.")
    source_note(f)
    stats = group_stats(f, "platform")
    kpi_row([
        ("Total platforms", f"{len(stats):,}", None),
        ("Best platform (avg rating)", best(stats, "avg_rating", min_listings=MIN_PLATFORM),
         f"Among platforms with ≥ {MIN_PLATFORM} rated listings"),
        ("Cheapest platform (avg price)", best(stats, "avg_price", ascending=True, min_listings=MIN_PLATFORM),
         f"Among platforms with ≥ {MIN_PLATFORM} listings"),
        ("Most products", stats.iloc[0]["name"] if len(stats) else "–", None),
    ])
    top = stats.head(TOP_N)
    left, right = st.columns(2)
    with left:
        chart_card(hbar(top, "listings", "name", labels={"listings": "Listings"}),
                   "Platform vs product count", f"Top {TOP_N} platforms", height=420)
    with right:
        chart_card(hbar(top, "avg_price", "name", labels={"avg_price": "Avg price (₹)"}),
                   "Platform vs average price", f"Top {TOP_N} platforms by listings", height=420)
    left, right = st.columns(2)
    with left:
        r = stats[stats["rated_listings"] >= MIN].head(TOP_N)
        fig = hbar(r, "avg_rating", "name", hover=["rated_listings"], labels={"avg_rating": "Avg rating"})
        fig.update_xaxes(range=[max(0, r["avg_rating"].min() - 0.3) if len(r) else 0, 5.05])
        chart_card(fig, "Platform vs average rating", f"Platforms with ≥ {MIN} rated listings")
    with right:
        pos = group_stats(f, "platform", MIN_PLATFORM, API).head(TOP_N)
        fig = px.bar(pos.sort_values("avg_position", ascending=False), x="avg_position", y="name", orientation="h",
                     hover_data=["listings"], labels={"avg_position": "Avg search position"},
                     color_discrete_sequence=[ACCENT])
        fig.update_yaxes(title=None)
        chart_card(fig, "Platform vs average ranking", f"Google Shopping · shorter bar = ranks higher · ≥ {MIN_PLATFORM} listings")
    top_brands = [b for b in group_stats(f, "brand")["name"] if b != "Unbranded"][:config.MATRIX_TOP_N]
    matrix = queries.brand_platform_matrix(f, top_brands, top["name"].head(config.MATRIX_TOP_N).tolist())
    fig = px.bar(matrix, x="listings", y="platform", color="brand", orientation="h",
                 labels={"platform": "", "listings": "Listings", "brand": "Brand"})
    chart_card(fig, "Brand distribution per platform",
               f"Top {config.MATRIX_TOP_N} brands across the top {config.MATRIX_TOP_N} platforms", height=420)


def visibility():
    f = filters()
    hero("Visibility & ranking", "What gets a product to the top",
         "Position is the product's rank in Google Shopping results for its keyword (40 per keyword). "
         "Visibility score = 100 / log₂(position + 1), so the top spots count most.")
    source_note(f)
    k, k_api = kpis(f), kpis(f, API)
    df = products(f)
    ranked = df[df["data_source"] == "api"]
    first = ranked[ranked["position"] == 1].sort_values(["rating_imputed", "rating"], ascending=[True, False])
    pick = first.iloc[0] if len(first) else None
    kpi_row([
        ("Average rating", num(k["avg_rating"]), "Real ratings only"),
        ("Avg visibility score", num(k_api["avg_visibility"], 1), API_NOTE),
        ("Products in top 10", pct(k_api["pct_top_10"]), "Share of products in positions 1–10. " + API_NOTE),
        ("Best-ranked product (#1)", short_title(pick) if pick is not None else "–",
         f"{pick['title']} · {pick['platform']} · {inr(pick['price'])}. Highest-rated of the #1 results."
         if pick is not None else API_NOTE),
    ])
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="position", color="source", nbins=40, color_discrete_map=SOURCE_COLORS,
                           labels={"position": "Search position"})
        fig.update_yaxes(title="Products")
        chart_card(fig, "Ranking distribution", "How listings spread across search positions")
    with right:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="position", y="rating", color="source", opacity=0.65, hover_name="title",
                         color_discrete_map=SOURCE_COLORS, labels={"position": "Search position (1 = top)", "rating": "Rating"})
        chart_card(fig, "Rating vs ranking", "Rated products only. In the analysis, the correlation is ≈ 0")
    left, right = st.columns(2)
    with left:
        fig = px.scatter(df.assign(bubble=df["rating"].clip(lower=1)), x="position", y="reviews", size="bubble",
                         color="source", opacity=0.55, hover_name="title", color_discrete_map=SOURCE_COLORS, size_max=15,
                         labels={"position": "Search position (1 = top)", "reviews": "Reviews"})
        chart_card(fig, "Reviews vs ranking", "Bubble size = rating")
    with right:
        g = group_stats(f, "brand", MIN, API)
        g = g[g["name"] != "Unbranded"].nlargest(TOP_N, "avg_visibility")
        chart_card(hbar(g, "avg_visibility", "name", hover=["listings"], labels={"avg_visibility": "Avg visibility"}),
                   "Visibility score by brand", f"Google Shopping · brands with ≥ {MIN} listings")
    with card("Highest-visibility products"):
        st.markdown('<p class="card-title">Highest-visibility products</p><p class="card-sub">Google Shopping · top 10 by visibility score</p>',
                    unsafe_allow_html=True)
        st.dataframe(
            (ranked if len(ranked) else df).nlargest(10, "visibility_score")[
                ["title", "brand", "platform", "keyword", "position", "price", "rating"]],
            hide_index=True, width="stretch",
            column_config={"title": st.column_config.TextColumn("Title", width="medium"),
                           "brand": "Brand", "platform": "Platform", "keyword": "Keyword", "position": "Position",
                           "price": st.column_config.NumberColumn("Price", format="₹%d"),
                           "rating": st.column_config.NumberColumn("Rating", format="%.1f")},
        )


def explorer():
    f = filters()
    hero("Product explorer", "Search, sort and export",
         "Type to search titles (a SQL LIKE query), click a column header to sort, and download what you see.")
    search = st.text_input("Search product titles", placeholder="e.g. 28 L convection, 20000 mAh, Pegasus",
                           label_visibility="collapsed")
    fs = Filters(**{**f.__dict__, "search": search})
    k = kpis(fs)
    kpi_row([
        ("Total products (filtered)", f"{k['products']:,}", None),
        ("Avg price (filtered)", inr(k["avg_price"]), None),
        ("Avg rating (filtered)", num(k["avg_rating"]), "Real ratings only"),
    ])
    df = products(fs)
    if df.empty:
        st.warning("No products match this search and the current filters.", icon=":material/search_off:")
        return
    table = df[["title", "brand", "price", "rating", "reviews", "platform", "discount_pct",
                "position", "visibility_score", "is_top_10", "keyword", "source"]].copy()
    table["is_top_10"] = table["is_top_10"].astype(bool)
    left, right = st.columns([3, 1])
    with right:
        only_top = st.toggle("Top performers only", help="Products in search positions 1–10")
    with left:
        st.caption("Highlighted rows are top performers (search positions 1–10). Click a header to sort.")
    if only_top:
        table = table[table["is_top_10"]]
    styled = table.style.apply(
        lambda row: ["background-color: rgba(79,70,229,0.08)" if row["is_top_10"] else ""] * len(row), axis=1)
    st.dataframe(
        styled, hide_index=True, width="stretch", height=480,
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
    st.download_button("Download these products (CSV)", df.to_csv(index=False).encode(), "filtered_products.csv",
                       "text/csv", icon=":material/download:")
    left, right = st.columns(2)
    with left:
        rated = df[df["rating_imputed"] == 0]
        fig = px.scatter(rated, x="price", y="rating", color="source", log_x=True, opacity=0.65, hover_name="title",
                         color_discrete_map=SOURCE_COLORS, labels={"price": "Price (₹, log)", "rating": "Rating"})
        chart_card(fig, "Rating vs price", "Rated products in the current selection")
    with right:
        fig = px.scatter(df.assign(bubble=df["rating"].clip(lower=1)), x="position", y="reviews", size="bubble",
                         color="source", opacity=0.55, hover_name="title", color_discrete_map=SOURCE_COLORS, size_max=15,
                         labels={"position": "Search position", "reviews": "Reviews"})
        chart_card(fig, "Reviews vs ranking", "Bubble size = rating")


def about():
    hero("About", "Data, method and caveats",
         "How the numbers on this dashboard were produced. Full detail is in the project report and the EDA notebook.")
    facts = queries.dataset_facts()
    m = market_facts()
    left, right = st.columns(2)
    with left:
        with card("Data sources"):
            st.markdown("##### Data sources")
            st.markdown(
                f"- **Google Shopping via SerpApi**: 5 keywords × 40 ranked results, India locale (`gl=in`), "
                f"taken on {config.SNAPSHOT_DATE}: {facts['api_raw']} results, {facts['api_products']} after removing duplicates.\n"
                f"- **Provided CSV** (`brand_dirty_dataset.csv`): {facts['csv_raw']:,} rows with planted errors; "
                f"{facts['csv_products']:,} after cleaning.\n"
                f"- **Merged:** {facts['products']:,} products, {facts['brands']} brands, {facts['platforms']} platforms, "
                f"{facts['keywords']} keywords, stored in SQLite (`products`, `raw_products`, `cleaning_log`)."
            )
        with card("Pipeline"):
            st.markdown("##### Pipeline")
            st.markdown(
                "Extract (SerpApi JSON, cached) → load CSV → merge with `concat` → clean (8 logged steps) → "
                "features (brand, visibility score, price/rating/review bands, discount) → SQLite → this dashboard.\n\n"
                "Each sidebar filter is added to a parameterised SQL `WHERE` clause, so every chart is a live query."
            )
            st.markdown(f"[Source code on GitHub]({config.GITHUB_URL}) · [Project report (PDF)]({config.REPORT_URL})")
    with right:
        with card("Read the numbers with these in mind"):
            st.markdown("##### Read the numbers with these in mind")
            st.markdown(
                "- **The provided CSV is synthetic.** Every one of its 9 brands sells every product (Dell air fryers, "
                "Nike microwaves), and it has no search positions. Its 'position' is row order.\n"
                "- **Ranking and discount metrics use Google Shopping rows only**, for that reason.\n"
                f"- **Ratings:** averages use real ratings only. {m['pct_unrated']:.0f}% of Google Shopping products have "
                "no rating; they are kept, with the gap filled for completeness and flagged.\n"
                "- **One snapshot**, one page of results per keyword, India only. Brand-level rankings in the real data rest "
                "on 3–7 listings each, so treat them as directional."
            )
        with card("Definitions"):
            st.markdown("##### Definitions")
            st.markdown(
                "- **Visibility score** = 100 / log₂(position + 1): 100 at #1, 63 at #2, 29 at #10.\n"
                "- **Top 10** = search position 1–10 for the product's keyword.\n"
                "- **Discount %** = (original − selling price) / original price × 100.\n"
                "- **Price bands:** Budget < ₹5k · Mid-range ₹5k–15k · Premium ₹15k–35k · Luxury ₹35k+."
            )
