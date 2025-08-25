"""add_chat_retention_days_to_configs

Revision ID: a1b2c3d4e5f6
Revises: f9d94e70461a
Create Date: 2025-08-25 13:55:00.000000

"""
from typing import Sequence, Union
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9d94e70461a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a connection and bind a session
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # Get all config entries
    configs = session.execute(
        sa.text("SELECT id, data, company_id FROM config")
    ).fetchall()
    
    # Update each config to add chat_retention_days = 90
    for config_row in configs:
        config_id, config_data, company_id = config_row
        
        # Parse the JSON data
        if isinstance(config_data, str):
            data = json.loads(config_data)
        else:
            data = config_data
        
        # Add chat_retention_days to the data section
        if "data" not in data:
            data["data"] = {}
        data["data"]["chat_retention_days"] = 90
        
        # Convert back to JSON string if needed
        updated_data = json.dumps(data) if isinstance(config_data, str) else data
        
        # Update the database record
        session.execute(
            sa.text("UPDATE config SET data = :data WHERE id = :id"),
            {"data": updated_data, "id": config_id}
        )
    
    # Commit the changes
    session.commit()
    print(f"Updated {len(configs)} company configurations with chat_retention_days = 90")


def downgrade() -> None:
    # Create a connection and bind a session
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # Get all config entries
    configs = session.execute(
        sa.text("SELECT id, data, company_id FROM config")
    ).fetchall()
    
    # Remove chat_retention_days from each config
    for config_row in configs:
        config_id, config_data, company_id = config_row
        
        # Parse the JSON data
        if isinstance(config_data, str):
            data = json.loads(config_data)
        else:
            data = config_data
        
        # Remove chat_retention_days from data section if it exists
        if "data" in data and "chat_retention_days" in data["data"]:
            del data["data"]["chat_retention_days"]
        
        # Convert back to JSON string if needed
        updated_data = json.dumps(data) if isinstance(config_data, str) else data
        
        # Update the database record
        session.execute(
            sa.text("UPDATE config SET data = :data WHERE id = :id"),
            {"data": updated_data, "id": config_id}
        )
    
    # Commit the changes
    session.commit()
    print(f"Removed chat_retention_days from {len(configs)} company configurations")
