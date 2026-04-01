"""Add ON DELETE CASCADE FK constraints from model/group/prompt/knowledge/config to company

Revision ID: 028
Revises: 027
Create Date: 2026-04-01 00:00:00.000000

Why: model, group, prompt, knowledge store company_id as plain TEXT without a FK
constraint.  Deleting a company therefore leaves orphaned rows in those tables.
This migration adds proper FOREIGN KEY … ON DELETE CASCADE so that PG cleans up
automatically when a company is removed.

Prebuilt assistants and prompts use company_id = 'system', so we first insert a
sentinel 'system' company row (same pattern as the 'system' user in 026).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '028'
down_revision: Union[str, None] = '027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, constraint_name, fk_column, nullable)
# nullable=True means we only delete orphans where company_id IS NOT NULL
CASCADE_CONSTRAINTS = [
    ("model",     "model_company_id_fkey",     "company_id", False),
    ('"group"',   "group_company_id_fkey",      "company_id", False),
    ("prompt",    "prompt_company_id_fkey",     "company_id", False),
    ("knowledge", "knowledge_company_id_fkey",  "company_id", False),
    ("config",    "config_company_id_fkey",     "company_id", False),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Insert sentinel 'system' company so that prebuilt rows with
    # company_id = 'system' satisfy the new FK constraint.
    conn.execute(sa.text("""
        INSERT INTO company (id, name, credit_balance)
        VALUES ('system', 'System', 0)
        ON CONFLICT (id) DO NOTHING
    """))

    for table, constraint, column, nullable in CASCADE_CONSTRAINTS:
        # Remove orphaned rows that would violate the new FK
        if nullable:
            conn.execute(sa.text(
                f'DELETE FROM {table} '
                f'WHERE {column} IS NOT NULL '
                f'AND {column} NOT IN (SELECT id FROM company)'
            ))
        else:
            conn.execute(sa.text(
                f'DELETE FROM {table} '
                f'WHERE {column} NOT IN (SELECT id FROM company)'
            ))

        conn.execute(sa.text(
            f'ALTER TABLE {table} '
            f'DROP CONSTRAINT IF EXISTS {constraint}, '
            f'ADD CONSTRAINT {constraint} '
            f'FOREIGN KEY ({column}) REFERENCES company(id) ON DELETE CASCADE'
        ))

    # model.company_id was historically nullable=True — enforce NOT NULL now
    # that every row is guaranteed to have a valid company reference.
    conn.execute(sa.text(
        'ALTER TABLE model ALTER COLUMN company_id SET NOT NULL'
    ))


def downgrade() -> None:
    return
