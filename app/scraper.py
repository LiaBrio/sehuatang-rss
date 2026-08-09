import re
import httpx
from html import unescape
from bs4 import BeautifulSoup
from app.config import BASE_URL, HEADERS, REQUEST_TIMEOUT, SESSION_COOKIE
from app.cache import cache_get, cache_set

# safeid 缓存
_safe_cookie: dict = {}


async def _get_client() -> httpx.AsyncClient:
    """创建配置好的 httpx 客户端"""
    client = httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
        verify=False,  # 某些部署环境可能需要
    )
    # 注入手动配置的 cookie
    if SESSION_COOKIE:
        client.cookies.update(
            dict(item.split("=", 1) for item in SESSION_COOKIE.split(";") if "=" in item)
        )
    return client


async def _ensure_safeid(client: httpx.AsyncClient):
    """确保获取 safeid cookie"""
    if "_safe" in client.cookies:
        return

    # 检查全局缓存
    if "safeid" in _safe_cookie:
        client.cookies.set("_safe", _safe_cookie["safeid"])
        return

    try:
        resp = await client.get(BASE_URL)
        # 无论状态码如何，尝试从 HTML 提取 safeid
        html = resp.text
        match = re.search(r"safeid='([^']+)'", html)
        if match:
            safeid = match.group(1)
            _safe_cookie["safeid"] = safeid
            client.cookies.set("_safe", safeid)
    except Exception:
        pass


async def fetch_forum_threads(fid: int = None, limit: int = 20) -> list[dict]:
    """
    获取板块帖子列表。
    fid=None 时获取首页最新帖子（status=2）
    返回: [{"title": str, "link": str, "author": str, "date": str, "fid": int}]
    """
    cache_key = f"forum:{fid or 'home'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached[:limit]

    client = await _get_client()
    await _ensure_safeid(client)

    if fid:
        url = f"{BASE_URL}/forum.php?mod=forumdisplay&orderby=dateline&fid={fid}"
    else:
        url = f"{BASE_URL}/forum.php?mod=forumdisplay&orderby=dateline&status=2"

    try:
        resp = await client.get(url)

        # 如果请求失败，可能是 safeid 失效，重新获取
        if resp.status_code != 200 or "safeid" in resp.text:
            client.cookies.clear()
            _safe_cookie.clear()
            await _ensure_safeid(client)
            resp = await client.get(url)
    except Exception as e:
        await client.aclose()
        raise RuntimeError(f"Failed to fetch forum page: {e}")

    await client.aclose()

    soup = BeautifulSoup(resp.text, "lxml")
    threads = []

    # Discuz! X 标准帖子列表解析
    thread_tbody_list = soup.select("tbody[id^=normalthread]")

    for tbody in thread_tbody_list:
        try:
            # 标题和链接
            title_el = tbody.select_one("a.xst")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if href.startswith("http"):
                link = href
            else:
                link = f"{BASE_URL}/{href}"

            # 作者
            author_el = tbody.select_one("td.by cite a")
            author = author_el.get_text(strip=True) if author_el else "Unknown"

            # 发布时间
            date_el = tbody.select_one("td.by em")
            date_str = date_el.get_text(strip=True) if date_el else ""

            # 提取帖子 tid（从链接中）
            tid_match = re.search(r"tid=(\d+)", link)
            tid = int(tid_match.group(1)) if tid_match else 0

            threads.append({
                "title": title,
                "link": link,
                "author": author,
                "date": date_str,
                "tid": tid,
                "fid": fid,
            })
        except Exception:
            continue

    cache_set(cache_key, threads)
    return threads[:limit]


def _empty_detail() -> dict:
    return {
        "description": "",
        "magnet": None,
        "magnets": [],
        "images": [],
        "enclosure_url": None,
    }


def _absolute_url(url: str) -> str:
    """把站内相对路径补全为绝对 URL"""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return f"{BASE_URL}/{url.lstrip('/')}"


async def fetch_thread_detail(tid: int) -> dict:
    """
    获取帖子详情（摘要内容 + 图片 + 磁力链接）。
    返回: {
        "description": str,          # 正文 HTML，img 的 src 已替换为真实 URL
        "magnet": str | None,        # 第一个磁力链接
        "magnets": list[str],        # 所有磁力链接
        "images": list[str],         # 所有图片的绝对 URL
        "enclosure_url": str | None,
    }
    """
    cache_key = f"thread:{tid}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    client = await _get_client()
    await _ensure_safeid(client)

    url = f"{BASE_URL}/forum.php?mod=viewthread&tid={tid}&extra=page%3D1"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            await client.aclose()
            return _empty_detail()
    except Exception:
        await client.aclose()
        return _empty_detail()

    await client.aclose()

    soup = BeautifulSoup(resp.text, "lxml")

    # 帖子正文
    post_msg = soup.select_one("td[id^=postmessage]")
    description = ""
    images: list[str] = []
    if post_msg:
        # 处理图片：Discuz 把真实 URL 放在 file / zoomfile 属性中，src 常为占位图
        for img in post_msg.find_all("img"):
            real_url = img.get("file") or img.get("zoomfile") or img.get("data-original")
            if real_url:
                img["src"] = real_url
            src = _absolute_url(img.get("src", "").strip())
            # 过滤表情、占位等站内静态小图
            if not src or "/static/image/" in src or src.endswith("none.gif"):
                continue
            img["src"] = src
            if src not in images:
                images.append(src)
        # td 脱离 table 后在阅读器中可能被丢弃，改为 div
        post_msg.name = "div"
        description = str(post_msg)

    # 磁力链接：优先 blockcode 代码块，再全页正则兜底
    magnets: list[str] = []
    for bc in soup.select("div.blockcode"):
        for li in bc.select("li"):
            text = li.get_text(strip=True)
            if text.startswith("magnet:") and text not in magnets:
                magnets.append(text)

    for found in re.findall(r"magnet:\?xt=urn:[a-zA-Z0-9]+:[a-zA-Z0-9]+[^\s\"'<>]*", resp.text):
        found = unescape(found)
        if found not in magnets:
            magnets.append(found)

    # 种子附件
    enclosure_url = None
    attnm = soup.select_one("p.attnm a[href]")
    if attnm:
        enclosure_url = _absolute_url(attnm.get("href", ""))

    result = {
        "description": description,
        "magnet": magnets[0] if magnets else None,
        "magnets": magnets,
        "images": images,
        "enclosure_url": enclosure_url,
    }

    cache_set(cache_key, result)
    return result
