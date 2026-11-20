"""Add manual equity awards and annual allocations."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equity_awards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("units", sa.Numeric(precision=13, scale=4), nullable=False),
        sa.Column("grant_date", sa.Date(), nullable=False),
        sa.Column("grant_currency", sa.Text(), nullable=False),
        sa.Column("exercise_price", sa.Numeric(precision=13, scale=4), nullable=True),
        sa.Column("valuation", sa.Numeric(precision=11, scale=2), nullable=True),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("last_year", sa.SmallInteger(), nullable=True),
        sa.Column("vesting", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'rsu' AND exercise_price IS NULL) OR (kind = 'option' AND exercise_price >= 0 AND exercise_price IS NOT NULL)"
        ),
        sa.CheckConstraint(
            "(valuation IS NULL) = (valuation_date IS NULL) AND valuation >= 0"
        ),
        sa.CheckConstraint("units > 0 AND version > 0"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["app.compensation_packages.employee_id"],
        ),
        sa.ForeignKeyConstraint(
            ["grant_currency"],
            ["app.currencies.code"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_equity_awards_employee_id"),
        "equity_awards",
        ["employee_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "equity_elections",
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["app.compensation_packages.employee_id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["app.hr_users.id"],
        ),
        sa.PrimaryKeyConstraint("employee_id"),
        schema="app",
    )
    op.create_table(
        "equity_allocations",
        sa.Column("award_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=11, scale=2), nullable=False),
        sa.CheckConstraint("year BETWEEN 1900 AND 9998 AND amount >= 0"),
        sa.ForeignKeyConstraint(
            ["award_id"],
            ["app.equity_awards.id"],
        ),
        sa.ForeignKeyConstraint(
            ["currency_code"],
            ["app.currencies.code"],
        ),
        sa.PrimaryKeyConstraint("award_id", "year"),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_equity_allocations_year"),
        "equity_allocations",
        ["year"],
        unique=False,
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("equity_allocations", schema="app")
    op.drop_table("equity_elections", schema="app")
    op.drop_table("equity_awards", schema="app")
