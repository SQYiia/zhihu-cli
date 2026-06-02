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

## 配置 cookie(可选)

匿名也能看热榜,但部分回答只有摘要。配上 cookie 才能看完整答案:

1. 浏览器登录 [知乎](https://www.zhihu.com/)
2. F12 → Application → Cookies → `https://www.zhihu.com`
3. 复制 `z_c0` 的值
4. 编辑 `~/.config/zhcli/config.toml`(首次运行会自动生成模板):

```toml
[cookies]
z_c0 = "贴在这里"
d_c0 = ""   # 可选
```

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
| `o` | 在浏览器打开当前问题 |
| `q` | 退出 |

## 已知限制

- 不渲染图片、视频、公式(LaTeX 保留为原文)
- 不支持点赞 / 评论 / 收藏
- 知乎随时可能改接口或加签名,接口失效需要更新 `zhcli/api.py`
