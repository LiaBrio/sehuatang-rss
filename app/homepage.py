"""首页 HTML。只描述订阅目录，不改动 RSS 抓取。"""

import ipaddress
from html import escape
from urllib.parse import urlsplit

from app.config import DEFAULT_PUBLIC_BASE_URL, settings

PAGE_TITLE = "论坛 RSS 订阅目录"
PAGE_DESCRIPTION = (
    "本站的论坛板块 RSS 订阅目录，说明如何订阅，以及总频道可能为空、"
    "缓存时间和来源站可用性等限制。授权与隐私请查看来源站和阅读器。"
)
INTRO_TEXT = (
    "本站提供论坛板块的 RSS 订阅地址。请把本站链接加入阅读器；"
    "下方的来源站点只用来说明这些板块对应哪一个论坛。"
    "同一批板块也可以从板块浏览页打开，地址是 /browse。"
)
BROWSE_PATH = "/browse"
BROWSE_LABEL = "板块浏览"
SUBSCRIBE_STEPS = (
    "从下方目录选择一个板块，复制对应链接。",
    "在 RSS 阅读器中添加订阅，并粘贴该链接。目录中的地址以 /rss/ 开头；阅读器里请使用带本站域名的完整地址。",
)
LIMITATIONS = (
    "「全部最新帖子」（/rss）会给出频道，但里面可能没有条目。没有条目时请改订具体板块。抓取和汇总方式保持原样。",
    "是否能看到内容，取决于来源站点当时能否访问。",
    "授权范围和隐私条款需查看来源站与阅读器自身的说明。本页只解释订阅地址怎么用。",
    "目录中的名称沿用现有板块名，只用来区分订阅地址。",
)

# 目录里仍使用这些板块名时，按 Google 对含露骨内容页面的说明加上 adult rating。
_ADULT_SECTION_MARKERS = ("无码", "有码", "性爱", "自拍", "写真")

_STYLE = """<style>
:root { color-scheme: light; }
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0 auto;
  padding: 1.25rem 1rem 2.5rem;
  max-width: 40rem;
  font-family: system-ui, -apple-system, "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif;
  font-size: 1rem;
  line-height: 1.55;
  color: #1a1a1a;
  background: #fff;
  overflow-wrap: anywhere;
}
header p { margin: 0.75rem 0 0; }
.site-nav { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
.site-nav a {
  display: inline-flex;
  align-items: center;
  min-height: 2.75rem;
  padding: 0.35rem 0.8rem;
  border: 1px solid #c8c8c8;
  border-radius: 0.375rem;
  color: #0848a8;
  text-decoration: none;
}
.site-nav a[aria-current="page"] { border-color: #0848a8; font-weight: 600; }
h1 { margin: 0; font-size: 1.5rem; line-height: 1.3; font-weight: 700; }
h2 { margin: 1.75rem 0 0.5rem; font-size: 1.125rem; line-height: 1.35; font-weight: 600; }
ol, ul.notes { margin: 0.25rem 0 0; padding-left: 1.25rem; }
ol li, ul.notes li { margin: 0.4rem 0; }
.source { margin: 0.75rem 0 0; }
.feed-list { list-style: none; margin: 0; padding: 0; }
.feed-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 2.75rem;
  border-bottom: 1px solid #e6e6e6;
}
.feed-list a {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  min-height: 2.75rem;
  padding: 0.5rem 0;
  color: #0848a8;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.15em;
}
.feed-list a:hover { text-decoration: underline; }
a:focus-visible { outline: 2px solid #0848a8; outline-offset: 2px; }
.badge {
  flex: none;
  background: #f3f3f3;
  color: #333;
  border-radius: 0.25rem;
  padding: 0.1rem 0.45rem;
  font-size: 0.75rem;
  line-height: 1.4;
}
footer {
  margin-top: 2rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e6e6e6;
  color: #4d4d4d;
  font-size: 0.875rem;
}
@media (max-width: 30rem) {
  body { padding: 1rem 0.875rem 2rem; }
  h1 { font-size: 1.375rem; }
}
</style>"""


def directory_has_adult_sections(groups: dict) -> bool:
    """当前目录名称是否仍包含需要 adult rating 的板块。"""
    for forums in groups.values():
        for name in forums.values():
            text = str(name)
            if any(marker in text for marker in _ADULT_SECTION_MARKERS):
                return True
    return False


def resolve_public_base_url(value: str | None) -> str:
    """把公开根地址收成安全的 http(s) origin，可选路径。失败时用生产默认值。"""
    fallback = DEFAULT_PUBLIC_BASE_URL
    raw = (value or "").strip()
    if not raw or any(ch.isspace() or ch in "<>\"'`\\" for ch in raw):
        return fallback

    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc or "@" in parts.netloc:
        return fallback
    if parts.username or parts.password:
        return fallback
    try:
        host = parts.hostname
        port = parts.port
    except ValueError:
        return fallback
    if not host or port == 0:
        return fallback
    if not _host_ok(host):
        return fallback

    path = parts.path.rstrip("/")
    if path and not path.startswith("/"):
        return fallback
    return f"{parts.scheme}://{parts.netloc}{path}"


def format_cache_ttl(seconds: int) -> str:
    """把缓存秒数写成简短中文。无法识别时用代码里的 15 分钟默认值。"""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "15 分钟"
    if seconds <= 0:
        return "15 分钟"
    if seconds % 60 == 0:
        return f"{seconds // 60} 分钟"
    return f"{seconds} 秒"


def render_homepage(
    groups: dict | None = None,
    source_base_url: str | None = None,
    public_base_url: str | None = None,
    cache_ttl: int | None = None,
) -> str:
    """渲染订阅目录首页。参数缺省时读取当前配置，便于本地覆盖公开地址。"""
    groups = settings.FORUM_GROUPS if groups is None else groups
    source_base_url = settings.base_url if source_base_url is None else source_base_url
    public_base_url = settings.public_base_url if public_base_url is None else public_base_url
    cache_ttl = settings.cache_ttl if cache_ttl is None else cache_ttl

    canonical = _esc(resolve_public_base_url(public_base_url) + "/")
    rating = (
        '<meta name="rating" content="adult">'
        if directory_has_adult_sections(groups)
        else ""
    )
    steps = list(SUBSCRIBE_STEPS)
    steps.append(
        "之后由阅读器定时拉取。服务端缓存时间目前约为 "
        f"{format_cache_ttl(cache_ttl)}，新内容可能不会马上出现。"
    )
    step_html = "".join(f"<li>{_esc(step)}</li>" for step in steps)
    limit_html = "".join(f"<li>{_esc(item)}</li>" for item in LIMITATIONS)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(PAGE_TITLE)}</title>
<meta name="description" content="{_esc(PAGE_DESCRIPTION)}">
<link rel="canonical" href="{canonical}">
{rating}
{_STYLE}
</head>
<body>
<header>
<h1>{_esc(PAGE_TITLE)}</h1>
<p>{_esc(INTRO_TEXT)}</p>
<nav class="site-nav" aria-label="站点页面">
<a href="/" aria-current="page">订阅目录</a>
<a href="{_esc(BROWSE_PATH)}">{_esc(BROWSE_LABEL)}</a>
</nav>
</header>
<main>
<section aria-labelledby="subscribe-heading">
<h2 id="subscribe-heading">如何订阅</h2>
<ol>{step_html}</ol>
</section>
<section aria-labelledby="limits-heading">
<h2 id="limits-heading">当前限制</h2>
<ul class="notes">{limit_html}</ul>
</section>
<nav aria-label="板块订阅目录">
<p class="source">来源站点：{_esc(source_base_url)}</p>
<h2>全部最新帖子</h2>
<ul class="feed-list"><li><a href="/rss">全部最新帖子</a></li></ul>
{_render_directory(groups)}
</nav>
</main>
<footer><p>Powered by sehuatang-rss</p></footer>
</body>
</html>
"""


def _render_directory(groups: dict) -> str:
    parts: list[str] = []
    for group_name, forums in groups.items():
        items: list[str] = []
        for fid, name in forums.items():
            fid_int = int(fid)
            items.append(
                f'<li><a href="/rss/{fid_int}">{_esc(name)}</a>'
                f'<span class="badge">fid={fid_int}</span></li>'
            )
        parts.append(
            f"<h2>{_esc(group_name)}</h2><ul class=\"feed-list\">{''.join(items)}</ul>"
        )
    return "".join(parts)


def _host_ok(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        host.encode("idna")
    except UnicodeError:
        return False
    return "." in host or host == "localhost"


def _esc(value: object) -> str:
    return escape(str(value), quote=True)
