"""SQLite storage. One products table (the fact table) plus summary views the
dashboard and notebook query directly.
"""
import sqlite3
from contextlib import closing

import pandas as pd

import config

SCHEMA = """
DROP VIEW IF EXISTS brand_summary;
DROP VIEW IF EXISTS platform_summary;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
    product_key        INTEGER PRIMARY KEY,
    keyword            TEXT    NOT NULL,
    title              TEXT    NOT NULL,
    brand              TEXT    NOT NULL,
    platform           TEXT    NOT NULL,
    data_source        TEXT    NOT NULL CHECK (data_source IN ('csv', 'api')),
    price              REAL    NOT NULL CHECK (price > 0),
    raw_price          REAL    NOT NULL,
    discount_amount    REAL    NOT NULL,
    discount_pct       REAL    NOT NULL,
    has_discount       INTEGER NOT NULL,
    price_range        TEXT    NOT NULL,
    rating             REAL    CHECK (rating BETWEEN 0 AND 5),
    rating_range       TEXT,
    reviews            INTEGER,
    review_engagement  TEXT,
    delivery           TEXT    NOT NULL,
    position           INTEGER NOT NULL,
    visibility_score   REAL    NOT NULL,
    is_top_10          INTEGER NOT NULL,
    price_imputed      INTEGER NOT NULL,
    price_capped       INTEGER NOT NULL,
    rating_imputed     INTEGER NOT NULL,
    reviews_imputed    INTEGER NOT NULL
);

CREATE INDEX idx_products_keyword  ON products (keyword);
CREATE INDEX idx_products_brand    ON products (brand);
CREATE INDEX idx_products_platform ON products (platform);

CREATE VIEW brand_summary AS
SELECT brand,
       COUNT(*)                         AS products,
       ROUND(AVG(price), 2)             AS avg_price,
       ROUND(AVG(rating), 2)            AS avg_rating,
       ROUND(AVG(position), 1)          AS avg_position,
       ROUND(AVG(visibility_score), 2)  AS avg_visibility,
       SUM(is_top_10)                   AS top_10_listings,
       ROUND(AVG(discount_pct), 2)      AS avg_discount_pct
FROM products GROUP BY brand;

CREATE VIEW platform_summary AS
SELECT platform,
       COUNT(*)                         AS products,
       ROUND(AVG(price), 2)             AS avg_price,
       ROUND(AVG(rating), 2)            AS avg_rating,
       ROUND(AVG(position), 1)          AS avg_position,
       ROUND(AVG(discount_pct), 2)      AS avg_discount_pct
FROM products GROUP BY platform;
"""

TABLE_COLUMNS = [
    "keyword", "title", "brand", "platform", "data_source", "price", "raw_price",
    "discount_amount", "discount_pct", "has_discount", "price_range", "rating",
    "rating_range", "reviews", "review_engagement", "delivery", "position",
    "visibility_score", "is_top_10", "price_imputed", "price_capped",
    "rating_imputed", "reviews_imputed",
]


def connect(path=config.DB_PATH):
    return sqlite3.connect(path)


def write_products(df, path=config.DB_PATH):
    out = df[TABLE_COLUMNS].copy()
    for col in out.select_dtypes(include="bool").columns:
        out[col] = out[col].astype(int)
    with closing(connect(path)) as conn, conn:
        conn.executescript(SCHEMA)
        out.to_sql("products", conn, if_exists="append", index=False)
    return len(out)


def query(sql, params=(), path=config.DB_PATH):
    """Run a parameterised query and return a DataFrame."""
    with closing(connect(path)) as conn:
        return pd.read_sql_query(sql, conn, params=params)
