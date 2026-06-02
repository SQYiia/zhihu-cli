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

热榜可以匿名看,但问题/回答接口知乎必须要 cookie。两种方式都行:

**方式一:在 CLI 里直接配(推荐)**

启动 zhcli 后按 `c`,弹窗里粘贴 `z_c0` 然后 Enter 保存。

**方式二:手动编辑配置文件**

编辑 `~/.config/zhcli/config.toml`(首次运行会自动生成):

```toml
[cookies]
z_c0 = "贴在这里"
d_c0 = ""   # 可选
```

**怎么拿到 z_c0**:浏览器登录 [知乎](https://www.zhihu.com/) → F12 → Application → Cookies → `https://www.zhihu.com` → 复制 `z_c0` 的值。

## 用法

```bash
zhcli
```

| 键 | 功能 |
|---|---|
| `↑` `↓` 或 `j` `k` | 在热榜里上下移动 |
| `Enter` | 加载选中问题 + 回答 |
| `n` / `p` | 下一页 / 上一页回答(每页 5 条) |
| `r` | 重新拉热榜 |
| `c` | 配置 / 修改 cookie |
| `o` | 在浏览器打开当前问题 |
| `q` | 退出 |

## 已知限制

- 不渲染图片、视频、公式(LaTeX 保留为原文)
- 不支持点赞 / 评论 / 收藏
- 知乎随时可能改接口或加签名,接口失效需要更新 `zhcli/api.py`
