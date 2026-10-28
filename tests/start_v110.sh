#!/usr/bin/env bash
# 只起浏览器 + http 服务（不跑探针、不清理），供交互调试用
#   bash tests/start_v110.sh [port] [httpport]
set -u
PORT="${1:-9224}"
HTTP_PORT="${2:-8784}"
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
PROFILE="$T/vsc_v110"
EXT_ASCII="$T/vsc_ext"
EXT_SRC="E:/程序/edge-video-speed"
EDGE="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
TESTS="E:/程序/edge-video-speed/tests"
mkdir -p "$T"

# 干净 ASCII 副本：中文路径经 PowerShell 传参会被截断 → 扩展根本加载不了
rm -rf "$EXT_ASCII"; mkdir -p "$EXT_ASCII"
cp -r "$EXT_SRC/manifest.json" "$EXT_SRC/background.js" "$EXT_SRC/content.js" "$EXT_SRC/shared.js" \
      "$EXT_SRC/options.html" "$EXT_SRC/options.css" "$EXT_SRC/options.js" \
      "$EXT_SRC/popup.html" "$EXT_SRC/popup.css" "$EXT_SRC/popup.js" \
      "$EXT_SRC/icons" "$EXT_SRC/_locales" "$EXT_ASCII/"
echo "ext_copy at $EXT_ASCII ($(ls -1 "$EXT_ASCII" | wc -l) entries)"

powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_v110*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*serve.py*$HTTP_PORT*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
sleep 1

python3 "$TESTS/serve.py" "$HTTP_PORT" >/dev/null 2>&1 &

powershell -NoProfile -Command "
\$a=@(
 '--headless=new',
 '--remote-debugging-port=$PORT','--remote-allow-origins=*',
 '--user-data-dir=$PROFILE','--load-extension=$EXT_ASCII',
 '--disable-sync','--disable-component-update',
 '--mute-audio','--no-first-run','--no-default-browser-check',
 '--disable-background-timer-throttling','--disable-backgrounding-occluded-windows',
 '--disable-renderer-backgrounding',
 '--disable-features=DisableLoadExtensionCommandLineSwitch,CalculateNativeWinOcclusion',
 '--window-size=1280,900',
 'about:blank')
Start-Process -FilePath '$EDGE' -ArgumentList \$a -WindowStyle Hidden
" >/dev/null 2>&1

code=000
for i in $(seq 1 40); do
  for h in "127.0.0.1" "[::1]"; do
    code=$(curl -s --noproxy '*' -m 2 -o /dev/null -w "%{http_code}" "http://$h:$PORT/json/version")
    [ "$code" = "200" ] && break
  done
  [ "$code" = "200" ] && break
  sleep 1
done
echo "cdp_ready=$code port=$PORT http=$HTTP_PORT"
