# -*- coding: utf-8 -*-
"""YouTube 专项：①外部改速是谁弹回的（逐次 ratechange 日志）②真实走 YouTube 自带菜单改速，扩展是否跟随"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
results = []


def check(name, expected, actual, note=""):
    ok = (expected == actual)
    results.append({"case": name, "expected": expected, "actual": actual, "pass": ok, "note": note})
    print("%-4s %-52s expect=%s actual=%s %s" % ("PASS" if ok else "FAIL", name, expected, actual, note))
    return ok


JS_BTN = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelector('.btn').textContent.trim() : null})()"
JS_RATES = "Array.from(document.querySelectorAll('video')).map(v=>v.playbackRate)"

cdp = CDP(9222)
ext_id = ext_id_for(r"E:\程序\edge-video-speed")
tid_c, sid_c = cdp.open("chrome-extension://%s/options.html" % ext_id, wait=1.5)


def store_get():
    return cdp.ev(sid_c, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings||{})))")


cdp.ev(sid_c, "new Promise(r=>chrome.storage.local.clear(()=>r(1)))")
time.sleep(0.5)

print("=== YouTube 专项 ===")
tid, sid = cdp.open(URL, wait=10)
cdp.activate(tid)
time.sleep(4)
print("video 数:", cdp.ev(sid, "document.querySelectorAll('video').length"),
      "| 按钮:", cdp.ev(sid, JS_BTN), "| readyState:",
      cdp.ev(sid, "document.querySelector('video').readyState"))

# 挂 ratechange 日志（页面侧观察者）
cdp.ev(sid, """(()=>{window.__log=[];const v=document.querySelector('video');
  v.addEventListener('ratechange',()=>window.__log.push([Math.round(performance.now()), v.playbackRate]));
  window.__ytState=()=>{try{return document.querySelector('.ytp-settings-button')?1:0}catch(e){return -1}};return 1})()""")

# ① 扩展先设 1.5
r = cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');const x=b.getBoundingClientRect();return {x:x.left+x.width/2,y:x.top+x.height/2}})()")
cdp.click(sid, r["x"], r["y"])
chip = cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');for(const c of h.shadowRoot.querySelectorAll('.chip')){if(c.textContent.trim()==='1.5×'){const b=c.getBoundingClientRect();return {x:b.left+b.width/2,y:b.top+b.height/2}}}})()")
cdp.click(sid, chip["x"], chip["y"])
time.sleep(1.0)
print("扩展设 1.5× 后：", cdp.ev(sid, JS_RATES), cdp.ev(sid, JS_BTN))
cdp.ev(sid, "window.__log=[]")

# ② 外部（模拟站点）改 1.25 → 看谁弹回
cdp.ev(sid, "document.querySelector('video').playbackRate = 1.25; 1", await_promise=False)
time.sleep(2.5)
log = cdp.ev(sid, "window.__log")
print("外部改 1.25 后的 ratechange 序列（时间ms, 速率）:", log)
print("此时 video:", cdp.ev(sid, JS_RATES), "| 按钮:", cdp.ev(sid, JS_BTN),
      "| storage 记录:", (store_get() or {}).get("siteSpeeds", {}))

# ③ 真实路径：走 YouTube 自带菜单把速度改成 1.25
cdp.ev(sid, "window.__log=[]")
menu_ok = cdp.ev(sid, """(()=>{
  const btn=document.querySelector('.ytp-settings-button'); if(!btn) return 'no-gear';
  btn.click(); return 'gear-clicked';})()""")
time.sleep(0.8)
step1 = cdp.ev(sid, """(()=>{
  const items=[...document.querySelectorAll('.ytp-settings-menu .ytp-menuitem')];
  const t=items.map(i=>i.textContent.trim());
  const it=items.find(i=>/速度|speed/i.test(i.textContent));
  if(it){it.click(); return 'opened-speed:'+t.join('|');}
  return 'items:'+t.join('|');})()""")
time.sleep(0.8)
step2 = cdp.ev(sid, """(()=>{
  const items=[...document.querySelectorAll('.ytp-settings-menu .ytp-menuitem')];
  const t=items.map(i=>i.textContent.trim());
  const it=items.find(i=>/^1\\.25/.test(i.textContent.trim()));
  if(it){it.click(); return 'picked-1.25';}
  return 'items:'+t.join('|');})()""")
time.sleep(2.0)
print("YouTube 菜单：", menu_ok, "|", step1[:120], "|", step2[:120])
rates = cdp.ev(sid, JS_RATES)
btn = cdp.ev(sid, JS_BTN)
st = (store_get() or {}).get("siteSpeeds", {})
print("走 YouTube 菜单改 1.25 后 → video:", rates, "| 扩展按钮:", btn, "| storage:", st)
print("ratechange 序列:", cdp.ev(sid, "window.__log"))

if step2 == "picked-1.25":
    check("YouTube 自带菜单改 1.25× → 扩展不抢回", [1.25], rates)
    check("YouTube 自带菜单改 1.25× → 按钮同步显示", "1.25×", btn)
    check("YouTube 自带菜单改 1.25× → 按网站记住", 1.25, st.get("www.youtube.com"))
    time.sleep(3.0)
    check("3 秒后仍保持 1.25×（扩展不与播放器打架）", [1.25], cdp.ev(sid, JS_RATES))
else:
    check("YouTube 菜单可达（能取到播放速度菜单项）", "picked-1.25", step2, "YouTube UI 结构可能变了")

cdp.shot(sid, os.path.join(OUT, "shot_youtube.png"))
fails = [r for r in results if not r["pass"]]
print("\n=== 汇总：%d 项，通过 %d，失败 %d ===" % (len(results), len(results) - len(fails), len(fails)))
with open(os.path.join(OUT, "vsc_youtube_results.json"), "w", encoding="utf-8") as f:
    json.dump({"total": len(results), "fail": len(fails), "results": results}, f, ensure_ascii=False, indent=2)
