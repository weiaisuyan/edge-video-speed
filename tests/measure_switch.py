# -*- coding: utf-8 -*-
"""量开关（toggle）里圆圈与背景条的垂直对齐：DOM 几何 + 4x 截图逐行像素剖面"""
import base64
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402
from PIL import Image  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
label = sys.argv[1] if len(sys.argv) > 1 else "before"

cdp = CDP(9222)
ext = ext_id_for(r"E:\程序\edge-video-speed")
tid, sid = cdp.open("chrome-extension://%s/options.html" % ext, wait=2.0)

# 让第一个开关处于「开」状态（圆圈在右），并滚动到可见
cdp.ev(sid, "document.getElementById('visible').checked = true; 1")
cdp.ev(sid, "document.querySelector('.row').scrollIntoView({block:'center'}); 1")
time.sleep(0.8)

geom = cdp.ev(sid, """(()=>{
  const row = [...document.querySelectorAll('.row')].find(r => r.querySelector('.switch'));
  const sw = row.querySelector('.switch');
  const tr = sw.querySelector('.track');
  const th = sw.querySelector('.thumb');
  const a = tr.getBoundingClientRect(), b = th.getBoundingClientRect(), c = sw.getBoundingClientRect();
  const rt = row.getBoundingClientRect();
  return {
    rowH: Math.round(rt.height),
    switchBox: [Math.round(c.width), Math.round(c.height)],
    switchTopInRow: Math.round(c.top - rt.top),
    track: [Math.round(a.width), Math.round(a.height)],
    thumb: [Math.round(b.width), Math.round(b.height)],
    thumbTopGap: Math.round(b.top - a.top),
    thumbBottomGap: Math.round(a.bottom - b.bottom),
    thumbLeftGap: Math.round(b.left - a.left),
    thumbRightGap: Math.round(a.right - b.right),
    trackBg: getComputedStyle(tr).backgroundColor,
    thumbBg: getComputedStyle(th).backgroundColor,
    switchDisplay: getComputedStyle(sw).display
  };
})()""")
print("[%s] DOM 几何:" % label, geom)
tg = geom.get("thumbTopGap")
bg = geom.get("thumbBottomGap")
print("[%s] DOM 判定：上间隙=%s 下间隙=%s 差值=%s px -> %s" %
      (label, tg, bg, abs((tg or 0) - (bg or 0)), "居中" if tg == bg else "未居中"))

# 4x 放大截图，再做逐行像素剖面（客观指标）
box = cdp.ev(sid, """(()=>{const sw=document.querySelector('.switch');const r=sw.getBoundingClientRect();
  return {x:Math.max(0,r.left-6),y:Math.max(0,r.top-6),w:r.width+12,h:r.height+12}})()""")
shot = cdp.send("Page.captureScreenshot", {"format": "png", "clip": {
    "x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"], "scale": 4}}, session=sid, timeout=30)
p = os.path.join(OUT, "switch_%s.png" % label)
with open(p, "wb") as f:
    f.write(base64.b64decode(shot["data"]))

im = Image.open(p).convert("RGB")
W, H = im.size
px = im.load()
white_rows, track_rows = [], []
for y in range(H):
    w = t = 0
    for x in range(W):
        r, g, b = px[x, y]
        if r > 205 and g > 205 and b > 205:
            w += 1
        elif abs(r - 51) < 26 and abs(g - 55) < 26 and abs(b - 61) < 26:
            t += 1
    if w > 4:
        white_rows.append(y)
    if t > 6:
        track_rows.append(y)
if white_rows and track_rows:
    wc = (min(white_rows) + max(white_rows)) / 2.0
    tc = (min(track_rows) + max(track_rows)) / 2.0
    print("[%s] 像素剖面(4x)：圆圈中心 y=%.1f 条中心 y=%.1f 差=%.1f 设备像素 = %.2f CSS px" %
          (label, wc, tc, wc - tc, (wc - tc) / 4.0))
else:
    print("[%s] 像素剖面：未识别到圆圈/条（white_rows=%d track_rows=%d）" % (label, len(white_rows), len(track_rows)))
print("[%s] 截图: %s (%dx%d)" % (label, p, W, H))
