"""
心随乐动 - 配置文件
"""

import os

# ============================================================
# AI 模型 API 配置
# ============================================================
AI_CONFIG = {
    "api_key": os.environ.get("DS_API_KEY", ""),
    "base_url": os.environ.get("DS_BASE_URL", "https://api.deepseek.com"),
    "model": os.environ.get("DS_MODEL", "deepseek-chat"),
    "temperature": 0.3,
    "max_tokens": 512,
    "timeout": 30
}
AI_ENABLED = bool(AI_CONFIG["api_key"])

# ============================================================
# 服务器配置
# ============================================================
SERVER_CONFIG = {
    "host": os.environ.get("HOST", "0.0.0.0"),
    "port": int(os.environ.get("PORT", "5000")),
    "debug": os.environ.get("FLASK_DEBUG", "false").lower() == "true"
}

# ============================================================
# 歌曲数据路径（本地回退曲库）
# ============================================================
SONGS_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "songs.json"
)

# ============================================================
# 多音乐 API 源配置（优先级 1→2→3→4 依次尝试）
# ============================================================
# 系统按 priority 升序尝试每个源，某个源成功即停止
# 每个源可独立配置重试次数和超时时间
MUSIC_SOURCES = [
    # -------------------------------------------------------
    # 源 1：网易云音乐搜索 API（无需密钥，中文曲库首选）
    # -------------------------------------------------------
    {
        "name": "netease",
        "label": "网易云音乐",
        "priority": 1,
        "search_url": os.environ.get(
            "MUSIC_NETEASE_URL",
            "https://music.163.com/api/search/get/web"
        ),
        "method": "GET",
        "params": {
            "s": "{keyword}",
            "type": 1,
            "limit": 15,
            "offset": 0
        },
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/"
        },
        "retry_count": 2,
        "timeout": 10
    },

    # -------------------------------------------------------
    # 源 2：QQ 音乐搜索 API（无需密钥，中文曲库第一备用）
    # -------------------------------------------------------
    {
        "name": "qqmusic",
        "label": "QQ音乐",
        "priority": 2,
        "search_url": os.environ.get(
            "MUSIC_QQ_URL",
            "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
        ),
        "method": "GET",
        "params": {
            "w": "{keyword}",
            "format": "json",
            "inCharset": "utf8",
            "outCharset": "utf-8",
            "notice": 0,
            "platform": "yqq.json",
            "needNewCode": 0,
            "p": 1,
            "n": 15,
            "t": 0,
            "aggr": 1,
            "cr": 1,
            "catZhida": 0
        },
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://y.qq.com/"
        },
        "retry_count": 2,
        "timeout": 10
    },

    # -------------------------------------------------------
    # 源 3：Apple iTunes 搜索 API（无需密钥，国际曲库兜底）
    # -------------------------------------------------------
    # 极其稳定，苹果官方 API，无需注册和密钥
    # 适合欧美音乐搜索，作为中文 API 失效时的可靠备选
    {
        "name": "itunes",
        "label": "Apple Music",
        "priority": 3,
        "search_url": "https://itunes.apple.com/search",
        "method": "GET",
        "params": {
            "term": "{keyword}",
            "entity": "song",
            "limit": 15
        },
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "retry_count": 1,
        "timeout": 10
    },

    # -------------------------------------------------------
    # 源 4：通用聚合 API（Listen1 / Meting 风格，需自行部署）
    # -------------------------------------------------------
    # 这是一个可配置的通用聚合源，适配以下项目：
    #   - Listen1 API:    https://github.com/toulanboy/listen1_api
    #   - Meting API:     https://github.com/metowolf/Meting
    #   - music-api(PHP): https://gitcode.com/gh_mirrors/mu/music-api
    #
    # 部署后设置环境变量 MUSIC_AGGREGATOR_URL 即可启用
    # 未配置时自动跳过此源，不影响其他源
    {
        "name": "aggregator",
        "label": "聚合音乐(自部署)",
        "priority": 4,
        "search_url": os.environ.get(
            "MUSIC_AGGREGATOR_URL",
            ""  # 为空时自动跳过此源
        ),
        "method": "GET",
        # Listen1 风格:  ?source=netease&keywords={keyword}
        # Meting 风格:    ?server=netease&type=search&id={keyword}
        # music-api风格:  ?platform=netease&action=search&keyword={keyword}
        #
        # 这里使用通用参数模板，您可以根据实际部署的项目修改
        "params": {
            "keywords": "{keyword}",
            "limit": 15
        },
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "retry_count": 1,
        "timeout": 8
    }
]

# ============================================================
# 缓存配置
# ============================================================
CACHE_CONFIG = {
    "enabled": True,
    "ttl_seconds": 300,          # 缓存有效期 5 分钟
    "max_entries": 200,          # 最大缓存条目数
    "file_path": os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "cache",
        "search_cache.json"
    )
}

# ============================================================
# 搜索配置
# ============================================================
# max_sources_to_try 自动取 MUSIC_SOURCES 的长度
SEARCH_CONFIG = {
    "max_sources_to_try": len(MUSIC_SOURCES),
    "retry_delay_base": 1.0,
    "results_per_keyword": 15
}
