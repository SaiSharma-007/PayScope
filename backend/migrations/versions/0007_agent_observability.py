"""Explicit observability access and run ordering."""
import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('hr_users', sa.Column('view_agent_observability', sa.Boolean(), nullable=False, server_default=sa.false()), schema='app')
    op.create_index('ix_agent_runs_created_id', 'agent_runs', ['created_at', 'id'], schema='app')


def downgrade():
    op.drop_index('ix_agent_runs_created_id', table_name='agent_runs', schema='app')
    op.drop_column('hr_users', 'view_agent_observability', schema='app')
