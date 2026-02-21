"""拉取并解析 RSS，返回 (title, link, doi, pii) 列表。"""
import re
from dataclasses import dataclass
from typing import Iterator

import feedparser
import requests

from config import REQUEST_TIMEOUT

# ScienceDirect 文章 URL 中 PII 常见形式：/science/article/pii/S... 或 /science/article/abs/pii/S...
PII_PATTERN = re.compile(
    r"/science/article(?:/abs)?/pii/(S[0-9A-Za-z]+)",
    re.IGNORECASE,
)
# DOI 有时出现在 link 或 description 中
DOI_PATTERN = re.compile(
    r"\b(10\.\d{4,}/[^\s\"'<>]+)\b",
)


@dataclass
class RSSItem:
    title: str
    link: str
    doi: str | None
    pii: str | None
    description: str  # 原始 description，可能含摘要片段

    def article_id(self) -> tuple[str, str] | None:
        """返回 (type, value) 用于 API：('doi', doi) 或 ('pii', pii)，优先 DOI。"""
        if self.doi:
            return ("doi", self.doi)
        if self.pii:
            return ("pii", self.pii)
        return None


def _extract_pii(link: str) -> str | None:
    m = PII_PATTERN.search(link)
    return m.group(1) if m else None


def _extract_doi_from_text(text: str) -> str | None:
    m = DOI_PATTERN.search(text)
    return m.group(1).rstrip(".,;") if m else None


def _extract_doi(entry: dict) -> str | None:
    # 部分 RSS 在 link 或 dc_identifier 等字段带 DOI
    link = entry.get("link", "") or ""
    desc = (entry.get("description", "") or entry.get("summary", "") or "")
    for raw in (link, desc):
        d = _extract_doi_from_text(raw)
        if d:
            return d
    # feedparser 有时把 dc:identifier 解析为 dc_identifier
    dc_id = entry.get("dc_identifier", "") or entry.get("prism_doi", "")
    if isinstance(dc_id, str) and dc_id.strip():
        return _extract_doi_from_text(dc_id) or dc_id.strip()
    return None


def parse_feed_url(feed_url: str, timeout: int = REQUEST_TIMEOUT) -> list[RSSItem]:
    """拉取并解析单个 RSS URL，返回 RSSItem 列表。"""
    resp = requests.get(feed_url, timeout=timeout)
    resp.raise_for_status()
    return parse_feed_content(resp.content, feed_url=feed_url)


def parse_feed_content(
    content: bytes | str,
    feed_url: str = "",
) -> list[RSSItem]:
    """解析 RSS/Atom 内容，返回 RSSItem 列表。"""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    parsed = feedparser.parse(content, response_headers={"content-type": "application/xml"})
    items: list[RSSItem] = []
    for entry in parsed.get("entries", []):
        link = (entry.get("link") or "").strip()
        if not link:
            continue
        title = (entry.get("title") or "").strip()
        description = (entry.get("description") or entry.get("summary", "") or "")
        if hasattr(description, "get"):
            description = description.get("value", str(description))
        description = (description or "").strip()

        pii = _extract_pii(link)
        doi = _extract_doi(entry) or _extract_doi_from_text(link + " " + description)

        items.append(
            RSSItem(
                title=title,
                link=link,
                doi=doi,
                pii=pii,
                description=description,
            )
        )
    return items


def parse_feeds(feed_urls: list[str], timeout: int = REQUEST_TIMEOUT) -> Iterator[RSSItem]:
    """解析多个 RSS，逐条 yield RSSItem（不去重）。单条失败不中断，跳过该 feed。"""
    for url in feed_urls:
        try:
            for item in parse_feed_url(url, timeout=timeout):
                yield item
        except Exception as e:
            # 单条失败不中断全部
            import sys
            print(f"Warning: 跳过 feed {url!r}: {e}", file=sys.stderr)
