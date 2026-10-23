/* 总后台前端核心：请求、登录与改密、页面框架、路由、个人设置。原生 JS，无构建、无外部依赖（断网可用）。
   各页面在 views/*.js 里通过 LG.view(name, {title, icon, admin, render, rail}) 注册。 */
(function () {
  'use strict';
  var LG = window.LG = { views: {}, S: { me: null, tree: [], treeAt: 0 } };
  var icon = window.icon;

  // ---------------- 小工具 ----------------
  LG.$ = function (sel, el) { return (el || document).querySelector(sel); };
  LG.$$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };
  LG.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  LG.fmt = function (v, d, unit) { return v == null || v === '' || isNaN(v) ? '--' : Number(v).toFixed(d) + (unit || ''); };
  LG.ago = function (ts) {
    if (!ts) return '从未';
    var s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return Math.round(s) + ' s';
    if (s < 3600) return Math.round(s / 60) + ' min';
    if (s < 86400) return Math.round(s / 3600) + ' h';
    return Math.round(s / 86400) + ' d';
  };
  LG.time = function (ts) {
    var d = new Date(ts * 1000), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  };
  LG.icon = icon;
  LG.isAdmin = function () { return LG.S.me && LG.S.me.role === 'admin'; };

  // 风险等级 → 显示
  LG.LV = {
    high: { text: '高危', tag: 'tag t-high', color: 'var(--high)', card: 'high' },
    mid: { text: '中危', tag: 'tag t-mid', color: 'var(--mid)', card: '' },
    low: { text: '低危', tag: 'tag t-low', color: 'var(--low)', card: '' },
    off: { text: '离线', tag: 'tag t-off', color: 'var(--mute-line)', card: 'off' },
    none: { text: '未接入', tag: 'tag t-off', color: 'var(--mute-line)', card: 'off' }
  };
  LG.deskLevel = function (d) {
    if (!d) return 'none';
    if (!d.online) return 'off';
    if (d.latched) return 'high';
    return d.risk_level || 'low';
  };

  // ---------------- 提示与弹层 ----------------
  LG.toast = function (msg, err) {
    var t = LG.$('#toast');
    t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false;
    clearTimeout(LG.toast._t); LG.toast._t = setTimeout(function () { t.hidden = true; }, err ? 6000 : 3600);
  };
  LG.dialog = function (title, bodyHtml, onMount) {
    var d = LG.$('#dialog');
    d.innerHTML = '<div class="ph">' + LG.esc(title) + '<span class="sp"></span><button class="btn sm flat" data-close aria-label="关闭">' + icon('x', 16) + '</button></div>' +
      '<div class="pad">' + bodyHtml + '</div>';
    LG.$('#mask').hidden = false;
    LG.$$('[data-close]', d).forEach(function (b) { b.onclick = LG.closeDialog; });
    if (onMount) onMount(d);
    var f = LG.$('input, select, textarea, button.pri', d); if (f) f.focus();
  };
  LG.closeDialog = function () { LG.$('#mask').hidden = true; LG.$('#dialog').innerHTML = ''; };
  LG.$('#mask').addEventListener('click', function (e) { if (e.target.id === 'mask') LG.closeDialog(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !LG.$('#mask').hidden) LG.closeDialog(); });
  LG.confirm = function (title, html, okText, danger) {
    return new Promise(function (resolve) {
      LG.dialog(title, html + '<div class="row" style="padding: 0; border: 0"><button class="btn ' + (danger ? 'dng' : 'pri') + '" data-ok>' +
        LG.esc(okText || '确定') + '</button><button class="btn" data-close>取消</button></div>', function (d) {
        LG.$('[data-ok]', d).onclick = function () { LG.closeDialog(); resolve(true); };
        LG.$$('[data-close]', d).forEach(function (b) { b.onclick = function () { LG.closeDialog(); resolve(false); }; });
      });
    });
  };
  LG.secret = function (title, label, value, note) {
    LG.dialog(title, '<div class="lbl">' + LG.esc(label) + '</div><div class="secret">' + LG.esc(value) + '</div>' +
      (note ? '<div class="mut">' + LG.esc(note) + '</div>' : '') +
      '<div class="row" style="padding: 0; border: 0"><button class="btn pri" data-copy>' + icon('doc', 16) + '复制</button><button class="btn" data-close>完成</button></div>',
      function (d) {
        LG.$('[data-copy]', d).onclick = function () {
          (navigator.clipboard ? navigator.clipboard.writeText(value) : Promise.reject()).then(function () { LG.toast('已复制'); },
            function () { LG.toast('请手动选中复制'); });
        };
      });
  };

  // ---------------- 请求 ----------------
  LG.api = function (method, path, body, raw) {
    var opt = { method: method, credentials: 'same-origin', headers: {} };
    if (raw !== undefined) { opt.body = raw; opt.headers['Content-Type'] = 'application/octet-stream'; }
    else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (r.status === 401 && path !== '/api/login') { gate('login'); throw new Error('请先登录'); }
        if (r.status === 403 && /修改密码/.test(j.detail || '')) { gate('password'); throw new Error(j.detail); }
        if (!r.ok) {
          var d = j.detail, msg = typeof d === 'string' ? d : d && d.errors ? Object.keys(d.errors).map(function (k) { return d.errors[k]; }).join('；') : '请求失败（' + r.status + '）';
          var e = new Error(msg); e.status = r.status; e.detail = d; throw e;
        }
        return j;
      });
    });
  };
  LG.fail = function (e) { if (e && e.message !== '请先登录') LG.toast(e.message || String(e), true); };

  // 区域树（缓存 10 秒）
  LG.loadTree = function (force) {
    if (!force && LG.S.tree.length && Date.now() - LG.S.treeAt < 10000) return Promise.resolve(LG.S.tree);
    return LG.api('GET', '/api/tree').then(function (t) { LG.S.tree = t; LG.S.treeAt = Date.now(); return t; });
  };
  LG.areaById = function (id) { return LG.S.tree.filter(function (a) { return a.id === id; })[0]; };
  LG.children = function (pid) { return LG.S.tree.filter(function (a) { return a.parent_id === pid; }); };
  LG.pathOf = function (id) {
    var out = [], a = LG.areaById(id), guard = 0;
    while (a && guard++ < 20) { out.unshift(a.name); a = LG.areaById(a.parent_id); }
    return out.join(' / ');
  };
  // 深度优先展开，带层级
  LG.flatTree = function (filter) {
    var out = [];
    (function walk(pid, depth) {
      LG.children(pid).forEach(function (a) {
        if (!filter || filter(a)) out.push({ a: a, depth: depth });
        walk(a.id, depth + 1);
      });
    })(null, 0);
    // 父节点不可见时（老师只被授权了某张桌），把孤立子树也补上
    LG.S.tree.forEach(function (a) {
      if (a.parent_id !== null && !LG.areaById(a.parent_id) && !out.some(function (x) { return x.a.id === a.id; })) {
        if (!filter || filter(a)) out.push({ a: a, depth: 0 });
      }
    });
    return out;
  };
  LG.KIND = { group: '楼栋 / 分组', room: '房间', desk: '实验桌' };

  // ---------------- 界面风格 ----------------
  LG.applyStyle = function () {
    var px = LG.S.me && LG.S.me.ui_style === 'pixel';
    if (px) document.documentElement.setAttribute('data-ui', 'pixel'); else document.documentElement.removeAttribute('data-ui');
  };

  // ---------------- 登录 / 改密 ----------------
  function gate(kind) {
    stopTimers();
    var root = LG.$('#root');
    var form = kind === 'login' ?
      '<label class="lbl">用户名<input class="fld" id="gUser" autocomplete="username" required></label>' +
      '<label class="lbl">密码<input class="fld" id="gPw" type="password" autocomplete="current-password" required></label>' +
      '<div class="err-line" id="gErr"></div><button class="btn pri" id="gGo" type="submit">' + icon('key', 18) + '登录</button>' :
      '<div class="mut">首次登录或密码已重置，请设置新密码（≥ 8 位，含字母和数字）</div>' +
      '<label class="lbl">当前密码<input class="fld" id="gOld" type="password" autocomplete="current-password" required></label>' +
      '<label class="lbl">新密码<input class="fld" id="gNew" type="password" autocomplete="new-password" required></label>' +
      '<label class="lbl">确认新密码<input class="fld" id="gNew2" type="password" autocomplete="new-password" required></label>' +
      '<div class="err-line" id="gErr"></div><div style="display:flex;gap:10px"><button class="btn pri" type="submit">' + icon('check', 18) + '确认修改</button>' +
      '<button class="btn" type="button" id="gOut">' + icon('logout', 18) + '退出</button></div>';
    root.innerHTML = '<div class="gate"><form class="panel" id="gForm">' +
      '<div class="brand">' + icon('logo', 28) + '<span class="hd">实验室安全监管平台</span></div>' +
      '<div class="ph dk">' + (kind === 'login' ? '账号登录' : '修改密码') + '</div>' +
      '<div class="pad" style="display:flex;flex-direction:column;gap:12px">' + form + '</div></form></div>';
    var err = function (m) { LG.$('#gErr').textContent = m; };
    if (kind === 'password') LG.$('#gOut').onclick = logout;
    LG.$('#gForm').onsubmit = function (e) {
      e.preventDefault();
      if (kind === 'login') {
        LG.api('POST', '/api/login', { username: LG.$('#gUser').value.trim(), password: LG.$('#gPw').value }).then(function (r) {
          LG.S.me = r.user;
          if (r.user.must_change) gate('password'); else boot();
        }).catch(function (x) { err(x.message); });
      } else {
        if (LG.$('#gNew').value !== LG.$('#gNew2').value) return err('两次输入的新密码不一致');
        LG.api('POST', '/api/me/password', { old: LG.$('#gOld').value, new: LG.$('#gNew').value }).then(function () {
          LG.toast('密码已修改'); boot();
        }).catch(function (x) { err(x.message); });
      }
    };
    var first = LG.$('input', root); if (first) first.focus();
  }
  function logout() {
    LG.api('POST', '/api/logout').catch(function () {}).then(function () { LG.S.me = null; LG.applyStyle(); gate('login'); });
  }
  LG.logout = logout;

  // ---------------- 个人设置 ----------------
  function prefs() {
    var me = LG.S.me;
    LG.dialog('个人设置',
      '<div class="row" style="padding:0;border:0">' + icon('user') + '<b>' + LG.esc(me.display_name) + '</b><span class="mut num">' + LG.esc(me.username) + '</span>' +
      '<span class="tag ' + (me.role === 'admin' ? 't-ink' : 't-soft') + '">' + (me.role === 'admin' ? '管理员' : '教师') + '</span></div>' +
      '<div class="lbl">界面风格<div class="seg" style="align-self:flex-start"><button class="btn" data-s="standard">标准</button><button class="btn" data-s="pixel">像素（旧版）</button></div></div>' +
      '<div class="mut">像素风格使用旧版 Zpix 字体，仅对本账号生效。</div>' +
      '<div class="row" style="padding:0;border:0"><button class="btn" data-pw>' + icon('lock', 18) + '修改密码</button><button class="btn" data-out>' + icon('logout', 18) + '退出登录</button></div>',
      function (d) {
        var paint = function () { LG.$$('[data-s]', d).forEach(function (b) { b.classList.toggle('on', b.dataset.s === (LG.S.me.ui_style || 'standard')); }); };
        paint();
        LG.$$('[data-s]', d).forEach(function (b) {
          b.onclick = function () {
            LG.api('PATCH', '/api/me/prefs', { ui_style: b.dataset.s }).then(function (r) {
              LG.S.me = r.user; LG.applyStyle(); paint();
            }).catch(LG.fail);
          };
        });
        LG.$('[data-pw]', d).onclick = function () { LG.closeDialog(); gate('password'); };
        LG.$('[data-out]', d).onclick = function () { LG.closeDialog(); logout(); };
      });
  }

  // ---------------- 页面框架与路由 ----------------
  LG.view = function (name, def) { def.name = name; LG.views[name] = def; };
  var RAIL = ['overview', 'desk', 'rules', 'models', 'voice', 'areas', 'access'];
  var timers = [];
  LG.every = function (ms, fn) { fn(); timers.push(setInterval(fn, ms)); };
  LG.later = function (ms, fn) { timers.push(setTimeout(fn, ms)); };
  function stopTimers() { timers.forEach(function (t) { clearInterval(t); clearTimeout(t); }); timers = []; }
  LG.route = function () {
    var parts = (location.hash.replace(/^#\/?/, '') || 'overview').split('/');
    return { name: parts[0], arg: parts[1] ? decodeURIComponent(parts[1]) : null };
  };
  LG.go = function (hash) { if (location.hash === hash) render(); else location.hash = hash; };
  LG.setCrumb = function (html) { var c = LG.$('#crumb'); if (c) c.innerHTML = html; };

  function frame() {
    var me = LG.S.me;
    var scope = me.role === 'admin' ? '全部区域' : (LG.S.scopeText || '');
    return '<div class="shell"><header class="panel top">' +
      '<div class="brand">' + icon('logo', 28) + '<span class="hd">实验室安全监管平台</span></div>' +
      '<div class="crumb" id="crumb"></div>' +
      '<div class="who"><span class="mut" style="display:flex;align-items:center;gap:6px">' + icon('clock') + '<span class="num" id="clock"></span></span>' +
      '<button class="tag t-soft" style="height:28px;cursor:pointer" id="btnMe">' + icon('user', 16) + LG.esc(me.display_name) + ' · ' + (me.role === 'admin' ? '系统管理员' : '教师') + '</button>' +
      '<span class="tag" style="height:28px" title="' + LG.esc(scope) + '">授权范围 ' + LG.esc(scope.length > 24 ? scope.slice(0, 24) + '…' : scope) + '</span>' +
      '<button class="btn" id="btnOut" aria-label="退出登录">' + icon('logout') + '</button></div></header>' +
      '<div class="body"><nav class="panel rail" aria-label="主导航" id="rail"></nav><main class="main" id="main"></main></div></div>';
  }
  function railHtml(cur) {
    return RAIL.filter(function (n) { var v = LG.views[n]; return v && (!v.admin || LG.isAdmin()); }).map(function (n) {
      var v = LG.views[n];
      return '<a href="#/' + n + '"' + (n === cur ? ' class="on" aria-current="page"' : '') + '>' + icon(v.icon) + LG.esc(v.rail || v.title) + '</a>';
    }).join('');
  }
  function render() {
    stopTimers();
    LG.closeDialog();
    if (!LG.$('#main')) {
      LG.$('#root').innerHTML = frame();
      LG.$('#btnMe').onclick = prefs;
      LG.$('#btnOut').onclick = logout;
    }
    LG.every(1000, function () {
      var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
      var c = LG.$('#clock'); if (c) c.textContent = p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
    });
    var r = LG.route(), v = LG.views[r.name];
    if (!v || (v.admin && !LG.isAdmin())) { location.hash = '#/overview'; return; }
    LG.$('#rail').innerHTML = railHtml(r.name);
    LG.setCrumb('<b>' + LG.esc(v.title) + '</b>');
    document.title = v.title + ' · 实验室安全监管平台';
    var old = LG.$('#main'), main = old.cloneNode(false);   // 换一个新容器，旧页面绑定的事件随之丢弃
    old.parentNode.replaceChild(main, old);
    main.innerHTML = '<div class="panel empty">加载中…</div>';
    window.scrollTo(0, 0);
    LG.loadTree().then(function () { v.render(main, r.arg); }).catch(function (e) {
      main.innerHTML = '<div class="panel empty">' + LG.esc(e.message) + '</div>';
    });
  }
  window.addEventListener('hashchange', function () { if (LG.S.me && !LG.S.me.must_change) render(); });

  function scopeText(grants) {
    return grants.map(function (id) { return LG.pathOf(id).split(' / ').slice(-2).join(' / '); }).join('、') || '未授权';
  }
  function boot() {
    LG.api('GET', '/api/me').then(function (r) {
      LG.S.me = r.user;
      LG.applyStyle();
      if (r.user.must_change) return gate('password');
      LG.$('#root').innerHTML = '';
      return LG.loadTree(true).then(function () { LG.S.scopeText = scopeText(r.grants || []); render(); });
    }).catch(function (e) { if (e.message !== '请先登录') gate('login'); });
  }
  LG.boot = boot;
  document.addEventListener('DOMContentLoaded', boot);
})();
