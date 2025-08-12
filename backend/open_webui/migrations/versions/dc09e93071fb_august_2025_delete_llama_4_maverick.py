"""August 2025 delete Llama 4 Maverick

Revision ID: dc09e93071fb
Revises: 9b79f110c1db
Create Date: 2025-08-12 14:39:38.506534

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = "dc09e93071fb"
down_revision: Union[str, None] = "9b79f110c1db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    companies = connection.execute(
        sqlalchemy.text("SELECT company_id FROM model GROUP BY company_id")
    ).fetchall()

    for company in companies:
        company_id = company[0]

        llama_model_id = connection.execute(
            sqlalchemy.text(
                "SELECT id FROM model WHERE name = 'Llama 4 Maverick' AND company_id = :company_id"
            ),
            {"company_id": company_id},
        ).scalar()
        google_25_flash_id = connection.execute(
            sqlalchemy.text(
                "SELECT id FROM model WHERE name = 'Google 2.5 Flash' AND company_id = :company_id"
            ),
            {"company_id": company_id},
        ).scalar()

        if llama_model_id and google_25_flash_id:
            connection.execute(
                sqlalchemy.text(
                    "UPDATE model SET base_model_id = :google_25_flash_id WHERE base_model_id = :llama_model_id AND company_id = :company_id"
                ),
                {
                    "google_25_flash_id": google_25_flash_id,
                    "llama_model_id": llama_model_id,
                    "company_id": company_id,
                },
            )
            connection.execute(
                sqlalchemy.text(
                    "DELETE FROM model WHERE id = :llama_model_id AND company_id = :company_id"
                ),
                {
                    "llama_model_id": llama_model_id,
                    "company_id": company_id,
                },
            )


def downgrade() -> None:
    pass
