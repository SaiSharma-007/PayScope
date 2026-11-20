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

The November 20 compensation report smoke benchmark used the configured PostgreSQL and Redis services with 10,000 saved packages. These timings measure the report service directly from the desktop and include remote connections.

| Concurrent calls | Cache | Samples | Median ms | p95 ms |
| ---: | --- | ---: | ---: | ---: |
| 1 | Cold | 1 | 6,015 | 6,015 |
| 1 | Warm | 5 | 2,103 | 2,511 |
| 5 | Cold | 5 | 5,059 | 5,088 |
| 5 | Warm | 5 | 1,874 | 2,282 |

The tested report occupied 5,986 payload bytes and 6,304 bytes per Redis key including overhead. Production report entries expire after 60 seconds and payloads larger than 16 KiB bypass storage. These small samples measure one report shape. They do not estimate service-wide Redis memory or production latency.

## Salary Insights Plan 1

Measured November 20, 2026 on the configured 10,000-employee PostgreSQL 17 dataset with 10,000 saved packages and no equity awards. The report service ran from the desktop using a read-only PostgreSQL transaction and short-lived, uniquely named Redis keys. Each row shows the median of three cold calls and three immediate repeat calls for the 2026 reporting year. Timings include remote database, savepoint, and Redis round trips. Payload sizes use the compact JSON stored by the report cache.

| View | Cold median | Repeat median | Repeat hits | Payload bytes |
| --- | ---: | ---: | ---: | ---: |
| Pay distribution | 2,409 ms | 1,141 ms | 3/3 | 1,605 |
| Country comparison | 2,384 ms | 1,124 ms | 3/3 | 1,607 |
| Role bands | 2,480 ms | 1,122 ms | 3/3 | 10,851 |
| Compensation mix | 2,652 ms | 1,233 ms | 3/3 | 5,559 |
| Guaranteed vs. target CTC | 2,361 ms | 1,119 ms | 3/3 | 1,196 |
| Payroll concentration by department | 2,310 ms | 1,114 ms | 3/3 | 3,844 |
| Headcount vs. payroll | 2,291 ms | 1,116 ms | 3/3 | 1,501 |
| Equity timeline | 1,970 ms | 1,940 ms | 0/3 | 157 |

The equity timeline returned no award rows, so its repeat calls went to PostgreSQL. The CTC sample primarily measures coverage because the dataset has no recorded awards. Isolated PostgreSQL fixtures exercise populated equity and CTC.

`EXPLAIN (ANALYZE, BUFFERS)` measured server execution at 75 ms for distribution, 169 ms for mix, 42 ms for department payroll, and 34 ms for the empty equity timeline. For the unfiltered workforce, PostgreSQL scanned the employee and package tables and used the existing package-component index for mix.

A separate local PostgreSQL 18 database with 10,000 synthetic packages, 4,999 awards, and 21,425 allocations exercised the populated plans. Over a five-year range, the equity timeline took 112 ms for all employees and 10 ms when filtered by country and department. The paired CTC query took 48 ms. Both used existing allocation indexes, and the filtered timeline used a bitmap scan on employees. The observed plans supported keeping the current indexes.
