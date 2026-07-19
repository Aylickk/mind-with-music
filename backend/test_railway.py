"""测试 Railway 后端 API"""
import urllib.request, json, sys

URL = "https://web-production-e016.up.railway.app"
tests_passed = 0

def check(name, ok):
    global tests_passed
    if ok: tests_passed += 1
    print(f"  [{('PASS' if ok else 'FAIL')}] {name}")

# 1. 健康检查
print("=== 1. 健康检查 ===")
try:
    resp = urllib.request.urlopen(f"{URL}/api/health", timeout=15)
    j = json.loads(resp.read())
    check(f"status={j.get('status')}", j.get('status') == 'ok')
except Exception as e:
    check(f"健康检查失败: {e}", False)

# 2. 推荐接口
print("\n=== 2. 情绪分析 + 歌曲推荐 ===")
try:
    data = json.dumps({"text": "和朋友一起看了日落，很放松开心"}).encode("utf-8")
    req = urllib.request.Request(f"{URL}/api/recommend", data=data, headers={"Content-Type":"application/json"})
    resp = urllib.request.urlopen(req, timeout=20)
    j = json.loads(resp.read())
    check(f"code={j.get('code')}", j.get('code') == 200)
    emotion = j['data']['emotion']
    check(f"情绪标签: {emotion['label']}", True)
    check(f"关键词: {', '.join(emotion['keywords'])}", len(emotion.get('keywords', [])) > 0)
    songs = j['data']['songs']
    check(f"歌曲数: {len(songs)}", len(songs) >= 5)
    if songs:
        s = songs[0]
        fields = ['id','title','artist','reason','tags','tagType']
        check("字段完整", all(k in s for k in fields))
        check(f"第一首: {s['title']} - {s['artist']}", True)
        if s.get('url'):
            check(f"播放链接: {s['url'][:60]}...", True)
except Exception as e:
    check(f"推荐接口失败: {e}", False)

print(f"\n=== 结果: {tests_passed}/8 通过 ===")
if tests_passed == 8:
    print("Railway 后端运行正常！")
else:
    print("部分测试未通过，请检查部署状态。")
