from __future__ import annotations

import argparse
import logging
from time import sleep
from typing import Iterable

import schedule

from src.scraper.flipkart_scraper import DEFAULT_SEARCH_URL, scrape_and_store


logger = logging.getLogger(__name__)


def run_scrape_job(url: str, category: str, max_pages: int | None, delay_seconds: float) -> None:
    try:
        count = scrape_and_store(
            url,
            category=category,
            max_pages=max_pages,
            delay_seconds=delay_seconds,
        )
        logger.info("Scheduler stored %s Flipkart product snapshots", count)
    except Exception:
        logger.exception("Flipkart scraper job failed")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Flipkart scraper every 5 hours.")
    parser.add_argument("--url", default=DEFAULT_SEARCH_URL, help="Flipkart search/listing URL to scrape.")
    parser.add_argument("--category", default="mobile", help="Product category value stored in the DB.")
    parser.add_argument("--max-pages", type=int, default=30, help="Maximum pages per run. Default: 30.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between pages in seconds.")
    parser.add_argument("--run-now", action="store_true", help="Run once immediately before scheduling.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)

    if args.run_now:
        run_scrape_job(args.url, args.category, args.max_pages, args.delay)

    schedule.every(5).hours.do(
        run_scrape_job,
        url=args.url,
        category=args.category,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
    )

    logger.info("Flipkart scraper scheduled every 5 hours")
    while True:
        schedule.run_pending()
        sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
