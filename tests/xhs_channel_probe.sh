#!/usr/bin/env bash
# 小红书「视频」频道 → 进笔记详情验证（直接导航，无 history.back）
export OPENCLI_BROWSER_COMMAND_TIMEOUT=90
T="C:/Users/weiai/AppData/Local/hermes/cache/scratch/vsc_test"
oc() { opencli browser vsc "$@" 2>&1 | grep -v -e UNDICI -e trace-warnings; }
ev() { oc eval "$1"; }

JS_STATE='(()=>{const h=document.querySelector("[data-vsc]");return JSON.stringify({title:(document.title||"").slice(0,30),videos:document.querySelectorAll("video").length,ext:!!h,visible:h?h.style.display!=="none":null,btn:h?h.shadowRoot.querySelector(".btn").textContent.trim():null,rates:Array.from(document.querySelectorAll("video")).map(v=>v.playbackRate)})})()'
JS_PANEL='(()=>{const h=document.querySelector("[data-vsc]");if(!h)return "no-host";const b=h.shadowRoot.querySelector(".btn");const r=b.getBoundingClientRect();const o={bubbles:true,cancelable:true,composed:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,pointerId:1,pointerType:"mouse",isPrimary:true,button:0,buttons:1};b.dispatchEvent(new PointerEvent("pointerdown",o));b.dispatchEvent(new PointerEvent("pointerup",Object.assign({},o,{buttons:0})));return h.shadowRoot.querySelector(".panel").classList.contains("open")?"open":"closed"})()'
JS_CHIP='(()=>{const want=window.__vsc_chip||"1.5×";const h=document.querySelector("[data-vsc]");if(!h)return "no-host";for(const c of h.shadowRoot.querySelectorAll(".chip")){if(c.textContent.trim()===want){c.click();return "clicked:"+want}}return "no-chip"})()'
JS_USERCLICK='(()=>{const o={bubbles:true,composed:true,clientX:300,clientY:600,pointerId:2,pointerType:"mouse",isPrimary:true,button:0,buttons:1};document.body.dispatchEvent(new PointerEvent("pointerdown",o));document.body.dispatchEvent(new PointerEvent("pointerup",Object.assign({},o,{buttons:0})));return "user-clicked"})()'
JS_SITERATE='(()=>{const v=document.querySelector("video");if(!v)return "no-video";v.playbackRate=Number(window.__vsc_r||1.25);return v.playbackRate})()'

oc open "https://www.xiaohongshu.com/explore?channel_id=homefeed.video" --window background >/dev/null
sleep 9
echo "频道页: $(ev "$JS_STATE")"

FOUND=0
for i in 0 1 2 3 4 5; do
  ev "window.__vsc_i=$i;1" >/dev/null
  H=$(ev '(()=>{const as=[...document.querySelectorAll("a")].filter(a=>/\/explore\/[0-9a-f]{16,}/.test(a.href)&&/xsec_token/.test(a.href));if(!as.length)return "none";return as[(window.__vsc_i||0)%as.length].href})()')
  [ "$H" = "none" ] && { echo "无候选链接"; break; }
  oc open "$H" --window background >/dev/null
  sleep 7
  ST=$(ev "$JS_STATE")
  echo "--- 第 $((i+1)) 篇: $ST"
  case "$ST" in *'"videos":0'*) continue ;; esac
  FOUND=1
  echo "    [点按钮] $(ev "$JS_PANEL")"
  ev 'window.__vsc_chip="1.5×";1' >/dev/null
  echo "    [选 1.5×] $(ev "$JS_CHIP")"
  sleep 1.5
  echo "    [调速后] $(ev "$JS_STATE")"
  echo "    [模拟你在播放器上改 1.25×] $(ev "$JS_USERCLICK") / $(ev "$JS_SITERATE")"
  sleep 2
  echo "    [跟随不抢回] $(ev "$JS_STATE")"
  oc screenshot "$T/shot_xhs_video_note.png" >/dev/null 2>&1
  break
done
[ "$FOUND" = "0" ] && echo "小红书：视频频道前 6 篇仍未拿到 <video> 页"
oc close >/dev/null 2>&1
echo done
