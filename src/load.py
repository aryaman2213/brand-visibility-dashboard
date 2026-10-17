"""Load the provided CSV and merge it with API data into one dataset."""
import logging

import pandas as pd

import config

log = logging.getLogger(__name__)


def load_csv(path=config.DIRTY_CSV_PATH):
    """Read the provided CSV as text so dirty values survive until cleaning.

    The CSV has no search position or original price. Its rows are listed in
    search order within each keyword, so position is the row's order inside its
    keyword (an assumption documented in the README).
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = df.columns.str.strip().str.lower()
    df["position"] = df.groupby("keyword").cumcount() + 1
    df["raw_price"] = pd.NA
    df["data_source"] = "csv"
    log.info("CSV rows: %d", len(df))
    return df[config.BASE_COLUMNS]


def merge(csv_df, api_df):
    """Append API rows to CSV rows; both already share the unified columns."""
    frames = [csv_df.astype(object)]
    if not api_df.empty:
        frames.append(api_df.astype(object))
    merged = pd.concat(frames, ignore_index=True, sort=False)
    log.info("Merged rows: %d (csv=%d, api=%d)", len(merged), len(csv_df), len(api_df))
    return merged
