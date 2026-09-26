/* 视频速度控制 — 工具栏弹窗（点扩展图标）
   行为与页面内菜单一致：档位网格 / −滑杆+ / 当前值 / 重置 1× / 本网站隐藏 / 设置。
   写入 storage 后，页面里的内容脚本会通过 chrome.storage.onChanged 立即把速度套到视频上。 */
(function () {
  'use strict';
  var S = window.VSC_SHARED;
  var st = Object.assign({}, S.DEFAULTS);
  var host = '';
  var siteRate = null;   // 本网站记住的速度（null = 未记录）

  function $(id) { return document.getElementById(id); }
  function round5(v) { return Math.round(Number(v) * 100) / 100; }
  function clampRate(v) { return S.clamp(round5(v), st.minRate, st.maxRate); }

  // 当前生效速度：本网站记录 → 最近一次使用 → 默认
  function currentRate() {
    if (siteRate !== null) return siteRate;
    var g = Number(st.globalSpeed);
    return isFinite(g) && g > 0 ? g : Number(st.defaultSpeed) || 1;
  }

  function currentTab(cb) {
    try {
      chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        var t = tabs && tabs[0];
        var url = (t && t.url) || '';
        var h = '';
        if (/^https?:\/\//i.test(url)) {
          try { h = new URL(url).hostname; } catch (e) { h = ''; }
        }
        cb(S.hostKey(h), url);
      });
    } catch (e) { cb('', ''); }
  }

  function applyAccent() {
    var s = S.style(st.styleId);
    document.documentElement.style.setProperty('--vsc-c', s.accent);
    document.documentElement.style.setProperty('--vsc-c-light', S.lighten(s.accent, 0.42));
  }

  function render() {
    var r = currentRate();
    $('pNow').innerHTML = S.fmtHTML(r);
    $('svalNum').innerHTML = S.fmtHTML(r);
    var sl = $('slider');
    sl.min = String(st.minRate);
    sl.max = String(st.maxRate);
    sl.value = String(r);

    var box = $('chips');
    box.innerHTML = '';
    (st.speeds || []).slice().sort(function (a, b) { return a - b; }).forEach(function (v) {
      var num = Number(v);
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip' + (Math.abs(num - r) < 0.001 ? ' on' : '');
      b.innerHTML = S.fmtHTML(num);
      b.addEventListener('click', function () { setRate(num); });
      box.appendChild(b);
    });
  }

  function setRate(rate, quiet) {
    var r = clampRate(rate);
    var next = Object.assign({}, st);
    next.siteSpeeds = Object.assign({}, st.siteSpeeds);
    // 1× 也是合法选择，照常记录（与页面内 persistRate 保持一致）
    if (st.rememberPerSite) next.siteSpeeds[host] = r;
    next.globalSpeed = r;
    st = next;
    siteRate = r;
    S.saveSettings(st);
    render();
    if (!quiet) $('hint').textContent = '已设为 ' + S.fmt(r) + '，本网站立即生效';
  }

  function init() {
    applyAccent();
    render();

    document.querySelectorAll('[data-act]').forEach(function (b) {
      b.addEventListener('click', function () {
        var act = b.getAttribute('data-act');
        if (act === 'plus') setRate(currentRate() + Number(st.step));
        else if (act === 'minus') setRate(currentRate() - Number(st.step));
        else if (act === 'reset') setRate(1);
        else if (act === 'hide') hideCurrentSite();
        else if (act === 'options') { chrome.runtime.openOptionsPage(); window.close(); }
      });
    });
    $('slider').addEventListener('input', function () {
      setRate(Number($('slider').value), true);
      $('svalNum').innerHTML = S.fmtHTML(clampRate($('slider').value));
    });
  }

  function hideCurrentSite() {
    if (!host) return;
    var next = Object.assign({}, st);
    if (!S.isSiteExcluded(next.excludedSites, host)) {
      next.excludedSites = next.excludedSites.concat([host]);
      st = next;
      S.saveSettings(st);
    }
    $('hint').textContent = '已在本网站隐藏按钮（可在设置里恢复）';
    document.querySelector('[data-act="hide"]').disabled = true;
  }

  S.loadSettings(function (s) {
    st = Object.assign({}, S.DEFAULTS, s);
    if (!Array.isArray(st.speeds) || !st.speeds.length) st.speeds = S.DEFAULTS.speeds.slice();
    currentTab(function (h, url) {
      host = h;
      if (!host) {
        // 系统页 / 扩展页 / 空白页：说明情况，保留「设置」入口
        $('panel').innerHTML = '<div class="p-head"><span class="p-title">播放速度</span></div>' +
          '<div class="hint">当前页面无法识别网站（系统页 / 扩展页 / 空白页）。<br>' +
          '请在网页里使用本扩展，或点下面的「设置」。</div>' +
          '<div class="acts"><button class="act" type="button" data-act="options">设置</button></div>';
        applyAccent();
        init();
        return;
      }
      if (st.rememberPerSite && typeof st.siteSpeeds[host] === 'number') siteRate = st.siteSpeeds[host];
      if (S.isSiteExcluded(st.excludedSites, host)) {
        $('hint').textContent = '本网站已隐藏按钮（可在设置里恢复）';
        document.querySelector('[data-act="hide"]').disabled = true;
      } else {
        $('hint').textContent = '选择档位或拖动滑杆，本网站立即生效';
      }
      applyAccent();
      render();
      init();
    });
  });
})();
