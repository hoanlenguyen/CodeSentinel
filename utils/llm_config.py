import os

from dotenv import load_dotenv


load_dotenv(override=True)


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-exp:free")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

if not LLM_API_KEY:
    raise ValueError("Missing required LLM environment variable: LLM_API_KEY")

LLM_CONFIG = {
    "config_list": [{
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY,
    }],
    "cache_seed": None
}
