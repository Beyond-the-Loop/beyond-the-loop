"""New LLMs

Revision ID: dfff99fbe06b
Revises: 6964fbec2a16
Create Date: 2025-11-26 15:29:47.410062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'dfff99fbe06b'
down_revision: Union[str, None] = '6964fbec2a16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    new_models = {
        "GPT-5.1 (instant)": {
            "cost": {
                "cost_per_million_input_tokens": 1.25,
                "cost_per_million_output_tokens": 10,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
        },
        "GPT-5.1 (thinking)": {
            "cost": {
                "cost_per_million_input_tokens": 1.25,
                "cost_per_million_output_tokens": 10,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
        }
    }

    for new_model_name, new_model_data in new_models.items():
        model_cost = new_model_data["cost"]
        print(f"Inserting model: {new_model_name}")
        connection.execute(
            sqlalchemy.text(
                """INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries) VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)"""
            ),
            {
                "model_name": new_model_name,
                "cost_per_million_input_tokens": model_cost[
                    "cost_per_million_input_tokens"
                ],
                "cost_per_million_output_tokens": model_cost[
                    "cost_per_million_output_tokens"
                ],
                "cost_per_image": model_cost["cost_per_image"],
                "cost_per_minute": model_cost["cost_per_minute"],
                "cost_per_million_characters": model_cost[
                    "cost_per_million_characters"
                ],
                "cost_per_million_reasoning_tokens": model_cost[
                    "cost_per_million_reasoning_tokens"
                ],
                "cost_per_thousand_search_queries": model_cost[
                    "cost_per_thousand_search_queries"
                ],
            },
        )

def downgrade() -> None:
    pass
