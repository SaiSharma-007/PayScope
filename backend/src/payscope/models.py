import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData(schema="app")

hr_users = sa.Table(
    "hr_users",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("email", sa.Text, nullable=False, unique=True),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("manage_agent_prompts", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint(
        "email = lower(btrim(email)) AND email <> ''", name="ck_hr_users_email"
    ),
)

auth_sessions = sa.Table(
    "auth_sessions",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("user_id", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column("token_hash", sa.LargeBinary, nullable=False, unique=True),
    sa.Column("csrf_token_hash", sa.LargeBinary, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
    sa.CheckConstraint("revoked_at >= created_at", name="ck_auth_sessions_revocation"),
    sa.UniqueConstraint("id", "user_id", name="uq_auth_sessions_id_user"),
)

countries = sa.Table(
    "countries",
    metadata,
    sa.Column("code", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.CheckConstraint("code ~ '^[A-Z]{2}$'", name="ck_countries_code"),
)

currencies = sa.Table(
    "currencies",
    metadata,
    sa.Column("code", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("minor_units", sa.SmallInteger, nullable=False),
    sa.CheckConstraint(
        "code IN ('INR', 'USD', 'GBP', 'EUR')", name="ck_currencies_code"
    ),
    sa.CheckConstraint("minor_units = 2", name="ck_currencies_minor_units"),
)

departments = sa.Table(
    "departments",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_departments_name"),
)
sa.Index(
    "uq_departments_normalized_name", sa.func.lower(departments.c.name), unique=True
)

job_titles = sa.Table(
    "job_titles",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_job_titles_name"),
)
sa.Index("uq_job_titles_normalized_name", sa.func.lower(job_titles.c.name), unique=True)

employees = sa.Table(
    "employees",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("employee_code", sa.Text, nullable=False, unique=True),
    sa.Column("full_name", sa.Text, nullable=False),
    sa.Column("country_code", sa.ForeignKey("app.countries.code"), nullable=False),
    sa.Column("department_id", sa.ForeignKey("app.departments.id"), nullable=False),
    sa.Column("job_title_id", sa.ForeignKey("app.job_titles.id"), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)
sa.Index(
    "ix_employees_country_department_title_id",
    employees.c.country_code,
    employees.c.department_id,
    employees.c.job_title_id,
    employees.c.id,
)
sa.Index("ix_employees_department_id", employees.c.department_id, employees.c.id)
sa.Index("ix_employees_job_title_id", employees.c.job_title_id, employees.c.id)

employee_salaries = sa.Table(
    "employee_salaries",
    metadata,
    sa.Column("employee_id", sa.ForeignKey("app.employees.id"), primary_key=True),
    sa.Column("annual_gross_base", sa.Numeric(11, 2), nullable=False),
    sa.Column("currency_code", sa.ForeignKey("app.currencies.code"), nullable=False),
    sa.Column("updated_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint(
        "annual_gross_base BETWEEN 0.01 AND 999999999.99",
        name="ck_employee_salaries_amount",
    ),
)

report_state = sa.Table(
    "report_state",
    metadata,
    sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
    sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("id = 1", name="ck_report_state_singleton"),
    sa.CheckConstraint("revision >= 0", name="ck_report_state_revision"),
)

compensation_rules = sa.Table(
    "compensation_rules",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("country_code", sa.ForeignKey("app.countries.code"), nullable=False),
    sa.Column("currency_code", sa.ForeignKey("app.currencies.code"), nullable=False),
    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("latest_version", sa.Integer, nullable=False),
    sa.Column("created_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("latest_version > 0", name="ck_compensation_rules_version"),
)
sa.Index(
    "ix_compensation_rules_country_currency",
    compensation_rules.c.country_code,
    compensation_rules.c.currency_code,
)

compensation_rule_versions = sa.Table(
    "compensation_rule_versions",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("rule_id", sa.ForeignKey("app.compensation_rules.id"), nullable=False),
    sa.Column("number", sa.Integer, nullable=False),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("created_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint("rule_id", "number", name="uq_compensation_rule_version"),
    sa.CheckConstraint("number > 0", name="ck_compensation_rule_version_number"),
)


def _component_columns():
    return (
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("value", sa.Numeric(13, 4), nullable=False),
        sa.Column("commitment", sa.Text, nullable=False),
        sa.Column("included_in_cost", sa.Boolean, nullable=False),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]{0,49}$' AND code <> 'basic_pay'"),
        sa.CheckConstraint("position BETWEEN 0 AND 31"),
        sa.CheckConstraint("category IN ('earning', 'employer_cost', 'deduction')"),
        sa.CheckConstraint("method IN ('fixed', 'percent_of_base')"),
        sa.CheckConstraint(
            "value >= 0 AND ((method = 'fixed' AND value <= 999999999.99 AND value = round(value, 2)) OR (method = 'percent_of_base' AND value <= 10000))"
        ),
        sa.CheckConstraint("commitment IN ('guaranteed', 'target')"),
        sa.CheckConstraint(
            "category <> 'deduction' OR (NOT included_in_cost AND commitment = 'guaranteed')"
        ),
    )


compensation_rule_components = sa.Table(
    "compensation_rule_components",
    metadata,
    sa.Column("version_id", sa.ForeignKey("app.compensation_rule_versions.id")),
    *_component_columns(),
    sa.PrimaryKeyConstraint("version_id", "code"),
    sa.UniqueConstraint("version_id", "position"),
)

compensation_packages = sa.Table(
    "compensation_packages",
    metadata,
    sa.Column("employee_id", sa.ForeignKey("app.employees.id"), primary_key=True),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("annual_basic_pay", sa.Numeric(11, 2), nullable=False),
    sa.Column("currency_code", sa.ForeignKey("app.currencies.code"), nullable=False),
    sa.Column("effective_date", sa.Date, nullable=False),
    sa.Column("rule_version_id", sa.ForeignKey("app.compensation_rule_versions.id")),
    sa.Column("guaranteed_earnings", sa.Numeric(11, 2), nullable=False),
    sa.Column("guaranteed_employer_costs", sa.Numeric(11, 2), nullable=False),
    sa.Column("employee_deductions", sa.Numeric(11, 2), nullable=False),
    sa.Column("guaranteed_cost", sa.Numeric(11, 2), nullable=False),
    sa.Column("target_cost", sa.Numeric(11, 2), nullable=False),
    sa.Column("updated_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("version > 0", name="ck_compensation_packages_version"),
    sa.CheckConstraint(
        "annual_basic_pay BETWEEN 0.01 AND 999999999.99",
        name="ck_compensation_packages_basic",
    ),
    sa.CheckConstraint(
        "guaranteed_cost >= annual_basic_pay AND target_cost >= guaranteed_cost",
        name="ck_compensation_packages_cost",
    ),
    sa.CheckConstraint(
        "guaranteed_earnings >= annual_basic_pay AND guaranteed_employer_costs >= 0 AND employee_deductions >= 0",
        name="ck_compensation_packages_subtotals",
    ),
)

compensation_package_components = sa.Table(
    "compensation_package_components",
    metadata,
    sa.Column("employee_id", sa.ForeignKey("app.compensation_packages.employee_id")),
    *_component_columns(),
    sa.Column("calculated_amount", sa.Numeric(11, 2), nullable=False),
    sa.Column("amount", sa.Numeric(11, 2), nullable=False),
    sa.Column("override_reason", sa.String(300)),
    sa.PrimaryKeyConstraint("employee_id", "code"),
    sa.UniqueConstraint("employee_id", "position"),
    sa.CheckConstraint(
        "calculated_amount >= 0 AND amount >= 0",
        name="ck_compensation_package_components_amount",
    ),
    sa.CheckConstraint(
        "(override_reason IS NOT NULL AND length(btrim(override_reason)) >= 3) OR (override_reason IS NULL AND amount = calculated_amount)",
        name="ck_compensation_package_components_override",
    ),
)

equity_elections = sa.Table(
    "equity_elections",
    metadata,
    sa.Column(
        "employee_id",
        sa.ForeignKey("app.compensation_packages.employee_id"),
        primary_key=True,
    ),
    sa.Column("updated_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

equity_awards = sa.Table(
    "equity_awards",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column(
        "employee_id",
        sa.ForeignKey("app.compensation_packages.employee_id"),
        nullable=False,
        index=True,
    ),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("units", sa.Numeric(13, 4), nullable=False),
    sa.Column("grant_date", sa.Date, nullable=False),
    sa.Column("grant_currency", sa.ForeignKey("app.currencies.code"), nullable=False),
    sa.Column("exercise_price", sa.Numeric(13, 4)),
    sa.Column("valuation", sa.Numeric(11, 2)),
    sa.Column("valuation_date", sa.Date),
    sa.Column("last_year", sa.SmallInteger),
    sa.Column("vesting", sa.JSON, nullable=False),
    sa.Column("updated_by", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("units > 0 AND version > 0"),
    sa.CheckConstraint(
        "(kind = 'rsu' AND exercise_price IS NULL) OR (kind = 'option' AND exercise_price >= 0 AND exercise_price IS NOT NULL)"
    ),
    sa.CheckConstraint(
        "(valuation IS NULL) = (valuation_date IS NULL) AND valuation >= 0"
    ),
)

equity_allocations = sa.Table(
    "equity_allocations",
    metadata,
    sa.Column("award_id", sa.ForeignKey("app.equity_awards.id"), primary_key=True),
    sa.Column("year", sa.SmallInteger, primary_key=True, index=True),
    sa.Column("currency_code", sa.ForeignKey("app.currencies.code"), nullable=False),
    sa.Column("amount", sa.Numeric(11, 2), nullable=False),
    sa.CheckConstraint("year BETWEEN 1900 AND 9998 AND amount >= 0"),
)

agent_prompt_catalog = sa.Table(
    "agent_prompt_catalog",
    metadata,
    sa.Column("agent_key", sa.Text, primary_key=True),
    sa.Column("active_version", sa.Integer, nullable=False),
    sa.Column("edit_revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("draft_body", sa.Text),
    sa.Column("draft_change_note", sa.Text),
    sa.Column("draft_author_id", sa.ForeignKey("app.hr_users.id")),
    sa.Column("draft_updated_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint(
        "agent_key IN ('pay_analyst', 'answer_writer')", name="ck_agent_prompt_catalog_key"
    ),
    sa.CheckConstraint("edit_revision >= 0", name="ck_agent_prompt_catalog_revision"),
    sa.CheckConstraint(
        "num_nonnulls(draft_body, draft_change_note, draft_author_id, draft_updated_at) = 0"
        " OR (num_nonnulls(draft_body, draft_change_note, draft_author_id, draft_updated_at) = 4"
        " AND length(btrim(draft_body)) > 0 AND length(draft_body) <= 12000"
        " AND length(draft_change_note) <= 500)",
        name="ck_agent_prompt_catalog_draft",
    ),
    sa.ForeignKeyConstraint(
        ["agent_key", "active_version"],
        ["app.agent_prompt_versions.agent_key", "app.agent_prompt_versions.version"],
        name="fk_agent_prompt_catalog_active",
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    ),
)

agent_prompt_versions = sa.Table(
    "agent_prompt_versions",
    metadata,
    sa.Column("agent_key", sa.ForeignKey("app.agent_prompt_catalog.agent_key"), primary_key=True),
    sa.Column("version", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("body", sa.Text, nullable=False),
    sa.Column("change_note", sa.Text, nullable=False),
    sa.Column("author_id", sa.ForeignKey("app.hr_users.id")),
    sa.Column("published_by", sa.ForeignKey("app.hr_users.id")),
    sa.Column(
        "published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.CheckConstraint("version > 0", name="ck_agent_prompt_versions_version"),
    sa.CheckConstraint(
        "length(btrim(body)) > 0 AND length(body) <= 12000 AND length(change_note) <= 500",
        name="ck_agent_prompt_versions_content",
    ),
)

agent_conversations = sa.Table(
    "agent_conversations",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("user_id", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column("title", sa.String(120), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True)),
    sa.Column("next_turn_number", sa.BigInteger, nullable=False, server_default="1"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("id", "user_id", name="uq_agent_conversations_owner"),
    sa.CheckConstraint("next_turn_number > 0", name="ck_agent_conversations_turn"),
)
sa.Index(
    "ix_agent_conversations_user_recent",
    agent_conversations.c.user_id,
    agent_conversations.c.updated_at.desc(),
    agent_conversations.c.id.desc(),
)

AGENT_ACTIVE_STATUSES = ("queued", "running")
AGENT_TERMINAL_STATUSES = (
    "completed", "awaiting_clarification", "unsupported", "failed", "cancelled", "interrupted"
)

agent_runs = sa.Table(
    "agent_runs",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("conversation_id", sa.Uuid, nullable=False),
    sa.Column("user_id", sa.Uuid, nullable=False),
    sa.Column("auth_session_id", sa.Uuid),
    sa.Column("turn_number", sa.BigInteger, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("parent_run_id", sa.Uuid),
    sa.Column("idempotency_key", sa.Uuid, nullable=False),
    sa.Column("request_hash", sa.LargeBinary, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("pay_analyst_key", sa.Text, sa.Computed("'pay_analyst'::text"), nullable=False),
    sa.Column("pay_analyst_version", sa.Integer, nullable=False),
    sa.Column("answer_writer_key", sa.Text, sa.Computed("'answer_writer'::text"), nullable=False),
    sa.Column("answer_writer_version", sa.Integer, nullable=False),
    sa.Column("runtime_fingerprint", sa.Text, nullable=False),
    sa.Column("runtime_limits", JSONB, nullable=False),
    sa.Column("last_event_sequence", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("execution_owner_token", sa.Uuid),
    sa.Column("execution_lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.ForeignKeyConstraint(
        ["conversation_id", "user_id"], ["app.agent_conversations.id", "app.agent_conversations.user_id"],
        name="fk_agent_runs_conversation_owner",
    ),
    sa.ForeignKeyConstraint(
        ["auth_session_id", "user_id"], ["app.auth_sessions.id", "app.auth_sessions.user_id"],
        name="fk_agent_runs_session_owner",
    ),
    sa.ForeignKeyConstraint(
        ["parent_run_id", "conversation_id"], ["app.agent_runs.id", "app.agent_runs.conversation_id"],
        name="fk_agent_runs_parent_conversation",
    ),
    sa.ForeignKeyConstraint(
        ["pay_analyst_key", "pay_analyst_version"],
        ["app.agent_prompt_versions.agent_key", "app.agent_prompt_versions.version"],
        name="fk_agent_runs_analyst_prompt",
    ),
    sa.ForeignKeyConstraint(
        ["answer_writer_key", "answer_writer_version"],
        ["app.agent_prompt_versions.agent_key", "app.agent_prompt_versions.version"],
        name="fk_agent_runs_writer_prompt",
    ),
    sa.UniqueConstraint("id", "conversation_id", name="uq_agent_runs_id_conversation"),
    sa.UniqueConstraint("conversation_id", "turn_number", name="uq_agent_runs_conversation_turn"),
    sa.UniqueConstraint("user_id", "idempotency_key", name="uq_agent_runs_request"),
    sa.CheckConstraint(
        "(kind = 'question' AND parent_run_id IS NULL)"
        " OR (kind IN ('clarification', 'retry') AND parent_run_id IS NOT NULL AND parent_run_id <> id)",
        name="ck_agent_runs_kind",
    ),
    sa.CheckConstraint(
        f"status IN {AGENT_ACTIVE_STATUSES + AGENT_TERMINAL_STATUSES}"
        f" AND (status IN {AGENT_TERMINAL_STATUSES}) = (finished_at IS NOT NULL)",
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
)
sa.Index(
    "uq_agent_runs_active_conversation",
    agent_runs.c.conversation_id,
    unique=True,
    postgresql_where=agent_runs.c.status.in_(AGENT_ACTIVE_STATUSES),
)
sa.Index(
    "ix_agent_runs_execution_expiry",
    agent_runs.c.execution_lease_expires_at,
    postgresql_where=agent_runs.c.status.in_(AGENT_ACTIVE_STATUSES),
)

agent_messages = sa.Table(
    "agent_messages",
    metadata,
    sa.Column("run_id", sa.ForeignKey("app.agent_runs.id"), primary_key=True),
    sa.Column("role", sa.Text, primary_key=True),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("structured_content", JSONB),
    sa.Column("is_partial", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint(
        "role = 'assistant' OR (role = 'user' AND NOT is_partial)", name="ck_agent_messages_role"
    ),
)

agent_tool_calls = sa.Table(
    "agent_tool_calls",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("run_id", sa.ForeignKey("app.agent_runs.id"), nullable=False),
    sa.Column("attempt_number", sa.SmallInteger, nullable=False),
    sa.Column("tool_name", sa.Text, nullable=False),
    sa.Column("arguments", JSONB, nullable=False),
    sa.Column("status", sa.Text, nullable=False, server_default="running"),
    sa.Column("result", JSONB),
    sa.Column("report_revision", sa.BigInteger),
    sa.Column("error_code", sa.Text),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.UniqueConstraint("run_id", "id", name="uq_agent_tool_calls_run_id"),
    sa.UniqueConstraint("run_id", "attempt_number", name="uq_agent_tool_calls_attempt"),
    sa.CheckConstraint(
        "attempt_number > 0 AND tool_name IN ('get_report_options', 'get_salary_summary')",
        name="ck_agent_tool_calls_request",
    ),
    sa.CheckConstraint(
        "status IN ('running', 'completed', 'failed', 'cancelled')"
        " AND (status = 'running') = (finished_at IS NULL)",
        name="ck_agent_tool_calls_status",
    ),
    sa.CheckConstraint("report_revision >= 0", name="ck_agent_tool_calls_revision"),
)

agent_events = sa.Table(
    "agent_events",
    metadata,
    sa.Column("run_id", sa.ForeignKey("app.agent_runs.id"), primary_key=True),
    sa.Column("sequence", sa.BigInteger, primary_key=True, autoincrement=False),
    sa.Column("event_id", sa.Uuid, nullable=False, unique=True),
    sa.Column("schema_version", sa.SmallInteger, nullable=False, server_default="1"),
    sa.Column("event_type", sa.Text, nullable=False),
    sa.Column("agent_name", sa.ForeignKey("app.agent_prompt_catalog.agent_key")),
    sa.Column("call_id", sa.Uuid),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.ForeignKeyConstraint(
        ["run_id", "call_id"], ["app.agent_tool_calls.run_id", "app.agent_tool_calls.id"],
        name="fk_agent_events_tool_call",
    ),
    sa.CheckConstraint("sequence > 0 AND schema_version > 0", name="ck_agent_events_sequence"),
)
sa.Index(
    "uq_agent_events_final",
    agent_events.c.run_id,
    unique=True,
    postgresql_where=agent_events.c.event_type == "final",
)
