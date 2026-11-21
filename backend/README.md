# PayScope backend

Use [uv](https://docs.astral.sh/uv/) and an empty PostgreSQL database. Run these commands from `backend/`.

1. Run `uv sync --locked`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your database. Set `DEMO_HR_PASSWORD` to a password of at least 12 characters.
3. Run `uv run --locked alembic upgrade head`.
4. Run `uv run --locked python -m payscope.seed`.
5. Run `uv run --locked uvicorn payscope.main:app`. Check `GET /health` at `http://127.0.0.1:8000/health`.

For a Supabase transaction-pooler URL on port `6543`, paste the database password into the URL and percent-encode any URL-reserved characters in it. The backend defaults to TLS for this connection.

For a long-running local or hosted FastAPI process, prefer Supabase's session-pooler connection from the dashboard (port `5432`), which allows this service to reuse its database connections. Keep transaction mode (`6543`, application `NullPool`) for serverless deployments. Use TLS (`?ssl=require`) with either remote endpoint. Connection mode and region materially affect startup and event latency; the model's response time is only one part of a chat run. See [Supabase's SQLAlchemy connection guidance](https://supabase.com/kb/troubleshooting/using-sqlalchemy-with-supabase-FUqebT).

Agent ownership has a separate Redis client with a three-second socket timeout and a five-second overall command deadline; cache reads retain their shorter fallback deadlines. Execution leases last 30 seconds and renewal starts alongside workflow setup. The stream uses one authorized snapshot query and local update notifications. Activity survives history reload and includes model usage, timing, handoffs, tool results, and final verification. No additional migration is required for these event payloads.

Migration `0005` adds reversible chat deletion. Run `uv run --locked alembic upgrade head` before using the updated chat API. `DELETE /api/agent/conversations/{id}` hides an owned conversation and `POST /api/agent/conversations/{id}/restore` implements Undo. Both require CSRF. A queued or running response blocks deletion with 409; unknown or other-owner conversations return 404. Deleted conversations are excluded from history, new admission, and run reads. Durable records are retained for restoration; this is not permanent erasure.

The UI caches recent conversations and drafts in memory for the signed-in session, with deduplicated reads and a 30-second freshness window. Signing out or changing session discards that cache. Verified report cards and Open report reuse the interactive chart controls for measure, sort order, exact values, and separate currencies.

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

The workspace overview uses `GET /api/analytics/workforce-overview` for employee and saved-package coverage by country. `GET /api/analytics/compensation` accepts country, department, job title, currency, grouping, calendar year, and `metric` (`basic`, `guaranteed`, `target`, `equity`, `ctc`, or `target_ctc`). Reports use current packages effective by December 31 and separate currencies. Equity measures and CTC exclude unknown allocations from eligible counts. Their composition uses total guaranteed CTC for the same eligible country and currency population. Employee deductions stay outside employer cost. The annual base-pay report and Ask about pay use saved package basic pay and currency when present, with recorded annual salary as the fallback for employees without a package.

Migration `0003` adds equity awards, annual allocations, and explicit no-equity elections. `GET /api/employees/{employee_id}/equity?year=2026` shows award details and annual CTC. `POST .../equity/awards` creates an RSU or stock option and `PUT .../equity/awards/{award_id}` updates it with `expected_version`. `PUT .../equity/not-applicable` records zero equity for an employee with no awards. Writes require the CSRF header. Grant valuation and the manually entered allocation are separate. Each applicable award needs an allocation in the current package currency for each calendar year from grant through its optional final year. Use explicit zero for a year with no cost. Unconfigured or missing equity leaves CTC incomplete. The original seed does not assign equity.

Run `uv run --locked alembic upgrade head` to add the five compensation tables. This preserves employee identities and original salary rows.

Use `GET/POST /api/compensation/rules`, `GET/PATCH /api/compensation/rules/{rule_id}`, `POST /api/compensation/rules/{rule_id}/versions`, and `GET /api/compensation/versions/{version_id}`. Rule lists are filtered by country, currency, and active status and paginated in pages of 50. Publishing requires `expected_version`; it creates an immutable version and leaves existing employee packages unchanged.

Use `POST /api/compensation/preview` for unsaved rule examples. Employee package endpoints are `GET/PUT /api/employees/{employee_id}/compensation` and `POST /api/employees/{employee_id}/compensation/preview`. Writes and previews require the CSRF header. Save uses `expected_version: 0` for a new package or the last saved version for an update. A conflict returns 409; reload before replacing another save. The backend always recalculates amounts instead of accepting client totals.

Components support `fixed` and `percent_of_base` methods, categories `earning`, `employer_cost`, and `deduction`, and guaranteed/target commitments. Overrides supply code, amount, and a required reason. Employee deductions do not contribute to cost. API amounts are decimal strings. The legacy salary write endpoint returns 409 for employees with packages. Edit their basic pay through Compensation. Migration `0009` advances the current report revision where packages exist so saved reports keep their original figures and can indicate when newer results are available.

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

## Agent prompt catalog and conversation history

Migration `0004` publishes Pay Analyst v1 and Answer Writer v1. The standard demo seed enables prompt management for `hr@payscope.example` and preserves existing prompt versions and account credentials. To grant the permission to another HR account, run this as the database administrator using the account's email address.

```sql
UPDATE app.hr_users
SET manage_agent_prompts = true
WHERE email = 'hr-admin@example.com';
```

The authentication response includes `user.manage_agent_prompts`. The server checks that permission for all catalog endpoints. Prompt mutations also require `X-CSRF-Token`.

| Method and path | Use |
| --- | --- |
| `GET /api/admin/agent-prompts` | List the two agents, their published version, and draft metadata. |
| `GET /api/admin/agent-prompts/{agent_key}` | Load a catalog entry with its draft body, if present. |
| `GET /api/admin/agent-prompts/{agent_key}/versions?limit=20&before_version=3` | Page through published versions, newest first, using `next_before_version`. |
| `GET /api/admin/agent-prompts/{agent_key}/versions/{version}` | Read a published prompt's exact body. |
| `PUT /api/admin/agent-prompts/{agent_key}/draft` | Save an editable draft. |
| `POST /api/admin/agent-prompts/{agent_key}/draft/restore` | Copy the selected published version into the draft. |
| `POST /api/admin/agent-prompts/{agent_key}/publish` | Publish the draft as the next immutable version. |
| `GET /api/agent/conversations?limit=20&offset=0` | List the signed-in user's chats. Use `next_offset` to request another page. |
| `GET /api/agent/conversations/{conversation_id}?limit=20&before_turn=4` | Load an owned chat with its active run and recent turns. Use `next_before_turn` to request older turns. |

The agent keys are `pay_analyst` and `answer_writer`. Save a draft with `{"body":"Updated instructions","change_note":"Clarify ranking","expected_revision":0}`. The response returns the current published version as `active`, the updated `draft`, and a new `edit_revision`. Publish with `{"expected_revision":1}`. To restore v1 after publishing v2, send `{"version":1,"expected_revision":2}` to the restore endpoint, review the draft, and publish using the returned revision. If another admin saved or published first, the response is `409 PROMPT_CHANGED` with `detail.current_revision`. Publishing without a draft returns `409 PROMPT_DRAFT_REQUIRED`.

A prompt detail response after saving a draft contains both the active version and the draft.

```json
{
  "agent_key": "pay_analyst",
  "edit_revision": 1,
  "active": {
    "version": 1,
    "author_id": null,
    "author_name": null,
    "published_by": null,
    "published_at": "2026-11-20T12:00:00Z",
    "change_note": "Initial prompt"
  },
  "draft": {
    "author_id": "b3e4741e-6a33-49a0-bb3d-ce2bf333e692",
    "author_name": "HR Manager",
    "updated_at": "2026-11-20T12:05:00Z",
    "change_note": "Clarify ranking",
    "body": "Updated instructions"
  }
}
```

A conversation detail page has `id`, `title`, creation and update timestamps, nullable `active_run_id`, a `turns` array in chronological order, and nullable `next_before_turn`. A populated turn looks like this.

```json
{
  "run_id": "d31c99d0-0dc6-4f78-9ae3-3e06ff095182",
  "turn_number": 2,
  "kind": "question",
  "parent_run_id": null,
  "status": "queued",
  "messages": [{
    "role": "user",
    "text": "What is median Engineering pay in India?",
    "structured_content": null,
    "is_partial": false,
    "created_at": "2026-11-20T12:00:00Z"
  }]
}
```

### Workflow integration

The write operations in [`payscope.agents.runs`](src/payscope/agents/runs.py) take a fresh async session per operation and commit before returning. Use `admit_run` after authorization and capacity reservation, or replay by the same request key. It returns the run and a flag indicating whether it was newly created. It also saves the initial `accepted` event and both version numbers. Use `pinned_prompts` to load those exact bodies for execution. Handle `CONVERSATION_BUSY` using the active run ID carried by the exception. Conflicting reuse of a request key returns `IDEMPOTENCY_CONFLICT`.

Claim and renew the run with its execution token and a bounded lease. Append events and record tool results with that token. Finalization uses the same run row lock as Stop. An earlier cancellation request wins and retains any committed partial answer and report. Replay returns persisted events in ascending sequence after the cursor.

## Ask about pay runtime

For NVIDIA NIM, set `AGENT_OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1` to select the Chat Completions connector. Set `AGENT_OPENAI_MODEL=nvidia/nemotron-3.5-bolt-e4b` and `AGENT_OPENAI_STRONG_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b`. Use the NVIDIA credential in `AGENT_OPENAI_API_KEY`. Bolt handles the analyst and writer by default. The analyst can escalate once when it returns invalid output or cannot resolve a prior report reference. Both attempts share the run limits, and the `model_escalated` event records the reason and model IDs.

In addition to PostgreSQL, set `REDIS_URL`, `AGENT_OPENAI_API_KEY`, `AGENT_OPENAI_MODEL`, and an explicit positive `AGENT_USER_QUOTA`. `AGENT_GLOBAL_QUOTA` defaults to five. Keep the per-user limit at or below the global limit. Use a model that supports streaming, function calling, and structured outputs over the OpenAI Responses API. The pinned Microsoft Agent Framework packages run on Python 3.14. Deploy the route with at least 60 seconds for execution plus cleanup headroom. Preserve streaming and disable response buffering in any reverse proxy.

The Pay Analyst receives the question, the available report tools, and bounded recent chat context with saved report settings. The Answer Writer receives aggregate report evidence. The backend validates and renders figures directly from that evidence. Requests with over 50 report groups ask HR to narrow the filters. Rankings use every group in the accepted report. The OpenAI Responses connector sets `store=false`.

| Method and path | Behavior |
| --- | --- |
| `POST /api/agent/runs` | Send JSON with a question, a UUID in `Idempotency-Key`, the session cookie, and `X-CSRF-Token`. Optional `conversation_id` adds a turn to an existing chat. A linked turn also sends `kind` and `parent_run_id`. Successful admissions and idempotent replays return SSE. |
| `GET /api/agent/runs/{run_id}/events?after={sequence}` | Replay events after the last seen sequence, then follow live events. The session must own the run. Idle connections receive `: keep-alive` comments. |
| `POST /api/agent/runs/{run_id}/cancel` | With CSRF and the owning session, request Stop. Returns `run_id`, `status`, and `cancel_requested`. Read the terminal outcome from the SSE stream. |

For example, send `{"question":"Which Engineering role in India has the highest median annual base pay in INR?"}`. On a lost creation response, resubmit the same body and idempotency key. To answer a clarification, send the selected currency as `question`, use `"kind":"clarification"`, and link the source run and conversation. A fresh retry sends the original question with a new idempotency key and `"kind":"retry"`, linked to a failed, interrupted, or cancelled run. A busy chat returns `409 CONVERSATION_BUSY` with `detail.run_id`. Capacity or Redis outages return `429` or `503` with `Retry-After`.

Each SSE frame carries `id` equal to the sequence, `event` equal to the type, and one JSON `data` object. Store the last received sequence per run through reconnects. The first accepted frame looks like this.

```text
id: 1
event: accepted
data: {"schema_version":1,"event_id":"9b616ebb-796c-4606-bf11-48fe67655407","run_id":"d31c99d0-0dc6-4f78-9ae3-3e06ff095182","sequence":1,"timestamp":"2026-11-20T12:00:00+00:00","type":"accepted","payload":{"conversation_id":"598fd1c4-0da5-4633-b870-acfaac4a36be"}}

```

| Example stream after `accepted` | Payloads and UI behavior |
| --- | --- |
| `run_started` → `agent_started` → `tool_started` → `tool_completed` → `report_ready` → `agent_completed` → `handoff_started` → `agent_started` → `token` → `agent_completed` → `final` | `tool_started` carries `tool_name` and validated `arguments`. `tool_completed` carries a `status`, bounded `summary`, and `duration_ms`. Both share `call_id`. A request rejected before execution emits `tool_rejected` with a safe code. |
| `token` | Append `{"text":"Engineer — highest median base pay of INR 900000.00."}`. Agent events include `agent_name`. |
| `final` with `status: completed` | Replace the draft with `answer` and use the final `report` card. `answer_source` is `verified_writer` or `computed` for deterministic fallback. An empty report can complete without writer activity. |
| `clarification` → `agent_completed` → `final` with `status: awaiting_clarification` | Example clarification is `{"field":"currency","question":"Which currency should I use?","choices":["INR","USD"]}`. The final payload repeats it under `clarification`; a saved report scope can also appear under `report_request`. |
| `agent_completed` → `error` → `final` with `status: failed` | Example error is `{"code":"MODEL_PROVIDER_FAILED","message":"The model could not complete the request. Try again.","retryable":true}`. The final payload includes the same `error`. |
| `final` with `status: cancelled` or `interrupted` | Example payload is `{"status":"interrupted","answer":null,"is_partial":true}`. Retain any partial answer and report included in the payload. |
| Reconnect with `after=7` | Replay starts at sequence 8 and preserves the original IDs. If sequence 7 was final, the response ends when there is nothing left to replay. |

**Open report** uses `GET /api/analytics/salary-summary` with the card's `filters`. Compare the returned revision with the stored `revision` and keep the chat card available for the original values. A report card looks like this.

```json
{
  "revision": 12,
  "currency_code": "INR",
  "report_type": "annual_gross_base",
  "filters": {"country_code":"IN","department_id":1,"group_by":"job_title","currency_code":"INR"},
  "operation": "highest",
  "metric": "median",
  "ranking_evidence_ids": ["b3e4741e-6a33-49a0-bb3d-ce2bf333e692"],
  "rows": [{
    "evidence_id": "b3e4741e-6a33-49a0-bb3d-ce2bf333e692",
    "group": "4",
    "group_id": 4,
    "group_name": "Engineer",
    "currency_code": "INR",
    "headcount": 9,
    "minimum": "400000.00",
    "maximum": "1200000.00",
    "mean": "835000.00",
    "median": "900000.00"
  }]
}
```

Run `uv run --locked pytest tests/integration/test_agent_streaming.py` with disposable PostgreSQL and Redis URLs. The tests use a streaming provider fixture and include an actual loopback HTTP connection. For a deployed smoke check, sign in and send the example question above with an unbuffered SSE client. Confirm the tool and answer events arrive before the terminal event, record the time to first activity and first answer text, and verify the figures via the report endpoint. [Microsoft Agent Framework OpenAI provider](https://learn.microsoft.com/en-us/agent-framework/agents/providers/openai/)

## Saved reports

Apply migration `0006` with `uv run --locked alembic upgrade head`. `/api/saved-reports` supports POST from `source_run_id`, required title, optional description and chart preferences; GET lists owned reports with `q`, `report_type` and `offset` filters. GET/PATCH/DELETE `/{id}` reads, edits metadata or reversibly deletes a report; POST `/{id}/restore` implements Undo. Mutations require CSRF. Figures are copied from completed persisted evidence, never accepted from the client. One snapshot per user/source run prevents duplicates. Snapshots remain available if the chat is deleted; their source identifiers intentionally do not cascade-delete records. Only metadata and deletion state can change.

The optional `artifacts/verification/smoke_saved_reports.py` harness creates a fixture chat/report, verifies ownership, CSRF, duplicate saves, independent snapshots after chat deletion, metadata edits and Delete/Undo, then leaves its fixture records soft-deleted. It does not modify existing chats or employee data.


Agent observability: migration 0007 adds view_agent_observability (default false). Explicit demo setup grants it to the demo HR account; other users require an intentional permission grant. GET /api/admin/agent-runs supports bounded pagination, status/date/owner/model/prompt/source filters and filtered status/duration totals. Detail, events and tools are read-only, no-store and independently authorized. Soft-deleting a chat preserves observability; user chat APIs continue hiding it. Prompt bodies still require manage_agent_prompts. Restart the API after upgrading.
