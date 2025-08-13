"""add_prebuilt_assistants_to_model_table

Revision ID: f9d94e70461a
Revises: 5be7088b9880
Create Date: 2025-08-08 13:33:59.780605

"""
from typing import Sequence, Union
import csv
import time
import json
import os
import pathlib
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'f9d94e70461a'
down_revision: Union[str, None] = '5be7088b9880'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a connection and bind a session
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # Get the path to the CSV file
    current_dir = pathlib.Path(__file__).parent.parent
    csv_file_path = current_dir / "data" / "prebuilt_assistants.csv"
    
    # Read the CSV data from file
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        
        # Insert assistants into the database
        current_time = int(time.time())
        system_user_id = "system"  # Use a system user ID for prebuilt assistants
        system_company_id = "system"

        for row in csv_reader:
            # Skip empty rows
            if not row.get('Name') or not row['Name'].strip():
                continue
                
            # Generate a unique ID for the assistant
            assistant_id = f"system-{str(uuid.uuid4())}"
            
            # Parse creativity level
            creativity_mapping = {
                'Creative': 0.8,
                'Balanced': 0.5,
                'Determined': 0.2
            }

            creativity = creativity_mapping.get(row.get('Creativity', 'Balanced'), 0.5)
            
            # Parse websearch boolean
            websearch = row.get('Websearch', 'FALSE').upper() == 'TRUE'

            # Pase System Prompt
            system_prompt = row.get('System Prompt', '')
            
            # Parse prompt suggestions
            prompt_suggestions = []
            if row.get('Prompt Suggestions'):
                suggestions = row['Prompt Suggestions'].split(';')
                prompt_suggestions = [s.strip() for s in suggestions if s.strip()]
            
            # Create meta object
            meta = {
                "description": row.get('Beschreibung', ''),
                "profile_image_url": "\ud83e\udd16",
                "categories": [row.get('Kategorie', 'Assistenzaufgaben')],
                "capabilities": {
                    "websearch": websearch,
                    "image_generation":False,
                    "code_interpreter": False,
                    "vision": False,
                    "citations": False
                }
            }

            params = {
                "system": system_prompt,
                "temperature": creativity
            }

            base_model = row.get('Model')

            # Insert the assistant into the model table
            insert_query = sa.text("""
                INSERT INTO model (id, user_id, company_id, base_model_id, name, meta, is_active, created_at, updated_at, params)
                VALUES (:id, :user_id, :company_id, :base_model_id, :name, :meta, :is_active, :created_at, :updated_at, :params)
            """)
            
            connection.execute(insert_query, {
                'id': assistant_id,
                'user_id': system_user_id,
                'company_id': system_company_id,
                'base_model_id': base_model,
                'name': row['Name'],
                'meta': json.dumps(meta),
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time,
                'params': json.dumps(params)
            })

    session.commit()
    session.close()


def downgrade() -> None:
    # Remove all system prebuilt assistants
    connection = op.get_bind()
    
    delete_query = sa.text("""
        DELETE FROM model 
        WHERE user_id = 'system' AND company_id = 'system' AND id LIKE 'system-%'
    """)
    
    connection.execute(delete_query)
    connection.commit()
