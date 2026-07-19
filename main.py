"""
心随乐动 - Railway 入口文件
"""
import sys
import os

# 将 backend 目录加入 Python 路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

# 切到 backend 目录（确保 songs.json、cache 等相对路径正常工作）
os.chdir(backend_dir)

# 导入并启动 Flask 应用
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
