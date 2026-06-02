from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

_BLANK_RUN = re.compile(r"\n{3,}")


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "figure", "img", "svg"]):
        tag.decompose()

    parts: list[str] = []
    _walk(soup, parts)
    text = "".join(parts)
    text = _BLANK_RUN.sub("\n\n", text).strip()
    return text


def _walk(node, parts: list[str]) -> None:
    if isinstance(node, NavigableString):
        parts.append(str(node))
        return

    if not isinstance(node, Tag):
        for child in getattr(node, "children", []):
            _walk(child, parts)
        return

    name = node.name.lower()

    if name == "br":
        parts.append("\n")
        return

    if name in ("p", "div", "li", "blockquote", "h1", "h2", "h3", "h4"):
        parts.append("\n")
        for child in node.children:
            _walk(child, parts)
        parts.append("\n")
        return

    if name == "a":
        text = node.get_text("", strip=False)
        href = node.get("href", "")
        if href and href != text:
            parts.append(f"{text} ({href})")
        else:
            parts.append(text)
        return

    if name == "pre":
        code = node.get_text("", strip=False)
        parts.append("\n```\n")
        parts.append(code.rstrip())
        parts.append("\n```\n")
        return

    if name == "code" and node.parent and node.parent.name != "pre":
        parts.append("`")
        parts.append(node.get_text("", strip=False))
        parts.append("`")
        return

    for child in node.children:
        _walk(child, parts)
