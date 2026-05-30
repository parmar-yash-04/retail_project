from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
import yaml
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_database_config() -> dict[str, Any]:
    config_path = ROOT_DIR / "configs" / "database.yaml"
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def get_database_url() -> str:
    load_dotenv(ROOT_DIR / ".env")

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    config = _load_database_config()
    database_url = config.get("database_url")
    if database_url:
        return str(database_url)

    host = os.getenv("POSTGRES_HOST", config.get("host", "localhost"))
    port = os.getenv("POSTGRES_PORT", config.get("port", 5432))
    database = os.getenv("POSTGRES_DB", config.get("database", "producttrend"))
    user = os.getenv("POSTGRES_USER", config.get("user", "postgres"))
    password = os.getenv("POSTGRES_PASSWORD", config.get("password", "postgres"))

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_connection() -> psycopg.Connection:
    return psycopg.connect(get_database_url())
