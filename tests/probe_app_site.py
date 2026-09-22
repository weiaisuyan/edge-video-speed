# -*- coding: utf-8 -*-
"""视频速度控制扩展 — 应用窗口（PWA/--app）与真实站点测试"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(OUT, "vsc_auto_edge")
BASE = "http://127.0.0.1:8782/"
results = []


def check(name, expected, actual, note=""):
    ok = (expected == actual)
    results.append({"case": name, "expected": expected, "actual": actual, "pass": ok, "note": note})
    print("%-4s %-50s expect=%s actual=%s %s" % ("PASS" if ok else "FAIL", name, expected, actual, note))
    return ok


JS_HOST = "document.querySelector('[data-vsc]') ? 1 : 0"
JS_VISIBLE = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.style.display !== 'none' : null})()"
JS_BTN = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelector('.btn').textContent.trim() : null})()"
JS_RATES = "Array.from(document.querySelectorAll('video')).map(v=>v.playbackRate)"
JS_PANEL = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelector('.panel').classList.contains('open') : null})()"


def wait_for(sid, expr, timeout=25, want=None, interval=0.5):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = cdp.ev(sid, expr)
        except Exception as e:
            last = "err:%s" % e
        if want is None:
            if last:
                return last
        elif last == want:
            return last
        time.sleep(interval)
    return last


def rect_of(sid, sel):
    return cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const e=h.shadowRoot.querySelector(%r);"
                       "if(!e) return null;const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()" % sel)


def rect_of_text(sid, sel, text):
    return cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const all=h.shadowRoot.querySelectorAll(%r);"
                       "for(const e of all){if(e.textContent.trim()===%r){const r=e.getBoundingClientRect();"
                       "return {x:r.left+r.width/2,y:r.top+r.height/2}}}})()" % (sel, text))


def store_get(sid):
    return cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings||{})))")


print("=== 应用窗口 + 真实站点测试 ===")
cdp = CDP(9222)

# storage 控制台（读设置用）：扩展 ID 用加载路径算出，并校验 manifest 名称
from cdp import ext_id_for  # noqa: E402
ext_id = ext_id_for(r"E:\程序\edge-video-speed")
print("profile 里的扩展 target：")
for t in cdp.targets():
    if (t.get("url") or "").startswith("chrome-extension://"):
        print("   ", t.get("type"), t.get("url"))
tid_con, sid_con = cdp.open("chrome-extension://%s/options.html" % ext_id, wait=1.8)
name = cdp.ev(sid_con, "chrome.runtime.getManifest().name")
print("ext_id =", ext_id, "| name =", name)
if not name or "视频速度" not in name:
    raise SystemExit("扩展页校验失败（name=%s），请确认扩展已加载" % name)

# ================= A. 应用窗口（等价于「安装为应用」的窗口：无工具栏无地址栏） =================
print("\n--- A. 应用窗口（--app，等价 PWA 窗口）---")
# 清掉上一轮残留的测试标签页/窗口（Edge 会话恢复会带回旧窗口，否则会抓错目标）
for t in cdp.targets():
    u = t.get("url") or ""
    if t.get("type") == "page" and ("127.0.0.1:8782" in u or u.startswith("chrome-extension://")):
        try:
            cdp.send("Target.closeTarget", {"targetId": t["targetId"]})
        except Exception:
            pass
time.sleep(1.5)
tid_con, sid_con = cdp.open("chrome-extension://%s/options.html" % ext_id, wait=1.5)

APP_URL = BASE + "vsc_test_app.html"
subprocess.Popen([EDGE, "--app=" + APP_URL,
                  "--user-data-dir=" + PROFILE, "--no-first-run",
                  "--disable-features=CalculateNativeWinOcclusion"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
app_t = None
for t in cdp.targets():
    if t.get("type") == "page" and "vsc_test_app.html" in (t.get("url") or ""):
        app_t = t
if not app_t:
    check("A0 找到应用窗口目标", True, False, "未找到 app 窗口 target")
else:
    sid_app = cdp.attach(app_t["targetId"])
    cdp.send("Runtime.enable", session=sid_app)
    cdp.send("Page.enable", session=sid_app)
    cdp.activate(app_t["targetId"])
    time.sleep(1.2)
    chrome_h = cdp.ev(sid_app, "window.outerHeight - window.innerHeight")
    check("A1 应用窗口（无浏览器工具栏，高度差很小）", True, chrome_h is not None and chrome_h <= 90, "外高-内高=%s px" % chrome_h)
    check("A2 应用窗口里扩展按钮存在", 1, cdp.ev(sid_app, JS_HOST))
    check("A3 应用窗口里按钮可见", True, cdp.ev(sid_app, JS_VISIBLE))
    nv = cdp.ev(sid_app, "document.querySelectorAll('video').length")
    check("A4 应用窗口里检测到视频", True, nv >= 1, "video 数=%s" % nv)
    # 在应用窗口里直接调速（这正是用户要的：不用切回浏览器）
    r = rect_of(sid_app, ".btn")
    cdp.click(sid_app, r["x"], r["y"])
    check("A5 应用窗口里点按钮 → 菜单打开", True, cdp.ev(sid_app, JS_PANEL))
    chip = rect_of_text(sid_app, ".chip", "2×")
    cdp.click(sid_app, chip["x"], chip["y"])
    time.sleep(0.4)
    rr = cdp.ev(sid_app, JS_RATES) or []
    check("A6 应用窗口里选 2× → 视频 playbackRate", True, rr and all(abs(x - 2) < 0.001 for x in rr), rr)
    check("A7 应用窗口里按钮文字同步", "2×", cdp.ev(sid_app, JS_BTN))
    cdp.shot(sid_app, os.path.join(OUT, "shot_app_window.png"))
    # 位置拖动
    before = cdp.ev(sid_app, "parseFloat(document.querySelector('[data-vsc]').style.left)")
    r = rect_of(sid_app, ".btn")
    cdp.drag(sid_app, r["x"], r["y"], r["x"] - 260, r["y"] + 180, modifiers=2)
    time.sleep(0.5)
    after = cdp.ev(sid_app, "parseFloat(document.querySelector('[data-vsc]').style.left)")
    posx = (store_get(sid_con) or {}).get("posX")
    check("A8 应用窗口里 Ctrl+拖动可移动按钮（并写入位置记忆）", True,
          after < before - 50 and posx is not None, "before=%s after=%s storage.posX=%s" % (before, after, posx))
    # 恢复默认设置，避免影响后面真实站点测试
    cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.clear(()=>r(1)))")
    time.sleep(0.6)
    cdp.send("Target.closeTarget", {"targetId": app_t["targetId"]})

# ================= B. 真实站点 =================
def site_case(label, url, has_video_expected=True, extra=None):
    print("\n--- %s ---" % label)
    tid, sid = cdp.open(url, wait=6)
    cdp.activate(tid)
    vids = wait_for(sid, "document.querySelectorAll('video').length", timeout=25, want=None)
    time.sleep(1.5)
    check("%s 页面有 video 元素" % label, has_video_expected, bool(vids), "video 数=%s" % vids)
    check("%s 扩展按钮存在" % label, 1, cdp.ev(sid, JS_HOST))
    if has_video_expected and vids:
        check("%s 按钮可见" % label, True, cdp.ev(sid, JS_VISIBLE))
        r = rect_of(sid, ".btn")
        cdp.click(sid, r["x"], r["y"])
        time.sleep(0.3)
        check("%s 点按钮 → 菜单打开" % label, True, cdp.ev(sid, JS_PANEL))
        chip = rect_of_text(sid, ".chip", "1.5×")
        cdp.click(sid, chip["x"], chip["y"])
        time.sleep(0.5)
        check("%s 选 1.5× → 视频 playbackRate" % label, True,
              all(abs(x - 1.5) < 0.001 for x in (cdp.ev(sid, JS_RATES) or [])), cdp.ev(sid, JS_RATES))
        # 关键：模拟「你在网站自带播放器上手动调速」= 真实点击 + 播放器随后改速
        cdp.click(sid, 420, 700)
        cdp.ev(sid, "(()=>{const v=document.querySelector('video'); v.playbackRate = 1.25; return v.playbackRate;})()",
               await_promise=False)
        time.sleep(1.0)
        check("%s 播放器手动改 1.25×（带点击）→ 不被抢回（跟随）" % label, [1.25], cdp.ev(sid, JS_RATES))
        check("%s 跟随并同步按钮文字" % label, "1.25×", cdp.ev(sid, JS_BTN))
        time.sleep(3.0)
        check("%s 3 秒后仍保持 1.25×（持续不打架）" % label, [1.25], cdp.ev(sid, JS_RATES))
        s = store_get(sid_con) or {}
        host = cdp.ev(sid, "location.hostname")
        key = host[4:] if host.startswith("www.") else host
        check("%s 跟随的速度已按网站记住" % label, 1.25,
              (s.get("siteSpeeds") or {}).get(key), "host=%s key=%s" % (host, key))
        cdp.shot(sid, os.path.join(OUT, "shot_site_%s.png" % label))
    else:
        print("      （该页面没有 video → 按钮按设计隐藏，属于正确行为）")
        print("      按钮可见性:", cdp.ev(sid, JS_VISIBLE))
    if extra:
        extra(sid)
    cdp.send("Target.closeTarget", {"targetId": tid})


try:
    site_case("YouTube", "https://www.youtube.com/watch?v=aqz-KE-bpKQ")
except Exception as e:
    check("YouTube 测试未抛异常", "无异常", "异常: %s" % e)

try:
    site_case("B站", "https://www.bilibili.com/video/BV1GJ411x7h7")
except Exception as e:
    check("B站 测试未抛异常", "无异常", "异常: %s" % e)

try:
    site_case("微博", "https://weibo.com/tv", has_video_expected=False)
except Exception as e:
    check("微博 测试未抛异常", "无异常", "异常: %s" % e)

try:
    site_case("小红书", "https://www.xiaohongshu.com/explore", has_video_expected=False)
except Exception as e:
    check("小红书 测试未抛异常", "无异常", "异常: %s" % e)

fails = [r for r in results if not r["pass"]]
print("\n=== 汇总：%d 项，通过 %d，失败 %d ===" % (len(results), len(results) - len(fails), len(fails)))
for r in fails:
    print("  FAIL %s expect=%s actual=%s %s" % (r["case"], r["expected"], r["actual"], r["note"]))
with open(os.path.join(OUT, "vsc_appsite_results.json"), "w", encoding="utf-8") as f:
    json.dump({"total": len(results), "fail": len(fails), "results": results}, f, ensure_ascii=False, indent=2)
print("结果已写入 vsc_appsite_results.json")
