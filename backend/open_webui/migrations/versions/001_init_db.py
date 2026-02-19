"""Init DB

Revision ID: 001
Revises: 
Create Date: 2025-12-20 16:25:47.709514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
create table if not exists migratehistory
(
    id          bigint not null
        constraint idx_16726_migratehistory_pkey
            primary key,
    name        text,
    migrated_at timestamp with time zone
);

create table if not exists chatidtag
(
    id        text,
    tag_name  text,
    chat_id   text,
    user_id   text,
    timestamp bigint
);

create unique index if not exists idx_16731_chatidtag_id
    on chatidtag (id);

create table if not exists auth
(
    id       text,
    email    text,
    password text,
    active   bigint
);

create unique index if not exists idx_16736_auth_id
    on auth (id);

create table if not exists chat
(
    id         text,
    user_id    text,
    title      text,
    share_id   text,
    archived   bigint,
    created_at bigint,
    updated_at bigint,
    chat       json,
    pinned     boolean,
    meta       json default '{}'::json,
    folder_id  text
);

create unique index if not exists idx_16741_chat_share_id
    on chat (share_id);

create unique index if not exists idx_16741_chat_id
    on chat (id);

create table if not exists document
(
    id              bigint not null
        constraint idx_16747_document_pkey
            primary key,
    collection_name text,
    name            text,
    title           text,
    filename        text,
    content         text,
    user_id         text,
    timestamp       bigint
);

create unique index if not exists idx_16747_document_collection_name
    on document (collection_name);

create unique index if not exists idx_16747_document_name
    on document (name);

create table if not exists memory
(
    id         text,
    user_id    text,
    content    text,
    updated_at bigint,
    created_at bigint
);

create unique index if not exists idx_16752_memory_id
    on memory (id);

create table if not exists alembic_version
(
    version_num text not null
        constraint idx_16757_sqlite_autoindex_alembic_version_1
            primary key
);

create table if not exists tag
(
    id      text not null,
    name    text,
    user_id text not null,
    meta    json,
    constraint idx_16762_sqlite_autoindex_tag_1
        primary key (id, user_id)
);

create table if not exists file
(
    id             text,
    user_id        text,
    filename       text,
    meta           json,
    created_at     bigint,
    hash           text,
    data           json,
    updated_at     bigint,
    path           text,
    access_control json
);

create unique index if not exists idx_16767_file_id
    on file (id);

create table if not exists feedback
(
    id         text not null
        constraint idx_16772_sqlite_autoindex_feedback_1
            primary key,
    user_id    text,
    version    bigint,
    type       text,
    data       json,
    meta       json,
    snapshot   json,
    created_at bigint,
    updated_at bigint
);

create table if not exists folder
(
    id          text not null,
    parent_id   text,
    user_id     text not null,
    name        text,
    items       json,
    meta        json,
    is_expanded boolean,
    created_at  bigint,
    updated_at  bigint,
    constraint idx_16777_sqlite_autoindex_folder_1
        primary key (id, user_id)
);

create table if not exists channel
(
    id             text not null
        constraint idx_16782_sqlite_autoindex_channel_1
            primary key,
    user_id        text,
    name           text,
    description    text,
    data           json,
    meta           json,
    access_control json,
    created_at     bigint,
    updated_at     bigint,
    type           text
);

create table if not exists message
(
    id         text not null
        constraint idx_16787_sqlite_autoindex_message_1
            primary key,
    user_id    text,
    channel_id text,
    content    text,
    data       json,
    meta       json,
    created_at bigint,
    updated_at bigint,
    parent_id  text
);

create table if not exists message_reaction
(
    id         text not null
        constraint idx_16792_sqlite_autoindex_message_reaction_1
            primary key,
    user_id    text,
    message_id text,
    name       text,
    created_at bigint
);

create table if not exists channel_member
(
    id         text not null
        constraint idx_16797_sqlite_autoindex_channel_member_1
            primary key,
    channel_id text,
    user_id    text,
    created_at bigint
);

create table if not exists "user"
(
    id                              text,
    email                           text,
    role                            text,
    profile_image_url               text,
    api_key                         text,
    created_at                      bigint,
    updated_at                      bigint,
    last_active_at                  bigint,
    settings                        text,
    info                            text,
    oauth_sub                       text,
    company_id                      text,
    invite_token                    text,
    first_name                      text default 'SYSTEM'::text,
    last_name                       text default 'SYSTEM'::text,
    password_reset_token            text,
    password_reset_token_expires_at text,
    registration_code               text
);

create unique index if not exists idx_16802_user_id
    on "user" (id);

create unique index if not exists idx_16802_user_api_key
    on "user" (api_key);

create unique index if not exists idx_16802_user_oauth_sub
    on "user" (oauth_sub);

create table if not exists model_cost
(
    model_name                        text not null
        constraint idx_16809_sqlite_autoindex_model_cost_1
            primary key,
    cost_per_million_input_tokens     double precision,
    cost_per_million_output_tokens    double precision,
    cost_per_image                    double precision,
    cost_per_minute                   double precision,
    cost_per_million_characters       double precision,
    cost_per_million_reasoning_tokens double precision,
    cost_per_thousand_search_queries  double precision
);

create table if not exists stripe_payment_history
(
    id                    text not null
        constraint idx_16814_sqlite_autoindex_stripe_payment_history_1
            primary key,
    stripe_transaction_id text,
    company_id            text,
    user_id               text,
    description           text                     default 'Standard Subscription Charge'::text,
    charged_amount        numeric(10, 2)           default 15.00,
    currency              text                     default 'EUR'::text,
    payment_status        text,
    payment_method        text,
    payment_date          timestamp with time zone default CURRENT_TIMESTAMP,
    created_at            timestamp with time zone default CURRENT_TIMESTAMP,
    updated_at            timestamp with time zone default CURRENT_TIMESTAMP,
    payment_metadata      json
);

create unique index if not exists idx_16814_sqlite_autoindex_stripe_payment_history_2
    on stripe_payment_history (stripe_transaction_id);

create table if not exists prompt
(
    id             bigint not null
        constraint idx_16825_prompt_pkey
            primary key,
    command        text,
    user_id        text,
    title          text,
    content        text,
    timestamp      bigint,
    access_control json,
    meta           text,
    prebuilt       boolean,
    description    text,
    company_id     text default 'system'::text
);

create unique index if not exists idx_16825_prompt_command
    on prompt (command);

create table if not exists model
(
    id             text,
    user_id        text,
    base_model_id  text,
    name           text,
    meta           text,
    params         text,
    created_at     bigint,
    updated_at     bigint,
    access_control json,
    is_active      boolean default true,
    company_id     text    default 'system'::text
);

create unique index if not exists idx_16831_model_id
    on model (id);

create table if not exists config
(
    id         bigint not null
        constraint idx_16838_config_pkey
            primary key,
    data       json,
    version    bigint,
    created_at timestamp with time zone default CURRENT_TIMESTAMP,
    updated_at timestamp with time zone default CURRENT_TIMESTAMP,
    company_id text                     default 'DEFAULT'::text
);

create table if not exists "group"
(
    id          text not null
        constraint idx_16846_sqlite_autoindex_group_1
            primary key,
    name        text,
    description text,
    data        json,
    meta        json,
    permissions json,
    user_ids    json,
    created_at  bigint,
    updated_at  bigint,
    company_id  text
);

create table if not exists knowledge
(
    id             text not null
        constraint idx_16851_sqlite_autoindex_knowledge_1
            primary key,
    user_id        text,
    name           text,
    description    text,
    data           json,
    meta           json,
    created_at     bigint,
    updated_at     bigint,
    access_control json,
    company_id     text
);

create table if not exists company
(
    id                        text not null
        constraint idx_16856_sqlite_autoindex_company_1
            primary key,
    name                      text,
    profile_image_url         text,
    default_model             text,
    allowed_models            text,
    credit_balance            double precision,
    flex_credit_balance       double precision,
    auto_recharge             boolean,
    credit_card_number        text,
    size                      text,
    industry                  text,
    team_function             text,
    stripe_customer_id        text,
    budget_mail_80_sent       boolean,
    budget_mail_100_sent      boolean,
    subscription_not_required boolean,
    next_credit_charge_check  bigint
);

create table if not exists completion
(
    id                    text not null
        constraint idx_16861_sqlite_autoindex_completion_1
            primary key,
    user_id               text,
    chat_id               text,
    model                 text,
    credits_used          double precision,
    created_at            bigint,
    time_saved_in_seconds double precision
);

create table if not exists bookmarked_assistants
(
    user_id  text not null,
    model_id text not null,
    constraint idx_16866_sqlite_autoindex_bookmarked_assistants_1
        primary key (user_id, model_id)
);

create table if not exists bookmarked_prompts
(
    user_id        text not null,
    prompt_command text not null,
    constraint idx_16871_sqlite_autoindex_bookmarked_prompts_1
        primary key (user_id, prompt_command)
);

create table if not exists user_model_bookmark
(
    user_id  text not null,
    model_id text not null,
    constraint idx_16876_sqlite_autoindex_user_model_bookmark_1
        primary key (user_id, model_id)
);

create table if not exists user_prompt_bookmark
(
    user_id        text not null,
    prompt_command text not null,
    constraint idx_16881_sqlite_autoindex_user_prompt_bookmark_1
        primary key (user_id, prompt_command)
);

create table if not exists domain
(
    id                  text not null
        constraint idx_16886_sqlite_autoindex_domain_1
            primary key,
    company_id          text,
    domain_fqdn         text,
    dns_approval_record text,
    ownership_approved  boolean
);

create unique index if not exists idx_16886_sqlite_autoindex_domain_2
    on domain (domain_fqdn);
        """)
    )

def downgrade() -> None:
    pass
