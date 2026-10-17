"""Cleaning steps. Each step is a small function; clean() runs them in order and
records what each step changed, which feeds the data-cleaning section of the report.
"""
import logging
import re

import numpy as np
import pandas as pd

import config

log = logging.getLogger(__name__)

# Statistics for capping and imputation are computed within these groups.
GROUP_KEYS = ["data_source", "keyword"]


def standardize_columns(df):
    df = df.copy()
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))
    return df


def _to_number(series):
    """Parse numbers like '₹1,299.00', '36225.0' or 3241; placeholders become NaN."""
    text = series.astype("string").str.strip().str.lower()
    text = text.mask(text.isin(config.MISSING_TOKENS))
    text = text.str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(text, errors="coerce").astype(float)


def convert_numeric(df):
    df = df.copy()
    for col in ["price", "raw_price", "rating", "reviews", "position"]:
        df[col] = _to_number(df[col])
    return df


def invalidate_bad_values(df):
    """Values that are impossible are treated as missing, not as data."""
    df = df.copy()
    df.loc[df["price"] <= config.INVALID_PRICE_MAX, "price"] = np.nan
    df.loc[df["raw_price"] <= config.INVALID_PRICE_MAX, "raw_price"] = np.nan
    df.loc[~df["rating"].between(config.RATING_MIN, config.RATING_MAX), "rating"] = np.nan
    df.loc[df["reviews"] < 0, "reviews"] = np.nan
    return df


def clean_text(df):
    """Strip noise like '!!!' from titles and normalise whitespace."""
    df = df.copy()
    df["title"] = (df["title"].astype("string")
                   .str.replace(r"[^\w\s\-&./()+,'\"]", " ", regex=True)
                   .str.replace(r"['\"]{2,}", " ", regex=True)
                   .str.replace(r"\s+", " ", regex=True).str.strip())
    df["keyword"] = df["keyword"].astype("string").str.strip().str.lower()
    return df


def _canonical_platform(name):
    if pd.isna(name) or not str(name).strip():
        return "Unknown"
    name = re.sub(config.PLATFORM_SUFFIXES, "", str(name).strip(), flags=re.IGNORECASE).strip()
    lowered = name.lower()
    for alias, canonical in config.PLATFORM_ALIASES.items():
        if alias in lowered:
            return canonical
    return name.title() if name.islower() or name.isupper() else name


def _canonical_delivery(value):
    """CSV uses 'Free Delivery' / 'N Days'; Google uses free-text like 'Free delivery by Mon'."""
    if pd.isna(value) or not str(value).strip():
        return "Unknown"
    text = str(value).strip().lower()
    if "free" in text:
        return "Free Delivery"
    days = re.search(r"(\d+)\s*day", text)
    if days:
        n = int(days.group(1))
        return f"{n} Day" if n == 1 else f"{n} Days"
    if re.search(r"\d", text):
        return "Paid Delivery"
    return "Unknown"


def standardize_categories(df):
    df = df.copy()
    df["platform"] = df["platform"].map(_canonical_platform)
    df["delivery"] = df["delivery"].map(_canonical_delivery)
    return df


def remove_duplicates(df):
    """Exact listing duplicates; done after text and price cleaning so 'X !!!' matches 'X'."""
    return df.drop_duplicates(subset=config.DUPLICATE_KEYS, keep="first").reset_index(drop=True)


def cap_price_outliers(df):
    """Cap prices above the per-keyword IQR fence instead of dropping the products.

    Only sources in OUTLIER_CAP_SOURCES are capped: the CSV's outliers are entry
    errors (a ₹1.9 lakh power bank), while high API prices are real premium listings.
    """
    df = df.copy()
    grouped = df.groupby(GROUP_KEYS)["price"]
    q1, q3 = grouped.transform(lambda s: s.quantile(0.25)), grouped.transform(lambda s: s.quantile(0.75))
    fence = q3 + config.OUTLIER_IQR_MULTIPLIER * (q3 - q1)
    in_scope = df["data_source"].isin(config.OUTLIER_CAP_SOURCES)
    df["price_capped"] = in_scope & (df["price"] > fence)
    df["price"] = df["price"].where(~df["price_capped"], fence)
    return df


def impute_missing(df):
    """Fill missing price/rating/reviews with the keyword median and flag each fill.

    Medians are per data source: synthetic CSV prices must not fill real API gaps.

    Exception: in Google Shopping data a missing review count means the product has
    no reviews, so those become 0 rather than a median (see REVIEWS_MISSING_IS_ZERO).

    Missing raw_price means no original price was listed, i.e. no visible discount,
    so it falls back to the selling price.
    """
    df = df.copy()
    for col in ["price", "rating", "reviews"]:
        df[f"{col}_imputed"] = df[col].isna()
    no_reviews = df["reviews"].isna() & df["data_source"].isin(config.REVIEWS_MISSING_IS_ZERO)
    df.loc[no_reviews, "reviews"] = 0
    for col in ["price", "rating", "reviews"]:
        df[col] = df[col].fillna(df.groupby(GROUP_KEYS)[col].transform("median"))
    # No original price means no visible discount; an original below the selling price is not a discount either.
    df["raw_price"] = df["raw_price"].fillna(df["price"]).clip(lower=df["price"])
    df["rating"] = df["rating"].round(1)
    df["reviews"] = df["reviews"].round().astype("Int64")
    df["position"] = df["position"].astype("Int64")
    return df


STEPS = [
    standardize_columns,
    convert_numeric,
    invalidate_bad_values,
    clean_text,
    standardize_categories,
    remove_duplicates,
    cap_price_outliers,
    impute_missing,
]


def clean(df):
    """Run every cleaning step; return the clean frame and a per-step change log."""
    report = []
    for step in STEPS:
        before_rows, before_missing = len(df), int(df.isna().sum().sum())
        df = step(df)
        report.append({
            "step": step.__name__,
            "rows_before": before_rows,
            "rows_after": len(df),
            "missing_before": before_missing,
            "missing_after": int(df.isna().sum().sum()),
        })
        log.info("%-24s rows %d -> %d", step.__name__, before_rows, len(df))
    return df, pd.DataFrame(report)
