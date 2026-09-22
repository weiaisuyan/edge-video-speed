#!/usr/bin/env bash
# 登录态真实站点验证（走 opencli 桥，操作用户真实浏览器；后台窗口）
# 注意：扩展按钮监听的是 pointerdown/pointerup，程序化 .click() 无效 → 用合成 PointerEvent
export OPENCLI_BROWSER_COMMAND_TIMEOUT=90
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
oc() { opencli browser vsc "$@" 2>&1 | grep -v -e UNDICI -e trace-warnings; }
ev() { oc eval "$1"; }

JS_STATE='(()=>{const h=document.querySelector("[data-vsc]");const t=(document.body.innerText||"").slice(0,900);return JSON.stringify({title:(document.title||"").slice(0,40),url:location.href.slice(0,70),wall:/扫码登录|手机号登录|登录后查看|请登录|Sign in to confirm/.test(t),videos:document.querySelectorAll("video").length,ext:!!h,visible:h?h.style.display!=="none":null,btn:h?h.shadowRoot.querySelector(".btn").textContent.trim():null,rates:Array.from(document.querySelectorAll("video")).map(v=>v.playbackRate)})})()'
JS_NOTE='(()=>{const i=window.__vsc_i||0;const as=[...document.querySelectorAll("a[href*=\"/explore/\"]")].filter(a=>/\/explore\/[0-9a-f]{16,}/.test(a.href));if(!as.length)return "no-links";const k=i%as.length;as[k].click();return as[k].href})()'
JS_PANEL='(()=>{const h=document.querySelector("[data-vsc]");if(!h)return "no-host";const b=h.shadowRoot.querySelector(".btn");const r=b.getBoundingClientRect();const o={bubbles:true,cancelable:true,composed:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,pointerId:1,pointerType:"mouse",isPrimary:true,button:0,buttons:1};b.dispatchEvent(new PointerEvent("pointerdown",o));b.dispatchEvent(new PointerEvent("pointerup",Object.assign({},o,{buttons:0})));return h.shadowRoot.querySelector(".panel").classList.contains("open")?"open":"closed"})()'
JS_CHIP='(()=>{const want=window.__vsc_chip||"1.5×";const h=document.querySelector("[data-vsc]");if(!h)return "no-host";for(const c of h.shadowRoot.querySelectorAll(".chip")){if(c.textContent.trim()===want){c.click();return "clicked:"+want}}return "no-chip"})()'
JS_USERCLICK='(()=>{const o={bubbles:true,composed:true,clientX:300,clientY:600,pointerId:2,pointerType:"mouse",isPrimary:true,button:0,buttons:1};document.body.dispatchEvent(new PointerEvent("pointerdown",o));document.body.dispatchEvent(new PointerEvent("pointerup",Object.assign({},o,{buttons:0})));return "user-clicked"})()'
JS_SITERATE='(()=>{const v=document.querySelector("video");if(!v)return "no-video";v.playbackRate=Number(window.__vsc_r||1.25);return v.playbackRate})()'

echo "===== 0. 桥连通性 ====="
ev 'location.href' | head -2

echo
echo "===== 1. 小红书（登录态）====="
oc open "https://www.xiaohongshu.com/explore" --window background >/dev/null
sleep 7
echo "初始: $(ev "$JS_STATE")"
NOTE=""
for i in 0 1 2 3 4 5; do
  ev "window.__vsc_i=$i;1" >/dev/null
  href=$(ev "$JS_NOTE")
  sleep 5
  st=$(ev "$JS_STATE")
  echo "  第 $((i+1)) 个笔记 -> $href"
  echo "     $st"
  case "$st" in
    *'"videos":0'*) ev 'history.back();1' >/dev/null; sleep 3 ;;
    *'"ext":false'*) NOTE="NOEXT:$href"; break ;;
    *) NOTE="$href"; break ;;
  esac
done
if [ -n "$NOTE" ] && [ "${NOTE#NOEXT}" = "$NOTE" ]; then
  echo "  [按钮] $(ev "$JS_PANEL")"
  ev 'window.__vsc_chip="1.5×";1' >/dev/null
  echo "  [选 1.5×] $(ev "$JS_CHIP")"
  sleep 1
  echo "  [调速后] $(ev "$JS_STATE")"
  echo "  [模拟你在播放器上改 1.25×] $(ev "$JS_USERCLICK") / $(ev "$JS_SITERATE")"
  sleep 2
  echo "  [是否跟随不抢回] $(ev "$JS_STATE")"
  oc screenshot "$T/shot_xhs_login.png" >/dev/null 2>&1
else
  echo "  小红书：未拿到可测的视频笔记（$NOTE）"
fi

echo
echo "===== 2. 微博（登录态）====="
oc open "https://weibo.com/" --window background >/dev/null
sleep 8
echo "初始: $(ev "$JS_STATE")"
WST=$(ev "$JS_STATE")
case "$WST" in
  *'"videos":0'*) echo "  首页无 video → 按钮按设计隐藏（$(ev "$JS_STATE")）" ;;
  *) echo "  [按钮] $(ev "$JS_PANEL")"
     ev 'window.__vsc_chip="1.5×";1' >/dev/null
     echo "  [选 1.5×] $(ev "$JS_CHIP")"; sleep 1
     echo "  [调速后] $(ev "$JS_STATE")"
     oc screenshot "$T/shot_weibo_login.png" >/dev/null 2>&1 ;;
esac

echo
echo "===== 3. YouTube（登录态）====="
oc open "https://www.youtube.com/watch?v=aqz-KE-bpKQ" --window background >/dev/null
sleep 12
echo "初始: $(ev "$JS_STATE")"
YST=$(ev "$JS_STATE")
case "$YST" in
  *'"ext":false'*) echo "  扩展未注入" ;;
  *) echo "  [按钮] $(ev "$JS_PANEL")"
     ev 'window.__vsc_chip="1.5×";1' >/dev/null
     echo "  [选 1.5×] $(ev "$JS_CHIP")"; sleep 1.5
     echo "  [调速后] $(ev "$JS_STATE")"
     echo "  [模拟你在播放器上改 1.25×] $(ev "$JS_USERCLICK") / $(ev "$JS_SITERATE")"
     sleep 2
     echo "  [是否跟随不抢回] $(ev "$JS_STATE")"
     oc screenshot "$T/shot_yt_login.png" >/dev/null 2>&1 ;;
esac

echo
echo "===== 4. 收尾：关闭测试标签页 ====="
oc close >/dev/null 2>&1
echo "done"
