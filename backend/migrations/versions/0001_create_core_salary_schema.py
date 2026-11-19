"""Create core salary schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema("app"))
    op.create_table(
        "countries",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("code ~ '^[A-Z]{2}$'", name="ck_countries_code"),
        sa.PrimaryKeyConstraint("code"),
        schema="app",
    )
    op.create_table(
        "currencies",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("minor_units", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("code IN ('INR', 'USD', 'GBP', 'EUR')", name="ck_currencies_code"),
        sa.CheckConstraint("minor_units = 2", name="ck_currencies_minor_units"),
        sa.PrimaryKeyConstraint("code"),
        schema="app",
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_departments_name"),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_index(
        "uq_departments_normalized_name",
        "departments",
        [sa.literal_column("lower(name)")],
        unique=True,
        schema="app",
    )
    op.create_table(
        "hr_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="ck_hr_users_email"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema="app",
    )
    op.create_table(
        "job_titles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_job_titles_name"),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_index(
        "uq_job_titles_normalized_name",
        "job_titles",
        [sa.literal_column("lower(name)")],
        unique=True,
        schema="app",
    )
    op.create_table(
        "report_state",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_report_state_singleton"),
        sa.CheckConstraint("revision >= 0", name="ck_report_state_revision"),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
        sa.CheckConstraint("revoked_at >= created_at", name="ck_auth_sessions_revocation"),
        sa.ForeignKeyConstraint(["user_id"], ["app.hr_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_auth_sessions_id_user"),
        sa.UniqueConstraint("token_hash"),
        schema="app",
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("employee_code", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.Text(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("job_title_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["country_code"], ["app.countries.code"]),
        sa.ForeignKeyConstraint(["department_id"], ["app.departments.id"]),
        sa.ForeignKeyConstraint(["job_title_id"], ["app.job_titles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_code"),
        schema="app",
    )
    op.create_index(
        "ix_employees_country_department_title_id",
        "employees",
        ["country_code", "department_id", "job_title_id", "id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_employees_department_id",
        "employees",
        ["department_id", "id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_employees_job_title_id", "employees", ["job_title_id", "id"], unique=False, schema="app"
    )
    op.create_table(
        "employee_salaries",
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("annual_gross_base", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "annual_gross_base BETWEEN 0.01 AND 999999999.99", name="ck_employee_salaries_amount"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["app.currencies.code"]),
        sa.ForeignKeyConstraint(["employee_id"], ["app.employees.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["app.hr_users.id"]),
        sa.PrimaryKeyConstraint("employee_id"),
        schema="app",
    )
    op.execute("INSERT INTO app.report_state (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("employee_salaries", schema="app")
    op.drop_table("employees", schema="app")
    op.drop_table("auth_sessions", schema="app")
    op.drop_table("report_state", schema="app")
    op.drop_table("job_titles", schema="app")
    op.drop_table("hr_users", schema="app")
    op.drop_table("departments", schema="app")
    op.drop_table("currencies", schema="app")
    op.drop_table("countries", schema="app")
    op.execute(sa.schema.DropSchema("app"))
