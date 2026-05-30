from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID, uuid4

from psycopg import Connection


@dataclass(frozen=True)
class ProductSnapshot:
    product_name: str
    brand: str | None
    category: str
    platform: str
    product_url: str
    price: float | None
    original_price: float | None
    discount: float | None
    rating: float | None
    review_count: int | None
    availability: bool
    captured_at: datetime


def ensure_schema(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id UUID PRIMARY KEY,
                product_name VARCHAR NOT NULL,
                brand VARCHAR,
                category VARCHAR,
                platform VARCHAR NOT NULL,
                product_url TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_snapshots (
                snapshot_id UUID PRIMARY KEY,
                product_id UUID NOT NULL REFERENCES products(product_id),
                price FLOAT,
                original_price FLOAT,
                discount FLOAT,
                rating FLOAT,
                review_count INTEGER,
                availability BOOLEAN,
                captured_at TIMESTAMP NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_snapshots_product_captured
            ON product_snapshots (product_id, captured_at);
            """
        )
    conn.commit()


def upsert_product(conn: Connection, snapshot: ProductSnapshot) -> UUID:
    product_id = uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO products (
                product_id,
                product_name,
                brand,
                category,
                platform,
                product_url
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_url) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                brand = EXCLUDED.brand,
                category = EXCLUDED.category,
                platform = EXCLUDED.platform
            RETURNING product_id;
            """,
            (
                str(product_id),
                snapshot.product_name,
                snapshot.brand,
                snapshot.category,
                snapshot.platform,
                snapshot.product_url,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise RuntimeError("Failed to upsert product")

    return UUID(str(row[0]))


def insert_snapshot(conn: Connection, product_id: UUID, snapshot: ProductSnapshot) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO product_snapshots (
                snapshot_id,
                product_id,
                price,
                original_price,
                discount,
                rating,
                review_count,
                availability,
                captured_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                str(uuid4()),
                str(product_id),
                snapshot.price,
                snapshot.original_price,
                snapshot.discount,
                snapshot.rating,
                snapshot.review_count,
                snapshot.availability,
                snapshot.captured_at,
            ),
        )


def save_product_snapshots(conn: Connection, snapshots: Iterable[ProductSnapshot]) -> int:
    count = 0
    ensure_schema(conn)

    for snapshot in snapshots:
        product_id = upsert_product(conn, snapshot)
        insert_snapshot(conn, product_id, snapshot)
        count += 1

    conn.commit()
    return count
