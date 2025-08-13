"""Hotfix Llama 4 deletion

Revision ID: 5be7088b9880
Revises: dc09e93071fb
Create Date: 2025-08-13 22:12:49.896466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '5be7088b9880'
down_revision: Union[str, None] = 'dc09e93071fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sqlalchemy.text("DELETE FROM model_cost WHERE model_name = 'Llama 4 Maverick'")
    )


def downgrade() -> None:
    pass
