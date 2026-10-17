"""SQL behind the dashboard.

Every query takes a Filters object, and Filters.where() turns the sidebar
selections into one parameterised WHERE clause, so each chart and KPI is a
SQL query over the same filtered set of products.
"""
from dataclasses import dataclass

import config
from src import db

# Columns the sidebar can filter on. Names are fixed here and never come from user input.
FILTER_COLUMNS = ("data_source", "keyword", "brand", "platform", "price_range", "rating_range")
GROUPABLE_COLUMNS = ("brand", "platform", "keyword", "price_range", "data_source")


@dataclass(frozen=True)
class Filters:
    data_source: tuple = ()
    keyword: tuple = ()
    brand: tuple = ()
    platform: tuple = ()
    price_range: tuple = ()
    rating_range: tuple = ()
    search: str = ""

    def where(self, *extra):
        """WHERE clause and its parameters. An empty selection means 'all'."""
        clauses, params = [], []
        for column in FILTER_COLUMNS:
            values = getattr(self, column)
            if values:
                clauses.append(f"{column} IN ({', '.join('?' * len(values))})")
                params.extend(values)
        if self.search.strip():
            clauses.append("title LIKE ?")
            params.append(f"%{self.search.strip()}%")
        clauses.extend(extra)
        sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return sql, tuple(params)


def distinct_values(column):
    if column not in FILTER_COLUMNS:
        raise ValueError(column)
    rows = db.query(f"SELECT DISTINCT {column} AS v FROM products ORDER BY {column}")
    return rows["v"].tolist()


# Extra WHERE clause for metrics that only the Google Shopping data supports:
# discounts (the CSV has no original prices) and rankings (CSV "positions" are row order).
API_ONLY = "data_source = 'api'"


def kpis(f, extra=()):
    where, params = f.where(*extra)
    row = db.query(f"""
        SELECT COUNT(*)                                             AS products,
               AVG(price)                                           AS avg_price,
               MAX(price)                                           AS max_price,
               MIN(price)                                           AS min_price,
               AVG(CASE WHEN rating_imputed = 0 THEN rating END)    AS avg_rating,
               SUM(CASE WHEN reviews_imputed = 0 THEN reviews END)  AS total_reviews,
               AVG(visibility_score)                                AS avg_visibility,
               100.0 * AVG(has_discount)                            AS pct_discounted,
               100.0 * AVG(is_top_10)                               AS pct_top_10,
               COUNT(DISTINCT brand)                                AS brands,
               COUNT(DISTINCT platform)                             AS platforms
        FROM products{where}
    """, params)
    result = row.iloc[0].to_dict()
    for key in ("products", "brands", "platforms"):
        result[key] = int(result[key])
    return result


def products(f, limit=None):
    where, params = f.where()
    sql = f"""
        SELECT title, brand, platform, keyword, data_source, price, raw_price, discount_pct,
               has_discount, price_range, rating, rating_imputed, rating_range, reviews,
               position, visibility_score, is_top_10, delivery
        FROM products{where}
        ORDER BY visibility_score DESC, rating DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.query(sql, params)


def group_stats(f, by, min_listings=1, extra=()):
    """Per-group metrics. Average rating uses real (non-imputed) ratings only."""
    if by not in GROUPABLE_COLUMNS:
        raise ValueError(by)
    where, params = f.where(*extra)
    stats = db.query(f"""
        SELECT {by}                                                  AS name,
               COUNT(*)                                              AS listings,
               ROUND(AVG(price), 0)                                  AS avg_price,
               ROUND(AVG(CASE WHEN rating_imputed = 0 THEN rating END), 2) AS avg_rating,
               SUM(rating_imputed = 0)                               AS rated_listings,
               ROUND(AVG(position), 1)                               AS avg_position,
               ROUND(AVG(visibility_score), 1)                       AS avg_visibility,
               SUM(is_top_10)                                        AS top_10_listings,
               ROUND(AVG(discount_pct), 1)                           AS avg_discount,
               ROUND(100.0 * AVG(has_discount), 1)                   AS pct_discounted
        FROM products{where}
        GROUP BY {by}
        HAVING COUNT(*) >= ?
        ORDER BY listings DESC
    """, params + (min_listings,))
    # An empty result comes back with object columns; keep metrics numeric so charts still work.
    # Empty or all-NULL columns come back as object dtype; keep metrics numeric for charts.
    return stats.astype({column: float for column in stats.columns.drop("name")})


def brand_platform_matrix(f, top_brands, top_platforms):
    """Listing counts for the stacked brand-per-platform chart."""
    if not top_brands or not top_platforms:
        return db.query("SELECT NULL AS platform, NULL AS brand, 0 AS listings WHERE 0")
    where, params = f.where(
        f"brand IN ({', '.join('?' * len(top_brands))})",
        f"platform IN ({', '.join('?' * len(top_platforms))})",
    )
    return db.query(f"""
        SELECT platform, brand, COUNT(*) AS listings
        FROM products{where}
        GROUP BY platform, brand
    """, params + tuple(top_brands) + tuple(top_platforms))


def price_band_order():
    return [label for _, label in config.PRICE_BANDS]


def rating_band_order():
    return [label for _, label in config.RATING_BANDS]
