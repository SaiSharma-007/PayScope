"""Allow reversible deletion of saved conversations."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_conversations", sa.Column("deleted_at", sa.DateTime(timezone=True)), schema="app")


def downgrade():
    op.drop_column("agent_conversations", "deleted_at", schema="app")
