# -*- coding: utf-8 -*-
"""视频速度控制 — 全屏场景专项探针（v2）

验证「全屏时隐藏按钮」在各类全屏下的真实表现。判据不只读 style.display，
还要**像素级验证按钮到底有没有被画出来**（裁剪按钮区域，统计接近按钮底色的像素数）。

全屏形态：
  A  普通页面（基线）
  B  原生全屏（Fullscreen API，元素=容器 div，视频在容器外）
  C  原生全屏（Fullscreen API，元素=video 本身）
  C2 原生全屏（Fullscreen API，元素=整个 html——这种全屏下 body 里的按钮会被画出来）
  D  网页伪全屏（网站自己的 CSS 全屏：播放器铺满视口，不触发 Fullscreen API）
  D2 伪全屏「不够大」对照（只有 80%×80%，不该被当全屏）
  E  浏览器窗口全屏（F11/Edge 全屏，真实 windowState=fullscreen）
"""
import base64
import io
import json
import os
import sys
import time

import faulthandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

faulthandler.dump_traceback_later(300, exit=True)

BASE = "http://127.0.0.1:8782/"
LOAD_PATH = "E:\\程序\\edge-video-speed"
PORT = 9223
OUT = os.path.dirname(os.path.abspath(__file__))
BTN_BG = (95, 114, 133)      # mist 纯色款底色 #5f7285

try:
    from PIL import Image
except Exception:
    Image = None

results = []


def check(name, expected, actual, note=""):
    ok = (expected == actual)
    results.append({"case": name, "expected": expected, "actual": actual, "pass": ok, "note": note})
    print("%-4s %-54s expect=%s actual=%s %s" % ("PASS" if ok else "FAIL", name, expected, actual, note))
    return ok


def info(name, value):
    print("     %-54s %s" % (name, value))


cdp = CDP(PORT)
print("Edge:", cdp.send("Browser.getVersion")["product"])
ext_id = ext_id_for(LOAD_PATH)

tid_con, sid_con = cdp.open("chrome-extension://%s/popup.html" % ext_id, wait=1.2)
cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.clear(()=>r(1)))")

tid_v, sid_v = cdp.open(BASE + "vsc_test_fullscreen.html", wait=2.6)
cdp.activate(tid_v)
time.sleep(0.4)

win_id = cdp.send("Browser.getWindowForTarget", {"targetId": tid_v})["windowId"]
win_bounds0 = cdp.send("Browser.getWindowBounds", {"windowId": win_id})["bounds"]

# 测试环境：关掉闲置淡化（否则按钮半透明，像素判据失真）
cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};"
                "s.showInFullscreen=false;s.idleFade=false;s.hoverOpacity=100;s.excludedSites=[];"
                "s.visible=true;s.displayMode='videoOnly';s.styleId='mist';s.showNumber=true;"
                "s.posX=92;s.posY=10;"
                "chrome.storage.local.set({settings:s},()=>r(s))}))")
time.sleep(1.2)
cdp.activate(tid_v)
time.sleep(0.3)
cdp.ev(sid_v, "window.playVideo()", user_gesture=True)
time.sleep(0.6)

JS_OBS = """(()=>{
  const h=document.querySelector('[data-vsc]');
  const out={hasHost:!!h};
  if(h){
    out.display=h.style.display||'(inline)';
    out.parent=h.parentNode?(h.parentNode.id||h.parentNode.tagName):null;
    const b=h.shadowRoot.querySelector('.btn');
    const r=b.getBoundingClientRect();
    out.rect={x:r.left,y:r.top,w:r.width,h:r.height};
  }
  const v=document.querySelector('video');
  const vr=v?v.getBoundingClientRect():null;
  out.video=vr?{w:Math.round(vr.width),h:Math.round(vr.height)}:null;
  out.vw=window.innerWidth; out.vh=window.innerHeight;
  out.screen={w:window.screen.width,h:window.screen.height};
  const fe=document.fullscreenElement;
  out.fsEl=fe?(fe.id||fe.tagName):null;
  out.fake=document.body.className||'';
  return out;
})()"""


def obs():
    return cdp.ev(sid_v, JS_OBS)


def painted_px(rect, tag):
    """截屏后裁剪按钮区域，统计与按钮底色接近的像素数（按钮真的被画出来了吗）"""
    if not Image or not rect:
        return None
    dpr = cdp.ev(sid_v, "window.devicePixelRatio") or 1
    r = cdp.send("Page.captureScreenshot", {"format": "png"}, session=sid_v, timeout=30)
    img = Image.open(io.BytesIO(base64.b64decode(r["data"]))).convert("RGB")
    pad = 4
    x0 = int(max(0, (rect["x"] - pad) * dpr)); y0 = int(max(0, (rect["y"] - pad) * dpr))
    x1 = int(min(img.width, (rect["x"] + rect["w"] + pad) * dpr))
    y1 = int(min(img.height, (rect["y"] + rect["h"] + pad) * dpr))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = img.crop((x0, y0, x1, y1))
    crop.save(os.path.join(OUT, "fs_%s.png" % tag))
    hit = 0
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for px in crop.getdata():
            if sum(abs(px[i] - BTN_BG[i]) for i in range(3)) < 90:
                hit += 1
    return hit


def reset_scene():
    cdp.ev(sid_v, "document.fullscreenElement?document.exitFullscreen():1", user_gesture=True)
    time.sleep(0.7)
    cdp.ev(sid_v, "window.exitFake();window.resetVideoSize?window.resetVideoSize():1")
    time.sleep(0.5)
    cdp.activate(tid_v)
    time.sleep(0.3)


def set_hide(flag):
    cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};"
                    "s.showInFullscreen=%s;chrome.storage.local.set({settings:s},()=>r(s))}))" % ("true" if flag else "false"))
    time.sleep(1.0)


def scene(tag):
    o = obs()
    n = painted_px(o.get("rect"), tag)
    info(tag, "fsEl=%s fake=%r display=%s parent=%s video=%s 按钮像素=%s"
         % (o["fsEl"], o["fake"], o["display"], o["parent"], o["video"], n))
    return o, n


print("\n### 设置：全屏时隐藏按钮 = 关（showInFullscreen=false）—— 用户报障的配置 ###")
set_hide(False)
reset_scene()
o, n = scene("A 基线")
check("A 普通页面：按钮可见（基线）", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

# ---- B 原生全屏（容器） ----
cdp.ev(sid_v, "window.enterNativeBox()", user_gesture=True)
time.sleep(1.2)
o, n = scene("B 原生全屏(容器)")
check("B 原生全屏(容器)：进入全屏", "fsbox", o["fsEl"])
check("B 原生全屏(容器)：按钮必须隐藏", "none", o["display"], "painted=%s" % n)
check("B 原生全屏(容器)：画面上无按钮像素", True, (n or 0) < 60, "painted=%s" % n)
reset_scene()
o, n = scene("B 退出后")
check("B 退出全屏：按钮恢复", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

# ---- C 原生全屏（video 元素） ----
cdp.ev(sid_v, "window.enterNativeVideo()", user_gesture=True)
time.sleep(1.2)
o, n = scene("C 原生全屏(video)")
check("C 原生全屏(video 元素)：进入全屏", "v1", o["fsEl"])
check("C 原生全屏(video 元素)：按钮必须隐藏", "none", o["display"], "painted=%s" % n)
reset_scene()

# ---- C2 原生全屏（整个 html）—— 这种全屏下 body 里的按钮本来会被画出来 ----
cdp.ev(sid_v, "window.enterNativeDoc()", user_gesture=True)
time.sleep(1.2)
o, n = scene("C2 原生全屏(整个html)")
check("C2 原生全屏(整个 html)：进入全屏", "HTML", o["fsEl"])
check("C2 原生全屏(整个 html)：按钮必须隐藏（否则看得见）", "none", o["display"], "painted=%s" % n)
check("C2 原生全屏(整个 html)：画面上无按钮像素", True, (n or 0) < 60, "painted=%s" % n)
reset_scene()

# ---- D 网页伪全屏（无 Fullscreen API，播放器铺满视口） ----
cdp.ev(sid_v, "window.enterFake()", user_gesture=True)
time.sleep(1.0)
o, n = scene("D 网页伪全屏100%")
check("D 伪全屏：确实无 fullscreenElement", None, o["fsEl"])
check("D 伪全屏：视频铺满视口（判据前提）", True,
      bool(o["video"] and o["video"]["w"] >= o["vw"] * 0.94 and o["video"]["h"] >= o["vh"] * 0.94), o["video"])
check("D 伪全屏：按钮必须隐藏（用户报障点）", "none", o["display"], "painted=%s" % n)
check("D 伪全屏：画面上无按钮像素", True, (n or 0) < 60, "painted=%s" % n)
reset_scene()
o, n = scene("D 退出伪全屏")
check("D 退出伪全屏：按钮恢复", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

# ---- D2 伪全屏「不够大」对照：80%×80%，绝不能隐藏 ----
cdp.ev(sid_v, "window.enterFake80()", user_gesture=True)
time.sleep(1.0)
o, n = scene("D2 伪全屏80%")
check("D2 伪全屏只有 80%：按钮必须照常显示（不能误判成全屏）", True,
      o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)
reset_scene()

# ---- D3 伪全屏的「信箱化」形态：fixed 容器铺满视口，视频只占 100%×70%（B站网页全屏在窗口比例≠视频比例时） ----
cdp.ev(sid_v, "window.enterFakeLetterbox()", user_gesture=True)
time.sleep(1.0)
o, n = scene("D3 伪全屏(信箱化)")
check("D3 信箱化伪全屏：视频本身不铺满视口（判据前提）", True,
      bool(o["video"] and o["video"]["h"] < o["vh"] * 0.94), o["video"])
check("D3 信箱化伪全屏：按钮也必须隐藏（靠定位容器识别）", "none", o["display"], "painted=%s" % n)
check("D3 信箱化伪全屏：画面上无按钮像素", True, (n or 0) < 60, "painted=%s" % n)
reset_scene()
o, n = scene("D3 退出后")
check("D3 退出信箱化伪全屏：按钮恢复", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

# ---- E 浏览器窗口全屏（F11/Edge 全屏，真实 windowState=fullscreen） ----
try:
    cdp.ev(sid_v, "window.setVideoPercent(90,70);1")
    time.sleep(0.6)
    cdp.send("Browser.setWindowBounds", {"windowId": win_id, "bounds": {"windowState": "fullscreen"}})
    time.sleep(1.5)
    o, n = scene("E 窗口全屏+视频占63%面积")
    info("E 视口/屏幕", "inner=%sx%s screen=%sx%s ratio_h=%.3f"
         % (o["vw"], o["vh"], o["screen"]["w"], o["screen"]["h"], o["vh"] / max(1, o["screen"]["h"])))
    check("E 窗口全屏：按钮隐藏（视频占大半个视口）", True,
          o["display"] == "none" and (n or 0) < 60, "display=%s painted=%s" % (o["display"], n))
    cdp.send("Browser.setWindowBounds", {"windowId": win_id, "bounds": win_bounds0})
    time.sleep(1.2)
    o, n = scene("E 退出窗口全屏")
    check("E 退出窗口全屏：按钮恢复", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)
    # E2 窗口全屏 + 视频很小（面积 < 60%）→ 不该隐藏
    cdp.ev(sid_v, "window.setVideoPercent(30,20);1")
    time.sleep(0.5)
    cdp.send("Browser.setWindowBounds", {"windowId": win_id, "bounds": {"windowState": "fullscreen"}})
    time.sleep(1.5)
    o, n = scene("E2 窗口全屏+小视频")
    check("E2 窗口全屏但视频很小：按钮照常显示（防误判）", True,
          o["display"] != "none" and (n or 0) > 150, "display=%s painted=%s" % (o["display"], n))
    cdp.send("Browser.setWindowBounds", {"windowId": win_id, "bounds": win_bounds0})
    time.sleep(1.2)
except Exception as e:
    check("E 窗口全屏", "无异常", "异常: %s" % e)
    try:
        cdp.send("Browser.setWindowBounds", {"windowId": win_id, "bounds": win_bounds0})
    except Exception:
        pass
time.sleep(0.6)
reset_scene()
o, n = scene("E 收尾")
check("E 收尾：按钮恢复", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

# ---- F 全屏状态下改设置（免刷新即时生效） ----
set_hide(True)
cdp.ev(sid_v, "window.enterNativeBox()", user_gesture=True)
time.sleep(1.2)
o, n = scene("F 全屏(hide=on)")
check("F 全屏中「全屏显示」=开：按钮搬进全屏容器且画出来", True,
      o["parent"] == "fsbox" and (n or 0) > 150, "parent=%s painted=%s" % (o["parent"], n))
set_hide(False)
time.sleep(0.3)
o, n = scene("F 全屏中改关")
check("F 全屏中把「全屏显示」改关：按钮立即隐藏（免刷新）", "none", o["display"], "painted=%s" % n)
set_hide(True)
time.sleep(0.3)
o, n = scene("F 全屏中改回开")
check("F 全屏中再改回开：按钮立即回来", True,
      o["display"] != "none" and (n or 0) > 150, "display=%s parent=%s painted=%s" % (o["display"], o["parent"], n))
set_hide(False)
reset_scene()

print("\n### 设置：全屏时隐藏按钮 = 开（showInFullscreen=true，默认值）—— 只做记录 ###")
set_hide(True)
reset_scene()
o, n = scene("G 基线")
check("G 普通页面：按钮可见", True, o["display"] != "none" and (n or 0) > 150, "painted=%s" % n)

cdp.ev(sid_v, "window.enterNativeBox()", user_gesture=True)
time.sleep(1.2)
o, n = scene("G 原生全屏(容器)")
check("G 原生全屏(容器)：按钮搬进全屏容器并画出来", True,
      o["parent"] == "fsbox" and (n or 0) > 150, "parent=%s painted=%s" % (o["parent"], n))
reset_scene()

cdp.ev(sid_v, "window.enterNativeVideo()", user_gesture=True)
time.sleep(1.2)
o, n = scene("G 原生全屏(video)")
check("G 原生全屏(video 元素)：按钮是否真的可见（现状记录）", True, (n or 0) > 150,
      "painted=%s（0 = 承诺「全屏仍显示」但实际看不到）" % n)
reset_scene()

cdp.ev(sid_v, "window.enterFake()", user_gesture=True)
time.sleep(1.0)
o, n = scene("G 伪全屏")
check("G 伪全屏：开启「全屏显示」时按钮保留", True, (n or 0) > 150, "painted=%s" % n)
reset_scene()

o = obs()
info("窗口参照", "inner=%sx%s screen=%sx%s dpr=%s"
     % (o["vw"], o["vh"], o["screen"]["w"], o["screen"]["h"], cdp.ev(sid_v, "window.devicePixelRatio")))

fails = [r for r in results if not r["pass"]]
print("\n=== 汇总：%d 项，通过 %d，失败 %d ===" % (len(results), len(results) - len(fails), len(fails)))
for r in fails:
    print("  FAIL %s expect=%s actual=%s %s" % (r["case"], r["expected"], r["actual"], r["note"]))
with open(os.path.join(OUT, "vsc_fullscreen_results.json"), "w", encoding="utf-8") as f:
    json.dump({"ext_id": ext_id, "total": len(results), "fail": len(fails), "results": results},
              f, ensure_ascii=False, indent=2)
