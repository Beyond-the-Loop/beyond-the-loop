"""August 2025 remove duplicate LLMs

Revision ID: 3572e4045c21
Revises: 703b58bcfdbc
Create Date: 2025-08-06 14:22:47.464864

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = "3572e4045c21"
down_revision: Union[str, None] = "703b58bcfdbc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("Removing duplicate LLMs")

    connection = op.get_bind()

    duplicate_models = ["GPT o4-mini", "Perplexity Sonar Pro", "Mistral Large 2"]
    companies = connection.execute(sqlalchemy.text("SELECT company_id FROM model GROUP BY company_id")).fetchall()

    should_commit = False
    for company in companies:
        company_id = company[0]

        for model in duplicate_models:
            model_ids = connection.execute(
                sqlalchemy.text("SELECT id FROM model WHERE name = :model AND company_id = :company_id AND base_model_id IS NULL"),
                {"company_id": company_id, "model": model},
            ).fetchall()

            if len(model_ids) > 1:
                print(f"Found duplicate models {model_ids} for company {company_id}")
                should_commit = True

                where_in_clause = ",".join(f'"{model_id[0]}"' for model_id in model_ids)
                model_referenced_as_base_model = connection.execute(
                    sqlalchemy.text(f"SELECT id, base_model_id FROM model WHERE base_model_id IN ({where_in_clause})"),
                ).fetchall()

                model_id_keep = model_referenced_as_base_model[0][1] if model_referenced_as_base_model and len(model_referenced_as_base_model) > 0 else model_ids[0][0]
                model_id_removes = [model_id[0] for model_id in model_ids if model_id[0] != model_id_keep]

                print(f"Keeping model {model_id_keep} and removing {model_id_removes} for company {company_id}")
                for model_id_remove in model_id_removes:
                    connection.execute(
                        sqlalchemy.text("UPDATE model SET base_model_id = :model_id_keep WHERE base_model_id = :model_id_remove AND company_id = :company_id"),
                        {
                            "model_id_keep": model_id_keep,
                            "model_id_remove": model_id_remove,
                            "company_id": company_id,
                        },
                    )
                    connection.execute(
                        sqlalchemy.text("DELETE FROM model WHERE id = :model_id_remove AND company_id = :company_id"),
                        {"model_id_remove": model_id_remove, "company_id": company_id},
                    )

    if should_commit:
        connection.commit()
        print("Duplicate LLMs removed successfully.")
    else:
        print("No duplicate LLMs found to remove.")


def downgrade() -> None:
    pass
