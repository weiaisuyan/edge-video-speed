# -*- coding: utf-8 -*-
"""实验：popover（顶层）能否让宿主按钮渲染在全屏 <video> 之上

背景：全屏元素是 <video> 本身时，浏览器只绘制该元素（它不渲染子元素），
现有实现把 host 搬进全屏容器 → 看不到。若 popover 可行，即可修复该承诺。
"""
import base64
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402
from PIL import Image

BASE = "http://127.0.0.1:8782/"
PORT = 9223
OUT = os.path.dirname(os.path.abspath(__file__))
BTN_BG = (95, 114, 133)

cdp = CDP(PORT)
ext_id = ext_id_for("E:\\程序\\edge-video-speed")
tid_con, sid_con = cdp.open("chrome-extension://%s/popup.html" % ext_id, wait=1.2)
cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};"
                "s.showInFullscreen=true;s.idleFade=false;s.hoverOpacity=100;s.excludedSites=[];"
                "s.visible=true;s.displayMode='videoOnly';s.styleId='mist';s.showNumber=true;"
                "chrome.storage.local.set({settings:s},()=>r(s))}))")
tid, sid = cdp.open(BASE + "vsc_test_fullscreen.html", wait=2.4)
cdp.activate(tid)
time.sleep(0.6)
cdp.ev(sid, "window.playVideo()", user_gesture=True)
time.sleep(0.5)


def hit(tag):
    r = cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                    "const q=b.getBoundingClientRect();return {x:q.left,y:q.top,w:q.width,h:q.height,"
                    "parent:h.parentNode?(h.parentNode.id||h.parentNode.tagName):null,"
                    "pop:h.hasAttribute('popover'),disp:h.style.display}})()")
    dpr = cdp.ev(sid, "window.devicePixelRatio") or 1
    shot = cdp.send("Page.captureScreenshot", {"format": "png"}, session=sid, timeout=30)
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
    x0 = int(max(0, (r["x"] - 4) * dpr)); y0 = int(max(0, (r["y"] - 4) * dpr))
    x1 = int(min(img.width, (r["x"] + r["w"] + 4) * dpr)); y1 = int(min(img.height, (r["y"] + r["h"] + 4) * dpr))
    n = 0
    if x1 > x0 and y1 > y0:
        for px in img.crop((x0, y0, x1, y1)).getdata():
            if sum(abs(px[i] - BTN_BG[i]) for i in range(3)) < 90:
                n += 1
    print("  %-26s parent=%-8s popover=%-5s display=%-6s 按钮像素=%s" % (tag, r["parent"], r["pop"], r["disp"], n))
    return n


# 1) 全屏 <video>：现状（不搬进去，因为搬进去也看不到）
cdp.ev(sid, "window.enterNativeVideo()", user_gesture=True)
time.sleep(1.3)
print("全屏元素 =", cdp.ev(sid, "document.fullscreenElement.tagName"))
n0 = hit("video全屏 现状")

# 2) 试着把 host 变成 manual popover（进顶层）
err = cdp.ev(sid, """(()=>{const h=document.querySelector('[data-vsc]');
  try{ h.setAttribute('popover','manual'); h.showPopover(); }
  catch(e){ return 'ERR: '+e.name+' '+e.message }
  return 'ok' })()""")
print("  set popover ->", err)
time.sleep(0.8)
n1 = hit("video全屏 + popover")

# 3) 顺手验证：popover 状态下 display:none 是否照样能隐藏
cdp.ev(sid, "document.querySelector('[data-vsc]').style.display='none';1")
time.sleep(0.4)
n2 = hit("popover + display:none")
cdp.ev(sid, "document.querySelector('[data-vsc]').style.display='block';1")
time.sleep(0.3)
# 4) 退出全屏后 popover 是否还正常（按钮还在原位、可点）
cdp.ev(sid, "document.exitFullscreen()", user_gesture=True)
time.sleep(1.2)
n3 = hit("退出全屏后 popover 仍在")
print("\n结论：video 全屏下现状=%s 像素；加 popover=%s 像素 → %s" % (n0, n1, "popover 有效" if n1 > 150 else "popover 无效"))
