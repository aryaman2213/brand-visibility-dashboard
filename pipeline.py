"""End-to-end ETL: extract (API + CSV) -> merge -> clean -> features -> CSV + SQLite.

Usage:
    python pipeline.py                # use cached API responses if present
    python pipeline.py --refresh-api  # call SerpApi again
"""
import argparse
import logging

import config
from src import clean, db, extract, features, load


def run(refresh_api=False):
    api_df = extract.load_api_data(refresh=refresh_api)
    csv_df = load.load_csv()
    merged = load.merge(csv_df, api_df)

    cleaned, report = clean.clean(merged)
    final = features.add_features(cleaned)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    db.to_table(final).to_csv(config.CLEAN_CSV_PATH, index=False)
    report.to_csv(config.PROCESSED_DIR / "cleaning_report.csv", index=False)
    rows = db.write_database(final, merged, report)
    logging.info("Wrote %d rows to %s and %s", rows, config.CLEAN_CSV_PATH.name, config.DB_PATH.name)
    return final, report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh-api", action="store_true", help="fetch fresh SerpApi results")
    run(refresh_api=parser.parse_args().refresh_api)
