# -*- coding: utf-8 -*-
"""视频速度控制扩展 — 本地量化测试（真实 Edge + 真实扩展加载 + CDP 合成事件）"""
import json
import os
import sys
import time

import faulthandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

faulthandler.dump_traceback_later(180, exit=True)   # 卡住时自动吐栈，避免静默挂死

BASE = "http://127.0.0.1:8782/"
LOAD_PATH = "E:\\程序\\edge-video-speed"
PORT = 9223
OUT = os.path.dirname(os.path.abspath(__file__))

results = []


def check(name, expected, actual, note=""):
    ok = (expected == actual)
    results.append({"case": name, "expected": expected, "actual": actual, "pass": ok, "note": note})
    print("%-4s %-46s expect=%s actual=%s %s" % ("PASS" if ok else "FAIL", name, expected, actual, note))
    return ok


def check_true(name, cond, actual_desc="", note=""):
    return check(name, True, bool(cond), actual_desc or note)


# ---------- 页面读取助手（主世界 DOM，即用户能看到的东西） ----------
JS_HOST = "document.querySelector('[data-vsc]') ? 1 : 0"
JS_VISIBLE = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.style.display !== 'none' : null})()"
JS_VIDS = "document.querySelectorAll('video').length"
JS_RATES = "Array.from(document.querySelectorAll('video')).map(v=>v.playbackRate)"
JS_BTN = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelector('.btn').textContent.trim() : null})()"
JS_PANEL = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelector('.panel').classList.contains('open') : null})()"
JS_CHIPN = "(()=>{const h=document.querySelector('[data-vsc]'); return h ? h.shadowRoot.querySelectorAll('.chip').length : null})()"
JS_HOSTPARENT = "(()=>{const h=document.querySelector('[data-vsc]'); return h && h.parentNode ? (h.parentNode.id || h.parentNode.tagName) : null})()"


def rect_of(sid, sel):
    return cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const e=h.shadowRoot.querySelector(%r);"
                       "if(!e) return null;const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,h:r.height}})()" % sel)


def rect_of_text(sid, sel, text):
    return cdp.ev(sid, "(()=>{const h=document.querySelector('[data-vsc]');const all=h.shadowRoot.querySelectorAll(%r);"
                       "for(const e of all){if(e.textContent.trim()===%r){const r=e.getBoundingClientRect();"
                       "return {x:r.left+r.width/2,y:r.top+r.height/2}}}})()" % (sel, text))


def store_get(sid):
    return cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings||{})))")


def store_patch(sid, patch_js):
    """patch_js 形如 "s.excludedSites=['127.0.0.1']" """
    return cdp.ev(sid, "new Promise(r=>chrome.storage.local.get('settings',o=>{const s=o.settings||{};%s;"
                       "chrome.storage.local.set({settings:s},()=>r(s))}))" % patch_js)


def open_panel(sid):
    if not cdp.ev(sid, JS_PANEL):
        r = rect_of(sid, ".btn")
        cdp.click(sid, r["x"], r["y"])


# ---------- 启动 ----------
print("=== 视频速度控制 本地测试 ===")
cdp = CDP(PORT)
print("Edge:", cdp.send("Browser.getVersion")["product"])

# 找到扩展 ID
ext_id = ext_id_for(LOAD_PATH)
tid_opt, sid_opt = cdp.open("chrome-extension://%s/options.html" % ext_id, wait=1.8)
try:
    ver = cdp.ev(sid_opt, "chrome.runtime.getManifest().version")
except Exception as e:
    ver = None
if not ver:
    # 兜底：从 profile Preferences 里找加载的扩展 ID
    pref = os.path.join(OUT, "vsc_auto_edge", "Default", "Preferences")
    data = json.load(open(pref, "r", encoding="utf-8"))
    for k, v in (data.get("extensions", {}).get("settings", {}) or {}).items():
        if "edge-video-speed" in json.dumps(v).lower().replace("\\\\", "\\"):
            ext_id = k
            break
    cdp.send("Target.closeTarget", {"targetId": tid_opt})
    tid_opt, sid_opt = cdp.open("chrome-extension://%s/options.html" % ext_id, wait=1.8)
    ver = cdp.ev(sid_opt, "chrome.runtime.getManifest().version")

MANIFEST_VER = json.load(open(os.path.join(r"E:\程序\edge-video-speed", "manifest.json"), encoding="utf-8"))["version"]
check("P1 扩展加载（设置页可访问 + 版本）", MANIFEST_VER, ver, "ext_id=%s" % ext_id)

# popup.html 当「storage 控制台」用（直接读写 chrome.storage）
tid_con, sid_con = cdp.open("chrome-extension://%s/popup.html" % ext_id, wait=1.2)
# 测试隔离：清空上次运行留下的设置（扩展里会自动回落到默认值）
cdp.ev(sid_con, "new Promise(r=>chrome.storage.local.clear(()=>r(1)))")
cdp.send("Page.reload", session=sid_opt)
time.sleep(1.8)
s0 = store_get(sid_con)

# ---------- P2 设置页渲染 ----------
chips = cdp.ev(sid_opt, "document.querySelectorAll('#speedChips .chip').length")
themes = cdp.ev(sid_opt, "document.querySelectorAll('#themes .tc').length")
pos = cdp.ev(sid_opt, "document.getElementById('posVal').textContent")
sites_empty = cdp.ev(sid_opt, "document.querySelector('#siteList .empty') ? 1 : 0")
check("P2 设置页渲染：9 个默认档位", 9, chips)
check("P2 设置页渲染：16 款按钮样式", 16, cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell').length"))
check("P2 设置页渲染：位置显示", "92% / 10%", pos)
check("P2 设置页渲染：排除清单为空提示", 1, sites_empty)

# ---------- P3 设置页交互 ----------
cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell')[1].click();")
time.sleep(0.4)
check("P3 点击样式 → storage.styleId", "steel", (store_get(sid_con) or {}).get("styleId"))

cdp.ev(sid_opt, "(()=>{const i=document.getElementById('newSpeed');i.value='1.35';"
                "document.getElementById('addSpeed').click();})()")
time.sleep(0.4)
s1 = store_get(sid_con)
check("P3 添加档位 1.35 → 档位数", 10, cdp.ev(sid_opt, "document.querySelectorAll('#speedChips .chip').length"))
check("P3 添加档位 1.35 → storage 含 1.35", True, 1.35 in [round(x, 2) for x in s1.get("speeds", [])])

cdp.ev(sid_opt, "document.getElementById('idleFade').click();")
time.sleep(0.35)
s2 = store_get(sid_con)
check("P3 关闭闲置淡化 → storage.idleFade", False, s2.get("idleFade"))
check("P3 关闭闲置淡化 → 滑杆 disabled", True, cdp.ev(sid_opt, "document.getElementById('idleDelay').disabled"))
cdp.ev(sid_opt, "document.getElementById('idleFade').click();")
time.sleep(0.3)

# 模拟窗口拖动定位（先把这个标签页置前 + 滚动到可见位置，否则合成输入落不到元素上）
cdp.activate(tid_opt)
time.sleep(0.4)
cdp.ev(sid_opt, "document.getElementById('mock').scrollIntoView({block:'center'}); 1")
time.sleep(0.4)
box = cdp.ev(sid_opt, "(()=>{const m=document.getElementById('mock');const r=m.getBoundingClientRect();"
                      "return {x:r.left+r.width*0.25,y:r.top+60}})()")
cdp.drag(sid_opt, box["x"], box["y"], box["x"] + 40, box["y"] + 40)
time.sleep(0.4)
s3 = store_get(sid_con)
check("P3 模拟窗口拖动 → posX 变小", True, (s3.get("posX", 999) < 92), "posX=%s posY=%s" % (s3.get("posX"), s3.get("posY")))
cdp.ev(sid_opt, "document.getElementById('resetPos').click();")
time.sleep(0.3)
# 恢复样式 + 移除 1.35 档位（保持后续断言环境干净）
cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell')[0].click();")
cdp.ev(sid_opt, "(()=>{const cs=document.querySelectorAll('#speedChips .chip');for(const c of cs){"
                "if(c.textContent.trim().indexOf('1.35')===0){c.querySelector('button').click();break;}}})()")
time.sleep(0.35)
s4 = store_get(sid_con)
check("P3 移除档位 → 回到 9 档", 9, len(s4.get("speeds", [])))

# ---------- P4 有视频页面 ----------
tid_v, sid_v = cdp.open(BASE + "vsc_test_basic.html", wait=2.2)
cdp.activate(tid_v)
time.sleep(0.3)
check("P4 有视频页：内容脚本注入（按钮存在）", 1, cdp.ev(sid_v, JS_HOST))
check("P4 有视频页：按钮可见", True, cdp.ev(sid_v, JS_VISIBLE))
check("P4 有视频页：检测到视频数", 1, cdp.ev(sid_v, JS_VIDS))
check("P4 有视频页：按钮显示当前速度", "1×", cdp.ev(sid_v, JS_BTN))
check("P4 有视频页：视频元数据已加载", True, cdp.ev(sid_v, "document.querySelector('video').readyState >= 1"))
check("P5 默认速度施加（无站点记录 → 1×）", [1], cdp.ev(sid_v, JS_RATES))

# ---------- P6 点按钮 → 面板 → 选 1.5× ----------
btn = rect_of(sid_v, ".btn")
cdp.click(sid_v, btn["x"], btn["y"])
check("P6 点按钮 → 面板打开", True, cdp.ev(sid_v, JS_PANEL))
check("P6 面板档位数量", 9, cdp.ev(sid_v, JS_CHIPN))
chip = rect_of_text(sid_v, ".chip", "1.5×")
cdp.click(sid_v, chip["x"], chip["y"])
time.sleep(0.35)
check("P6 选 1.5× → 视频 playbackRate（实测）", [1.5], cdp.ev(sid_v, JS_RATES))
check("P6 按钮文字同步", "1.5×", cdp.ev(sid_v, JS_BTN))
check("P6 按网站记忆写入 storage", 1.5, (store_get(sid_con) or {}).get("siteSpeeds", {}).get("127.0.0.1"))
check("P6 面板仍打开（可连续试速度）", True, cdp.ev(sid_v, JS_PANEL))
cdp.shot(sid_v, os.path.join(OUT, "shot_page_panel.png"))

# ---------- P7 「你在网站播放器上手动调速」（在播放器上真实点击）→ 跟随，不抢回 ----------
# 注意：必须点在「视频上」。v1.0.5 起判据是「点击坐标落在视频内 或 目标属于播放器容器」，
# 以前随便点页面任意位置都算——那不真实（点页面空白处并不是在调速度）。
_vr = cdp.ev(sid_v, "(()=>{const r=document.getElementById('v1').getBoundingClientRect();"
                    "return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
cdp.click(sid_v, _vr["x"], _vr["y"])                        # 真实点击「播放器」= 你在调速度
cdp.ev(sid_v, "window.siteReset()", await_promise=False)    # 播放器随即将速度设为 1×
time.sleep(0.8)
check("P7 手动调速（带真实点击）→ 不被抢回（跟随 1×）", [1], cdp.ev(sid_v, JS_RATES))
check("P7 跟随并同步按钮文字", "1×", cdp.ev(sid_v, JS_BTN))
# v1.0.5 行为变更：1× 也是合法选择，照常记住（旧版这里是「1× 不记录」）
check("P7 跟随并记住（1× 也记录）", 1.0,
      (store_get(sid_con) or {}).get("siteSpeeds", {}).get("127.0.0.1"),
      (store_get(sid_con) or {}).get("siteSpeeds"))
# 回到 1.5× 继续后续用例
open_panel(sid_v)
chip = rect_of_text(sid_v, ".chip", "1.5×")
cdp.click(sid_v, chip["x"], chip["y"])
time.sleep(0.4)
check("P7 再选 1.5× 生效", [1.5], cdp.ev(sid_v, JS_RATES))

# ---------- P7c 站点自己程序化重置（页面上没有用户操作）→ 不采纳，保持我们设定的速度 ----------
time.sleep(3.0)                                             # 等「最近用户输入」窗口过期
cdp.ev(sid_v, "window.siteReset()", await_promise=False)
time.sleep(0.8)
check("P7c 站点自动重置（无用户操作）→ 保持我们设定的 1.5×", [1.5], cdp.ev(sid_v, JS_RATES))

# ---------- P7b 换素材瞬间站点设默认速度 → 套用我们的速度（不算手动调速） ----------
cdp.ev(sid_v, "(()=>{const v=document.getElementById('v1');v.load();v.playbackRate=1;})()", await_promise=False)
time.sleep(0.8)
check("P7b 换素材瞬间的站点重置 → 自动套用 1.5×", [1.5], cdp.ev(sid_v, JS_RATES))

# ---------- P8 动态插入新播放器 ----------
cdp.ev(sid_v, "window.addVideo()", await_promise=False)
time.sleep(0.9)
check("P8 动态插入新 video → 自动施加", [1.5, 1.5], cdp.ev(sid_v, JS_RATES))

# ---------- P9 重新加载素材 ----------
cdp.ev(sid_v, "document.getElementById('v1').load()", await_promise=False)
time.sleep(1.0)
check("P9 素材重载后保持速度", [1.5, 1.5], cdp.ev(sid_v, JS_RATES))

# ---------- P10 快捷键 ----------
cdp.activate(tid_v)
time.sleep(0.3)
cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": ">", "code": "Period",
                                    "modifiers": 10, "windowsVirtualKeyCode": 190}, session=sid_v)
cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": ">", "code": "Period",
                                    "modifiers": 10, "windowsVirtualKeyCode": 190}, session=sid_v)
time.sleep(0.35)
check("P10 Ctrl+Shift+> 加快一档 → 1.75", [1.75, 1.75], cdp.ev(sid_v, JS_RATES))

# ---------- P11 拖动按钮（Ctrl+左键拖动 = 移动位置） ----------
cdp.activate(tid_v)
time.sleep(0.3)
before = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');return {l:parseFloat(h.style.left),t:parseFloat(h.style.top)}})()")
btn = rect_of(sid_v, ".btn")
# ① 不按 Ctrl 拖动 → 不应移动（也不能误触菜单之外的行为）
cdp.drag(sid_v, btn["x"], btn["y"], btn["x"] - 240, btn["y"] + 200)
time.sleep(0.4)
noctrl = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');return {l:parseFloat(h.style.left),t:parseFloat(h.style.top)}})()")
check("P11 不按 Ctrl 拖动 → 位置不变", [before["l"], before["t"]], [noctrl["l"], noctrl["t"]])
# ② Ctrl+左键拖动 → 移动 + 记住
btn = rect_of(sid_v, ".btn")
cdp.drag(sid_v, btn["x"], btn["y"], btn["x"] - 260, btn["y"] + 220, modifiers=2)
time.sleep(0.45)
after_pos = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');return {l:parseFloat(h.style.left),t:parseFloat(h.style.top)}})()")
sp = store_get(sid_con) or {}
check("P11 Ctrl+拖动 → 位置变化", True, after_pos["l"] < before["l"] - 100, "before.l=%s after.l=%s" % (before["l"], after_pos["l"]))
check("P11 Ctrl+拖动后位置写入 storage（记忆）", True, abs((sp.get("posX") or 0) - 92) > 5, "posX=%s posY=%s" % (sp.get("posX"), sp.get("posY")))
check("P11 拖动不会误触菜单（面板仍关）", False, cdp.ev(sid_v, JS_PANEL))
# ③ 位置记忆持久化：重新打开同页新标签，位置应沿用 storage 的百分比
posX_now, posY_now = sp.get("posX"), sp.get("posY")
tid_v2, sid_v2 = cdp.open(BASE + "vsc_test_basic.html?mem=1", wait=1.8)
v2pos = cdp.ev(sid_v2, "(()=>{const h=document.querySelector('[data-vsc]');const vw=window.innerWidth,vh=window.innerHeight;"
                       "return {x:Math.round(parseFloat(h.style.left)/vw*1000)/10, y:Math.round(parseFloat(h.style.top)/vh*1000)/10}})()")
check("P11 新标签页沿用记住的位置（±1%）", True,
      abs(v2pos["x"] - posX_now) <= 1 and abs(v2pos["y"] - posY_now) <= 1,
      "存储=%s/%s 新页实测=%s/%s" % (posX_now, posY_now, v2pos["x"], v2pos["y"]))
check("P11 新标签页速度也按网站记忆", [sp.get("siteSpeeds", {}).get("127.0.0.1")],
      cdp.ev(sid_v2, JS_RATES), "storage 记录=%s" % sp.get("siteSpeeds", {}).get("127.0.0.1"))
cdp.send("Target.closeTarget", {"targetId": tid_v2})
cdp.activate(tid_v)
time.sleep(0.3)

# ESC 关闭面板：先点开再 ESC
btn = rect_of(sid_v, ".btn")
cdp.click(sid_v, btn["x"], btn["y"])
opened = cdp.ev(sid_v, JS_PANEL)
cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, session=sid_v)
time.sleep(0.25)
check("P12 点开/ESC 关闭 面板", [True, False], [opened, cdp.ev(sid_v, JS_PANEL)])
# Ctrl+单击（不移动）仍然开菜单
btn = rect_of(sid_v, ".btn")
cdp.click(sid_v, btn["x"], btn["y"], modifiers=2)
check("P12 Ctrl+单击（未移动）也开菜单", True, cdp.ev(sid_v, JS_PANEL))
cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, session=sid_v)
time.sleep(0.25)

# ---------- P13 无视频页面 ----------
tid_n, sid_n = cdp.open(BASE + "vsc_test_novideo.html", wait=1.8)
check("P13 无视频页：脚本注入但按钮隐藏", [1, False], [cdp.ev(sid_n, JS_HOST), cdp.ev(sid_n, JS_VISIBLE)])

store_patch(sid_con, "s.displayMode='always'")
time.sleep(0.8)
check("P13 切「所有页面显示」→ 无视频页按钮出现", True, cdp.ev(sid_n, JS_VISIBLE))
store_patch(sid_con, "s.displayMode='videoOnly'")
time.sleep(0.8)
check("P13 切回「只在有视频页显示」→ 又隐藏", False, cdp.ev(sid_n, JS_VISIBLE))

# ---------- P14 网站排除 ----------
store_patch(sid_con, "s.excludedSites=['127.0.0.1']")
time.sleep(0.8)
check("P14 加入排除清单 → 视频页按钮隐藏", False, cdp.ev(sid_v, JS_VISIBLE))
store_patch(sid_con, "s.excludedSites=[]")
time.sleep(0.8)
check("P14 移除排除 → 按钮恢复", True, cdp.ev(sid_v, JS_VISIBLE))

# ---------- P15 iframe 内嵌播放器 ----------
tid_i, sid_i = cdp.open(BASE + "vsc_test_iframe.html", wait=2.8)
cdp.activate(tid_i)
time.sleep(0.3)
check("P15 iframe 页：顶层按钮可见（同源 iframe 里的视频也算本页有视频）", True, cdp.ev(sid_i, JS_VISIBLE))
iframe_rate = cdp.ev(sid_i, "(()=>{const v=document.querySelector('iframe').contentDocument.querySelector('video');return v?v.playbackRate:null})()")
_sp15 = (store_get(sid_con) or {}).get("siteSpeeds", {}).get("127.0.0.1")
check("P15 iframe 内 video playbackRate 跟随站点记忆", _sp15, iframe_rate, "storage=%s" % _sp15)

# ---------- P16 全屏（用页面自己的按钮触发真实用户手势） ----------
try:
    cdp.activate(tid_v)
    time.sleep(0.3)
    cdp.ev(sid_v, "document.getElementById('fsbtn').scrollIntoView({block:'center'}); 1")
    time.sleep(0.3)
    fbr = cdp.ev(sid_v, "(()=>{const r=document.getElementById('fsbtn').getBoundingClientRect();"
                        "return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
    cdp.click(sid_v, fbr["x"], fbr["y"])
    time.sleep(1.0)
    check("P16 进入原生全屏", "fsbox", cdp.ev(sid_v, "document.fullscreenElement ? document.fullscreenElement.id : null"))
    check("P16 全屏时按钮被搬进全屏容器（仍可见可点）", "fsbox", cdp.ev(sid_v, JS_HOSTPARENT))
    check("P16 全屏时按钮可见", True, cdp.ev(sid_v, JS_VISIBLE))
    cdp.shot(sid_v, os.path.join(OUT, "shot_fullscreen.png"))
    cdp.ev(sid_v, "document.exitFullscreen()", user_gesture=True)
    time.sleep(1.0)
    check("P16 退出全屏 → 按钮归位", "BODY", cdp.ev(sid_v, JS_HOSTPARENT))
except Exception as e:
    check("P16 全屏测试", "无异常", "异常: %s" % e)

# ---------- P17 总开关 ----------
store_patch(sid_con, "s.visible=false")
time.sleep(0.8)
check("P17 关闭扩展 → 按钮隐藏", False, cdp.ev(sid_v, JS_VISIBLE))
store_patch(sid_con, "s.visible=true")
time.sleep(0.8)
check("P17 重新开启 → 按钮恢复", True, cdp.ev(sid_v, JS_VISIBLE))

# ---------- P19 按钮样式（16 款 / 4 组） ----------
styles_count = cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell').length")
groups_count = cdp.ev(sid_opt, "document.querySelectorAll('#styles .stgroup').length")
check("P19 设置页样式网格：16 款 / 4 组", [16, 4], [styles_count, groups_count])
cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell')[12].click();")   # 第 4 组第 1 款：发光-霓虹青
time.sleep(0.7)
check("P19 选中样式写入 storage", "neonCyan", (store_get(sid_con) or {}).get("styleId"))
cdp.activate(tid_v)
time.sleep(0.3)
stt = cdp.ev(sid_v, "(()=>{const b=document.querySelector('[data-vsc]').shadowRoot.querySelector('.btn');"
                    "const c=getComputedStyle(b);return {cls:b.className,bg:c.backgroundColor,fg:c.color}})()")
check("P19 页面按钮切到发光款（带呼吸动画）", True, "anim-pulse" in (stt["cls"] or ""), stt)
check("P19 发光样式底色生效", "rgb(22, 35, 43)", stt["bg"])
cdp.ev(sid_opt, "document.querySelectorAll('#styles .stcell')[0].click();")     # 回到纯色第一款
time.sleep(0.6)
stt2 = cdp.ev(sid_v, "(()=>{const b=document.querySelector('[data-vsc]').shadowRoot.querySelector('.btn');"
                     "const c=getComputedStyle(b);return {cls:b.className,bg:c.backgroundColor}})()")
check("P19 切回纯色款：底色正确 + 无动画", ["rgb(95, 114, 133)", False], [stt2["bg"], "anim-pulse" in stt2["cls"]])

# ---------- P20 鼠标悬停 / 移开的不透明度（量「生效值」：从 host 到按钮逐级相乘，防止重复设值相乘） ----------
JS_EFF = """(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');
let op=1,n=b;while(n&&n!==h){if(n.nodeType===1){op*=parseFloat(getComputedStyle(n).opacity||1);}n=n.parentNode||n.host||null;}
return Math.round(op*1000)/1000})()"""
store_patch(sid_con, "s.hoverOpacity=100; s.idleFade=true; s.idleOpacity=20; s.idleDelay=1")
time.sleep(0.9)
cdp.activate(tid_v)
time.sleep(0.3)
btn = rect_of(sid_v, ".btn")
cdp.mouse(sid_v, "mouseMoved", btn["x"], btn["y"], buttons=0)
time.sleep(0.7)
hover_op = cdp.ev(sid_v, JS_EFF)
check("P20 鼠标悬停时不透明度 = 100%", True, hover_op is not None and abs(float(hover_op) - 1) < 0.02, "实测=%s" % hover_op)
cdp.mouse(sid_v, "mouseMoved", 400, 700, buttons=0)      # 鼠标移开
time.sleep(2.6)
idle_op = cdp.ev(sid_v, JS_EFF)
check("P20 鼠标移开后不透明度 = 20%（延时 1 秒）", True, idle_op is not None and abs(float(idle_op) - 0.2) < 0.05, "实测=%s" % idle_op)
cdp.mouse(sid_v, "mouseMoved", btn["x"], btn["y"], buttons=0)
time.sleep(0.6)
back_op = cdp.ev(sid_v, JS_EFF)
check("P20 鼠标再移上去 → 立刻恢复 100%", True, back_op is not None and abs(float(back_op) - 1) < 0.02, "实测=%s" % back_op)

# ---------- P29 打开过菜单后移开，仍必须变暗（曾经 panelOpen 挡住定时器 → 永远 100%） ----------
store_patch(sid_con, "s.hoverOpacity=100; s.idleFade=true; s.idleOpacity=20; s.idleDelay=1")
time.sleep(0.9)
cdp.activate(tid_v)
time.sleep(0.3)
btn = rect_of(sid_v, ".btn")
cdp.mouse(sid_v, "mouseMoved", btn["x"], btn["y"], buttons=0)
time.sleep(0.4)
cdp.click(sid_v, btn["x"], btn["y"])                     # 打开菜单（关键：保持菜单开着）
time.sleep(0.5)
panel_open_now = cdp.ev(sid_v, JS_PANEL)
cdp.mouse(sid_v, "mouseMoved", 300, 700, buttons=0)       # 从按钮/菜单移开到页面
time.sleep(2.6)
op1 = cdp.ev(sid_v, JS_EFF)
check("P29 开过菜单（仍开着）后移开 → 仍会变暗", True,
      panel_open_now and op1 is not None and abs(float(op1) - 0.2) < 0.05,
      "菜单开着=%s 实测 opacity=%s" % (panel_open_now, op1))
store_patch(sid_con, "s.hoverOpacity=100; s.idleOpacity=35; s.idleDelay=3")
time.sleep(0.5)

# ---------- P22 页面菜单：滑杆上限 10× + 滑杆下方实时显示数值 ----------
open_panel(sid_v)
sl = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const s=h.shadowRoot.querySelector('.slider');"
                   "return {max:s.max,min:s.min}})()")
check("P22 页面滑杆上限 = 10×", "10", sl.get("max"), "min=%s" % sl.get("min"))
cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const s=h.shadowRoot.querySelector('.slider');"
              "s.value='2.5';s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()")
time.sleep(0.5)
check("P22 拖滑杆 → 滑杆下方数值与视频速率同步", True,
      cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');return h.shadowRoot.querySelector('.sval-num').textContent})()") == "2.5×"
      and all(abs(x - 2.5) < 0.001 for x in (cdp.ev(sid_v, JS_RATES) or [])),
      [cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');return h.shadowRoot.querySelector('.sval-num').textContent})()"),
       cdp.ev(sid_v, JS_RATES)])
cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');for(const c of h.shadowRoot.querySelectorAll('.chip')){"
              "if(c.textContent.trim()==='1.5×'){c.click();break;}}return 1})()")
time.sleep(0.4)

# ---------- P23 设置页档位区 = 真实面板布局（三列网格 + 滑杆数值） ----------
grid = cdp.ev(sid_opt, "(()=>{const g=document.getElementById('speedChips');const cs=getComputedStyle(g);"
                       "return {display:cs.display, cols:cs.gridTemplateColumns.split(' ').length, chips:g.querySelectorAll('.chip').length}})()")
check("P23 档位区=三列网格（页面菜单的真实布局）", ["grid", 3], [grid.get("display"), grid.get("cols")], "chips=%s" % grid.get("chips"))
check("P23 设置页滑杆上限 = 10×", "10", cdp.ev(sid_opt, "document.getElementById('mpSlider').max"))
cdp.ev(sid_opt, "(()=>{const s=document.getElementById('mpSlider');s.value='2';s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()")
time.sleep(0.5)
check("P23 设置页滑杆 → 数值实时显示 + 写入 storage", ["2×", 2], [
    cdp.ev(sid_opt, "document.getElementById('mpSval').textContent"),
    (store_get(sid_con) or {}).get("defaultSpeed")])
cdp.ev(sid_opt, "(()=>{const s=document.getElementById('mpSlider');s.value='1';s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()")
time.sleep(0.4)

# ---------- P24 按钮形态：任何标签长度下都必须是胶囊（宽 ≥ 高+14） ----------
def btn_geom():
    return cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                         "const r=b.getBoundingClientRect();return {w:Math.round(r.width*10)/10,h:Math.round(r.height*10)/10,"
                         "label:b.textContent.trim(),hasSvg:!!b.querySelector('svg')}})()")


cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');for(const c of h.shadowRoot.querySelectorAll('.chip')){"
              "if(c.textContent.trim()==='1×'){c.click();break;}}return 1})()")
time.sleep(0.5)
g1 = btn_geom()
check("P24 短标签「1×」下按钮是胶囊（不是正圆）", True, g1["w"] >= g1["h"] + 14,
      "label=%s %.1f×%.1f 比例=%.2f" % (g1["label"], g1["w"], g1["h"], g1["w"] / g1["h"]))
cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');for(const c of h.shadowRoot.querySelectorAll('.chip')){"
              "if(c.textContent.trim()==='1.75×'){c.click();break;}}return 1})()")
time.sleep(0.5)
g2 = btn_geom()
check("P24 长标签「1.75×」下按钮也是胶囊", True, g2["w"] >= g2["h"] + 14,
      "label=%s %.1f×%.1f 比例=%.2f" % (g2["label"], g2["w"], g2["h"], g2["w"] / g2["h"]))
store_patch(sid_con, "s.showNumber=false")
time.sleep(0.8)
g3 = btn_geom()
check("P24 关闭数字（只显示图标）时也是胶囊", True, g3["w"] >= g3["h"] + 14,
      "svg=%s %.1f×%.1f" % (g3["hasSvg"], g3["w"], g3["h"]))
store_patch(sid_con, "s.showNumber=true")
time.sleep(0.6)

# ---------- P25 尺寸 500%：等比放大 + 圆角收敛 + 乘号比例 ----------
store_patch(sid_con, "s.size=500")
time.sleep(0.9)
g5 = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                   "const r=b.getBoundingClientRect();const c=getComputedStyle(b);const x=b.querySelector('.x');"
                   "const n=b.querySelector('.n');return {w:Math.round(r.width),h:Math.round(r.height),"
                   "radius:parseFloat(c.borderRadius),fs:parseFloat(c.fontSize),"
                   "xfs:x?parseFloat(getComputedStyle(x).fontSize):0,nfs:n?parseFloat(getComputedStyle(n).fontSize):0,"
                   "cssH:getComputedStyle(h).getPropertyValue('--vsc-h').trim(),label:b.textContent.trim()}})()")
check("P25 尺寸 500% → 按钮高 = 34×5", "170px", g5["cssH"])
check("P25 尺寸 500% → 仍是胶囊（宽 ≥ 高×1.4）", True, g5["w"] >= g5["h"] * 1.4, "%.0f×%.0f" % (g5["w"], g5["h"]))
check("P25 圆角随尺寸等比收敛（< 高度一半）", True, g5["radius"] < g5["h"] / 2, "radius=%.1fpx h=%s" % (g5["radius"], g5["h"]))
check("P25 字号随尺寸等比（0.5×高度=85px）", True, abs(g5["fs"] - 170 * 0.5) < 1.5, "fs=%.1f（--vsc-h=170）" % g5["fs"])
check("P25 乘号比数字小（约 0.70em）", True, 0 < g5["xfs"] < g5["nfs"] * 0.80, "x=%.1f n=%.1f" % (g5["xfs"], g5["nfs"]))
store_patch(sid_con, "s.size=100")
time.sleep(0.8)

# ---------- P27 关闭数字再打开 → 数字必须能回来（曾经 renderButtonLabel 早退导致回不来） ----------
store_patch(sid_con, "s.showNumber=false")
time.sleep(0.8)
icon_only = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                          "return {svg:!!b.querySelector('svg'), txt:b.textContent.trim()}})()")
store_patch(sid_con, "s.showNumber=true")
time.sleep(0.9)
back_num = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                         "return {svg:!!b.querySelector('svg'), txt:b.textContent.trim(), x:!!b.querySelector('.x')}})()")
check("P27 关闭数字 → 只显示图标", [True, ""], [icon_only["svg"], icon_only["txt"]])
check("P27 再打开数字 → 数字/乘号结构恢复（不是空白）", True,
      back_num["txt"] != "" and back_num["x"] and not back_num["svg"], back_num)

# ---------- P26 1× 也是合法记忆值：记录、显示、都能恢复 ----------
# v1.0.5 改了规则：1× 不再被当作「取消记忆」，所以旧断言（1× 不显示/不记录）已随新行为更新
store_patch(sid_con, "s.siteSpeeds={'a.com':1.25,'b.com':1,'c.com':2}")
time.sleep(0.5)
cdp.send("Page.reload", session=sid_opt)
time.sleep(1.8)
lst = cdp.ev(sid_opt, "Array.from(document.querySelectorAll('#rateList .li')).map(e=>e.textContent.trim().slice(0,24))")
check("P26 清单显示全部记录（含 1×）", True,
      any("a.com" in x for x in lst) and any("c.com" in x for x in lst) and any("b.com" in x for x in lst), lst)
store_patch(sid_con, "s.siteSpeeds={'127.0.0.1':2}")
time.sleep(0.6)
cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');for(const c of h.shadowRoot.querySelectorAll('.chip')){"
              "if(c.textContent.trim()==='1×'){c.click();break;}}return 1})()")
time.sleep(0.7)
sp26 = (store_get(sid_con) or {}).get("siteSpeeds", {})
check("P26 在页面设 1× → 记录保留为 1（不再被删除）", 1.0, sp26.get("127.0.0.1"), sp26)

# ---------- P28 圆角可调（0 / 42 / 50 / 80） ----------
rad = {}
for v in (0, 42, 50, 80):
    store_patch(sid_con, "s.radius=%d" % v)
    time.sleep(0.8)
    rad[v] = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const b=h.shadowRoot.querySelector('.btn');"
                           "return {radius:parseFloat(getComputedStyle(b).borderRadius),"
                           "cssH:parseFloat(getComputedStyle(h).getPropertyValue('--vsc-h'))}})()")
check("P28 圆角 0% → 直角", True, rad[0]["radius"] == 0, rad[0])
check("P28 圆角 42% ≈ 高度×0.42（默认值）", True, abs(rad[42]["radius"] - rad[42]["cssH"] * 0.42) < 1, rad[42])
check("P28 圆角 50% = 全圆角（高度一半）", True, abs(rad[50]["radius"] - rad[50]["cssH"] / 2) < 1, rad[50])
check("P28 圆角 80% → 被浏览器收敛为完全胶囊（≥ 高度一半）", True, rad[80]["radius"] >= rad[80]["cssH"] / 2 - 1, rad[80])
check("P28 设置页有圆角滑杆（0–80）", ["0", "80"], [
    cdp.ev(sid_opt, "document.getElementById('radius').min"),
    cdp.ev(sid_opt, "document.getElementById('radius').max")])
store_patch(sid_con, "s.radius=42")
time.sleep(0.5)

# ---------- P30 不透明度必须量「生效值」（逐级相乘），不能只看单个节点 ----------
store_patch(sid_con, "s.hoverOpacity=60; s.idleFade=true; s.idleOpacity=40; s.idleDelay=1")
time.sleep(0.9)
cdp.activate(tid_v)
time.sleep(0.3)
btn = rect_of(sid_v, ".btn")
cdp.mouse(sid_v, "mouseMoved", btn["x"], btn["y"], buttons=0)
time.sleep(0.7)
hov30 = cdp.ev(sid_v, JS_EFF)
cdp.mouse(sid_v, "mouseMoved", 300, 700, buttons=0)
time.sleep(2.6)
idl30 = cdp.ev(sid_v, JS_EFF)
check("P30 悬停时生效不透明度 = 60%（不再相乘）", True, abs(float(hov30) - 0.6) < 0.03, hov30)
check("P30 移开后生效不透明度 = 40%（不再相乘）", True, abs(float(idl30) - 0.4) < 0.03, idl30)
# 复现旧 bug：再给 .wrap 加一层 opacity → 生效值立刻变成两者相乘
cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');const s=document.createElement('style');"
              "s.id='vsc-repro';s.textContent='.wrap{opacity:var(--vsc-op-hover) !important}';"
              "h.shadowRoot.appendChild(s);return 1})()")
time.sleep(0.5)
rep = cdp.ev(sid_v, JS_EFF)
check("P30 复现旧 bug（.wrap 再加 opacity）→ 生效值 = 0.4×0.6 = 0.24", True, abs(float(rep) - 0.24) < 0.03, rep)
cdp.ev(sid_v, "(()=>{const s=document.querySelector('[data-vsc]').shadowRoot.getElementById('vsc-repro');"
              "if(s)s.remove();return 1})()")
time.sleep(0.4)
store_patch(sid_con, "s.hoverOpacity=100; s.idleOpacity=35; s.idleDelay=3")
time.sleep(0.5)

# ---------- P31 菜单面板始终 100% 不透明（不跟按钮一起变淡） ----------
store_patch(sid_con, "s.hoverOpacity=20; s.idleFade=true; s.idleOpacity=20; s.idleDelay=1")
time.sleep(0.9)
cdp.activate(tid_v)
time.sleep(0.3)
open_panel(sid_v)
time.sleep(0.4)
cdp.mouse(sid_v, "mouseMoved", 300, 700, buttons=0)      # 鼠标移开（菜单保持开着）
time.sleep(2.6)
JS_EFF2 = """(()=>{const h=document.querySelector('[data-vsc]');const sh=h.shadowRoot;
const f=(el)=>{let op=1,n=el;while(n&&n!==h){if(n.nodeType===1){op*=parseFloat(getComputedStyle(n).opacity||1);}n=n.parentNode||n.host||null;}return Math.round(op*1000)/1000};
return {btn:f(sh.querySelector('.btn')),panel:f(sh.querySelector('.panel')),panelOpen:sh.querySelector('.panel').classList.contains('open')}})()"""
r31 = cdp.ev(sid_v, JS_EFF2)
check("P31 按钮按设置变淡到 20%", True, abs(r31["btn"] - 0.2) < 0.03, r31)
check("P31 菜单面板始终 100% 不透明", True, abs(r31["panel"] - 1.0) < 0.02, r31)
store_patch(sid_con, "s.hoverOpacity=100; s.idleOpacity=35; s.idleDelay=3")
time.sleep(0.5)

# ---------- P18 设置页截图 + 汇总 ----------
cdp.shot(sid_opt, os.path.join(OUT, "shot_options.png"))

# ---------- P21 面板「设置」按钮 → 必须走后台 openOptionsPage（曾被 ERR_BLOCKED_BY_CLIENT 拦） ----------
for t in cdp.targets():
    if "options.html" in (t.get("url") or ""):
        cdp.send("Target.closeTarget", {"targetId": t["targetId"]})
time.sleep(1.0)
cdp.activate(tid_v)
time.sleep(0.3)
open_panel(sid_v)
setbtn = cdp.ev(sid_v, "(()=>{const h=document.querySelector('[data-vsc]');"
                       "for(const b of h.shadowRoot.querySelectorAll('.act')){if(b.textContent.trim()==='设置'){"
                       "const r=b.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}}}return null})()")
opened = 0
if setbtn:
    cdp.click(sid_v, setbtn["x"], setbtn["y"])
    time.sleep(2.0)
    opened = len([t for t in cdp.targets() if "options.html" in (t.get("url") or "")])
check("P21 面板「设置」→ 打开设置页（后台 openOptionsPage）", True, opened >= 1, "新开的设置页数=%s" % opened)

fails = [r for r in results if not r["pass"]]
print("\n=== 汇总：%d 项，通过 %d，失败 %d ===" % (len(results), len(results) - len(fails), len(fails)))
for r in fails:
    print("  FAIL %s expect=%s actual=%s" % (r["case"], r["expected"], r["actual"]))
with open(os.path.join(OUT, "vsc_local_results.json"), "w", encoding="utf-8") as f:
    json.dump({"ext_id": ext_id, "total": len(results), "fail": len(fails), "results": results},
              f, ensure_ascii=False, indent=2)
print("结果已写入 vsc_local_results.json")
