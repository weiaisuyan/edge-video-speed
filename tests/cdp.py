# -*- coding: utf-8 -*-
"""极简 CDP 客户端（websockets sync）——本机自动化测试用"""
import json
import os
import time
import urllib.request

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

from websockets.sync.client import connect  # noqa: E402


def http_json(port, path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (port, path), timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


class CDP:
    def __init__(self, port=9222):
        self.port = port
        v = http_json(port, "/json/version")
        self.browser_ws = v["webSocketDebuggerUrl"]
        self.ws = connect(self.browser_ws, max_size=64 * 1024 * 1024, proxy=None)
        self.n = 0
        self.events = []

    def send(self, method, params=None, session=None, timeout=20):
        self.n += 1
        mid = self.n
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        end = time.time() + timeout
        while time.time() < end:
            try:
                raw = self.ws.recv(timeout=max(0.2, end - time.time()))
            except TimeoutError:
                break
            m = json.loads(raw)
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError("%s -> %s" % (method, m["error"]))
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)
        raise TimeoutError(method)

    def targets(self):
        return self.send("Target.getTargets")["targetInfos"]

    def find(self, needle, kind="page"):
        for t in self.targets():
            if kind and t.get("type") != kind:
                continue
            if needle in (t.get("url") or ""):
                return t
        return None

    def attach(self, target_id):
        return self.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})["sessionId"]

    def open(self, url, wait=1.6):
        r = self.send("Target.createTarget", {"url": url})
        tid = r["targetId"]
        sid = self.attach(tid)
        self.send("Runtime.enable", session=sid)
        self.send("Page.enable", session=sid)
        time.sleep(wait)
        return tid, sid

    def ev(self, session, expr, await_promise=True, user_gesture=False, timeout=20):
        r = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": user_gesture,
        }, session=session, timeout=timeout)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            txt = d.get("exception", {}).get("description") or d.get("text")
            raise RuntimeError("JS error: %s" % txt)
        return r.get("result", {}).get("value")

    def activate(self, target_id):
        return self.send("Target.activateTarget", {"targetId": target_id})

    def mouse(self, session, kind, x, y, button="left", buttons=1, clicks=1, modifiers=0):
        self.send("Input.dispatchMouseEvent", {
            "type": kind, "x": x, "y": y, "button": button,
            "buttons": buttons, "clickCount": clicks, "modifiers": modifiers,
        }, session=session)

    def drag(self, session, x1, y1, x2, y2, steps=12, modifiers=0):
        self.mouse(session, "mousePressed", x1, y1, modifiers=modifiers)
        for i in range(1, steps + 1):
            self.mouse(session, "mouseMoved", x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps,
                       modifiers=modifiers)
            time.sleep(0.02)
        self.mouse(session, "mouseReleased", x2, y2, buttons=0, modifiers=modifiers)

    def click(self, session, x, y, modifiers=0):
        self.mouse(session, "mousePressed", x, y, modifiers=modifiers)
        time.sleep(0.05)
        self.mouse(session, "mouseReleased", x, y, buttons=0, modifiers=modifiers)
        time.sleep(0.25)

    def key(self, session, key, code, modifiers=0):
        for kind in ("keyDown", "keyUp", "char"):
            if kind == "char" and len(key) != 1:
                continue
            self.send("Input.dispatchKeyEvent", {
                "type": kind, "key": key, "code": code, "modifiers": modifiers,
                "text": key if kind == "char" else "",
            }, session=session)

    def shot(self, session, path):
        r = self.send("Page.captureScreenshot", {"format": "png"}, session=session, timeout=30)
        import base64
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def ext_id_for(path):
    """--load-extension 的扩展 ID = sha256(路径 UTF-16LE) 前 16 字节 → hex → 0-f 映射到 a-p"""
    import hashlib
    h = hashlib.sha256(path.encode("utf-16-le")).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in h)
