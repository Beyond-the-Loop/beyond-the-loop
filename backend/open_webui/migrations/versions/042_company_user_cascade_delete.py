"""Tighten company cascade chain and drop unused legacy tables

Revision ID: 042
Revises: 041
Create Date: 2026-05-29 00:00:00.000000

Schema cleanups:

- Add company → domain ON DELETE CASCADE (missed by migration 029).
- Drop the redundant company → {prompt, knowledge} CASCADE FKs added in 029.
  Those rows are owned by users (prompt.user_id, knowledge.user_id) and
  already cascade away via the user-side FKs from migration 028. The
  company-side CASCADE was a second path to the same end state; the
  company-delete flow leans on the user cascade chain
  (Users.delete_users_by_company_id → user→X cascades).
  The NOT NULL constraints on company_id stay — every row still belongs to a
  company, we just don't enforce the reference at the DB level.
  company → model, company → group, and company → config keep their CASCADE.
  group and config don't have a user_id (no user-side cascade path). model
  has system-owned per-company rows (OpenAI models + kickstart assistants
  seeded with user_id='system' but company_id=<real_company> in
  routers/companies.py) that the user-side cascade wouldn't reach.
- Drop legacy tables `bookmarked_assistants`, `bookmarked_prompts`,
  `channel_member`, `chatidtag`, `document`, `migratehistory`, and
  `stripe_payment_history` — none are referenced anywhere in the codebase.
  Active bookmarks live in `user_model_bookmark` / `user_prompt_bookmark`
  (which already cascade via migration 030); channel membership is modeled
  via `channel.access_control` JSON, not a join table; chat tagging uses
  the active `tag` table; document content lives in `file` + `knowledge` +
  vector collections (the pgvector internal `document_chunk` table is a
  different thing and untouched); `migratehistory` is a leftover from the
  Peewee migration system that predated the switch to Alembic, whose state
  lives in `alembic_version`.

- Add ON DELETE CASCADE FKs `chat.folder_id → folder.id` and
  `folder.parent_id → folder.id` so deleting a folder also removes its chats
  and any nested subfolders (recursively). Replaces the manual Python
  recursion in `Folders.delete_folder_by_id_and_user_id`. Orphan references
  are nulled out first to preserve the chat/folder rows themselves.

- Add ON DELETE CASCADE FKs `message.channel_id → channel.id`,
  `message.parent_id → message.id`, and
  `message_reaction.message_id → message.id`. Closes three cascade gaps:
  deleting a channel now removes its messages, deleting a message removes
  its thread replies, and deleting a message removes its reactions. The
  message + message_reaction tables are empty in prod, so no orphan
  pre-cleanup is needed.

- Promote the leftover unique-index-on-(id) to a proper PRIMARY KEY for
  `user`, `auth`, `chat`, `memory`, `file`, and `model`. The Peewee→Alembic
  conversion left these tables with a unique index instead of a PK
  constraint, which meant `id` was technically nullable in the DB. Promotion
  uses ADD PRIMARY KEY USING INDEX so existing FKs that target these tables
  keep working (the index object itself stays, just gets reclassified).

- Add `completion.user_id → "user"(id) ON DELETE SET NULL`. Migration 028
  missed this; the SQLAlchemy model declared the FK with SET NULL but no
  DB-level constraint ever got created. Today user deletes leave silent
  orphans in the completion table. Orphan user_ids are nulled out first.

- Enforce NOT NULL on `knowledge.company_id`, `prompt.company_id`, and
  `group.company_id` to match the SQLAlchemy models. For knowledge and
  prompt, existing NULL values are backfilled from the owning user's
  company_id; prompt falls back to 'system' for stragglers. Group rows in
  prod always have a company_id set, so no backfill is needed there.

Users are deliberately *not* wired up with a DB-level FK to company because
historical "NEW" and "NO_COMPANY" sentinel values in user.company_id don't
reference real company rows. User deletion on company delete is handled at the
application layer (Users.delete_users_by_company_id).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE domain
            ALTER COLUMN company_id SET NOT NULL,
            DROP CONSTRAINT IF EXISTS domain_company_id_fkey,
            ADD CONSTRAINT domain_company_id_fkey
                FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE CASCADE
    """))

    # Drop the redundant company-side CASCADE FKs on user-owned tables;
    # user→X cascades from migration 028 handle the cleanup.
    # model is excluded: it has system-owned per-company rows (seeded with
    # user_id='system' in routers/companies.py) that the user-side cascade
    # wouldn't reach, so model_company_id_fkey stays.
    conn.execute(sa.text("ALTER TABLE prompt DROP CONSTRAINT IF EXISTS prompt_company_id_fkey"))
    conn.execute(sa.text("ALTER TABLE knowledge DROP CONSTRAINT IF EXISTS knowledge_company_id_fkey"))

    # Promote the leftover unique-index-on-(id) to a proper PRIMARY KEY for
    # the tables that came out of the Peewee→Alembic conversion without one.
    # Uses ADD PRIMARY KEY USING INDEX so the index object stays (existing
    # FKs that target these tables keep working without recreation).
    for table_sql in ['"user"', 'auth', 'chat', 'memory', 'file', 'model']:
        conn.execute(sa.text(f"""
            DO $$
            DECLARE
                pk_exists boolean;
                idx_name text;
            BEGIN
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = '{table_sql}'::regclass AND contype = 'p'
                ) INTO pk_exists;

                IF NOT pk_exists THEN
                    SELECT i.relname INTO idx_name
                    FROM pg_index x
                    JOIN pg_class i ON i.oid = x.indexrelid
                    WHERE x.indrelid = '{table_sql}'::regclass
                      AND x.indisunique
                      AND NOT x.indisprimary
                      AND array_length(x.indkey, 1) = 1
                      AND (SELECT attname FROM pg_attribute
                           WHERE attrelid = x.indrelid AND attnum = x.indkey[0]) = 'id'
                    LIMIT 1;

                    IF idx_name IS NULL THEN
                        RAISE EXCEPTION
                            'No unique single-column index on {table_sql}(id) found — cannot promote to PK';
                    END IF;

                    EXECUTE 'ALTER TABLE {table_sql} ALTER COLUMN id SET NOT NULL';
                    EXECUTE 'ALTER TABLE {table_sql} ADD PRIMARY KEY USING INDEX '
                        || quote_ident(idx_name);
                END IF;
            END $$;
        """))

    # completion.user_id was missing a FK entirely (oversight in migration
    # 028). Null out orphan references first to make the FK addition safe,
    # then add it with ON DELETE SET NULL so billing history survives user
    # deletes.
    conn.execute(sa.text("""
        UPDATE completion SET user_id = NULL
        WHERE user_id IS NOT NULL
          AND user_id NOT IN (SELECT id FROM "user")
    """))
    conn.execute(sa.text("""
        ALTER TABLE completion
            DROP CONSTRAINT IF EXISTS completion_user_id_fkey,
            ADD CONSTRAINT completion_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE SET NULL
    """))

    # Bring knowledge.company_id NOT NULL constraint up to match the
    # SQLAlchemy model. Backfill any NULLs from the owning user's company_id.
    # knowledge.user_id has CASCADE on user-delete, so we shouldn't see
    # knowledge rows referencing dead users; if any NULL survives the
    # backfill, fail loudly so a human can investigate.
    conn.execute(sa.text("""
        UPDATE knowledge k
        SET company_id = u.company_id
        FROM "user" u
        WHERE k.user_id = u.id AND k.company_id IS NULL
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM knowledge WHERE company_id IS NULL) THEN
                RAISE EXCEPTION
                    'knowledge rows with NULL company_id remain after backfill — investigate manually';
            END IF;
        END $$;
    """))
    conn.execute(sa.text("ALTER TABLE knowledge ALTER COLUMN company_id SET NOT NULL"))

    # prompt.company_id has 'system' as DEFAULT for new rows; for any
    # pre-default NULLs, prefer the owning user's company_id, falling back
    # to 'system' (matches the row's effective behavior in code today).
    conn.execute(sa.text("""
        UPDATE prompt p
        SET company_id = u.company_id
        FROM "user" u
        WHERE p.user_id = u.id AND p.company_id IS NULL
    """))
    conn.execute(sa.text("""
        UPDATE prompt SET company_id = 'system' WHERE company_id IS NULL
    """))
    conn.execute(sa.text("ALTER TABLE prompt ALTER COLUMN company_id SET NOT NULL"))

    conn.execute(sa.text('ALTER TABLE "group" ALTER COLUMN company_id SET NOT NULL'))

    # folder still has the Peewee-era composite primary key (id, user_id);
    # normalize it to a simple PK on id so we can target it from FKs. Folder
    # ids are UUIDs, so id-alone uniqueness is already guaranteed in practice.
    # Drop any FKs that depend on the existing PK first so the PK drop
    # succeeds (they get re-added with CASCADE further down).
    conn.execute(sa.text("ALTER TABLE chat DROP CONSTRAINT IF EXISTS chat_folder_id_fkey"))
    conn.execute(sa.text("ALTER TABLE folder DROP CONSTRAINT IF EXISTS folder_parent_id_fkey"))
    conn.execute(sa.text("""
        DO $$
        DECLARE
            pk_name text;
        BEGIN
            SELECT conname INTO pk_name
            FROM pg_constraint
            WHERE conrelid = 'folder'::regclass AND contype = 'p';

            IF pk_name IS NOT NULL THEN
                EXECUTE 'ALTER TABLE folder DROP CONSTRAINT ' || quote_ident(pk_name);
            END IF;
        END $$;
    """))
    conn.execute(sa.text("ALTER TABLE folder ADD PRIMARY KEY (id)"))

    # Null out orphan references before introducing folder cascade FKs so
    # the chats/folders themselves survive the migration.
    conn.execute(sa.text("""
        UPDATE chat SET folder_id = NULL
        WHERE folder_id IS NOT NULL
          AND folder_id NOT IN (SELECT id FROM folder)
    """))
    conn.execute(sa.text("""
        UPDATE folder SET parent_id = NULL
        WHERE parent_id IS NOT NULL
          AND parent_id NOT IN (SELECT id FROM folder)
    """))

    conn.execute(sa.text("""
        ALTER TABLE chat
            DROP CONSTRAINT IF EXISTS chat_folder_id_fkey,
            ADD CONSTRAINT chat_folder_id_fkey
                FOREIGN KEY (folder_id) REFERENCES folder(id) ON DELETE CASCADE
    """))
    conn.execute(sa.text("""
        ALTER TABLE folder
            DROP CONSTRAINT IF EXISTS folder_parent_id_fkey,
            ADD CONSTRAINT folder_parent_id_fkey
                FOREIGN KEY (parent_id) REFERENCES folder(id) ON DELETE CASCADE
    """))

    # message + message_reaction tables are empty in prod; add FKs directly.
    conn.execute(sa.text("""
        ALTER TABLE message
            DROP CONSTRAINT IF EXISTS message_channel_id_fkey,
            ADD CONSTRAINT message_channel_id_fkey
                FOREIGN KEY (channel_id) REFERENCES channel(id) ON DELETE CASCADE,
            DROP CONSTRAINT IF EXISTS message_parent_id_fkey,
            ADD CONSTRAINT message_parent_id_fkey
                FOREIGN KEY (parent_id) REFERENCES message(id) ON DELETE CASCADE
    """))
    conn.execute(sa.text("""
        ALTER TABLE message_reaction
            DROP CONSTRAINT IF EXISTS message_reaction_message_id_fkey,
            ADD CONSTRAINT message_reaction_message_id_fkey
                FOREIGN KEY (message_id) REFERENCES message(id) ON DELETE CASCADE
    """))

    # Legacy / unused tables — no code references.
    conn.execute(sa.text("DROP TABLE IF EXISTS bookmarked_assistants"))
    conn.execute(sa.text("DROP TABLE IF EXISTS bookmarked_prompts"))
    conn.execute(sa.text("DROP TABLE IF EXISTS channel_member"))
    conn.execute(sa.text("DROP TABLE IF EXISTS chatidtag"))
    conn.execute(sa.text("DROP TABLE IF EXISTS document"))
    conn.execute(sa.text("DROP TABLE IF EXISTS migratehistory"))
    conn.execute(sa.text("DROP TABLE IF EXISTS stripe_payment_history"))


def downgrade() -> None:
    pass
