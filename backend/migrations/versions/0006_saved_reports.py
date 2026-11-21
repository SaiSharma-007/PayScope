"""Independent saved report snapshots."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("saved_reports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("app.hr_users.id"), nullable=False),
        sa.Column("source_run_id", sa.Uuid, nullable=False),
        sa.Column("source_conversation_id", sa.Uuid, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("report", JSONB, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("snapshot_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("chart_view", JSONB, nullable=False, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "source_run_id", name="uq_saved_report_source"),
        schema="app")

def downgrade():
    op.drop_table("saved_reports", schema="app")
