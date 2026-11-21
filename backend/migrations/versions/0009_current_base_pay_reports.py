"""Mark legacy report snapshots stale where compensation packages exist."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def advance_revision():
    op.execute("""
        UPDATE app.report_state SET revision = revision + 1,
            updated_at = clock_timestamp()
        WHERE id = 1 AND EXISTS (SELECT 1 FROM app.compensation_packages)
    """)


def upgrade():
    advance_revision()


def downgrade():
    advance_revision()
