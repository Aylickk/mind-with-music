/**
 * 心随乐动 - 前端交互逻辑
 *
 * 连接后端 API 进行情绪分析与歌曲推荐
 * API_BASE: 自动根据环境切换（开发=localhost / 生产=Koyeb域名）
 */

// Mock 数据已移除，改用真实后端 API 调用
// ============================================================

// -------------------------------------------------------
// API 地址配置（自动检测开发/生产环境）
// -------------------------------------------------------
// 本地开发 → http://127.0.0.1:5000
// 生产部署 → https://your-app.koyeb.app
//
// 方式 1: 通过 meta 标签手动指定（优先）
//   在 index.html 的 <head> 中添加:
//   <meta name="api-base" content="https://your-app.koyeb.app">
//
// 方式 2: 自动检测
const API_BASE = (() => {
  // 检查 meta 标签
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta) return meta.getAttribute('content');

  // 生产环境域名列表（按需添加你的 Railway 域名）
  const productionHosts = [
    'mind-with-music.up.railway.app',  // Railway 自动分配的域名
    'your-username.github.io'
  ];
  const isProduction = productionHosts.some(h => window.location.hostname.includes(h));

  return isProduction
    ? 'https://mind-with-music.up.railway.app'   // ← 部署后替换为你的 Railway 域名
    : 'http://127.0.0.1:5000';
})();

// -------------------------------------------------------
// DOM 元素引用
// -------------------------------------------------------

const dom = {
  input: document.getElementById('user-input'),
  charCount: document.getElementById('char-count'),
  submitBtn: document.getElementById('submit-btn'),
  loading: document.getElementById('loading'),
  resultSection: document.getElementById('result-section'),
  emotionTags: document.getElementById('emotion-tags'),
  emotionExplain: document.getElementById('emotion-explain'),
  songsGrid: document.getElementById('songs-grid'),
  songsCount: document.getElementById('songs-count'),
  errorSection: document.getElementById('error-section'),
  errorCard: document.querySelector('.error-card'),
  errorIcon: document.getElementById('error-icon'),
  errorBadge: document.getElementById('error-badge'),
  errorTitle: document.getElementById('error-title'),
  errorSuggestion: document.getElementById('error-suggestion'),
  retryBtn: document.getElementById('retry-btn'),
  emptyState: document.getElementById('empty-state')
};

// ============================================================
// 3. 核心功能函数
// ============================================================

/**
 * 显示加载状态
 */
function showLoading() {
  dom.loading.classList.remove('hidden');
  dom.resultSection.classList.add('hidden');
  dom.errorSection.classList.add('hidden');
  dom.emptyState.classList.add('hidden');
  dom.submitBtn.disabled = true;
}

/**
 * 隐藏加载状态
 */
function hideLoading() {
  dom.loading.classList.add('hidden');
  dom.submitBtn.disabled = false;
}

/**
 * 错误类型配置
 */
const ERROR_TYPES = {
  network: {
    icon: '\u26A0\uFE0F',     // ⚠️
    badge: '网络错误',
    title: '无法连接到服务器',
    suggestion: `确认后端已启动：在 backend 目录执行 python app.py（API: ${API_BASE}）`
  },
  server: {
    icon: '\u274C',            // ❌
    badge: '服务异常',
    title: '服务器暂时出了点问题',
    suggestion: '请稍后重试，或换一种描述方式。如果问题持续，请检查后端运行状态'
  },
  empty: {
    icon: '\uD83D\uDD0C',      // 🔌
    badge: '服务暂不可用',
    title: '暂时无法获取推荐歌曲',
    suggestion: '当前所有音乐源暂时不可用，请稍后再试。你也可以尝试换个情绪描述'
  },
  input: {
    icon: '\uD83D\uDCEB',      // 📫
    badge: '输入提示',
    title: '请描述你的心情',
    suggestion: '输入更多细节（场景、感受、事件），让 AI 更好地理解你的心情'
  }
};

/**
 * 显示错误信息
 * @param {string} type  - 错误类型: 'network' | 'server' | 'empty' | 'input'
 * @param {string} customTitle - 自定义标题（可选，覆盖默认）
 */
function showError(type, customTitle) {
  hideLoading();

  const config = ERROR_TYPES[type] || ERROR_TYPES.input;

  // 设置内容
  dom.errorIcon.textContent = config.icon;
  dom.errorBadge.textContent = config.badge;

  if (customTitle) {
    dom.errorTitle.textContent = customTitle;
    dom.errorSuggestion.textContent = config.suggestion;
  } else {
    dom.errorTitle.textContent = config.title;
    dom.errorSuggestion.textContent = config.suggestion;
  }

  // 移除旧的分类 class，添加新的
  dom.errorCard.classList.remove(
    'is-network', 'is-server', 'is-empty', 'is-input'
  );
  dom.errorCard.classList.add('is-' + type);

  // 显示错误区
  dom.errorSection.classList.remove('hidden');
  dom.resultSection.classList.add('hidden');
  dom.emptyState.classList.add('hidden');
}

/**
 * 检测后端返回的歌曲是否为 fallback 兜底数据
 */
function isFallbackResult(data) {
  if (!data || !data.songs || data.songs.length === 0) return false;
  // 如果所有歌曲的 id 都以 "fallback_" 开头，说明所有 API 源都失败了
  return data.songs.every(s => s.id && s.id.startsWith('fallback_'));
}

/**
 * 调用后端 API 进行情绪分析与歌曲推荐
 */
async function fetchRecommendation(text) {
  const response = await fetch(`${API_BASE}/api/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });

  // 处理 HTTP 状态码错误（如 500）
  if (!response.ok) {
    const errorText = await response.text().catch(() => '服务器内部错误');
    throw new Error(`服务器错误 (${response.status}): ${errorText}`);
  }

  return await response.json();
}

/**
 * 渲染情绪分析结果
 */
function renderEmotion(emotion) {
  // 渲染情绪标签
  dom.emotionTags.innerHTML = emotion.keywords
    .map((kw) => `<span class="emotion-tag">${kw}</span>`)
    .join('');

  // 渲染情绪解释
  dom.emotionExplain.textContent = emotion.explanation;
}

/**
 * 获取封面样式类名和图标
 */
function getCoverStyle(index) {
  const coverClasses = [
    'song-cover-0', 'song-cover-1', 'song-cover-2', 'song-cover-3',
    'song-cover-4', 'song-cover-5', 'song-cover-6', 'song-cover-7'
  ];
  const icons = ['♫', '♪', '♩', '♬'];
  return {
    coverClass: coverClasses[index % coverClasses.length],
    icon: icons[index % icons.length]
  };
}

/**
 * 渲染歌曲列表
 */
function renderSongs(songs) {
  dom.songsCount.textContent = `共 ${songs.length} 首`;

  dom.songsGrid.innerHTML = songs
    .map((song, index) => {
      const { coverClass, icon } = getCoverStyle(index);
      return `
        <div class="song-card">
          <div class="song-cover ${coverClass}">
            <span class="song-cover-icon">${icon}</span>
          </div>
          <div class="song-info">
            <div class="song-title">${song.title}</div>
            <div class="song-artist">${song.artist}</div>
            <div class="song-reason">${song.reason}</div>
            <div class="song-tags">
              ${song.tags.map((tag) => `<span class="song-tag ${song.tagType}">${tag}</span>`).join('')}
            </div>
          </div>
        </div>
      `;
    })
    .join('');
}

/**
 * 渲染完整的推荐结果
 */
function renderResult(data) {
  const { emotion, songs } = data;

  renderEmotion(emotion);
  renderSongs(songs);

  hideLoading();
  dom.resultSection.classList.remove('hidden');
  dom.emptyState.classList.add('hidden');
  dom.errorSection.classList.add('hidden');

  // 滚动到结果区
  dom.resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * 处理用户提交
 */
async function handleSubmit() {
  const text = dom.input.value.trim();

  // 验证输入
  if (!text) {
    showError('input', '请先描述你的心情或经历');
    dom.input.focus();
    return;
  }

  if (text.length < 4) {
    showError('input', '描述太短了，再多写一点细节吧');
    dom.input.focus();
    return;
  }

  // 显示加载状态
  showLoading();

  try {
    // 调用后端 API
    const response = await fetchRecommendation(text);

    if (response.code === 200 && response.data) {
      // 检测是否所有 API 源都失败（返回了 fallback 兜底数据）
      if (isFallbackResult(response.data)) {
        showError('empty');
        return;
      }
      renderResult(response.data);
    } else {
      showError('server');
    }
  } catch (err) {
    console.error('请求失败:', err);
    // 区分网络错误和服务器错误
    if (err instanceof TypeError && err.message === 'Failed to fetch') {
      showError('network');
    } else if (err.message && err.message.includes('服务器错误')) {
      showError('server');
    } else {
      showError('network');
    }
  }
}

// ============================================================
// 4. 事件绑定
// ============================================================

// 提交按钮点击
dom.submitBtn.addEventListener('click', handleSubmit);

// 回车键提交（Shift+Enter 换行）
dom.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
});

// 字数统计
dom.input.addEventListener('input', () => {
  const len = dom.input.value.length;
  dom.charCount.textContent = len;

  // 超过 500 字截断
  if (len > 500) {
    dom.input.value = dom.input.value.substring(0, 500);
    dom.charCount.textContent = 500;
  }
});

// 重试按钮
dom.retryBtn.addEventListener('click', () => {
  dom.errorSection.classList.add('hidden');
  handleSubmit();
});

// ============================================================
// 5. 页面加载完成后自动聚焦输入框
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  dom.input.focus();
});

// ============================================================
// 6. 导出以供调试
// ============================================================

console.log('心随乐动 v1.0 已加载 (联调模式)');
console.log('API: http://127.0.0.1:5000/api/recommend');
console.log('输入文字后点击"获取音乐推荐"即可体验');
