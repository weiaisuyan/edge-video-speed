#!/usr/bin/env bash
# 重跑本地测试：重启专用测试浏览器 → 等 CDP 就绪 → 跑探针
set -u
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$T/vsc_auto_edge"

# 只杀专用测试 profile 的 Edge（按命令行过滤，绝不碰日常 Edge）
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_auto_edge*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { taskkill /PID \$_ /F | Out-Null }" >/dev/null 2>&1
sleep 2

"$EDGE" --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir="$PROFILE" --load-extension='E:/程序/edge-video-speed' \
  --no-first-run --no-default-browser-check \
  --disable-background-timer-throttling --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding --disable-features=CalculateNativeWinOcclusion \
  --window-size=1280,860 --window-position=180,60 about:blank >/dev/null 2>&1 &

code=000
for i in $(seq 1 30); do
  code=$(curl -s --noproxy '*' -m 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:9222/json/version)
  if [ "$code" = "200" ]; then break; fi
  sleep 1
done
echo "cdp_ready=$code"
if [ "$code" != "200" ]; then echo "CDP 未就绪，退出"; exit 1; fi

cd "$T" || exit 1
python3 -u probe_local.py
echo "PROBE_EXIT=$?"
