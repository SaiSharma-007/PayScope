"""Add versioned compensation rules and employee packages."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compensation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.Text(), nullable=False),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latest_version > 0", name="ck_compensation_rules_version"),
        sa.ForeignKeyConstraint(
            ["country_code"],
            ["app.countries.code"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app.hr_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["currency_code"],
            ["app.currencies.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_index(
        "ix_compensation_rules_country_currency",
        "compensation_rules",
        ["country_code", "currency_code"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "compensation_rule_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("number > 0", name="ck_compensation_rule_version_number"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app.hr_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["app.compensation_rules.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "number", name="uq_compensation_rule_version"),
        schema="app",
    )
    op.create_table(
        "compensation_packages",
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "annual_basic_pay", sa.Numeric(precision=11, scale=2), nullable=False
        ),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("rule_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "guaranteed_earnings", sa.Numeric(precision=11, scale=2), nullable=False
        ),
        sa.Column(
            "guaranteed_employer_costs",
            sa.Numeric(precision=11, scale=2),
            nullable=False,
        ),
        sa.Column(
            "employee_deductions", sa.Numeric(precision=11, scale=2), nullable=False
        ),
        sa.Column("guaranteed_cost", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("target_cost", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.CheckConstraint("version > 0", name="ck_compensation_packages_version"),
        sa.ForeignKeyConstraint(
            ["currency_code"],
            ["app.currencies.code"],
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["app.employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["app.compensation_rule_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("employee_id"),
        schema="app",
    )
    op.create_table(
        "compensation_rule_components",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(precision=13, scale=4), nullable=False),
        sa.Column("commitment", sa.Text(), nullable=False),
        sa.Column("included_in_cost", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "category <> 'deduction' OR (NOT included_in_cost AND commitment = 'guaranteed')"
        ),
        sa.CheckConstraint("category IN ('earning', 'employer_cost', 'deduction')"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]{0,49}$' AND code <> 'basic_pay'"),
        sa.CheckConstraint("commitment IN ('guaranteed', 'target')"),
        sa.CheckConstraint("method IN ('fixed', 'percent_of_base')"),
        sa.CheckConstraint(
            "value >= 0 AND ((method = 'fixed' AND value <= 999999999.99 AND value = round(value, 2)) OR (method = 'percent_of_base' AND value <= 10000))"
        ),
        sa.CheckConstraint("position BETWEEN 0 AND 31"),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["app.compensation_rule_versions.id"],
        ),
        sa.PrimaryKeyConstraint("version_id", "code"),
        sa.UniqueConstraint("version_id", "position"),
        schema="app",
    )
    op.create_table(
        "compensation_package_components",
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(precision=13, scale=4), nullable=False),
        sa.Column("commitment", sa.Text(), nullable=False),
        sa.Column("included_in_cost", sa.Boolean(), nullable=False),
        sa.Column(
            "calculated_amount", sa.Numeric(precision=11, scale=2), nullable=False
        ),
        sa.Column("amount", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.Column("override_reason", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "category <> 'deduction' OR (NOT included_in_cost AND commitment = 'guaranteed')"
        ),
        sa.CheckConstraint("category IN ('earning', 'employer_cost', 'deduction')"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]{0,49}$' AND code <> 'basic_pay'"),
        sa.CheckConstraint("commitment IN ('guaranteed', 'target')"),
        sa.CheckConstraint("method IN ('fixed', 'percent_of_base')"),
        sa.CheckConstraint(
            "value >= 0 AND ((method = 'fixed' AND value <= 999999999.99 AND value = round(value, 2)) OR (method = 'percent_of_base' AND value <= 10000))"
        ),
        sa.CheckConstraint(
            "(override_reason IS NOT NULL AND length(btrim(override_reason)) >= 3) OR (override_reason IS NULL AND amount = calculated_amount)",
            name="ck_compensation_package_components_override",
        ),
        sa.CheckConstraint(
            "calculated_amount >= 0 AND amount >= 0",
            name="ck_compensation_package_components_amount",
        ),
        sa.CheckConstraint("position BETWEEN 0 AND 31"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["app.compensation_packages.employee_id"],
        ),
        sa.PrimaryKeyConstraint("employee_id", "code"),
        sa.UniqueConstraint("employee_id", "position"),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("compensation_package_components", schema="app")
    op.drop_table("compensation_rule_components", schema="app")
    op.drop_table("compensation_packages", schema="app")
    op.drop_table("compensation_rule_versions", schema="app")
    op.drop_table("compensation_rules", schema="app")
