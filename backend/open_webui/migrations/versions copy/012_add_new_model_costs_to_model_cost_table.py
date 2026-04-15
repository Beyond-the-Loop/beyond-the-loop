"""Add new model costs to model_cost table

Revision ID: 012
Revises: 011
Create Date: 2026-01-20 13:59:44.275835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                UPDATE model_cost
                SET cost_per_million_input_tokens = 0.2,
                    cost_per_million_output_tokens = 0.5
                WHERE model_name IN ('Grok 4 fast (thinking)');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 0.2,
                    cost_per_million_output_tokens = 0.5
                WHERE model_name IN ('Grok 4 fast (instant)');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 0.15,
                    cost_per_million_output_tokens = 0.6
                WHERE model_name IN ('GPT OSS 120b');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 0.5,
                    cost_per_million_output_tokens = 1.5
                WHERE model_name IN ('Mistral Large 3');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 0.64,
                    cost_per_million_output_tokens = 1.85
                WHERE model_name IN ('DeepSeek-V3.2');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 1.35,
                    cost_per_million_output_tokens = 5.4
                WHERE model_name IN ('DeepSeek R1');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 1.25,
                    cost_per_million_output_tokens = 10
                WHERE model_name IN ('GPT-5.1 Codex');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 1.75,
                    cost_per_million_output_tokens = 14
                WHERE model_name IN ('GPT-5.2');
                    
                UPDATE model_cost
                SET cost_per_million_input_tokens = 2,
                    cost_per_million_output_tokens = 40
                WHERE model_name IN ('GPT o3 Deep Research');
                """
                )
    )


def downgrade() -> None:
    pass
