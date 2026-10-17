"""Derived business metrics: brand, visibility score, price/rating bands, discount."""
import re

import numpy as np
import pandas as pd

import config

_BRAND_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in sorted(config.KNOWN_BRANDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_BRAND_CANONICAL = {b.lower(): b for b in config.KNOWN_BRANDS}


def extract_brand(title):
    """Known brand anywhere in the title, else the title's first word.

    Titles that open with a generic word ('Men Running Shoes', 'Ergonomic Chairs - ...')
    and contain no known brand are labelled Unbranded rather than guessed.
    """
    if pd.isna(title) or not str(title).strip():
        return "Unknown"
    match = _BRAND_PATTERN.search(str(title))
    if match:
        return _BRAND_CANONICAL[match.group(1).lower()]
    first = re.sub(r"[^\w]", "", str(title).split()[0]).lower()
    if not first or first in config.GENERIC_TITLE_WORDS:
        return "Unbranded"
    return str(title).split()[0].strip(",.-").title()


def visibility_score(position):
    """0–100 score that decays with rank like click-through does (DCG-style).

    Position 1 -> 100, 2 -> 63, 3 -> 50, 10 -> 29, 50 -> 18.
    """
    return (100 / np.log2(position.astype(float) + 1)).round(2)


def _band(values, bands):
    bins = [-np.inf] + [upper for upper, _ in bands]
    labels = [label for _, label in bands]
    return pd.cut(values, bins=bins, labels=labels, right=False)


def add_features(df):
    df = df.copy()
    df["brand"] = df["title"].map(extract_brand)
    df["visibility_score"] = visibility_score(df["position"])
    df["is_top_10"] = df["position"] <= config.TOP_N_POSITION
    df["price_range"] = _band(df["price"], config.PRICE_BANDS).astype("string")
    df["rating_range"] = _band(df["rating"], config.RATING_BANDS).astype("string")
    discount = ((df["raw_price"] - df["price"]) / df["raw_price"] * 100).clip(lower=0)
    df["discount_amount"] = (df["raw_price"] - df["price"]).clip(lower=0).round(2)
    df["discount_pct"] = discount.round(2)
    df["has_discount"] = df["discount_pct"] > 0
    df["review_engagement"] = pd.qcut(
        df["reviews"].astype(float), q=3, labels=["Low", "Medium", "High"]
    ).astype("string")
    return df
