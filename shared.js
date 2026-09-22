/* 视频速度控制 — 共享定义（设置默认值 / 主题 / 站点匹配 / 取值小工具）
   被 content.js（页面注入）与 options.js、popup.js（扩展页）共同引用。 */
window.VSC_SHARED = (function () {
  'use strict';

  var DEFAULTS = {
    version: 1,
    visible: true,              // 总开关
    displayMode: 'videoOnly',   // videoOnly = 只在该页面检测到视频时显示；always = 所有页面都显示
    excludedSites: [],          // 不显示按钮的网站（域名清单，条目命中其全部子域）

    posX: 92,                   // 按钮位置：视口宽度百分比
    posY: 10,                   // 按钮位置：视口高度百分比

    size: 100,                  // 按钮尺寸（百分比 60–500）
    radius: 42,                 // 圆角（占按钮高度的百分比：0=直角，50 以上=完全胶囊）
    styleId: 'mist',            // 按钮样式（纯色/渐变/玻璃/发光）
    showNumber: true,           // 按钮上是否显示速度数字
    idleFade: true,             // 鼠标移开后是否变淡
    idleDelay: 3,               // 鼠标移开后多少秒开始变淡（1–15）
    idleOpacity: 35,            // 鼠标移开后的不透明度（百分比 10–100）
    hoverOpacity: 100,          // 鼠标悬停时不透明度（百分比 10–100）

    showInFullscreen: true,     // 全屏播放时是否仍然显示按钮
    respectSiteRate: true,      // 你在网站自带播放器上手动调速 → 扩展读取并记住它（不抢回）
    enforce: true,              // 加载新视频时自动套用你设定的速度
    hotkeys: true,              // 键盘快捷键（Ctrl+Shift+. / Ctrl+Shift+, / Ctrl+Shift+0）

    speeds: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3],  // 档位（可在设置里增删改）
    step: 0.25,                 // 微调步长
    minRate: 0.1,
    maxRate: 10,                // 上限 10×（用户要求：不要 16× 那么快）
    defaultSpeed: 1,            // 没有网站记录时用这个速度

    rememberPerSite: true,      // 按网站记住速度
    siteSpeeds: {},             // { 域名: 速度 }
    globalSpeed: 1              // 最近一次使用的速度（iframe 内嵌播放器跟随它）
  };

  // 按钮样式：4 组 × 4 款（纯色 / 渐变 / 玻璃 / 发光）
  var STYLES = [
    { id: 'mist',  name: '雾霾蓝', group: 'solid', bg: '#5f7285', fg: '#ffffff', accent: '#5f7285' },
    { id: 'steel', name: '石板蓝', group: 'solid', bg: '#637f9e', fg: '#ffffff', accent: '#637f9e' },
    { id: 'sage',  name: '灰绿',   group: 'solid', bg: '#6f9584', fg: '#ffffff', accent: '#6f9584' },
    { id: 'mauve', name: '藕荷紫', group: 'solid', bg: '#8d80a8', fg: '#ffffff', accent: '#8d80a8' },

    { id: 'deep',  name: '深海',   group: 'grad', bg: 'linear-gradient(135deg,#728699,#3d4b5b)', fg: '#ffffff', accent: '#5f7285', anim: 'pan' },
    { id: 'dusk',  name: '暮色',   group: 'grad', bg: 'linear-gradient(135deg,#8d80a8,#565f86)', fg: '#ffffff', accent: '#8d80a8', anim: 'pan' },
    { id: 'champ', name: '香槟',   group: 'grad', bg: 'linear-gradient(135deg,#c6a97b,#8d6f4a)', fg: '#ffffff', accent: '#a88d63', anim: 'pan' },
    { id: 'aurora', name: '极光',  group: 'grad', bg: 'linear-gradient(135deg,#7fae9b,#637f9e)', fg: '#ffffff', accent: '#6f9584', anim: 'pan' },

    { id: 'glass', name: '毛玻璃', group: 'glass', bg: 'rgba(255,255,255,.18)', fg: '#ffffff', accent: '#7d94ad',
      blur: 10, bd: '1px solid rgba(255,255,255,.45)', shadow: '0 2px 10px rgba(0,0,0,.32)' },
    { id: 'space', name: '深空',   group: 'glass', bg: 'rgba(28,34,44,.62)', fg: '#eef2f6', accent: '#7d94ad',
      blur: 10, bd: '1px solid rgba(255,255,255,.18)', shadow: '0 2px 10px rgba(0,0,0,.36)' },
    { id: 'pearl', name: '珍珠',   group: 'glass', bg: 'rgba(247,244,239,.74)', fg: '#3a3f46', accent: '#a88d63',
      blur: 8, bd: '1px solid rgba(255,255,255,.8)', shadow: '0 2px 10px rgba(0,0,0,.24)' },
    { id: 'ice',   name: '冰晶',   group: 'glass', bg: 'rgba(200,222,234,.58)', fg: '#22323c', accent: '#637f9e',
      blur: 9, bd: '1px solid rgba(255,255,255,.72)', shadow: '0 2px 10px rgba(0,0,0,.26)' },

    { id: 'neonCyan', name: '霓虹青', group: 'glow', bg: '#16232b', fg: '#8ff0e4', accent: '#4fd8c8',
      glow: 'rgba(79,216,200,.75)', anim: 'pulse' },
    { id: 'neonPurple', name: '霓虹紫', group: 'glow', bg: '#1d1a2b', fg: '#c3b4ff', accent: '#9b7dff',
      glow: 'rgba(155,125,255,.75)', anim: 'pulse' },
    { id: 'amber', name: '暖金',   group: 'glow', bg: '#2b2418', fg: '#f3d9a4', accent: '#e0b062',
      glow: 'rgba(224,176,98,.7)', anim: 'pulse' },
    { id: 'coral', name: '珊瑚',   group: 'glow', bg: '#2c1f22', fg: '#ffc3bb', accent: '#f08a7c',
      glow: 'rgba(240,138,124,.7)', anim: 'pulse' }
  ];

  var GROUPS = [
    { id: 'solid', name: '纯色' },
    { id: 'grad',  name: '渐变' },
    { id: 'glass', name: '玻璃' },
    { id: 'glow',  name: '发光' }
  ];

  function style(id) {
    for (var i = 0; i < STYLES.length; i++) if (STYLES[i].id === id) return STYLES[i];
    return STYLES[0];
  }

  // 主题色的提亮版（深色面板上用小字时保证对比度）
  function lighten(hex, amt) {
    var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ''));
    if (!m) return hex;
    var n = parseInt(m[1], 16);
    var r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    r = Math.round(r + (255 - r) * amt);
    g = Math.round(g + (255 - g) * amt);
    b = Math.round(b + (255 - b) * amt);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  }

  function clamp(n, a, b) {
    n = Number(n);
    if (!isFinite(n)) return a;
    return Math.min(b, Math.max(a, n));
  }

  // 速度 → 显示文本：1 → "1×"、1.25 → "1.25×"、0.5 → "0.5×"
  function fmt(rate) {
    var v = Math.round(Number(rate) * 1000) / 1000;
    return String(v) + '×';
  }

  // 速度 → HTML（数字与「×」分开，× 略小，视觉更协调）；textContent 仍是 "1.25×"
  function fmtHTML(rate) {
    var v = Math.round(Number(rate) * 1000) / 1000;
    return '<span class="n">' + String(v) + '</span><span class="x">×</span>';
  }

  // 速度 → 保留两位的数值（storage 里存干净的数字）
  function cleanRate(rate, min, max) {
    var v = Math.round(Number(rate) * 100) / 100;
    if (!isFinite(v)) v = 1;
    return clamp(v, min == null ? DEFAULTS.minRate : min, max == null ? DEFAULTS.maxRate : max);
  }

  // 域名归一化：去协议/用户名/端口/路径/查询/结尾点，去开头 www. 与 *.，转小写
  function normalizeSite(input) {
    if (typeof input !== 'string') return '';
    var s = input.trim().toLowerCase();
    if (!s) return '';
    s = s.replace(/^[a-z][a-z0-9+.-]*:\/\//, '');
    var at = s.indexOf('@');
    if (at !== -1) s = s.slice(at + 1);
    s = s.split('/')[0].split('?')[0].split('#')[0];
    s = s.replace(/:.*$/, '');
    s = s.replace(/\.+$/, '');
    if (s.indexOf('..') !== -1) return '';
    if (s.indexOf('*.') === 0) s = s.slice(2);
    if (s.indexOf('www.') === 0) s = s.slice(4);
    if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(s)) return '';
    return s;
  }

  // 当前域名（去 www.）——用于「按网站记忆」与「排除清单」的匹配
  function hostKey(hostname) {
    return normalizeSite(hostname || '') || String(hostname || '').toLowerCase();
  }

  // 条目命中判断：条目 zhihu.com 命中 zhihu.com 与其全部子域
  function isSiteExcluded(list, hostname) {
    var h = hostKey(hostname);
    if (!h || !Array.isArray(list)) return false;
    for (var i = 0; i < list.length; i++) {
      var e = normalizeSite(list[i]);
      if (!e) continue;
      if (h === e || h.slice(-(e.length + 1)) === '.' + e) return true;
    }
    return false;
  }

  function loadSettings(cb) {
    try {
      chrome.storage.local.get('settings', function (o) {
        var s = (o && o.settings) || {};
        var merged = Object.assign({}, DEFAULTS, s);
        if (!Array.isArray(merged.speeds) || !merged.speeds.length) merged.speeds = DEFAULTS.speeds.slice();
        if (!Array.isArray(merged.excludedSites)) merged.excludedSites = [];
        if (typeof merged.siteSpeeds !== 'object' || !merged.siteSpeeds) merged.siteSpeeds = {};
        cb(merged);
      });
    } catch (e) {
      cb(Object.assign({}, DEFAULTS));
    }
  }

  function saveSettings(s, cb) {
    try {
      chrome.storage.local.set({ settings: s }, cb || function () {});
    } catch (e) {
      if (cb) cb();
    }
  }

  return {
    DEFAULTS: DEFAULTS,
    STYLES: STYLES,
    GROUPS: GROUPS,
    style: style,
    lighten: lighten,
    clamp: clamp,
    fmt: fmt,
    fmtHTML: fmtHTML,
    cleanRate: cleanRate,
    normalizeSite: normalizeSite,
    hostKey: hostKey,
    isSiteExcluded: isSiteExcluded,
    loadSettings: loadSettings,
    saveSettings: saveSettings
  };
})();
