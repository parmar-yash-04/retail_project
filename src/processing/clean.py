from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Iterable
from uuid import UUID

from psycopg import Connection
from psycopg.rows import tuple_row

from src.database.connection import get_connection


logger = logging.getLogger(__name__)


RAW_SNAPSHOTS_QUERY = """
SELECT
    s.snapshot_id,
    s.product_id,
    s.price,
    s.original_price,
    s.discount,
    s.rating,
    s.review_count,
    s.availability,
    s.captured_at
FROM product_snapshots s
ORDER BY s.captured_at DESC
LIMIT %s;
"""


def ensure_clean_schema(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clean_product_snapshots (
                clean_snapshot_id UUID PRIMARY KEY,
                source_snapshot_id UUID NOT NULL UNIQUE REFERENCES product_snapshots(snapshot_id),
                product_id UUID NOT NULL REFERENCES products(product_id),
                price FLOAT,
                original_price FLOAT,
                discount FLOAT,
                rating FLOAT,
                review_count INTEGER,
                availability BOOLEAN,
                captured_at TIMESTAMP NOT NULL,
                cleaned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_clean_snapshots_product_captured
            ON clean_product_snapshots (product_id, captured_at);
            """
        )
    conn.commit()


def clean_price(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return float(value)


def clean_discount(value: float | None) -> float | None:
    if value is None or value < 0 or value > 100:
        return None
    return float(value)


def clean_rating(value: float | None) -> float | None:
    if value is None or value < 0 or value > 5:
        return None
    return float(value)


def clean_review_count(value: int | None) -> int | None:
    if value is None or value < 0:
        return None
    return int(value)


def clean_snapshot_row(row: tuple) -> tuple:
    (
        source_snapshot_id,
        product_id,
        price,
        original_price,
        discount,
        rating,
        review_count,
        availability,
        captured_at,
    ) = row

    clean_price_value = clean_price(price)
    clean_original_price_value = clean_price(original_price)

    if clean_price_value and clean_original_price_value and clean_original_price_value < clean_price_value:
        clean_original_price_value = None

    return (
        str(UUID(str(source_snapshot_id))),
        str(UUID(str(product_id))),
        clean_price_value,
        clean_original_price_value,
        clean_discount(discount),
        clean_rating(rating),
        clean_review_count(review_count),
        bool(availability) if availability is not None else None,
        captured_at,
    )


def fetch_raw_snapshots(conn: Connection, limit: int) -> list[tuple]:
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(RAW_SNAPSHOTS_QUERY, (limit,))
        return cur.fetchall()


def insert_clean_snapshots(conn: Connection, rows: Iterable[tuple]) -> int:
    clean_rows = list(rows)
    if not clean_rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO clean_product_snapshots (
                clean_snapshot_id,
                source_snapshot_id,
                product_id,
                price,
                original_price,
                discount,
                rating,
                review_count,
                availability,
                captured_at
            )
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_snapshot_id) DO UPDATE SET
                price = EXCLUDED.price,
                original_price = EXCLUDED.original_price,
                discount = EXCLUDED.discount,
                rating = EXCLUDED.rating,
                review_count = EXCLUDED.review_count,
                availability = EXCLUDED.availability,
                captured_at = EXCLUDED.captured_at,
                cleaned_at = CURRENT_TIMESTAMP;
            """,
            clean_rows,
        )

    conn.commit()
    return len(clean_rows)


def run_cleaning(limit: int) -> int:
    with get_connection() as conn:
        ensure_clean_schema(conn)
        raw_rows = fetch_raw_snapshots(conn, limit)
        clean_rows = [clean_snapshot_row(row) for row in raw_rows]
        return insert_clean_snapshots(conn, clean_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean raw product snapshots into clean_product_snapshots.")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum raw snapshots to clean.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    started_at = datetime.utcnow()
    count = run_cleaning(args.limit)
    logger.info("Cleaned %s product snapshots in %s", count, datetime.utcnow() - started_at)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
