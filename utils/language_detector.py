import anthropic
from utils.llm_config import LLM_CONFIG

COMMON_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript", ".tsx": "TypeScript", ".java": "Java",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".kt": "Kotlin", ".swift": "Swift",
    ".cpp": "C++", ".c": "C", ".sh": "Shell", ".sql": "SQL",
    ".r": "R", ".scala": "Scala", ".dart": "Dart",
}


def detect_language(code, ext=None):
    # Fast-path: known extension — no LLM call needed
    if ext and ext.lower() in COMMON_EXTENSIONS:
        return COMMON_EXTENSIONS[ext.lower()]

    # Fallback: ask the LLM to detect from code content
    config = LLM_CONFIG["config_list"][0]
    client = anthropic.Anthropic(api_key=config["api_key"])

    try:
        response = client.messages.create(
            model=config["model"],
            max_tokens=20,
            system=(
                "Identify the programming language of this code snippet. "
                "Respond with ONLY the language name (e.g. Python, JavaScript, Go, Rust, SQL). "
                "If you cannot determine the language, respond with UNKNOWN."
            ),
            messages=[{"role": "user", "content": code}],
        )
        result = response.content[0].text.strip()
        return result if result else "UNKNOWN"
    except Exception as e:
        print(f"[language_detector] LLM call failed: {e}")
        return "UNKNOWN"
