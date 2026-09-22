# -*- coding: utf-8 -*-
"""打包上架包：store/video-speed-<版本>.zip

规则（与手动上架一致）：
  · manifest.json 必须在 zip 根层
  · 只含扩展运行必需文件（不含 README/tools/tests/store）
  · 打完打印文件清单 + 大小 + sha256，便于核对
用法：python3 tools/build_zip.py
"""
import hashlib
import json
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "store")

FILES = [
    "manifest.json",
    "shared.js",
    "content.js",
    "background.js",
    "options.html",
    "options.css",
    "options.js",
    "popup.html",
    "popup.css",
    "popup.js",
    "icons/icon16.png",
    "icons/icon32.png",
    "icons/icon48.png",
    "icons/icon128.png",
    "_locales/zh_CN/messages.json",
    "_locales/en/messages.json",
]


def main():
    ver = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))["version"]
    out = os.path.join(STORE, "video-speed-%s.zip" % ver)
    missing = [f for f in FILES if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        raise SystemExit("缺少文件：%s" % missing)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(ROOT, f), f)
    data = open(out, "rb").read()
    print("版本        : %s" % ver)
    print("输出        : %s" % out)
    print("文件数      : %d" % len(FILES))
    print("大小        : %d 字节" % len(data))
    print("sha256      : %s" % hashlib.sha256(data).hexdigest())
    with zipfile.ZipFile(out) as z:
        print("zip 根层含 manifest.json: %s" % ("manifest.json" in z.namelist()))
        bad = [n for n in z.namelist() if n.startswith("/") or ".." in n]
        print("非法路径    : %s" % (bad or "无"))


if __name__ == "__main__":
    main()
