from __future__ import annotations

import argparse
import logging

from src.scraper.flipkart_scraper import DEFAULT_SEARCH_URL, scrape_and_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Flipkart scraper once and store data in PostgreSQL.")
    parser.add_argument("--url", default=DEFAULT_SEARCH_URL, help="Flipkart search/listing URL to scrape.")
    parser.add_argument("--category", default="mobile", help="Product category stored in the database.")
    parser.add_argument("--max-pages", type=int, default=30, help="Maximum pages to scrape. Default: 30.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between pages in seconds.")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()

    count = scrape_and_store(
        args.url,
        category=args.category,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
    )
    logging.info("Stored %s Flipkart product snapshots", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
