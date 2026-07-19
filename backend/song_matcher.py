"""
心随乐动 - 歌曲匹配模块（多源故障转移版）

核心能力：
  1. 多 API 源按优先级自动切换（网易云 → QQ 音乐）
  2. 单个源失败自动重试（最多 2 次）
  3. 搜索请求本地缓存（5 分钟有效期）
  4. 所有源失败时回退本地曲库
  5. 输出格式与之前完全一致
"""

import json
import hashlib
import time
import random
import requests
from typing import Optional

from config import (
    SONGS_DATA_PATH,
    MUSIC_SOURCES,
    CACHE_CONFIG,
    SEARCH_CONFIG
)


# ============================================================
# 1. 缓存管理
# ============================================================

class SearchCache:
    """基于文件的搜索缓存"""

    def __init__(self, config: dict):
        self.enabled = config["enabled"]
        self.ttl = config["ttl_seconds"]
        self.max_entries = config["max_entries"]
        self.file_path = config["file_path"]
        self._data: dict = {}
        self._load()

    def _load(self):
        """从磁盘加载缓存"""
        if not self.enabled:
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def _save(self):
        """持久化缓存到磁盘"""
        if not self.enabled:
            return
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] 缓存写入失败: {e}")

    def _make_key(self, keywords: list) -> str:
        """根据搜索关键词生成缓存键"""
        raw = ",".join(sorted(keywords))
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(self, keywords: list) -> Optional[list]:
        """获取缓存（未过期返回数据，已过期返回 None）"""
        if not self.enabled:
            return None
        key = self._make_key(keywords)
        entry = self._data.get(key)
        if entry is None:
            return None
        # 检查是否过期
        if time.time() - entry.get("ts", 0) > self.ttl:
            del self._data[key]
            return None
        print(f"[CACHE] 命中缓存: keywords={keywords}")
        return entry.get("data")

    def set(self, keywords: list, data: list):
        """写入缓存"""
        if not self.enabled or not data:
            return
        key = self._make_key(keywords)
        self._data[key] = {"ts": time.time(), "data": data}
        # 限制缓存大小（淘汰最旧的）
        if len(self._data) > self.max_entries:
            oldest = min(self._data.items(), key=lambda x: x[1]["ts"])
            del self._data[oldest[0]]
        self._save()


# 全局缓存实例
_cache = SearchCache(CACHE_CONFIG)


# ============================================================
# 2. 各 API 源解析器
# ============================================================

def _parse_netease_response(data: dict) -> list:
    """解析网易云音乐 API 响应"""
    songs = []
    if data.get("code") != 200:
        return songs
    result = data.get("result")
    if not result:
        return songs
    for s in result.get("songs", []):
        song_id = str(s.get("id", ""))
        song_name = s.get("name", "未知歌曲")
        artists = ", ".join(
            a.get("name", "") for a in s.get("artists", [])
        ) or "未知歌手"
        album = s.get("album", {}) or {}
        cover_url = album.get("picUrl", "") or ""
        songs.append({
            "id": f"net_{song_id}",
            "title": song_name,
            "artist": artists,
            "cover_url": cover_url,
            "url": f"https://music.163.com/song?id={song_id}" if song_id else "",
            "source": "netease"
        })
    return songs


def _parse_qqmusic_response(data: dict) -> list:
    """解析 QQ 音乐 API 响应"""
    songs = []
    try:
        song_list = data.get("data", {}).get("song", {}).get("list", [])
    except AttributeError:
        return songs
    for s in song_list:
        if not isinstance(s, dict):
            continue
        song_name = s.get("name", "未知歌曲")
        song_mid = s.get("mid", "")
        song_id = str(s.get("id", ""))
        # QQ 音乐的歌手信息可能在 singer 或 artists 字段
        singers = s.get("singer", [])
        if not singers:
            singers = s.get("artists", [])
        artist_names = ", ".join(
            a.get("name", "") for a in singers if isinstance(a, dict)
        ) or "未知歌手"
        # 专辑封面
        album = s.get("album", {}) or {}
        album_mid = album.get("mid", "")
        cover_url = (
            f"https://y.qq.com/n/yqq/song/{song_mid}.html"
            if song_mid else ""
        )
        songs.append({
            "id": f"qq_{song_id}",
            "title": song_name,
            "artist": artist_names,
            "cover_url": "",
            "url": f"https://y.qq.com/n/yqq/song/{song_mid}.html" if song_mid else "",
            "source": "qqmusic"
        })
    return songs


def _parse_itunes_response(data: dict) -> list:
    """解析 Apple iTunes 搜索 API 响应"""
    songs = []
    for s in data.get("results", []):
        if not isinstance(s, dict):
            continue
        track_id = str(s.get("trackId", ""))
        track_name = s.get("trackName", "")
        if not track_name:
            continue
        artist_name = s.get("artistName", "未知歌手")
        collection_name = s.get("collectionName", "")
        # Apple 的封面图片有尺寸后缀，替换为 300x300
        cover_url = (s.get("artworkUrl100", "") or "").replace(
            "100x100bb", "300x300bb"
        )
        track_url = s.get("trackViewUrl", "") or ""
        songs.append({
            "id": f"it_{track_id}",
            "title": track_name,
            "artist": artist_name,
            "cover_url": cover_url,
            "url": track_url,
            "source": "itunes"
        })
    return songs


def _parse_aggregator_response(data: dict) -> list:
    """
    解析通用聚合 API 响应（兼容 Listen1 / Meting / music-api 风格）

    自动探测多种常见的 JSON 响应结构：
      Listen1 风格: data.list[] 或 data[] (含 name, author, pic_id, url)
      Meting 风格: [] (含 name, artist, cover, url_id)
      music-api风格: data[] (含 title, author, pic, url)
    """
    songs = []
    candidates = []

    # 尝试多种可能的歌曲列表路径
    paths = [
        ["data", "list"],
        ["data"],
        ["list"]
    ]
    for path in paths:
        current = data
        try:
            for key in path:
                current = current[key]
            if isinstance(current, list):
                candidates = current
                break
        except (KeyError, TypeError):
            continue

    if not candidates:
        # 如果顶级就是列表，直接使用
        if isinstance(data, list):
            candidates = data

    for s in candidates[:SEARCH_CONFIG["results_per_keyword"]]:
        if not isinstance(s, dict):
            continue

        # 兼容各种字段命名
        name = (s.get("name") or s.get("title") or s.get("songname") or "")
        if not name:
            continue
        artist = (
            s.get("artist") or s.get("author") or
            s.get("singer") or s.get("artists", [{}])[0].get("name", "") or
            "未知歌手"
        )

        # 兼容各种 id 字段
        song_id = str(
            s.get("id") or s.get("mid") or s.get("songmid") or
            s.get("url_id") or hash(name + artist)
        )

        # 兼容各种封面字段
        cover = (
            s.get("cover") or s.get("pic") or s.get("picUrl") or
            s.get("cover_url") or s.get("album", {}).get("picUrl", "") or
            ""
        )

        # 兼容各种链接字段
        url = (
            s.get("url") or s.get("link") or s.get("play_url") or
            (f"https://music.163.com/song?id={song_id}"
             if song_id and song_id.isdigit() else "")
        )

        songs.append({
            "id": f"ag_{song_id}",
            "title": name,
            "artist": artist if isinstance(artist, str) else str(artist),
            "cover_url": cover,
            "url": url,
            "source": "aggregator"
        })

    return songs


# 解析器注册表（名字 -> 解析函数）
_PARSERS = {
    "netease": _parse_netease_response,
    "qqmusic": _parse_qqmusic_response,
    "itunes": _parse_itunes_response,
    "aggregator": _parse_aggregator_response
}


# ============================================================
# 3. 单源搜索（含重试）
# ============================================================

def _search_single_source(source: dict, keyword: str) -> list:
    """
    调用单个 API 源搜索，支持自动重试

    返回: 歌曲列表（空列表表示失败）
    """
    url = source["search_url"]
    method = source.get("method", "GET").upper()
    headers = source.get("headers", {})
    params_template = source.get("params", {})
    timeout = source.get("timeout", 10)
    max_retries = source.get("retry_count", 2)
    base_delay = SEARCH_CONFIG["retry_delay_base"]

    # 替换参数模板中的 {keyword}
    params = {}
    for k, v in params_template.items():
        if isinstance(v, str) and "{keyword}" in v:
            params[k] = v.replace("{keyword}", keyword)
        else:
            params[k] = v

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if method == "GET":
                resp = requests.get(
                    url, params=params, headers=headers,
                    timeout=timeout
                )
            else:
                resp = requests.post(
                    url, data=params, headers=headers,
                    timeout=timeout
                )

            resp.raise_for_status()

            # 检查响应是否为有效的 JSON
            try:
                data = resp.json()
            except json.JSONDecodeError as e:
                raise ValueError(f"响应不是有效的 JSON: {e}")

            # 通过注册的解析器解析
            parser = _PARSERS.get(source["name"])
            if parser:
                songs = parser(data)
            else:
                # 没有注册解析器时，尝试通用解析
                songs = _generic_parse(data)

            if songs:
                return songs

            # 解析出空列表也视为异常
            raise ValueError("搜索结果为空")

        except requests.Timeout:
            last_error = f"超时 (attempt {attempt + 1})"
        except requests.ConnectionError:
            last_error = f"连接失败 (attempt {attempt + 1})"
        except requests.HTTPError as e:
            last_error = f"HTTP {e.response.status_code}"
            # 4xx 错误不重试（客户端问题）
            if e.response.status_code < 500:
                break
        except Exception as e:
            last_error = str(e)

        # 需要重试时等待
        if attempt < max_retries:
            delay = base_delay * (attempt + 1) + random.uniform(0, 0.5)
            print(f"[RETRY] {source['label']}「{keyword}」{last_error}，{delay:.1f}s 后重试...")
            time.sleep(delay)

    print(f"[FAIL] {source['label']}「{keyword}」所有重试失败: {last_error}")
    return []


def _generic_parse(data: dict) -> list:
    """通用解析器（当没有注册特定解析器时的兜底方案）"""
    # 尝试常见的 JSON 结构
    songs = []
    candidates = []

    # 尝试多种可能的路径
    paths = [
        ["data", "song", "list"],
        ["result", "songs"],
        ["data", "songs"],
        ["songs"],
        ["data", "list"]
    ]

    for path in paths:
        current = data
        try:
            for key in path:
                current = current[key]
            if isinstance(current, list):
                candidates = current
                break
        except (KeyError, TypeError):
            continue

    for s in candidates[:SEARCH_CONFIG["results_per_keyword"]]:
        if not isinstance(s, dict):
            continue
        name = s.get("name") or s.get("title") or s.get("songname") or ""
        if not name:
            continue
        artist = (
            s.get("artist") or s.get("singer") or
            s.get("artists", [{}])[0].get("name", "") or
            ""
        )
        songs.append({
            "id": str(s.get("id", s.get("mid", random.randint(10000, 99999)))),
            "title": name,
            "artist": artist if isinstance(artist, str) else str(artist),
            "cover_url": "",
            "url": s.get("url", ""),
            "source": "unknown"
        })

    return songs


# ============================================================
# 4. 故障转移搜索（多源按优先级切换）
# ============================================================

def _search_with_failover(keywords: list) -> list:
    """
    按优先级逐个尝试 API 源，实现故障转移

    流程：
      1. 先查缓存
      2. 按优先级排序源
      3. 对每个源用关键词搜索
      4. 某个源成功即返回（并写入缓存）
      5. 全部失败返回空列表
    """
    # --- 查缓存 ---
    cached = _cache.get(keywords)
    if cached is not None:
        return cached

    # --- 构造搜索词 ---
    search_queries = _build_search_queries(keywords)

    # --- 按优先级排序 ---
    sources = sorted(MUSIC_SOURCES, key=lambda s: s.get("priority", 99))
    sources_to_try = sources[:SEARCH_CONFIG["max_sources_to_try"]]

    all_results = []
    seen_ids = set()

    for source in sources_to_try:
        if len(all_results) >= SEARCH_CONFIG["results_per_keyword"]:
            break

        # 跳过未配置的源（search_url 为空）
        if not source.get("search_url"):
            print(f"[SKIP] {source['label']} 未配置 search_url，跳过")
            continue

        print(f"[SEARCH] 尝试源: {source['label']} (优先级 {source.get('priority')})")

        for query in search_queries:
            if len(all_results) >= SEARCH_CONFIG["results_per_keyword"]:
                break
            try:
                songs = _search_single_source(source, query)
                for song in songs:
                    if song["id"] not in seen_ids:
                        all_results.append(song)
                        seen_ids.add(song["id"])
                if songs:
                    print(f"[SEARCH] {source['label']}「{query}」→ {len(songs)} 首")
            except Exception as e:
                print(f"[WARN] {source['label']}「{query}」搜索异常: {e}")
                continue

        # 如果当前源找到了足够的结果，不再尝试后面的源
        if len(all_results) >= 5:
            print(f"[SWITCH] {source['label']} 搜索成功，使用该源结果")
            break
        else:
            print(f"[SWITCH] {source['label']} 结果不足，尝试下一源...")

    # --- 写入缓存 ---
    if all_results:
        _cache.set(keywords, all_results)

    return all_results


def _build_search_queries(keywords: list) -> list:
    """根据情绪关键词构造搜索词列表"""
    if not keywords:
        return ["热门音乐"]

    # 主要搜索词：前两个关键词组合
    if len(keywords) >= 2:
        primary = f"{keywords[0]} {keywords[1]}"
    else:
        primary = keywords[0]

    # 备用搜索词：单个关键词
    fallbacks = [kw for kw in keywords if kw != primary]

    # 最终备选
    final_fallback = ["音乐", "热门歌曲"]

    return [primary] + fallbacks + final_fallback


# ============================================================
# 5. 结果格式化（统一输出格式）
# ============================================================

def format_results(songs: list, emotion_result: dict) -> list:
    """将搜索结果格式化为前端接口要求的统一格式"""
    if not songs:
        return []

    emotion_label = emotion_result.get("label", "")
    emotion_keywords = emotion_result.get("keywords", [])
    sentiment = emotion_result.get("sentiment", "neutral")
    intensity = emotion_result.get("intensity", 5)

    results = []
    for song in songs[:10]:  # 最多返回 10 首
        reason = _generate_reason(song, emotion_label, sentiment, intensity)
        tags, tag_type = _generate_tags(song, sentiment, emotion_keywords)

        results.append({
            "id": song.get("id", ""),
            "title": song.get("title", "未知歌曲"),
            "artist": song.get("artist", "未知歌手"),
            "reason": reason,
            "tags": tags[:3],
            "tagType": tag_type,
            "url": song.get("url", ""),
            "cover_url": song.get("cover_url", "")
        })

    return results


def _generate_reason(song: dict, label: str, sentiment: str, intensity: int) -> str:
    """生成推荐理由"""
    title = song.get("title", "")
    artist = song.get("artist", "")
    source = song.get("source", "")

    if sentiment == "negative":
        templates = [
            f"「{title}」温柔的旋律或许能抚慰您此刻的心情",
            f"让{artist}的「{title}」陪伴您度过这段时光",
            f"推荐一首治愈系的「{title}」，希望能给您一些温暖",
            f"{label}的时刻，听听{artist}的「{title}」",
            f"「{title}」- 来自{artist}，愿音乐能治愈心灵"
        ]
    elif sentiment == "positive":
        templates = [
            f"「{title}」充满活力的节奏，与您积极的心情相得益彰",
            f"推荐{artist}的「{title}」，让快乐加倍",
            f"「{title}」- {artist}，让好心情随着旋律飞扬",
            f"这首{artist}的「{title}」和您{label}的心情很配",
            f"用{artist}的「{title}」为美好的心情伴奏"
        ]
    else:
        templates = [
            f"「{title}」的风格与您此刻{label}的心情非常契合",
            f"推荐来自{artist}的「{title}」，希望能触动您的心弦",
            f"轻快的旋律配合{label}的心情，试试「{title}」",
            f"「{title}」- {artist}，一首适合{label}时刻的歌曲",
            f"根据您的心情推荐{artist}的「{title}」，让音乐为您共鸣"
        ]

    if intensity >= 7:
        templates.append(f"充满能量的「{title}」，为您{label}的心情再添一把火")
    elif intensity <= 3:
        templates.append(f"平静舒缓的「{title}」，适合此刻宁静的心境")

    return random.choice(templates)


def _generate_tags(song: dict, sentiment: str, keywords: list) -> tuple:
    """生成情绪标签和颜色类型"""
    tags = keywords[:2] if keywords else ["推荐"]

    if sentiment == "negative":
        tag_type = "sad"
    elif sentiment == "positive":
        tag_type = "joy"
    else:
        tag_type = "calm"

    return tags, tag_type


# ============================================================
# 6. 本地回退匹配（原逻辑保留）
# ============================================================

def load_local_songs() -> list:
    """加载本地曲库"""
    try:
        with open(SONGS_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERROR] 本地曲库加载失败: {e}")
        return []


def jaccard_similarity(set1: set, set2: set) -> float:
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def match_from_local(emotion_result: dict, top_n: int = 10) -> list:
    """从本地曲库匹配歌曲"""
    songs = load_local_songs()
    if not songs:
        return []

    emotion_keywords = set(emotion_result.get("keywords", []))
    sentiment_type = emotion_result.get("sentiment", "neutral")
    intensity = emotion_result.get("intensity", 5)

    scored = []
    for song in songs:
        song_tags = set(song.get("emotion_tags", []))
        ts = jaccard_similarity(emotion_keywords, song_tags)
        sb = 0.15 if song.get("sentiment_type") == sentiment_type else 0
        ib = 0
        mv = song.get("mood_vector", {})
        if mv:
            ed = abs(mv.get("energy", 0.5) - intensity / 10.0)
            if ed < 0.2:
                ib = 0.1
            elif ed < 0.4:
                ib = 0.05
        cb = 0
        if sentiment_type == "negative" and mv and mv.get("calmness", 0.5) > 0.65:
            cb = 0.1
        scored.append((ts + sb + ib + cb, song))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected, seen = [], set()
    for score, song in scored:
        if len(selected) >= top_n:
            break
        if song["id"] not in seen:
            selected.append((score, song))
            seen.add(song["id"])

    if len(selected) < 5:
        for score, song in scored:
            if len(selected) >= 5:
                break
            if song["id"] not in seen:
                selected.append((score, song))
                seen.add(song["id"])

    results = []
    for score, song in selected:
        label = emotion_result.get("label", "")
        sentiment = emotion_result.get("sentiment", "neutral")
        song_tags = song.get("emotion_tags", [])
        matched = list(set(emotion_result.get("keywords", [])) & set(song_tags))

        if score >= 0.3:
            reason = (
                f"歌曲中的「{'、'.join(matched[:2])}」氛围与您{label}的心情高度契合"
                if matched else
                f"这首歌的整体氛围与您{label}的心情很搭"
            )
        elif score >= 0.1:
            if sentiment == "negative":
                reason = f"温柔的旋律能抚慰心灵，给{label}的你一些温暖"
            elif sentiment == "positive":
                reason = f"充满活力的节奏，与您积极的心情相得益彰"
            else:
                reason = f"平静舒缓的旋律，适合此刻的心境"
        else:
            reason = "或许可以换个风格，试试这首不一样的歌曲"

        tag_type = "sad" if sentiment == "negative" else ("joy" if sentiment == "positive" else "calm")

        results.append({
            "id": song["id"],
            "title": song["title"],
            "artist": song["artist"],
            "reason": reason,
            "tags": song_tags[:3],
            "tagType": tag_type,
            "url": "",
            "cover_url": ""
        })

    return results[:top_n]


# ============================================================
# 7. 统一入口
# ============================================================

def match_songs(emotion_result: dict, top_n: int = 10) -> list:
    """
    根据情绪分析结果匹配歌曲（统一入口）

    故障转移流程：
      [缓存命中] → 直接返回
      [不命中]    → 网易云 API（优先级 1）
                  → QQ 音乐 API（优先级 2）
                  → 本地 songs.json（最终回退）
                  → 固定提示

    参数:
        emotion_result: 情绪分析结果
        top_n: 返回歌曲数量

    返回:
        歌曲列表（格式与之前完全一致）
    """
    keywords = emotion_result.get("keywords", [])

    # === 第一阶段：多源 API 搜索 ===
    try:
        api_songs = _search_with_failover(keywords)
        if api_songs:
            print(f"[INFO] API 搜索成功，共 {len(api_songs)} 首歌曲")
            results = format_results(api_songs, emotion_result)
            return results[:top_n]
        else:
            print("[WARN] 所有 API 源搜索均返回空")
    except Exception as e:
        print(f"[WARN] 多源搜索整体失败: {e}")

    # === 第二阶段：回退本地曲库 ===
    print("[INFO] 回退到本地曲库匹配...")
    try:
        local_results = match_from_local(emotion_result, top_n)
        if local_results:
            return local_results
    except Exception as e:
        print(f"[ERROR] 本地匹配失败: {e}")

    # === 第三阶段：最终兜底 ===
    print("[INFO] 所有源均失败，返回固定提示")
    return [
        {
            "id": "fallback_001",
            "title": "未知",
            "artist": "未知",
            "reason": "暂时无法获取推荐歌曲，请稍后再试",
            "tags": ["推荐"],
            "tagType": "calm",
            "url": "",
            "cover_url": ""
        }
    ]
