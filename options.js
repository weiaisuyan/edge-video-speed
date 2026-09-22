/* 视频速度控制 — 设置页逻辑 */
(function () {
  'use strict';
  var S = window.VSC_SHARED;
  var NUM_KEYS = {
    posX: [0, 100], posY: [0, 100], size: [60, 500], radius: [0, 80],
    idleDelay: [1, 15], idleOpacity: [10, 100], hoverOpacity: [10, 100], step: [0.05, 1],
    minRate: [0.1, 10], maxRate: [0.1, 10], defaultSpeed: [0.1, 10], version: [0, 99]
  };
  var BOOL_KEYS = ['visible', 'showNumber', 'idleFade', 'showInFullscreen', 'enforce', 'hotkeys', 'rememberPerSite', 'respectSiteRate'];

  var st = Object.assign({}, S.DEFAULTS);
  var saveTimer = null;

  function $(id) { return document.getElementById(id); }
  function round2(v) { return Math.round(Number(v) * 100) / 100; }

  /* ---------- 读取 / 写入 ---------- */

  function sanitize(raw) {
    var out = Object.assign({}, S.DEFAULTS);
    if (!raw || typeof raw !== 'object') return out;
    BOOL_KEYS.forEach(function (k) { out[k] = raw[k] === undefined ? out[k] : !!raw[k]; });
    Object.keys(NUM_KEYS).forEach(function (k) {
      if (raw[k] === undefined) return;
      out[k] = S.clamp(raw[k], NUM_KEYS[k][0], NUM_KEYS[k][1]);
    });
    out.styleId = S.style(raw.styleId || raw.themeId).id;
    out.displayMode = raw.displayMode === 'always' ? 'always' : 'videoOnly';
    if (Array.isArray(raw.speeds)) {
      var seen = {};
      out.speeds = raw.speeds
        .map(function (v) { return S.cleanRate(v); })
        .filter(function (v) { var k = String(v); if (seen[k]) return false; seen[k] = 1; return true; })
        .sort(function (a, b) { return a - b; })
        .slice(0, 12);
    }
    if (!out.speeds.length) out.speeds = S.DEFAULTS.speeds.slice();
    if (Array.isArray(raw.excludedSites)) {
      var s2 = {};
      out.excludedSites = raw.excludedSites
        .map(function (v) { return S.normalizeSite(v); })
        .filter(function (v) { if (!v || s2[v]) return false; s2[v] = 1; return true; });
    }
    if (raw.siteSpeeds && typeof raw.siteSpeeds === 'object') {
      var ss = {};
      Object.keys(raw.siteSpeeds).forEach(function (k) {
        var nk = S.normalizeSite(k);
        var nv = Number(raw.siteSpeeds[k]);
        if (nk && isFinite(nv)) ss[nk] = S.cleanRate(nv);
      });
      out.siteSpeeds = ss;
    }
    out.globalSpeed = S.cleanRate(raw.globalSpeed === undefined ? 1 : raw.globalSpeed);
    return out;
  }

  function load() {
    S.loadSettings(function (s) {
      st = sanitize(s);
      renderAll();
    });
  }

  function save(now) {
    if (saveTimer) clearTimeout(saveTimer);
    if (now) { S.saveSettings(st); return; }
    saveTimer = setTimeout(function () { saveTimer = null; S.saveSettings(st); }, 150);
  }

  function set(key, val, now) { st[key] = val; save(now); }

  /* ---------- 渲染 ---------- */

  function renderAll() {
    $('verTag').textContent = 'v' + (chrome.runtime.getManifest().version);
    $('verTag2').textContent = 'v' + (chrome.runtime.getManifest().version);

    $('visible').checked = !!st.visible;
    $('showInFullscreen').checked = !!st.showInFullscreen;
    $('enforce').checked = !!st.enforce;
    $('respectSiteRate').checked = !!st.respectSiteRate;
    $('showNumber').checked = !!st.showNumber;
    $('idleFade').checked = !!st.idleFade;
    $('hotkeys').checked = !!st.hotkeys;
    $('rememberPerSite').checked = !!st.rememberPerSite;

    ['videoOnly', 'always'].forEach(function (v) {
      var b = document.querySelector('#displayMode button[data-v="' + v + '"]');
      if (b) b.classList.toggle('on', st.displayMode === v);
    });

    $('size').value = st.size; $('sizeVal').textContent = sizeLabelText();
    $('radius').value = st.radius; $('radiusVal').textContent = st.radius + '%';
    $('hoverOpacity').value = st.hoverOpacity; $('hoverOpacityVal').textContent = st.hoverOpacity + '%';
    $('idleDelay').value = st.idleDelay; $('idleDelayVal').textContent = st.idleDelay + ' 秒';
    $('idleOpacity').value = st.idleOpacity; $('idleOpacityVal').textContent = st.idleOpacity + '%';
    $('step').value = st.step; $('stepVal').textContent = String(st.step);
    $('idleDelay').disabled = !st.idleFade;
    $('idleOpacity').disabled = !st.idleFade;

    renderSpeeds();
    renderStyles();
    renderSites();
    renderRates();
    renderPreview();
    renderPos();
  }

  function applyMockAccent() {
    var mp = $('mockPanel');
    if (mp) mp.style.setProperty('--mp-accent', S.style(st.styleId).accent);
  }

  // 档位编辑区 = 页面上菜单的真实样子（深色面板 / 三列网格 / −+ 与滑杆 / 数值在滑杆下方）
  function renderSpeeds() {
    var box = $('speedChips');
    box.innerHTML = '';
    st.speeds.forEach(function (r) {
      var on = Math.abs(r - st.defaultSpeed) < 0.001;
      var d = document.createElement('div');
      d.className = 'chip mp-chip' + (on ? ' on' : '');
      d.innerHTML = '<span>' + S.fmt(r) + '</span><button type="button" class="del" title="删除该档位">×</button>';
      d.addEventListener('click', function (e) {
        if (e.target && e.target.classList.contains('del')) {
          if (st.speeds.length <= 1) return;
          st.speeds = st.speeds.filter(function (x) { return Math.abs(x - r) > 0.001; });
          if (Math.abs(st.defaultSpeed - r) < 0.001) st.defaultSpeed = st.speeds[0];
          save(true);
          renderSpeeds();
          return;
        }
        st.defaultSpeed = r;      // 点档位本身 = 设为默认速度
        save(true);
        renderSpeeds();
      });
      box.appendChild(d);
    });
    renderMockState();
  }

  function renderMockState() {
    var v = S.fmt(st.defaultSpeed);
    if ($('mpNow')) $('mpNow').textContent = v;
    if ($('mpSval')) $('mpSval').textContent = v;
    if ($('mpSlider')) $('mpSlider').value = String(st.defaultSpeed);
    applyMockAccent();
  }

  // 只更新「哪一档被选中」的高亮，不重建 DOM（滑杆拖动时用，避免输入被打断）
  function renderSpeedChipsOn() {
    var box = $('speedChips');
    if (!box) return;
    var chips = box.querySelectorAll('.chip');
    for (var i = 0; i < chips.length; i++) {
      var t = (chips[i].querySelector('span') || {}).textContent || '';
      chips[i].classList.toggle('on', t.trim() === S.fmt(st.defaultSpeed));
    }
  }

  function bumpDefault(dir) {
    st.defaultSpeed = S.cleanRate(Number(st.defaultSpeed) + dir * Number(st.step));
    save(true);
    renderSpeeds();
  }

  function renderStyles() {
    var box = $('styles');
    box.innerHTML = '';
    S.GROUPS.forEach(function (g) {
      var row = document.createElement('div');
      row.className = 'stgroup';
      var nm = document.createElement('div');
      nm.className = 'stgname';
      nm.textContent = g.name;
      var cells = document.createElement('div');
      cells.className = 'strow';
      S.STYLES.filter(function (s) { return s.group === g.id; }).forEach(function (s) {
        var c = document.createElement('div');
        c.className = 'stcell' + (s.id === st.styleId ? ' on' : '');
        var pill = document.createElement('div');
        pill.className = 'stpill';
        pill.style.background = s.bg;
        pill.style.color = s.fg || '#ffffff';
        if (s.bd) pill.style.border = s.bd;
        if (s.blur) {
          pill.style.backdropFilter = 'blur(' + s.blur + 'px)';
          pill.style.webkitBackdropFilter = 'blur(' + s.blur + 'px)';
        }
        if (s.glow) pill.style.boxShadow = '0 0 9px 1px ' + s.glow;
        pill.textContent = '1.5×';
        var label = document.createElement('div');
        label.className = 'stname';
        label.textContent = s.name;
        c.appendChild(pill);
        c.appendChild(label);
        c.addEventListener('click', function () {
          st.styleId = s.id;
          save(true);
          renderStyles();
          renderPreview();
          renderPos();
        });
        cells.appendChild(c);
      });
      row.appendChild(nm);
      row.appendChild(cells);
      box.appendChild(row);
    });
  }

  function sizeLabelText() {
    return st.size + '%' + (st.size > 200 ? '（预览按 200% 缩小显示）' : '');
  }

  function paintPvBtn(el, s, pv) {
    el.style.background = s.bg;
    el.style.color = s.fg || '#ffffff';
    el.style.border = s.bd || 'none';
    el.style.backdropFilter = s.blur ? 'blur(' + s.blur + 'px)' : 'none';
    el.style.webkitBackdropFilter = s.blur ? 'blur(' + s.blur + 'px)' : 'none';
    el.style.boxShadow = s.glow ? '0 0 10px 1px ' + s.glow : '0 2px 8px rgba(0,0,0,.25)';
    el.style.fontSize = Math.round(12 * pv) + 'px';
    el.style.height = Math.round(30 * pv) + 'px';
    el.style.borderRadius = Math.round(30 * pv * st.radius / 100) + 'px';
    el.textContent = st.showNumber ? '1.5×' : '▶';
  }

  function renderPreview() {
    var s = S.style(st.styleId);
    var pv = Math.min(st.size, 200) / 100;   // 预览区装不下 500%，按 200% 上限显示
    var hov = $('pvBtn'), idl = $('pvBtnIdle');
    if (hov) {
      paintPvBtn(hov, s, pv);
      hov.style.opacity = String(st.hoverOpacity / 100);
    }
    if (idl) {
      paintPvBtn(idl, s, pv);
      idl.style.opacity = String((st.idleFade ? st.idleOpacity : st.hoverOpacity) / 100);
    }
    if ($('pvCapHover')) $('pvCapHover').textContent = '悬停时 ' + st.hoverOpacity + '%';
    if ($('pvCapIdle')) {
      $('pvCapIdle').textContent = st.idleFade ? ('移开后 ' + st.idleOpacity + '%') : '移开后（未开启淡化）';
    }
  }

  function renderSites() {
    var box = $('siteList');
    box.innerHTML = '';
    if (!st.excludedSites.length) {
      box.innerHTML = '<div class="empty">暂无排除的网站</div>';
    } else {
      st.excludedSites.forEach(function (s) {
        var d = document.createElement('div');
        d.className = 'li';
        d.innerHTML = '<span>' + s + '</span><button type="button" title="移除">×</button>';
        d.querySelector('button').addEventListener('click', function () {
          st.excludedSites = st.excludedSites.filter(function (x) { return x !== s; });
          save(true); renderSites();
        });
        box.appendChild(d);
      });
    }
  }

  function renderRates() {
    var box = $('rateList');
    box.innerHTML = '';
    // 1× = 默认值，不列出来（只显示你主动调过的非 1× 记录）
    var keys = Object.keys(st.siteSpeeds || {}).filter(function (k) {
      return Math.abs(Number(st.siteSpeeds[k]) - 1) > 0.001;
    });
    if (!keys.length) {
      box.innerHTML = '<div class="empty">暂无记录（1× 不记录；在页面上调过非 1× 的速度后就会出现在这里）</div>';
      return;
    }
    keys.sort().forEach(function (k) {
      var d = document.createElement('div');
      d.className = 'li';
      d.innerHTML = '<span>' + k + '</span><span class="mono">' + S.fmt(st.siteSpeeds[k]) + '</span>';
      var b = document.createElement('button');
      b.type = 'button'; b.title = '清除该记录'; b.textContent = '×';
      b.addEventListener('click', function () {
        delete st.siteSpeeds[k];
        save(true); renderRates();
      });
      d.appendChild(b);
      box.appendChild(d);
    });
  }

  /* ---------- 位置模拟窗口 ---------- */

  function renderPos() {
    $('posVal').textContent = st.posX + '% / ' + st.posY + '%';
    var m = $('mock'), b = $('mockBtn');
    var barH = m.querySelector('.mock-bar').offsetHeight || 26;
    var w = m.clientWidth, h = m.clientHeight - barH;
    var bw = b.offsetWidth || 46, bh = b.offsetHeight || 28;
    b.style.fontSize = Math.round(12 * Math.min(st.size, 200) / 100) + 'px';
    b.style.borderRadius = Math.round(28 * Math.min(st.size, 200) / 100 * st.radius / 100) + 'px';
    var s2 = S.style(st.styleId);
    b.style.background = s2.bg;
    b.style.color = s2.fg || '#ffffff';
    b.style.border = s2.bd || 'none';
    b.textContent = st.showNumber ? S.fmt(st.defaultSpeed) : '▶';
    var x = Math.min(w - bw - 6, Math.max(6, w * st.posX / 100));
    var y = Math.min(h - bh - 6, Math.max(6, h * st.posY / 100));
    b.style.left = Math.round(x) + 'px';
    b.style.top = Math.round(y + barH) + 'px';
  }

  function mockMove(ev) {
    var m = $('mock'), b = $('mockBtn');
    var rect = m.getBoundingClientRect();
    var barH = m.querySelector('.mock-bar').offsetHeight || 26;
    var w = m.clientWidth, h = m.clientHeight - barH;
    var bw = b.offsetWidth || 46, bh = b.offsetHeight || 28;
    var x = Math.min(w - bw - 6, Math.max(6, ev.clientX - rect.left - bw / 2));
    var y = Math.min(h - bh - 6, Math.max(6, ev.clientY - rect.top - barH - bh / 2));
    st.posX = Math.round(x / w * 1000) / 10;
    st.posY = Math.round(y / h * 1000) / 10;
    renderPos();
    save();
  }

  /* ---------- 备份 ---------- */

  function exportSettings() {
    var data = { app: 'video-speed-control', version: chrome.runtime.getManifest().version, exportedAt: new Date().toISOString(), settings: st };
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    var d = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    a.href = url;
    a.download = 'video-speed-settings-' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '-' +
      pad(d.getHours()) + pad(d.getMinutes()) + '.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
    $('backupMsg').textContent = '已导出。';
  }

  function importSettings(file) {
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var obj = JSON.parse(String(fr.result));
        var raw = obj && obj.settings ? obj.settings : obj;
        if (!raw || typeof raw !== 'object' || !Object.keys(raw).length) throw new Error('empty');
        st = sanitize(raw);
        S.saveSettings(st);
        renderAll();
        $('backupMsg').textContent = '已导入并生效。';
      } catch (e) {
        $('backupMsg').textContent = '导入失败：文件不是有效的设置 JSON。';
      }
    };
    fr.readAsText(file);
  }

  /* ---------- 事件绑定 ---------- */

  function bind() {
    $('visible').addEventListener('change', function (e) { set('visible', e.target.checked); });
    $('showInFullscreen').addEventListener('change', function (e) { set('showInFullscreen', e.target.checked); });
    $('enforce').addEventListener('change', function (e) { set('enforce', e.target.checked); });
    $('respectSiteRate').addEventListener('change', function (e) { set('respectSiteRate', e.target.checked); });
    $('showNumber').addEventListener('change', function (e) { set('showNumber', e.target.checked); renderPreview(); renderPos(); });
    $('idleFade').addEventListener('change', function (e) {
      set('idleFade', e.target.checked);
      $('idleDelay').disabled = !e.target.checked;
      $('idleOpacity').disabled = !e.target.checked;
    });
    $('hotkeys').addEventListener('change', function (e) { set('hotkeys', e.target.checked); });
    $('rememberPerSite').addEventListener('change', function (e) { set('rememberPerSite', e.target.checked); });

    document.querySelectorAll('#displayMode button').forEach(function (b) {
      b.addEventListener('click', function () {
        st.displayMode = b.getAttribute('data-v');
        save(true);
        document.querySelectorAll('#displayMode button').forEach(function (x) { x.classList.toggle('on', x === b); });
      });
    });

    $('size').addEventListener('input', function (e) {
      st.size = Number(e.target.value); $('sizeVal').textContent = sizeLabelText();
      renderPreview(); renderPos(); save();
    });
    $('radius').addEventListener('input', function (e) {
      st.radius = Number(e.target.value); $('radiusVal').textContent = st.radius + '%';
      renderPreview(); renderPos(); save();
    });
    $('hoverOpacity').addEventListener('input', function (e) {
      st.hoverOpacity = Number(e.target.value); $('hoverOpacityVal').textContent = st.hoverOpacity + '%';
      renderPreview(); save();
    });
    $('idleDelay').addEventListener('input', function (e) {
      st.idleDelay = Number(e.target.value); $('idleDelayVal').textContent = st.idleDelay + ' 秒'; save();
    });
    $('idleOpacity').addEventListener('input', function (e) {
      st.idleOpacity = Number(e.target.value); $('idleOpacityVal').textContent = st.idleOpacity + '%'; save();
    });
    $('step').addEventListener('input', function (e) {
      st.step = round2(e.target.value); $('stepVal').textContent = String(st.step); save();
    });
    $('mpSlider').addEventListener('input', function (e) {
      st.defaultSpeed = S.cleanRate(e.target.value);
      renderMockState();
      renderSpeedChipsOn();
      save();
    });
    $('mpMinus').addEventListener('click', function () { bumpDefault(-1); });
    $('mpPlus').addEventListener('click', function () { bumpDefault(1); });

    $('addSpeed').addEventListener('click', function () {
      var v = Number($('newSpeed').value);
      if (!isFinite(v) || v < S.DEFAULTS.minRate || v > S.DEFAULTS.maxRate) {
        $('newSpeed').value = '';
        $('newSpeed').placeholder = '请输入 0.1–10 之间的数值';
        return;
      }
      var r = S.cleanRate(v);
      if (st.speeds.some(function (x) { return Math.abs(x - r) < 0.001; })) { $('newSpeed').value = ''; return; }
      if (st.speeds.length >= 12) { $('newSpeed').value = ''; $('newSpeed').placeholder = '最多 12 个档位'; return; }
      st.speeds = st.speeds.concat([r]).sort(function (a, b) { return a - b; });
      $('newSpeed').value = '';
      save(true); renderSpeeds();
    });
    $('resetSpeeds').addEventListener('click', function () {
      st.speeds = S.DEFAULTS.speeds.slice();
      st.defaultSpeed = 1;
      save(true); renderSpeeds();
    });

    $('resetPos').addEventListener('click', function () {
      st.posX = S.DEFAULTS.posX; st.posY = S.DEFAULTS.posY;
      save(true); renderPos();
    });

    var dragging = false;
    $('mock').addEventListener('pointerdown', function (e) {
      if (e.target.closest('.mock-bar')) return;
      dragging = true;
      try { $('mock').setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
      mockMove(e);
    });
    $('mock').addEventListener('pointermove', function (e) { if (dragging) mockMove(e); });
    $('mock').addEventListener('pointerup', function (e) {
      dragging = false;
      try { $('mock').releasePointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
      save(true);
    });
    window.addEventListener('resize', renderPos);

    $('addSite').addEventListener('click', function () {
      var raw = $('newSite').value;
      var n = S.normalizeSite(raw);
      if (!n) { $('siteErr').textContent = '请输入有效域名，例如 bilibili.com'; return; }
      if (st.excludedSites.indexOf(n) !== -1) { $('siteErr').textContent = '该网站已在清单中'; return; }
      st.excludedSites = st.excludedSites.concat([n]);
      $('newSite').value = '';
      $('siteErr').textContent = '';
      save(true); renderSites();
    });
    $('newSite').addEventListener('keydown', function (e) { if (e.key === 'Enter') $('addSite').click(); });

    $('clearRates').addEventListener('click', function () {
      if (!confirm('清空所有「按网站记住的速度」记录？')) return;
      st.siteSpeeds = {};
      save(true); renderRates();
    });

    $('exportBtn').addEventListener('click', exportSettings);
    $('importBtn').addEventListener('click', function () { $('importFile').click(); });
    $('importFile').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (f) importSettings(f);
      e.target.value = '';
    });

    $('resetAll').addEventListener('click', function () {
      if (!confirm('恢复出厂设置？所有自定义档位、位置、排除清单与速度记录都会被清空。')) return;
      st = Object.assign({}, S.DEFAULTS, { speeds: S.DEFAULTS.speeds.slice(), excludedSites: [], siteSpeeds: {} });
      S.saveSettings(st);
      renderAll();
      $('backupMsg').textContent = '已恢复出厂设置。';
    });
  }

  bind();
  load();
})();
