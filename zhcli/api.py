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


@dataclass
class AnswerPage:
    question: Question | None
    answers: list[Answer]
    is_end: bool


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

    async def fetch_recommend(self, page_number: int = 1, limit: int = 10) -> list[HotItem]:
        """首页"推荐" feed,每页 limit 条 answer,提取其 question 维度。"""
        url = "https://www.zhihu.com/api/v3/feed/topstory/recommend"
        r = await self._client.get(
            url,
            params={"desktop": "true", "page_number": page_number, "limit": limit},
        )
        r.raise_for_status()
        items: list[HotItem] = []
        seen: set[int] = set()
        for entry in r.json().get("data", []):
            target = entry.get("target", {}) or {}
            if target.get("type") != "answer":
                continue
            q = target.get("question") or {}
            qid = q.get("id")
            if not qid:
                continue
            qid = int(qid)
            if qid in seen:
                continue
            seen.add(qid)
            author = (target.get("author") or {}).get("name", "")
            voteup = target.get("voteup_count", 0)
            sub = f"{author} · 赞 {voteup}" if author else f"赞 {voteup}"
            items.append(
                HotItem(
                    rank=0,  # 推荐没有排名,稍后由 app 赋值
                    qid=qid,
                    title=(q.get("title") or "").strip(),
                    hot_text=sub,
                    excerpt=(target.get("excerpt") or "").strip(),
                )
            )
        return items

    async def fetch_answer_page(
        self, qid: int, offset: int = 0, limit: int = 5
    ) -> AnswerPage:
        """拉一页回答。返回的 AnswerPage.question 从 feeds 内嵌字段提取,
        因为 /api/v4/questions/{qid} 单接口被风控更严。"""
        url = f"https://www.zhihu.com/api/v4/questions/{qid}/feeds"
        include = "data[*].is_normal,content,voteup_count,author.name"
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
        data = r.json()

        question: Question | None = None
        answers: list[Answer] = []
        for entry in data.get("data", []):
            target = entry.get("target", {}) or {}
            if target.get("type") != "answer":
                continue
            if question is None:
                q = target.get("question") or {}
                title = (q.get("title") or "").strip()
                if title:
                    question = Question(
                        qid=qid,
                        title=title,
                        detail_html=q.get("detail") or "",
                    )
            author = (target.get("author") or {}).get("name", "匿名")
            answers.append(
                Answer(
                    aid=int(target.get("id", 0)),
                    author=author,
                    voteup=int(target.get("voteup_count", 0)),
                    content_html=target.get("content", "") or "",
                )
            )

        is_end = bool(data.get("paging", {}).get("is_end", True))
        return AnswerPage(question=question, answers=answers, is_end=is_end)
