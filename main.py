"""
心随乐动 - Railway 入口文件
此文件在项目根目录，确保 Railway 能正确找到并启动 Flask 应用
"""
import sys
import os

# 将 backend 目录加入 Python 路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

# 切到 backend 目录（确保 songs.json、cache 等相对路径正常工作）
os.chdir(backend_dir)

# 导入 Flask 应用实例
from app import app

# Gunicorn 会寻找此模块的 application 变量
application = app
