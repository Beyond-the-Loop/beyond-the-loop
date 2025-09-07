"""Remove Claude Opus 4

Revision ID: 41f6c14e7cf5
Revises: a1b2c3d4e5f6
Create Date: 2025-09-07 11:04:13.232477

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = "41f6c14e7cf5"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    companies = connection.execute(
        sqlalchemy.text("SELECT company_id FROM model GROUP BY company_id")
    ).fetchall()

    for company in companies:
        company_id = company[0]

        claude_opus4_model_id = connection.execute(
            sqlalchemy.text(
                "SELECT id FROM model WHERE name = 'Claude Opus 4' AND company_id = :company_id"
            ),
            {"company_id": company_id},
        ).scalar()
        claude_opus41_model_id = connection.execute(
            sqlalchemy.text(
                "SELECT id FROM model WHERE name = 'Claude Opus 4.1' AND company_id = :company_id"
            ),
            {"company_id": company_id},
        ).scalar()

        if claude_opus4_model_id and claude_opus41_model_id:
            connection.execute(
                sqlalchemy.text(
                    "UPDATE model SET base_model_id = :claude_opus41_model_id WHERE base_model_id = :claude_opus4_model_id AND company_id = :company_id"
                ),
                {
                    "claude_opus41_model_id": claude_opus41_model_id,
                    "claude_opus4_model_id": claude_opus4_model_id,
                    "company_id": company_id,
                },
            )
            connection.execute(
                sqlalchemy.text(
                    "DELETE FROM model WHERE id = :claude_opus4_model_id AND company_id = :company_id"
                ),
                {
                    "claude_opus4_model_id": claude_opus4_model_id,
                    "company_id": company_id,
                },
            )

    connection.execute(
        sqlalchemy.text("DELETE FROM model_cost WHERE model_name = 'Claude Opus 4'")
    )


def downgrade() -> None:
    pass
