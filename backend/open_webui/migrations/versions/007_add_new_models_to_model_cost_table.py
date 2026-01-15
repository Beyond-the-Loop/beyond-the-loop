"""Add new models to model_cost table

Revision ID: 007
Revises: 006
Create Date: 2026-01-13 14:41:02.118238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('Grok 4 fast (thinking)', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 300, 300);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('Grok 4 fast (instant)', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 300, 300);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('GPT OSS 120b', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 300, 300);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('Mistral Large 3', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 50, 150);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('DeepSeek-V3.2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 50, 150);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('DeepSeek R1', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 50, 150);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('GPT-5.1 Codex', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 50);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('GPT-5.2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 50);
                    
                INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image,
                        cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                        cost_per_thousand_search_queries, allowed_messages_per_three_hours_free, allowed_messages_per_three_hours_premium)
                        VALUES ('GPT o3 Deep Research', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 5);
                
                UPDATE model_cost SET allowed_messages_per_three_hours_free = 300, allowed_messages_per_three_hours_premium = 300 WHERE model_name IN ('GPT-5 nano', 'Gemini 2.5 Flash');
                    
                UPDATE model_cost SET allowed_messages_per_three_hours_free = 50, allowed_messages_per_three_hours_premium = 100 WHERE model_name IN ('GPT-5 mini', 'GPT o4-mini', 'GPT o3');
                    
                UPDATE model_cost SET allowed_messages_per_three_hours_premium = 50 WHERE model_name IN ('GPT-5.1 (thinking)', 'GPT-5.1 (instant)', 'GPT-5');                    
                """)
    )


def downgrade() -> None:
    pass
