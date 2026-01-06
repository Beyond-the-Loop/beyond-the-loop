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
CREATE TABLE IF NOT EXISTS "auth" ("id" VARCHAR(255) NOT NULL, "email" VARCHAR(255) NOT NULL, "password" TEXT NOT NULL, "active" INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS channel (
	id TEXT NOT NULL PRIMARY KEY UNIQUE, 
	user_id TEXT, 
	name TEXT, 
	description TEXT, 
	data JSON, 
	meta JSON, 
	access_control JSON, 
	created_at BIGINT, 
	updated_at BIGINT,
    type TEXT
);

CREATE TABLE IF NOT EXISTS channel_member (
	id TEXT NOT NULL PRIMARY KEY UNIQUE, 
	channel_id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	created_at BIGINT
);

CREATE TABLE IF NOT EXISTS "chat" (
    "id" VARCHAR(255) NOT NULL,
    "user_id" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL NOT NULL,
    "share_id" VARCHAR(255),
    "archived" INTEGER NOT NULL,
    "created_at" TIMESTAMP NOT NULL,
    "updated_at" TIMESTAMP NOT NULL,
    chat JSON,
    pinned BOOLEAN,
    meta JSON DEFAULT '{}' NOT NULL,
    folder_id TEXT);

CREATE TABLE IF NOT EXISTS "chatidtag" (
    "id" VARCHAR(255) NOT NULL,
    "tag_name" VARCHAR(255) NOT NULL,
    "chat_id" VARCHAR(255) NOT NULL,
    "user_id" VARCHAR(255) NOT NULL,
    "timestamp" INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS "company" (
	id VARCHAR NOT NULL PRIMARY KEY UNIQUE, 
	name VARCHAR NOT NULL, 
	profile_image_url TEXT, 
	default_model VARCHAR, 
	allowed_models TEXT, 
	credit_balance FLOAT NOT NULL, 
	flex_credit_balance FLOAT, 
	auto_recharge BOOLEAN, 
	credit_card_number VARCHAR, 
	size VARCHAR, 
	industry VARCHAR, 
	team_function VARCHAR, 
	stripe_customer_id VARCHAR, 
	budget_mail_80_sent BOOLEAN, 
	budget_mail_100_sent BOOLEAN,
    subscription_not_required BOOLEAN,
    next_credit_charge_check BIGINT 
);

CREATE TABLE IF NOT EXISTS feedback (
	id TEXT NOT NULL PRIMARY KEY, 
	user_id TEXT, 
	version BIGINT, 
	type TEXT, 
	data JSON, 
	meta JSON, 
	snapshot JSON, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS "file" (
	id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	filename TEXT NOT NULL, 
	meta JSON, 
	created_at INTEGER NOT NULL, 
	hash TEXT, 
	data JSON, 
	updated_at BIGINT, 
	path TEXT,
    access_control JSON
);

CREATE TABLE IF NOT EXISTS "folder" (
	id TEXT NOT NULL, 
	parent_id TEXT, 
	user_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	items JSON, 
	meta JSON, 
	is_expanded BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id, user_id)
);

CREATE TABLE IF NOT EXISTS "memory" (
    "id" VARCHAR(255) NOT NULL,
    "user_id" VARCHAR(255) NOT NULL,
    "content" TEXT NOT NULL,
    "updated_at" INTEGER NOT NULL,
    "created_at" INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS message (
	id TEXT NOT NULL PRIMARY KEY UNIQUE,
	user_id TEXT, 
	channel_id TEXT, 
	content TEXT, 
	data JSON, 
	meta JSON, 
	created_at BIGINT, 
	updated_at BIGINT, parent_id TEXT
);

CREATE TABLE IF NOT EXISTS message_reaction (
	id TEXT NOT NULL PRIMARY KEY UNIQUE,
	user_id TEXT NOT NULL, 
	message_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	created_at BIGINT
);
    
CREATE TABLE IF NOT EXISTS "model_cost" (
	model_name VARCHAR(255) NOT NULL PRIMARY KEY UNIQUE,
    cost_per_million_input_tokens FLOAT,
    cost_per_million_output_tokens FLOAT,
    cost_per_image FLOAT,
    cost_per_minute FLOAT,
    cost_per_million_characters FLOAT,
    cost_per_million_reasoning_tokens FLOAT,
    cost_per_thousand_search_queries FLOAT 
);
    
CREATE TABLE IF NOT EXISTS "tag" (
	id VARCHAR(255) NOT NULL,
	name VARCHAR(255) NOT NULL, 
	user_id VARCHAR(255) NOT NULL, 
	meta JSON, 
	CONSTRAINT pk_id_user_id PRIMARY KEY (id, user_id)
);

CREATE TABLE IF NOT EXISTS "migratehistory" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "migrated_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "user" (
	id VARCHAR(255) NOT NULL PRIMARY KEY, 
	email VARCHAR(255) NOT NULL, 
	role VARCHAR(255) NOT NULL, 
	profile_image_url TEXT NOT NULL, 
	api_key VARCHAR(255), 
	created_at INTEGER NOT NULL, 
	updated_at INTEGER NOT NULL, 
	last_active_at INTEGER NOT NULL, 
	settings TEXT, 
	info TEXT, 
	oauth_sub TEXT, 
	company_id VARCHAR NOT NULL,
    invite_token VARCHAR,
    first_name VARCHAR(255) DEFAULT 'SYSTEM' NOT NULL,
    last_name VARCHAR(255) DEFAULT 'SYSTEM' NOT NULL,
    password_reset_token VARCHAR,
    password_reset_token_expires_at VARCHAR,
    registration_code VARCHAR
);

CREATE TABLE IF NOT EXISTS "model" (
	id TEXT NOT NULL PRIMARY KEY, 
	user_id TEXT, 
	base_model_id TEXT, 
	name TEXT NOT NULL, 
	meta TEXT NOT NULL, 
	params TEXT NOT NULL, 
	created_at INTEGER NOT NULL, 
	updated_at INTEGER NOT NULL, 
	access_control JSON, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	company_id VARCHAR DEFAULT 'system' NOT NULL, 
	CONSTRAINT fk_user_company_id FOREIGN KEY(company_id) REFERENCES company (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "prompt" (
	id INTEGER NOT NULL PRIMARY KEY, 
	command VARCHAR(255) NOT NULL UNIQUE, 
	user_id VARCHAR(255) NOT NULL, 
	title TEXT NOT NULL, 
	content TEXT NOT NULL, 
	timestamp INTEGER NOT NULL, 
	access_control JSON, 
	meta TEXT, 
	prebuilt BOOLEAN, 
	description VARCHAR, 
	company_id VARCHAR DEFAULT 'system' NOT NULL, 
	CONSTRAINT fk_user_company_id FOREIGN KEY(company_id) REFERENCES company (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stripe_payment_history (
	id VARCHAR NOT NULL, 
	stripe_transaction_id VARCHAR NOT NULL, 
	company_id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	description TEXT DEFAULT 'Standard Subscription Charge' NOT NULL, 
	charged_amount DECIMAL(10, 2) DEFAULT '15.00' NOT NULL, 
	currency VARCHAR DEFAULT 'EUR' NOT NULL, 
	payment_status VARCHAR NOT NULL, 
	payment_method VARCHAR, 
	payment_date TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP), 
	updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP), 
	payment_metadata JSON, 
	PRIMARY KEY (id), 
	UNIQUE (id), 
	UNIQUE (stripe_transaction_id), 
	FOREIGN KEY(company_id) REFERENCES company (id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE IF NOT EXISTS user_model_bookmark (
	user_id VARCHAR NOT NULL, 
	model_id VARCHAR NOT NULL, 
	PRIMARY KEY (user_id, model_id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_id) REFERENCES model (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_prompt_bookmark (
	user_id VARCHAR NOT NULL, 
	prompt_command VARCHAR NOT NULL, 
	PRIMARY KEY (user_id, prompt_command), 
	FOREIGN KEY(user_id) REFERENCES "user" (id) ON DELETE CASCADE, 
	FOREIGN KEY(prompt_command) REFERENCES prompt (command) ON DELETE CASCADE
);
    
CREATE TABLE IF NOT EXISTS "completion" (
	id VARCHAR NOT NULL, 
	user_id VARCHAR, 
	chat_id VARCHAR, 
	model TEXT, 
	credits_used FLOAT NOT NULL, 
	created_at BIGINT, 
	time_saved_in_seconds FLOAT, 
	PRIMARY KEY (id), 
	UNIQUE (id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS "config" (
	id INTEGER NOT NULL, 
	data JSON NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP), 
	company_id VARCHAR DEFAULT 'DEFAULT' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_config_company_id FOREIGN KEY(company_id) REFERENCES company (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "document" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "collection_name" VARCHAR(255) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "content" TEXT,
    "user_id" VARCHAR(255) NOT NULL,
    "timestamp" INTEGER NOT NULL NOT NULL
);

CREATE TABLE IF NOT EXISTS domain (
	id TEXT NOT NULL, 
	company_id TEXT NOT NULL, 
	domain_fqdn TEXT NOT NULL, 
	dns_approval_record TEXT NOT NULL, 
	ownership_approved BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (id), 
	UNIQUE (domain_fqdn), 
	FOREIGN KEY(company_id) REFERENCES company (id) ON DELETE CASCADE, 
	UNIQUE (domain_fqdn)
);
    
CREATE TABLE IF NOT EXISTS "group" (
	id TEXT NOT NULL, 
	name TEXT, 
	description TEXT, 
	data JSON, 
	meta JSON, 
	permissions JSON, 
	user_ids JSON, 
	created_at BIGINT, 
	updated_at BIGINT, 
	company_id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_group_company_id FOREIGN KEY(company_id) REFERENCES company (id), 
	UNIQUE (id)
);

CREATE TABLE IF NOT EXISTS "knowledge" (
	id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	description TEXT, 
	data JSON, 
	meta JSON, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT, 
	access_control JSON, 
	company_id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_knowledge_company_id FOREIGN KEY(company_id) REFERENCES company (id)
);
    """)
    )

def downgrade() -> None:
    pass
