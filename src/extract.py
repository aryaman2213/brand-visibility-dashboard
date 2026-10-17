"""Extract product listings from Google Shopping via SerpApi.

Raw JSON responses are cached per keyword in data/raw/serpapi/ so re-running the
pipeline does not spend API credits. Pass refresh=True to fetch again.
"""
import json
import logging
import re

import pandas as pd
import requests

import config

log = logging.getLogger(__name__)


def _cache_path(keyword):
    slug = re.sub(r"[^a-z0-9]+", "_", keyword.lower()).strip("_")
    return config.SERPAPI_CACHE_DIR / f"{slug}.json"


def fetch_keyword(keyword, api_key):
    """Call SerpApi for one keyword and return the parsed JSON."""
    params = {**config.SERPAPI_PARAMS, "q": keyword, "api_key": api_key}
    response = requests.get(
        config.SERPAPI_ENDPOINT, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
    )
    # Report errors without the request URL: it contains the API key.
    if response.status_code == 401:
        raise RuntimeError("SerpApi rejected the API key (401). Check SERPAPI_API_KEY in .env.")
    if not response.ok:
        raise RuntimeError(f"SerpApi request for '{keyword}' failed: HTTP {response.status_code}")
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"SerpApi error for '{keyword}': {payload['error']}")
    return payload


def fetch_all(keywords=config.KEYWORDS, refresh=False):
    """Return {keyword: raw_json}, using the cache unless refresh is set."""
    config.SERPAPI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for keyword in keywords:
        path = _cache_path(keyword)
        if path.exists() and not refresh:
            results[keyword] = json.loads(path.read_text())
            continue
        if not config.SERPAPI_KEY:
            log.warning("No SERPAPI_API_KEY set and no cache for '%s'; skipping.", keyword)
            continue
        log.info("Fetching '%s' from SerpApi", keyword)
        payload = fetch_keyword(keyword, config.SERPAPI_KEY)
        path.write_text(json.dumps(payload, indent=2))
        results[keyword] = payload
    return results


def _shopping_items(payload):
    """Organic product results, ranked 1..N.

    categorized_shopping_results (carousels like 'Deals' or 'Under ₹7,000') are
    left out: each carousel restarts its positions at 1, so those ranks are not
    comparable with the main list, and most of their items repeat it anyway.
    """
    return list(payload.get("shopping_results", []))


_PERCENT_OFF = re.compile(r"(\d{1,2})\s*%\s*off", re.IGNORECASE)


def _full_price(item):
    """Selling price. For installment offers ('₹2,499/mo') extracted_price is the
    monthly amount, so the full price is monthly x number of periods."""
    price = item.get("extracted_price")
    installment = item.get("installment") or {}
    if price is not None and installment.get("period"):
        return round(installment.get("extracted_price", price) * installment["period"], 2)
    return price


_CURRENCY_AMOUNT = re.compile(r"[₹$€£]\s*([\d,]+(?:\.\d+)?)")


def _original_price(item, price):
    """Pre-discount price, or None when no discount is shown.

    SerpApi's extracted_old_price is unreliable for strings like '60% off₹990',
    where it returns 60 (the percentage). So the currency amount is read from
    old_price first, then a 'N% off' anywhere is converted back to a price.
    """
    amounts = _CURRENCY_AMOUNT.findall(item.get("old_price") or "")
    if amounts:
        return float(amounts[-1].replace(",", ""))
    extracted = item.get("extracted_old_price")
    if extracted and price and extracted > price:
        return extracted
    texts = [item.get("old_price") or "", item.get("tag") or ""]
    texts += [str(e) for e in item.get("extensions") or []]
    for text in texts:
        match = _PERCENT_OFF.search(text)
        if match and price:
            return round(price / (1 - int(match.group(1)) / 100), 2)
    return None


def flatten(raw_by_keyword):
    """Turn raw responses into one row per product, in the unified column layout."""
    rows = []
    for keyword, payload in raw_by_keyword.items():
        for item in _shopping_items(payload):
            price = _full_price(item)
            rows.append({
                "keyword": keyword,
                "title": item.get("title"),
                "price": price,
                "raw_price": _original_price(item, price),
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
                "platform": item.get("source"),
                "delivery": item.get("delivery"),
                "position": item.get("position"),
                "data_source": "api",
                "product_id": item.get("product_id"),
                "product_link": item.get("product_link"),
            })
    return pd.DataFrame(rows, columns=config.BASE_COLUMNS + ["product_id", "product_link"])


def load_api_data(refresh=False):
    """Fetch (or read cached) API data and save it as a flat CSV."""
    df = flatten(fetch_all(refresh=refresh))
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.API_CSV_PATH, index=False)
    log.info("API rows: %d", len(df))
    return df
