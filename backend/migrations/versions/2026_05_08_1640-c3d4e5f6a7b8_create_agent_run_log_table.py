"""create_agent_run_log_table

Revision ID: c3d4e5f6a7b8
Revises: b7c1d2e3f4a5

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_run_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('triggered_by', sa.String(length=32), nullable=False),
        sa.Column('risk_level', sa.String(length=16), nullable=False),
        sa.Column('observations', JSONB, nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('actions_planned', JSONB, nullable=False),
        sa.Column('actions_executed', JSONB, nullable=False),
        sa.Column('context_snapshot', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_run_log_user_created', 'agent_run_log', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_agent_run_log_user_created', table_name='agent_run_log')
    op.drop_table('agent_run_log')
