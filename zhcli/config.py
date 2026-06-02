from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "zhcli" / "config.toml"

TEMPLATE = """\
# zhcli 配置文件
# 在浏览器登录知乎后,F12 → Application → Cookies → https://www.zhihu.com
# 把 z_c0 的值复制到下面(d_c0 可选)。不填也能跑,只是部分回答可能拿不到全文。

[cookies]
z_c0 = ""
d_c0 = ""
"""


def load_cookies() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(TEMPLATE, encoding="utf-8")
        return {}

    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)

    raw = data.get("cookies", {})
    return {k: v for k, v in raw.items() if isinstance(v, str) and v}
