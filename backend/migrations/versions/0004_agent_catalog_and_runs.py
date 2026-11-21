"""Add the versioned agent prompt catalog and durable run storage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

PAY_ANALYST_V1 = """You are PayScope's Pay Analyst. Interpret questions about current annual
gross base pay using read-only aggregate reports. Return a typed report request,
clarification, or unsupported outcome through the application-provided schema.
Call get_report_options to resolve countries, departments, job titles, and currencies
to allowed filter values. Use get_salary_summary with validated filters, at most one
grouping dimension, and a currency when known. Supported metrics are minimum,
median, maximum, average, and salaried headcount. Highest and lowest comparisons
use average or median within one currency. When several currencies match and the
user has not selected one, ask which currency to use. Use only report evidence for
figures, rankings, and empty results. Historical pay, compensation edits, CTC,
and individual employee pay are outside this aggregate workflow.
"""

ANSWER_WRITER_V1 = """You are PayScope's Answer Writer. Explain only the verified aggregate
evidence for this run. Emit structured statements through the application-provided
schema. Each statement identifies its claim and evidence IDs, group, currency,
metric, and statement type. Use value, highest, lowest, tied highest, or tied lowest
only when supported by the supplied evidence. Preserve all tied groups and the
report's currency. Use the supplied group and evidence identifiers exactly. The
application renders amounts and checks rankings. Do not invent figures, infer
missing values, combine currencies, or call tools.
"""


def upgrade() -> None:
    op.add_column(
        "hr_users",
        sa.Column(
            "manage_agent_prompts",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        schema="app",
    )
    op.create_table(
        "agent_prompt_catalog",
        sa.Column("agent_key", sa.Text(), nullable=False),
        sa.Column("active_version", sa.Integer(), nullable=False),
        sa.Column("edit_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("draft_body", sa.Text(), nullable=True),
        sa.Column("draft_change_note", sa.Text(), nullable=True),
        sa.Column("draft_author_id", sa.Uuid(), nullable=True),
        sa.Column("draft_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "agent_key IN ('pay_analyst', 'answer_writer')",
            name="ck_agent_prompt_catalog_key",
        ),
        sa.CheckConstraint(
            "edit_revision >= 0", name="ck_agent_prompt_catalog_revision"
        ),
        sa.CheckConstraint(
            "num_nonnulls(draft_body, draft_change_note, draft_author_id, draft_updated_at) = 0 OR (num_nonnulls(draft_body, draft_change_note, draft_author_id, draft_updated_at) = 4 AND length(btrim(draft_body)) > 0 AND length(draft_body) <= 12000 AND length(draft_change_note) <= 500)",
            name="ck_agent_prompt_catalog_draft",
        ),
        sa.ForeignKeyConstraint(
            ["draft_author_id"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("agent_key"),
        schema="app",
    )
    op.create_table(
        "agent_prompt_versions",
        sa.Column("agent_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(body)) > 0 AND length(body) <= 12000 AND length(change_note) <= 500",
            name="ck_agent_prompt_versions_content",
        ),
        sa.CheckConstraint("version > 0", name="ck_agent_prompt_versions_version"),
        sa.ForeignKeyConstraint(
            ["agent_key"],
            ["app.agent_prompt_catalog.agent_key"],
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["app.hr_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("agent_key", "version"),
        schema="app",
    )
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column(
            "next_turn_number", sa.BigInteger(), server_default="1", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("next_turn_number > 0", name="ck_agent_conversations_turn"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_agent_conversations_owner"),
        schema="app",
    )
    op.create_index(
        "ix_agent_conversations_user_recent",
        "agent_conversations",
        ["user_id", sa.literal_column("updated_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        schema="app",
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("auth_session_id", sa.Uuid(), nullable=True),
        sa.Column("turn_number", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "pay_analyst_key",
            sa.Text(),
            sa.Computed(
                "'pay_analyst'::text",
            ),
            nullable=False,
        ),
        sa.Column("pay_analyst_version", sa.Integer(), nullable=False),
        sa.Column(
            "answer_writer_key",
            sa.Text(),
            sa.Computed(
                "'answer_writer'::text",
            ),
            nullable=False,
        ),
        sa.Column("answer_writer_version", sa.Integer(), nullable=False),
        sa.Column("runtime_fingerprint", sa.Text(), nullable=False),
        sa.Column("runtime_limits", postgresql.JSONB(), nullable=False),
        sa.Column(
            "last_event_sequence", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("execution_owner_token", sa.Uuid(), nullable=True),
        sa.Column(
            "execution_lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(kind = 'question' AND parent_run_id IS NULL) OR (kind IN ('clarification', 'retry') AND parent_run_id IS NOT NULL AND parent_run_id <> id)",
            name="ck_agent_runs_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'awaiting_clarification', 'unsupported', 'failed', 'cancelled', 'interrupted') AND (status IN ('completed', 'awaiting_clarification', 'unsupported', 'failed', 'cancelled', 'interrupted')) = (finished_at IS NOT NULL)",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint(
            "(status IN ('queued', 'running')) = (execution_lease_expires_at IS NOT NULL)"
            " AND (status = 'running') = (execution_owner_token IS NOT NULL)"
            " AND (status <> 'running' OR started_at IS NOT NULL)",
            name="ck_agent_runs_execution",
        ),
        sa.CheckConstraint(
            "turn_number > 0 AND last_event_sequence >= 0 AND octet_length(request_hash) = 32",
            name="ck_agent_runs_counters",
        ),
        sa.ForeignKeyConstraint(
            ["answer_writer_key", "answer_writer_version"],
            [
                "app.agent_prompt_versions.agent_key",
                "app.agent_prompt_versions.version",
            ],
            name="fk_agent_runs_writer_prompt",
        ),
        sa.ForeignKeyConstraint(
            ["auth_session_id", "user_id"],
            ["app.auth_sessions.id", "app.auth_sessions.user_id"],
            name="fk_agent_runs_session_owner",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["app.agent_conversations.id", "app.agent_conversations.user_id"],
            name="fk_agent_runs_conversation_owner",
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id", "conversation_id"],
            ["app.agent_runs.id", "app.agent_runs.conversation_id"],
            name="fk_agent_runs_parent_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["pay_analyst_key", "pay_analyst_version"],
            [
                "app.agent_prompt_versions.agent_key",
                "app.agent_prompt_versions.version",
            ],
            name="fk_agent_runs_analyst_prompt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "turn_number", name="uq_agent_runs_conversation_turn"
        ),
        sa.UniqueConstraint(
            "id", "conversation_id", name="uq_agent_runs_id_conversation"
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_agent_runs_request"),
        schema="app",
    )
    op.create_index(
        "ix_agent_runs_execution_expiry",
        "agent_runs",
        ["execution_lease_expires_at"],
        unique=False,
        schema="app",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "uq_agent_runs_active_conversation",
        "agent_runs",
        ["conversation_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "agent_messages",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("structured_content", postgresql.JSONB(), nullable=True),
        sa.Column(
            "is_partial", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role = 'assistant' OR (role = 'user' AND NOT is_partial)",
            name="ck_agent_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.agent_runs.id"],
        ),
        sa.PrimaryKeyConstraint("run_id", "role"),
        schema="app",
    )
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("arguments", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("report_revision", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_number > 0 AND tool_name IN ('get_report_options', 'get_salary_summary')",
            name="ck_agent_tool_calls_request",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled') AND (status = 'running') = (finished_at IS NULL)",
            name="ck_agent_tool_calls_status",
        ),
        sa.CheckConstraint("report_revision >= 0", name="ck_agent_tool_calls_revision"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.agent_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "attempt_number", name="uq_agent_tool_calls_attempt"
        ),
        sa.UniqueConstraint("run_id", "id", name="uq_agent_tool_calls_run_id"),
        schema="app",
    )
    op.create_table(
        "agent_events",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "schema_version", sa.SmallInteger(), server_default="1", nullable=False
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=True),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence > 0 AND schema_version > 0", name="ck_agent_events_sequence"
        ),
        sa.ForeignKeyConstraint(
            ["agent_name"],
            ["app.agent_prompt_catalog.agent_key"],
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "call_id"],
            ["app.agent_tool_calls.run_id", "app.agent_tool_calls.id"],
            name="fk_agent_events_tool_call",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.agent_runs.id"],
        ),
        sa.PrimaryKeyConstraint("run_id", "sequence"),
        sa.UniqueConstraint("event_id"),
        schema="app",
    )
    op.create_index(
        "uq_agent_events_final",
        "agent_events",
        ["run_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("event_type = 'final'"),
    )
    op.create_foreign_key(
        "fk_agent_prompt_catalog_active",
        "agent_prompt_catalog",
        "agent_prompt_versions",
        ["agent_key", "active_version"],
        ["agent_key", "version"],
        source_schema="app",
        referent_schema="app",
        initially="DEFERRED",
        deferrable=True,
    )

    catalog = sa.table(
        "agent_prompt_catalog",
        sa.column("agent_key", sa.Text()),
        sa.column("active_version", sa.Integer()),
        schema="app",
    )
    versions = sa.table(
        "agent_prompt_versions",
        sa.column("agent_key", sa.Text()),
        sa.column("version", sa.Integer()),
        sa.column("body", sa.Text()),
        sa.column("change_note", sa.Text()),
        schema="app",
    )
    prompts = {"pay_analyst": PAY_ANALYST_V1, "answer_writer": ANSWER_WRITER_V1}
    op.bulk_insert(
        catalog, [{"agent_key": key, "active_version": 1} for key in prompts]
    )
    op.bulk_insert(
        versions,
        [
            {
                "agent_key": key,
                "version": 1,
                "body": body,
                "change_note": "Initial prompt",
            }
            for key, body in prompts.items()
        ],
    )
    op.execute("""
        CREATE FUNCTION app.reject_agent_prompt_version_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Published agent prompt versions are immutable' USING ERRCODE = '23514';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER agent_prompt_versions_immutable
        BEFORE UPDATE OR DELETE ON app.agent_prompt_versions
        FOR EACH ROW EXECUTE FUNCTION app.reject_agent_prompt_version_change();
    """)


def downgrade() -> None:
    op.drop_table("agent_events", schema="app")
    op.drop_table("agent_tool_calls", schema="app")
    op.drop_table("agent_messages", schema="app")
    op.drop_table("agent_runs", schema="app")
    op.drop_table("agent_conversations", schema="app")
    op.drop_constraint(
        "fk_agent_prompt_catalog_active",
        "agent_prompt_catalog",
        schema="app",
        type_="foreignkey",
    )
    op.drop_table("agent_prompt_versions", schema="app")
    op.execute("DROP FUNCTION app.reject_agent_prompt_version_change()")
    op.drop_table("agent_prompt_catalog", schema="app")
    op.drop_column("hr_users", "manage_agent_prompts", schema="app")
