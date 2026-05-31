from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from typing import Any

from src.database.connection import get_connection


LATEST_PRODUCTS_QUERY = """
SELECT
    p.product_name,
    p.brand,
    p.category,
    p.platform,
    s.price,
    s.original_price,
    s.discount,
    s.rating,
    s.review_count,
    s.availability,
    s.captured_at,
    p.product_url
FROM product_snapshots s
JOIN products p ON p.product_id = s.product_id
ORDER BY s.captured_at DESC
LIMIT %s;
"""


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Decimal):
        return str(float(value))
    return str(value)


def _print_table(headers: list[str], rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        print("No rows found.")
        return

    formatted_rows = [[_format_value(value) for value in row] for row in rows]
    widths = [
        min(
            max(len(headers[index]), *(len(row[index]) for row in formatted_rows)),
            45,
        )
        for index in range(len(headers))
    ]

    def trim(value: str, width: int) -> str:
        return value if len(value) <= width else value[: width - 3] + "..."

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in formatted_rows:
        print(" | ".join(trim(value, widths[index]).ljust(widths[index]) for index, value in enumerate(row)))


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        );
        """,
        (table_name,),
    )
    return bool(cursor.fetchone()[0])


def view_data(limit: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            products_exists = _table_exists(cur, "products")
            snapshots_exists = _table_exists(cur, "product_snapshots")

            if not products_exists or not snapshots_exists:
                print("Required tables are missing in Neon.")
                print("Expected tables: products, product_snapshots")
                return

            cur.execute("SELECT COUNT(*) FROM products;")
            product_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM product_snapshots;")
            snapshot_count = cur.fetchone()[0]

            print(f"Products: {product_count}")
            print(f"Product snapshots: {snapshot_count}")
            print()

            cur.execute(LATEST_PRODUCTS_QUERY, (limit,))
            rows = cur.fetchall()

    headers = [
        "product_name",
        "brand",
        "category",
        "platform",
        "price",
        "original_price",
        "discount",
        "rating",
        "reviews",
        "available",
        "captured_at",
        "url",
    ]
    _print_table(headers, rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View latest product data from Neon PostgreSQL.")
    parser.add_argument("--limit", type=int, default=20, help="Number of latest snapshots to show.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    view_data(args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
