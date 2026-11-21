# Agent experience verification — 2026-11-21

This change keeps two model agents and the five designed workflow stages. It improves execution ownership, transport, saved tracing, and the chat layout; it does not claim TrackForge-equivalent response latency.

## Live checks

The configured demo account asked the same Germany/EUR annual-base-pay question against a temporary backend on loopback port 8001. These are individual sequential observations, not a benchmark distribution. The original user server was left running on port 8000.

| Configuration during verification | Observed result |
| --- | --- |
| Startup ownership renewal, shared cache Redis client, original event writes | Completed with verified writer output in 68.3 s |
| Atomic event writes, shared cache Redis client | Interrupted; sharing cache's 500 ms Redis socket timeout remained a reliability risk |
| Dedicated lease Redis client, atomic event writes, transaction-pooler database connection | Completed with verified writer output in 57.3 s |
| Same implementation, verified session-pooler database connection | Accepted at 8.2 s; first rendered answer segment at 34.1 s; completed at 39.7 s |

The final run's saved history contained 15 non-token activity events, including model telemetry and final verification. The smoke script signs out its own session after a successful check. Test conversations remain in the demo account as verification history.

Read-only connection probes (`SELECT 1` with a fresh session each time) measured transaction-pooler checks at 2.790 / 1.563 / 1.585 s and session-pooler checks at 2.754 / 0.895 / 0.784 s. The local ignored `.env` now uses the tested session-pooler port 5432; credentials and database identity are unchanged. TLS remains required. Serverless deployments should retain their transaction-mode configuration as described in the backend README.

## Checks

- Backend unit suite: 110 passed.
- Frontend suite: 11 passed, 2 optional live-API tests skipped.
- Seven PostgreSQL/Redis integration tests were skipped because disposable test service URLs were not configured. They were not pointed at the demo database.
- ESLint and production build passed.
- Scoped premium static audit of the agent UI passed; this is not a whole-product compliance audit.
- Browser regressions cover continuous POST streaming while adopting the chat ID, reload with five-stage activity, cursor replay and duplicate suppression, Stop, retry, clarification, chat isolation, report navigation, prompt administration, and mobile composer visibility.
- Browser screenshots in `artifacts/verification/agent-chat-*.png` use controlled fixture data, not live performance figures.

## Remaining latency

The connection change and reduced round trips improve latency but the live path still spends substantial time in database operations. The report-options lookup and validation repeat reference reads; admission and tool bookkeeping still use several sequential statements. Co-locating the API and database and profiling these operations are the next performance steps. Do not solve this by removing ownership fencing, authorization, evidence validation, or durable replay.

Run the optional smoke harness from `backend/` with `.venv\Scripts\python.exe ..\artifacts\verification\smoke_agent.py` while an updated backend listens on port 8001. It reads configured demo credentials without logging them and creates one saved test chat. Restart the normal backend to load the code and local connection configuration; these enhancements need no additional schema migration.
