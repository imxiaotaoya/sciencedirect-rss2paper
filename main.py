"""
串联：读配置 → 解析 RSS → 去重 → 逐篇拉取 → 提取正文 → 写入本地。
用法：
  python main.py <RSS_URL> [RSS_URL ...]
  或设置环境变量 RSS_FEEDS（多行 URL），然后 python main.py
"""
import argparse
import json
import sys
from pathlib import Path

from article_fetcher import fetch_article
from config import ELSEVIER_API_KEY, get_rss_feeds_from_env, REQUEST_TIMEOUT
from content_extractor import extract_content
from rss_parser import parse_feeds, RSSItem


def dedupe_by_link(items: list[RSSItem]) -> list[RSSItem]:
    """按 link 去重，保留首次出现。"""
    seen: set[str] = set()
    out: list[RSSItem] = []
    for x in items:
        if x.link not in seen:
            seen.add(x.link)
            out.append(x)
    return out


def run(
    feed_urls: list[str],
    output_dir: str | Path = "output",
    limit: int | None = None,
    prefer_api: bool = True,
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not feed_urls:
        print("未提供 RSS URL，请通过参数或环境变量 RSS_FEEDS 指定。", file=sys.stderr)
        sys.exit(1)

    # 解析所有 RSS，去重
    items: list[RSSItem] = []
    for item in parse_feeds(feed_urls, timeout=REQUEST_TIMEOUT):
        items.append(item)
    items = dedupe_by_link(items)
    if limit is not None:
        items = items[:limit]
    print(f"共 {len(items)} 篇文章（已去重）")

    results: list[dict] = []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item.title[:60]}...")
        if not item.article_id():
            print("  跳过：无法从 link 提取 DOI/PII")
            results.append({
                "title": item.title,
                "link": item.link,
                "doi": item.doi,
                "pii": item.pii,
                "abstract": "",
                "full_text": "",
                "source": "skip",
                "error": "no_doi_or_pii",
            })
            continue

        fetched = fetch_article(
            item,
            prefer_api=prefer_api,
            api_key=ELSEVIER_API_KEY or None,
            timeout=REQUEST_TIMEOUT,
        )
        if not fetched:
            print("  获取失败")
            results.append({
                "title": item.title,
                "link": item.link,
                "doi": item.doi,
                "pii": item.pii,
                "abstract": "",
                "full_text": "",
                "source": "skip",
                "error": "fetch_failed",
            })
            continue

        extracted = extract_content(fetched)
        results.append({
            "title": item.title,
            "link": item.link,
            "doi": item.doi,
            "pii": item.pii,
            "abstract": extracted.abstract,
            "full_text": extracted.full_text,
            "source": extracted.source,
        })
        if extracted.full_text:
            print(f"  已提取正文 {len(extracted.full_text)} 字")
        elif extracted.abstract:
            print(f"  仅摘要 {len(extracted.abstract)} 字")
        else:
            print("  未解析到正文/摘要")

    # 写入 JSON
    out_file = output_path / "articles.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到 {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ScienceDirect RSS 全文爬取")
    parser.add_argument(
        "rss_urls",
        nargs="*",
        help="RSS Feed URL 列表（也可通过环境变量 RSS_FEEDS 提供）",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="输出目录（默认 output）",
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=None,
        help="最多处理文章数（默认不限制）",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="不使用 API，仅通过爬取文章页获取",
    )
    args = parser.parse_args()

    feed_urls = list(args.rss_urls) or get_rss_feeds_from_env()
    run(
        feed_urls=feed_urls,
        output_dir=args.output,
        limit=args.limit,
        prefer_api=not args.no_api,
    )


if __name__ == "__main__":
    main()
