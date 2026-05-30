import os

from dotenv import load_dotenv


load_dotenv(override=True)


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

# Primary model + fallbacks — AG2 tries each in order on rate-limit or error
MODELS = [
    os.getenv("LLM_MODEL", "openai/gpt-oss-120b:free"),
    "qwen/qwen3-coder:free",
    "deepseek/deepseek-v4-flash:free",
]

if not LLM_API_KEY:
    raise ValueError("Missing required LLM environment variable: LLM_API_KEY")

LLM_CONFIG = {
    "config_list": [
        {
            "model": model,
            "base_url": LLM_BASE_URL,
            "api_key": LLM_API_KEY,
        }
        for model in MODELS
    ],
    "cache_seed": None
}
