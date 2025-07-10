import datetime
import sqlalchemy
import uuid
import json

DATABASE_URL = "sqlite:///./backend/data/database.sqlite"

print("Updating LLMs...")
print(f"Using database URL: {DATABASE_URL}")

db_engine = sqlalchemy.create_engine(DATABASE_URL)

with db_engine.connect() as connection:
    new_models_object = {
        "Claude Opus 4": {
            "model_name": "Claude Opus 4",
            "cost_per_million_input_tokens": 15,
            "cost_per_million_output_tokens": 75,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Claude Sonnet 4": {
            "model_name": "Claude Sonnet 4",
            "cost_per_million_input_tokens": 3,
            "cost_per_million_output_tokens": 15,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Google 2.5 Pro": {
            "model_name": "Google 2.5 Pro",
            "cost_per_million_input_tokens": 1.25,
            "cost_per_million_output_tokens": 10,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Google 2.5 Flash": {
            "model_name": "Google 2.5 Flash",
            "cost_per_million_input_tokens": 0.15,
            "cost_per_million_output_tokens": 0.6,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Google 2.5 Flash-Lite": {
            "model_name": "Google 2.5 Flash-Lite",
            "cost_per_million_input_tokens": 0.1,
            "cost_per_million_output_tokens": 0.4,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT 4.1": {
            "model_name": "GPT 4.1",
            "cost_per_million_input_tokens": 2,
            "cost_per_million_output_tokens": 8,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT-4.1 mini": {
            "model_name": "GPT-4.1 mini",
            "cost_per_million_input_tokens": 0.4,
            "cost_per_million_output_tokens": 1.6,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT-4.1 nano": {
            "model_name": "GPT-4.1 nano",
            "cost_per_million_input_tokens": 0.1,
            "cost_per_million_output_tokens": 0.4,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT o3": {
            "model_name": "GPT o3",
            "cost_per_million_input_tokens": 2,
            "cost_per_million_output_tokens": 8,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT o4-mini": {
            "model_name": "GPT o4-mini",
            "cost_per_million_input_tokens": 1.1,
            "cost_per_million_output_tokens": 4.4,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Grok 4": {
            "model_name": "Grok 4",
            "cost_per_million_input_tokens": 3,
            "cost_per_million_output_tokens": 15,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Llama 4 Maverick": {
            "model_name": "Llama 4 Maverick",
            "cost_per_million_input_tokens": 0.17,
            "cost_per_million_output_tokens": 0.6,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
    }

    # add new models to model_cost table
    changes_to_commit = False
    for model, model_data in new_models_object.items():
        changes_to_commit = True
        print(f"Inserting model: {model} with data {model_data}")
        connection.execute(
            sqlalchemy.text(
                """INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries)
                VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)"""
            ),
            {
                "model_name": model_data["model_name"],
                "cost_per_million_input_tokens": model_data[
                    "cost_per_million_input_tokens"
                ],
                "cost_per_million_output_tokens": model_data[
                    "cost_per_million_output_tokens"
                ],
                "cost_per_image": model_data["cost_per_image"],
                "cost_per_minute": model_data["cost_per_minute"],
                "cost_per_million_characters": model_data[
                    "cost_per_million_characters"
                ],
                "cost_per_million_reasoning_tokens": model_data[
                    "cost_per_million_reasoning_tokens"
                ],
                "cost_per_thousand_search_queries": model_data[
                    "cost_per_thousand_search_queries"
                ],
            },
        )
    if changes_to_commit:
        connection.commit()

    replace_models_object = {
        "Claude 3.5 Sonnet": {"replace_with": "Claude Sonnet 4"},
        "Claude 3.7 Sonnet": {"replace_with": "Claude Sonnet 4"},
        "Gemini 2.0 Flash": {"replace_with": "Google 2.5 Flash"},
        "GPT 4o-mini": {"replace_with": "GPT-4.1 mini"},
        "GPT 4o": {"replace_with": "GPT 4.1"},
        "GPT o1": {"replace_with": "GPT o3"},
        "Llama 3.1": {"replace_with": "Llama 4 Maverick"},
    }

    # delete old models from model_cost table
    changes_to_commit = False
    for model in replace_models_object.keys():
        changes_to_commit = True
        print(f"Deleting model: {model}")
        connection.execute(
            sqlalchemy.text("DELETE FROM model_cost WHERE model_name = :model_name"),
            {"model_name": model},
        )
    if changes_to_commit:
        connection.commit()

    # update model names in model table
    changes_to_commit = False
    for model, model_data in replace_models_object.items():
        changes_to_commit = True
        print(f"Updating model: {model} to {model_data['replace_with']}")
        connection.execute(
            sqlalchemy.text(
                """UPDATE model SET name = :replace_with WHERE name = :model_name"""
            ),
            {
                "replace_with": model_data["replace_with"],
                "model_name": model,
            },
        )
    if changes_to_commit:
        connection.commit()

    companies = connection.execute(sqlalchemy.text("SELECT id FROM company")).fetchall()
    models = connection.execute(
        sqlalchemy.text("SELECT model_name FROM model_cost")
    ).fetchall()
    models_additional_info = {
        "Claude 3.5 Haiku": {"meta": {}, "params": {}},
        "Claude Opus 4": {"meta": {}, "params": {}},
        "Claude Sonnet 4": {"meta": {}, "params": {}},
        "dall-e-3": {"meta": {}, "params": {}},
        "Google 2.5 Flash-Lite": {"meta": {}, "params": {}},
        "Google 2.5 Flash": {"meta": {}, "params": {}},
        "Google 2.5 Pro": {"meta": {}, "params": {}},
        "GPT 4.1": {"meta": {}, "params": {}},
        "GPT o3-mini": {"meta": {}, "params": {}},
        "GPT o3": {"meta": {}, "params": {}},
        "GPT o4-mini": {"meta": {}, "params": {}},
        "GPT-4.1 mini": {"meta": {}, "params": {}},
        "GPT-4.1 nano": {"meta": {}, "params": {}},
        "Grok 4": {"meta": {}, "params": {}},
        "Llama 4 Maverick": {"meta": {}, "params": {}},
        "Mistral Large 2.0": {"meta": {}, "params": {}},
        "Perplexity Sonar Deep Research": {"meta": {}, "params": {}},
        "Perplexity Sonar Pro": {"meta": {}, "params": {}},
        "Perplexity Sonar Reasoning Pro": {"meta": {}, "params": {}},
        "Perplexity Sonar": {"meta": {}, "params": {}},
        "Pixtral Large": {"meta": {}, "params": {}},
        "text-embedding-3-small": {"meta": {}, "params": {}},
        "tts-1": {"meta": {}, "params": {}},
        "whisper-1": {"meta": {}, "params": {}},
    }
    # add missing models to companies
    changes_to_commit = False
    for company in companies:
        company_models = connection.execute(
            sqlalchemy.text("SELECT name FROM model WHERE company_id = :company_id"),
            {"company_id": company.id},
        ).fetchall()

        missing_models = [model for model in models if model not in company_models]
        for model in missing_models:
            changes_to_commit = True
            print(f"Adding missing model: {model.model_name} to company: {company.id}")

            meta = (
                models_additional_info.get(model.model_name).get("meta")
                if models_additional_info.get(model.model_name)
                else {}
            )
            params = (
                models_additional_info.get(model.model_name).get("params")
                if models_additional_info.get(model.model_name)
                else {}
            )

            connection.execute(
                sqlalchemy.text(
                    "INSERT INTO model (id, name, meta, params, created_at, updated_at, company_id) VALUES (:id, :model_name, :meta, :params, :created_at, :updated_at, :company_id)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "model_name": model.model_name,
                    "meta": json.dumps(meta),
                    "params": json.dumps(params),
                    "created_at": int(datetime.datetime.now().timestamp()),
                    "updated_at": int(datetime.datetime.now().timestamp()),
                    "company_id": company.id,
                },
            )
    if changes_to_commit:
        connection.commit()
