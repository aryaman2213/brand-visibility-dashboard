# Brand Visibility Intelligence Dashboard

Analyses how brands perform in e-commerce search results — ranking, pricing, discounts and
platform competition — using Google Shopping data (via SerpApi) merged with a provided CSV.

## Pipeline

```
SerpApi JSON ─┐
              ├─ merge ─ clean ─ features ─┬─ data/processed/clean_dataset.csv
dirty CSV ────┘                            └─ data/brand_visibility.db (SQLite)
```

| Module | Role |
|---|---|
| `config.py` | Paths, API params, keywords and every cleaning/feature rule |
| `src/extract.py` | SerpApi calls, per-keyword JSON cache, flattening |
| `src/load.py` | Reads the CSV, aligns it to the unified schema, `concat` merge |
| `src/clean.py` | Ordered cleaning steps with a per-step change log |
| `src/features.py` | Brand, visibility score, price/rating bands, discount |
| `src/db.py` | SQLite schema (`products` table, `brand_summary` / `platform_summary` views) |
| `pipeline.py` | Runs everything end to end |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your SerpApi key
python pipeline.py     # add --refresh-api to re-fetch instead of using the cache
```

## Assumptions

- **Ranking means `position`** (search rank, 1 = top). The brief sometimes writes "rating (ranking)";
  star rating and search rank are treated as separate columns throughout.
- **CSV position** — the CSV has no rank column, so a row's order within its keyword is taken as its
  search position.
- **Visibility score** = `100 / log2(position + 1)`: 100 at position 1, 63 at 2, 29 at 10. It decays the way
  click-through does, so the gap between #1 and #5 matters more than between #41 and #45.
- **Discount** — when no original price is listed (all CSV rows, many API rows), `raw_price` = `price`
  and discount is 0.
- **API original price** — read from the ₹ amount in `old_price`. SerpApi's own `extracted_old_price` returns the
  *percentage* for strings like `"60% off₹990"` (gives 60, not 990), so it is only used when it exceeds the price.
- **Installment offers** — for "₹X/mo" listings, `extracted_price` is the monthly amount, so price = monthly × `period`.
- **API volume** — Google Shopping via SerpApi returns one page (40 ranked items) per query; `start`/`num` are ignored.
- **API ranking** — only the main `shopping_results` list is used. The `categorized_shopping_results` carousels
  ("Deals", "Under ₹7,000") each restart their positions at 1, so their ranks can't be compared with the main list.
- **Brand** — known brand anywhere in the title, else the first word. Titles that start with a generic word
  ("Men…", "Ergonomic Chairs – …") and have no known brand are labelled `Unbranded`.
- **Locale** — SerpApi is queried with `gl=in` so prices are in INR like the CSV.

## Cleaning decisions

| Issue | Treatment |
|---|---|
| `"Not Available"` price, `"many"` reviews | Treated as missing |
| `-999` price | Invalid sentinel → missing |
| Missing price / rating / reviews | Median for the same keyword *and* source (synthetic CSV values never fill real API gaps), flagged in `*_imputed` columns. Exception: a Google Shopping listing with no review count has **0** reviews, not an unknown number |
| Price outliers (e.g. ₹4.9 lakh power bank) | CSV only: capped at per-keyword Q3 + 1.5×IQR, flagged in `price_capped`. API prices are real listings (a ₹13k Nike Pegasus is not an error), so they are left as is. |
| `"!!!"` and other noise in titles | Stripped, whitespace collapsed |
| `amazon` / `AMAZON` etc. | Mapped to one canonical platform name |
| Duplicates | Same keyword + title + platform + price, checked *after* text cleaning. Removes 94 CSV rows |
| Delivery | Normalised to Free Delivery / N Days / Paid Delivery / Unknown |
