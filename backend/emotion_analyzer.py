"""
心随乐动 - 情绪分析模块

支持两种模式：
  1. AI 模式：调用 ds-V4-Flash（OpenAI 兼容接口）进行深度学习分析
  2. 本地模式：基于关键词规则进行本地分析（无需 API Key，作为回退）
"""

import json
import re
from config import AI_CONFIG, AI_ENABLED

# ============================================================
# 1. AI 模式 - 调用 ds-V4-Flash
# ============================================================

# 只有在有 API Key 时才导入 openai
openai = None
if AI_ENABLED:
    import openai as _openai
    openai = _openai
    openai.api_key = AI_CONFIG["api_key"]
    openai.base_url = AI_CONFIG["base_url"]


# 情绪分析的 Prompt
EMOTION_ANALYSIS_PROMPT = """你是一个专业的情绪分析助手。你的任务是根据用户输入的文本，分析其中蕴含的情绪。

请严格按照以下 JSON 格式返回结果，不要输出任何其他内容：

{{
  "emotion_label": "用2-4个字概括核心情绪，如'温暖愉悦'、'忧郁感伤'、'紧张不安'",
  "emotion_keywords": ["情绪关键词1", "情绪关键词2", "情绪关键词3"],
  "sentiment": "positive|negative|neutral",
  "intensity": 1-10,
  "explanation": "一句话解释为什么分析出这个情绪"
}}

用户输入：{user_text}"""


def analyze_with_ai(user_text: str) -> dict:
    """调用 ds-V4-Flash 模型进行情绪分析"""
    try:
        client = openai.OpenAI(
            api_key=AI_CONFIG["api_key"],
            base_url=AI_CONFIG["base_url"],
            timeout=AI_CONFIG["timeout"]
        )

        response = client.chat.completions.create(
            model=AI_CONFIG["model"],
            messages=[
                {"role": "system", "content": "你是一个专业的情绪分析助手，只返回 JSON 格式结果。"},
                {"role": "user", "content": EMOTION_ANALYSIS_PROMPT.format(
                    user_text=user_text
                )}
            ],
            temperature=AI_CONFIG["temperature"],
            max_tokens=AI_CONFIG["max_tokens"],
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content.strip()

        # 尝试解析 JSON
        # 有些 API 可能返回 markdown 代码块包裹的 JSON
        if result_text.startswith("```"):
            result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)

        result = json.loads(result_text)

        # 验证必要字段
        required_keys = ["emotion_label", "emotion_keywords", "sentiment", "explanation"]
        for key in required_keys:
            if key not in result:
                raise ValueError(f"AI 返回结果缺少字段: {key}")

        return {
            "label": result["emotion_label"],
            "keywords": result["emotion_keywords"],
            "sentiment": result["sentiment"],
            "intensity": result.get("intensity", 5),
            "explanation": result["explanation"]
        }

    except Exception as e:
        raise RuntimeError(f"AI 情绪分析失败: {str(e)}")


# ============================================================
# 2. 本地模式 - 基于关键词和规则的本地分析
# ============================================================

# 情绪关键词词库
EMOTION_KEYWORDS = {
    # 正面情绪
    "高兴": {
        "label": "开心愉悦",
        "keywords": ["快乐", "愉悦", "开心", "高兴", "嘻嘻", "哈哈", "笑", "欢乐", "兴高采烈"],
        "sentiment": "positive",
        "intensity": 7
    },
    "温暖": {
        "label": "温暖治愈",
        "keywords": ["温暖", "治愈", "暖心", "感动", "温馨", "幸福", "美好", "甜蜜", "亲情", "友情"],
        "sentiment": "positive",
        "intensity": 6
    },
    "放松": {
        "label": "平静放松",
        "keywords": ["放松", "舒服", "惬意", "悠闲", "自在", "平静", "安宁", "宁静", "慢", "休息", "假期"],
        "sentiment": "neutral",
        "intensity": 4
    },
    "激动": {
        "label": "激昂澎湃",
        "keywords": ["激动", "兴奋", "燃", "热血", "振奋", "充满力量", "斗志", "激情", "奋斗", "梦想"],
        "sentiment": "positive",
        "intensity": 8
    },
    "感恩": {
        "label": "感恩珍惜",
        "keywords": ["感恩", "感谢", "珍惜", "幸运", "福", "知足", "感谢"],
        "sentiment": "positive",
        "intensity": 6
    },
    # 负面情绪
    "悲伤": {
        "label": "忧郁悲伤",
        "keywords": ["悲伤", "难过", "伤心", "哭了", "流泪", "痛苦", "心碎", "绝望", "崩溃"],
        "sentiment": "negative",
        "intensity": 8
    },
    "孤独": {
        "label": "孤独感伤",
        "keywords": ["孤独", "寂寞", "孤单", "一个人", "没人", "独自", "寂寞", "空虚"],
        "sentiment": "negative",
        "intensity": 6
    },
    "怀念": {
        "label": "怀念感伤",
        "keywords": ["怀念", "回忆", "想念", "思念", "想起", "过去", "曾经", "以前", "旧", "时光"],
        "sentiment": "negative",
        "intensity": 5
    },
    "焦虑": {
        "label": "焦虑不安",
        "keywords": ["焦虑", "紧张", "压力", "担心", "害怕", "慌", "不安", "烦躁", "失眠"],
        "sentiment": "negative",
        "intensity": 7
    },
    "疲惫": {
        "label": "疲惫无力",
        "keywords": ["累", "疲惫", "疲劳", "无力", "困", "倦", "乏", "没精神"],
        "sentiment": "negative",
        "intensity": 5
    },
    # 复杂情绪
    "迷茫": {
        "label": "迷茫困惑",
        "keywords": ["迷茫", "困惑", "不知道", "不知所措", "方向", "迷路", "混沌"],
        "sentiment": "neutral",
        "intensity": 5
    },
    "期待": {
        "label": "期待憧憬",
        "keywords": ["期待", "希望", "向往", "憧憬", "盼望", "愿", "等待", "未来"],
        "sentiment": "positive",
        "intensity": 6
    },
    "失落": {
        "label": "失落沮丧",
        "keywords": ["失落", "沮丧", "失望", "灰心", "丧", "低落", "消极", "郁闷"],
        "sentiment": "negative",
        "intensity": 6
    },
    "愤怒": {
        "label": "愤怒不满",
        "keywords": ["生气", "愤怒", "恼火", "烦", "不爽", "忍不了", "暴躁", "怒火"],
        "sentiment": "negative",
        "intensity": 8
    }
}


def analyze_locally(user_text: str) -> dict:
    """基于关键词规则进行本地情绪分析"""
    text_lower = user_text.lower()

    scores = {}
    keyword_matches = {}

    for emotion_key, emotion_data in EMOTION_KEYWORDS.items():
        score = 0
        matched = []
        for kw in emotion_data["keywords"]:
            count = text_lower.count(kw.lower())
            if count > 0:
                score += count * 2
                matched.append(kw)
        # 长文本中关键词出现在靠前位置权重更高
        for kw in matched:
            pos = text_lower.find(kw.lower())
            if pos < len(text_lower) * 0.3:
                score += 1  # 位置加分
        if score > 0:
            scores[emotion_key] = score
            keyword_matches[emotion_key] = matched

    # 没有匹配到任何情绪
    if not scores:
        return {
            "label": "平和淡然",
            "keywords": ["平静", "淡然", "中性"],
            "sentiment": "neutral",
            "intensity": 3,
            "explanation": "从您的文字中没有检测到明显的情感倾向，或许您此刻的心情平静而淡然。"
        }

    # 获取得分最高的情绪类别
    top_emotion = max(scores, key=scores.get)

    # 如果第二个情绪得分也接近，合并标签
    sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    emotion_data = EMOTION_KEYWORDS[top_emotion]

    if len(sorted_emotions) > 1 and sorted_emotions[1][1] >= sorted_emotions[0][1] * 0.6:
        secondary = EMOTION_KEYWORDS[sorted_emotions[1][0]]
        merged_keywords = list(set(emotion_data['keywords'][:3] + secondary['keywords'][:2]))
        # 合并标签
        label = f"{emotion_data['label']}与{secondary['label']}"
    else:
        merged_keywords = emotion_data["keywords"][:4]
        label = emotion_data["label"]

    # 生成解释
    matched_list = keyword_matches.get(top_emotion, [])
    explanation_templates = {
        "positive": "您的文字中流露出积极的情感，",
        "negative": "您的文字中透露出一些负面的情绪，",
        "neutral": "您的文字传递出一种平静淡然的氛围，"
    }
    sentiment_base = emotion_data["sentiment"]
    explanation = explanation_templates.get(
        sentiment_base, "从您的文字中，我感受到："
    )
    if matched_list:
        explanation += f"特别是「{'、'.join(matched_list[:3])}」等词语，"
    suffix_map = {
        "positive": "让人感受到满满的温暖与力量。",
        "negative": "或许此刻的你需要一首歌来陪伴。",
        "neutral": "享受这份宁静的时光吧。"
    }
    explanation += suffix_map.get(sentiment_base, "希望音乐能与你共鸣。")

    return {
        "label": label,
        "keywords": merged_keywords[:5],
        "sentiment": emotion_data["sentiment"],
        "intensity": emotion_data["intensity"],
        "explanation": explanation
    }


# ============================================================
# 3. 统一入口
# ============================================================

def analyze_emotion(user_text: str) -> dict:
    """
    分析用户文本的情绪

    优先使用 AI 模式（需要配置 API Key）
    回退到本地关键词分析
    """
    if AI_ENABLED:
        try:
            return analyze_with_ai(user_text)
        except Exception as e:
            print(f"[WARN] AI 分析失败，回退到本地分析: {e}")
            return analyze_locally(user_text)
    else:
        return analyze_locally(user_text)
