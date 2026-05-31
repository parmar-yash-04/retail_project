# Development Workflow Instructions

This document defines the working process for building each feature in this project.

## Core Rule

Every feature should be built in this order:

```text
Understand -> Plan -> Implement -> Validate -> Test -> Commit -> Push -> Explain
```

## Before Building A Feature

### 1. Understand The Goal

Before coding, confirm:

- What problem the feature solves
- Which user or pipeline step needs it
- What input data it needs
- What output it should produce
- Where the output should be stored

Example:

```text
Feature: Cleaning pipeline
Input: product_snapshots
Output: clean_product_snapshots
Purpose: protect EDA and ML from invalid raw scrape values
```

### 2. Read Existing Code First

Check related files before changing anything:

```text
src/scraper/
src/database/
src/processing/
src/feature_engineering/
configs/
requirements.txt
.github/workflows/
```

Use existing patterns instead of creating a completely different style.

### 3. Decide Data Contract

For data features, define:

- Source table
- Destination table
- Required columns
- Nullable columns
- Validation rules
- Duplicate handling

Do not silently overwrite important raw data. Prefer creating clean or derived tables.

### 4. Keep Secrets Out Of Git

Never commit:

```text
.env
DATABASE_URL
API keys
Passwords
Proxy credentials
Cloud credentials
```

Use:

```text
GitHub Actions secrets
local .env
```

## During Feature Implementation

### 1. Make Small Focused Changes

Each feature should have a clear boundary.

Good:

```text
Add cleaning pipeline
```

Avoid mixing:

```text
Cleaning pipeline + dashboard + ML model + unrelated refactor
```

### 2. Prefer Reusable Modules

Put core logic inside `src/`.

Use root runner files only as simple entry points.

Example:

```text
src/processing/clean.py
clean_runner.py
```

### 3. Use Database Tables Intentionally

Current table roles:

```text
products                  product identity
product_snapshots          raw scrape snapshots
clean_product_snapshots    cleaned EDA-ready snapshots
```

Future table roles:

```text
product_features           engineered features
trend_scores               rule-based or model-based scores
scrape_runs                scrape job logs
```

### 4. Do Not Fake Missing Data

If a value is missing from Flipkart, store it as `NULL`.

Good:

```text
rating = NULL
review_count = NULL
```

Bad:

```text
rating = 120186
review_count = 0 guessed without evidence
```

Imputation should happen later during EDA, feature engineering, or modeling.

### 5. Make Scripts CLI-Friendly

Every runner should support useful arguments.

Examples:

```bash
python scrape_runner.py --max-pages 30
python clean_runner.py --limit 10000
python view_neon_data.py --limit 20
```

## After Feature Implementation

### 1. Syntax Check

Run:

```bash
python -m py_compile path/to/file.py
```

For multiple files:

```bash
python -m py_compile scrape_runner.py clean_runner.py src/processing/clean.py
```

### 2. Run A Small Smoke Test

Use a small limit before full execution.

Examples:

```bash
python scrape_runner.py --max-pages 1
python clean_runner.py --limit 50
python view_neon_data.py --limit 10
```

### 3. Verify Database Results

Use SQL checks.

Raw tables:

```sql
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM product_snapshots;
```

Clean table:

```sql
SELECT COUNT(*) FROM clean_product_snapshots;
SELECT COUNT(*) FROM clean_product_snapshots WHERE rating > 5;
```

Latest rows:

```sql
SELECT
    p.product_name,
    s.price,
    s.rating,
    s.review_count,
    s.captured_at
FROM clean_product_snapshots s
JOIN products p ON p.product_id = s.product_id
ORDER BY s.captured_at DESC
LIMIT 20;
```

### 4. Check Git Status

Run:

```bash
git status --short
```

Review changed files before commit.

### 5. Commit With A Clear Message

Use short action-based commit messages.

Examples:

```bash
git commit -m "Add snapshot cleaning pipeline"
git commit -m "Add Neon data viewer"
git commit -m "Handle Flipkart fetch timeouts"
```

### 6. Push To GitHub

Run:

```bash
git push
```

After pushing workflow changes, verify:

```text
GitHub -> Actions -> latest workflow run
```

## Testing Standards By Feature Type

### Scraper Features

Test:

- Imports work
- One page can scrape
- Max page limit works
- Timeout handling works
- Product URL is absolute
- Missing fields become `NULL`
- Database insert works

Useful commands:

```bash
python -m py_compile scrape_runner.py src/scraper/flipkart_scraper.py
python scrape_runner.py --max-pages 1
python view_neon_data.py --limit 10
```

### Database Features

Test:

- Table is created
- Inserts work
- Upserts work
- Foreign keys are valid
- Duplicate URLs do not create duplicate products

Useful SQL:

```sql
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM product_snapshots;
```

### Cleaning Features

Test:

- Invalid values become `NULL`
- Raw table remains unchanged
- Clean table count matches expected raw rows
- Re-running cleaning does not duplicate rows

Useful commands:

```bash
python clean_runner.py --limit 50
```

Useful SQL:

```sql
SELECT COUNT(*) FROM clean_product_snapshots;
SELECT COUNT(*) FROM clean_product_snapshots WHERE rating > 5;
```

### Feature Engineering

Test:

- Features are calculated from clean data only
- Products with insufficient history are handled safely
- No division by zero
- Generated features are explainable

Expected future command:

```bash
python feature_runner.py
```

### API Features

Test:

- App starts successfully
- `/health` returns OK
- Query endpoints return expected fields
- Empty database states do not crash

Expected future commands:

```bash
uvicorn src.api.app:app --reload
```

### GitHub Actions

Test:

- Workflow installs dependencies
- Imports pass
- Secret `DATABASE_URL` exists
- Workflow can run manually
- Scheduled workflow does not fail on scrape timeout

Check:

```text
GitHub -> Actions -> Flipkart Scraper
```

## Git Rules

### Always Ignore

Do not commit:

```text
.env
__pycache__/
*.pyc
.venv/
data/raw/
data/processed/
data/features/
data/predictions/
```

### Safe Commit Checklist

Before every push:

```text
1. Syntax check passed
2. Smoke test passed or limitation explained
3. No secrets in diff
4. git status reviewed
5. Commit message is clear
6. Push completed
```

## Preferred Project Direction

Build this project in stages:

```text
1. Scraping
2. Raw storage
3. Cleaning
4. EDA
5. Feature engineering
6. Rule-based trend score
7. API
8. Dashboard
9. ML model
10. Production hardening
```

Do not jump to ML until there is enough historical data.

## Current Best Next Action

Update GitHub Actions so every scheduled scrape also runs:

```bash
python clean_runner.py
```

That keeps both raw and clean tables current automatically.
