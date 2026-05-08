"""create_questionnaire_response_table

Revision ID: ac59efc39af8
Revises: 418b9ec4294a

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'ac59efc39af8'
down_revision: Union[str, None] = '418b9ec4294a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'questionnaire_response',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('scenario', sa.String(length=32), nullable=False),
        sa.Column('answers', JSONB, nullable=False),
        sa.Column('context_snapshot', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_questionnaire_response_user_date'),
    )


def downgrade() -> None:
    op.drop_table('questionnaire_response')
