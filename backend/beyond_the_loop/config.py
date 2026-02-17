import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Generic, TypeVar
from urllib.parse import urlparse

import chromadb
from sqlalchemy import JSON, Column, DateTime, Integer, func, String

from open_webui.env import (
    DATA_DIR,
    FRONTEND_BUILD_DIR,
    OFFLINE_MODE,
    OPEN_WEBUI_DIR,
    log,
)
from open_webui.internal.db import Base, get_db
from beyond_the_loop.socket.main import COMPANY_CONFIG_CACHE


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

####################################
# Config helpers
####################################


# Function to run the alembic migrations
def run_migrations():
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(OPEN_WEBUI_DIR / "alembic.ini")

        # Set the script location dynamically
        migrations_path = OPEN_WEBUI_DIR / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_path))

        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        print(f"Error: {e}")


run_migrations()


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    company_id = Column(String, nullable=False)


def load_json_config():
    with open(f"{DATA_DIR}/config.json", "r") as file:
        return json.load(file)


def save_to_db(data, company_id):
    with get_db() as db:
        existing_config = db.query(Config).filter_by(company_id=company_id).first()
        if not existing_config:
            new_config = Config(data=data, version=0, company_id=company_id)
            db.add(new_config)
        else:
            existing_config.data = data
            existing_config.updated_at = datetime.now()
            db.add(existing_config)
        db.commit()


def reset_config(company_id):
    with get_db() as db:
        db.query(Config).filter_by(company_id=company_id).delete()
        db.commit()


DEFAULT_CONFIG = {
    "concurrent_requests": 10,
    "rag": {
        "youtube_loader_language": ["en"],
        "youtube_loader_proxy_url": "",
        "enable_web_loader_ssl_verification": False,
        "web": {
            "search": {
                "enable": True,
                "concurrent_requests": 10,
            }
        },
        "template": "### Task:\nRespond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.\n\n### Guidelines:\n- If you don't know the answer, clearly state that.\n- If uncertain, ask the user for clarification.\n- Respond in the same language as the user's query.\n- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.\n- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.\n- **Only include inline citations using [source_id] when a <source_id> tag is explicitly provided in the context.**  \n- Do not cite if the <source_id> tag is not provided in the context.  \n- Do not use XML tags in your response.\n- Ensure citations are concise and directly related to the information provided.\n\n### Example of Citation:\nIf the user asks about a specific topic and the information is found in \"whitepaper.pdf\" with a provided <source_id>, the response should include the citation like so:  \n* \"According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf].\"\nIf no <source_id> is present, the response should omit the citation.\n\n### Output:\nProvide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.\n\n<context>\n{{CONTEXT}}\n</context>\n\n<user_query>\n{{QUERY}}\n</user_query>\n",
        "top_k": 10,
        "relevance_threshold": 0.0,
        "enable_hybrid_search": True,
        "embedding_engine": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_batch_size": 2048,
        "reranking_model": "",
        "file": {"max_size": None, "max_count": None},
        "CONTENT_EXTRACTION_ENGINE": "",
        "text_splitter": "",
        "chunk_size": 1000,
        "chunk_overlap": 100,
    },
    "google_drive": {"enable": False},
    "audio": {
        "tts": {
            "engine": "openai",
            "model": "tts-1",
            "voice": "alloy",
            "split_on": "punctuation"
        },
        "stt": {
            "engine": "openai",
            "model": "whisper-1"
        },
    },
    "image_generation": {
        "engine": "flux",
        "enable": True,
        "model": "flux-kontext-max",
        "size": "1024x1024"
    },
    "data": {
        "chat_retention_days": 90,
    }
}

def get_config(company_id):
    # If company_id is None, return the default config directly
    if company_id is None:
        return DEFAULT_CONFIG

    cached = COMPANY_CONFIG_CACHE.get(company_id)

    with get_db() as db:
        config_entry = db.query(Config).filter_by(company_id=company_id).order_by(Config.id.desc()).first()

        if not config_entry and not cached:
            # If no config exists for this company, return the default config
            return DEFAULT_CONFIG

        if cached:
            return cached
        else:
            COMPANY_CONFIG_CACHE[company_id] = config_entry.data
            return config_entry.data


# Initialize with the default config
CONFIG_DATA = DEFAULT_CONFIG


def get_config_value(config_path: str, company_id):
    path_parts = config_path.split(".")
    cur_config = get_config(company_id)
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


PERSISTENT_CONFIG_REGISTRY = []


def save_config(config, company_id):
    # If company_id is None, we can't save to the database (company_id is required)
    if company_id is None:
        return False

    if company_id in COMPANY_CONFIG_CACHE:
        del COMPANY_CONFIG_CACHE[company_id]

    global CONFIG_DATA
    global PERSISTENT_CONFIG_REGISTRY
    try:
        save_to_db(config, company_id)

        # Trigger updates on all registered PersistentConfig entries
        for config_entry in PERSISTENT_CONFIG_REGISTRY:
            if hasattr(config_entry, "update"):
                config_entry.update(company_id)

        return True
    except Exception as e:
        log.error(f"Error saving config: {e}")
        return False


T = TypeVar("T")


class PersistentConfig(Generic[T]):
    def __init__(self, env_name: str, config_path: str, env_value: T):
        self.env_name = env_name
        self.config_path = config_path
        self.env_value = env_value
        self.config_value = get_config_value(config_path, company_id=None)
        if self.config_value is not None:
            # log.info(f"'{env_name}' loaded from the default config")
            self.value = self.config_value
        else:
            self.value = env_value

        PERSISTENT_CONFIG_REGISTRY.append(self)

    def __str__(self):
        return str(self.value)

    @property
    def __dict__(self):
        raise TypeError(
            "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
        )

    def __getattribute__(self, item):
        if item == "__dict__":
            raise TypeError(
                "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
            )
        return super().__getattribute__(item)

    def update(self, company_id):
        self.config_value = get_config_value(self.config_path, company_id)

        if self.config_value is not None:
            self.value = self.config_value
            #log.info(f"Updated {self.env_name} to new value {self.value}")
        else:
            self.value = self.env_value
            #log.info(f"Updated {self.env_name} to default value {self.value}")

    def save(self, company_id):
        # If company_id is None, we can't save to the database
        if company_id is None:
            return

        #log.info(f"Saving '{self.env_name}' to the database")
        path_parts = self.config_path.split(".")

        # Get the full config
        full_config = get_config(company_id)
        
        # Create a reference to navigate through the config
        current = full_config
        
        # Navigate to the correct nested location
        for key in path_parts[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
            
        # Update the specific value
        current[path_parts[-1]] = self.value
        
        # Save the entire updated config
        save_config(full_config, company_id)
        self.config_value = self.value


class AppConfig:
    def __init__(self):
        super().__setattr__("_state", {})
        super().__setattr__("_current_company_id", None)

    def __setattr__(self, key, value):
        if isinstance(value, PersistentConfig):
            self._state[key] = value
        else:
            self._state[key].value = value
            self._state[key].save(self._current_company_id)

    def __getattr__(self, key):
        return self._state[key].value

    # Set the current company ID for this config instance and update all config values
    def set_company_id(self, company_id: str):
        super().__setattr__("_current_company_id", company_id)
        for key, config in self._state.items():
            if hasattr(config, "update"):
                config.update(company_id)

    # Get the current company ID for this config instance
    def get_company_id(self):
        return self._current_company_id

####################################
# WEBUI_AUTH (Required for security)
####################################

JWT_EXPIRES_IN = PersistentConfig(
    "JWT_EXPIRES_IN", "auth.jwt_expiry", os.environ.get("JWT_EXPIRES_IN", "-1")
)

####################################
# OAuth config
####################################

ENABLE_OAUTH_SIGNUP = PersistentConfig(
    "ENABLE_OAUTH_SIGNUP",
    "oauth.enable_signup",
    os.environ.get("ENABLE_OAUTH_SIGNUP", "False").lower() == "true",
)

OAUTH_MERGE_ACCOUNTS_BY_EMAIL = PersistentConfig(
    "OAUTH_MERGE_ACCOUNTS_BY_EMAIL",
    "oauth.merge_accounts_by_email",
    os.environ.get("OAUTH_MERGE_ACCOUNTS_BY_EMAIL", "False").lower() == "true",
)

OAUTH_PROVIDERS = {
    "google": {}
}

GOOGLE_CLIENT_ID = PersistentConfig(
    "GOOGLE_CLIENT_ID",
    "oauth.google.client_id",
    os.environ.get("GOOGLE_CLIENT_ID", ""),
)

GOOGLE_CLIENT_SECRET = PersistentConfig(
    "GOOGLE_CLIENT_SECRET",
    "oauth.google.client_secret",
    os.environ.get("GOOGLE_CLIENT_SECRET", ""),
)


GOOGLE_OAUTH_SCOPE = PersistentConfig(
    "GOOGLE_OAUTH_SCOPE",
    "oauth.google.scope",
    os.environ.get("GOOGLE_OAUTH_SCOPE", "openid email profile"),
)

GOOGLE_REDIRECT_URI = PersistentConfig(
    "GOOGLE_REDIRECT_URI",
    "oauth.google.redirect_uri",
    os.environ.get("GOOGLE_REDIRECT_URI", ""),
)

MICROSOFT_CLIENT_ID = PersistentConfig(
    "MICROSOFT_CLIENT_ID",
    "oauth.microsoft.client_id",
    os.environ.get("MICROSOFT_CLIENT_ID", ""),
)

MICROSOFT_CLIENT_SECRET = PersistentConfig(
    "MICROSOFT_CLIENT_SECRET",
    "oauth.microsoft.client_secret",
    os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
)

MICROSOFT_CLIENT_TENANT_ID = PersistentConfig(
    "MICROSOFT_CLIENT_TENANT_ID",
    "oauth.microsoft.tenant_id",
    os.environ.get("MICROSOFT_CLIENT_TENANT_ID", ""),
)

MICROSOFT_OAUTH_SCOPE = PersistentConfig(
    "MICROSOFT_OAUTH_SCOPE",
    "oauth.microsoft.scope",
    os.environ.get("MICROSOFT_OAUTH_SCOPE", "openid email profile"),
)

MICROSOFT_REDIRECT_URI = PersistentConfig(
    "MICROSOFT_REDIRECT_URI",
    "oauth.microsoft.redirect_uri",
    os.environ.get("MICROSOFT_REDIRECT_URI", ""),
)

OAUTH_CLIENT_ID = PersistentConfig(
    "OAUTH_CLIENT_ID",
    "oauth.oidc.client_id",
    os.environ.get("OAUTH_CLIENT_ID", ""),
)

OAUTH_CLIENT_SECRET = PersistentConfig(
    "OAUTH_CLIENT_SECRET",
    "oauth.oidc.client_secret",
    os.environ.get("OAUTH_CLIENT_SECRET", ""),
)

OAUTH_SCOPES = PersistentConfig(
    "OAUTH_SCOPES",
    "oauth.oidc.scopes",
    os.environ.get("OAUTH_SCOPES", "openid email profile"),
)

OAUTH_PROVIDER_NAME = PersistentConfig(
    "OAUTH_PROVIDER_NAME",
    "oauth.oidc.provider_name",
    os.environ.get("OAUTH_PROVIDER_NAME", "SSO"),
)

OAUTH_USERNAME_CLAIM = PersistentConfig(
    "OAUTH_USERNAME_CLAIM",
    "oauth.oidc.username_claim",
    os.environ.get("OAUTH_USERNAME_CLAIM", "name"),
)

OAUTH_FIRST_NAME_CLAIM = PersistentConfig(
    "OAUTH_FIRST_NAME_CLAIM",
    "oauth.oidc.first_name_claim",
    os.environ.get("OAUTH_FIRST_NAME_CLAIM", "given_name"),
)

OAUTH_LAST_NAME_CLAIM = PersistentConfig(
    "OAUTH_LAST_NAME_CLAIM",
    "oauth.oidc.last_name_claim",
    os.environ.get("OAUTH_LAST_NAME_CLAIM", "family_name"),
)

OAUTH_PICTURE_CLAIM = PersistentConfig(
    "OAUTH_PICTURE_CLAIM",
    "oauth.oidc.avatar_claim",
    os.environ.get("OAUTH_PICTURE_CLAIM", "picture"),
)

OAUTH_EMAIL_CLAIM = PersistentConfig(
    "OAUTH_EMAIL_CLAIM",
    "oauth.oidc.email_claim",
    os.environ.get("OAUTH_EMAIL_CLAIM", "email"),
)

OAUTH_MICROSOFT_PREFERRED_EMAIL_CLAIM = PersistentConfig(
    "OAUTH_MICROSOFT_PREFERRED_EMAIL_CLAIM",
    "oauth.oidc.microsoft.preferred_email_claim",
    os.environ.get("OAUTH_MICROSOFT_PREFERRED_EMAIL_CLAIM", "preferred_username"),
)

OAUTH_GROUPS_CLAIM = PersistentConfig(
    "OAUTH_GROUPS_CLAIM",
    "oauth.oidc.group_claim",
    os.environ.get("OAUTH_GROUP_CLAIM", "groups"),
)

ENABLE_OAUTH_ROLE_MANAGEMENT = PersistentConfig(
    "ENABLE_OAUTH_ROLE_MANAGEMENT",
    "oauth.enable_role_mapping",
    os.environ.get("ENABLE_OAUTH_ROLE_MANAGEMENT", "False").lower() == "true",
)

ENABLE_OAUTH_GROUP_MANAGEMENT = PersistentConfig(
    "ENABLE_OAUTH_GROUP_MANAGEMENT",
    "oauth.enable_group_mapping",
    os.environ.get("ENABLE_OAUTH_GROUP_MANAGEMENT", "False").lower() == "true",
)

OAUTH_ROLES_CLAIM = PersistentConfig(
    "OAUTH_ROLES_CLAIM",
    "oauth.roles_claim",
    os.environ.get("OAUTH_ROLES_CLAIM", "roles"),
)

OAUTH_ALLOWED_ROLES = PersistentConfig(
    "OAUTH_ALLOWED_ROLES",
    "oauth.allowed_roles",
    [
        role.strip()
        for role in os.environ.get("OAUTH_ALLOWED_ROLES", "user,admin").split(",")
    ],
)

OAUTH_ADMIN_ROLES = PersistentConfig(
    "OAUTH_ADMIN_ROLES",
    "oauth.admin_roles",
    [role.strip() for role in os.environ.get("OAUTH_ADMIN_ROLES", "admin").split(",")],
)

OAUTH_ALLOWED_DOMAINS = PersistentConfig(
    "OAUTH_ALLOWED_DOMAINS",
    "oauth.allowed_domains",
    [
        domain.strip()
        for domain in os.environ.get("OAUTH_ALLOWED_DOMAINS", "*").split(",")
    ],
)


def load_oauth_providers():
    OAUTH_PROVIDERS.clear()
    if GOOGLE_CLIENT_ID.value and GOOGLE_CLIENT_SECRET.value:

        def google_oauth_register(client):
            client.register(
                name="google",
                client_id=GOOGLE_CLIENT_ID.value,
                client_secret=GOOGLE_CLIENT_SECRET.value,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": GOOGLE_OAUTH_SCOPE.value},
                redirect_uri=GOOGLE_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["google"] = {
            "redirect_uri": GOOGLE_REDIRECT_URI.value,
            "register": google_oauth_register,
        }

    if (
        MICROSOFT_CLIENT_ID.value
        and MICROSOFT_CLIENT_SECRET.value
        and MICROSOFT_CLIENT_TENANT_ID.value
    ):

        def microsoft_oauth_register(client):
            client.register(
                name="microsoft",
                client_id=MICROSOFT_CLIENT_ID.value,
                client_secret=MICROSOFT_CLIENT_SECRET.value,
                server_metadata_url=f"https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration?appid={MICROSOFT_CLIENT_ID.value}",
                client_kwargs={
                    "scope": MICROSOFT_OAUTH_SCOPE.value,
                },
                redirect_uri=MICROSOFT_REDIRECT_URI.value,
            )

        OAUTH_PROVIDERS["microsoft"] = {
            "redirect_uri": MICROSOFT_REDIRECT_URI.value,
            "picture_url": "https://graph.microsoft.com/v1.0/me/photo/$value",
            "register": microsoft_oauth_register,
        }

load_oauth_providers()

####################################
# Static DIR
####################################

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static")).resolve()

frontend_favicon = FRONTEND_BUILD_DIR / "static" / "favicon.png"

if frontend_favicon.exists():
    try:
        shutil.copyfile(frontend_favicon, STATIC_DIR / "favicon.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
else:
    logging.warning(f"Frontend favicon not found at {frontend_favicon}")

frontend_splash = FRONTEND_BUILD_DIR / "static" / "splash.png"

if frontend_splash.exists():
    try:
        shutil.copyfile(frontend_splash, STATIC_DIR / "splash.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
else:
    logging.warning(f"Frontend splash not found at {frontend_splash}")

####################################
# STORAGE PROVIDER
####################################

STORAGE_PROVIDER = "gcs"

S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", None)
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", None)
S3_REGION_NAME = os.environ.get("S3_REGION_NAME", None)
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", None)
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", None)

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "bchat-uploads-dev")

GOOGLE_APPLICATION_CREDENTIALS_JSON = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS_JSON", None
)

####################################
# File Upload DIR
####################################

UPLOAD_DIR = f"{DATA_DIR}/uploads"
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


####################################
# Cache DIR
####################################

CACHE_DIR = f"{DATA_DIR}/cache"
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

####################################
# OPENAI_API
####################################

ENABLE_OPENAI_API = PersistentConfig(
    "ENABLE_OPENAI_API",
    "openai.enable",
    os.environ.get("ENABLE_OPENAI_API", "True").lower() == "true",
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL", "")


if OPENAI_API_BASE_URL == "":
    OPENAI_API_BASE_URL = "https://api.openai.com/v1"

OPENAI_API_KEYS = os.environ.get("OPENAI_API_KEYS", "")
OPENAI_API_KEYS = OPENAI_API_KEYS if OPENAI_API_KEYS != "" else OPENAI_API_KEY

OPENAI_API_KEYS = [url.strip() for url in OPENAI_API_KEYS.split(";")]
OPENAI_API_KEYS = PersistentConfig(
    "OPENAI_API_KEYS", "openai.api_keys", OPENAI_API_KEYS
)

OPENAI_API_BASE_URLS = os.environ.get("OPENAI_API_BASE_URLS", "")
OPENAI_API_BASE_URLS = (
    OPENAI_API_BASE_URLS if OPENAI_API_BASE_URLS != "" else OPENAI_API_BASE_URL
)

OPENAI_API_BASE_URLS = [
    url.strip() if url != "" else "https://api.openai.com/v1"
    for url in OPENAI_API_BASE_URLS.split(";")
]
OPENAI_API_BASE_URLS = PersistentConfig(
    "OPENAI_API_BASE_URLS", "openai.api_base_urls", OPENAI_API_BASE_URLS
)

OPENAI_API_CONFIGS = PersistentConfig(
    "OPENAI_API_CONFIGS",
    "openai.api_configs",
    {},
)

# Get the actual OpenAI API key based on the base URL
OPENAI_API_KEY = ""
try:
    OPENAI_API_KEY = OPENAI_API_KEYS.value[
        OPENAI_API_BASE_URLS.value.index("https://api.openai.com/v1")
    ]
except Exception:
    pass
OPENAI_API_BASE_URL = "https://api.openai.com/v1"

####################################
# WEBUI
####################################


WEBUI_URL = PersistentConfig(
    "WEBUI_URL", "webui.url", os.environ.get("WEBUI_URL", "http://localhost:3000")
)

DEFAULT_LOCALE = PersistentConfig(
    "DEFAULT_LOCALE",
    "ui.default_locale",
    os.environ.get("DEFAULT_LOCALE", ""),
)

DEFAULT_PROMPT_SUGGESTIONS = PersistentConfig(
    "DEFAULT_PROMPT_SUGGESTIONS",
    "ui.prompt_suggestions",
    [
        {
            "title": ["Help me study", "vocabulary for a college entrance exam"],
            "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option.",
        },
        {
            "title": ["Give me ideas", "for what to do with my kids' art"],
            "content": "What are 5 creative things I could do with my kids' art? I don't want to throw them away, but it's also so much clutter.",
        },
        {
            "title": ["Tell me a fun fact", "about the Roman Empire"],
            "content": "Tell me a random fun fact about the Roman Empire",
        },
        {
            "title": ["Show me a code snippet", "of a website's sticky header"],
            "content": "Show me a code snippet of a website's sticky header in CSS and JavaScript.",
        },
        {
            "title": [
                "Explain options trading",
                "if I'm familiar with buying and selling stocks",
            ],
            "content": "Explain options trading in simple terms if I'm familiar with buying and selling stocks.",
        },
        {
            "title": ["Overcome procrastination", "give me tips"],
            "content": "Could you start by asking me about instances when I procrastinate the most and then give me some suggestions to overcome it?",
        },
    ],
)

ENABLE_CHANNELS = PersistentConfig(
    "ENABLE_CHANNELS",
    "channels.enable",
    os.environ.get("ENABLE_CHANNELS", "False").lower() == "true",
)

ENABLE_COMMUNITY_SHARING = PersistentConfig(
    "ENABLE_COMMUNITY_SHARING",
    "ui.enable_community_sharing",
    os.environ.get("ENABLE_COMMUNITY_SHARING", "True").lower() == "true",
)

ENABLE_MESSAGE_RATING = PersistentConfig(
    "ENABLE_MESSAGE_RATING",
    "ui.enable_message_rating",
    os.environ.get("ENABLE_MESSAGE_RATING", "True").lower() == "true",
)

HIDE_MODEL_LOGO_IN_CHAT = PersistentConfig(
    "HIDE_MODEL_LOGO_IN_CHAT",
    "ui.hide_model_logo_in_chat",
    os.environ.get("HIDE_MODEL_LOGO_IN_CHAT", "False").lower() == "true",
)


CUSTOM_USER_NOTICE = PersistentConfig(
    "CUSTOM_USER_NOTICE",
    "ui.custom_user_notice",
    os.environ.get("CUSTOM_USER_NOTICE", None),
)


def validate_cors_origins(origins):
    for origin in origins:
        if origin != "*":
            validate_cors_origin(origin)


def validate_cors_origin(origin):
    parsed_url = urlparse(origin)

    # Check if the scheme is either http or https
    if parsed_url.scheme not in ["http", "https"]:
        raise ValueError(
            f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. Only 'http' and 'https' are allowed."
        )

    # Ensure that the netloc (domain + port) is present, indicating it's a valid URL
    if not parsed_url.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


# For production, you should only need one host as
# fastapi serves the svelte-kit built frontend and backend from the same host and port.
# To test CORS_ALLOW_ORIGIN locally, you can set something like
# CORS_ALLOW_ORIGIN=http://localhost:5173;http://localhost:8080
# in your .env file depending on your frontend port, 5173 in this case.
CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*").split(";")

if "*" in CORS_ALLOW_ORIGIN:
    log.warning(
        "\n\nWARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.\n"
    )

validate_cors_origins(CORS_ALLOW_ORIGIN)

####################################
# TASKS
####################################

TITLE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "task.title.prompt_template",
    os.environ.get("TITLE_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a concise, 3-5 word title without any emojis (this is important) summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Write the title in the chat's primary language; default to German if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "Stock Market Trends" },
- { "title": "Perfect Chocolate Chip Recipe" },
- { "title": "Evolution of Music Streaming" },
- { "title": "Remote Work Productivity Tips" },
- { "title": "Artificial Intelligence in Healthcare" },
- { "title": "Video Game Development Insights" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

TAGS_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TAGS_GENERATION_PROMPT_TEMPLATE",
    "task.tags.prompt_template",
    os.environ.get("TAGS_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE",
    "task.image.prompt_template",
    os.environ.get("IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a detailed prompt for am image generation task based on the given language and context. Describe the image as if you were explaining it to someone who cannot see it. Include relevant details, colors, shapes, and any other important elements.

### Guidelines:
- Be descriptive and detailed, focusing on the most important aspects of the image.
- Avoid making assumptions or adding information not present in the image.
- Use the chat's primary language; default to English if multilingual.
- If the image is too complex, focus on the most prominent elements.

### Output:
Strictly return in JSON format:
{
    "prompt": "Your detailed description here."
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

ENABLE_TAGS_GENERATION = PersistentConfig(
    "ENABLE_TAGS_GENERATION",
    "task.tags.enable",
    os.environ.get("ENABLE_TAGS_GENERATION", "False").lower() == "true",
)

WEBHOOK_URL = PersistentConfig(
    "WEBHOOK_URL", "webhook_url", os.environ.get("WEBHOOK_URL", "")
)

WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Please generate 1-3 web search queries for me that help me to answer the user's question.
For each of the web search queries I want you to tell me a result_limit that determines how many web pages are scraped for the query.

### Guidelines:
- Use the language given in the user's prompt; default to English if unclear.
- Today's date is: {{CURRENT_DATE}}.
- Do **not** wrap URLs in phrases like “search for” or “analyze”.
- IMPORTANT: Generate at least one query and result_limit should also always be at least one! In general be very conservative so only create more than one web search query if you really think it is necessary to answer the question.

### URL Extraction Rules:
- Scan messages for URLs (http:// or https://)
- If found, insert the URL (unaltered) as the **first element** your response

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

RAG_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Analyze the chat history to generate search queries that retrieve **relevant information from a local RAG (Retrieval-Augmented Generation) document store**. The goal is to identify **semantically rich, specific, and content-focused** queries rather than broad web searches.

### Guidelines:
- Respond **EXCLUSIVELY** with a JSON object. No commentary or explanations.
- Response format: { "queries": ["query1", "query2"] }
- Focus on **semantic retrieval** — generate queries that align with document embeddings and maximize recall of relevant context.
- Prefer **topic-specific, question-style**, or **phrase-based** queries that match possible file content.
- If no meaningful retrieval is possible, return: { "queries": [] }
- Use the chat’s language; default to English if unclear.
- Today's date is: {{CURRENT_DATE}}.

### Output:
{
  "queries": ["query1", "query2"]
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""


CODE_INTERPRETER_PROMPT = """
#### Tools Available that you have to use:

1. **Code Interpreter**: `<code_interpreter type="code" lang="python"></code_interpreter>`
   - You are a senior Python developer. You write a single script that implements the user's task. You have only on chance to write the script and there is no chance for asking questions. Use the information provided by the user to solve the task.
   - The Python code you write can incorporate all packages from the standard python library and packages from this list:
        annotated-doc==0.0.4
        annotated-types==0.7.0
        anyio==4.11.0
        cachetools==6.2.2
        certifi==2025.11.12
        charset-normalizer==3.4.4
        click==8.3.1
        et_xmlfile==2.0.0
        fastapi==0.121.2
        google-api-core==2.28.1
        google-auth==2.43.0
        google-cloud-core==2.5.0
        google-cloud-storage==2.19.0
        google-crc32c==1.7.1
        google-resumable-media==2.7.2
        googleapis-common-protos==1.72.0
        h11==0.16.0
        httptools==0.7.1
        idna==3.11
        lxml==6.0.2
        matplotlib==3.10.7
        openpyxl==3.1.5
        pandas==2.3.3
        pillow==12.0.0
        proto-plus==1.26.1
        protobuf==6.33.1
        pyasn1==0.6.1
        pyasn1_modules==0.4.2
        pydantic==2.12.4
        pydantic_core==2.41.5
        pypdf==6.3.0
        python-docx==1.2.0
        python-dotenv==1.2.1
        PyYAML==6.0.3
        reportlab==4.4.4
        requests==2.32.5
        rsa==4.9.1
        sniffio==1.3.1
        starlette==0.49.3
        typing-inspection==0.4.2
        typing_extensions==4.15.0
        urllib3==2.5.0
        uvicorn==0.38.0
        uvloop==0.22.1
        watchfiles==1.1.1
        websockets==15.0.1
   - Use this flexibility to **think outside the box, craft elegant solutions, and harness Python's full potential**.
   - Make sure it is always valid Python code that you create. No syntax errors (especially no SyntaxError: unterminated triple-quoted string literal)!
   - By default, you may create files when needed, using simple colors and minimal design. However, if the user explicitly asks for a different style, layout, or level of complexity, their instructions override this default.
   - When creating a file, always use only the filename without any path. The file should be created in the current working directory. Do not use subfolders or absolute paths unless explicitly requested. Example: 'text.txt' instead of 'tmp/text.txt' or '/home/user/text.txt'.
   - Be careful when creating files like pdfs with emojis or smileys, some Python libraries are not supporting it.
   - To use it, **you must enclose your code within `<code_interpreter type="code" lang="python">` XML tags**. If you don't, the code won't execute. Do NOT use triple backticks.
   - All responses should be communicated in the chat's primary language, ensuring seamless understanding. If the chat is multilingual, default to English for clarity.
   - Ignore all base64 strings from the messages. They should not be part of the code.
   - When creating files with long texts as content, make sure to include the text exactly how defined in the chat and under no circumstances truncate it.

Ensure that the tools are effectively utilized to achieve the highest-quality analysis for the user.
"""

CODE_INTERPRETER_FILE_HINT_TEMPLATE = """
    The following uploaded files will be available in your current working directory when your code runs: {{file_list}}
    Open them directly by filename (for example: pandas.read_csv('data.csv')).
    Do not attempt to download files from external URLs; use these local files.
"""

CODE_INTERPRETER_SUMMARY_PROMPT = """
    Based on the most recent code execution output, write a concise wrap up to inform the user what happened: 
        - Clearly state whether the execution succeeded or failed.
        - If any file URLs are available, include a Markdown link to each of the files. Inform the user that the link is valid for 48 hours.
        - IMPORTANT! Use the **exact** link from the response. Every letter is important, don't alter it. Otherwise the user will se a 404 Error what we want to avoid.
        - Inform the user if you decided to not write the emojis or smileys in the file (e.g. because pdfs don't support it).
        - If there was an error, briefly summarize it in one sentence. If necessary generate adjusted code (Code Interpreter Tool).
"""

CODE_INTERPRETER_FAIL_PROMPT = """
    Tell the user kindly that it was not possible for you to execute the task with the code interpreter. IMPORTANT! Don't write any new code. It is over. Do not try again to solve the task. Just tell the user that he has to try again.
"""

DEFAULT_AGENT_MODEL = PersistentConfig(
    "DEFAULT_AGENT_MODEL",
    "default_agent_model",
    os.getenv("DEFAULT_AGENT_MODEL", ""),
)

####################################
# Vector Database
####################################

MODEL_ORDER_LIST = PersistentConfig(
    "MODEL_ORDER_LIST",
    "ui.model_order_list",
    [],
)

VECTOR_DB = os.environ.get("VECTOR_DB", "chroma")

# Chroma
CHROMA_DATA_PATH = f"{DATA_DIR}/vector_db"
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", chromadb.DEFAULT_TENANT)
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", chromadb.DEFAULT_DATABASE)
CHROMA_HTTP_HOST = os.environ.get("CHROMA_HTTP_HOST", "")
CHROMA_HTTP_PORT = int(os.environ.get("CHROMA_HTTP_PORT", "8000"))
CHROMA_CLIENT_AUTH_PROVIDER = os.environ.get("CHROMA_CLIENT_AUTH_PROVIDER", "")
CHROMA_CLIENT_AUTH_CREDENTIALS = os.environ.get("CHROMA_CLIENT_AUTH_CREDENTIALS", "")
# Comma-separated list of header=value pairs
CHROMA_HTTP_HEADERS = os.environ.get("CHROMA_HTTP_HEADERS", "")
if CHROMA_HTTP_HEADERS:
    CHROMA_HTTP_HEADERS = dict(
        [pair.split("=") for pair in CHROMA_HTTP_HEADERS.split(",")]
    )
else:
    CHROMA_HTTP_HEADERS = None
CHROMA_HTTP_SSL = os.environ.get("CHROMA_HTTP_SSL", "false").lower() == "true"
# this uses the model defined in the Dockerfile ENV variable. If you dont use docker or docker based deployments such as k8s, the default embedding model will be used (sentence-transformers/all-MiniLM-L6-v2)

####################################
# Information Retrieval (RAG)
####################################

# If configured, Google Drive will be available as an upload option.
ENABLE_GOOGLE_DRIVE_INTEGRATION = PersistentConfig(
    "ENABLE_GOOGLE_DRIVE_INTEGRATION",
    "google_drive.enable",
    os.getenv("ENABLE_GOOGLE_DRIVE_INTEGRATION", "False").lower() == "true",
)

GOOGLE_DRIVE_CLIENT_ID = PersistentConfig(
    "GOOGLE_DRIVE_CLIENT_ID",
    "google_drive.client_id",
    os.environ.get("GOOGLE_DRIVE_CLIENT_ID", ""),
)

GOOGLE_DRIVE_API_KEY = PersistentConfig(
    "GOOGLE_DRIVE_API_KEY",
    "google_drive.api_key",
    os.environ.get("GOOGLE_DRIVE_API_KEY", ""),
)

# RAG Content Extraction
CONTENT_EXTRACTION_ENGINE = PersistentConfig(
    "CONTENT_EXTRACTION_ENGINE",
    "rag.CONTENT_EXTRACTION_ENGINE",
    os.environ.get("CONTENT_EXTRACTION_ENGINE", "").lower(),
)

RAG_TOP_K = PersistentConfig(
    "RAG_TOP_K", "rag.top_k", int(os.environ.get("RAG_TOP_K", "3"))
)

RAG_RELEVANCE_THRESHOLD = PersistentConfig(
    "RAG_RELEVANCE_THRESHOLD",
    "rag.relevance_threshold",
    float(os.environ.get("RAG_RELEVANCE_THRESHOLD", "0.0")),
)

ENABLE_RAG_HYBRID_SEARCH = PersistentConfig(
    "ENABLE_RAG_HYBRID_SEARCH",
    "rag.enable_hybrid_search",
    os.environ.get("ENABLE_RAG_HYBRID_SEARCH", "").lower() == "true",
)

RAG_FILE_MAX_COUNT = PersistentConfig(
    "RAG_FILE_MAX_COUNT",
    "rag.file.max_count",
    (
        int(os.environ.get("RAG_FILE_MAX_COUNT"))
        if os.environ.get("RAG_FILE_MAX_COUNT")
        else None
    ),
)

RAG_FILE_MAX_SIZE = PersistentConfig(
    "RAG_FILE_MAX_SIZE",
    "rag.file.max_size",
    (
        int(os.environ.get("RAG_FILE_MAX_SIZE"))
        if os.environ.get("RAG_FILE_MAX_SIZE")
        else None
    ),
)

ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = PersistentConfig(
    "ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION",
    "rag.enable_web_loader_ssl_verification",
    os.environ.get("ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION", "True").lower() == "true",
)

RAG_EMBEDDING_ENGINE = PersistentConfig(
    "RAG_EMBEDDING_ENGINE",
    "rag.embedding_engine",
    os.environ.get("RAG_EMBEDDING_ENGINE", ""),
)

RAG_EMBEDDING_MODEL = PersistentConfig(
    "RAG_EMBEDDING_MODEL",
    "rag.embedding_model",
    os.environ.get("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)

RAG_EMBEDDING_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("RAG_EMBEDDING_MODEL_AUTO_UPDATE", "True").lower() == "true"
)

RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE", "True").lower() == "true"
)

RAG_EMBEDDING_BATCH_SIZE = PersistentConfig(
    "RAG_EMBEDDING_BATCH_SIZE",
    "rag.embedding_batch_size",
    int(
        os.environ.get("RAG_EMBEDDING_BATCH_SIZE")
        or os.environ.get("RAG_EMBEDDING_OPENAI_BATCH_SIZE", "1")
    ),
)

RAG_RERANKING_MODEL = PersistentConfig(
    "RAG_RERANKING_MODEL",
    "rag.reranking_model",
    os.environ.get("RAG_RERANKING_MODEL", ""),
)
if RAG_RERANKING_MODEL.value != "":
    log.info(f"Reranking model set: {RAG_RERANKING_MODEL.value}")

RAG_RERANKING_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("RAG_RERANKING_MODEL_AUTO_UPDATE", "True").lower() == "true"
)

RAG_RERANKING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_RERANKING_MODEL_TRUST_REMOTE_CODE", "True").lower() == "true"
)


RAG_TEXT_SPLITTER = PersistentConfig(
    "RAG_TEXT_SPLITTER",
    "rag.text_splitter",
    os.environ.get("RAG_TEXT_SPLITTER", ""),
)

CHUNK_SIZE = PersistentConfig(
    "CHUNK_SIZE", "rag.chunk_size", int(os.environ.get("CHUNK_SIZE", "1000"))
)
CHUNK_OVERLAP = PersistentConfig(
    "CHUNK_OVERLAP",
    "rag.chunk_overlap",
    int(os.environ.get("CHUNK_OVERLAP", "100")),
)

COMPLETION_ERROR_MESSAGE_PROMPT = """
You are an AI assistant generating a helpful fallback message after an upstream model request failed.
Your goal is to explain the failure in a clear and reassuring way.
- Describe the error in human-readable terms.
- Do not invent technical details.
- Do not blame the user.
- Keep the tone calm, neutral, and professional.
- If the cause is unknown, say that the system encountered an unexpected error.

IMPORTANT: If appropriate based on the error, suggest that the user try a different model.
Only make this suggestion when the error clearly indicates that the current model cannot handle the task.
"""

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [source_id] when a <source_id> tag is explicitly provided in the context.**  
- Do not cite if the <source_id> tag is not provided in the context.  
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in "whitepaper.pdf" with a provided <source_id>, the response should include the citation like so:  
* "According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf]."
If no <source_id> is present, the response should omit the citation.

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.

<context>
{{CONTEXT}}
</context>

<user_query>
{{QUERY}}
</user_query>
"""

RAG_TEMPLATE = PersistentConfig(
    "RAG_TEMPLATE",
    "rag.template",
    os.environ.get("RAG_TEMPLATE", DEFAULT_RAG_TEMPLATE),
)

RAG_OPENAI_API_BASE_URL = PersistentConfig(
    "RAG_OPENAI_API_BASE_URL",
    "rag.openai_api_base_url",
    os.getenv("RAG_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)

RAG_OPENAI_API_KEY = PersistentConfig(
    "RAG_OPENAI_API_KEY",
    "rag.openai_api_key",
    os.getenv("RAG_OPENAI_API_KEY", OPENAI_API_KEY),
)

####################################
# Images
####################################

ENABLE_IMAGE_GENERATION = PersistentConfig(
    "ENABLE_IMAGE_GENERATION",
    "image_generation.enable",
    os.environ.get("ENABLE_IMAGE_GENERATION", "").lower() == "true",
)

####################################
# Audio
####################################

# Transcription
WHISPER_MODEL = PersistentConfig(
    "WHISPER_MODEL",
    "audio.stt.whisper_model",
    os.getenv("WHISPER_MODEL", "base"),
)

WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", f"{CACHE_DIR}/whisper/models")
WHISPER_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("WHISPER_MODEL_AUTO_UPDATE", "").lower() == "true"
)


AUDIO_STT_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_STT_OPENAI_API_BASE_URL",
    "audio.stt.openai.api_base_url",
    os.getenv("AUDIO_STT_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)

AUDIO_STT_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_STT_OPENAI_API_KEY",
    "audio.stt.openai.api_key",
    os.getenv("AUDIO_STT_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_STT_ENGINE = PersistentConfig(
    "AUDIO_STT_ENGINE",
    "audio.stt.engine",
    os.getenv("AUDIO_STT_ENGINE", ""),
)

AUDIO_STT_MODEL = PersistentConfig(
    "AUDIO_STT_MODEL",
    "audio.stt.model",
    os.getenv("AUDIO_STT_MODEL", ""),
)

AUDIO_TTS_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_BASE_URL",
    "audio.tts.openai.api_base_url",
    os.getenv("AUDIO_TTS_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
AUDIO_TTS_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_KEY",
    "audio.tts.openai.api_key",
    os.getenv("AUDIO_TTS_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_TTS_API_KEY = PersistentConfig(
    "AUDIO_TTS_API_KEY",
    "audio.tts.api_key",
    os.getenv("AUDIO_TTS_API_KEY", ""),
)

AUDIO_TTS_ENGINE = PersistentConfig(
    "AUDIO_TTS_ENGINE",
    "audio.tts.engine",
    os.getenv("AUDIO_TTS_ENGINE", ""),
)


AUDIO_TTS_MODEL = PersistentConfig(
    "AUDIO_TTS_MODEL",
    "audio.tts.model",
    os.getenv("AUDIO_TTS_MODEL", "tts-1"),  # OpenAI default model
)

AUDIO_TTS_VOICE = PersistentConfig(
    "AUDIO_TTS_VOICE",
    "audio.tts.voice",
    os.getenv("AUDIO_TTS_VOICE", "alloy"),  # OpenAI default voice
)

AUDIO_TTS_SPLIT_ON = PersistentConfig(
    "AUDIO_TTS_SPLIT_ON",
    "audio.tts.split_on",
    os.getenv("AUDIO_TTS_SPLIT_ON", "punctuation"),
)

AUDIO_TTS_AZURE_SPEECH_REGION = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_REGION",
    "audio.tts.azure.speech_region",
    os.getenv("AUDIO_TTS_AZURE_SPEECH_REGION", "eastus"),
)

AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT",
    "audio.tts.azure.speech_output_format",
    os.getenv(
        "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT", "audio-24khz-160kbitrate-mono-mp3"
    ),
)


####################################
# LDAP
####################################

ENABLE_LDAP = PersistentConfig(
    "ENABLE_LDAP",
    "ldap.enable",
    os.environ.get("ENABLE_LDAP", "false").lower() == "true",
)

LDAP_SERVER_LABEL = PersistentConfig(
    "LDAP_SERVER_LABEL",
    "ldap.server.label",
    os.environ.get("LDAP_SERVER_LABEL", "LDAP Server"),
)

LDAP_SERVER_HOST = PersistentConfig(
    "LDAP_SERVER_HOST",
    "ldap.server.host",
    os.environ.get("LDAP_SERVER_HOST", "localhost"),
)

LDAP_SERVER_PORT = PersistentConfig(
    "LDAP_SERVER_PORT",
    "ldap.server.port",
    int(os.environ.get("LDAP_SERVER_PORT", "389")),
)

LDAP_ATTRIBUTE_FOR_MAIL = PersistentConfig(
    "LDAP_ATTRIBUTE_FOR_MAIL",
    "ldap.server.attribute_for_mail",
    os.environ.get("LDAP_ATTRIBUTE_FOR_MAIL", "mail"),
)

LDAP_ATTRIBUTE_FOR_USERNAME = PersistentConfig(
    "LDAP_ATTRIBUTE_FOR_USERNAME",
    "ldap.server.attribute_for_username",
    os.environ.get("LDAP_ATTRIBUTE_FOR_USERNAME", "uid"),
)

LDAP_APP_DN = PersistentConfig(
    "LDAP_APP_DN", "ldap.server.app_dn", os.environ.get("LDAP_APP_DN", "")
)

LDAP_APP_PASSWORD = PersistentConfig(
    "LDAP_APP_PASSWORD",
    "ldap.server.app_password",
    os.environ.get("LDAP_APP_PASSWORD", ""),
)

LDAP_SEARCH_BASE = PersistentConfig(
    "LDAP_SEARCH_BASE", "ldap.server.users_dn", os.environ.get("LDAP_SEARCH_BASE", "")
)

LDAP_SEARCH_FILTERS = PersistentConfig(
    "LDAP_SEARCH_FILTER",
    "ldap.server.search_filter",
    os.environ.get("LDAP_SEARCH_FILTER", ""),
)

LDAP_USE_TLS = PersistentConfig(
    "LDAP_USE_TLS",
    "ldap.server.use_tls",
    os.environ.get("LDAP_USE_TLS", "True").lower() == "true",
)

LDAP_CA_CERT_FILE = PersistentConfig(
    "LDAP_CA_CERT_FILE",
    "ldap.server.ca_cert_file",
    os.environ.get("LDAP_CA_CERT_FILE", ""),
)

LDAP_CIPHERS = PersistentConfig(
    "LDAP_CIPHERS", "ldap.server.ciphers", os.environ.get("LDAP_CIPHERS", "ALL")
)