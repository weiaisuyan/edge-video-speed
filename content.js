/* 视频速度控制 — 页面内容脚本
   职责：①在页面内画悬浮按钮与菜单（仅顶层框架）②把速度施加到页面里的所有 <video>
   （含 shadow DOM 穿透、含 iframe 内框架）③挡回网站把速度改回 1× 的行为 */
(function () {
  'use strict';

  var S = window.VSC_SHARED;
  if (!S || window.__vsc_injected) return;
  window.__vsc_injected = true;

  var IS_TOP = (window.top === window);
  var settings = Object.assign({}, S.DEFAULTS);

  var host = null, wrap = null, btnEl = null, numEl = null, panelEl = null, toastEl = null;
  var inFullscreenHost = false;
  var fsActive = false;        // 当前是否处于「全屏观看」（原生全屏 / 网页伪全屏 / 浏览器窗口全屏）
  var fsPopover = false;       // 是否用顶层 popover 让按钮浮在全屏内容之上
  var fsWatch = null;          // 伪全屏与浏览器全屏没有事件可听 → 轮询
  var FS_POLL_MS = 400;
  var videos = [];
  var currentRate = 1;
  var applying = false;      // 我们自己写 playbackRate 时置位，避免 ratechange 里自打架
  var idleTimer = null;
  var scanTimer = null;
  var panelOpen = false;
  var hiddenByUser = false;   // 面板里点了「本网站不再显示」
  var dragging = false, dragMoved = false, dragStart = null, dragWithCtrl = false;
  var loadTs = new WeakMap();   // 每个 video 最近一次「换素材」的时间戳
  var FRESH_MS = 1200;          // 换素材后 1.2s 内的速率变化 = 站点默认值（可覆盖）；之后 = 用户手动调速（跟随）
  var lastInputTs = 0;          // 页面上最近一次真实用户输入（点击/按键）的时间戳
  var lastPlayerInputTs = 0;    // 最近一次「在播放器上」的真实调速意图（点击落在视频上 / 调速快捷键）
  var USER_INPUT_MS = 2500;     // 「页面上刚有输入」的窗口（用来区分脚本改写 vs 真人在操作）
  var PLAYER_INPUT_MS = 1000;   // 「这次输入与速率变化有因果关系」的窗口——必须紧，才能排除巧合
  var SITE_LOAD_GRACE = 2000;   // 换素材后的宽限期：这期间的速率变化算站点自己的默认值，不采纳
  var stickyArmedAt = 0;        // 「防误判」武装时间：我们主动写入速率的时刻；0 = 未武装
  var APPLY_STICKY_MS = 3000;   // 武装后这段时间内，站点来改一律算「抢回默认值」，不认
  var reapplying = false;       // 正在「补写被站点抢回的速度」——这种写入不算主动施加，不再重新武装

  /* ---------- 设置 ---------- */

  function clampRate(v) {
    return S.cleanRate(v, settings.minRate, settings.maxRate);
  }

  function resolveRate() {
    var key = S.hostKey(location.hostname);
    if (settings.rememberPerSite && typeof settings.siteSpeeds[key] === 'number') {
      return clampRate(settings.siteSpeeds[key]);
    }
    if (!settings.rememberPerSite && typeof settings.globalSpeed === 'number') {
      return clampRate(settings.globalSpeed);
    }
    if (!IS_TOP) {
      // iframe 里的内嵌播放器没有自己的记录时，跟随「最近一次使用的速度」
      if (typeof settings.globalSpeed === 'number') return clampRate(settings.globalSpeed);
    }
    return clampRate(settings.defaultSpeed);
  }

  function persistRate(rate) {
    var next = Object.assign({}, settings);
    next.siteSpeeds = Object.assign({}, settings.siteSpeeds);
    next.globalSpeed = rate;
    var key = S.hostKey(location.hostname);
    if (settings.rememberPerSite) {
      // 1× 也是用户的合法选择，照常记忆（修 v1.0.5 前的 bug：以前这里直接删记录，
      // 导致 YouTube 把速度重置为 1× 时，你的记忆被抹掉，下次进站点又从 1× 开始）
      if (rate > 0) next.siteSpeeds[key] = rate;
    }
    settings = next;
    S.saveSettings(next);
  }

  /* ---------- 视频发现与速度施加 ---------- */

  function collectVideos(root, out, depth) {
    if (!root || depth > 12) return out;
    try {
      var vs = root.querySelectorAll('video');
      for (var i = 0; i < vs.length; i++) if (out.indexOf(vs[i]) === -1) out.push(vs[i]);
      var all = root.querySelectorAll('*');
      for (var j = 0; j < all.length; j++) {
        if (all[j].shadowRoot) collectVideos(all[j].shadowRoot, out, depth + 1);
      }
      // 同源 iframe 里的播放器也算本页有视频（跨域的读不到，由它自己的内容脚本负责施加）
      var ifr = root.querySelectorAll('iframe');
      for (var k = 0; k < ifr.length; k++) {
        try {
          var doc = ifr[k].contentDocument;
          if (doc) collectVideos(doc, out, depth + 1);
        } catch (e2) { /* 跨域 iframe 忽略 */ }
      }
    } catch (e) { /* 跨域/已卸载节点忽略 */ }
    return out;
  }

  // 站点刚换素材（事件窗口内）→ 此时站点设的速率算默认值，可被我们覆盖
  function justLoaded(v) {
    return (Date.now() - (loadTs.get(v) || 0)) < FRESH_MS;
  }

  // 标记「这个 video 刚换了素材」——记录时间戳，供 justLoaded / inSiteLoadGrace 判断。
  // v1.0.4 漏了这个定义：loadstart/emptied/loadedmetadata 三处都在调它，但函数不存在，
  // 一调就抛 ReferenceError，导致 loadTs 永远是空的 → 「刚换素材」判据全线失效，
  // 于是站点把速度重置为 1× 总被误判成「用户手动调速」，记忆被反复抹掉。
  function markLoad(v) {
    try {
      loadTs.set(v, Date.now());
      // 换了素材 = 新的播放会话，武装状态清零，从头开始判
      if (v) { stickyArmedAt = 0; reapplying = false; }
    } catch (e) { /* WeakMap 只接受对象 */ }
  }

  // 页面上刚有真实用户输入（点击/按键）→ 速率变化大概率来自「你在网站播放器上手动调速」
  function userRecent(ms) {
    return (Date.now() - lastInputTs) < (ms || USER_INPUT_MS);
  }

  // 站点刚换素材后的宽限期内 → 一律视为「站点自己设的默认值」，不采纳。
  // 为什么需要它：YouTube 等站点常常在 loadedmetadata 之后几百 ms 到两秒才把速度拨回 1×。
  // 为什么只给 2s（v1.0.5 曾用 6s，实测会把你开头的真实调速也压掉）：宽限期太长会误伤
  // 「打开视频后马上自己调速」这个正常操作。更晚发生的站点重置由「黏滞期 + enforce 兜底」负责。
  function inSiteLoadGrace(v) {
    return (Date.now() - (loadTs.get(v) || 0)) < SITE_LOAD_GRACE;
  }

  // 判定「这是不是你在播放器上手动调速」——三条同时成立才认：
  //   ① 设置里开着 respectSiteRate
  //   ② 页面上最近有输入（排除纯脚本改写）
  //   ③ 播放器上有**紧因果**的输入（默认 1s 内）——这一条优先于一切：
  //      点播放器后站点随即改速度 = 你在用站点自带菜单调速，必须跟随
  //   ④ 不在「站点刚换素材」的宽限期内
  // 注意：这里刻意**不**被「黏滞期」挡住。黏滞期是给「页面上没有任何输入、站点自己把速度
  // 拨回默认值」准备的；若你确有播放器上的紧因果输入，那是你的操作，不能被黏滞期盖掉
  // （v1.0.5 实测踩到：用我们面板设完速度后 3s 内，你在播放器里调速会被硬顶回去）。
  function isManualAdjust(v) {
    if (!settings.respectSiteRate) return false;
    if (!userRecent()) return false;
    if (inSiteLoadGrace(v)) return false;
    return (Date.now() - lastPlayerInputTs) < PLAYER_INPUT_MS;
  }

  // 站点把速度抢回了默认值 → 重新施加我们记住的速度。
  // 黏滞期只服务「一次」：命中后立刻解除武装，并且由 reapplying 保证随之而来的补写不再重新武装，
  // 否则 applyOne→站点重置→applyOne 会无限续期，把你真实的点击也一并挡掉。
  function isSiteReset(v) {
    if (inSiteLoadGrace(v)) return true;
    if (stickyArmedAt && (Date.now() - stickyArmedAt) < APPLY_STICKY_MS) {
      stickyArmedAt = 0;          // 解除武装：这一轮只认一次
      reapplying = true;          // 接下来的补写不算「主动施加」，不许再武装
      return true;
    }
    return false;
  }

  // 任何一次「用户主动改速」都解除武装（新的一次交互，从干净状态开始判）
  function resetStick() {
    stickyArmedAt = 0;
  }

  // 点击坐标是否落在某个视频的矩形内（外扩 pad，覆盖悬浮控制条）。
  // 用坐标判断而不是赌某个站点的类名——v1.0.5 一开始把 YouTube 的容器类名写成
  // 'html-video-player'（真实是 'html5-video-player'，少了那个 5），导致在油管菜单里
  // 调速被判成「站点重置」而抢回。坐标法不依赖类名，任何站点都成立。
  function pointInVideo(x, y, pad) {
    for (var i = 0; i < videos.length; i++) {
      var v = videos[i];
      if (!v || !v.isConnected) continue;
      var r;
      try { r = v.getBoundingClientRect(); } catch (e) { continue; }
      if (!r || r.width < 8 || r.height < 8) continue;
      if (x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad) return true;
    }
    return false;
  }

  // 事件目标是否属于「播放器」：video 自身，或带 player 字样的容器
  // （兼容 html5-video-player / html-video-player / bw-video-player / movie_player 等写法）
  function targetInPlayer(t) {
    for (var node = t, d = 0; d < 8 && node; d++) {
      if (node.tagName === 'VIDEO') return true;
      var cls = node.className, id = node.id;
      if (typeof cls === 'string' && /video-?player|player-?(wrap|box|container)|movie_player/i.test(cls)) return true;
      if (typeof id === 'string' && /movie_player|player/i.test(id)) return true;
      node = node.parentNode || node.host;
    }
    return false;
  }

  // 只认「真的在调速度」的按键：> < ] [（YouTube / B站 / 多数站点的倍速快捷键）。
  // 空格、方向键、K/J/L 是播放控制，不是调速 → 不算，否则会被误当成「你要改速度」。
  function isSpeedKey(e) {
    if (!e || e.ctrlKey || e.metaKey || e.altKey) return false;   // 带修饰键的是我们自己的/浏览器的
    var k = e.key;
    return k === '>' || k === '<' || k === ']' || k === '[';
  }

  function noteInput(e) {
    if (!e) return;
    // 我们自己悬浮按钮/面板上的操作不算——那是显式调速，走 setRate 自己的路径
    try {
      if (host && e.composedPath && e.composedPath().indexOf(host) !== -1) return;
    } catch (err) { /* 忽略 */ }

    lastInputTs = Date.now();
    try {
      if (e.type === 'keydown') {
        // 键盘：调速快捷键，或焦点在播放器上时，才认定为调速意图
        if (isSpeedKey(e) || targetInPlayer(e.target)) lastPlayerInputTs = Date.now();
        return;
      }
      // 指针：优先用坐标判断（不赌类名），坐标不可用时再看目标节点
      var x = e.clientX, y = e.clientY;
      if (typeof x === 'number' && typeof y === 'number' && pointInVideo(x, y, 80)) {
        lastPlayerInputTs = Date.now();
        return;
      }
      if (targetInPlayer(e.target)) lastPlayerInputTs = Date.now();
    } catch (err) { /* 忽略 */ }
  }

  function watchVideo(v) {
    if (!v || v.__vsc_watched) return;
    v.__vsc_watched = true;
    var onMeta = function () { markLoad(v); applyOne(v); };
    v.addEventListener('loadstart', function () { markLoad(v); });
    v.addEventListener('emptied', function () { markLoad(v); });
    v.addEventListener('loadedmetadata', onMeta);
    v.addEventListener('play', function () {
      // 站点刚换了视频才施加；播放中途不动（那时速度可能来自网站播放器的手动调速）
      if (justLoaded(v)) applyOne(v);
    });
    v.addEventListener('ratechange', function () {
      if (applying) return;
      var r = Number(v.playbackRate) || 1;
      // 判定为「你在网站播放器上手动调速」：读取并记住，绝不抢回。
      // 判据收紧后（isManualAdjust）：站点把速度重置为 1× 不再被误当成你的选择。
      if (isManualAdjust(v)) {
        adoptFromSite(r);
        return;
      }
      // 站点自己重置了速度 → 视为「站点默认值」，重新施加我们记住的速度（不弹提示）
      if (isSiteReset(v)) {
        applyOne(v);
        return;
      }
      if (settings.enforce && Math.abs(r - currentRate) > 0.001) applyOne(v);
    });
  }

  // 网站播放器手动调速 → 采纳为当前速度并记住
  function adoptFromSite(r) {
    var val = clampRate(r);
    if (Math.abs(val - currentRate) < 0.001) return;
    currentRate = val;
    // 这是「你手动调的」，不是站点重置 → 解除黏滞武装
    resetStick();
    setButtonText();
    syncPanelHighlight();
    persistRate(val);
    showToast('跟随播放器 ' + S.fmt(val));
  }

  function applyOne(v) {
    try {
      if (v.preservesPitch !== undefined) v.preservesPitch = true;
      if (v.webkitPreservesPitch !== undefined) v.webkitPreservesPitch = true;
      if (Math.abs((v.defaultPlaybackRate || 1) - currentRate) > 0.001) v.defaultPlaybackRate = currentRate;
      if (Math.abs((v.playbackRate || 1) - currentRate) > 0.001) {
        applying = true;
        v.playbackRate = currentRate;
        applying = false;
        // 武装「防误判」：站点接下来把速度拨回默认值时，要认得出那是站点在抢，而不是你手动调的
        // （v1.0.5 实测踩到：YouTube 加载后几百 ms~几秒就把速度拨回 1×）
        // 但「补写被抢回的速度」这种写入不算主动施加，否则 applyOne→站点重置→applyOne
        // 会无限续期，把你真实的点击也一并挡掉。
        if (reapplying) {
          reapplying = false;
        } else {
          stickyArmedAt = Date.now();
        }
      }
    } catch (e) {
      applying = false;
    }
  }

  function applyAll() {
    for (var i = 0; i < videos.length; i++) applyOne(videos[i]);
  }

  function scan() {
    var next = collectVideos(document, [], 0);
    // 只保留仍挂在文档里的节点，避免站点移除播放器后无限累积
    var alive = [];
    for (var i = 0; i < next.length; i++) {
      if (next[i].isConnected && alive.indexOf(next[i]) === -1) alive.push(next[i]);
    }
    videos = alive;
    for (var j = 0; j < videos.length; j++) watchVideo(videos[j]);
    applyAll();
    if (IS_TOP) refreshVisibility();
    return videos.length;
  }

  function scheduleScan() {
    if (scanTimer) return;
    scanTimer = setTimeout(function () {
      scanTimer = null;
      scan();
    }, 300);
  }

  /* ---------- 显示判定 ---------- */

  function hasVideo() { return videos.length > 0; }

  /* ---------- 全屏判定 ----------
     三类「全屏」都要认，设置里关掉「全屏播放时仍然显示按钮」时一律要把按钮藏起来：
     ① 原生全屏（Fullscreen API）—— 有 fullscreenchange 事件；
     ② 网页伪全屏（网站用 CSS 把播放器铺满视口，例如 B站「网页全屏」）—— 没有任何事件，只能轮询；
     ③ 浏览器窗口全屏（F11 / Edge「全屏」）—— 视口尺寸≈屏幕尺寸，且视频占住大半个视口。 */

  function nativeFullscreen() { return !!document.fullscreenElement; }

  // 页面里「最大的那个视频」占视口的比例（宽比 / 高比 / 面积比）
  function videoRatio() {
    var vw = window.innerWidth || 1, vh = window.innerHeight || 1;
    var best = { w: 0, h: 0, area: 0 };
    for (var i = 0; i < videos.length; i++) {
      var v = videos[i];
      if (!v || !v.isConnected) continue;
      var r;
      try { r = v.getBoundingClientRect(); } catch (e) { continue; }
      if (!r || r.width <= 0 || r.height <= 0) continue;
      var wr = r.width / vw, hr = r.height / vh;
      if (wr * hr > best.area) best = { w: wr, h: hr, area: wr * hr };
    }
    return best;
  }

  // 浏览器窗口全屏（F11 / Edge「全屏」）：视口几乎等于整个屏幕
  // （普通窗口 innerHeight 明显小于 screen.height；最大化窗口也差着一个任务栏 ≈90px）
  function windowIsFullscreen() {
    var sc = window.screen || {};
    var sw = Number(sc.width) || 0, sh = Number(sc.height) || 0;
    if (sw <= 0 || sh <= 0) return false;
    return window.innerWidth >= sw - 4 && window.innerHeight >= sh - 4;
  }

  function computeFsActive() {
    if (nativeFullscreen()) return true;                          // ①
    var r = videoRatio();
    if (r.w >= 0.94 && r.h >= 0.94) return true;                  // ② 视频铺满视口
    if (videoInFullCoverWrap()) return true;                      // ②' 视频被信箱化在铺满视口的定位容器里
    if (windowIsFullscreen() && r.area >= 0.55) return true;      // ③ 浏览器全屏 + 视频占大半个视口
    return false;
  }

  // 视频被「信箱化」在铺满视口的定位容器里。
  // 为什么要这条：窗口比例和视频比例不一致时（例如竖一点或很宽的窗口），
  // 铺满视口的是播放器的 fixed 容器（B站「网页全屏」就是 .mode-webscreen，z-index 100000），
  // 视频本身只占容器的一部分（上下留黑边），单看视频占比会漏判。
  function videoInFullCoverWrap() {
    var vw = window.innerWidth || 1, vh = window.innerHeight || 1;
    for (var i = 0; i < videos.length; i++) {
      var v = videos[i];
      if (!v || !v.isConnected || !v.parentElement) continue;
      var vr;
      try { vr = v.getBoundingClientRect(); } catch (e) { continue; }
      if (vr.width * vr.height < vw * vh * 0.3) continue;   // 视频本身太小，不必深查
      var el = v.parentElement, depth = 0;
      while (el && el !== document.body && depth < 6) {
        var cs, r;
        try { cs = getComputedStyle(el); r = el.getBoundingClientRect(); } catch (e) { break; }
        if ((cs.position === 'fixed' || cs.position === 'absolute') &&
            r.width >= vw * 0.96 && r.height >= vh * 0.96 &&
            vr.width * vr.height >= r.width * r.height * 0.6) return true;
        el = el.parentElement;
        depth++;
      }
    }
    return false;
  }

  // 是否因为「全屏 + 设置要求隐藏」而不该出现
  function fsHide() { return !settings.showInFullscreen && fsActive; }

  function shouldShow() {
    if (!IS_TOP) return false;
    if (!settings.visible) return false;
    if (hiddenByUser) return false;
    if (S.isSiteExcluded(settings.excludedSites, location.hostname)) return false;
    if (settings.displayMode === 'always') return true;
    return hasVideo();
  }

  function refreshVisibility() {
    if (!host) return;
    fsActive = computeFsActive();
    syncFullscreenHost();
    var show = shouldShow() && !fsHide();
    host.style.display = show ? 'block' : 'none';
    if (!show && panelOpen) closePanel();
  }

  /* ---------- 界面 ---------- */

  var STYLE_TEXT = [
    ':host{all:initial}',
    '*{box-sizing:border-box;font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}',
    '.wrap{position:relative}',
    '.btn{pointer-events:auto;display:flex;align-items:center;justify-content:center;gap:3px;',
    '  min-width:calc(var(--vsc-h) * 1.55);height:var(--vsc-h);padding:0 calc(var(--vsc-h) * 0.30);',
    '  border-radius:calc(var(--vsc-h) * var(--vsc-radius));',
    '  background:var(--vsc-bg);color:var(--vsc-fg);border:var(--vsc-bd);',
    '  -webkit-backdrop-filter:var(--vsc-blur);backdrop-filter:var(--vsc-blur);',
    '  font-size:calc(var(--vsc-h) * .50);font-weight:600;letter-spacing:.2px;cursor:pointer;',
    '  box-shadow:var(--vsc-shadow);',
    '  opacity:var(--vsc-op-hover);',   /* 透明度只在按钮这一层设（菜单不受影响，也不会相乘） */
    '  transition:transform .14s ease, opacity .18s ease;user-select:none;line-height:1}',
    '.lbl{display:inline-flex;align-items:baseline}',
    '.x{font-size:.70em;font-weight:600;margin-left:.05em}',
    '.btn:hover{transform:scale(1.06);filter:brightness(1.06)}',
    '.btn:active{transform:scale(.97)}',
    '.btn .ico{width:calc(var(--vsc-h) * .42);height:calc(var(--vsc-h) * .42);display:block}',
    '.btn.anim-pulse{animation:vscPulse 2.6s ease-in-out infinite}',
    '.btn.anim-pan{background-size:220% 220%;animation:vscPan 7s ease-in-out infinite}',
    '@keyframes vscPulse{0%,100%{box-shadow:0 0 0 0 var(--vsc-glow),var(--vsc-shadow)}',
    '  50%{box-shadow:0 0 13px 2px var(--vsc-glow),var(--vsc-shadow)}}',
    '@keyframes vscPan{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}',
    '@media (prefers-reduced-motion: reduce){.btn{animation:none!important}}',
    /* 按钮变淡/恢复（菜单面板 .panel 不参与，始终 100% 不透明，保证菜单看得清） */
    '.wrap.idle .btn{opacity:var(--vsc-op-idle);transition:opacity .55s ease}',
    '.wrap.idle:hover .btn{opacity:var(--vsc-op-hover);transition:opacity .18s ease}',
    '.panel{pointer-events:auto;position:absolute;right:0;top:calc(100% + 8px);width:238px;',
    '  background:rgba(26,28,32,.97);border:1px solid rgba(255,255,255,.09);border-radius:14px;',
    '  box-shadow:0 12px 34px rgba(0,0,0,.44);padding:12px;color:#eef0f3;z-index:2;',
    '  backdrop-filter:blur(6px);display:none}',
    '.panel.up{bottom:calc(100% + 8px);top:auto}',
    '.panel.open{display:block}',
    '.p-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:9px}',
    '.p-title{font-size:12px;color:#a7adb7;letter-spacing:.4px}',
    '.p-now{font-size:17px;font-weight:700;color:var(--vsc-c-light);font-variant-numeric:tabular-nums}',
    '.chips{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}',
    '.chip{pointer-events:auto;height:30px;border-radius:9px;border:1px solid rgba(255,255,255,.1);',
    '  background:rgba(255,255,255,.045);color:#e7eaee;font-size:12.5px;font-weight:600;cursor:pointer;',
    '  font-variant-numeric:tabular-nums;transition:background .14s ease,border-color .14s ease}',
    '.chip:hover{background:rgba(255,255,255,.1)}',
    '.chip.on{background:var(--vsc-c);border-color:var(--vsc-c);color:#fff}',
    '.row{display:flex;align-items:center;gap:7px;margin-top:10px}',
    '.mini{pointer-events:auto;flex:0 0 auto;width:38px;height:30px;border-radius:9px;',
    '  border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.045);color:#e7eaee;',
    '  font-size:15px;font-weight:700;cursor:pointer;line-height:1;user-select:none}',
    '.mini:hover{background:rgba(255,255,255,.12)}',
    '.slider{-webkit-appearance:none;appearance:none;flex:1 1 auto;height:4px;border-radius:3px;',
    '  background:rgba(255,255,255,.16);outline:none;pointer-events:auto}',
    '.slider::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;',
    '  background:var(--vsc-c);border:2px solid #fff;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.4)}',
    '.sval{margin-top:7px;text-align:center;font-size:12px;color:var(--vsc-c-light);',
    '  font-variant-numeric:tabular-nums;letter-spacing:.3px}',
    '.acts{display:flex;gap:6px;margin-top:11px;padding-top:10px;border-top:1px solid rgba(255,255,255,.08)}',
    '.act{pointer-events:auto;flex:1 1 0;height:28px;border-radius:8px;border:1px solid rgba(255,255,255,.1);',
    '  background:transparent;color:#c8cdd4;font-size:11px;cursor:pointer;white-space:nowrap;',
    '  padding:0 4px;overflow:hidden;text-overflow:ellipsis}',
    '.act:hover{background:rgba(255,255,255,.08);color:#fff}',
    '.hint{margin-top:8px;font-size:11px;color:#9aa2ad;line-height:1.55}',
    '.toast{position:fixed;pointer-events:none;padding:6px 12px;border-radius:999px;',
    '  background:rgba(20,22,25,.9);color:#fff;font-size:13px;font-weight:700;opacity:0;',
    '  transition:opacity .22s ease;font-variant-numeric:tabular-nums}',
    '.toast.on{opacity:1}'
  ].join('');

  var ICON_SVG = '<svg class="ico" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M8 6.5v11l9-5.5-9-5.5z" fill="currentColor"/>' +
    '<path d="M19.5 8.2c.9 1.1 1.4 2.4 1.4 3.8s-.5 2.7-1.4 3.8" stroke="currentColor" ' +
    'stroke-width="1.7" stroke-linecap="round"/></svg>';

  function buildUI() {
    if (host) return;
    host = document.createElement('div');
    host.setAttribute('data-vsc', '1');
    host.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;margin:0;padding:0;' +
      'border:0;background:transparent;width:auto;height:auto;';
    var sh = host.attachShadow({ mode: 'open' });
    var st = document.createElement('style');
    st.textContent = STYLE_TEXT;
    sh.appendChild(st);

    wrap = document.createElement('div');
    wrap.className = 'wrap';
    btnEl = document.createElement('button');
    btnEl.className = 'btn';
    btnEl.type = 'button';
    numEl = document.createElement('span');
    numEl.className = 'lbl';
    btnEl.appendChild(numEl);
    wrap.appendChild(btnEl);

    panelEl = document.createElement('div');
    panelEl.className = 'panel';
    wrap.appendChild(panelEl);

    sh.appendChild(wrap);

    toastEl = document.createElement('div');
    toastEl.className = 'toast';
    sh.appendChild(toastEl);

    (document.body || document.documentElement).appendChild(host);

    btnEl.addEventListener('pointerdown', onBtnDown);
    btnEl.addEventListener('pointerenter', holdIdle);
    btnEl.addEventListener('pointerleave', scheduleIdle);
    wrap.addEventListener('pointerenter', holdIdle);
    wrap.addEventListener('pointerleave', scheduleIdle);   // 从菜单移开也要重新计时（曾经漏了 → 永远不变暗）

    document.addEventListener('pointerdown', onDocDown, true);
    document.addEventListener('keydown', onDocKey, true);
    document.addEventListener('fullscreenchange', onFullscreen);
    window.addEventListener('resize', place);

    applyStyle();
    place();
    renderPanel();
    refreshVisibility();
    scheduleIdle();
    startFsWatch();
  }

  function applyStyle() {
    if (!host) return;
    var s = S.style(settings.styleId);
    var h = Math.round(34 * (settings.size / 100));
    var hover = S.clamp(settings.hoverOpacity, 10, 100) / 100;
    var idle = settings.idleFade ? S.clamp(settings.idleOpacity, 10, 100) / 100 : hover;
    host.style.setProperty('--vsc-bg', s.bg);
    host.style.setProperty('--vsc-fg', s.fg || '#ffffff');
    host.style.setProperty('--vsc-bd', s.bd || '0');
    host.style.setProperty('--vsc-blur', s.blur ? 'blur(' + s.blur + 'px)' : 'none');
    host.style.setProperty('--vsc-shadow', s.shadow || '0 2px 8px rgba(0,0,0,.28)');
    host.style.setProperty('--vsc-glow', s.glow || 'rgba(0,0,0,0)');
    host.style.setProperty('--vsc-c', s.accent);
    host.style.setProperty('--vsc-c-light', S.lighten(s.accent, 0.42));
    host.style.setProperty('--vsc-h', h + 'px');
    host.style.setProperty('--vsc-radius', String(S.clamp(settings.radius === undefined ? 42 : settings.radius, 0, 80) / 100));
    host.style.setProperty('--vsc-op-hover', String(hover));   // 鼠标悬停时
    host.style.setProperty('--vsc-op-idle', String(idle));     // 鼠标移开后
    host.style.opacity = '1';
    paintImmune(s);   // 见下：把关键颜色用内联 !important 写死，防止被深色模式扩展改写
    if (btnEl) {
      btnEl.classList.toggle('anim-pulse', s.anim === 'pulse');
      btnEl.classList.toggle('anim-pan', s.anim === 'pan');
    }
    renderButtonLabel();
  }

  /* ---------- 深色模式扩展免疫 ----------
     Dark Reader 之类的扩展会遍历并重写 shadow DOM 内的样式表：把
     `.btn{background:var(--vsc-bg)}` 改写成 `var(--darkreader-bgimg--vsc-bg)`，
     而这个变量永远不会被定义（我们的颜色是运行时用 JS 写到 host 上的，它静态分析看不到），
     结果 background 变成「无效值」→ 渲染为完全透明。
     解决办法：关键颜色一律用「元素内联样式 + !important」写死。内联 !important 的
     优先级高于任何作者样式（含 Dark Reader 注入的 !important 规则），它无法再压掉。
     ⚠️ 只写「颜色类」属性；opacity 交给样式表（变淡/悬停逻辑要能生效）。 */
  function paintImmune(s) {
    s = s || S.style(settings.styleId);
    var blur = s.blur ? 'blur(' + s.blur + 'px)' : 'none';
    if (btnEl) {
      btnEl.style.setProperty('background', s.bg, 'important');
      btnEl.style.setProperty('color', s.fg || '#ffffff', 'important');
      btnEl.style.setProperty('border', s.bd || '0', 'important');
      btnEl.style.setProperty('box-shadow', s.shadow || '0 2px 8px rgba(0,0,0,.28)', 'important');
      btnEl.style.setProperty('backdrop-filter', blur, 'important');
      btnEl.style.setProperty('-webkit-backdrop-filter', blur, 'important');
    }
    if (panelEl) {
      panelEl.style.setProperty('background', 'rgba(26,28,32,.97)', 'important');
      panelEl.style.setProperty('color', '#eef0f3', 'important');
      panelEl.style.setProperty('border-color', 'rgba(255,255,255,.09)', 'important');
      panelEl.querySelectorAll('.mini').forEach(function (b) {
        b.style.setProperty('background', 'rgba(255,255,255,.045)', 'important');
        b.style.setProperty('color', '#e7eaee', 'important');
        b.style.setProperty('border-color', 'rgba(255,255,255,.1)', 'important');
      });
      panelEl.querySelectorAll('.act').forEach(function (b) {
        b.style.setProperty('background', 'transparent', 'important');
        b.style.setProperty('color', '#c8cdd4', 'important');
        b.style.setProperty('border-color', 'rgba(255,255,255,.1)', 'important');
      });
      var sl = panelEl.querySelector('.slider');
      if (sl) sl.style.setProperty('background', 'rgba(255,255,255,.16)', 'important');
      var hint = panelEl.querySelector('.hint');
      if (hint) hint.style.setProperty('color', '#9aa2ad', 'important');
      var pt = panelEl.querySelector('.p-title');
      if (pt) pt.style.setProperty('color', '#a7adb7', 'important');
    }
    if (toastEl) {
      toastEl.style.setProperty('background', 'rgba(20,22,25,.9)', 'important');
      toastEl.style.setProperty('color', '#ffffff', 'important');
    }
    paintAccent(s);
  }

  // 菜单里随主题色变化的元素（选中档位、当前速度文字）同样要免疫
  function paintAccent(s) {
    s = s || S.style(settings.styleId);
    if (!panelEl) return;
    var light = S.lighten(s.accent, 0.42);
    panelEl.querySelectorAll('.chip').forEach(function (c) {
      if (c.classList.contains('on')) {
        c.style.setProperty('background', s.accent, 'important');
        c.style.setProperty('border-color', s.accent, 'important');
        c.style.setProperty('color', '#ffffff', 'important');
      } else {
        c.style.setProperty('background', 'rgba(255,255,255,.045)', 'important');
        c.style.setProperty('border-color', 'rgba(255,255,255,.1)', 'important');
        c.style.setProperty('color', '#e7eaee', 'important');
      }
    });
    panelEl.querySelectorAll('.p-now').forEach(function (e) {
      e.style.setProperty('color', light, 'important');
    });
    panelEl.querySelectorAll('.sval').forEach(function (e) {
      e.style.setProperty('color', light, 'important');
    });
  }

  function renderButtonLabel() {
    if (!btnEl) return;
    if (settings.showNumber) {
      // numEl 在「关闭数字」时被置 null → 这里必须能重建，否则再打开时数字回不来（曾经的真 bug）
      if (!numEl) {
        numEl = document.createElement('span');
        numEl.className = 'lbl';
      }
      numEl.innerHTML = S.fmtHTML(currentRate);
      if (!btnEl.contains(numEl)) {
        btnEl.innerHTML = '';
        btnEl.appendChild(numEl);
      }
      btnEl.title = '当前速度 ' + S.fmt(currentRate) + '（点击调节，Ctrl+拖动移动位置）';
    } else {
      btnEl.innerHTML = ICON_SVG;
      numEl = null;
      btnEl.title = '当前速度 ' + S.fmt(currentRate) + '（点击调节，Ctrl+拖动移动位置）';
    }
  }

  function setButtonText() {
    if (!settings.showNumber) { renderButtonLabel(); return; }
    if (!numEl) renderButtonLabel();
    else numEl.innerHTML = S.fmtHTML(currentRate);
    if (btnEl) btnEl.title = '当前速度 ' + S.fmt(currentRate) + '（点击调节，Ctrl+拖动移动位置）';
    var now = panelEl && panelEl.querySelector('.p-now');
    if (now) now.innerHTML = S.fmtHTML(currentRate);
  }

  function place() {
    if (!host || !wrap) return;
    var vw = window.innerWidth, vh = window.innerHeight;
    var w = wrap.offsetWidth || 60, h = (btnEl && btnEl.offsetHeight) || 34;
    var x = Math.round(vw * S.clamp(settings.posX, 0, 100) / 100);
    var y = Math.round(vh * S.clamp(settings.posY, 0, 100) / 100);
    x = Math.min(vw - w - 8, Math.max(8, x));
    y = Math.min(vh - h - 8, Math.max(8, y));
    host.style.left = x + 'px';
    host.style.top = y + 'px';
    panelEl.classList.toggle('up', y > vh * 0.55);
    placeToast();
  }

  function placeToast() {
    if (!toastEl || !host) return;
    var h = (btnEl && btnEl.offsetHeight) || 34;
    toastEl.style.left = Math.max(8, Math.round(host.getBoundingClientRect().left)) + 'px';
    toastEl.style.top = Math.round(host.getBoundingClientRect().top + h + 10) + 'px';
  }

  /* ---------- 菜单 ---------- */

  function renderPanel() {
    if (!panelEl) return;
    var speeds = (settings.speeds || []).slice().sort(function (a, b) { return a - b; });
    var html = '<div class="p-head"><span class="p-title">播放速度</span>' +
      '<span class="p-now">' + S.fmt(currentRate) + '</span></div><div class="chips">';
    for (var i = 0; i < speeds.length; i++) {
      var r = Number(speeds[i]);
      var on = Math.abs(r - currentRate) < 0.001 ? ' on' : '';
      html += '<button class="chip' + on + '" type="button" data-rate="' + r + '">' + S.fmt(r) + '</button>';
    }
    html += '</div>' +
      '<div class="row">' +
      '<button class="mini" type="button" data-act="minus">−</button>' +
      '<input class="slider" type="range" min="' + settings.minRate + '" max="' + settings.maxRate +
      '" step="0.05" value="' + currentRate + '">' +
      '<button class="mini" type="button" data-act="plus">+</button>' +
      '</div>' +
      '<div class="sval">当前：<b class="sval-num">' + S.fmtHTML(currentRate) + '</b></div>' +
      '<div class="acts">' +
      '<button class="act" type="button" data-act="reset">重置 1×</button>' +
      '<button class="act" type="button" data-act="hide">本网站隐藏</button>' +
      '<button class="act" type="button" data-act="options">设置</button>' +
      '</div>' +
      '<div class="hint">按住 Ctrl 拖动按钮可移动位置（自动记住）<br>Ctrl+Shift+&gt; 加快 · Ctrl+Shift+&lt; 减慢<br>Ctrl+Shift+0 重置为 1×</div>';
    panelEl.innerHTML = html;

    panelEl.querySelectorAll('.chip').forEach(function (c) {
      c.addEventListener('click', function () { setRate(Number(c.getAttribute('data-rate'))); });
    });
    panelEl.querySelectorAll('[data-act]').forEach(function (b) {
      b.addEventListener('click', function () {
        var act = b.getAttribute('data-act');
        if (act === 'plus') setRate(round5(currentRate + Number(settings.step)));
        else if (act === 'minus') setRate(round5(currentRate - Number(settings.step)));
        else if (act === 'reset') setRate(1);
        else if (act === 'hide') hideCurrentSite();
        else if (act === 'options') openOptions();
      });
    });
    var sl = panelEl.querySelector('.slider');
    if (sl) {
      sl.addEventListener('input', function () { setRate(Number(sl.value), true); });
    }
    paintImmune();   // 新生成的菜单元素：关键颜色立刻用内联 !important 写死
  }

  function round5(v) { return Math.round(Number(v) * 100) / 100; }

  function openPanel() {
    if (!panelEl) return;
    renderPanel();
    panelEl.classList.add('open');
    panelOpen = true;
    holdIdle();
  }

  function closePanel() {
    if (!panelEl) return;
    panelEl.classList.remove('open');
    panelOpen = false;
    scheduleIdle();
  }

  function openOptions() {
    // 走后台 → chrome.runtime.openOptionsPage()：网页自己跳 chrome-extension:// 会被浏览器拦（ERR_BLOCKED_BY_CLIENT）
    try {
      chrome.runtime.sendMessage({ type: 'vsc-open-options' }, function (resp) {
        if (chrome.runtime.lastError || !resp || !resp.ok) {
          try { window.open(chrome.runtime.getURL('options.html'), '_blank'); } catch (e) { /* 忽略 */ }
        }
      });
    } catch (e) {
      try { window.open(chrome.runtime.getURL('options.html'), '_blank'); } catch (e2) { /* 忽略 */ }
    }
  }

  function hideCurrentSite() {
    var key = S.hostKey(location.hostname);
    if (!key) return;
    hiddenByUser = true;
    if (settings.excludedSites.indexOf(key) === -1) {
      var next = Object.assign({}, settings, {
        excludedSites: settings.excludedSites.concat([key])
      });
      settings = next;
      S.saveSettings(next);
    }
    closePanel();
    refreshVisibility();
  }

  /* ---------- 调速 ---------- */

  function setRate(rate) {
    var r = clampRate(rate);
    var changed = Math.abs(r - currentRate) > 0.0001;
    currentRate = r;
    // 用户主动调速：新的一次交互，把黏滞期状态清干净（否则刚施加完的 3s 内
    // 站点任何改写都会被当成「抢回默认值」，你紧接着的第二次调整就不被认了）
    resetStick();
    applyAll();
    setButtonText();
    syncPanelHighlight();
    if (changed) persistRate(r);   // 只在速度真正变化时写一次 storage
    showToast(S.fmt(r));
  }

  function syncPanelHighlight() {
    if (!panelEl) return;
    panelEl.querySelectorAll('.chip').forEach(function (c) {
      var on = Math.abs(Number(c.getAttribute('data-rate')) - currentRate) < 0.001;
      c.classList.toggle('on', on);
    });
    var sl = panelEl.querySelector('.slider');
    if (sl) sl.value = String(currentRate);
    var sn = panelEl.querySelector('.sval-num');
    if (sn) sn.innerHTML = S.fmtHTML(currentRate);
    paintAccent();   // 选中态/主题色文字用内联 !important 重写一遍（深色模式扩展免疫）
  }

  var toastTimer = null;
  function showToast(text) {
    if (!toastEl) return;
    toastEl.textContent = text;
    toastEl.classList.add('on');
    placeToast();
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('on'); }, 900);
  }

  /* ---------- 交互 ---------- */

  function onBtnDown(e) {
    if (e.button !== 0) return;
    dragging = true;
    dragMoved = false;
    dragWithCtrl = !!e.ctrlKey;   // 只有按住 Ctrl 才是「移动位置」，避免误拖
    var r = host.getBoundingClientRect();
    dragStart = { x: e.clientX, y: e.clientY, left: r.left, top: r.top };
    try { btnEl.setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
    e.preventDefault();
  }

  // 唯一的收尾点（window 捕获阶段）：区分「Ctrl 拖动移动位置」与「单击开菜单」
  function endPress(e) {
    if (!dragging) return;
    dragging = false;
    if (btnEl && e && e.pointerId !== undefined) {
      try { btnEl.releasePointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
    }
    if (dragMoved) {
      var next = Object.assign({}, settings);
      settings = next;
      S.saveSettings(next);       // 位置以视口百分比记住
      return;
    }
    if (panelOpen) closePanel(); else openPanel();
  }

  function onPointerMove(e) {
    if (!dragging || !dragStart || !dragWithCtrl) return;   // 未按 Ctrl = 不移动，只当作普通点击
    var dx = e.clientX - dragStart.x, dy = e.clientY - dragStart.y;
    if (!dragMoved && Math.abs(dx) + Math.abs(dy) < 6) return;
    dragMoved = true;
    var vw = window.innerWidth, vh = window.innerHeight;
    var w = wrap.offsetWidth || 60, h = (btnEl && btnEl.offsetHeight) || 34;
    var x = Math.min(vw - w - 8, Math.max(8, dragStart.left + dx));
    var y = Math.min(vh - h - 8, Math.max(8, dragStart.top + dy));
    host.style.left = Math.round(x) + 'px';
    host.style.top = Math.round(y) + 'px';
    settings.posX = Math.round(x / vw * 1000) / 10;
    settings.posY = Math.round(y / vh * 1000) / 10;
    panelEl.classList.toggle('up', y > vh * 0.55);
    placeToast();
  }

  function onPointerUpGlobal() {
    if (!dragging) return;
    dragging = false;
  }

  function onDocDown(e) {
    if (!panelOpen) return;
    var path = e.composedPath ? e.composedPath() : [];
    if (path.indexOf(host) === -1) closePanel();
  }

  function onDocKey(e) {
    if (e.key === 'Escape' && panelOpen) { closePanel(); return; }
    if (!settings.hotkeys || !IS_TOP) return;
    if (!e.ctrlKey || !e.shiftKey || e.altKey || e.metaKey) return;
    if (!hasVideo() && settings.displayMode !== 'always') return;
    var k = e.key;
    if (k === '>' || k === '.') { setRate(round5(currentRate + Number(settings.step))); e.preventDefault(); }
    else if (k === '<' || k === ',') { setRate(round5(currentRate - Number(settings.step))); e.preventDefault(); }
    else if (k === ')' || k === '0') { setRate(1); e.preventDefault(); }
  }

  /* ---------- 闲置淡化 ---------- */

  function holdIdle() {
    if (!wrap) return;
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
    wrap.classList.remove('idle');
  }

  function scheduleIdle() {
    if (!wrap || !settings.idleFade) { if (wrap) wrap.classList.remove('idle'); return; }
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      idleTimer = null;
      if (!wrap) return;
      if (wrap.matches(':hover')) return;   // 鼠标还停在按钮/菜单上就不淡化（不管菜单开没开）
      wrap.classList.add('idle');
    }, Math.max(1, Number(settings.idleDelay)) * 1000);
  }

  /* ---------- 全屏 ---------- */

  function onFullscreen() {
    if (!IS_TOP || !host) return;
    fsActive = computeFsActive();
    syncFullscreenHost();
    refreshVisibility();
    place();
  }

  /* 「全屏播放时仍然显示按钮」= 开时，把按钮搬到「看得见」的地方：
     · 全屏元素能装子元素（div 播放器容器）→ 直接搬进去（原生全屏只绘制全屏元素本身）
     · 全屏元素是 video / iframe 这类不渲染子元素的标签 → 改用顶层 popover 浮在它上面
       （实测：搬进 <video> 里 0 像素；popover 后 3457 像素正常可见）
     关掉该设置（要求全屏隐藏）时，两者都撤掉。 */
  function syncFullscreenHost() {
    var el = document.fullscreenElement;
    if (!el || !settings.showInFullscreen || fsHide()) {
      if (fsPopover) {
        try { host.hidePopover(); } catch (e) { /* 忽略 */ }
        try { host.removeAttribute('popover'); } catch (e) { /* 忽略 */ }
        fsPopover = false;
      }
      if (inFullscreenHost) restoreHostToBody();
      return;
    }
    var t = el.tagName;
    if (t === 'VIDEO' || t === 'IFRAME' || t === 'IMG' || t === 'CANVAS') {
      if (!fsPopover) {
        try {
          host.setAttribute('popover', 'manual');
          host.showPopover();
          fsPopover = true;
        } catch (e) { fsPopover = false; }
      }
      return;
    }
    if (host.parentNode !== el) {
      try { el.appendChild(host); inFullscreenHost = true; } catch (e) { /* 忽略 */ }
    }
  }

  function restoreHostToBody() {
    try { (document.body || document.documentElement).appendChild(host); } catch (e) { /* 忽略 */ }
    inFullscreenHost = false;
  }

  /* 伪全屏 / 浏览器全屏没有事件可听 → 轻量轮询。
     只在「设置要求全屏隐藏」时跑（默认设置下零开销），单次成本 = 几个 getBoundingClientRect。 */
  function startFsWatch() {
    if (fsWatch || !IS_TOP) return;
    fsWatch = setInterval(function () {
      if (!host || !host.isConnected) return;
      if (settings.showInFullscreen) return;
      var next = computeFsActive();
      if (next === fsActive) return;
      fsActive = next;
      syncFullscreenHost();
      refreshVisibility();
      place();
    }, FS_POLL_MS);
  }

  /* ---------- 启动 ---------- */

  function init() {
    settings = Object.assign({}, settings, {});
    S.loadSettings(function (s) {
      settings = s;
      currentRate = resolveRate();
      scan();
      if (IS_TOP) {
        buildUI();
        applyStyle();
        setButtonText();
        refreshVisibility();
        place();
        scheduleIdle();
      }
      // 引擎侧持续工作：新插入的 video 会被纳入，换素材时重新施加
      // 注意：不做定时「抢回」——播放中途的速率变化一律视为用户在网站播放器上的手动调速
      var mo = new MutationObserver(function () { scheduleScan(); });
      try { mo.observe(document.documentElement, { childList: true, subtree: true }); } catch (e) { /* 忽略 */ }
    });

    if (IS_TOP) {
      // 拖动过程中的全局兜底：指针移出按钮/窗口松开也要收尾（区分点击与拖动）
      window.addEventListener('pointermove', onPointerMove, true);
      window.addEventListener('pointerup', endPress, true);
      window.addEventListener('pointercancel', onPointerUpGlobal, true);
      window.addEventListener('blur', onPointerUpGlobal);
    }
    // 记录真实用户输入：用来区分「你在网站播放器上手动调速」与「站点自己重置速度」
    document.addEventListener('pointerdown', noteInput, true);
    document.addEventListener('keydown', noteInput, true);

    try {
      chrome.storage.onChanged.addListener(function (changes, area) {
        if (area !== 'local' || !changes.settings) return;
        var nv = changes.settings.newValue || {};
        settings = Object.assign({}, S.DEFAULTS, nv);
        if (!Array.isArray(settings.speeds) || !settings.speeds.length) settings.speeds = S.DEFAULTS.speeds.slice();
        hiddenByUser = false;
        currentRate = resolveRate();
        applyAll();
        if (IS_TOP && host) {
          applyStyle();
          setButtonText();
          if (panelOpen) renderPanel();
          refreshVisibility();
          place();
          scheduleIdle();
        }
      });
    } catch (e) { /* 忽略 */ }
  }

  // 暴露给自动化测试的只读探针（不改变任何行为）
  window.__vsc_probe = function () {
    return {
      injected: true,
      isTop: IS_TOP,
      rate: currentRate,
      videos: videos.length,
      rates: videos.map(function (v) { return v.playbackRate; }),
      hasHost: !!host,
      hostInDom: !!(host && host.isConnected),
      visible: !!(host && host.style.display !== 'none'),
      panelOpen: panelOpen,
      fullscreen: !!document.fullscreenElement,
      fsActive: fsActive,
      fsHide: fsHide(),
      fsPopover: fsPopover,
      hostParent: host && host.parentNode ? (host.parentNode.id || host.parentNode.tagName) : null,
      siteExcluded: S.isSiteExcluded(settings.excludedSites, location.hostname)
    };
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
