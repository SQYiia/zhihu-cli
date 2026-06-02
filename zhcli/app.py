from __future__ import annotations

import asyncio
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
            yield Label("z_c0(必填,登录态主 cookie):")
            yield Input(value=self._initial.get("z_c0", ""), id="z_c0")
            yield Label("d_c0(可选,设备 cookie):")
            yield Input(value=self._initial.get("d_c0", ""), id="d_c0")
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
        Binding("r", "refresh", "刷新热榜"),
        Binding("c", "edit_cookie", "配 cookie"),
        Binding("n", "next_page", "下一页"),
        Binding("p", "prev_page", "上一页"),
        Binding("o", "open_browser", "浏览器打开"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.cookies = load_cookies()
        self.client = ZhihuClient(cookies=self.cookies)
        self.hot_items: list[HotItem] = []
        self.current_qid: int | None = None
        self.current_offset: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield HotList(id="left")
            with VerticalScroll(id="right"):
                yield Static("← 选一条热榜按 Enter", id="content")
        yield Static("加载中…", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self.title = "zhcli — 知乎热榜"
        await self._load_hot()
        self.query_one(HotList).focus()

    async def on_unmount(self) -> None:
        await self.client.aclose()

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    async def _load_hot(self) -> None:
        self._set_status("正在拉取热榜…")
        try:
            self.hot_items = await self.client.fetch_hot()
        except Exception as e:
            self._set_status(f"拉热榜失败: {e}")
            return
        lv = self.query_one(HotList)
        await lv.clear()
        for item in self.hot_items:
            label = f"{item.rank:02d}. {item.title}"
            if item.hot_text:
                label += f"  · {item.hot_text}"
            lv.append(ListItem(Label(label)))
        if self.hot_items:
            lv.index = 0
        self._set_status(f"已加载 {len(self.hot_items)} 条 · 方向键/jk 移动 · Enter 看问题 · q 退出")

    async def action_refresh(self) -> None:
        await self._load_hot()

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
        if idx is None or idx >= len(self.hot_items):
            return
        item = self.hot_items[idx]
        self.current_qid = item.qid
        self.current_offset = 0
        await self._render_question()

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
            if idx is None or idx >= len(self.hot_items):
                return
            qid = self.hot_items[idx].qid
        else:
            qid = self.current_qid
        webbrowser.open(f"https://www.zhihu.com/question/{qid}")

    async def _render_question(self) -> None:
        assert self.current_qid is not None
        qid = self.current_qid
        offset = self.current_offset
        self._set_status(f"加载问题 {qid} · 第 {offset // ANSWERS_PER_PAGE + 1} 页…")

        content = self.query_one("#content", Static)
        content.update("加载中…")

        try:
            q_task = asyncio.create_task(self.client.fetch_question(qid))
            a_task = asyncio.create_task(
                self.client.fetch_answers(qid, offset=offset, limit=ANSWERS_PER_PAGE)
            )
            question, answers = await asyncio.gather(q_task, a_task)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                msg = (
                    f"知乎拒绝了请求({e.response.status_code})。\n\n"
                    f"问题/回答接口必须带 cookie 才能访问。\n"
                    f"按 c 在弹窗里粘贴 z_c0 cookie 即可。\n\n"
                    f"获取方法:浏览器登录知乎 → F12 → Application →\n"
                    f"Cookies → www.zhihu.com → 复制 z_c0 的值。\n\n"
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

        content.update(_format_question(question, answers, offset))
        self._set_status(
            f"问题 {qid} · 第 {offset // ANSWERS_PER_PAGE + 1} 页 · "
            f"n 下一页 · p 上一页 · o 浏览器打开"
        )
        self.query_one("#right", VerticalScroll).scroll_home(animate=False)


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
