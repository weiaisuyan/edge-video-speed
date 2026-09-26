# -*- coding: utf-8 -*-
"""v1.0.5 记忆功能回归 —— 修复后的完整验收

覆盖：
  A 你反馈的真实 bug：设 1.75× → 点一下视频 → 站点重置为 1× → 必须抢回且记忆不被改
  B 换素材宽限期：load() 后站点立即设 1× → 必须抢回且记忆不被改（这条以前从没被测到）
  C 用站点自带播放器调速 → 必须被采纳（v1.0.5 中途曾因类名写错而失效）
  D 用调速快捷键 → 必须被采纳（v1.0.5 中途曾失效）
  E 手动设 1× → 必须被记住（不再被当成「取消记忆」）
  F F5 重进 → 记忆生效

全程静音：不调用 play()，测试页 muted+volume0，媒体文件无音轨，独立测试 profile。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

from cdp import CDP, ext_id_for  # noqa: E402

PORT = 9222
PAGE = "http://127.0.0.1:8731/vsc_test_memory.html"
EXT = ext_id_for("E:\\程序\\edge-video-speed")
G = 0.85   # 宽限期外等待（SITE_LOAD_GRACE=2000ms）

results = []


def check(name, expect, actual):
    ok = (expect == actual)
    results.append((ok, name, expect, actual))
    print("%s  %-52s 期望=%-10s 实测=%s" % ("PASS" if ok else "FAIL", name, expect, actual))
    return ok


def main():
    c = CDP(PORT)
    print("扩展 ID:", EXT)

    # ---------- 准备：写入「该站记忆=1.75」 ----------
    tid_o, sid_o = c.open("chrome-extension://%s/options.html" % EXT, wait=1.6)

    def store_get():
        return c.ev(sid_o, "new Promise(r=>chrome.storage.local.get('settings',o=>r(o.settings||{})))")

    def set_record(v):
        c.ev(sid_o, "new Promise(r=>chrome.storage.local.get('settings',o=>{"
                    "var s=o.settings||{};s.siteSpeeds=s.siteSpeeds||{};"
                    "s.siteSpeeds['127.0.0.1']=%s;chrome.storage.local.set({settings:s},()=>r(1))}))" % v)
        time.sleep(0.4)

    c.ev(sid_o, "new Promise(r=>chrome.storage.local.clear(()=>r(1)))")
    time.sleep(0.4)
    set_record(1.75)
    sp = store_get().get("siteSpeeds", {})
    print("准备完成：siteSpeeds =", json.dumps(sp, ensure_ascii=False))

    # ---------- 打开测试页 ----------
    tid, sid = c.open(PAGE, wait=2.2)
    c.activate(tid)
    time.sleep(3.0)          # 等页面自加载的 markLoad 宽限期(2s)过期
    c.ev(sid, "__vscT.silence()")

    n = c.ev(sid, "document.querySelectorAll('[data-vsc]').length")
    rs = c.ev(sid, "document.getElementById('v').readyState")
    print("扩展注入元素数:", n, " video.readyState:", rs)
    if not n:
        print("!! 扩展未注入，无法测")
        return 1
    if rs is None or rs < 1:
        print("!! 媒体元数据没加载（readyState=%s）——宽限期测不到，先修测试页" % rs)
        return 1

    def rate():
        return c.ev(sid, "document.getElementById('v').playbackRate")

    def btn():
        return c.ev(sid, "window.__vscT.btnText()")

    def rec():
        return store_get().get("siteSpeeds", {}).get("127.0.0.1")

    # ---------- 基线 ----------
    print("\n=== 基线：进入页面应自动套用记忆的 1.75× ===")
    check("基线 video=1.75×", 1.75, rate())
    check("基线 按钮=1.75×", "1.75×", btn())
    check("基线 记录仍是 1.75", 1.75, rec())

    # ---------- A 你反馈的真实 bug ----------
    print("\n=== A 点一下视频（播放/暂停，不改速度）→ 1.5s 后站点重置为 1× ===")
    c.ev(sid, "__vscT.tapVideo()")
    time.sleep(1.5)
    c.ev(sid, "__vscT.siteReset()")
    time.sleep(G)
    check("A 速度被抢回 1.75×", 1.75, rate())
    check("A 记忆未被改成 1（核心）", 1.75, rec())
    check("A 按钮仍显示 1.75×", "1.75×", btn())

    # ---------- B 换素材宽限期（以前从没测到）----------
    print("\n=== B 换素材（load()）后站点立即设 1× → 宽限期应拦住 ===")
    c.ev(sid, "__vscT.reloadMedia()")
    time.sleep(0.30)                       # 卡在 SITE_LOAD_GRACE(2s) 内
    c.ev(sid, "__vscT.siteReset()")
    time.sleep(G)
    check("B 速度被抢回 1.75×", 1.75, rate())
    check("B 记忆未被改成 1", 1.75, rec())

    # ---------- C 站点自带播放器调速仍要被采纳 ----------
    print("\n=== C 在播放器上点一下 + 改速度 → 应被采纳 ===")
    time.sleep(2.3)                        # 先让宽限期彻底过期
    c.ev(sid, "__vscT.manualClick(2)")
    time.sleep(G)
    check("C 采纳为 2×", 2, rate())
    check("C 记忆写入 2", 2, rec())

    # ---------- D 调速快捷键仍要被采纳 ----------
    print("\n=== D 按调速快捷键 '>' + 改速度 → 应被采纳 ===")
    c.ev(sid, "__vscT.manualKey(3, '>')")
    time.sleep(G)
    check("D 采纳为 3×", 3, rate())
    check("D 记忆写入 3", 3, rec())

    # ---------- E 手动设 1× 要被记住 ----------
    print("\n=== E 在播放器上调回 1× → 应被记住（不再当成取消记忆）===")
    c.ev(sid, "__vscT.manualClick(1)")
    time.sleep(G)
    check("E 采纳为 1×", 1, rate())
    check("E 记忆写入 1（不是删除）", 1.0, rec())

    # ---------- F F5 后记忆仍生效 ----------
    print("\n=== F F5 重进 → 记忆应生效 ===")
    c.send("Page.reload", {}, session=sid)
    time.sleep(3.0)
    c.ev(sid, "__vscT.silence()")
    check("F 重进后按钮=1×", "1×", btn())
    check("F 重进后记录仍是 1", 1.0, rec())

    # ---------- 事件时间线（诊断用） ----------
    print("\n=== 事件时间线 ===")
    try:
        for e in json.loads(c.ev(sid, "JSON.stringify(window.__vscT.log)"))[:18]:
            print("  %-46s rate=%s 按钮=%s readyState=%s" % (e["tag"], e["rate"], e["btn"], e["readyState"]))
    except Exception as ex:
        print("  （读取失败：%s）" % ex)

    print("\n=== 汇总 ===")
    p = sum(1 for ok, _, _, _ in results if ok)
    print("通过 %d / %d" % (p, len(results)))
    for ok, name, e, a in results:
        if not ok:
            print("  FAIL: %s 期望=%s 实测=%s" % (name, e, a))
    c.send("Target.closeTarget", {"targetId": tid_o})
    c.close()
    return 0 if p == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(2)
