"""首页元数据和订阅接口的离线测试。不访问来源论坛。"""

import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import ALL_FORUMS, DEFAULT_PUBLIC_BASE_URL, FORUM_GROUPS, settings
from app.homepage import (
    BROWSE_LABEL,
    BROWSE_PATH,
    INTRO_TEXT,
    LIMITATIONS,
    PAGE_DESCRIPTION,
    PAGE_TITLE,
    SUBSCRIBE_STEPS,
    directory_has_adult_sections,
    render_homepage,
    resolve_public_base_url,
)
from app.main import app

# 当前仓库目录。测试锁住这些链接，避免首页改版时丢掉板块。
EXPECTED_LINKS = {
    2: "国产原创",
    36: "亚洲无码原创",
    37: "亚洲有码原创",
    103: "高清中文字幕",
    107: "三级写真",
    160: "VR视频",
    104: "素人有码",
    38: "欧美无码",
    151: "4K原版",
    152: "韩国主播",
    39: "动漫原创",
    155: "原创自拍",
    125: "转贴自拍",
    50: "华人街拍",
    48: "亚洲性爱",
    49: "欧美性爱",
    117: "卡通动漫",
    165: "套图下载",
    95: "综合讨论",
}
EXPECTED_GROUPS = ("原创BT电影区", "色花图片区", "综合讨论")
GRAPHIC_TERMS = ("无码", "有码", "性爱", "自拍", "写真", "色情")

SAMPLE_THREAD = {
    "title": "sample-thread",
    "link": "https://example.test/thread/1",
    "author": "tester",
    "date": "2026-01-02 03:04:05",
    "tid": 7,
    "fid": None,
}
SAMPLE_DETAIL = {
    "description": "<div>plain summary</div>",
    "magnet": None,
    "magnets": [],
    "images": [],
    "enclosure_url": None,
}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_attrs = {}
        self.metas = []
        self.links = []
        self.anchors = []
        self.h1 = []
        self.h2 = []
        self.title = ""
        self._capture = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.html_attrs = data
        elif tag == "meta":
            self.metas.append(data)
        elif tag == "link":
            self.links.append(data)
        elif tag == "a":
            self.anchors.append({"href": data.get("href", ""), "text": ""})
            self._capture = "a"
            self._buf = []
        elif tag in {"h1", "h2", "title"}:
            self._capture = tag
            self._buf = []

    def handle_endtag(self, tag):
        if self._capture != tag:
            return
        text = "".join(self._buf).strip()
        if tag == "h1":
            self.h1.append(text)
        elif tag == "h2":
            self.h2.append(text)
        elif tag == "title":
            self.title = text
        elif tag == "a":
            self.anchors[-1]["text"] = text
        self._capture = None
        self._buf = []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)


def _parse(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    return page


def _meta(page: _Page, name: str) -> str | None:
    for item in page.metas:
        if item.get("name") == name:
            return item.get("content")
    return None


class PublicUrlTests(unittest.TestCase):
    def test_default_and_local_urls(self):
        self.assertEqual(
            resolve_public_base_url(None),
            "https://98trss.chainseek.top",
        )
        self.assertEqual(resolve_public_base_url("   "), DEFAULT_PUBLIC_BASE_URL)
        self.assertEqual(
            resolve_public_base_url("https://98trss.chainseek.top/"),
            "https://98trss.chainseek.top",
        )
        self.assertEqual(
            resolve_public_base_url("http://127.0.0.1:8000"),
            "http://127.0.0.1:8000",
        )
        self.assertEqual(
            resolve_public_base_url("http://localhost:8000/"),
            "http://localhost:8000",
        )
        self.assertEqual(
            resolve_public_base_url("http://[::1]:8000"),
            "http://[::1]:8000",
        )

    def test_strips_query_and_keeps_path(self):
        self.assertEqual(
            resolve_public_base_url("https://example.com/app?q=1#section"),
            "https://example.com/app",
        )

    def test_rejects_unsafe_values(self):
        unsafe = [
            "javascript:alert(1)",
            "data:text/html,hi",
            "https://user:pass@example.com",
            "https://example.com/\"><script>",
            "file:///tmp/index.html",
            "https:///missing-host",
        ]
        for value in unsafe:
            with self.subTest(value=value):
                self.assertEqual(resolve_public_base_url(value), DEFAULT_PUBLIC_BASE_URL)


class HomepageRenderTests(unittest.TestCase):
    def test_metadata_language_and_rating(self):
        html = render_homepage()
        page = _parse(html)
        self.assertEqual(page.html_attrs.get("lang"), "zh-CN")
        self.assertEqual(page.title, PAGE_TITLE)
        self.assertEqual(page.h1, [PAGE_TITLE])
        self.assertEqual(_meta(page, "viewport"), "width=device-width, initial-scale=1")
        self.assertEqual(_meta(page, "description"), PAGE_DESCRIPTION)
        self.assertEqual(_meta(page, "rating"), "adult")
        canonical = [item for item in page.links if item.get("rel") == "canonical"]
        self.assertEqual(
            [item.get("href") for item in canonical],
            ["https://98trss.chainseek.top/"],
        )
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<img", html.lower())
        self.assertNotIn('name="robots"', html.lower())
        for term in GRAPHIC_TERMS:
            self.assertNotIn(term, PAGE_TITLE)
            self.assertNotIn(term, PAGE_DESCRIPTION)
            self.assertNotIn(term, INTRO_TEXT)
            self.assertNotIn(term, BROWSE_LABEL)
            for step in SUBSCRIBE_STEPS:
                self.assertNotIn(term, step)
            for item in LIMITATIONS:
                self.assertNotIn(term, item)

    def test_instructions_and_existing_directory(self):
        html = render_homepage()
        page = _parse(html)
        self.assertIn(INTRO_TEXT, html)
        self.assertIn("如何订阅", page.h2)
        self.assertIn("当前限制", page.h2)
        for step in SUBSCRIBE_STEPS:
            self.assertIn(step, html)
        self.assertIn("15 分钟", html)
        for item in LIMITATIONS:
            self.assertIn(item, html)
        self.assertIn("来源站点：https://sehuatang.org", html)
        self.assertIn("Powered by sehuatang-rss", html)

        by_href = {anchor["href"]: anchor["text"] for anchor in page.anchors}
        feed_hrefs = [anchor["href"] for anchor in page.anchors if anchor["href"].startswith("/rss")]
        self.assertEqual(by_href["/rss"], "全部最新帖子")
        self.assertEqual(set(feed_hrefs), {"/rss", *(f"/rss/{fid}" for fid in EXPECTED_LINKS)})
        self.assertEqual(len(feed_hrefs), 20)
        for fid, name in EXPECTED_LINKS.items():
            self.assertEqual(by_href[f"/rss/{fid}"], name)
            self.assertIn(f"fid={fid}", html)
        self.assertEqual(ALL_FORUMS, EXPECTED_LINKS)
        for group in EXPECTED_GROUPS:
            self.assertIn(group, page.h2)
        browse_links = [anchor for anchor in page.anchors if anchor["href"] == BROWSE_PATH]
        self.assertEqual([(anchor["text"]) for anchor in browse_links], [BROWSE_LABEL])
        self.assertNotIn("/browse?", html)
        self.assertNotIn("/browser", html)
        self.assertNotIn('href="https://sehuatang.org"', html)

    def test_rating_follows_directory_contents(self):
        self.assertTrue(directory_has_adult_sections(FORUM_GROUPS))
        plain = render_homepage(
            groups={"讨论": {1: "综合讨论"}},
            source_base_url="https://example.org",
            public_base_url="http://127.0.0.1:8000/",
            cache_ttl=45,
        )
        plain_page = _parse(plain)
        self.assertIsNone(_meta(plain_page, "rating"))
        self.assertEqual(
            [item.get("href") for item in plain_page.links if item.get("rel") == "canonical"],
            ["http://127.0.0.1:8000/"],
        )
        self.assertIn("45 秒", plain)
        self.assertEqual(
            {anchor["href"] for anchor in plain_page.anchors if anchor["href"].startswith("/rss")},
            {"/rss", "/rss/1"},
        )
        self.assertEqual(
            [anchor["href"] for anchor in plain_page.anchors if anchor["href"] == BROWSE_PATH],
            [BROWSE_PATH],
        )

        marked = render_homepage(
            groups={"分区": {8: "示例无码"}},
            public_base_url="javascript:alert(1)",
        )
        marked_page = _parse(marked)
        self.assertEqual(_meta(marked_page, "rating"), "adult")
        self.assertEqual(
            [item.get("href") for item in marked_page.links if item.get("rel") == "canonical"],
            [f"{DEFAULT_PUBLIC_BASE_URL}/"],
        )
        self.assertNotIn("<script", marked.lower())

    def test_configured_names_are_escaped(self):
        html = render_homepage(
            groups={"<分组>": {3: "名称<b>"}},
            source_base_url="https://example.org/?q=<x>",
            public_base_url="https://example.com",
        )
        self.assertIn("&lt;分组&gt;", html)
        self.assertIn("名称&lt;b&gt;", html)
        self.assertIn("https://example.org/?q=&lt;x&gt;", html)
        self.assertNotIn("<b>", html)
        self.assertIn('href="/rss/3"', html)


class HomepageEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._public_base_url = settings.public_base_url

    def tearDown(self):
        settings.public_base_url = self._public_base_url

    def test_get_homepage_without_network(self):
        with patch("app.main.fetch_forum_threads", new_callable=AsyncMock) as fetch_threads, \
                patch("app.main.fetch_thread_detail", new_callable=AsyncMock) as fetch_detail, \
                patch("app.scraper.httpx.AsyncClient", side_effect=AssertionError("network disabled")):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("utf-8", response.headers["content-type"].lower())
        self.assertIn(PAGE_TITLE, response.text)
        self.assertEqual(fetch_threads.await_count, 0)
        self.assertEqual(fetch_detail.await_count, 0)

    def test_endpoint_reads_public_base_url(self):
        settings.public_base_url = "http://127.0.0.1:8000"
        ok = self.client.get("/")
        self.assertIn('href="http://127.0.0.1:8000/"', ok.text)

        settings.public_base_url = "javascript:alert(1)"
        rejected = self.client.get("/")
        self.assertEqual(rejected.status_code, 200)
        self.assertIn(f'href="{DEFAULT_PUBLIC_BASE_URL}/"', rejected.text)
        self.assertNotIn("javascript:", rejected.text)


class FeedEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _mock_feeds(self):
        threads = patch("app.main.fetch_forum_threads", new_callable=AsyncMock)
        details = patch("app.main.fetch_thread_detail", new_callable=AsyncMock)
        network = patch(
            "app.scraper.httpx.AsyncClient",
            side_effect=AssertionError("network disabled"),
        )
        return threads, details, network

    def test_aggregate_and_category_feeds_keep_their_responses(self):
        threads, details, network = self._mock_feeds()
        with threads as fetch_threads, details as fetch_detail, network:
            fetch_threads.return_value = [dict(SAMPLE_THREAD)]
            fetch_detail.return_value = dict(SAMPLE_DETAIL)

            home = self.client.get("/rss")
            category = self.client.get("/rss/103")

        self.assertEqual(fetch_threads.await_count, 2)
        self.assertEqual(fetch_detail.await_count, 2)
        for response, title, description in (
            (home, "色花堂 - 最新帖子", "色花堂论坛最新帖子"),
            (category, "色花堂 - 高清中文字幕", "色花堂论坛 高清中文字幕 板块最新帖子"),
        ):
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers["content-type"].startswith("application/rss+xml"))
            self.assertEqual(response.headers["cache-control"], "public, max-age=900")
            channel = ET.fromstring(response.content).find("channel")
            self.assertEqual(channel.findtext("title"), title)
            self.assertEqual(channel.findtext("description"), description)
            self.assertEqual(channel.findtext("link"), "https://sehuatang.org")
            self.assertEqual(channel.findtext("language"), "zh-CN")
            item = channel.find("item")
            self.assertEqual(item.findtext("title"), "sample-thread")
            self.assertIn("plain summary", response.text)

    def test_unknown_forum_and_fetch_failure_stay_the_same(self):
        with patch("app.main.fetch_forum_threads", new_callable=AsyncMock) as fetch_threads, \
                patch("app.scraper.httpx.AsyncClient", side_effect=AssertionError("network disabled")):
            missing = self.client.get("/rss/999999")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(fetch_threads.await_count, 0)

            fetch_threads.side_effect = RuntimeError("offline")
            failed = self.client.get("/rss")
        self.assertEqual(failed.status_code, 502)
        self.assertIn("抓取失败", failed.json()["detail"])

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})

        rejected = self.client.get("/rss/not-a-number")
        self.assertEqual(rejected.status_code, 422)

    def test_browse_routes_are_absent_from_this_source(self):
        """线上 /browse 不在本仓库。锁定这个差异，避免把未实现的页面写成 200。"""
        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertNotIn("/browse", paths)
        self.assertNotIn("/browse/{fid}", paths)
        self.assertNotIn("/browser", paths)
        for path in ("/browser", "/browse", "/browse?all=1", "/browse/95", "/browse/95?page=2"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)


if __name__ == "__main__":
    unittest.main()
