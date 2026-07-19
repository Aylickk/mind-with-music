# Railway 部署启动配置
# 绑定 $PORT 变量（Railway 自动设置），监听 0.0.0.0
web: gunicorn --bind 0.0.0.0:$PORT --worker-class sync --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level debug main:application
