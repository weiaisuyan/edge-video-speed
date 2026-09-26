#!/usr/bin/env bash
# 一键跑全部自动化测试（后台静默：headless Edge + 静音；自带 http 服务，跑完自清理）
#
#   bash tests/run_all_tests.sh
#
# 依赖：系统 Python 3.12（带 websockets）。
# 说明：http 服务与浏览器进程都由本脚本自己起、自己收——不要依赖外部常驻进程，
#       它们可能被上层的生命周期清理杀掉，表现为「页面加载不到脚本」。
set -u

HERE="E:/程序/edge-video-speed/tests"
PY="C:/Users/weiai/AppData/Local/Programs/Python/Python312/python.exe"
# 注意：HERE 必须是原生 Windows 风格（E:/...）。git-bash 的 pwd 给出 /e/...，
# 直接传给原生 python 会被错误转换（实测变成 E:\e\程序\... 打不开文件）。

cleanup() {
  [ -n "${SRV1:-}" ] && kill "$SRV1" 2>/dev/null
  [ -n "${SRV2:-}" ] && kill "$SRV2" 2>/dev/null
}
trap cleanup EXIT

echo "### 启动内置 http 服务（多线程）"
"$PY" -u "$HERE/serve.py" 8731 >/dev/null 2>&1 &
SRV1=$!
"$PY" -u "$HERE/serve.py" 8782 >/dev/null 2>&1 &
SRV2=$!
sleep 3

echo
echo "### 记忆专项测试（端口 9222）"
bash "$HERE/launch_test_edge.sh" 9222 | tail -1
sleep 2
"$PY" -u "$HERE/probe_memory.py" > "$TMPDIR/probe_memory.log" 2>&1
R1=$?
tail -3 "$TMPDIR/probe_memory.log"
grep -E "^FAIL" "$TMPDIR/probe_memory.log" || echo "  无失败"

echo
echo "### 全量回归测试（端口 9223）"
bash "$HERE/launch_test_edge.sh" 9223 | tail -1
sleep 2
"$PY" -u "$HERE/probe_local.py" > "$TMPDIR/probe_local.log" 2>&1
R2=$?
tail -3 "$TMPDIR/probe_local.log"
grep -E "^FAIL" "$TMPDIR/probe_local.log" || echo "  无失败"

echo
echo "### 汇总：记忆专项 exit=$R1  全量回归 exit=$R2（0 = 全绿）"
exit $(( R1 + R2 ))
