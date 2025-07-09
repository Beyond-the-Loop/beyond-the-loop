import sqlalchemy

DATABASE_URL = "sqlite:///./backend/data/database.sqlite"

print("Updating LLMs...")
print(f"Using database URL: {DATABASE_URL}")

db_engine = sqlalchemy.create_engine(DATABASE_URL)

with db_engine.connect() as connection:
    delete_models = [
        "GPT 4o",
        "GPT 4o-mini",
        "GPT o1",
        "Gemini 2.0 Flash",
        "Claude 3.5 Sonnet",
        "Llama 3.1",
    ]

    add_models_object = {
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
        "Claude Opus 4": {
            "model_name": "Claude Opus 4",
            "cost_per_million_input_tokens": 75,
            "cost_per_million_output_tokens": 375,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "Claude Sonnet 4": {
            "model_name": "Claude Sonnet 4",
            "cost_per_million_input_tokens": 15,
            "cost_per_million_output_tokens": 75,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        # "Claude 3.5 Haiku": {
        #     "model_name": "Claude 3.5 Haiku",
        #     "cost_per_million_input_tokens": 4,
        #     "cost_per_million_output_tokens": 20,
        #     "cost_per_image": None,
        #     "cost_per_minute": None,
        #     "cost_per_million_characters": None,
        #     "cost_per_million_reasoning_tokens": None,
        #     "cost_per_thousand_search_queries": None,
        # },
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
            "cost_per_million_input_tokens": 0.5,
            "cost_per_million_output_tokens": 2,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT o3": {
            "model_name": "GPT o3",
            "cost_per_million_input_tokens": 10,
            "cost_per_million_output_tokens": 40,
            "cost_per_image": None,
            "cost_per_minute": None,
            "cost_per_million_characters": None,
            "cost_per_million_reasoning_tokens": None,
            "cost_per_thousand_search_queries": None,
        },
        "GPT o4-mini": {
            "model_name": "GPT o4-mini",
            "cost_per_million_input_tokens": 5.5,
            "cost_per_million_output_tokens": 22,
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

    model_transfer = {
        "GPT 4o": "GPT 4.1",
        "GPT 4o-mini": "GPT-4.1 mini",
        "GPT o1": "",
        "Gemini 2.0 Flash": "Google 2.5 Flash",
        "Claude 3.5 Sonnet": "",
        "Llama 3.1": "",
    }

    for model in add_models_object:
        model_data = add_models_object[model]
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
        connection.commit()

    for model_from in model_transfer:
        model_to = model_transfer[model_from]

        connection.execute(
            sqlalchemy.text(
                """UPDATE model SET name = :model_to WHERE name = :model_from"""
            ),
            {"model_to": model_to, "model_from": model_from},
        )
        connection.commit()
