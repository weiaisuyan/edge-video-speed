# -*- coding: utf-8 -*-
"""B站真实站点：网页全屏 / 原生全屏 下按钮的实际表现（含 DOM 形态测量）

目的：确认「非 16:9 窗口下视频被信箱化（letterbox）」时，
      网页伪全屏能不能被识别出来（视频本身可能不铺满视口，铺满的是它的定位祖先）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

PORT = 9223
URL = "https://www.bilibili.com/video/BV1BqhB6nEdN/"
OUT = os.path.dirname(os.path.abspath(__file__))

JS_STATE = """(()=>{
  const h=document.querySelector('[data-vsc]');
  const v=document.querySelector('video');
  const out={};
  out.hasVideo=!!v;
  if(v){
    const r=v.getBoundingClientRect();
    out.video={w:Math.round(r.width),h:Math.round(r.height)};
    out.videoVR={w:+ (r.width/window.innerWidth).toFixed(3), h:+(r.height/window.innerHeight).toFixed(3)};
    // 视频的祖先链（定位元素才可能造成「伪全屏」）
    const chain=[];
    let el=v.parentElement, d=0;
    while(el && el!==document.body && d<7){
      const cs=getComputedStyle(el); const q=el.getBoundingClientRect();
      chain.push({tag:(el.className&&typeof el.className==='string'?('.'+el.className.trim().split(/\\s+/).slice(0,2).join('.')):el.tagName),
                  pos:cs.position, w:Math.round(q.width), h:Math.round(q.height),
                  vr:[+(q.width/window.innerWidth).toFixed(2), +(q.height/window.innerHeight).toFixed(2)],
                  z:cs.zIndex});
      el=el.parentElement; d++;
    }
    out.chain=chain;
  }
  out.vw=window.innerWidth; out.vh=window.innerHeight;
  out.fsEl=document.fullscreenElement?document.fullscreenElement.tagName+(document.fullscreenElement.className?('.'+String(document.fullscreenElement.className).trim().split(/\\s+/)[0]):''):null;
  if(h){
    out.btnDisplay=h.style.display||'(inline)';
    out.hostParent=h.parentNode?(h.parentNode.id||h.parentNode.tagName):null;
    out.popover=h.hasAttribute('popover');
  } else out.btnDisplay='(no host)';
  if(window.__vsc_probe){ const p=window.__vsc_probe(); out.fsActive=p.fsActive; out.fsHide=p.fsHide; out.label=p.rates; }
  return out;
})()"""

cdp = CDP(PORT)
ext_id = ext_id_for("E:\\程序\\edge-video-speed")
tid_con, sid_con = cdp.open("chrome-extension://%s/popup.html" % ext_id, wait=1.2)


def set_hide(flag):
    cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};"
                    "s.showInFullscreen=%s;s.idleFade=false;s.hoverOpacity=100;"
                    "chrome.storage.local.set({settings:s},()=>r(s))}))" % ("true" if flag else "false"))
    time.sleep(0.8)


tid, sid = cdp.open(URL, wait=6.0)
cdp.activate(tid)
time.sleep(2.5)
set_hide(False)
time.sleep(1.2)

print("=== B站 初始（普通页面，设置=全屏隐藏） ===")
st = cdp.ev(sid, JS_STATE)
print("  视口 %sx%s  video=%s 占比=%s" % (st["vw"], st["vh"], st["video"], st.get("videoVR")))
print("  fsEl=%s fsActive=%s fsHide=%s 按钮 display=%s" % (st["fsEl"], st.get("fsActive"), st.get("fsHide"), st["btnDisplay"]))

# 进入 B站「网页全屏」
entered = cdp.ev(sid, """(()=>{
  const b=document.querySelector('.bpx-player-ctrl-web');
  if(!b) return 'no-button';
  b.click();
  return 'clicked';
})()""")
print("\n=== 点「网页全屏」 ===", entered)
time.sleep(2.5)
st2 = cdp.ev(sid, JS_STATE)
print("  fsEl=%s" % st2["fsEl"])
print("  video=%s 占比=%s" % (st2["video"], st2.get("videoVR")))
for c in (st2.get("chain") or []):
    print("    %-34s pos=%-8s %sx%s 占比=%s z=%s" % (c["tag"], c["pos"], c["w"], c["h"], c["vr"], c["z"]))
print("  fsActive=%s fsHide=%s 按钮 display=%s" % (st2.get("fsActive"), st2.get("fsHide"), st2["btnDisplay"]))

# 退出网页全屏 → 换成设置=全屏显示，做原生全屏对照
cdp.ev(sid, """(()=>{const b=document.querySelector('.bpx-player-ctrl-web'); if(b) b.click(); return 1})()""")
time.sleep(2.0)
print("\n=== 原生全屏（设置=全屏显示，验证「搬进容器」在真实站点仍有效） ===")
set_hide(True)
time.sleep(1.0)
moved = False
for sel in ('.bpx-player-ctrl-full', '.bpx-player-ctrl-web', '.bpx-player-ctrl-setting'):
    r = cdp.ev(sid, """(()=>{const b=document.querySelector(%r); if(!b) return null;
        const q=b.getBoundingClientRect(); return {x:q.left+q.width/2,y:q.top+q.height/2,w:q.width,h:q.height}})()""" % sel)
    if r and r["w"] > 0:
        v = cdp.ev(sid, "(()=>{const v=document.querySelector('video');const q=v.getBoundingClientRect();return {x:q.left+q.width/2,y:q.top+q.height/2}})()")
        cdp.mouse(sid, "mouseMoved", v["x"], v["y"], buttons=0)
        time.sleep(0.6)
        r = cdp.ev(sid, """(()=>{const b=document.querySelector(%r); const q=b.getBoundingClientRect();
             return {x:q.left+q.width/2,y:q.top+q.height/2}})()""" % sel)
        cdp.click(sid, r["x"], r["y"])
        time.sleep(1.8)
        moved = True
        break
print("  点全屏按钮 =", moved)
st3 = cdp.ev(sid, JS_STATE)
print("  fsEl=%s 按钮 display=%s 宿主父节点=%s popover=%s fsActive=%s"
      % (st3["fsEl"], st3["btnDisplay"], st3.get("hostParent"), st3.get("popover"), st3.get("fsActive")))
cdp.ev(sid, "document.fullscreenElement?document.exitFullscreen():1", user_gesture=True)
time.sleep(1.2)
print("\n=== 站点原生全屏支持情况（供人工判断） ===")
info = cdp.ev(sid, """(()=>{
  const b=document.querySelector('.bpx-player-ctrl-full');
  return {hasFullBtn:!!b, supported:!!(document.documentElement.requestFullscreen), title:b?b.getAttribute('aria-label')||b.title||'':''}})()""")
print(" ", info)
