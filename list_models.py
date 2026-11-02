import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for model in client.models.list():
    if "flash" in model.name.lower():
        print("Model:", model.name)
        print("Supported actions:", model.supported_actions)
        print("-" * 40)