"""Change model_cost table dall-e-3 to flux-kontext-pro

Revision ID: 396ffa64269c
Revises: fbde9eebf688
Create Date: 2025-07-19 14:04:49.174528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '396ffa64269c'
down_revision: Union[str, None] = 'fbde9eebf688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # from model_cost table update the entry with the model_name "dall-e-3"
    # to the model_name "flux-kontext-pro" also set the cost per image to 0.04
    op.execute(
        """
        UPDATE model_cost
        SET model_name = 'flux-kontext-pro', cost_per_image = 0.04
        WHERE model_name = 'dall-e-3';
        """
    )


def downgrade() -> None:
    pass
