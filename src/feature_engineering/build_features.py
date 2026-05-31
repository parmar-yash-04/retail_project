from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from psycopg import Connection
from psycopg.rows import tuple_row

from src.database.connection import get_connection


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    product_id: str
    price: float | None
    discount: float | None
    rating: float | None
    review_count: int | None
    availability: bool | None
    captured_at: datetime


@dataclass(frozen=True)
class ProductFeatures:
    product_id: str
    latest_price: float | None
    latest_discount: float | None
    latest_rating: float | None
    latest_review_count: int | None
    price_change: float | None
    price_change_pct: float | None
    discount_change: float | None
    review_growth: int | None
    review_growth_pct: float | None
    snapshot_count: int
    days_observed: float
    is_available: bool | None
    first_seen_at: datetime
    last_seen_at: datetime


FETCH_CLEAN_SNAPSHOTS_QUERY = """
SELECT
    product_id,
    price,
    discount,
    rating,
    review_count,
    availability,
    captured_at
FROM clean_product_snapshots
ORDER BY product_id, captured_at ASC;
"""


def ensure_feature_schema(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_features (
                feature_id UUID PRIMARY KEY,
                product_id UUID NOT NULL UNIQUE REFERENCES products(product_id),
                latest_price FLOAT,
                latest_discount FLOAT,
                latest_rating FLOAT,
                latest_review_count INTEGER,
                price_change FLOAT,
                price_change_pct FLOAT,
                discount_change FLOAT,
                review_growth INTEGER,
                review_growth_pct FLOAT,
                snapshot_count INTEGER NOT NULL,
                days_observed FLOAT NOT NULL,
                is_available BOOLEAN,
                first_seen_at TIMESTAMP NOT NULL,
                last_seen_at TIMESTAMP NOT NULL,
                feature_created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_features_last_seen
            ON product_features (last_seen_at);
            """
        )
    conn.commit()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _first_non_null(values: Iterable[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _last_non_null(values: Iterable[Any]) -> Any:
    latest = None
    for value in values:
        if value is not None:
            latest = value
    return latest


def _difference(latest: float | int | None, first: float | int | None) -> float | int | None:
    if latest is None or first is None:
        return None
    return latest - first


def _percent_change(latest: float | int | None, first: float | int | None) -> float | None:
    if latest is None or first is None or first == 0:
        return None
    return round(((latest - first) / first) * 100, 2)


def fetch_clean_snapshots(conn: Connection) -> list[Snapshot]:
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(FETCH_CLEAN_SNAPSHOTS_QUERY)
        rows = cur.fetchall()

    return [
        Snapshot(
            product_id=str(row[0]),
            price=_to_float(row[1]),
            discount=_to_float(row[2]),
            rating=_to_float(row[3]),
            review_count=_to_int(row[4]),
            availability=bool(row[5]) if row[5] is not None else None,
            captured_at=row[6],
        )
        for row in rows
    ]


def build_product_features(snapshots: list[Snapshot]) -> list[ProductFeatures]:
    grouped: dict[str, list[Snapshot]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.product_id].append(snapshot)

    features: list[ProductFeatures] = []
    for product_id, product_snapshots in grouped.items():
        product_snapshots.sort(key=lambda item: item.captured_at)

        prices = [snapshot.price for snapshot in product_snapshots]
        discounts = [snapshot.discount for snapshot in product_snapshots]
        ratings = [snapshot.rating for snapshot in product_snapshots]
        reviews = [snapshot.review_count for snapshot in product_snapshots]
        availability = [snapshot.availability for snapshot in product_snapshots]

        first_price = _first_non_null(prices)
        latest_price = _last_non_null(prices)
        first_discount = _first_non_null(discounts)
        latest_discount = _last_non_null(discounts)
        first_reviews = _first_non_null(reviews)
        latest_reviews = _last_non_null(reviews)

        first_seen_at = product_snapshots[0].captured_at
        last_seen_at = product_snapshots[-1].captured_at
        days_observed = round((last_seen_at - first_seen_at).total_seconds() / 86400, 4)

        features.append(
            ProductFeatures(
                product_id=product_id,
                latest_price=latest_price,
                latest_discount=latest_discount,
                latest_rating=_last_non_null(ratings),
                latest_review_count=latest_reviews,
                price_change=_difference(latest_price, first_price),
                price_change_pct=_percent_change(latest_price, first_price),
                discount_change=_difference(latest_discount, first_discount),
                review_growth=_difference(latest_reviews, first_reviews),
                review_growth_pct=_percent_change(latest_reviews, first_reviews),
                snapshot_count=len(product_snapshots),
                days_observed=days_observed,
                is_available=_last_non_null(availability),
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
            )
        )

    return features


def save_product_features(conn: Connection, features: Iterable[ProductFeatures]) -> int:
    feature_rows = [
        (
            feature.product_id,
            feature.latest_price,
            feature.latest_discount,
            feature.latest_rating,
            feature.latest_review_count,
            feature.price_change,
            feature.price_change_pct,
            feature.discount_change,
            feature.review_growth,
            feature.review_growth_pct,
            feature.snapshot_count,
            feature.days_observed,
            feature.is_available,
            feature.first_seen_at,
            feature.last_seen_at,
        )
        for feature in features
    ]

    if not feature_rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO product_features (
                feature_id,
                product_id,
                latest_price,
                latest_discount,
                latest_rating,
                latest_review_count,
                price_change,
                price_change_pct,
                discount_change,
                review_growth,
                review_growth_pct,
                snapshot_count,
                days_observed,
                is_available,
                first_seen_at,
                last_seen_at
            )
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id) DO UPDATE SET
                latest_price = EXCLUDED.latest_price,
                latest_discount = EXCLUDED.latest_discount,
                latest_rating = EXCLUDED.latest_rating,
                latest_review_count = EXCLUDED.latest_review_count,
                price_change = EXCLUDED.price_change,
                price_change_pct = EXCLUDED.price_change_pct,
                discount_change = EXCLUDED.discount_change,
                review_growth = EXCLUDED.review_growth,
                review_growth_pct = EXCLUDED.review_growth_pct,
                snapshot_count = EXCLUDED.snapshot_count,
                days_observed = EXCLUDED.days_observed,
                is_available = EXCLUDED.is_available,
                first_seen_at = EXCLUDED.first_seen_at,
                last_seen_at = EXCLUDED.last_seen_at,
                feature_created_at = CURRENT_TIMESTAMP;
            """,
            feature_rows,
        )

    conn.commit()
    return len(feature_rows)


def run_feature_build() -> int:
    with get_connection() as conn:
        ensure_feature_schema(conn)
        snapshots = fetch_clean_snapshots(conn)
        features = build_product_features(snapshots)
        return save_product_features(conn, features)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build product features from clean product snapshots.")


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_parser().parse_args(argv)
    started_at = datetime.utcnow()
    count = run_feature_build()
    logger.info("Built %s product feature rows in %s", count, datetime.utcnow() - started_at)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
