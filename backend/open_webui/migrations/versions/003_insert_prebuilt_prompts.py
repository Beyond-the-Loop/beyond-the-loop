"""Insert Prebuilt Prompts

Revision ID: 003
Revises: 002
Create Date: 2026-01-06 11:42:05.577836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import pathlib
import time
import json
import csv

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a connection and bind a session
    connection = op.get_bind()
    session = Session(bind=connection)

    # Delete all prebuilt prompts
    delete_query = sa.text("DELETE FROM prompt WHERE prebuilt = :prebuilt")
    session.execute(delete_query, {"prebuilt": True})

    current_dir = pathlib.Path(__file__).parent.parent
    csv_file_path = current_dir / "data" / "prebuilt_prompts.csv"

    with open(csv_file_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)

        current_time = int(time.time())
        system_user_id = "system"
        system_company_id = "system"

        for index, row in enumerate(csv_reader):
            command = row['title'].lower().replace(' ', '-')
            meta = {"tags": [{"name": row['tag']}]}

            insert_query = sa.text("""
                INSERT INTO prompt (command, user_id, title, content, timestamp, meta, prebuilt, description, company_id)
                VALUES (:command, :user_id, :title, :content, :timestamp, :meta, :prebuilt, :description, :company_id)
            """)

            session.execute(insert_query, {
                "command": f"/{command}",
                "user_id": system_user_id,
                "company_id": system_company_id,
                "title": row['title'],
                "content": row['content'],
                "timestamp": current_time,
                "meta": json.dumps(meta),
                "prebuilt": True,
                "description": row['description'],
            })

        session.commit()


def downgrade() -> None:
    # Create a connection
    connection = op.get_bind()
    session = Session(bind=connection)

    # Delete all prebuilt prompts
    delete_query = sa.text("DELETE FROM prompt WHERE prebuilt = :prebuilt")
    session.execute(delete_query, {"prebuilt": True})

    # Commit the changes
    session.commit()
