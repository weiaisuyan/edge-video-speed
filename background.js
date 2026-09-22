/* 视频速度控制 — 后台服务（Service Worker）
   唯一职责：把内容脚本里的「设置」点击转成浏览器官方 API chrome.runtime.openOptionsPage()。
   为什么必须这样：网页（内容脚本所在的世界）用 window.open 跳 chrome-extension:// 会被 Edge
   判为跨方案导航拦截，表现为 ERR_BLOCKED_BY_CLIENT「已阻止 <扩展ID>」。 */
chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (!msg || msg.type !== 'vsc-open-options') return;
  try {
    chrome.runtime.openOptionsPage(function () {
      if (chrome.runtime.lastError) {
        sendResponse({ ok: false, error: String(chrome.runtime.lastError.message) });
      } else {
        sendResponse({ ok: true });
      }
    });
  } catch (e) {
    sendResponse({ ok: false, error: String(e) });
  }
  return true;   // 异步响应
});

// 保持服务存在的最小监听（也方便后续扩展功能）
chrome.runtime.onInstalled.addListener(function () { /* 首次安装不做打扰性动作 */ });
