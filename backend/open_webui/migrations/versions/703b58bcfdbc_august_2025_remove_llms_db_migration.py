"""August 2025 remove LLMs DB migration

Revision ID: 703b58bcfdbc
Revises: e956533c9867
Create Date: 2025-08-02 16:24:55.904104

"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table
import open_webui.internal.db
import sqlalchemy
from open_webui.env import DATABASE_URL


# revision identifiers, used by Alembic.
revision: str = "703b58bcfdbc"
down_revision: Union[str, None] = "e956533c9867"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("Removing LLMs; GPT o3-mini, Perplexity Sonar and Pixtral Large")

    db_engine = sqlalchemy.create_engine(DATABASE_URL)

    with db_engine.connect() as connection:
        replacement_models_list = {
            "GPT o3-mini": {
                "meta": {},
                "params": {},
                "replace_with": "GPT o4-mini",
                "stats": "replace",
            },
            "GPT o4-mini": {
                "meta": {},
                "params": {},
                "replace_with": None,
                "stats": "unchanged",
            },
            "Mistral Large 2": {
                "meta": {},
                "params": {},
                "replace_with": None,
                "stats": "unchanged",
            },
            "Perplexity Sonar": {
                "meta": {},
                "params": {},
                "replace_with": "Perplexity Sonar Pro",
                "stats": "replace",
            },
            "Perplexity Sonar Pro": {
                "meta": {},
                "params": {},
                "replace_with": None,
                "stats": "unchanged",
            },
            "Pixtral Large": {
                "meta": {},
                "params": {},
                "replace_with": "Mistral Large 2",
                "stats": "replace",
            },
        }

        # replace models in model table
        to_replace_models_list = {
            k: v
            for k, v in replacement_models_list.items()
            if v["stats"] == "replace" and v["replace_with"] is not None
        }

        should_commit = False
        for model_name, model_data in to_replace_models_list.items():
            should_commit = True
            replacement_model_name = model_data["replace_with"]
            print(f"Replacing model: {model_name} with {replacement_model_name}")
            connection.execute(
                sqlalchemy.text("UPDATE model SET name = :replace_with, meta = :meta, params = :params WHERE name = :model_name"),
                {
                    "meta": json.dumps(replacement_models_list[replacement_model_name]["meta"]),
                    "model_name": model_name,
                    "params": json.dumps(replacement_models_list[replacement_model_name]["params"]),
                    "replace_with": replacement_model_name,
                },
            )
        if should_commit:
            connection.commit()

        # remove models from model_cost table
        to_remove_models_list = {
            k: v for k, v in replacement_models_list.items() if v["stats"] == "replace"
        }

        should_commit = False
        for model_name in to_remove_models_list.keys():
            should_commit = True
            print(f"Removing model: {model_name} from model_cost table")
            connection.execute(
                sqlalchemy.text("DELETE FROM model_cost WHERE model_name = :model_name"),
                {"model_name": model_name},
            )
        if should_commit:
            connection.commit()

def downgrade() -> None:
    pass
