# -*- coding: utf-8 -*-
"""重拍商店「设置页」两张截图（screenshot-3 / screenshot-4），精确 1280×800

为什么要单独一件事：设置页头部会显示版本号（v1.0.x），版本一升级旧截图就过期。
本脚本拍完会读 DOM 核对版本号，避免拍到旧版本。
用法：先起测试浏览器（--load-extension 本目录），再 python3 tests/shots_options.py
"""
import base64
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

from PIL import Image  # noqa: E402

OUT = r"E:\程序\edge-video-speed\store"
W, H = 1280, 800
PORT = 9223
cdp = CDP(PORT)
ext = ext_id_for(r"E:\程序\edge-video-speed")
tid, sid = cdp.open("chrome-extension://%s/options.html" % ext, wait=2.0)

# 统一外观（与既有截图保持一致：150% 尺寸 + 深海渐变 + 关掉淡化，按钮清晰）
cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};"
           "s.size=150;s.styleId='deep';s.radius=42;s.showNumber=true;s.idleFade=false;"
           "s.hoverOpacity=100;s.siteSpeeds={};s.showInFullscreen=true;"
           "chrome.storage.local.set({settings:s},()=>r(1))}))")
time.sleep(1.0)
cdp.send("Page.reload", session=sid)
time.sleep(2.0)
cdp.send("Emulation.setDeviceMetricsOverride",
         {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False}, session=sid)
time.sleep(1.0)

ver_tag = cdp.ev(sid, "document.getElementById('verTag').textContent")
ver_manifest = cdp.ev(sid, "chrome.runtime.getManifest().version")
print("设置页版本标签 =", ver_tag, " manifest =", ver_manifest)
assert ver_tag == "v" + ver_manifest, "版本号对不上，可能拍到了旧版本"


def shot(path):
    r = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False},
                 session=sid, timeout=40)
    open(path, "wb").write(base64.b64decode(r["data"]))
    print(os.path.basename(path), Image.open(path).size)


cdp.ev(sid, "window.scrollTo(0,0); 1")
time.sleep(1.0)
shot(os.path.join(OUT, "screenshot-3.png"))

cdp.ev(sid, "window.scrollTo(0, document.getElementById('mockPanel').getBoundingClientRect().top + window.scrollY - 110); 1")
time.sleep(1.0)
shot(os.path.join(OUT, "screenshot-4.png"))

try:
    cdp.send("Emulation.clearDeviceMetricsOverride", session=sid)
except Exception:
    pass
cdp.send("Target.closeTarget", {"targetId": tid})
print("done")
