# ProductTrend AI Project Plan

## Project Goal

ProductTrend AI is a product trend forecasting platform for e-commerce products. The system collects product data over time, stores historical snapshots, cleans the data, builds features, and later predicts trend scores, demand signals, and emerging products.

## Current Architecture

```text
Flipkart Search Pages
        |
        v
Scrapling Scraper
        |
        v
Neon PostgreSQL
        |
        v
Cleaning Pipeline
        |
        v
Clean Snapshot Table
        |
        v
EDA / Feature Engineering / Trend Scoring
```

## Completed Work

### 1. Project Scaffold

Created the base project structure:

```text
configs/
data/
docs/
models/
notebooks/
src/
tests/
```

Main source areas:

```text
src/scraper/
src/database/
src/processing/
src/feature_engineering/
src/training/
src/inference/
src/api/
```

### 2. Flipkart Scraper

Implemented:

```text
src/scraper/flipkart_scraper.py
```

Current behavior:

- Uses Scrapling fetcher.
- Scrapes Flipkart mobile search pages.
- Uses the filtered Flipkart URL for Apple, Google, Motorola, and Nothing phones.
- Supports pagination.
- Limits scraping to 30 pages by default.
- Extracts product name, price, original price, discount, rating, review count, category, platform, product URL, availability, and captured timestamp.
- Handles Flipkart timeout errors without crashing the whole GitHub workflow.

### 3. Direct Database Storage

Implemented:

```text
src/database/connection.py
src/database/repository.py
```

Current behavior:

- Reads `DATABASE_URL` from `.env` locally.
- Reads `DATABASE_URL` from GitHub Actions secrets in cloud.
- Stores data directly in Neon PostgreSQL.
- Does not write scraped data to JSON.

Database tables:

```text
products
product_snapshots
```

### 4. Root Scraper Runner

Implemented:

```text
scrape_runner.py
```

Run manually:

```bash
python scrape_runner.py --max-pages 30
```

### 5. Scheduler

Implemented:

```text
src/scraper/scheduler.py
```

Local scheduler behavior:

- Runs the scraper every 5 hours.
- Only works while the local PC and Python process are running.

### 6. Free Cloud Scheduling

Implemented GitHub Actions workflow:

```text
.github/workflows/flipkart-scraper.yml
```

Current behavior:

- Can run manually from GitHub Actions.
- Runs automatically on schedule.
- Uses Neon PostgreSQL through GitHub secret `DATABASE_URL`.
- Installs Python dependencies.
- Installs Playwright browser dependencies for Scrapling.
- Runs:

```bash
python scrape_runner.py --max-pages 30
```

Current schedule:

```text
00:00, 05:00, 10:00, 15:00, 20:00 UTC
```

India time:

```text
05:30 AM, 10:30 AM, 03:30 PM, 08:30 PM, 01:30 AM
```

### 7. Neon Data Viewer

Implemented:

```text
view_neon_data.py
```

Run:

```bash
python view_neon_data.py --limit 20
```

Current verified data:

```text
products: 408
product_snapshots: 408
```

### 8. Cleaning Pipeline

Implemented:

```text
clean_runner.py
src/processing/clean.py
```

Created clean table:

```text
clean_product_snapshots
```

Cleaning rules:

```text
rating > 5        -> NULL
rating < 0        -> NULL
price <= 0        -> NULL
discount < 0      -> NULL
discount > 100    -> NULL
review_count < 0  -> NULL
```

Current verified result:

```text
clean_product_snapshots: 408
invalid ratings: 0
```

## Known Issues / Notes

### Flipkart Card Data

Flipkart does not always show rating and review data in every product card. Missing values should remain `NULL` in the clean table and be handled later during EDA or feature engineering.

### GitHub Runner Timeout Risk

Flipkart may timeout or block GitHub cloud IPs. The scraper now avoids crashing, but reliable production scraping may later need:

- Better retry strategy
- Proxy support
- Browser-based fetcher
- Alternative data source or API

### Raw Data Quality

Raw scraped data may contain unstable values because Flipkart page markup changes. The clean pipeline protects downstream EDA and modeling by validating values.

## Immediate Next Moves

### Step 1. Improve Data Validation

Add summary checks for:

- Number of products scraped per run
- Number of missing prices
- Number of missing ratings
- Number of invalid raw ratings
- Number of duplicate snapshots

Output these checks after every scrape and clean run.

### Step 2. Automate Cleaning After Scraping

Update GitHub Actions so every scheduled run does:

```text
scrape_runner.py
clean_runner.py
```

This keeps `clean_product_snapshots` updated automatically.

### Step 3. EDA Notebook

Create:

```text
notebooks/eda.ipynb
```

EDA goals:

- Price distribution
- Discount distribution
- Missing value analysis
- Brand-wise product count
- Brand-wise average price
- Snapshot count over time
- Duplicate product checks

### Step 4. Feature Engineering

Create:

```text
src/feature_engineering/build_features.py
feature_runner.py
```

Feature table:

```text
product_features
```

Initial features:

```text
latest_price
latest_discount
latest_rating
latest_review_count
price_change
discount_change
review_growth
snapshot_count
days_observed
```

### Step 5. Rule-Based Trend Score

Before ML, build a simple trend score:

```text
trend_score = weighted score from review growth, discount movement, rating, price stability, and product freshness
```

Create:

```text
src/feature_engineering/trend_score.py
trend_score_runner.py
```

Output table:

```text
trend_scores
```

### Step 6. API Layer

Create FastAPI app:

```text
src/api/app.py
src/api/routes.py
```

Initial endpoints:

```text
GET /health
GET /products
GET /products/trending
GET /products/{product_id}
GET /brands/summary
```

### Step 7. Dashboard

Build a simple dashboard after API is stable.

Views:

- Top trending products
- Brand comparison
- Price and discount movement
- Product snapshot history
- Missing data report

### Step 8. ML Model

Only start ML after enough historical snapshots exist.

Phase 1 model options:

```text
Random Forest
XGBoost
LightGBM
```

Initial target:

```text
trend_score
```

Later targets:

```text
future_review_count
future_popularity
bestseller_probability
```

### Step 9. Production Hardening

Add:

- Structured logging
- Error alerts
- Scrape run table
- Data quality checks
- Retry policies
- Proxy configuration
- Tests
- Docker setup

## End-to-End Target Flow

```text
GitHub Actions Scheduler
        |
        v
Flipkart Scraper
        |
        v
Raw PostgreSQL Tables
        |
        v
Cleaning Pipeline
        |
        v
Clean Snapshot Table
        |
        v
Feature Engineering
        |
        v
Trend Scores
        |
        v
FastAPI
        |
        v
Dashboard
```

## Current Next Task Recommendation

The next best implementation task is:

```text
Update GitHub Actions to run clean_runner.py after scrape_runner.py.
```

This will make the raw and clean tables update automatically every scheduled run.
