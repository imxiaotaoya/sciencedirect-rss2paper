"""通过 Elsevier API 或文章页 HTML 获取全文。"""
from dataclasses import dataclass
from typing import Literal

import requests

from config import (
    ELSEVIER_API_KEY,
    ELSEVIER_ARTICLE_BASE,
    REQUEST_TIMEOUT,
    SCIENCE_DIRECT_COOKIE,
)
from rss_parser import RSSItem

# User-Agent 标识，礼貌爬取
USER_AGENT = "SDRSS/1.0 (ScienceDirect RSS full-text fetcher; +https://github.com/sdrss)"


@dataclass
class FetchedArticle:
    """单篇文章的拉取结果。"""
    source: Literal["api", "crawl"]
    raw_body: str  # XML 或 HTML 字符串
    content_type: str  # application/xml, text/html 等
    item: RSSItem


def fetch_via_api(
    item: RSSItem,
    api_key: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
    accept: str = "application/xml",
) -> FetchedArticle | None:
    """
    使用 Elsevier Article Retrieval API 获取全文。
    需要 ELSEVIER_API_KEY 及机构权限；无权限时可能返回 403 或仅元数据。
    """
    key = (api_key or ELSEVIER_API_KEY).strip()
    if not key:
        return None

    aid = item.article_id()
    if not aid:
        return None

    id_type, id_value = aid
    url = f"{ELSEVIER_ARTICLE_BASE}/{id_type}/{id_value}"
    headers = {
        "X-ELS-APIKey": key,
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    params = {"httpAccept": accept}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "").split(";")[0].strip()
        return FetchedArticle(
            source="api",
            raw_body=resp.text,
            content_type=ct or accept,
            item=item,
        )
    except requests.RequestException:
        return None


def fetch_via_crawl(
    item: RSSItem,
    cookie: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> FetchedArticle | None:
    """
    请求文章页 HTML（需机构 Cookie 才能看到全文，否则多为摘要+付费墙）。
    """
    cookie = (cookie or SCIENCE_DIRECT_COOKIE).strip()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(item.link, headers=headers, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "").split(";")[0].strip() or "text/html"
        return FetchedArticle(
            source="crawl",
            raw_body=resp.text,
            content_type=ct,
            item=item,
        )
    except requests.RequestException:
        return None


def fetch_article(
    item: RSSItem,
    prefer_api: bool = True,
    api_key: str | None = None,
    cookie: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> FetchedArticle | None:
    """
    优先用 API 获取全文，失败或无 Key 时尝试爬取文章页。
    """
    if prefer_api:
        result = fetch_via_api(item, api_key=api_key, timeout=timeout)
        if result is not None:
            return result
    return fetch_via_crawl(item, cookie=cookie, timeout=timeout)
