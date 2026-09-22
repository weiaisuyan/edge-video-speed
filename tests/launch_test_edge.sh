#!/usr/bin/env bash
# 起专用测试浏览器（不碰用户日常 Edge）；可选随后跑测量或全量回归
# 用法：bash launch_test_edge.sh measure [before|after]   |   bash launch_test_edge.sh tests
set -u
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$T/vsc_auto_edge"

powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_auto_edge*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { taskkill /PID \$_ /F | Out-Null }" >/dev/null 2>&1
sleep 2

"$EDGE" --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir="$PROFILE" --load-extension='E:/程序/edge-video-speed' \
  --mute-audio --no-first-run --no-default-browser-check \
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
[ "$code" != "200" ] && { echo "CDP 未就绪"; exit 1; }

cd "$T" || exit 1
case "${1:-measure}" in
  measure) python3 -u measure_switch.py "${2:-current}" ;;
  tests)   python3 -u probe_local.py ;;
  *)       echo "未知模式 $1" ;;
esac
