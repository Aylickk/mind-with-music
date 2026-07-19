# 心随乐动 - 部署运维文档

> 本文记录项目的完整部署流程、配置文件说明、故障排查和日常维护要点。

---

## 一、项目概览

| 项目 | 心随乐动 - AI 情绪音乐推荐助手 |
|------|--------------------------------|
| 技术栈 | 前端：HTML/CSS/JS  ｜  后端：Python Flask |
| 部署平台 | 前端：GitHub Pages  ｜  后端：Railway |
| 仓库地址 | https://github.com/Aylickk/mind-with-music |
| 在线后端 | https://web-production-e016.up.railway.app |
| 在线前端 | https://aylickk.github.io/mind-with-music |

---

## 二、目录结构

```
mind-with-music/
├── index.html              # 前端主页面
├── css/style.css           # 样式表
├── js/app.js               # 前端交互逻辑
├── main.py                 # Railway 入口文件
├── requirements.txt        # 根目录依赖（Railway 必需）
├── Procfile                # Railway 启动配置（备选）
├── railway.json            # Railway 部署配置
├── .gitignore              # Git 忽略规则
└── backend/
    ├── app.py              # Flask 主程序
    ├── config.py           # 配置文件
    ├── emotion_analyzer.py # 情绪分析模块
    ├── song_matcher.py     # 多源歌曲匹配
    ├── requirements.txt    # 备用依赖
    ├── test_railway.py     # 部署后测试脚本
    ├── quick_test.py       # 单次快速测试
    ├── data/
    │   └── songs.json      # 本地回退曲库（55 首）
    └── cache/              # 缓存目录（自动生成）
```

---

## 三、关键配置文件说明

### 1. `main.py`（Railway 入口文件）

```python
# 核心逻辑：
# 1. 将 backend 目录加入 Python 路径
# 2. 切换工作目录到 backend
# 3. 导入 Flask 应用
# 4. 提供 application 变量供 Gunicorn 加载

application = app  # ⚠️ 必须有这行，否则 Gunicorn 报错
```

### 2. `Procfile`

```
web: gunicorn --bind 0.0.0.0:$PORT main:application --workers 1 --timeout 120
```

| 参数 | 含义 |
|------|------|
| `--bind 0.0.0.0:$PORT` | 监听 Railway 分配的环境变量 PORT |
| `main:application` | 入口模块:变量名 |
| `--workers 1` | 单 worker（Demo 项目够用） |
| `--timeout 120` | 120 秒超时（音乐 API 可能较慢） |

### 3. `railway.json`

```json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "gunicorn --bind 0.0.0.0:$PORT main:application --workers 1 --timeout 120",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 4. `requirements.txt`（根目录）

```
flask
flask-cors
requests
openai
gunicorn
```

> Railway NIXPACKS 在**根目录**寻找此文件，这是部署成功的关键之一。

### 5. `backend/config.py` - 环境变量驱动

所有配置都通过环境变量管理，便于部署切换：

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| `DS_API_KEY` | 空 | DeepSeek API Key，启用 AI 情绪分析 |
| `DS_BASE_URL` | `https://api.deepseek.com` | AI 模型 API 地址 |
| `DS_MODEL` | `deepseek-chat` | 模型名称 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口（Railway 自动设置） |
| `FLASK_DEBUG` | `false` | 是否开启调试 |
| `MUSIC_NETEASE_URL` | 网易云 API | 网易云搜索 API |
| `MUSIC_QQ_URL` | QQ 音乐 API | QQ 音乐搜索 API |
| `MUSIC_AGGREGATOR_URL` | 空 | 自部署聚合 API |

---

## 四、部署流程

### 4.1 前端部署（GitHub Pages）

1. 打开 GitHub 仓库 → **Settings** → **Pages**
2. **Source** 选择 `Deploy from a branch`
3. **Branch** 选择 `main`，目录选 `/ (root)`
4. 点击 **Save**
5. 等待 1-2 分钟，访问 `https://aylickk.github.io/mind-with-music/`

### 4.2 后端部署（Railway）

#### 首次部署

1. 打开 [Railway](https://railway.app) → 用 GitHub 登录
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择 `Aylickk/mind-with-music` 仓库
4. Railway 自动检测 `railway.json` 开始构建
5. 等待构建完成（约 3-5 分钟）
6. 点击 **Settings** → **Public Networking** → **Generate Domain**
7. 复制分配的域名（如 `web-production-e016.up.railway.app`）

#### 配置环境变量（可选）

在项目 Dashboard → **Variables** 中添加：

```
DS_API_KEY=sk-xxxxxxxxxxxxx
DS_BASE_URL=https://api.deepseek.com
```

#### 重新部署

推送代码到 GitHub 后，Railway 自动检测并重新部署：

```bash
git add .
git commit -m "更新说明"
git push
```

### 4.3 修改前端 API 地址

打开 [js/app.js](file:///d:/Program%20Files%20(x86)/Trae/参赛demo/mind-with-music/js/app.js) 第 30-37 行：

```javascript
const productionHosts = [
  'web-production-e016.up.railway.app',  // 你的 Railway 域名
  'aylickk.github.io'                    // 你的 GitHub 用户名
];
const isProduction = productionHosts.some(h => window.location.hostname.includes(h));

return isProduction
  ? 'https://web-production-e016.up.railway.app'  // 你的 Railway 域名
  : 'http://127.0.0.1:5000';
```

---

## 五、测试与验证

### 5.1 本地测试

```bash
# 启动后端
cd backend
python app.py

# 启动前端（另开终端）
cd mind-with-music
python -m http.server 8080
```

访问 `http://localhost:8080` 测试。

### 5.2 部署后测试

```bash
# 健康检查
curl https://web-production-e016.up.railway.app/api/health

# 推荐接口测试
python backend/quick_test.py

# 完整测试（8 项）
python backend/test_railway.py
```

### 5.3 预期输出

**健康检查：**
```json
{"ai_enabled": false, "message": "心随乐动后端服务运行正常", "status": "ok"}
```

**推荐接口：**
- 耗时：1-3 秒
- 情绪标签：2-4 字
- 关键词：3-5 个
- 歌曲数：5-10 首

---

## 六、常见故障排查

### 6.1 部署后访问 502 Bad Gateway

**症状**：访问域名返回 502。

**原因**：
- 应用还没启动完成
- 端口绑定错误
- 应用崩溃

**解决**：
1. 等待 1-2 分钟
2. 检查 Railway Dashboard → Deployments → 日志
3. 确认 `main.py` 中有 `application = app`
4. 确认 `Procfile` / `railway.json` 启动命令正确

### 6.2 Failed to find attribute 'application' in 'main'

**症状**：Gunicorn 启动失败，CRASHED 状态。

**原因**：`main.py` 缺少 `application` 变量。

**解决**：

```python
# main.py 必须包含这一行
from app import app
application = app  # ← 关键
```

### 6.3 ModuleNotFoundError: No module named 'flask'

**症状**：构建成功但启动失败，提示找不到模块。

**原因**：根目录缺少 `requirements.txt`，依赖没被安装。

**解决**：
- 在根目录创建 `requirements.txt`
- 包含：`flask`, `flask-cors`, `requests`, `openai`, `gunicorn`

### 6.4 推荐接口超时

**症状**：健康检查正常，但推荐请求超时。

**原因**：外部音乐 API（网易云/QQ/iTunes）响应慢或被墙。

**解决**：
1. 增加 Gunicorn `--timeout` 参数
2. 检查 Railway 服务器 IP 是否被网易云限制
3. 等待 30 秒后重试（多源故障转移会自动切换）

### 6.5 前端跨域问题

**症状**：浏览器控制台报 CORS 错误。

**原因**：Flask 跨域未开启。

**解决**：确认 `backend/app.py` 包含：

```python
from flask_cors import CORS
CORS(app)  # 允许所有跨域
```

---

## 七、监控与日志

### 7.1 Railway 日志查看

1. Railway Dashboard → 项目 → **Deployments**
2. 点击最新部署 → 查看 **Build Logs**（构建日志）和 **Deploy Logs**（运行日志）

### 7.2 关键日志标识

后端会输出以下关键日志（可在 Railway Deploy Logs 中看到）：

```
[SEARCH] 尝试源: 网易云音乐 (优先级 1)
[CACHE] 命中缓存: keywords=['开心', '快乐']
[FAIL] 网易云音乐「开心 快乐」所有重试失败: 超时
[SWITCH] 网易云音乐 结果不足，尝试下一源...
[SEARCH] 尝试源: QQ音乐 (优先级 2)
[INFO] API 搜索成功，共 10 首歌曲
```

### 7.3 性能基准

| 指标 | 参考值 |
|------|--------|
| 健康检查响应 | < 1 秒 |
| 推荐接口响应 | 2-4 秒（首次） / < 0.1 秒（缓存命中） |
| 内存占用 | ~80 MB |
| CPU 占用 | 极低（仅在请求时） |

---

## 八、扩展与定制

### 8.1 启用 AI 情绪分析

1. 获取 DeepSeek API Key：https://platform.deepseek.com/
2. 在 Railway 项目 → **Variables** 中添加：

   ```
   DS_API_KEY=sk-xxxxxxxxxxxxx
   ```

3. Railway 自动重新部署
4. 重启后 `/api/health` 中 `ai_enabled` 变为 `true`

### 8.2 添加新的音乐源

在 [backend/config.py](file:///d:/Program%20Files%20(x86)/Trae/参赛demo/mind-with-music/backend/config.py) 的 `MUSIC_SOURCES` 列表中添加：

```python
{
    "name": "new_source",
    "label": "新音乐源",
    "priority": 5,  # 数字越小优先级越高
    "search_url": "https://api.example.com/search",
    "method": "GET",
    "params": {"q": "{keyword}", "limit": 15},
    "headers": {"User-Agent": "..."},
    "retry_count": 2,
    "timeout": 10
}
```

然后在 [backend/song_matcher.py](file:///d:/Program%20Files%20(x86)/Trae/参赛demo/mind-with-music/backend/song_matcher.py) 的 `_PARSERS` 字典中添加对应解析器。

### 8.3 扩展本地曲库

编辑 [backend/data/songs.json](file:///d:/Program%20Files%20(x86)/Trae/参赛demo/mind-with-music/backend/data/songs.json) 添加歌曲：

```json
{
  "id": "s056",
  "title": "新歌曲名",
  "artist": "歌手名",
  "album": "专辑名",
  "cover_url": "",
  "emotion_tags": ["温暖", "治愈"],
  "sentiment_type": "positive",
  "mood_vector": {
    "valence": 0.8,
    "energy": 0.6,
    "calmness": 0.7
  }
}
```

---

## 九、安全注意事项

1. **API Key 保护**
   - 永远不要把 API Key 提交到 Git
   - 使用 Railway 环境变量管理敏感信息
   - 定期更换 API Key

2. **请求频率限制**
   - 避免高频调用外部音乐 API（可能触发 IP 封禁）
   - 缓存机制（5 分钟 TTL）已自动减少重复请求
   - 前端可加入按钮防抖（debounce）

3. **数据隐私**
   - 用户输入文本不会被存储
   - Railway 日志不包含用户输入内容
   - 可在 `backend/app.py` 中添加日志脱敏

---

## 十、备份与恢复

### 10.1 代码备份

代码已托管在 GitHub：https://github.com/Aylickk/mind-with-music

### 10.2 重要数据

- 曲库数据：`backend/data/songs.json`（在 Git 仓库中）
- 环境变量：手动记录到本地密码管理器
- Railway 配置：登录账号即可恢复

### 10.3 迁移到新平台

如果需要迁移到其他平台（如 Render、Fly.io）：

1. 复制所有源代码（已在 Git 仓库）
2. 在新平台导入仓库
3. 配置等效的启动命令：
   - Render：使用 `gunicorn main:application`
   - Fly.io：使用 `gunicorn --bind 0.0.0.0:8080 main:application`
4. 设置相同的 Python 版本（3.11+）

---

## 十一、联系与支持

- **GitHub Issues**：https://github.com/Aylickk/mind-with-music/issues
- **项目作者**：Aylickk

---

**最后更新**：2026-07-19
