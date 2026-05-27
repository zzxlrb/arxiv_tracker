import os
from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def get_int(key: str, default: int) -> int:
    val = os.getenv(key, "")
    if val == "":
        return default
    return int(val)


DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = get_env("DEEPSEEK_MODEL", "deepseek-chat")

ARXIV_MAX_RESULTS = get_int("ARXIV_MAX_RESULTS", 10)
ARXIV_LOOKBACK_DAYS = get_int("ARXIV_LOOKBACK_DAYS", 7)

def get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "").lower()
    if val == "":
        return default
    return val in ("1", "true", "yes")


SMTP_SERVER = get_env("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = get_int("SMTP_PORT", 465)
SMTP_USE_SSL = get_bool("SMTP_USE_SSL", True)
SENDER_EMAIL = get_env("SENDER_EMAIL")
SENDER_AUTH_CODE = get_env("SENDER_AUTH_CODE")
RECEIVER_EMAIL = get_env("RECEIVER_EMAIL")
