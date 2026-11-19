# Backend Performance Check

Measured on November 19, 2026 with 10,000 seeded employees and one salary each. The client called Uvicorn over loopback HTTP on Windows. PostgreSQL 18.6 ran locally and Redis 8.0.6 ran in WSL with a 30 MB memory limit.

| Workload | HR sessions | Requests | Median ms | p95 ms | HTTP errors | Cache | DB checkout p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Directory | 1 | 50 | 12.73 | 38.05 | 0 | — | 0.01 |
| Salary report | 1 | 50 | 23.07 | 29.00 | 0 | 50 misses | <0.01 |
| Salary report | 1 | 50 | 5.33 | 5.95 | 0 | 50 hits | <0.01 |
| Directory | 5 | 50 | 30.42 | 66.25 | 0 | — | <0.01 |
| Salary report | 5 | 50 | 51.50 | 55.74 | 0 | 50 misses | 0.01 |
| Salary report | 5 | 50 | 17.81 | 20.98 | 0 | 50 hits | <0.01 |

Each concurrent client had its own signed-in session. Directory requests searched by name substring, filtered by country, and fetched 25 rows. Reports used the same five country filters and grouped by job title. The cold run removed only the requested cache keys before each batch. The warm run reused those keys. The PostgreSQL pool was warmed before sampling. DB checkout measures time spent acquiring a pool connection. The p95 uses the nearest rank.

Redis used 829,728 bytes before the timed workloads and peaked at 966,848 bytes. After 50 additional report queries across country, department, and grouping combinations, the 56 benchmark keys occupied 57,792 bytes including key overhead. The measured peak was about 3.2% of the 30 MB limit.

Three read-only checks from the desktop to the configured Redis service measured about 1.0–1.35 seconds for a fresh connection and 332–397 ms for a warm lookup. Cache operations have a 1.5-second deadline and a single attempt.

The local HTTP smoke test covered health, OpenAPI, sign-in, directory, and salary reports. Hosted API verification is pending a deployed endpoint.
