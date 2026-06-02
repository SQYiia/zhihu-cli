from __future__ import annotations

from dataclasses import dataclass

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class HotItem:
    rank: int
    qid: int
    title: str
    hot_text: str
    excerpt: str


@dataclass
class Question:
    qid: int
    title: str
    detail_html: str


@dataclass
class Answer:
    aid: int
    author: str
    voteup: int
    content_html: str


class ZhihuClient:
    def __init__(self, cookies: dict[str, str] | None = None):
        headers = {
            "user-agent": UA,
            "referer": "https://www.zhihu.com/",
            "accept": "application/json, text/plain, */*",
        }
        self._client = httpx.AsyncClient(
            headers=headers,
            cookies=cookies or {},
            timeout=15.0,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_hot(self) -> list[HotItem]:
        url = "https://api.zhihu.com/topstory/hot-list"
        r = await self._client.get(url, params={"limit": 50})
        r.raise_for_status()
        items: list[HotItem] = []
        for i, entry in enumerate(r.json().get("data", []), start=1):
            target = entry.get("target", {}) or {}
            qid = target.get("id")
            if not qid or target.get("type") != "question":
                continue
            items.append(
                HotItem(
                    rank=i,
                    qid=int(qid),
                    title=target.get("title", "").strip(),
                    hot_text=(entry.get("detail_text") or "").strip(),
                    excerpt=(target.get("excerpt") or "").strip(),
                )
            )
        return items

    async def fetch_question(self, qid: int) -> Question:
        url = f"https://www.zhihu.com/api/v4/questions/{qid}"
        r = await self._client.get(url, params={"include": "detail"})
        r.raise_for_status()
        data = r.json()
        return Question(
            qid=qid,
            title=data.get("title", "").strip(),
            detail_html=data.get("detail", "") or "",
        )

    async def fetch_answers(self, qid: int, offset: int = 0, limit: int = 5) -> list[Answer]:
        url = f"https://www.zhihu.com/api/v4/questions/{qid}/feeds"
        include = (
            "data[*].is_normal,content,voteup_count,"
            "author.name,author.headline"
        )
        r = await self._client.get(
            url,
            params={
                "limit": limit,
                "offset": offset,
                "order": "default",
                "include": include,
            },
        )
        r.raise_for_status()
        out: list[Answer] = []
        for entry in r.json().get("data", []):
            target = entry.get("target", {}) or {}
            if target.get("type") != "answer":
                continue
            author = (target.get("author") or {}).get("name", "匿名")
            out.append(
                Answer(
                    aid=int(target.get("id", 0)),
                    author=author,
                    voteup=int(target.get("voteup_count", 0)),
                    content_html=target.get("content", "") or "",
                )
            )
        return out
