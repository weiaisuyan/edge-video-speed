#!/usr/bin/env bash
# 在用户真实浏览器里量「B站页面上的按钮」几何（走 opencli 桥；后台窗口；不用 history.back）
export OPENCLI_BROWSER_COMMAND_TIMEOUT=90
oc() { opencli browser vsc "$@" 2>&1 | grep -v -e UNDICI -e trace-warnings; }
ev() { oc eval "$1"; }

JS_BTN='(()=>{const h=document.querySelector("[data-vsc]");if(!h)return "no-host";
const b=h.shadowRoot.querySelector(".btn");const r=b.getBoundingClientRect();const c=getComputedStyle(b);
return JSON.stringify({label:b.textContent.trim(),w:Math.round(r.width*10)/10,h:Math.round(r.height*10)/10,
ratio:Math.round(r.width/r.height*100)/100,radius:c.borderRadius,padding:c.padding,minW:c.minWidth,
fontSize:c.fontSize,boxSizing:c.boxSizing,hasSvg:!!b.querySelector("svg"),visible:h.style.display!=="none"})})()'

echo "=== 打开 B站视频页（你登录态，后台窗口）==="
oc open "https://www.bilibili.com/video/BV1GJ411x7h7" --window background >/dev/null
sleep 10
echo "按钮几何: $(ev "$JS_BTN")"
echo
echo "=== 对比：同一按钮在 YouTube 上（标签更长时的形态）==="
oc open "https://www.youtube.com/watch?v=aqz-KE-bpKQ" --window background >/dev/null
sleep 10
echo "按钮几何: $(ev "$JS_BTN")"
oc close >/dev/null 2>&1
echo done
