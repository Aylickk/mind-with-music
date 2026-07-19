# Railway 部署启动配置
# 使用 Gunicorn 生产服务器启动 Flask 应用
web: gunicorn main:application --worker-class sync --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level debug
