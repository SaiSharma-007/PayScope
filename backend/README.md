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

## Salary Insights API

`GET /api/analytics/salary-insights?insight=pay_distribution&metric=basic&year=2026` returns one view per request. Use the HR session cookie. All views accept `country_code`, `department_id`, `job_title_id`, and `currency_code`. `year` defaults to the current calendar year. Historical years use the current saved package when it was effective by the end of the requested year.

| Insight | Grouping | Metrics and row fields |
| --- | --- | --- |
| `pay_distribution` | Country, department, or job title | `basic` (default), `ctc`, `target_ctc`. Returns `percentiles` and `spread` (maximum minus minimum). |
| `role_bands` | Job title | Same distribution and metrics. |
| `country_comparison` | Country | Same distribution and metrics. Use `p50`, `spread`, and `eligible` for median, spread, and eligible headcount. |
| `compensation_mix` | Country, department, or job title | `guaranteed` (default), `target`, `ctc`, `target_ctc`. Returns total `amount`, `categories`, and `components`. |
| `guaranteed_vs_target_ctc` | Country, department, or job title | `ctc`. Returns `guaranteed_ctc` and `target_ctc` for the same employees. |
| `payroll_concentration`, `headcount_vs_payroll` | Country, department, or job title | `guaranteed` (default), `target`, `ctc`, `target_ctc`. Returns `amount`, `headcount_share`, and `payroll_share`. |
| `equity_timeline` | Calendar year and award kind | Set `start_year` and `year` for an inclusive range of up to 20 years. Defaults to up to five years ending at `year`, with 1900 as the earliest year. Rows use `kind` (`rsu` or `option`), `year`, `amount`, and award counts. |

Grouped responses use `group_by=country` by default where grouping is selectable. Each currency has `population`, `eligible`, `missing`, `group_count`, and `rows`. Group rows repeat the coverage counts for that group and carry a string `group_id` plus `group_name`. Use `limit` (default 12, maximum 25) to bound rows per currency. Payroll results sort by descending cost, followed by group name and ID. Other views sort by group name and ID. Coverage and payroll denominators include every group in the filtered currency. Top-level `employees` counts the filtered workforce and `without_currency` counts employees whose currency could not be determined. Legacy salary rows can supply a currency for coverage. Pay values come from saved packages.

Percentiles use linear interpolation at zero-based index `(eligible - 1) × percentile / 100` over sorted eligible pay. The API rounds at the end to cents, half up. Groups with one eligible employee have five equal percentiles and zero spread. Groups with zero eligible employees have null percentiles and spread. Filters with no known-currency employees return an empty `currencies` array.

Guaranteed amounts include basic pay and guaranteed employer costs and earnings. Target adds included target components. CTC adds the same annual equity cost once per employee and excludes employees with unknown annual equity. Explicit no-equity elections have zero cost. Employee deductions and excluded components stay outside company cost. Mix components carry `category`, `commitment`, `code`, `label`, `amount`, and `component_count`. The 16 highest-cost components retain their codes. Any remainder rolls into a row with `code: null` per category and commitment. The category and component amounts reconcile to the group amount.

Drill from country to department with `?insight=payroll_concentration&country_code=IN&group_by=department`, then to role by adding `department_id` and changing `group_by=job_title`. Shares are decimal-string percentages. For example, a group with 3 of 5 employees and INR 645.01 of INR 710.01 payroll returns this currency entry with `limit=1`.

```json
{
  "currency_code": "INR",
  "group_count": 3,
  "population": 5,
  "eligible": 4,
  "missing": 1,
  "payroll_total": "710.01",
  "rows": [
    {
      "group_id": "1",
      "group_name": "Engineering",
      "population": 3,
      "eligible": 3,
      "missing": 0,
      "amount": "645.01",
      "headcount_share": "60.00",
      "payroll_share": "90.85"
    }
  ]
}
```

Headcount share uses the currency's full filtered population. Payroll share uses the currency's total eligible payroll and is null if the group's payroll is unknown or the denominator is zero. Each currency has its own amounts and denominators.

`?insight=equity_timeline&department_id=1&start_year=2025&year=2026` returns only year/currency/kind combinations with applicable awards. The counts `population`, `eligible`, `missing`, and `recorded_zero` count awards within each row. An amount can be partial when some awards are missing an allocation. For example, one recorded zero and one missing stock-option allocation return this row.

```json
{"year":2025,"kind":"option","population":2,"eligible":1,"missing":1,"recorded_zero":1,"amount":"0.00"}
```

The response envelope includes `revision`, `insight`, `year`, `start_year`, `metric`, `group_by`, `employees`, `without_currency`, and `currencies`. Inapplicable fields are null. Amounts are decimal strings or null. The existing cache header, entry cap, and TTL apply. Normalized filters, view, grouping, and report revision determine cache keys.

### CTC and equity coverage

CTC metrics include `missing_reasons` on each currency and group. The counts add up to that row's `missing` count. Currency counts cover all filtered groups before the group limit. `no_effective_package` means there is no saved package effective by year-end. `equity_unconfigured` means the employee has neither an award nor a no-equity election. `missing_allocation` means at least one applicable award lacks an allocation in the package currency.

For `?insight=guaranteed_vs_target_ctc&country_code=IN&year=2026`, a populated group can return these fields.

```json
{"group_id":"IN","population":5,"eligible":3,"missing":2,"guaranteed_ctc":"520.01","target_ctc":"580.01","missing_reasons":{"no_effective_package":1,"equity_unconfigured":0,"missing_allocation":1}}
```

When nobody in the group is eligible, both totals are null.

```json
{"group_id":"IN","population":5,"eligible":0,"missing":5,"guaranteed_ctc":null,"target_ctc":null,"missing_reasons":{"no_effective_package":1,"equity_unconfigured":4,"missing_allocation":0}}
```

Timeline rows include `coverage_status`. `complete` means every applicable award has a recorded amount. `partial` means the amount sums only the recorded allocations. `missing` means every applicable allocation is missing and `amount` is null. An exact recorded zero is `"0.00"` and counts toward `recorded_zero`. An absent year and award type combination means there were no applicable awards for that currency and filter.

### Populate the fictional demo

On a fresh demo database, apply the migrations and create the seeded workforce and packages with `uv run --locked python -m payscope.seed --compensation apply`. Newly created packages start at the beginning of the default five-year reporting window and include a fictional target bonus. Guaranteed company costs still match the original recorded totals.

Run these commands against the demo environment.

```sh
uv run --locked python -m payscope.seed --equity preview
uv run --locked python -m payscope.seed --equity apply
```

Preview reports the proposed no-equity, award, allocation, and intentionally unconfigured counts. Apply inserts the same cohorts into untouched demo packages with recognized demo rules and skips existing elections, awards, and edited packages. Rerunning apply inserts only newly eligible records. Existing demo packages keep their effective dates and target components. A package first effective in 2026 contributes to the timeline starting in 2026.

For a demo originally seeded with 2026-only packages, use `uv run --locked python -m payscope.seed --demo-history preview` and then `uv run --locked python -m payscope.seed --demo-history apply`. This explicit upgrade makes recognized, untouched legacy demo packages effective from 2022 and adds the fictional target bonus. It backfills earlier years for recognized seeded awards and preserves their recorded 2026 and later allocations. Edited packages and employees with manually created or edited awards are excluded. Guaranteed package costs stay the same.
