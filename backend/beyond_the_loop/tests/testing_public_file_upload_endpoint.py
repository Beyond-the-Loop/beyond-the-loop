import logging
import openai
from openai import OpenAI
import os

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Path to the file in Downloads folder
downloads_folder = os.path.expanduser("~/Downloads")
file_name = "SR06-KM-C4525110518020.pdf"  # replace with the actual filename
file_path = os.path.join(downloads_folder, file_name)

# Initialize the OpenAI client pointing to your local API
client = OpenAI(
    api_key="sk-e549954e642b403493ece2cf91597d02",
    base_url="http://localhost:8080/api/openai"  # root of your FastAPI server
)

# Open the file in binary mode
with open(file_path, "rb") as f:
    response = client.files.create(
        file=f,
        purpose="user_data"  # or "fine-tune" if needed
    )

log.info(f"Response: {response}")