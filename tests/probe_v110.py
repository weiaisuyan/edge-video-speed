# -*- coding: utf-8 -*-
"""v1.1.0 探针：①设置页档位拖动排序 ②工具栏弹窗「本网站隐藏 / 本网站显示」两态

真 Edge + 真实扩展（--load-extension）+ CDP 合成鼠标事件。
判据全部来自真实 DOM / chrome.storage，不看截图。
"""
import json
import os
import sys
import time

import faulthandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

faulthandler.dump_traceback_later(240, exit=True)

LOAD_PATH = os.environ.get("VSC_EXT_PATH", "E:\\程序\\edge-video-speed")
PORT = int(os.environ.get("VSC_PORT", "9224"))
BASE = "http://127.0.0.1:%d/" % int(os.environ.get("VSC_HTTP_PORT", "8784"))
PAGE = BASE + "vsc_test_basic.html"
SITE = "127.0.0.1"

results = []


def check(name, expected, actual, note=""):
    ok = (expected == actual)
    results.append({"case": name, "expected": expected, "actual": actual, "pass": ok, "note": note})
    print("%-4s %-52s expect=%s actual=%s %s" % ("PASS" if ok else "FAIL", name, expected, actual, note))
    return ok


def check_true(name, cond, note=""):
    return check(name, True, bool(cond), note)


ext_id = ext_id_for(LOAD_PATH)
print("ext_id(by path hash)=%s" % ext_id)
cdp = CDP(PORT)

# 真实扩展 ID 不能靠路径哈希猜（实测与 Edge 实际 ID 不符 → 打开 options 页被「已阻止」）。
# 硬判据 = target 列表里出现 chrome-extension://<id>/background.js 的 service_worker。
def real_ext_id():
    for t in cdp.targets():
        u = t.get("url") or ""
        if t.get("type") == "service_worker" and u.startswith("chrome-extension://") and u.endswith("/background.js"):
            return u.split("/")[2]
    return ""

for _ in range(20):
    rid = real_ext_id()
    if rid:
        break
    time.sleep(0.5)
print("ext_id(from SW target)=%s" % rid)
if not rid:
    print("FAIL 扩展未加载（target 列表里没有 background.js 的 service_worker）")
    sys.exit(1)
ext_id = rid

# ---------- 1) 设置页：档位拖动排序 ----------

opt_url = "chrome-extension://%s/options.html" % ext_id
tid, sid = cdp.open(opt_url, wait=2.0)
cdp.activate(tid)

JS_ORDER = ("(()=>{return Array.from(document.querySelectorAll('#speedChips .mp-chip'))"
            ".map(c=>c.getAttribute('data-rate'))})()")
JS_CHIP_RECT = ("(()=>{const cs=document.querySelectorAll('#speedChips .mp-chip');"
                "const out=[];cs.forEach(c=>{const r=c.getBoundingClientRect();"
                "out.push({rate:c.getAttribute('data-rate'),x:r.left+r.width/2,y:r.top+r.height/2,"
                "l:r.left,t:r.top,r:r.right,b:r.bottom})});return out})()")


def scroll_chips_into_view(sid):
    """把档位区滚进视口：CDP 合成点击用的是视口坐标，元素在视口外就点不中
    （第一次跑 T2/T5 全失败的真因就是 viewport 只有 750×485、档位区在下面）"""
    cdp.ev(sid, "(()=>{const b=document.getElementById('speedChips');"
                "b.scrollIntoView({block:'center'});return 1})()")
    time.sleep(0.3)
    # 再确认一次：所有档位都在视口内
    return cdp.ev(sid, """(()=>{const vh=innerHeight;const cs=document.querySelectorAll('#speedChips .mp-chip');
      let ok=0;cs.forEach(c=>{const r=c.getBoundingClientRect();if(r.top>=0&&r.bottom<=vh&&r.height>0)ok++;});
      return {count:cs.length,inView:ok,vh:vh}})()""")

# 先把档位设成一个非升序的初始顺序，验证「不再自动按数值排序」
setup = cdp.ev(sid, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  const s = Object.assign({}, o.settings||{});
  s.speeds = [2, 1.5, 1, 0.75, 2.5, 0.5];
  s.defaultSpeed = 1.5;
  s.excludedSites = [];
  s.siteSpeeds = {};
  await new Promise(r=>chrome.storage.local.set({settings:s}, r));
  return s.speeds;
})()""")
print("setup speeds =", setup)

cdp.ev(sid, "location.reload()", await_promise=False)
time.sleep(2.0)

order0 = cdp.ev(sid, JS_ORDER)
check("T1 非升序顺序被原样保留（不再自动排序）", ["2", "1.5", "1", "0.75", "2.5", "0.5"], order0)

vis = scroll_chips_into_view(sid)
print("chips in view:", vis)

# 拖第 1 格（2×）到最后一格（0.5×）的右半区 → 应排到末尾
chips = cdp.ev(sid, JS_CHIP_RECT)
src = chips[0]
dst = chips[-1]
cdp.mouse(sid, "mousePressed", src["x"], src["y"])
time.sleep(0.05)
for i in range(1, 13):
    x = src["x"] + (dst["x"] - src["x"]) * i / 12.0
    y = src["y"] + (dst["y"] - src["y"]) * i / 12.0
    cdp.mouse(sid, "mouseMoved", x, y, buttons=1)
    time.sleep(0.03)
# 停在最后一格右半边
cdp.mouse(sid, "mouseMoved", dst["r"] - 4, dst["y"], buttons=1)
time.sleep(0.05)
cdp.mouse(sid, "mouseReleased", dst["r"] - 4, dst["y"], buttons=0)
time.sleep(0.6)

order1 = cdp.ev(sid, JS_ORDER)
check("T2 拖动后顺序 = 首项移到末尾", ["1.5", "1", "0.75", "2.5", "0.5", "2"], order1)

stored = cdp.ev(sid, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  return (o.settings&&o.settings.speeds)||null;
})()""")
check("T3 新顺序已落盘到 storage", [1.5, 1, 0.75, 2.5, 0.5, 2], stored)

# 刷新后顺序仍在（持久化）
cdp.ev(sid, "location.reload()", await_promise=False)
time.sleep(2.0)
check("T4 刷新后顺序仍保持", ["1.5", "1", "0.75", "2.5", "0.5", "2"], cdp.ev(sid, JS_ORDER))

# 单击（不移动）= 设为默认速度，且顺序不变
scroll_chips_into_view(sid)
chips = cdp.ev(sid, JS_CHIP_RECT)
c = chips[2]
cdp.click(sid, c["x"], c["y"])
time.sleep(0.5)
def_speed = cdp.ev(sid, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  return o.settings.defaultSpeed;
})()""")
check("T5 单击档位 = 设为默认速度", 0.75, def_speed)
check("T6 单击不改变顺序", ["1.5", "1", "0.75", "2.5", "0.5", "2"], cdp.ev(sid, JS_ORDER))

# 新增档位追加到末尾（不插到排序位）
cdp.ev(sid, "(()=>{document.getElementById('newSpeed').value='3.5';document.getElementById('addSpeed').click();return 1})()")
time.sleep(0.5)
check("T7 新档位追加到末尾", ["1.5", "1", "0.75", "2.5", "0.5", "2", "3.5"], cdp.ev(sid, JS_ORDER))

# ---------- 2) 页面菜单跟随新顺序 ----------

ptid, psid = cdp.open(PAGE, wait=2.2)
cdp.activate(ptid)
host_ok = cdp.ev(psid, "document.querySelector('[data-vsc]')?1:0")
check("T8 测试页注入悬浮按钮", 1, host_ok)

JS_PANEL_CHIPS = ("(()=>{const h=document.querySelector('[data-vsc]');if(!h)return null;"
                  "const p=h.shadowRoot.querySelector('.panel');"
                  "if(!p.classList.contains('open'))return 'closed';"
                  "return Array.from(p.querySelectorAll('.chip')).map(c=>c.textContent.trim())})()")

# 点按钮开菜单
rect = cdp.ev(psid, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                    "const r=b.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
cdp.click(psid, rect["x"], rect["y"])
time.sleep(0.5)
panel_chips = cdp.ev(psid, JS_PANEL_CHIPS)
check("T9 页面菜单档位顺序 = 设置页顺序",
      ["1.5×", "1×", "0.75×", "2.5×", "0.5×", "2×", "3.5×"], panel_chips)

# ---------- 3) 工具栏弹窗：本网站隐藏 / 本网站显示 ----------

pop_url = "chrome-extension://%s/popup.html" % ext_id
ptid2, psid2 = cdp.open("about:blank", wait=0.5)
# 打桩 chrome.tabs.query：把当前标签当成「正在看的网站」
stub = ("(()=>{ if(!window.chrome||!chrome.tabs) return; "
        "chrome.tabs.query=function(q,cb){cb([{url:'%s'}]);};})()" % PAGE)
cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": stub}, session=psid2)
cdp.send("Page.navigate", {"url": pop_url}, session=psid2)
time.sleep(2.0)
cdp.activate(ptid2)

JS_TOGGLE_TEXT = "(()=>{const b=document.querySelector('[data-act=\"hide\"]');return b?b.textContent.trim():null})()"
JS_TOGGLE_DISABLED = "(()=>{const b=document.querySelector('[data-act=\"hide\"]');return b?b.disabled:null})()"
JS_HINT = "(()=>{const e=document.getElementById('hint');return e?e.textContent.trim():null})()"

check("T10 弹窗识别到当前网站（打桩成功）", "本网站隐藏", cdp.ev(psid2, JS_TOGGLE_TEXT))

cdp.ev(psid2, "document.querySelector('[data-act=\"hide\"]').click()")
time.sleep(0.8)
excl = cdp.ev(psid2, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  return (o.settings&&o.settings.excludedSites)||[];
})()""")
check("T11 点「本网站隐藏」→ 加入排除清单", [SITE], excl)
check("T12 按钮变成「本网站显示」（不再 disabled）", "本网站显示", cdp.ev(psid2, JS_TOGGLE_TEXT))
check("T13 按钮可点（disabled=false）", False, cdp.ev(psid2, JS_TOGGLE_DISABLED))

# 页面侧应实时隐藏按钮（storage.onChanged）
time.sleep(0.8)
check("T14 页面悬浮按钮立即隐藏", "none", cdp.ev(psid, "(()=>{const h=document.querySelector('[data-vsc]');"
                                                    "return h?h.style.display:null})()"))

# 再点一次 → 显示回来
cdp.ev(psid2, "document.querySelector('[data-act=\"hide\"]').click()")
time.sleep(0.9)
excl2 = cdp.ev(psid2, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  return (o.settings&&o.settings.excludedSites)||[];
})()""")
check("T15 再点「本网站显示」→ 排除清单移除本站", [], excl2)
check("T16 按钮回到「本网站隐藏」", "本网站隐藏", cdp.ev(psid2, JS_TOGGLE_TEXT))
check("T17 页面悬浮按钮立即恢复", "block", cdp.ev(psid, "(()=>{const h=document.querySelector('[data-vsc]');"
                                                     "return h?h.style.display:null})()"))

# ---------- 4) 上级域名条目也能被「显示」移除 ----------

# 先清空排除清单，再做上级域名一致性单测（在设置页里跑 shared.js 的纯函数）
cdp.ev(sid, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  const s = Object.assign({}, o.settings||{});
  s.excludedSites = ['127.0.0.1', 'example.com'];
  await new Promise(r=>chrome.storage.local.set({settings:s}, r));
  return s.excludedSites;
})()""")
cdp.send("Page.navigate", {"url": pop_url}, session=psid2)
time.sleep(1.8)
check("T18 排除清单命中本站时按钮显示「本网站显示」", "本网站显示", cdp.ev(psid2, JS_TOGGLE_TEXT))
cdp.ev(psid2, "document.querySelector('[data-act=\"hide\"]').click()")
time.sleep(0.8)
excl3 = cdp.ev(psid2, """(async()=>{
  const o = await new Promise(r=>chrome.storage.local.get('settings',r));
  return (o.settings&&o.settings.excludedSites)||[];
})()""")
check("T19 点「显示」只移除命中本站的条目，保留其它站点", ["example.com"], excl3)

# shared.js 纯函数单测：条目 zhihu.com 命中 www.zhihu.com，且 removeSiteEntries 能一致地移除它
unit = cdp.ev(sid, """(()=>{
  const S = window.VSC_SHARED;
  return {
    hit: S.isSiteExcluded(['zhihu.com'], 'www.zhihu.com'),
    removed: S.removeSiteEntries(['zhihu.com', 'example.com'], 'www.zhihu.com'),
    keepOther: S.removeSiteEntries(['example.com'], 'www.zhihu.com'),
    noMatch: S.isSiteExcluded(['zhihu.com'], 'bilibili.com')
  };
})()""")
check("T20 上级域名条目命中子域", True, unit["hit"])
check("T21 removeSiteEntries 移除上级条目、保留其它", ["example.com"], unit["removed"])
check("T22 未命中时不动其它条目", ["example.com"], unit["keepOther"])
check("T23 不同站点不误命中", False, unit["noMatch"])

# ---------- 汇总 ----------

passed = sum(1 for r in results if r["pass"])
print("\n==== %d/%d PASS ====" % (passed, len(results)))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vsc_v110_results.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("results ->", out)
sys.exit(0 if passed == len(results) else 1)
