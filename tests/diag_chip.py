# -*- coding: utf-8 -*-
"""拖动排序诊断：确认 pointerdown 是否到达、拖动过程中 DOM 顺序是否变化"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

cdp = CDP(int(os.environ.get("VSC_PORT", "9224")))
eid = ext_id_for("E:\\程序\\edge-video-speed")
tid, sid = cdp.open("chrome-extension://%s/options.html" % eid, wait=2.2)
cdp.activate(tid)

print("viewport:", cdp.ev(sid, "({w:innerWidth,h:innerHeight})"))
JS_RECT = ("Array.from(document.querySelectorAll('#speedChips .mp-chip')).map(c=>{"
           "const r=c.getBoundingClientRect();return {rate:c.getAttribute('data-rate'),"
           "x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}})")
print("chips:", cdp.ev(sid, JS_RECT))

# 装事件探针
cdp.ev(sid, """(()=>{window.__log=[];
document.getElementById('speedChips').addEventListener('pointerdown',e=>window.__log.push('pd:'+(e.target.className||e.target.tagName)));
window.addEventListener('pointerup',e=>window.__log.push('pu'),true);
window.addEventListener('pointermove',e=>{if(window.__log.length<40)window.__log.push('pm');},true);
window.addEventListener('pointercancel',e=>window.__log.push('pcancel'),true);
return 1})()""")

r = cdp.ev(sid, "(()=>{const c=document.querySelectorAll('#speedChips .mp-chip')[0];const r=c.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
print("click target:", r)
cdp.click(sid, r["x"], r["y"])
time.sleep(0.4)
print("log after click:", cdp.ev(sid, "window.__log.slice(0,12)"))
print("defaultSpeed:", cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings&&o.settings.defaultSpeed)))"))

# 现在做一次拖动
cdp.ev(sid, "window.__log=[]")
chips = cdp.ev(sid, JS_RECT)
src, dst = chips[0], chips[-1]
print("drag %s -> %s" % (src, dst))
cdp.mouse(sid, "mousePressed", src["x"], src["y"])
time.sleep(0.08)
for i in range(1, 13):
    x = src["x"] + (dst["x"] - src["x"]) * i / 12.0
    y = src["y"] + (dst["y"] - src["y"]) * i / 12.0
    cdp.mouse(sid, "mouseMoved", x, y, buttons=1)
    time.sleep(0.04)
time.sleep(0.05)
print("order mid-drag:", cdp.ev(sid, "Array.from(document.querySelectorAll('#speedChips .mp-chip')).map(c=>c.getAttribute('data-rate'))"))
print("log mid-drag:", cdp.ev(sid, "window.__log.slice(0,8)"))
cdp.mouse(sid, "mouseReleased", dst["x"], dst["y"], buttons=0)
time.sleep(0.6)
print("order after:", cdp.ev(sid, "Array.from(document.querySelectorAll('#speedChips .mp-chip')).map(c=>c.getAttribute('data-rate'))"))
print("log after:", cdp.ev(sid, "window.__log.slice(0,10)"))
print("stored:", cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings&&o.settings.speeds)))"))
