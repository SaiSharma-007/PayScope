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
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="ck_hr_users_email"),
)

auth_sessions = sa.Table(
    "auth_sessions",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("user_id", sa.ForeignKey("app.hr_users.id"), nullable=False),
    sa.Column("token_hash", sa.LargeBinary, nullable=False, unique=True),
    sa.Column("csrf_token_hash", sa.LargeBinary, nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
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
    sa.CheckConstraint("code IN ('INR', 'USD', 'GBP', 'EUR')", name="ck_currencies_code"),
    sa.CheckConstraint("minor_units = 2", name="ck_currencies_minor_units"),
)

departments = sa.Table(
    "departments",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_departments_name"),
)
sa.Index("uq_departments_normalized_name", sa.func.lower(departments.c.name), unique=True)

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
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
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
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.CheckConstraint(
        "annual_gross_base BETWEEN 0.01 AND 999999999.99", name="ck_employee_salaries_amount"
    ),
)

report_state = sa.Table(
    "report_state",
    metadata,
    sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
    sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.CheckConstraint("id = 1", name="ck_report_state_singleton"),
    sa.CheckConstraint("revision >= 0", name="ck_report_state_revision"),
)
