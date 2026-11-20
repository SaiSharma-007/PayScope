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

## Compensation rules and packages

The workspace overview uses `GET /api/analytics/workforce-overview` for employee and saved-package coverage by country. `GET /api/analytics/compensation` accepts country, department, job title, currency, grouping, calendar year, and `metric` (`basic`, `guaranteed`, `target`, `equity`, `ctc`, or `target_ctc`). Reports use current packages effective by December 31 and separate currencies. Equity measures and CTC exclude unknown allocations from eligible counts. Their composition uses total guaranteed CTC for the same eligible country and currency population. Employee deductions stay outside employer cost. The legacy salary-summary route remains available.

Migration `0003` adds equity awards, annual allocations, and explicit no-equity elections. `GET /api/employees/{employee_id}/equity?year=2026` shows award details and annual CTC. `POST .../equity/awards` creates an RSU or stock option and `PUT .../equity/awards/{award_id}` updates it with `expected_version`. `PUT .../equity/not-applicable` records zero equity for an employee with no awards. Writes require the CSRF header. Grant valuation and the manually entered allocation are separate. Each applicable award needs an allocation in the current package currency for each calendar year from grant through its optional final year. Use explicit zero for a year with no cost. Unconfigured or missing equity leaves CTC incomplete. The original seed does not assign equity.

Run `uv run --locked alembic upgrade head` to add the five compensation tables. This preserves employee identities and original salary rows.

Use `GET/POST /api/compensation/rules`, `GET/PATCH /api/compensation/rules/{rule_id}`, `POST /api/compensation/rules/{rule_id}/versions`, and `GET /api/compensation/versions/{version_id}`. Rule lists are filtered by country, currency, and active status and paginated in pages of 50. Publishing requires `expected_version`; it creates an immutable version and leaves existing employee packages unchanged.

Use `POST /api/compensation/preview` for unsaved rule examples. Employee package endpoints are `GET/PUT /api/employees/{employee_id}/compensation` and `POST /api/employees/{employee_id}/compensation/preview`. Writes and previews require the CSRF header. Save uses `expected_version: 0` for a new package or the last saved version for an update. A conflict returns 409; reload before replacing another save. The backend always recalculates amounts instead of accepting client totals.

Components support `fixed` and `percent_of_base` methods, categories `earning`, `employer_cost`, and `deduction`, and guaranteed/target commitments. Overrides supply code, amount, and a required reason. Employee deductions do not contribute to cost. API amounts are decimal strings. The old salary write endpoint returns 409 for employees with packages, and the original salary reports remain legacy recorded-amount reports.

Preview the fictional country reframing with `uv run --locked python -m payscope.seed --compensation preview`, then apply with `uv run --locked python -m payscope.seed --compensation apply`. Each original total is preserved exactly, and existing packages are skipped, including HR-edited packages. Employee identities and old salary rows remain intact. Country rates and component names are illustrative demo assumptions. A flexible allowance balances the package to its original total, with an explicit reason. Normal application startup never seeds or recalculates data.

To test against the configured `.env` database without Docker, set `RUN_CONFIGURED_DB_TESTS=1` and run `uv run --locked pytest tests/integration/test_compensation_configured_database.py`. This opt-in test creates temporary fixtures inside one transaction, permits API commits only through savepoints, and rolls back the entire transaction. It checks preservation of the employee count afterward. The existing `TEST_DATABASE_URL` suite is for a separate empty database and must not target the demo database.
