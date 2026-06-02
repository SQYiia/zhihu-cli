# zhcli

知乎热榜终端阅读器。两栏 TUI:左边热榜(约 30 条,接口上限),右边问题正文 + 回答。

## 安装

需要 Python 3.11+。

```bash
cd zhcli
uv venv && source .venv/bin/activate
uv pip install -e .
```

或者用 pip:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 配置 cookie

热榜可以匿名看,但问题/回答接口知乎有 JS 反爬挑战(`zse-ck`),必须带 3 个 cookie:

| Cookie | 用途 | 失效频率 |
|---|---|---|
| `z_c0` | 登录态 | 几个月 |
| `d_c0` | 设备指纹 | 较少变 |
| `__zse_ck` | 反爬挑战的解 | **几小时~几天**,失效后重新粘贴 |

**怎么拿**:浏览器登录 [知乎](https://www.zhihu.com/) → F12 → Application → Cookies → `https://www.zhihu.com` → 找上面三个的 Value。

**怎么填**:启动 zhcli 后按 `c`,弹窗里粘贴 → Enter 保存(配置写到 `~/.config/zhcli/config.toml`)。

如果突然又 403 了,通常是 `__zse_ck` 过期了 —— 按 `c` 重新粘一次就行。

## 用法

```bash
zhcli
```

| 键 | 功能 |
|---|---|
| `↑` `↓` 或 `j` `k` | 在当前焦点面板上下移动 / 滚动 |
| `→` `l` / `←` `h` | 切换焦点到右栏 / 左栏 |
| `g` / `G` | 右栏置顶 / 置底 |
| `Ctrl+u` / `Ctrl+d` | 右栏半屏上 / 下滚 |
| `Enter` | 加载选中问题 + 回答 |
| `t` | 在 **热榜** 和 **推荐** 之间切换 |
| `m` | 推荐模式下加载下一页(每页 ~6 条) |
| `n` / `p` | 下一页 / 上一页回答(每页 5 条) |
| `r` | 重新加载当前列表 |
| `c` | 配置 / 修改 cookie |
| `o` | 在浏览器打开当前问题 |
| `q` | 退出 |

热榜接口硬上限 30 条;推荐 feed 是知乎首页那种个性化无限流,按 `m` 持续追加。

## 已知限制

- 不渲染图片、视频、公式(LaTeX 保留为原文)
- 不支持点赞 / 评论 / 收藏
- 知乎随时可能改接口或加签名,接口失效需要更新 `zhcli/api.py`
