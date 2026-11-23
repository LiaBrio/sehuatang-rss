# 色花堂 RSS 订阅源

sehuatang.org 论坛 RSS 订阅生成服务

## 功能特性

- 支持首页最新帖子订阅
- 支持按板块订阅（19 个板块可选）
- 15 分钟缓存，避免频繁请求
- 自动处理网站反爬机制（safeid）
- Docker 一键部署
- 可选 cookie 注入绕过 Cloudflare

## 快速开始

### Docker 部署（推荐）

```bash
docker-compose up -d
```

访问 http://localhost:8000 查看可用订阅源

### 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## RSS 订阅地址

| 地址 | 说明 |
|------|------|
| `http://localhost:8000/rss` | 首页最新帖子 |
| `http://localhost:8000/rss/{fid}` | 指定板块（如 `/rss/103` = 高清中文字幕） |

## 板块列表

### 原创BT电影区

- 国产原创 (fid=2)
- 亚洲无码原创 (fid=36)
- 亚洲有码原创 (fid=37)
- 高清中文字幕 (fid=103)
- 三级写真 (fid=107)
- VR视频 (fid=160)
- 素人有码 (fid=104)
- 欧美无码 (fid=38)
- 4K原版 (fid=151)
- 韩国主播 (fid=152)
- 动漫原创 (fid=39)

### 色花图片区

- 原创自拍 (fid=155)
- 转贴自拍 (fid=125)
- 华人街拍 (fid=50)
- 亚洲性爱 (fid=48)
- 欧美性爱 (fid=49)
- 卡通动漫 (fid=117)
- 套图下载 (fid=165)

### 综合讨论

- 综合讨论 (fid=95)

## 配置说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BASE_URL` | `https://sehuatang.org` | 目标网站地址 |
| `PUBLIC_BASE_URL` | `https://98trss.chainseek.top` | 首页 canonical 使用的本站公开根地址 |
| `CACHE_TTL` | `900` | 缓存过期时间（秒） |
| `REQUEST_TIMEOUT` | `30` | HTTP 请求超时（秒） |
| `SESSION_COOKIE` | 空 | 可选，手动注入浏览器 cookie |

## 绕过 Cloudflare

如果 httpx 请求被 Cloudflare 拦截，可以：

1. 在浏览器中打开目标网站
2. 打开开发者工具 → Application → Cookies
3. 复制所有 cookie，设置到 `SESSION_COOKIE` 环境变量

## 技术栈

- Python 3.12
- FastAPI + Uvicorn
- httpx（异步 HTTP 客户端）
- BeautifulSoup4（HTML 解析）
- feedgen（RSS 生成）

## 免责声明

本项目仅供学习交流使用，请遵守当地法律法规。
