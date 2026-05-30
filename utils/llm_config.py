import os

from dotenv import load_dotenv


load_dotenv(override=True)


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.getenv("LLM_API_KEY")

if not LLM_API_KEY:
    raise ValueError("Missing required LLM environment variable: LLM_API_KEY")


LLM_CONFIG = {
    "config_list": [{
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
        "api_key": LLM_API_KEY
    }],
    "cache_seed": None
}
