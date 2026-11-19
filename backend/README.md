# PayScope backend

Use [uv](https://docs.astral.sh/uv/) and an empty PostgreSQL database. Run these commands from `backend/`.

1. Run `uv sync --locked`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your database. Set `DEMO_HR_PASSWORD` to a password of at least 12 characters.
3. Run `uv run --locked alembic upgrade head`.
4. Run `uv run --locked python -m payscope.seed`.
5. Run `uv run --locked uvicorn payscope.main:app`. Check `GET /health` at `http://127.0.0.1:8000/health`.

For a Supabase transaction-pooler URL on port `6543`, paste the database password into the URL and percent-encode any URL-reserved characters in it. The backend defaults to TLS for this connection.

The API logs request IDs, route templates, status codes, and elapsed time to stderr. Match a response's `X-Request-ID` header to its log entries. The seed command logs its start and outcome to the same stream.

The seed creates the `hr@payscope.example` account and fills in 10,000 fictional employees with localized names and annual salaries that vary by country and role. Re-running the seed preserves existing employees, salaries, and the account password. The report revision advances only when seeding inserts data used by reports.

## HR API

Use HTTPS for browser sessions. Sign in with JSON at `POST /api/auth/sign-in`. The response sets the session cookie and returns a CSRF token. Hold the token in memory and recover it after a page reload with `GET /api/auth/session`. Send it in `X-CSRF-Token` for `POST /api/auth/sign-out` and salary writes. Sessions expire after eight hours by default, configurable with `SESSION_TTL_SECONDS`.

Use `GET /api/employees` for search, filters, and pagination, `GET /api/employees/{employee_id}` for details, and `GET /api/reference-data` for filter and currency options. Read or replace a salary with `GET` or `PUT /api/employees/{employee_id}/salary`. Send the amount as a decimal string and the currency as its three-letter code. A missing current salary is returned as `null`. The request and response schemas are available at `/docs`.

HR requests distinguish missing or expired sessions (`401`), invalid CSRF tokens (`403`), missing employees (`404`), and field validation errors (`422`).

Use `GET /api/analytics/salary-summary` with optional `country_code`, `department_id`, `job_title_id`, and `group_by` (`country`, `department`, or `job_title`). The response includes the report revision and one row per currency and group. Rows within a currency are ordered by their calculated mean. Monetary fields are decimal strings rounded half-up to two places.

Set `REDIS_URL` to enable the 60-second report cache. The cache stores only aggregates, with a 16 KiB limit per entry. The `X-Report-Cache` response header reports `hit`, `miss`, or `bypass`. Reports use PostgreSQL when Redis is unavailable. See the [10,000-employee performance check](../artifacts/design/backend-performance.md).

Run `uv run --locked pytest` for the tests. Set `TEST_DATABASE_URL` to a separate, empty PostgreSQL database to include database integration tests. Also set `TEST_REDIS_URL` to a disposable Redis instance to exercise cache hits, rollovers, and fallback. The database tests apply and roll back the Alembic migration.
