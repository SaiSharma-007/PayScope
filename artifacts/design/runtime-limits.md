# Agent Runtime Limits

## Capacity policy

Capacity is shared across application instances. The pool counts active agent runs, and separate conversations can execute concurrently. Admission checks authenticated ownership, the conversation's active run, the user's quota, and the shared pool.

| Limit | Proposed value | Enforcement |
| --- | --- | --- |
| Active turns per conversation | 1 | PostgreSQL partial unique index for queued and running states |
| Global active agent runs | 5 initially, configurable | Shared atomic capacity reservation |
| Concurrent runs per user | Configurable, numeric value pending approval | Shared per-user reservation using authenticated user ID |
| Total execution time | 60 seconds per run | Orchestrator deadline covering all agents and tools |
| First model update | 15 seconds per model invocation | Provider-stream deadline |
| Tool execution time | 10 seconds per attempt | Tool timeout |
| Model invocations | At most 4 per run | Shared counter across both agents |
| Tool attempts | At most 3 per run, including rejected attempts | Orchestrator tool counter |
| Successful salary summaries | At most 1 per run | Reporting tool budget |
| Combined model output | 2,000 tokens per run | Remaining output budget passed to each model invocation |
| Question length | 2,000 characters | Request validation before model execution |

The per-user quota is a required deployment setting and must be a positive integer no greater than global capacity. Admission checks use the same quota across all sessions for that account. A shared demo HR account therefore shares one quota across its browser sessions. Independent accounts receive separate quotas.

Replayed events and repeated idempotent creation requests reuse the existing run. They consume that run's existing reservation. A resumed workflow receives a new run ID, checks admission again, and inherits its source checkpoint's remaining model, tool, and output budgets. Its wall-clock deadline starts for the new execution attempt.

## Admission responses

| Condition | HTTP status | Error code | User-facing message |
| --- | --- | --- | --- |
| Conversation already has an active run | 409 | `CONVERSATION_BUSY` | This chat already has a running request. |
| User concurrent-run quota reached | 429 | `USER_CONCURRENCY_LIMIT` | You have reached your concurrent request limit. |
| Global agent pool full | 503 | `AGENT_POOL_BUSY` | Agent capacity is busy. Please try again shortly. |
| Shared admission store unavailable | 503 | `AGENT_ADMISSION_UNAVAILABLE` | Agent requests are temporarily unavailable. Please try again shortly. |

429 and 503 responses include a `Retry-After` header and an explicit retry action in the UI. The retry delay is a hint, with admission rechecked on the next request. A 409 response identifies the owned active run so HR can inspect it. Rejections occur before model execution and are returned as ordinary JSON responses.

The same idempotency key with a different request body receives an idempotency conflict. A request with an invalid or expired session receives the normal authentication response before capacity is checked.

## Shared reservations

Redis holds short-lived capacity leases keyed by run and owner identity. An atomic reservation checks both the user's limit and the global pool, using a consistent shared key scope. The reservation also verifies request identity so concurrent copies of the same admission can converge on the same logical run. PostgreSQL persists the run and its idempotency key.

The admission flow first returns an existing idempotent run or identifies an active conversation, then reserves capacity. The database transaction rechecks ownership, request identity, and conversation ordering before committing the run and user message. A reservation is released when admission fails or resolves to an already accepted run. Model execution starts after the durable run has been admitted and its execution owner has been claimed.

Each executing run renews its own lease and releases it after completion, failure, cancellation, or interruption. Renewal and release compare the lease owner token. A lease expires after an instance fails, and its duration includes renewal and cleanup headroom. If renewal fails, the owner stops work before its known lease deadline. The configured execution and cleanup deadlines fit within the deployment's invocation duration.

PostgreSQL stores the run's `execution_owner_token` and `execution_lease_expires_at`. Event, checkpoint, and finalization writes check the current owner token and lease deadline. A stale owner cannot finalize a run after it has been marked interrupted or superseded. A conditional claim gives one invocation ownership of execution.

Expired-run reconciliation targets only runs whose execution lease has expired. It marks those runs interrupted, persists their partial output and terminal event, and makes compatible checkpoints available for explicit Resume. Reconciliation can run during admission and periodic maintenance. Shared ownership makes recovery independent of any particular application's startup.

Redis coordinates capacity, while PostgreSQL retains the durable run history. During an admission-store outage, new agent execution receives the unavailable response. Manual salary reports retain the existing PostgreSQL fallback.

## Streaming lifecycle

The request that starts execution stays active while it runs and streams events. Its first SSE event acknowledges the durable run ID. Agent execution and provider stream cleanup are tied to that invocation's managed lifecycle. A client disconnect is handled within the available execution duration, and persisted checkpoints support recovery if the invocation ends.

An authenticated events endpoint can replay saved events and follow a run owned by another instance. Cancellation writes a durable request to the owned run; the executing invocation observes it and cancels its local task and provider stream. Both streaming and Stop use shared run state, so a request can be served by any instance.

## Acceptance checks

- Fill the shared pool from multiple application instances and verify the next admission receives `AGENT_POOL_BUSY`.
- Fill one user's quota while global slots remain and verify a different user can start a run while the first user receives 429.
- Submit twice to one active conversation and verify the second request identifies its existing run.
- Repeat an idempotent creation request during capacity exhaustion and verify it returns the original run without another model execution.
- Verify lease renewal, expiration after process loss, owner-checked release, and rejection of writes from a stale owner.
- Cancel through an instance that does not own execution and verify its owner observes cancellation and releases capacity.
- Confirm that requests exceeding time, tool, model, and output budgets finish with a clear recorded outcome and provider-stream cleanup.

[Agent streaming design](agent-streaming-design.md) · [Database schema](database-schema.md)
