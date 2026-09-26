#!/usr/bin/env bash
# 起「后台静默」测试浏览器（headless，不弹窗口），供自动化测试用。
#
#   bash launch_test_edge.sh [端口]        # 默认 9222
#
# 铁律（用户反复强调，违反按事故处理）：
#   1. 一律后台静默：--headless=new，屏幕上不应出现任何窗口
#   2. 必须静音：--mute-audio + profile sound=2 + 测试不调 play()
#   3. 只碰本测试 profile；杀进程必须按 profile 过滤，绝不按进程名杀
#      （按进程名杀会连用户正在用的 Edge 一起杀掉）
#   4. 独立 profile 必须干净 + 禁同步：否则 Edge 账号同步会把用户全部商店扩展
#      灌进来（实测 47 个），其中一个卡死页面主线程 → 所有 CDP 调用超时，
#      看起来像「扩展写挂了」，极难排查
#   5. headless 模式下 Edge 只监听 IPv6 回环 [::1]，探测端口要试两个地址
set -u
PORT="${1:-9222}"

# 只清理本测试 profile 的实例
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*vsc_test*' } | Select-Object -ExpandProperty ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
sleep 2

# 经 PowerShell 传参：git-bash 直传中文路径给原生程序会变成乱码 E:/???/...
powershell -NoProfile -Command "
\$edge='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
\$prof='C:\Users\weiai\AppData\Local\hermes\cache\scratch\vsc_test\vsc_clean'
\$ext='E:\程序\edge-video-speed'
\$a=@(
 '--headless=new',
 '--remote-debugging-port=$PORT','--remote-allow-origins=*',
 \"--user-data-dir=\$prof\", \"--load-extension=\$ext\",
 '--disable-sync','--disable-component-update',
 '--mute-audio','--no-first-run','--no-default-browser-check',
 '--disable-background-timer-throttling','--disable-backgrounding-occluded-windows',
 '--disable-renderer-backgrounding','--disable-features=CalculateNativeWinOcclusion',
 'about:blank')
Start-Process -FilePath \$edge -ArgumentList \$a -WindowStyle Hidden
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
echo "cdp_ready=$code port=$PORT mode=headless"
[ "$code" != "200" ] && exit 1
exit 0
