# -*- coding: utf-8 -*-
"""诊断 options 页加载状态"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP, ext_id_for  # noqa: E402

cdp = CDP(int(os.environ.get("VSC_PORT", "9224")))
eid = ext_id_for("E:\\程序\\edge-video-speed")
print("targets:")
for t in cdp.targets():
    print("  ", t.get("type"), "|", (t.get("url") or "")[:110])

tid, sid = cdp.open("chrome-extension://%s/options.html" % eid, wait=3.0)
cdp.activate(tid)
print("url:", cdp.ev(sid, "location.href"))
print("readyState:", cdp.ev(sid, "document.readyState"))
print("hasSpeedChips:", cdp.ev(sid, "!!document.getElementById('speedChips')"))
print("title:", cdp.ev(sid, "document.title"))
print("bodyHead:", cdp.ev(sid, "(document.body?document.body.innerHTML.slice(0,300):'NO BODY')"))
print("shared:", cdp.ev(sid, "typeof window.VSC_SHARED"))
print("errs:", cdp.ev(sid, "window.__errs||null"))
