from __future__ import annotations

import webbrowser

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from .api import Answer, HotItem, Question, ZhihuClient
from .config import CONFIG_PATH, load_cookies, save_cookies
from .parser import html_to_text

ANSWERS_PER_PAGE = 5


class HotList(ListView):
    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]


class ScrollPane(VerticalScroll, can_focus=True):
    BINDINGS = [
        Binding("j,down", "scroll_down", show=False),
        Binding("k,up", "scroll_up", show=False),
        Binding("g,home", "scroll_home", show=False),
        Binding("G,end", "scroll_end", show=False),
        Binding("ctrl+d,pagedown", "scroll_page_down", show=False),
        Binding("ctrl+u,pageup", "scroll_page_up", show=False),
    ]


class CookieScreen(ModalScreen[dict[str, str] | None]):
    """编辑 cookie 的模态弹窗。返回新的 cookie dict,或 None 表示取消。"""

    DEFAULT_CSS = """
    CookieScreen {
        align: center middle;
    }
    #dialog {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $accent;
    }
    #dialog Label.title { text-style: bold; padding-bottom: 1; }
    #dialog Label.hint { color: $text-muted; padding-top: 1; }
    #dialog Input { margin-bottom: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, cookies: dict[str, str]):
        super().__init__()
        self._initial = cookies

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("配置知乎 cookie", classes="title")
            yield Label("z_c0(登录态):")
            yield Input(value=self._initial.get("z_c0", ""), id="z_c0")
            yield Label("d_c0(设备指纹):")
            yield Input(value=self._initial.get("d_c0", ""), id="d_c0")
            yield Label("__zse_ck(反爬挑战;失效后重新粘贴):")
            yield Input(value=self._initial.get("__zse_ck", ""), id="zse_ck")
            yield Label(
                "浏览器 F12 → Application → Cookies → www.zhihu.com 复制\n"
                "Tab 切换字段 · Enter 保存 · Esc 取消",
                classes="hint",
            )

    def on_mount(self) -> None:
        self.query_one("#z_c0", Input).focus()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._save()

    def _save(self) -> None:
        cookies = {
            "z_c0": self.query_one("#z_c0", Input).value.strip(),
            "d_c0": self.query_one("#d_c0", Input).value.strip(),
            "__zse_ck": self.query_one("#zse_ck", Input).value.strip(),
        }
        self.dismiss({k: v for k, v in cookies.items() if v})

    def action_cancel(self) -> None:
        self.dismiss(None)


class ZhihuApp(App):
    CSS = """
    Screen { layout: horizontal; }
    #left { width: 45%; border-right: solid $accent; }
    #right { width: 1fr; padding: 0 1; }
    HotList { height: 1fr; }
    ListItem { padding: 0 1; }
    ListItem.--highlight { background: $accent 30%; }
    #status { dock: bottom; height: 1; padding: 0 1; color: $text-muted; }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("r", "refresh", "刷新"),
        Binding("t", "toggle_feed", "热榜/推荐"),
        Binding("m", "more", "加载更多"),
        Binding("c", "edit_cookie", "配 cookie"),
        Binding("n", "next_page", "下一页回答"),
        Binding("p", "prev_page", "上一页回答"),
        Binding("o", "open_browser", "浏览器打开"),
        Binding("l,right", "focus_right", "焦点右栏", show=False),
        Binding("h,left", "focus_left", "焦点左栏", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cookies = load_cookies()
        self.client = ZhihuClient(cookies=self.cookies)
        # 有 cookie 默认进推荐(知乎首页风格),没 cookie 推荐接口会 403,退回热榜
        self.feed_mode: str = "recommend" if self.cookies.get("z_c0") else "hot"
        self.feed_items: list[HotItem] = []
        self.recommend_page: int = 0
        self.current_qid: int | None = None
        self.current_offset: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield HotList(id="left")
            with ScrollPane(id="right"):
                yield Static("← 选一条按 Enter · t 切热榜/推荐 · l/→ 进右栏滚动", id="content")
        yield Static("加载中…", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self._update_title()
        await self._load_feed()
        self.query_one(HotList).focus()

    async def on_unmount(self) -> None:
        await self.client.aclose()

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _update_title(self) -> None:
        self.title = "zhcli — 热榜" if self.feed_mode == "hot" else "zhcli — 推荐"

    async def _load_feed(self) -> None:
        """从头加载当前模式的列表。"""
        lv = self.query_one(HotList)
        if self.feed_mode == "hot":
            self._set_status("正在拉取热榜…")
            try:
                items = await self.client.fetch_hot()
            except Exception as e:
                self._set_status(f"拉热榜失败: {e}")
                return
            self.feed_items = items
        else:
            self._set_status("正在拉取推荐…")
            self.recommend_page = 1
            try:
                items = await self.client.fetch_recommend(page_number=1)
            except Exception as e:
                self._set_status(f"拉推荐失败: {e}")
                return
            for i, it in enumerate(items, 1):
                it.rank = i
            self.feed_items = items

        await lv.clear()
        for item in self.feed_items:
            lv.append(ListItem(Label(self._format_item(item))))
        if self.feed_items:
            lv.index = 0
        self._set_status(self._feed_hint(len(self.feed_items)))

    async def _append_recommend(self) -> None:
        """在推荐模式下追加下一页。"""
        if self.feed_mode != "recommend":
            return
        next_page = self.recommend_page + 1
        self._set_status(f"正在加载推荐第 {next_page} 页…")
        try:
            new_items = await self.client.fetch_recommend(page_number=next_page)
        except Exception as e:
            self._set_status(f"加载更多失败: {e}")
            return
        existing_qids = {it.qid for it in self.feed_items}
        new_items = [it for it in new_items if it.qid not in existing_qids]
        if not new_items:
            self._set_status("没有更多新内容了")
            return
        start = len(self.feed_items)
        for i, it in enumerate(new_items, start + 1):
            it.rank = i
        self.feed_items.extend(new_items)
        self.recommend_page = next_page
        lv = self.query_one(HotList)
        for item in new_items:
            lv.append(ListItem(Label(self._format_item(item))))
        self._set_status(self._feed_hint(len(self.feed_items)))

    def _format_item(self, item: HotItem) -> str:
        label = f"{item.rank:02d}. {item.title}"
        if item.hot_text:
            label += f"  · {item.hot_text}"
        return label

    def _feed_hint(self, total: int) -> str:
        if self.feed_mode == "hot":
            return f"热榜 {total} 条 · jk/方向键 · Enter 看问题 · t 切推荐 · c 配 cookie · q 退出"
        return f"推荐 {total} 条 · m 加载更多 · Enter 看问题 · t 切热榜 · q 退出"

    async def action_refresh(self) -> None:
        await self._load_feed()

    async def action_toggle_feed(self) -> None:
        self.feed_mode = "recommend" if self.feed_mode == "hot" else "hot"
        self._update_title()
        await self._load_feed()

    async def action_more(self) -> None:
        if self.feed_mode == "recommend":
            await self._append_recommend()
        else:
            self._set_status("热榜没有更多(接口上限 30 条)。t 切到推荐可加载更多")

    def action_focus_right(self) -> None:
        self.query_one("#right", ScrollPane).focus()

    def action_focus_left(self) -> None:
        self.query_one(HotList).focus()

    @work
    async def action_edit_cookie(self) -> None:
        new_cookies = await self.push_screen_wait(CookieScreen(self.cookies))
        if new_cookies is None:
            return
        save_cookies(new_cookies)
        self.cookies = new_cookies
        await self.client.aclose()
        self.client = ZhihuClient(cookies=self.cookies)
        if self.cookies.get("z_c0"):
            self._set_status("cookie 已保存,可以重新选问题或按 r 刷新")
        else:
            self._set_status("cookie 已清空")

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(HotList).index
        if idx is None or idx >= len(self.feed_items):
            return
        item = self.feed_items[idx]
        self.current_qid = item.qid
        self.current_offset = 0
        await self._render_question()
        self.query_one("#right", ScrollPane).focus()

    async def action_next_page(self) -> None:
        if self.current_qid is None:
            return
        self.current_offset += ANSWERS_PER_PAGE
        await self._render_question()

    async def action_prev_page(self) -> None:
        if self.current_qid is None:
            return
        self.current_offset = max(0, self.current_offset - ANSWERS_PER_PAGE)
        await self._render_question()

    def action_open_browser(self) -> None:
        if self.current_qid is None:
            lv = self.query_one(HotList)
            idx = lv.index
            if idx is None or idx >= len(self.feed_items):
                return
            qid = self.feed_items[idx].qid
        else:
            qid = self.current_qid
        webbrowser.open(f"https://www.zhihu.com/question/{qid}")

    async def _render_question(self) -> None:
        assert self.current_qid is not None
        qid = self.current_qid
        offset = self.current_offset
        page_no = offset // ANSWERS_PER_PAGE + 1
        self._set_status(f"加载问题 {qid} · 第 {page_no} 页…")

        content = self.query_one("#content", Static)
        content.update("加载中…")

        try:
            page = await self.client.fetch_answer_page(
                qid, offset=offset, limit=ANSWERS_PER_PAGE
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                msg = (
                    f"知乎拒绝了请求({e.response.status_code})。\n\n"
                    f"通常是 cookie 不全或 __zse_ck 已过期。按 c 重新粘贴:\n"
                    f"  必须有 z_c0(登录态)、d_c0(设备)、__zse_ck(反爬)\n\n"
                    f"获取方法:浏览器登录知乎 → F12 → Application →\n"
                    f"Cookies → www.zhihu.com → 复制对应 Value。\n\n"
                    f"__zse_ck 几小时到几天会失效,失效再粘一次即可。\n"
                    f"配置文件位置:{CONFIG_PATH}"
                )
            else:
                msg = f"加载失败: HTTP {e.response.status_code}"
            content.update(msg)
            self._set_status(msg.splitlines()[0])
            return
        except Exception as e:
            content.update(f"加载失败: {e}")
            self._set_status(f"加载失败: {e}")
            return

        question = page.question or self._fallback_question(qid)
        if not question.detail_html:
            fallback = self._fallback_question(qid)
            question = Question(
                qid=qid, title=question.title, detail_html=fallback.detail_html
            )
        content.update(_format_question(question, page.answers, offset))
        nav_hint = "n 下一页 · p 上一页" if not page.is_end else "已是最后一页 · p 上一页"
        self._set_status(f"问题 {qid} · 第 {page_no} 页 · {nav_hint} · o 浏览器打开")
        self.query_one("#right", ScrollPane).scroll_home(animate=False)

    def _fallback_question(self, qid: int) -> Question:
        for item in self.feed_items:
            if item.qid == qid:
                return Question(qid=qid, title=item.title, detail_html=item.excerpt)
        return Question(qid=qid, title=f"问题 {qid}", detail_html="")


def _format_question(q: Question, answers: list[Answer], offset: int) -> str:
    parts: list[str] = []
    parts.append(f"# {q.title}")
    parts.append(f"https://www.zhihu.com/question/{q.qid}")
    parts.append("")
    detail = html_to_text(q.detail_html)
    if detail:
        parts.append(detail)
        parts.append("")

    if not answers:
        parts.append("(没有更多回答了)")
        return "\n".join(parts)

    for i, ans in enumerate(answers, start=offset + 1):
        parts.append("─" * 60)
        parts.append(f"[{i}] {ans.author} · 赞 {ans.voteup}")
        parts.append("")
        parts.append(html_to_text(ans.content_html))
        parts.append("")

    return "\n".join(parts)
