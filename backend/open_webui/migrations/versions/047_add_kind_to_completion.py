"""Add kind column to completion (chat/stt/tts)

Revision ID: 047
Revises: 046
Create Date: 2026-06-25 10:00:00.000000

Why: only chat completions ever inserted rows here. STT/TTS deducted credits
but left no trace, which made the recent recharge-loop investigation a math
puzzle instead of a query. Adds a `kind` discriminator so every credit-burning
call leaves a row; existing rows backfill to 'chat' via server_default.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '047'
down_revision: Union[str, None] = '046'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'completion',
        sa.Column('kind', sa.Text(), nullable=False, server_default='chat'),
    )


def downgrade() -> None:
    op.drop_column('completion', 'kind')
