"""配置：RSS 列表、API Key、请求超时等。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 从项目根目录加载 .env
load_dotenv(Path(__file__).resolve().parent / ".env")

# Elsevier Article Retrieval API
ELSEVIER_API_KEY: str = os.getenv("ELSEVIER_API_KEY", "").strip()
ELSEVIER_ARTICLE_BASE = "https://api.elsevier.com/content/article"

# 请求超时（秒）
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

# 可选：爬取文章页时使用的 Cookie（机构登录后复制）
SCIENCE_DIRECT_COOKIE: str = os.getenv("SCIENCE_DIRECT_COOKIE", "").strip()

# RSS 列表：环境变量 RSS_FEEDS（多行 URL）或空列表，由调用方/CLI 传入
def get_rss_feeds_from_env() -> list[str]:
    raw = os.getenv("RSS_FEEDS", "").strip()
    if not raw:
        return []
    return [u.strip() for u in raw.splitlines() if u.strip()]
