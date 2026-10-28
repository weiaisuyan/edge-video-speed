#!/usr/bin/env bash
# v1.1.0 回归：起后台静默测试浏览器（headless + 静音）+ 本地 http 服务，跑 probe_v110.py
#   铁律：headless（不弹窗）、--mute-audio、只碰 vsc_test profile、杀进程按 profile 过滤
#   ⚠️ 扩展先复制到 ASCII 路径再 --load-extension：中文路径经 PowerShell 传参会被截断成
#      E:/????/e（实测扩展根本没加载，表现为 options 页「已阻止 <id>」）——ASCII 副本才稳。
set -u
PORT="${VSC_PORT:-9224}"
HTTP_PORT="${VSC_HTTP_PORT:-8784}"
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
PROFILE="$T/vsc_v110"
EXT_SRC="E:/程序/edge-video-speed"
EXT_ASCII="$T/vsc_ext"
EDGE="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
TESTS="E:/程序/edge-video-speed/tests"

mkdir -p "$T"

# 只杀本测试 profile 的 Edge（绝不按进程名杀）
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_v110*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
# 收掉旧的 http 服务
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*serve.py*$HTTP_PORT*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
sleep 1

# 干净 ASCII 副本（不带 tests/store/tools/.git）
rm -rf "$EXT_ASCII"
mkdir -p "$EXT_ASCII"
cp -r "$EXT_SRC/manifest.json" "$EXT_SRC/background.js" "$EXT_SRC/content.js" "$EXT_SRC/shared.js" \
      "$EXT_SRC/options.html" "$EXT_SRC/options.css" "$EXT_SRC/options.js" \
      "$EXT_SRC/popup.html" "$EXT_SRC/popup.css" "$EXT_SRC/popup.js" \
      "$EXT_SRC/icons" "$EXT_SRC/_locales" "$EXT_ASCII/"
echo "ext_copy_entries=$(ls -1 "$EXT_ASCII" | wc -l) at $EXT_ASCII"

python3 "$TESTS/serve.py" "$HTTP_PORT" >/dev/null 2>&1 &
SRV=$!

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
if [ "$code" != "200" ]; then kill $SRV 2>/dev/null; exit 1; fi

cd "$TESTS" || exit 1
VSC_PORT="$PORT" VSC_HTTP_PORT="$HTTP_PORT" VSC_EXT_PATH="$EXT_ASCII" python3 -u probe_v110.py
RC=$?
echo "PROBE_EXIT=$RC"

kill $SRV 2>/dev/null
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_v110*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
exit $RC
