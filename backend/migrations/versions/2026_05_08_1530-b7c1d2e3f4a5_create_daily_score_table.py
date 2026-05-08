"""create_daily_score_table

Revision ID: b7c1d2e3f4a5
Revises: ac59efc39af8

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, None] = 'ac59efc39af8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_score',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('hrv_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sleep_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('audio_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('survey_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('hrv_weight', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('sleep_weight', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('audio_weight', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('survey_weight', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_daily_score_user_date'),
    )


def downgrade() -> None:
    op.drop_table('daily_score')
