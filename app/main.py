import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse
from app.config import ALL_FORUMS
from app.homepage import render_homepage
from app.scraper import fetch_forum_threads, fetch_thread_detail
from app.rss_generator import generate_rss_feed

app = FastAPI(title="色花堂 RSS", description="sehuatang.org RSS 订阅源")

# 抓取帖子详情时的最大并发数
DETAIL_CONCURRENCY = 3


async def _fetch_all_details(threads: list[dict]) -> dict[int, dict]:
    """并发获取所有帖子的详情（图片 + 磁力链接），失败的帖子跳过。"""
    semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def worker(tid: int):
        async with semaphore:
            try:
                return tid, await fetch_thread_detail(tid)
            except Exception:
                return tid, None

    tids = [t["tid"] for t in threads if t.get("tid")]
    results = await asyncio.gather(*(worker(tid) for tid in tids))
    return {tid: detail for tid, detail in results if detail}


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页：列出所有可用板块及 RSS 链接。"""
    return render_homepage()


@app.get("/rss")
async def rss_home():
    """首页最新帖子 RSS"""
    try:
        threads = await fetch_forum_threads(fid=None, limit=20)
        # 获取全部帖子的详情（Semaphore 控制并发）
        details = await _fetch_all_details(threads)

        xml = generate_rss_feed(threads, details,
                                 title="色花堂 - 最新帖子",
                                 description="色花堂论坛最新帖子")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=900"})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"抓取失败: {str(e)}")


@app.get("/rss/{fid}")
async def rss_forum(fid: int):
    """指定板块 RSS"""
    if fid not in ALL_FORUMS:
        raise HTTPException(status_code=404, detail=f"板块 fid={fid} 不存在")

    try:
        threads = await fetch_forum_threads(fid=fid, limit=20)
        # 获取全部帖子的详情（Semaphore 控制并发）
        details = await _fetch_all_details(threads)

        forum_name = ALL_FORUMS[fid]
        xml = generate_rss_feed(threads, details,
                                 title=f"色花堂 - {forum_name}",
                                 description=f"色花堂论坛 {forum_name} 板块最新帖子")
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=900"})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"抓取失败: {str(e)}")


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}
