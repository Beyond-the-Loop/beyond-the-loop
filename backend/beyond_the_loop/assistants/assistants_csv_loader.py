import csv
import json
import pathlib

current_dir = pathlib.Path(__file__).parent
csv_file_path = current_dir / "kickstart_assistants.csv"

def load_kickstart_assistants():
    with open(csv_file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        return [
            {
                "name": row["Name"],
                "base_model_id": "Smart Router",
                "description": row.get("Beschreibung", ""),
                "profile_image_url": row["Emoji"],
                "category": "",
                "suggestion_prompts": [
                    "Wie funktionierst du?",
                    "Was ist deine Aufgabe?"
                ],
                "system_prompt": row.get("Systemprompt", ""),
            }
            for row in reader
            if row.get("Status", "").strip() == "Bereit"
        ]
