"""
心随乐动 - Flask 主程序

API 接口：
  POST /api/recommend  - 情绪分析 + 歌曲推荐
  GET  /api/health     - 健康检查
"""

import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import SERVER_CONFIG, AI_ENABLED
from emotion_analyzer import analyze_emotion
from song_matcher import match_songs

app = Flask(__name__)
CORS(app)  # 允许跨域请求


# ============================================================
# API 路由
# ============================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "message": "心随乐动后端服务运行正常",
        "ai_enabled": AI_ENABLED
    })


@app.route("/api/recommend", methods=["POST"])
def recommend():
    """
    情绪分析 + 歌曲推荐

    请求体（JSON）：
      {"text": "用户描述的心情文字"}

    成功返回：
      {
        "code": 200,
        "data": {
          "emotion": { ... },
          "songs": [ ... ]
        }
      }

    错误返回：
      {"code": 400/500, "message": "错误描述"}
    """
    try:
        # 1. 解析请求
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400

        user_text = data.get("text", "").strip()
        if not user_text:
            return jsonify({"code": 400, "message": "输入文本不能为空"}), 400

        if len(user_text) < 2:
            return jsonify({"code": 400, "message": "输入文本太短，请多描述一些"}), 400

        if len(user_text) > 1000:
            return jsonify({"code": 400, "message": "输入文本太长了，请控制在1000字以内"}), 400

        # 2. 情绪分析
        emotion_result = analyze_emotion(user_text)

        # 3. 歌曲匹配
        songs = match_songs(emotion_result, top_n=10)

        # 4. 构建响应
        response_data = {
            "emotion": {
                "label": emotion_result["label"],
                "keywords": emotion_result["keywords"],
                "sentiment": emotion_result["sentiment"],
                "explanation": emotion_result["explanation"]
            },
            "songs": songs
        }

        return jsonify({"code": 200, "data": response_data})

    except Exception as e:
        print(f"[ERROR] 请求处理失败: {e}")
        return jsonify({
            "code": 500,
            "message": "服务器内部错误，请稍后重试"
        }), 500


# ============================================================
# 启动服务器
# ============================================================

if __name__ == "__main__":
    mode = "AI 模式" if AI_ENABLED else "本地关键词分析模式"
    print(f"""
{'=' * 50}
   心随乐动 - 后端服务
{'=' * 50}
   运行模式: {mode}
   监听地址: http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}
   API 文档:
     POST /api/recommend  - 情绪分析 + 歌曲推荐
     GET  /api/health     - 健康检查
{'=' * 50}
   启动中...
""")
    app.run(
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        debug=SERVER_CONFIG["debug"]
    )
