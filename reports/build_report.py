"""Build the project report (HTML -> PDF).

Numbers and tables are read from the SQLite database and the written answers from
notebooks/eda.ipynb, so the report always matches the analysis. The PDF is printed
with headless Chrome through Playwright (pip install playwright).

    python reports/build_report.py          # links default to config.GITHUB_URL / config.LIVE_URL
"""
import argparse
import html
import re
import sys
from pathlib import Path

import markdown
import nbformat
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src import db  # noqa: E402

REPORTS = ROOT / "reports"
BUILD = REPORTS / "_build"
PDF_PATH = REPORTS / "Brand_Visibility_Intelligence_Report.pdf"
AUTHOR = "Aryaman Bhatnagar"


# ---------------------------------------------------------------- inputs
def notebook_answers():
    """{question id: (question, answer html)} plus the key-insights html, from the executed notebook."""
    nb = nbformat.read(ROOT / "notebooks" / "eda.ipynb", as_version=4)
    answers, current, insights = {}, None, ""
    for cell in nb.cells:
        if cell.cell_type != "markdown":
            continue
        heading = re.match(r"### (\w+)\. (.+)", cell.source)
        if heading:
            current = heading.groups()
        elif cell.source.startswith("**Answer:**") and current:
            body = cell.source.removeprefix("**Answer:**").strip()
            answers[current[0]] = (current[1], md(body))
            current = None
        elif "## Key insights" in cell.source:
            insights = md(cell.source.split("## Key insights", 1)[1])
    return answers, insights


def md(text):
    # Python-Markdown needs a blank line before a list; Jupyter doesn't, so the notebook text may lack one.
    text = re.sub(r"([^\n])\n(?=(\d+\.|-) )", r"\1\n\n", text)
    return markdown.markdown(text, extensions=["tables"])


def table(frame, formats=None, classes=""):
    formats = formats or {}
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in frame.columns)
    rows = []
    for _, row in frame.iterrows():
        cells = []
        for col, value in row.items():
            text = formats[col](value) if col in formats else value
            cells.append(f"<td>{html.escape(str(text))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def image(path, caption, width="100%"):
    return (f'<figure><img src="{path.as_uri()}" style="width:{width}"/>'
            f'<figcaption>{caption}</figcaption></figure>')


def shrink_screenshots():
    """Report-sized JPEG copies of the dashboard screenshots."""
    BUILD.mkdir(exist_ok=True)
    out = {}
    for png in sorted((REPORTS / "screenshots").glob("*.png")):
        im = Image.open(png).convert("RGB")
        im.thumbnail((1700, 6000))
        target = BUILD / (png.stem + ".jpg")
        im.save(target, quality=86, optimize=True)
        out[png.stem] = target
    return out


def fig(name):
    return REPORTS / "figures" / f"{name}.png"


# ---------------------------------------------------------------- facts from the database
def facts():
    q = db.query
    f = {}
    f["by_source"] = q("SELECT data_source, COUNT(*) n FROM products GROUP BY 1").set_index("data_source")["n"].to_dict()
    f["raw_by_source"] = q("SELECT data_source, COUNT(*) n FROM raw_products GROUP BY 1").set_index("data_source")["n"].to_dict()
    f["log"] = q("SELECT step_order AS '#', step AS Step, rows_before AS 'Rows before', rows_after AS 'Rows after', "
                 "missing_before AS 'Missing before', missing_after AS 'Missing after' FROM cleaning_log ORDER BY 1")
    f["schema"] = q("SELECT name AS Object, type AS Type FROM sqlite_master WHERE type IN ('table','view') "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY type, name")
    f["columns"] = q("SELECT name, type FROM pragma_table_info('products')")
    f["keywords"] = q("""SELECT keyword AS Keyword,
                         SUM(data_source='api') AS 'API products', SUM(data_source='csv') AS 'CSV products',
                         ROUND(AVG(CASE WHEN data_source='api' THEN price END)) AS 'API avg price (₹)',
                         ROUND(100.0*AVG(CASE WHEN data_source='api' THEN has_discount END),1) AS 'API % discounted'
                         FROM products GROUP BY keyword ORDER BY keyword""")
    as_ints = lambda row: {k: (v if k == "avg_price" else int(v)) for k, v in row.items()}
    f["api"] = as_ints(q("""SELECT COUNT(*) products, AVG(price) avg_price,
                    COUNT(DISTINCT CASE WHEN brand!='Unbranded' THEN brand END) brands,
                    COUNT(DISTINCT platform) platforms FROM products WHERE data_source='api'""").iloc[0].to_dict())
    f["all"] = as_ints(q("""SELECT COUNT(*) products, COUNT(DISTINCT CASE WHEN brand!='Unbranded' THEN brand END) brands,
                    COUNT(DISTINCT platform) platforms FROM products""").iloc[0].to_dict())
    return f


# ---------------------------------------------------------------- document
CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
* { box-sizing: border-box; }
body { font-family: Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color: #0f172a; font-size: 10.2pt;
       line-height: 1.5; margin: 0; }
h1 { font-size: 21pt; letter-spacing: -0.02em; margin: 0 0 4mm 0; color: #1e1b4b; }
h2 { font-size: 15pt; letter-spacing: -0.01em; margin: 7mm 0 2.5mm 0; color: #1e1b4b; border-bottom: 2px solid #e0e7ff; padding-bottom: 1.5mm; }
h3 { font-size: 11.5pt; margin: 5mm 0 1.5mm 0; color: #312e81; }
p { margin: 0 0 2.5mm 0; }
ul, ol { margin: 0 0 3mm 0; padding-left: 5.5mm; }
li { margin-bottom: 1.2mm; }
code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 8.6pt; background: #f1f5f9; padding: 0.2mm 1mm; border-radius: 1mm; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm 0; font-size: 8.8pt; page-break-inside: avoid; }
th { background: #eef2ff; color: #312e81; text-align: left; font-weight: 600; padding: 1.6mm 2mm; border-bottom: 1px solid #c7d2fe; }
td { padding: 1.4mm 2mm; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
figure { margin: 3mm 0 5mm 0; page-break-inside: avoid; text-align: center; }
figure img { border: 1px solid #e5e7eb; border-radius: 2mm; }
figcaption { font-size: 8.4pt; color: #64748b; margin-top: 1.5mm; }
.section { page-break-before: always; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover .band { background: linear-gradient(135deg, #312e81, #4f46e5 60%, #0ea5e9); color: white; border-radius: 4mm; padding: 16mm 14mm; }
.cover .eyebrow { text-transform: uppercase; letter-spacing: 0.14em; font-size: 9pt; opacity: 0.85; }
.cover h1 { color: white; font-size: 30pt; margin: 4mm 0 3mm 0; line-height: 1.12; }
.cover .sub { font-size: 12.5pt; opacity: 0.92; max-width: 150mm; }
.meta td { border: none; padding: 1.2mm 0; font-size: 10pt; }
.meta td:first-child { color: #64748b; width: 42mm; }
.kpis { display: flex; gap: 3mm; margin: 3mm 0 4mm 0; }
.kpi { flex: 1; border: 1px solid #e0e7ff; border-left: 3px solid #4f46e5; border-radius: 2mm; padding: 2.5mm 3mm; }
.kpi .v { font-size: 15pt; font-weight: 750; color: #1e1b4b; }
.kpi .l { font-size: 8.3pt; color: #475569; }
.callout { background: #f5f7ff; border: 1px solid #e0e7ff; border-radius: 2mm; padding: 3mm 4mm; margin: 3mm 0 4mm 0; }
.qa { page-break-inside: avoid; margin-bottom: 3.2mm; }
.qa .q { font-weight: 650; color: #312e81; margin-bottom: 0.8mm; }
.qa .a p { margin-bottom: 1.4mm; }
.qa .a table { font-size: 8.3pt; }
.toc li { margin-bottom: 1.6mm; }
.two { display: flex; gap: 5mm; } .two > div { flex: 1; }
.small { font-size: 8.8pt; color: #475569; }
"""


def build_html(github, live):
    answers, insights = notebook_answers()
    f = facts()
    shots = shrink_screenshots()
    api, csv = f["by_source"].get("api", 0), f["by_source"].get("csv", 0)
    api_raw, csv_raw = f["raw_by_source"].get("api", 0), f["raw_by_source"].get("csv", 0)

    def qa(ids):
        out = []
        for qid in ids:
            question, answer = answers[qid]
            out.append(f'<div class="qa"><div class="q">{qid}. {html.escape(question)}</div><div class="a">{answer}</div></div>')
        return "".join(out)

    def answer_only(qid):
        return answers[qid][1]

    link = lambda url: f'<a href="{url}">{html.escape(url)}</a>' if url else "<em>see README</em>"

    parts = []
    # ---------------- cover
    parts.append(f"""
    <div class="cover">
      <div class="band">
        <div class="eyebrow">E-commerce analytics · Digital marketing intelligence · BI</div>
        <h1>Brand Visibility<br/>Intelligence Dashboard</h1>
        <div class="sub">How brands rank, price and discount in Google Shopping search results, built from SerpApi
        data merged with the provided dataset, stored in SQLite and explored in Streamlit.</div>
      </div>
      <div>
        <table class="meta">
          <tr><td>Author</td><td>{AUTHOR}</td></tr>
          <tr><td>Data snapshot</td><td>{config.SNAPSHOT_DATE} · Google Shopping, India</td></tr>
          <tr><td>Dataset</td><td>{f['all']['products']:,} products · {f['all']['brands']} brands · {f['all']['platforms']} platforms · {len(config.KEYWORDS)} keywords</td></tr>
          <tr><td>Stack</td><td>Python, Requests, Pandas, SQLite, Matplotlib, Seaborn, Plotly, Streamlit</td></tr>
          <tr><td>Live dashboard</td><td>{link(live)}</td></tr>
          <tr><td>Source code</td><td>{link(github)}</td></tr>
        </table>
      </div>
    </div>""")

    # ---------------- contents
    parts.append("""
    <div class="section"><h1>Contents</h1><ol class="toc">
      <li>Executive summary</li><li>Problem statement and business use cases</li><li>Data sources</li>
      <li>Approach and architecture</li><li>Data extraction (API)</li><li>Data merging</li><li>Data cleaning</li>
      <li>Feature engineering</li><li>Data storage (SQL)</li><li>Exploratory data analysis</li>
      <li>Dashboard</li><li>Business insights and recommendations</li><li>Assumptions and limitations</li>
      <li>Reproducing the project</li><li>Appendix A: the 30 data-cleaning questions</li>
      <li>Appendix B: the 30 EDA questions</li></ol></div>""")

    # ---------------- 1 executive summary
    parts.append(f"""
    <div class="section"><h2>1. Executive summary</h2>
    <p>This project measures how visible brands are in online shopping search results and what drives that visibility.
    Product listings for five search keywords were pulled from Google Shopping through SerpApi ({api_raw} ranked results)
    and merged with the provided dataset ({csv_raw:,} rows). After cleaning, {f['all']['products']:,} products remain:
    {api} real Google Shopping listings and {csv:,} from the provided file.</p>
    <div class="kpis">
      <div class="kpi"><div class="v">{f['all']['products']:,}</div><div class="l">clean products in SQLite</div></div>
      <div class="kpi"><div class="v">{f['api']['brands']}</div><div class="l">brands in real search results</div></div>
      <div class="kpi"><div class="v">{f['api']['platforms']}</div><div class="l">sellers / platforms (real data)</div></div>
      <div class="kpi"><div class="v">₹{f['api']['avg_price']:,.0f}</div><div class="l">average real price</div></div>
    </div>
    <h3>Key findings</h3>{insights}
    </div>""")

    # ---------------- 2 problem
    parts.append("""
    <div class="section"><h2>2. Problem statement and business use cases</h2>
    <p><strong>Problem:</strong> build a Brand Visibility Intelligence Dashboard by extracting product data from online
    shopping search results through an API, and analyse how brands perform in search rankings, pricing strategies and
    platform competition.</p>
    <h3>Business use cases addressed</h3>
    <table><thead><tr><th>Use case</th><th>How the project answers it</th></tr></thead><tbody>
    <tr><td>Competitive analysis for e-commerce brands</td><td>Brand listing counts, top-10 presence and visibility score (Brands page, EDA E6–E10)</td></tr>
    <tr><td>Pricing strategy optimisation</td><td>Price distribution, price bands, price index vs category, price vs rank (Pricing page, E11–E15)</td></tr>
    <tr><td>Market positioning for new launches</td><td>Share of products per price band and how crowded each band is (E12)</td></tr>
    <tr><td>Platform performance comparison</td><td>Listings, prices, ratings and ranking per platform (Platforms page, E21–E25)</td></tr>
    <tr><td>Identifying high-visibility brands and products</td><td>Visibility score, top-10 products (Visibility page, E26–E30)</td></tr>
    <tr><td>Monitoring discount strategies</td><td>Discount share and depth by brand and platform (E16–E20); the pipeline re-runs on demand to track changes</td></tr>
    </tbody></table></div>""")

    # ---------------- 3 data
    parts.append(f"""
    <div class="section"><h2>3. Data sources</h2>
    <h3>3.1 Google Shopping via SerpApi (real data)</h3>
    <p>Engine <code>google_shopping</code>, Google domain <code>google.co.in</code>, <code>gl=in</code>, <code>hl=en</code>,
    location India, so prices come back in rupees like the provided file. The same five keywords as the CSV were queried:
    {", ".join(f"<em>{k}</em>" for k in config.KEYWORDS)}. Each search returns one page of 40 ranked products; SerpApi ignores
    pagination for this engine. Raw JSON responses are cached in <code>data/raw/serpapi/</code>.</p>
    <h3>3.2 Provided dataset (<code>brand_dirty_dataset.csv</code>)</h3>
    <p>{csv_raw:,} rows and 7 columns (<code>keyword, title, price, rating, reviews, platform, delivery</code>) with planted
    problems: placeholder text, a -999 price code, mixed-case platform names, “!!!” in titles, duplicates and extreme prices.
    It turned out to be synthetic: each of its 9 brands sells every product category, and it has no search positions.</p>
    <h3>3.3 Variables</h3>
    <table><thead><tr><th>Column</th><th>Type</th><th>Description</th></tr></thead><tbody>
    <tr><td>keyword</td><td>text</td><td>Search term used to find the product</td></tr>
    <tr><td>title</td><td>text</td><td>Product name as listed</td></tr>
    <tr><td>price</td><td>float (₹)</td><td>Selling price after any discount</td></tr>
    <tr><td>raw_price</td><td>float (₹)</td><td>Original price before discount (API <code>old_price</code>; equals price when none is shown)</td></tr>
    <tr><td>rating</td><td>float</td><td>Average user rating out of 5</td></tr>
    <tr><td>reviews</td><td>integer</td><td>Number of customer reviews</td></tr>
    <tr><td>platform</td><td>category</td><td>Seller or marketplace (Amazon, Flipkart, Croma…)</td></tr>
    <tr><td>delivery</td><td>category</td><td>Delivery terms (Free Delivery, N Days, Unknown)</td></tr>
    <tr><td>position</td><td>integer</td><td>Rank in the search results (1 = top); row order for the CSV</td></tr>
    <tr><td>data_source</td><td>category</td><td><code>api</code> or <code>csv</code></td></tr>
    </tbody></table>
    <h3>3.4 Products per keyword after cleaning</h3>
    {table(f['keywords'], {'API avg price (₹)': lambda v: f"{v:,.0f}"})}
    </div>""")

    # ---------------- 4 approach
    parts.append(f"""
    <div class="section"><h2>4. Approach and architecture</h2>
    <p>The work follows the nine steps in the brief. Each step is a separate module, and every rule (keywords, thresholds,
    bands, aliases) lives in <code>config.py</code> rather than in the code.</p>
    <table><thead><tr><th>#</th><th>Step</th><th>Implementation</th></tr></thead><tbody>
    <tr><td>1</td><td>Data extraction</td><td><code>src/extract.py</code>: SerpApi requests, JSON cache, flattening to a DataFrame</td></tr>
    <tr><td>2</td><td>Additional dataset</td><td><code>src/load.py</code>: reads the CSV as text so dirty values survive until cleaning</td></tr>
    <tr><td>3</td><td>Data merging</td><td><code>load.merge</code>: aligned columns and <code>pd.concat</code>, with a <code>data_source</code> tag</td></tr>
    <tr><td>4</td><td>Data cleaning</td><td><code>src/clean.py</code>: 8 ordered steps, each logged</td></tr>
    <tr><td>5</td><td>Feature engineering</td><td><code>src/features.py</code>: brand, visibility score, bands, discount</td></tr>
    <tr><td>6</td><td>Data storage</td><td><code>src/db.py</code>: SQLite tables and views</td></tr>
    <tr><td>7</td><td>EDA</td><td><code>notebooks/eda.ipynb</code>: 60 questions with code, output and written answers</td></tr>
    <tr><td>8</td><td>Visualisation</td><td><code>app/</code>: Streamlit dashboard reading SQLite through parameterised SQL</td></tr>
    <tr><td>9</td><td>Insight generation</td><td>Notebook “Key insights”, dashboard insight cards, sections 10–12 of this report</td></tr>
    </tbody></table>
    <div class="callout"><code>python pipeline.py</code> runs steps 1–6 end to end in a few seconds. Add
    <code>--refresh-api</code> to fetch fresh results (5 API searches), which makes repeat monitoring a one-line job.</div>
    </div>""")

    # ---------------- 5 extraction
    parts.append(f"""
    <div class="section"><h2>5. Data extraction (API)</h2>
    <p>For every keyword, <code>fetch_keyword</code> calls <code>https://serpapi.com/search.json</code> with the parameters
    above. Errors are raised with a clear message and without the request URL, which contains the API key. The key is read
    from a <code>.env</code> file that git ignores. Each product in <code>shopping_results</code> becomes one row with
    title, price, original price, rating, reviews, seller, delivery and position.</p>
    <h3>Problems found in the API data, and the fixes</h3>
    <table><thead><tr><th>Problem</th><th>Fix</th></tr></thead><tbody>
    <tr><td>For strings like <code>"60% off₹990"</code>, SerpApi's <code>extracted_old_price</code> returns <strong>60</strong> (the percentage), not 990</td>
        <td>The ₹ amount is read from the <code>old_price</code> text; a “N% off” tag is converted back to a price</td></tr>
    <tr><td>Installment listings: <code>extracted_price</code> is the monthly amount (the brief's own sample shows $29.12/mo)</td>
        <td>Price = monthly amount × number of periods</td></tr>
    <tr><td><code>categorized_shopping_results</code> carousels (“Deals”, “Under ₹7,000”) restart their positions at 1</td>
        <td>Only the main ranked list is used, so every product has a unique, comparable rank (1–40)</td></tr>
    <tr><td>Seller names vary (<code>Amazon.in</code>, <code>Myntra - MNow</code>, <code>Bata IN</code>)</td>
        <td>Suffixes are removed and names are mapped to one platform name</td></tr>
    </tbody></table>
    <p>Result: {api_raw} API rows ({api_raw // len(config.KEYWORDS)} per keyword), saved as <code>data/processed/api_products.csv</code>.</p>
    <h2>6. Data merging</h2>
    <p>The CSV is loaded with every column as text, its columns are lower-cased to match, and two columns the CSV lacks are
    added: <code>position</code> (row order within keyword) and <code>raw_price</code> (empty). Both sources then share the same
    columns, and <code>pd.concat</code> appends them into one {api_raw + csv_raw:,}-row dataset. Each row keeps a
    <code>data_source</code> tag because the two sources behave very differently: CSV prices are about 4× real prices, and
    only the API has real ranks and original prices.</p>
    </div>""")

    # ---------------- 7 cleaning
    parts.append(f"""
    <div class="section"><h2>7. Data cleaning</h2>
    <p>Cleaning runs as eight ordered functions. The rule throughout: <strong>an impossible value becomes missing, an
    implausible extreme is capped, and no row is dropped without a reason</strong>. Every filled or capped value is flagged.</p>
    <table><thead><tr><th>Issue found</th><th>Size</th><th>Treatment</th></tr></thead><tbody>
    <tr><td>Price as text (<code>"Not Available"</code>), reviews as text (<code>"many"</code>)</td><td>66 / 26 cells</td><td>Parsed safely; placeholders become missing</td></tr>
    <tr><td>Price of -999</td><td>26</td><td>Invalid code → missing</td></tr>
    <tr><td>Missing price / rating / reviews</td><td>see C4–C5</td><td>Median for the same keyword <em>and</em> source, flagged in <code>*_imputed</code>. API products with no review count get 0 reviews</td></tr>
    <tr><td>Extreme CSV prices (up to ₹4.98 lakh)</td><td>46 capped</td><td>Capped at per-keyword Q3 + 1.5×IQR; real API prices left as they are</td></tr>
    <tr><td>“!!!” and stray symbols in titles</td><td>136 + 4</td><td>Removed, spaces collapsed, brand capitalisation kept</td></tr>
    <tr><td>Platform spelt 61 ways</td><td>→ {f['all']['platforms']}</td><td>Suffixes stripped, aliases mapped</td></tr>
    <tr><td>Duplicate listings</td><td>99</td><td>Same keyword + title + platform + price after cleaning; first kept</td></tr>
    <tr><td>Delivery in 9 formats</td><td>→ 4</td><td>Free Delivery / N Days / Paid Delivery / Unknown</td></tr>
    </tbody></table>
    <h3>Cleaning log (stored in the <code>cleaning_log</code> table)</h3>
    {table(f['log'])}
    <p class="small">The cells still missing after the last step are <code>product_id</code>/<code>product_link</code>, which only API rows have; they
    are not part of the analysis table. After cleaning there are no missing values, no non-positive prices, no ratings outside 0–5 and no duplicates (C26).</p>
    <div class="two"><div>{image(fig('c17_raw_price_distribution'), 'Raw price distribution by source, before cleaning')}</div>
    <div>{image(fig('c18_csv_price_outliers'), 'CSV raw prices by keyword: the far-right points are entry errors')}</div></div>
    </div>""")

    # ---------------- 8 features + 9 storage
    parts.append(f"""
    <div><h2>8. Feature engineering</h2>
    <table><thead><tr><th>Feature</th><th>Definition</th><th>Why</th></tr></thead><tbody>
    <tr><td><code>brand</code></td><td>Known brand anywhere in the title, else the first word; generic or size words → Unbranded</td><td>Neither source has a brand column</td></tr>
    <tr><td><code>visibility_score</code></td><td>100 / log₂(position + 1): 100 at #1, 63 at #2, 29 at #10</td><td>Decays like click-through, so the top spots count most</td></tr>
    <tr><td><code>is_top_10</code></td><td>position ≤ 10</td><td>First-screen presence</td></tr>
    <tr><td><code>price_range</code></td><td>Budget &lt; ₹5k · Mid-range ₹5k–15k · Premium ₹15k–35k · Luxury ₹35k+</td><td>Positioning bands</td></tr>
    <tr><td><code>rating_range</code></td><td>Below 3 · 3–4 · 4–4.5 · 4.5–5</td><td>Dashboard filter</td></tr>
    <tr><td><code>review_engagement</code></td><td>No reviews · 1–99 · 100–999 · 1,000+</td><td>Low vs high engagement</td></tr>
    <tr><td><code>discount_amount</code>, <code>discount_pct</code>, <code>has_discount</code></td><td>raw_price − price, and as % of raw_price</td><td>Offer analysis</td></tr>
    <tr><td><code>*_imputed</code>, <code>price_capped</code></td><td>1 where a value was filled or capped</td><td>Lets every analysis exclude filled values</td></tr>
    </tbody></table>
    <h2>9. Data storage (SQL)</h2>
    <p>Python connects to SQLite with <code>sqlite3</code>. <code>pipeline.py</code> rebuilds the database from scratch each run.
    Constraints guard the data: prices must be positive, ratings between 0 and 5, and the source either api or csv.</p>
    <ul><li><strong>products</strong>: the clean analysis table ({f['all']['products']:,} rows, {len(f['columns']) - 1} columns: the
    variables in section 3 plus the features in section 8).</li>
    <li><strong>raw_products</strong>: the merged rows exactly as extracted ({api_raw + csv_raw:,} rows), for traceability.</li>
    <li><strong>cleaning_log</strong>: the step-by-step log shown in section 7.</li>
    <li><strong>Views</strong> <code>brand_summary</code>, <code>platform_summary</code> and <code>keyword_summary</code>
    pre-aggregate per brand, platform and keyword for quick queries.</li></ul>
    <p>The dashboard never loads a CSV: each sidebar filter is added to a parameterised <code>WHERE</code> clause, for example
    <code>WHERE data_source IN (?) AND keyword IN (?)</code>, and every chart is its own SQL query.</p>
    </div>""")

    # ---------------- 10 EDA
    parts.append(f"""
    <div class="section"><h2>10. Exploratory data analysis</h2>
    <p>All 30 EDA questions are answered in the notebook and in Appendix B. The highlights by theme are below. Ranking
    conclusions use the real Google Shopping data, since the CSV's positions are only row order.</p>
    <h3>General market</h3>{answer_only('E3')}
    <div class="two"><div>{image(fig('e03_price_distribution'), 'Price distribution by source (log scale)')}</div>
    <div>{image(fig('e12_price_range'), 'Products per price range by source')}</div></div>
    <h3>Brands</h3>{answer_only('E6')}{answer_only('E11')}
    {image(fig('e11_brand_price_index'), 'Brand price relative to its keyword median (1.0 = typical)', '58%')}
    </div>
    <div class="section">
    <h3>Pricing and discounts</h3>{answer_only('E13')}{answer_only('E16')}{answer_only('E19')}
    <div class="two"><div>{image(fig('e18_discount_by_brand'), 'Average discount by brand (API)')}</div>
    <div>{image(fig('e21_platform_listings'), 'Listings per platform (API, top 10)')}</div></div>
    <h3>Platforms</h3>{answer_only('E24')}
    </div>
    <div class="section">
    <h3>Visibility and ranking</h3>{answer_only('E28')}{answer_only('E29')}{answer_only('E30')}
    <div class="two"><div>{image(fig('e29_reviews_vs_position'), 'Reviews vs search position (API)')}</div>
    <div>{image(fig('e30_top10_drivers'), 'What predicts a top-10 position (logistic coefficients)')}</div></div>
    </div>""")

    # ---------------- 11 dashboard
    pages = [
        ("01_overview", "Overview", "KPIs: total products, average price, average rating, total reviews, average visibility score. "
         "Real-market insight cards. Charts: price distribution (histogram), products per keyword (bar), platform share (donut), products per price range."),
        ("02_brands", "Brands", "KPIs: total brands, top brand, highest-rated brand, best-visibility brand, average visibility. "
         "Charts: brand vs product count, brand vs average rating, top brands in top-10 positions, visibility score by brand."),
        ("03_pricing", "Pricing", "KPIs: average price, max price, lowest price, % discounted products. Charts: price distribution, price spread by keyword, "
         "price vs ranking (scatter), price vs rating (scatter), discount % by brand and by platform."),
        ("04_platforms", "Platforms", "KPIs: total platforms, best platform (rating), cheapest platform, platform with most products. Charts: platform vs "
         "product count, average price, average rating, average ranking, and brand distribution per platform (stacked bar)."),
        ("05_visibility", "Visibility & ranking", "KPIs: average rating, average visibility score, % of products in the top 10, best-ranked product. Charts: "
         "ranking distribution, rating vs ranking, reviews vs ranking (bubble), visibility score by brand, and a table of the highest-visibility products."),
        ("06_product_explorer", "Product explorer", "Title search (SQL LIKE), filtered KPIs, a sortable table (title, brand, price, rating, reviews, platform, "
         "discount, position, visibility) with top performers highlighted, CSV download, rating vs price and reviews vs ranking charts."),
        ("08_brands_google_shopping_only", "Filters in action", "The Brands page with the data source filter set to Google Shopping only: every KPI "
         "and chart is re-queried, and the real market's brand leaders appear."),
        ("09_explorer_search", "Search in action", "The product explorer after searching “air fryer”."),
        ("07_about", "About", "Data sources, pipeline, caveats and metric definitions, for anyone reading the dashboard cold."),
    ]
    dash = [f"""<div class="section"><h2>11. Dashboard</h2>
    <p>Built in Streamlit with seven pages in a top navigation bar. A sidebar of filters (data source, keyword, brand,
    platform, price range, rating range) is shared by every page and changes the SQL behind each element. Two rules
    keep the numbers honest: discount and ranking averages use Google Shopping rows only, and average ratings use real
    ratings only. Live version: {link(live)}.</p>"""]
    for i, (key, title, text) in enumerate(pages):
        if i:
            dash.append('<div class="section">')
        dash.append(f"<h3>11.{i + 1} {title}</h3><p>{text}</p>{image(shots[key], title + ' page')}</div>")
    parts.append("".join(dash))

    # ---------------- 12 insights & recommendations
    parts.append(f"""
    <div class="section"><h2>12. Business insights and recommendations</h2>
    <p>The seven key findings are listed in the executive summary. Here they are mapped to the business use cases in the brief.</p>
    <table><thead><tr><th>Use case</th><th>What the data shows</th></tr></thead><tbody>
    <tr><td>Competitive analysis</td><td>No brand dominates real search results: the leaders have 7 of 195 listings. Top-10 slots are spread
        thinly (Croma, with 3 of 3 listings in the top 10, is the most consistent).</td></tr>
    <tr><td>Pricing strategy</td><td>Price relative to category doesn't relate to rank. Puma and boAt price 1.6–2.3× their category median;
        Portronics and Campus compete at about 0.5×.</td></tr>
    <tr><td>Launch positioning</td><td>54% of real listings are under ₹5k and 91% under ₹15k; the Premium and Luxury bands hold 9%.</td></tr>
    <tr><td>Platform comparison</td><td>Amazon has the most listings (28%) but only 20% of them rank in the top 10; Pepperfry places
        5 of 7 in the top 10. Specialists win their niche.</td></tr>
    <tr><td>High-visibility brands</td><td>Croma, Nivia, Portronics and LG have the highest average visibility among brands with 3+ listings.</td></tr>
    <tr><td>Discount monitoring</td><td>46% of real listings show a discount (31% off on average). AJIO and Flipkart discount every listing,
        Amazon only 31% of its listings. Discounted products don't rank better (p = 0.71).</td></tr>
    </tbody></table>
    <h3>Recommendations</h3>
    <ol>
      <li><strong>Compete on coverage and relevance, not discount depth.</strong> Discounts, price and ratings don't move
      search rank. Brands should list with more sellers, including specialist stores that win their niche (Pepperfry for
      chairs, Decathlon for shoes), and write titles that match how shoppers search (brand + core spec).</li>
      <li><strong>On this evidence, pricing above the category doesn't cost visibility.</strong> A product's price relative to its
      category is unrelated to its rank (Spearman ρ = +0.05, p = 0.51), so price can be set for margin and positioning rather
      than to chase rank. With 195 real listings this is a weak signal, worth re-testing as more snapshots are collected.</li>
      <li><strong>Launch where the field is thin, or go where the volume is.</strong> 91% of real listings are under ₹15,000.
      A launch above that point competes with fewer products; below it, it needs to stand out on reviews and seller coverage.</li>
      <li><strong>Treat discounts as a platform norm.</strong> On AJIO and Flipkart every listing shows a discount, so a
      discount there is expected rather than a differentiator. On Amazon, an honest everyday price is the norm.</li>
      <li><strong>Get the first reviews.</strong> 56% of real products have none. Top-10 products are slightly more likely to
      have any reviews (51% vs 42%), and a first review is a cheap thing to test.</li>
      <li><strong>Monitor continuously.</strong> <code>python pipeline.py --refresh-api</code> re-captures all five keywords with
      five API calls. Scheduled weekly, it turns this snapshot into a share-of-top-10 trend per brand and platform.</li>
    </ol></div>""")

    # ---------------- 13 assumptions + 14 reproduce
    parts.append(f"""
    <div class="section"><h2>13. Assumptions and limitations</h2>
    <ul>
      <li><strong>Ranking means search position.</strong> The brief sometimes writes “rating (ranking)”; star rating and search rank
      are kept as separate measures.</li>
      <li><strong>The CSV is synthetic.</strong> Its positions are row order and its brands are random, so it is used for the cleaning
      exercise and for whole-dataset questions, not for brand or ranking conclusions.</li>
      <li><strong>Original prices</strong> exist only where Google Shopping shows one; elsewhere the discount is 0.</li>
      <li><strong>Filled values</strong> keep every product in the data but are excluded from rating averages and flagged everywhere.</li>
      <li><strong>One snapshot</strong> ({config.SNAPSHOT_DATE}), India locale, 40 results per keyword. Brand-level results in the real data
      rest on 3–7 listings per brand, so they show direction, not precise rankings. Over half of real ratings are missing.</li>
      <li><strong>Ranking drivers outside the data</strong> (query relevance, merchant quality, paid placement) probably explain
      most of the rank, as the weak model in E30 shows.</li>
    </ul>
    <h2>14. Reproducing the project</h2>
    <p>Source code: {link(github)}</p>
    <ol><li><code>pip install -r requirements.txt</code></li>
    <li>Optional: copy <code>.env.example</code> to <code>.env</code> and add a SerpApi key (only needed to re-fetch)</li>
    <li><code>python pipeline.py</code> rebuilds the clean CSV and the SQLite database from the cached API data</li>
    <li><code>jupyter notebook notebooks/eda.ipynb</code> for the analysis</li>
    <li><code>streamlit run app/streamlit_app.py</code> for the dashboard</li></ol>
    <h3>Deliverables</h3>
    <table><thead><tr><th>Deliverable</th><th>Location</th></tr></thead><tbody>
    <tr><td>Source code</td><td><code>src/</code>, <code>pipeline.py</code>, <code>app/</code>, <code>notebooks/eda.ipynb</code></td></tr>
    <tr><td>Clean dataset</td><td><code>data/processed/clean_dataset.csv</code></td></tr>
    <tr><td>SQL database</td><td><code>data/brand_visibility.db</code></td></tr>
    <tr><td>Dashboard</td><td><code>app/</code> · {link(live)}</td></tr>
    <tr><td>Report</td><td>this document, <code>reports/Brand_Visibility_Intelligence_Report.pdf</code></td></tr>
    <tr><td>Screenshots</td><td><code>reports/screenshots/</code></td></tr>
    </tbody></table></div>""")

    # ---------------- appendices
    parts.append(f'<div class="section"><h2>Appendix A: the 30 data-cleaning questions</h2>{qa([f"C{i}" for i in range(1, 31)])}</div>')
    parts.append(f'<div class="section"><h2>Appendix B: the 30 EDA questions</h2>{qa([f"E{i}" for i in range(1, 31)])}</div>')

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Brand Visibility Intelligence: Project Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>{CSS}</style></head><body>{''.join(parts)}</body></html>"""


def print_pdf(html_path, pdf_path):
    from playwright.sync_api import sync_playwright
    footer = ('<div style="font-size:7.5pt;color:#94a3b8;width:100%;padding:0 15mm;display:flex;justify-content:space-between;'
              'font-family:Helvetica,Arial,sans-serif"><span>Brand Visibility Intelligence · Project report</span>'
              '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, display_header_footer=True,
                 header_template="<span></span>", footer_template=footer,
                 margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--github", default=config.GITHUB_URL)
    parser.add_argument("--live", default=config.LIVE_URL)
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    html_path = BUILD / "report.html"
    html_path.write_text(build_html(args.github, args.live), encoding="utf-8")
    print_pdf(html_path, PDF_PATH)
    print(f"wrote {PDF_PATH.relative_to(ROOT)}")
