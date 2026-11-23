from pydantic import Field, PrivateAttr, computed_field
from pydantic_settings import BaseSettings


# 本服务对外公开的根地址。非法配置会回退到这个生产首页，避免本地值写坏 canonical。
DEFAULT_PUBLIC_BASE_URL = "https://98trss.chainseek.top"

# 静态请求头（非环境变量配置）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class Settings(BaseSettings):
    """应用配置，所有环境变量通过 Pydantic Field 声明。"""

    base_url: str = Field(
        default="https://sehuatang.org",
        description="目标网站地址（默认 sehuatang.org，也可改为 .net）",
    )
    public_base_url: str = Field(
        default=DEFAULT_PUBLIC_BASE_URL,
        description="本服务对外公开的根地址，仅用于首页 canonical。只接受 http/https，不要写入账号或密钥。",
    )
    cache_ttl: int = Field(
        default=900,
        description="缓存过期时间（秒），默认 15 分钟",
    )
    request_timeout: int = Field(
        default=30,
        description="HTTP 请求超时时间（秒）",
    )
    session_cookie: str = Field(
        default="",
        description="可选，手动注入浏览器 cookie 用于绕过 Cloudflare。来源：浏览器 DevTools → Application → Cookies → 复制所有 cookie 拼接",
    )

    # 板块数据（私有属性，由 model_validator 构建）
    _forum_groups: dict = PrivateAttr(default_factory=dict)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def model_post_init(self, __context) -> None:
        """在模型初始化后构建板块分类数据。"""
        self._forum_groups = {
            "原创BT电影区": {
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
            },
            "色花图片区": {
                155: "原创自拍",
                125: "转贴自拍",
                50: "华人街拍",
                48: "亚洲性爱",
                49: "欧美性爱",
                117: "卡通动漫",
                165: "套图下载",
            },
            "综合讨论": {
                95: "综合讨论",
            },
        }

    @property
    def FORUM_GROUPS(self) -> dict:
        """板块分类（按分组）。"""
        return self._forum_groups

    @computed_field
    @property
    def ALL_FORUMS(self) -> dict[int, str]:
        """合并所有板块 fid → 名称 映射。"""
        result: dict[int, str] = {}
        for group in self._forum_groups.values():
            result.update(group)
        return result


settings = Settings()

# ── 向后兼容：保留模块级变量供现有代码 import ──
BASE_URL = settings.base_url
CACHE_TTL = settings.cache_ttl
REQUEST_TIMEOUT = settings.request_timeout
SESSION_COOKIE = settings.session_cookie
FORUM_GROUPS = settings.FORUM_GROUPS
ALL_FORUMS = settings.ALL_FORUMS
