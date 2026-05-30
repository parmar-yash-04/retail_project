from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from time import sleep
from typing import Iterable
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

from src.database.connection import get_connection
from src.database.repository import ProductSnapshot, save_product_snapshots


FLIPKART_BASE_URL = "https://www.flipkart.com"
DEFAULT_SEARCH_URL = (
    "https://www.flipkart.com/search?"
    "q=mobiles&as=on&as-show=on&otracker=AS_Query_TrendingAutoSuggest_2_0_na_na_na"
    "&otracker1=AS_Query_TrendingAutoSuggest_2_0_na_na_na&as-pos=2&as-type=TRENDING"
    "&suggestionId=mobiles&requestId=3789ba92-fcb5-431c-82fd-61387a59feff&as-backfill=on"
    "&p%5B%5D=facets.brand%255B%255D%3DApple"
    "&p%5B%5D=facets.brand%255B%255D%3DGoogle"
    "&p%5B%5D=facets.brand%255B%255D%3DMOTOROLA"
    "&p%5B%5D=facets.brand%255B%255D%3DNothing"
)

PRODUCT_CARD_SELECTOR = "div.jIjQ8S"
PRODUCT_NAME_SELECTOR = ".RG5Slk::text"
PRICE_SELECTOR = ".hZ3P6w.DeU9vF::text"
ORIGINAL_PRICE_SELECTOR = ".kRYCnD.gxR4EY::text"
RATING_SELECTOR = ".PvbNMB span span:nth-child(1)::text"
REVIEW_SELECTOR = ".PvbNMB span span:nth-child(3)::text"
PRODUCT_URL_SELECTOR = "a::attr(href)"
NEXT_PAGE_SELECTOR = "nav.iu0OAI a.jgg0SZ::attr(href)"
FETCH_TIMEOUT_SECONDS = 90
FETCH_RETRIES = 2
FETCH_RETRY_DELAY_SECONDS = 5

logger = logging.getLogger(__name__)


def _first_text(node, selector: str) -> str | None:
    values = node.css(selector)
    if not values:
        return None

    value = values[0]
    text = getattr(value, "text", None)
    if text is None:
        text = str(value)

    text = str(text).strip()
    return text or None


def _parse_money(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = re.sub(r"[^\d.]", "", value)
    return float(cleaned) if cleaned else None


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None

    cleaned = re.sub(r"[^\d]", "", value)
    return int(cleaned) if cleaned else None


def _calculate_discount(price: float | None, original_price: float | None) -> float | None:
    if not price or not original_price or original_price <= 0:
        return None

    return round(((original_price - price) / original_price) * 100, 2)


def _extract_brand(product_name: str) -> str | None:
    first_word = product_name.split(maxsplit=1)[0].strip()
    return first_word.upper() if first_word else None


def _absolute_url(href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(FLIPKART_BASE_URL, href)


def _extract_product(card, *, captured_at: datetime, category: str) -> ProductSnapshot | None:
    product_name = _first_text(card, PRODUCT_NAME_SELECTOR)
    product_url = _absolute_url(_first_text(card, PRODUCT_URL_SELECTOR))

    if not product_name or not product_url:
        return None

    price = _parse_money(_first_text(card, PRICE_SELECTOR))
    original_price = _parse_money(_first_text(card, ORIGINAL_PRICE_SELECTOR))
    rating = _parse_float(_first_text(card, RATING_SELECTOR))
    review_count = _parse_int(_first_text(card, REVIEW_SELECTOR))

    return ProductSnapshot(
        product_name=product_name,
        brand=_extract_brand(product_name),
        category=category,
        platform="flipkart",
        product_url=product_url,
        price=price,
        original_price=original_price,
        discount=_calculate_discount(price, original_price),
        rating=rating,
        review_count=review_count,
        availability=True,
        captured_at=captured_at,
    )


def _next_page_url(page) -> str | None:
    next_url = _first_text(page, NEXT_PAGE_SELECTOR)
    return _absolute_url(next_url)


def _fetch_page(url: str):
    try:
        return Fetcher.get(
            url,
            stealthy_headers=True,
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            retries=FETCH_RETRIES,
            retry_delay=FETCH_RETRY_DELAY_SECONDS,
        )
    except Exception as exc:
        logger.error("Failed to fetch Flipkart page: %s", url)
        logger.error("Fetch error: %s", exc)
        return None


def scrape_flipkart_products(
    start_url: str = DEFAULT_SEARCH_URL,
    *,
    category: str = "mobile",
    max_pages: int | None = None,
    delay_seconds: float = 2.0,
) -> list[ProductSnapshot]:
    scraped: list[ProductSnapshot] = []
    current_url: str | None = start_url
    page_number = 1

    while current_url:
        if max_pages is not None and page_number > max_pages:
            break

        logger.info("Scraping Flipkart page %s: %s", page_number, current_url)
        page = _fetch_page(current_url)
        if page is None:
            logger.warning("Stopping scrape because page %s could not be fetched", page_number)
            break

        captured_at = datetime.utcnow()

        page_products = [
            product
            for product in (
                _extract_product(card, captured_at=captured_at, category=category)
                for card in page.css(PRODUCT_CARD_SELECTOR)
            )
            if product is not None
        ]

        logger.info("Found %s products on page %s", len(page_products), page_number)
        scraped.extend(page_products)

        next_url = _next_page_url(page)
        if not next_url or next_url == current_url:
            break

        current_url = next_url
        page_number += 1
        sleep(delay_seconds)

    return scraped


def scrape_and_store(
    start_url: str = DEFAULT_SEARCH_URL,
    *,
    category: str = "mobile",
    max_pages: int | None = None,
    delay_seconds: float = 2.0,
) -> int:
    products = scrape_flipkart_products(
        start_url,
        category=category,
        max_pages=max_pages,
        delay_seconds=delay_seconds,
    )

    if not products:
        logger.warning("No Flipkart products scraped; skipping database insert")
        return 0

    with get_connection() as conn:
        return save_product_snapshots(conn, products)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Flipkart products and store them in PostgreSQL.")
    parser.add_argument("--url", default=DEFAULT_SEARCH_URL, help="Flipkart search/listing URL to scrape.")
    parser.add_argument("--category", default="mobile", help="Product category value stored in the DB.")
    parser.add_argument("--max-pages", type=int, default=30, help="Maximum pages to scrape. Default: 30.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between pages in seconds.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    count = scrape_and_store(
        args.url,
        category=args.category,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
    )
    logger.info("Stored %s Flipkart product snapshots", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
