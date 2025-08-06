"""Reset/Update company configs

Revision ID: 325015866531
Revises: b5f1f7576bd0
Create Date: 2025-07-19 15:57:12.514960

"""
from typing import Sequence, Union
import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '325015866531'
down_revision: Union[str, None] = 'b5f1f7576bd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Import here to avoid circular imports
    from sqlalchemy.orm import sessionmaker

    connection = op.get_bind()
    
    try:
        # Get all config entries
        configs = connection.execute(
            sa.text("SELECT id, data, company_id FROM config")
        ).fetchall()
        
        new_image_generation_config = {
            "engine": "flux",
            "enable": True,
            "model": "flux-kontext-max",
            "size": "1024x1024"
        }
        
        # Update each config
        for config_row in configs:
            config_id, config_data, company_id = config_row
            
            # Parse the JSON data
            if isinstance(config_data, str):
                data = json.loads(config_data)
            else:
                data = config_data
            
            # Update the image_generation section
            data["image_generation"] = new_image_generation_config
            
            # Convert back to JSON string if needed
            updated_data = json.dumps(data) if isinstance(config_data, str) else data
            
            # Update the database record
            connection.execute(
                sa.text("UPDATE config SET data = :data WHERE id = :id"),
                {"data": updated_data, "id": config_id}
            )
        
        # Commit all changes
        connection.commit()
        print(f"Updated {len(configs)} company configurations with new Flux image generation settings")
        
    except Exception as e:
        connection.rollback()
        print(f"Error updating configs: {e}")
        raise


def downgrade() -> None:
    pass
