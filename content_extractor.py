"""从 API 返回的 XML 或文章页 HTML 中提取摘要与正文。"""
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from lxml import etree

from article_fetcher import FetchedArticle


@dataclass
class ExtractedContent:
    """提取后的结构化内容。"""
    abstract: str
    full_text: str
    source: str  # "api" | "crawl"


# Elsevier 全文 XML 常见命名空间
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "xocs": "http://www.elsevier.com/xml/xocs/dtd",
    "ce": "http://www.elsevier.com/xml/ani/dtd",
    "sb": "http://www.elsevier.com/xml/common/struct-bib/dtd",
    "ja": "http://www.elsevier.com/xml/ja/dtd",
    "article": "http://www.elsevier.com/xml/ja/dtd",
    "mml": "http://www.w3.org/1998/Math/MathML",
}


def _strip_ns(tag: str) -> str:
    if tag and "}" in tag:
        return tag.split("}", 1)[1]
    return tag or ""


def _collect_text(el: ET.Element, buf: list[str]) -> None:
    if el.text:
        buf.append(el.text)
    for child in el:
        _collect_text(child, buf)
        if child.tail:
            buf.append(child.tail)


def extract_from_api_xml(raw_body: str) -> ExtractedContent:
    """
    解析 Elsevier Article Retrieval API 返回的 XML，提取摘要与正文。
    正文多在 <dc:description>（摘要）、<ce:abstract>、<body> 内 <section>/<para> 等。
    """
    abstract_parts: list[str] = []
    body_parts: list[str] = []

    try:
        root = ET.fromstring(raw_body)
    except ET.ParseError:
        return ExtractedContent(abstract="", full_text="", source="api")

    # 递归查找所有元素（忽略命名空间匹配）
    def find_all_with_tag(parent: ET.Element, local_name: str) -> list[ET.Element]:
        out: list[ET.Element] = []
        for el in parent.iter():
            if _strip_ns(el.tag) == local_name:
                out.append(el)
        return out

    def text_of(el: ET.Element) -> str:
        buf: list[str] = []
        _collect_text(el, buf)
        return " ".join(buf).strip()

    # 摘要：dc:description, description, abstract, ce:abstract
    for name in ("description", "abstract"):
        for el in find_all_with_tag(root, name):
            t = text_of(el)
            if t and len(t) > 20 and t not in abstract_parts:
                abstract_parts.append(t)
    if abstract_parts:
        abstract_parts = abstract_parts[:3]  # 避免重复

    # 正文：body 下的 section / para，或 direct para
    body_el = None
    for el in root.iter():
        if _strip_ns(el.tag) == "body":
            body_el = el
            break
    if body_el is not None:
        for tag in ("section", "para", "p"):
            for el in find_all_with_tag(body_el, tag):
                t = text_of(el)
                if t and len(t) > 30:  # 过滤过短片段
                    body_parts.append(t)
    if not body_parts:
        # 退而求其次：任意长段落
        for el in find_all_with_tag(root, "para"):
            t = text_of(el)
            if t and len(t) > 50:
                body_parts.append(t)

    abstract = "\n\n".join(abstract_parts) if abstract_parts else ""
    full_text = "\n\n".join(body_parts) if body_parts else ""

    # 若正文为空但摘要很长，可把摘要当正文
    if not full_text and len(abstract) > 200:
        full_text = abstract
        abstract = abstract[:500] + "..." if len(abstract) > 500 else abstract

    return ExtractedContent(abstract=abstract, full_text=full_text, source="api")


def extract_from_api_xml_lxml(raw_body: str) -> ExtractedContent:
    """
    使用 lxml 解析（对命名空间更友好），提取 abstract 与 body 段落。
    """
    abstract_parts: list[str] = []
    body_parts: list[str] = []

    try:
        root = etree.fromstring(raw_body.encode("utf-8"))
    except Exception:
        return extract_from_api_xml(raw_body)  # 回退到 etree

    def xpath_text(nodes: list) -> list[str]:
        out: list[str] = []
        for n in nodes:
            if n.text:
                out.append(n.text)
            t = etree.tostring(n, encoding="unicode", method="text")
            if t:
                t = re.sub(r"\s+", " ", t).strip()
                if t and t not in out:
                    out.append(t)
        return out

    # 摘要：任意命名空间下的 description, abstract
    for path in (
        "//*[local-name()='description' and string-length(normalize-space(.))>20]",
        "//*[local-name()='abstract' and string-length(normalize-space(.))>20]",
    ):
        for el in root.xpath(path):
            t = (el.text or "") + "".join(el.itertext())
            t = re.sub(r"\s+", " ", t).strip()
            if t and len(t) > 20 and t not in abstract_parts:
                abstract_parts.append(t)
    abstract_parts = abstract_parts[:3]

    # 正文：body 内 section/para
    body = root.xpath("//*[local-name()='body']")
    if body:
        for el in body[0].xpath(".//*[local-name()='para' or local-name()='section']"):
            t = (el.text or "") + "".join(el.itertext())
            t = re.sub(r"\s+", " ", t).strip()
            if t and len(t) > 30:
                body_parts.append(t)
    if not body_parts:
        for el in root.xpath("//*[local-name()='para']"):
            t = (el.text or "") + "".join(el.itertext())
            t = re.sub(r"\s+", " ", t).strip()
            if t and len(t) > 50:
                body_parts.append(t)

    abstract = "\n\n".join(abstract_parts) if abstract_parts else ""
    full_text = "\n\n".join(body_parts) if body_parts else ""
    if not full_text and len(abstract) > 200:
        full_text = abstract

    return ExtractedContent(abstract=abstract, full_text=full_text, source="api")


def extract_from_html(raw_body: str) -> ExtractedContent:
    """
    从 ScienceDirect 文章页 HTML 中提取摘要与正文区域。
    需根据当前 SD 页面结构调整选择器；常见为 .abstract、.body div 等。
    """
    soup = BeautifulSoup(raw_body, "lxml")
    abstract_parts: list[str] = []
    body_parts: list[str] = []

    # 摘要：常见 class
    for sel in (
        "[class*='abstract']",
        ".abstract",
        "[data-abstract]",
        "div.abstract-group",
    ):
        for el in soup.select(sel):
            t = el.get_text(separator=" ", strip=True)
            if t and len(t) > 20 and t not in abstract_parts:
                abstract_parts.append(t)
    abstract_parts = abstract_parts[:3]

    # 正文：文章主体
    for sel in (
        ".body",
        "[class*='article-body']",
        "[class*='Body']",
        "div.article-body",
        "section.body",
        "#body",
        ".main-content",
    ):
        for el in soup.select(sel):
            # 按段落取
            for p in el.find_all(["p", "div"], recursive=True):
                if p.find_all(["p", "div"], recursive=False):
                    continue  # 只取叶子段落
                t = p.get_text(separator=" ", strip=True)
                if t and len(t) > 40:
                    body_parts.append(t)
            if body_parts:
                break
        if body_parts:
            break

    if not body_parts:
        # 最后手段：所有长段落
        for p in soup.find_all("p"):
            t = p.get_text(separator=" ", strip=True)
            if t and len(t) > 80:
                body_parts.append(t)

    abstract = "\n\n".join(abstract_parts) if abstract_parts else ""
    full_text = "\n\n".join(body_parts) if body_parts else ""
    if not full_text and abstract:
        full_text = abstract

    return ExtractedContent(abstract=abstract, full_text=full_text, source="crawl")


def extract_content(fetched: FetchedArticle) -> ExtractedContent:
    """根据拉取来源选择 XML 或 HTML 解析，返回统一的结构化内容。"""
    ct = (fetched.content_type or "").lower()
    if "xml" in ct or fetched.source == "api":
        try:
            return extract_from_api_xml_lxml(fetched.raw_body)
        except Exception:
            return extract_from_api_xml(fetched.raw_body)
    return extract_from_html(fetched.raw_body)
