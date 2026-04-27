"""Add Kickstart Assistants

Revision ID: 036
Revises: 035
Create Date: 2026-01-06 12:07:04.497624

"""
from typing import Sequence, Union
import csv
import time
import json
import pathlib
import uuid

from alembic import op
from beyond_the_loop.assistants.assistants_csv_loader import load_kickstart_assistants
from open_webui.internal.db import get_db
import sqlalchemy as sa
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = '036'
down_revision: Union[str, None] = '035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a connection and bind a session
    connection = op.get_bind()
    session = Session(bind=connection)

    result = connection.execute(sa.text("SELECT id FROM company;"))
    company_ids = [row[0] for row in result]
    
    kickstart_assistants = load_kickstart_assistants()
    kickstart_user_id = "system"
    for company in company_ids:
        if company != 'system':
            for assistant in kickstart_assistants:
                assistant_id = str(uuid.uuid4())
                assistant_name=assistant.get("name")
                base_model_id=assistant.get("base_model_id")
                meta = {
                    "description": assistant.get("description"),
                    "profile_image_url": assistant.get("profile_image_url"),
                    "categories": [assistant.get("category")], # gibt keine
                    "suggestion_prompts": [{"content": s} for s in assistant.get("suggestion_prompts")],
                    "is_kickstart_assistant": True
                }
                params = {
                    "system": assistant.get("system_prompt"),
                    "temperature": 0.5
                }

                # Insert the assistant into the model table
                insert_query = sa.text("""
                    INSERT INTO model (id, user_id, company_id, base_model_id, name, meta, is_active,
                                        created_at, updated_at, params)
                    VALUES (:id, :user_id, :company_id, :base_model_id, :name, :meta, :is_active,
                            :created_at, :updated_at, :params)
                """)

                connection.execute(insert_query, {
                    'id': assistant_id,
                    'user_id': kickstart_user_id,
                    'company_id': company,
                    'base_model_id': base_model_id,
                    'name': assistant_name,
                    'meta': json.dumps(meta),
                    'is_active': True,
                    'created_at': 1,
                    'updated_at': 1,
                    'params': json.dumps(params)
                })

    session.commit()
    session.close()


def downgrade() -> None:
    pass