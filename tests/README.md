# tests · 自动化验证（真实 Edge + CDP 合成事件）

全部测试都跑在**专用测试浏览器**上（独立 profile，绝不碰日常浏览器），
断言取的是运行时 DOM / 像素数据，不看截图猜。

## 起测试环境

```bash
# 1) 静态服务器（服务本目录的测试页 + sample.mp4）
cd tests && python3 -m http.server 8782 --bind 127.0.0.1

# 2) 专用测试浏览器（加载未打包扩展）
msedge.exe --remote-debugging-port=9223 --remote-allow-origins=* \
  --user-data-dir=<任意临时目录> --load-extension=<本仓库根目录> \
  --no-first-run --no-default-browser-check \
  --disable-background-timer-throttling --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding --disable-features=CalculateNativeWinOcclusion \
  --window-size=1280,860 --window-position=180,60 about:blank
```

## 探针

| 脚本 | 作用 | 断言数 |
|---|---|---|
| `probe_local.py` | 全量回归：设置页渲染/交互、速度施加、面板、滑块、按钮几何、圆角、不透明度（含「逐级相乘」这类叠加 bug）、备份导入导出、原生全屏 | 92 |
| `probe_fullscreen.py` | 全屏专项：原生全屏（容器 / video / 整个 html）、网页伪全屏（铺满 / 信箱化 / 不够大的对照）、浏览器窗口全屏（真实 windowState=fullscreen）、全屏中改设置 | 31 |
| `probe_bili_fullscreen.py` | 真实站点（B站）网页全屏 / 原生全屏的 DOM 形态与按钮行为 | — |
| `probe_popover.py` | 实验：顶层 popover 能否渲染在全屏 `<video>` 之上 | — |
| `probe_app_site.py` / `probe_yt.py` | 应用窗口形态 + 真实站点（需要登录态，用日常浏览器跑） | — |
| `shots_options.py` | 重拍商店设置页截图（screenshot-3/4），拍前核对版本号 | — |

## 关键判据

- **像素级可见性**：裁剪按钮所在矩形，统计与按钮底色接近的像素数。
  只看 `style.display` 会得出「状态对了但用户照样看得见」的错误结论——
  原生全屏元素是 `<video>`/整个 `<html>` 时，按钮往往仍然被画出来。
- 几何结论一律取 `getBoundingClientRect()`，不靠看图。
- 改完扩展代码必须**重启测试浏览器**（`--load-extension` 的 content script 不会热更新）。
