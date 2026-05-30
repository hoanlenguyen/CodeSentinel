import os

from dotenv import load_dotenv


load_dotenv(override=True)


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5")
LLM_API_TYPE = os.getenv("LLM_API_TYPE", "anthropic")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional — only needed for custom endpoints

if not LLM_API_KEY:
    raise ValueError("Missing required LLM environment variable: LLM_API_KEY")

config_entry = {
    "model": LLM_MODEL,
    "api_key": LLM_API_KEY,
    "api_type": LLM_API_TYPE,
}
if LLM_BASE_URL:
    config_entry["base_url"] = LLM_BASE_URL

LLM_CONFIG = {
    "config_list": [config_entry],
    "cache_seed": None
}
