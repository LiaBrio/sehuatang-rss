import re
from html import escape
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone, timedelta
from app.config import BASE_URL

CST = timezone(timedelta(hours=8))


def generate_rss_feed(threads: list[dict], details: dict[int, dict] = None,
                       title: str = "色花堂", description: str = "色花堂最新帖子") -> str:
    """
    将帖子列表转换为 RSS 2.0 XML 字符串。
    threads: fetch_forum_threads 返回的列表
    details: {tid: fetch_thread_detail 返回值} 可选
    """
    fg = FeedGenerator()
    fg.title(title)
    fg.link(href=BASE_URL, rel="alternate")
    fg.description(description)
    fg.language("zh-CN")
    fg.lastBuildDate(datetime.now(CST))

    for thread in threads:
        fe = fg.add_entry()
        fe.title(thread["title"])
        fe.link(href=thread["link"])
        fe.author({"name": thread["author"]})

        # 解析日期
        pub_date = _parse_date(thread.get("date", ""))
        if pub_date:
            fe.published(pub_date)

        # 添加详情（如果有）
        tid = thread.get("tid", 0)
        detail = details.get(tid) if details else None
        if detail:
            content = _build_content(detail)
            if content:
                fe.content(content, type="CDATA")
                fe.description(content)

            # 磁力链接作为 enclosure
            if detail.get("magnet"):
                fe.enclosure(detail["magnet"], "0", "application/x-bittorrent")
            elif detail.get("enclosure_url"):
                fe.enclosure(detail["enclosure_url"], "0", "application/x-bittorrent")

        # guid 使用帖子链接
        fe.guid(thread["link"], permalink=True)

    return fg.rss_str(pretty=True)


IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


def _build_content(detail: dict) -> str:
    """
    构建 RSS 条目正文：图片 → 磁力链接 → 正文摘要。
    """
    parts: list[str] = []

    images = detail.get("images") or IMG_SRC_RE.findall(detail.get("description") or "")
    if images:
        imgs = "".join(
            f'<img src="{escape(src, quote=True)}" '
            'style="max-width:100%;height:auto;display:block;margin:10px 0" />'
            for src in images
        )
        parts.append(f'<div class="images">{imgs}</div>')

    magnets = detail.get("magnets") or ([detail["magnet"]] if detail.get("magnet") else [])
    if magnets:
        links = "".join(
            f'<p><a href="{escape(m, quote=True)}">{escape(m)}</a></p>' for m in magnets
        )
        parts.append(
            '<div class="magnet"><p><strong>磁力链接：</strong></p>' + links + "</div>"
        )

    if detail.get("enclosure_url"):
        url = escape(detail["enclosure_url"], quote=True)
        parts.append(f'<div class="torrent"><p><a href="{url}">种子附件下载</a></p></div>')

    # 正文摘要：图片已单独渲染，这里去掉 img 标签避免重复
    body = IMG_TAG_RE.sub("", detail.get("description") or "").strip()
    if body:
        parts.append(f'<div class="content">{body}</div>')

    return "".join(parts)


def _parse_date(date_str: str):
    """尝试解析各种日期格式"""
    if not date_str:
        return None

    date_str = date_str.strip()

    # 常见格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year == 1900:  # 没有年份的情况
                dt = dt.replace(year=datetime.now().year)
            return dt.replace(tzinfo=CST)
        except ValueError:
            continue

    # 相对时间（如 "3 分钟前", "2 小时前", "昨天 12:30"）
    now = datetime.now(CST)
    if "分钟前" in date_str:
        try:
            mins = int(re.search(r"(\d+)", date_str).group(1))
            return now - timedelta(minutes=mins)
        except Exception:
            pass
    elif "小时前" in date_str:
        try:
            hours = int(re.search(r"(\d+)", date_str).group(1))
            return now - timedelta(hours=hours)
        except Exception:
            pass
    elif "天前" in date_str:
        try:
            days = int(re.search(r"(\d+)", date_str).group(1))
            return now - timedelta(days=days)
        except Exception:
            pass
    elif "昨天" in date_str:
        try:
            time_part = date_str.replace("昨天", "").strip()
            t = datetime.strptime(time_part, "%H:%M")
            yesterday = now - timedelta(days=1)
            return yesterday.replace(hour=t.hour, minute=t.minute, second=0, tzinfo=CST)
        except Exception:
            pass

    return None
