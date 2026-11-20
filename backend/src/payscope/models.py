import sqlalchemy as sa

metadata = sa.MetaData(schema="app")

hr_users = sa.Table(
    "hr_users",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("email", sa.Text, nullable=False, unique=True),
    sa.Column("display_name", sa.Text, nullable=False),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
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
