from dotenv import load_dotenv
import os
from openai import OpenAI

# Load .env file
load_dotenv(".env")

# Read key from environment
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("❌ OPENAI_API_KEY not found in .env")

# Initialize client
client = OpenAI(api_key=api_key)

# Simple test request
try:
    res = client.models.list()
    print("✅ API key works, able to fetch model list.")
    print("Available models:", [m.id for m in res.data[:3]], "...")
except Exception as e:
    print("🚫 Failed to use key:", e)
