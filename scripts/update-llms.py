import datetime
import sqlalchemy
import uuid
import json
import os

# Get the project root directory (parent of the scripts directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = (
    f"sqlite:///{os.path.join(project_root, 'backend', 'data', 'database.sqlite')}"
)

print("Updating LLMs")

db_engine = sqlalchemy.create_engine(DATABASE_URL)

with db_engine.connect() as connection:
    all_models_list = {
        "Claude 3.5 Haiku": {
            "cost": {
                "cost_per_million_input_tokens": 0.8,
                "cost_per_million_output_tokens": 4,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Claude 3.5 Sonnet": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "Claude Sonnet 4",
            "stats": "replace",
            "visibility": "show",
        },
        "Claude 3.7 Sonnet": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "Claude Sonnet 4",
            "stats": "replace",
            "visibility": "show",
        },
        "Claude Opus 4": {
            "cost": {
                "cost_per_million_input_tokens": 15,
                "cost_per_million_output_tokens": 75,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "Claude Sonnet 4": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "Gemini 2.0 Flash": {
            "cost": {
                "cost_per_million_input_tokens": 0.15,
                "cost_per_million_output_tokens": 0.6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "Google 2.5 Flash",
            "stats": "replace",
            "visibility": "show",
        },
        "Google 2.5 Flash": {
            "cost": {
                "cost_per_million_input_tokens": 0.15,
                "cost_per_million_output_tokens": 0.6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        # "Google 2.5 Flash-Lite": {
        #     "cost": {
        #         "cost_per_million_input_tokens": 0.1,
        #         "cost_per_million_output_tokens": 0.4,
        #         "cost_per_image": None,
        #         "cost_per_minute": None,
        #         "cost_per_million_characters": None,
        #         "cost_per_million_reasoning_tokens": None,
        #         "cost_per_thousand_search_queries": None,
        #     },
        #     "meta": {},
        #     "params": {},
        #     "replace_with": None,
        #     "stats": "add",
        #     "visibility": "show",
        # },
        "Google 2.5 Pro": {
            "cost": {
                "cost_per_million_input_tokens": 1.25,
                "cost_per_million_output_tokens": 10,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "GPT 4.1": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 8,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        # "GPT 4.5-preview": {
        #     "cost": {
        #         "cost_per_million_input_tokens": "tbd",
        #         "cost_per_million_output_tokens": "tbd",
        #         "cost_per_image": None,
        #         "cost_per_minute": None,
        #         "cost_per_million_characters": None,
        #         "cost_per_million_reasoning_tokens": None,
        #         "cost_per_thousand_search_queries": None,
        #     },
        #     "meta": {},
        #     "params": {},
        #     "replace_with": None,
        #     "stats": "add",
        #     "visibility": "show",
        # },
        "GPT 4o": {
            "cost": {
                "cost_per_million_input_tokens": 2.75,
                "cost_per_million_output_tokens": 11,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "GPT 4.1",
            "stats": "replace",
            "visibility": "show",
        },
        "GPT 4o-mini": {
            "cost": {
                "cost_per_million_input_tokens": 0.165,
                "cost_per_million_output_tokens": 0.66,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "GPT-4.1 mini",
            "stats": "replace",
            "visibility": "show",
        },
        "GPT o1": {
            "cost": {
                "cost_per_million_input_tokens": 16.5,
                "cost_per_million_output_tokens": 66,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "GPT o4-mini",
            "stats": "replace",
            "visibility": "show",
        },
        "GPT o3": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 8,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "GPT o3-mini": {
            "cost": {
                "cost_per_million_input_tokens": 1.21,
                "cost_per_million_output_tokens": 4.84,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "GPT o4-mini": {
            "cost": {
                "cost_per_million_input_tokens": 1.1,
                "cost_per_million_output_tokens": 4.4,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "GPT-4.1 mini": {
            "cost": {
                "cost_per_million_input_tokens": 0.4,
                "cost_per_million_output_tokens": 1.6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "GPT-4.1 nano": {
            "cost": {
                "cost_per_million_input_tokens": 0.1,
                "cost_per_million_output_tokens": 0.4,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "Grok 4": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "Llama 3.1": {
            "cost": {
                "cost_per_million_input_tokens": 5,
                "cost_per_million_output_tokens": 16,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": "Llama 4 Maverick",
            "stats": "replace",
            "visibility": "show",
        },
        "Llama 4 Maverick": {
            "cost": {
                "cost_per_million_input_tokens": 0.17,
                "cost_per_million_output_tokens": 0.6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
        },
        "Mistral Large 2": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Perplexity Sonar": {
            "cost": {
                "cost_per_million_input_tokens": 1,
                "cost_per_million_output_tokens": 1,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": 8,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Perplexity Sonar Deep Research": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 8,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": 3,
                "cost_per_thousand_search_queries": 5,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Perplexity Sonar Pro": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": 10,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Perplexity Sonar Reasoning Pro": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 8,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": 10,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "Pixtral Large": {
            "cost": {
                "cost_per_million_input_tokens": 2,
                "cost_per_million_output_tokens": 6,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "show",
        },
        "dall-e-3": {
            "cost": {
                "cost_per_million_input_tokens": None,
                "cost_per_million_output_tokens": None,
                "cost_per_image": 0.08,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "hide",
        },
        "text-embedding-3-small": {
            "cost": {
                "cost_per_million_input_tokens": 0.02,
                "cost_per_million_output_tokens": None,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "hide",
        },
        "tts-1": {
            "cost": {
                "cost_per_million_input_tokens": None,
                "cost_per_million_output_tokens": None,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": 15,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "hide",
        },
        "whisper-1": {
            "cost": {
                "cost_per_million_input_tokens": None,
                "cost_per_million_output_tokens": None,
                "cost_per_image": None,
                "cost_per_minute": 0.006,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "unchanged",
            "visibility": "hide",
        },
    }

    # upsert models into model_cost table
    current_model_list_names = connection.execute(
        sqlalchemy.text("SELECT model_name FROM model_cost"),
    ).fetchall()
    current_model_list_names = [model[0] for model in current_model_list_names]

    to_insert_models_list = {
        k: v
        for k, v in all_models_list.items()
        if k not in current_model_list_names
        if v["stats"] != "replace"
    }
    to_update_models_list = {
        k: v
        for k, v in all_models_list.items()
        if k in current_model_list_names and v["stats"] != "replace"
    }

    should_commit = False
    for model_name, model_data in to_insert_models_list.items():
        should_commit = True
        model_cost = model_data["cost"]
        print(f"Inserting model: {model_name}")
        connection.execute(
            sqlalchemy.text(
                """INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries) VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)"""
            ),
            {
                "model_name": model_name,
                "cost_per_million_input_tokens": model_cost[
                    "cost_per_million_input_tokens"
                ],
                "cost_per_million_output_tokens": model_cost[
                    "cost_per_million_output_tokens"
                ],
                "cost_per_image": model_cost["cost_per_image"],
                "cost_per_minute": model_cost["cost_per_minute"],
                "cost_per_million_characters": model_cost[
                    "cost_per_million_characters"
                ],
                "cost_per_million_reasoning_tokens": model_cost[
                    "cost_per_million_reasoning_tokens"
                ],
                "cost_per_thousand_search_queries": model_cost[
                    "cost_per_thousand_search_queries"
                ],
            },
        )

    for model_name, model_data in to_update_models_list.items():
        should_commit = True
        model_cost = model_data["cost"]
        print(f"Updating model: {model_name}")
        connection.execute(
            sqlalchemy.text(
                """UPDATE model_cost SET cost_per_million_input_tokens = :cost_per_million_input_tokens, cost_per_million_output_tokens = :cost_per_million_output_tokens, cost_per_image = :cost_per_image, cost_per_minute = :cost_per_minute, cost_per_million_characters = :cost_per_million_characters, cost_per_million_reasoning_tokens = :cost_per_million_reasoning_tokens, cost_per_thousand_search_queries = :cost_per_thousand_search_queries WHERE model_name = :model_name"""
            ),
            {
                "model_name": model_name,
                "cost_per_million_input_tokens": model_cost[
                    "cost_per_million_input_tokens"
                ],
                "cost_per_million_output_tokens": model_cost[
                    "cost_per_million_output_tokens"
                ],
                "cost_per_image": model_cost["cost_per_image"],
                "cost_per_minute": model_cost["cost_per_minute"],
                "cost_per_million_characters": model_cost[
                    "cost_per_million_characters"
                ],
                "cost_per_million_reasoning_tokens": model_cost[
                    "cost_per_million_reasoning_tokens"
                ],
                "cost_per_thousand_search_queries": model_cost[
                    "cost_per_thousand_search_queries"
                ],
            },
        )
    if should_commit:
        connection.commit()

    # replace models in model table
    to_replace_models_list = {
        k: v
        for k, v in all_models_list.items()
        if v["stats"] == "replace" and v["replace_with"] is not None
    }

    should_commit = False
    for model_name, model_data in to_replace_models_list.items():
        should_commit = True
        replacement_model_name = model_data["replace_with"]
        print(f"Replacing model: {model_name} with {replacement_model_name}")
        connection.execute(
            sqlalchemy.text(
                """UPDATE model SET name = :replace_with, meta = :meta, params = :params WHERE name = :model_name"""
            ),
            {
                "replace_with": replacement_model_name,
                "model_name": model_name,
                "meta": json.dumps(all_models_list[replacement_model_name]["meta"]),
                "params": json.dumps(all_models_list[replacement_model_name]["params"]),
            },
        )
    if should_commit:
        connection.commit()

    # remove models from model_cost table
    to_remove_models_list = {
        k: v for k, v in all_models_list.items() if v["stats"] == "replace"
    }

    should_commit = False
    for model_name in to_remove_models_list.keys():
        should_commit = True
        print(f"Removing model: {model_name} from model_cost table")
        connection.execute(
            sqlalchemy.text("DELETE FROM model_cost WHERE model_name = :model_name"),
            {"model_name": model_name},
        )
    if should_commit:
        connection.commit()

    # remove hidden models from model table
    to_remove_hidden_models_list = {
        k: v for k, v in all_models_list.items() if v["visibility"] == "hide"
    }

    should_commit = False
    for model_name in to_remove_hidden_models_list.keys():
        should_commit = True
        print(f"Removing hidden model: {model_name} from model table")
        connection.execute(
            sqlalchemy.text("DELETE FROM model WHERE name = :model_name"),
            {"model_name": model_name},
        )
    if should_commit:
        connection.commit()

    # add missing models to companies
    companies = connection.execute(sqlalchemy.text("SELECT id FROM company")).fetchall()
    to_sync_models_list = {
        k: v
        for k, v in all_models_list.items()
        if v["stats"] != "replace" and v["visibility"] == "show"
    }

    should_commit = False
    for company in companies:
        company_id = company[0]
        current_company_models = connection.execute(
            sqlalchemy.text("SELECT name FROM model WHERE company_id = :company_id"),
            {"company_id": company_id},
        ).fetchall()
        current_company_models = [model[0] for model in current_company_models]
        mode_company_user_id = connection.execute(
            sqlalchemy.text("SELECT user_id FROM model WHERE company_id = :company_id"),
            {"company_id": company_id},
        ).fetchone()[0]

        for model_name, model_data in to_sync_models_list.items():
            if model_name not in current_company_models:
                should_commit = True
                print(f"Adding model: {model_name} to company: {company_id}")
                connection.execute(
                    sqlalchemy.text(
                        "INSERT INTO model (id, user_id, name, meta, params, created_at, updated_at, is_active, company_id) VALUES (:id, :user_id, :name, :meta, :params, :created_at, :updated_at, :is_active, :company_id)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": mode_company_user_id,
                        "name": model_name,
                        "meta": json.dumps(model_data["meta"]),
                        "params": json.dumps(model_data["params"]),
                        "created_at": int(datetime.datetime.now().timestamp()),
                        "updated_at": int(datetime.datetime.now().timestamp()),
                        "is_active": 1,
                        "company_id": company_id,
                    },
                )
    if should_commit:
        connection.commit()

    # remove unassigned models from model_cost table
    current_model_list_names = connection.execute(
        sqlalchemy.text("SELECT model_name FROM model_cost"),
    ).fetchall()
    current_model_list_names = [model[0] for model in current_model_list_names]

    to_remove_unassigned_models_list = [
        model_name
        for model_name in current_model_list_names
        if model_name not in all_models_list
    ]

    should_commit = False
    for model_name in to_remove_unassigned_models_list:
        should_commit = True
        print(f"Removing unassigned model: {model_name} from model_cost table")
        connection.execute(
            sqlalchemy.text("DELETE FROM model_cost WHERE model_name = :model_name"),
            {"model_name": model_name},
        )
    if should_commit:
        connection.commit()

    # remove dupplicate "Claude Sonnet 4" models
    should_commit = False
    for company in companies:
        company_id = company[0]
        claude_sonnet_model_ids = connection.execute(
            sqlalchemy.text(
                "SELECT id FROM model WHERE name = 'Claude Sonnet 4' AND base_model_id IS NULL AND company_id = :company_id"
            ),
            {"company_id": company_id},
        ).fetchall()

        if len(claude_sonnet_model_ids) == 2:
            should_commit = True
            claude_sonnet_model_id_keep = claude_sonnet_model_ids[0][0]
            claude_sonnet_model_id_remove = claude_sonnet_model_ids[1][0]

            print(
                f"Keeping Claude Sonnet 4 model with id {claude_sonnet_model_id_keep} and removing {claude_sonnet_model_id_remove}"
            )
            connection.execute(
                sqlalchemy.text(
                    "UPDATE model SET base_model_id = :claude_sonnet_model_id_keep WHERE base_model_id = :claude_sonnet_model_id_remove"
                ),
                {
                    "claude_sonnet_model_id_remove": claude_sonnet_model_id_remove,
                    "claude_sonnet_model_id_keep": claude_sonnet_model_id_keep,
                },
            )
            connection.execute(
                sqlalchemy.text("DELETE FROM model WHERE id = :model_id"),
                {"model_id": claude_sonnet_model_id_remove},
            )
    if should_commit:
        connection.commit()

print("LLMs updated successfully")
