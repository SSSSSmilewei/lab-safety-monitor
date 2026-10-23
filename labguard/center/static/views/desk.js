/* 实验桌详情：双路画面、传感器、交叉验证、安全助手问答、远程操作、事件记录（1.5 秒刷新） */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var chats = {};          // 每张桌的问答历史（只在本页面会话内保留）
  var LEVEL_TAG = { CRITICAL: ['紧急', 't-high'], WARNING: ['警告', 't-mid'], NOTICE: ['提醒', 't-soft'], INFO: ['信息', 't-soft'] };
  var QUICK = ['当前风险等级与主要原因？', '处置建议？', '可否暂离实验台？'];

  function picker(main) {
    var desks = LG.flatTree(function (a) { return a.kind === 'desk' && a.managed; });
    LG.setCrumb('<b>实验桌</b>');
    main.innerHTML = '<section class="panel"><div class="ph">' + icon('desk') + '选择实验桌</div>' +
      (desks.length ? desks.map(function (x) {
        var n = x.a.node, lv = LG.deskLevel(n), L = LG.LV[lv];
        return '<a class="tree" href="#/desk/' + x.a.id + '" style="text-decoration:none"><i class="dot" aria-hidden="true" style="background:' + L.color + '"></i>' +
          '<span class="grow">' + esc(LG.pathOf(x.a.id)) + '</span><span class="' + L.tag + '">' + L.text + '</span></a>';
      }).join('') : '<div class="empty">无可查看的实验桌</div>') + '</section>';
  }

  function camHtml(which, title, ic) {
    return '<figure class="panel cam"><figcaption class="ph">' + icon(ic) + title + '<span class="sp"></span><small class="num" id="fps-' + which + '"></small></figcaption>' +
      '<div class="view"><img id="img-' + which + '" alt="' + title + '画面" hidden><span id="noimg-' + which + '">画面加载中…</span></div></figure>';
  }

  function sensorsHtml(s) {
    var t = s.telemetry || {}, wm = s.world_model || {}, r = s.rules || {};
    var eta = wm.eta_s != null ? '预计 ' + Math.round(wm.eta_s) + ' s 后干烧' : wm.eta_boil_s != null ? '预计 ' + Math.max(1, Math.round(wm.eta_boil_s / 60)) + ' min 后沸腾' : (wm.phase_text || '');
    var cell = function (ic, label, val, unit, sub, last) {
      return '<div class="stat"' + (last ? ' style="border-right:0"' : '') + '>' + icon(ic, 28) + '<div><div class="mut">' + label + '</div><div class="big">' + val +
        (unit ? '<span style="font-size:16px">' + unit + '</span>' : '') + '</div>' + (sub ? '<div class="mut">' + sub + '</div>' : '') + '</div></div>';
    };
    return cell('thermo', '热源温度', LG.fmt(t.obj_temp, 1), '℃', esc(eta) + (r.dry_burn_c ? ' · 断电 <span class="num">' + r.dry_burn_c + '℃</span>' : '')) +
      cell('building', '环境温度', LG.fmt(t.temp, 1), '℃') +
      cell('drop', '相对湿度', LG.fmt(t.humi, 0), '%') +
      cell('smoke', '烟雾 MQ-2', t.smoke == null ? '--' : t.smoke, '', r.smoke_raw ? '断电 <span class="num">' + r.smoke_raw + '</span>' : '', true);
  }

  function crossHtml(s) {
    var k = s.risk || {}, lv = k.level || 'low', score = k.score || 0;
    var th = k.thresholds || { mid: 30, high: 70 };
    var col = { high: 'var(--high)', mid: 'var(--mid)', low: '#2EBD85' }[lv];
    var bg = { high: 'var(--high-bg)', mid: 'var(--mid-bg)', low: 'var(--low-bg)' }[lv];
    var voice = { high: '严厉干预', mid: '温和提醒', low: '静默' }[lv];
    var lightName = { high: '红', mid: '黄', low: '绿' }[lv];
    var factors = (k.factors || []).slice().sort(function (a, b) { return b.points - a.points; });
    return '<div style="display:flex;align-items:stretch;border-bottom:2px solid var(--ink)">' +
      '<div class="light" aria-hidden="true"><i class="' + (lv === 'high' ? 'on-r' : '') + '"></i><i class="' + (lv === 'mid' ? 'on-y' : '') + '"></i><i class="' + (lv === 'low' ? 'on-g' : '') + '"></i></div>' +
      '<div class="grow" style="padding:10px 14px;background:' + bg + '"><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">' +
      '<span class="hd" style="font-size:32px;line-height:1.1">' + esc(k.level_text || '低危') + '</span><span class="big">' + score + '<span style="font-size:14px;color:var(--dim)">/100</span></span></div>' +
      '<div>' + esc(k.scene || '') + ' · 信号灯 ' + lightName + ' · 语音 ' + voice + '</div></div></div>' +
      '<div style="padding:10px 14px;border-bottom:2px solid var(--ink)"><div class="scorebar"><i class="fill" style="width:' + Math.min(100, score) + '%;background:' + col + '"></i>' +
      '<i class="tick" style="left:' + th.mid + '%"></i><i class="tick" style="left:' + th.high + '%"></i></div>' +
      '<div class="scorelbl num mut"><span style="left:0">0 低危</span><span style="left:' + th.mid + '%">' + th.mid + ' 中危</span><span style="left:' + th.high + '%">' + th.high + ' 高危</span></div></div>' +
      '<div class="row head">判定依据</div>' +
      (factors.length ? factors.map(function (f) {
        var cross = /×/.test(f.source);
        return '<div class="row"><span class="tag ' + (cross ? 't-ink' : 't-soft') + '">' + esc(f.source) + '</span><span class="grow" style="flex:1 1 160px">' + esc(f.text) +
          '</span><span class="num" style="font-weight:700">+' + f.points + '</span></div>';
      }).join('') : '<div class="row mut">无风险因素</div>');
  }

  function ppeHtml(s) {
    var p = (s.vision || {}).ppe || [];
    if (!p.length) return '';
    return '<div class="row" style="gap:6px">' + p.map(function (x) {
      var cls = x.status === 'bad' ? 't-high' : x.status === 'ok' ? 't-low' : 't-off';
      return '<span class="tag ' + cls + '">' + icon(x.status === 'bad' ? 'x' : x.status === 'ok' ? 'check' : 'eye', 14) + esc(x.name) + '</span>';
    }).join('') + '</div>';
  }

  function eventsHtml(s, cmds) {
    var ev = (s.active_events || []).map(function (e) {
      var t = LEVEL_TAG[e.level] || [e.level, 't-soft'];
      return '<div class="row"><span class="num mut">' + esc(e.time_str || '') + '</span><span class="tag ' + t[1] + '">' + t[0] + '</span><span class="grow">' + esc(e.title) +
        (e.message ? '<span class="mut"> · ' + esc(e.message) + '</span>' : '') + '</span></div>';
    });
    var cm = (cmds || []).slice(0, 5).map(function (c) {
      return '<div class="row"><span class="num mut">' + LG.time(c.created) + '</span><span class="tag ' + (c.cmd === 'cut_power' ? 't-high' : 't-soft') + '">' +
        (c.cmd === 'cut_power' ? '远程断电' : '静音') + '</span><span class="grow">' + esc(c.created_by) + '</span><span class="mut">' + esc(c.result || '待下发') + '</span></div>';
    });
    return '<div class="row head">进行中的事件</div>' + (ev.join('') || '<div class="row mut">无</div>') +
      '<div class="row head">远程指令</div>' + (cm.join('') || '<div class="row mut">无</div>');
  }

  function chatHtml(id) {
    var h = chats[id] || [];
    if (!h.length) return '<div class="msg ai">已接入 ' + esc(LG.pathOf(id)) + ' 的实时状态与交叉验证结果。</div>';
    return h.map(function (m) {
      if (m.role === 'user') return '<div class="msg me">' + esc(m.content) + '</div>';
      return '<div class="msg ai' + (m.wait ? ' wait' : '') + '">' + esc(m.content) + (m.cite ? '<div class="cite">' + esc(m.cite) + '</div>' : '') + '</div>';
    }).join('');
  }

  LG.view('desk', {
    title: '实验桌', icon: 'desk',
    render: function (main, arg) {
      var id = Number(arg);
      if (!arg || !LG.areaById(id)) return picker(main);
      var path = LG.pathOf(id);
      LG.setCrumb('<a href="#/overview">总览</a><span class="mut">/</span>' + esc(path).replace(/ \/ /g, '<span class="mut"> / </span>'));
      main.innerHTML =
        '<section class="panel top" id="dkHead" aria-label="终端概况"></section>' +
        '<div class="cols"><div style="flex:3 1 520px;display:flex;flex-direction:column;gap:16px;min-width:0">' +
        '<div class="cams">' + camHtml('pano', '全景 · 人员模型', 'camera') + camHtml('desk', '台面 · 器皿模型', 'flask') + '</div>' +
        '<section class="panel stats" aria-label="传感器" id="dkSensors"></section>' +
        '<section class="panel" aria-label="安全助手"><div class="ph">' + icon('chat') + '安全助手<span class="sp"></span><small>数据源：实时状态 · 交叉验证 · 安全手册</small></div>' +
        '<div class="chat" id="dkChat" aria-live="polite"></div>' +
        '<div class="row">' + QUICK.map(function (q) { return '<button class="btn" data-q="' + esc(q) + '">' + esc(q) + '</button>'; }).join('') + '</div>' +
        '<form class="row" id="dkAsk"><label class="grow" style="display:flex"><span class="sr">提问</span><input class="fld" id="dkQ" maxlength="500" placeholder="输入问题" autocomplete="off"></label>' +
        '<button class="btn pri" type="submit">' + icon('send') + '发送</button></form></section></div>' +
        '<div style="flex:2 1 340px;display:flex;flex-direction:column;gap:16px;min-width:0">' +
        '<section class="panel" aria-label="交叉验证"><div class="ph dk">' + icon('layers') + '交叉验证<span class="sp"></span><small>人员 × 器皿 × 传感器</small></div><div id="dkCross"></div><div id="dkPpe"></div></section>' +
        '<section class="panel" aria-label="远程操作"><div class="ph">' + icon('power') + '远程操作</div>' +
        '<div class="pad" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px">' +
        '<button class="btn" id="dkMute">' + icon('mute') + '静音 60 s</button><button class="btn" id="dkReport">' + icon('doc') + '实验安全报告</button>' +
        '<button class="btn dng" id="dkCut" style="grid-column:1 / 3;min-height:44px">' + icon('power') + '切断加热电源</button></div>' +
        '<div class="row mut foot" style="font-size:12px">' + icon('lock', 16) + '仅支持断电 · 复电须现场复位</div></section>' +
        '<section class="panel" aria-label="事件记录"><div class="ph">' + icon('clock') + '事件记录</div><div id="dkEvents"></div></section></div></div>';

      var online = false, snap = null;
      function paintChat() { var c = LG.$('#dkChat'); c.innerHTML = chatHtml(id); c.scrollTop = c.scrollHeight; }
      paintChat();

      function ask(q) {
        q = (q || '').trim();
        if (!q) return;
        var h = chats[id] = chats[id] || [];
        var history = h.filter(function (m) { return !m.wait; }).map(function (m) { return { role: m.role, content: m.content }; });
        h.push({ role: 'user', content: q });
        var wait = { role: 'assistant', content: '分析中…', wait: true };
        h.push(wait); paintChat();
        LG.api('POST', '/api/desks/' + id + '/ask', { question: q, history: history.slice(-6) }).then(function (r) {
          wait.wait = false; wait.content = r.text || '（无回答）'; wait.cite = r.provider_label || '';
        }).catch(function (e) { wait.wait = false; wait.content = '无法获取回答：' + e.message; }).then(paintChat);
      }
      LG.$('#dkAsk').onsubmit = function (e) { e.preventDefault(); var i = LG.$('#dkQ'); ask(i.value); i.value = ''; };
      LG.$$('[data-q]', main).forEach(function (b) { b.onclick = function () { ask(b.dataset.q); }; });
      LG.$('#dkMute').onclick = function () {
        LG.api('POST', '/api/desks/' + id + '/command', { cmd: 'mute', seconds: 60 }).then(function () { LG.toast('静音指令已下发'); }).catch(LG.fail);
      };
      LG.$('#dkCut').onclick = function () { LG.cutPower(id, path); };
      LG.$('#dkReport').onclick = function () {
        LG.toast('报告生成中，约需 10–60 秒…');
        LG.api('POST', '/api/desks/' + id + '/report').then(function (r) {
          LG.dialog('实验安全报告 · ' + path, '<div style="white-space:pre-wrap;max-height:60vh;overflow-y:auto">' + esc(r.text || '') + '</div>' +
            '<div class="mut">' + esc(r.provider_label || '') + '</div>');
        }).catch(LG.fail);
      };

      // 画面：上一张加载完再取下一张，离线时停止
      ['pano', 'desk'].forEach(function (w) {
        var img = LG.$('#img-' + w), no = LG.$('#noimg-' + w);
        function next(delay) { LG.later(delay, function () { if (online) img.src = '/api/desks/' + id + '/frame/' + w + '.jpg?_=' + Date.now(); else next(2000); }); }
        img.onload = function () { img.hidden = false; no.hidden = true; next(1000); };
        img.onerror = function () { img.hidden = true; no.hidden = false; no.textContent = '画面不可用'; next(5000); };
        next(300);
      });

      var dead = false;     // 实验桌未绑定终端：停止轮询
      LG.every(1500, function () {
        if (dead) return;
        LG.api('GET', '/api/desks/' + id).then(function (d) {
          var n = d.node, s = d.snapshot || {};
          online = n.online; snap = s;
          var lv = n.online ? (s.latched ? 'high' : (s.risk || {}).level || 'low') : 'off', L = LG.LV[lv];
          LG.$('#dkHead').innerHTML =
            '<div style="display:flex;align-items:center;gap:12px;padding:8px 16px;border-right:3px solid var(--ink);flex:1 1 260px;flex-wrap:wrap">' +
            '<span class="hd" style="font-size:26px">' + esc(d.area.name) + '</span><span class="' + L.tag + '">' + (s.latched ? '断电锁定' : L.text + (n.online && s.risk ? ' ' + s.risk.score : '')) + '</span>' +
            '<span style="font-weight:600">' + esc(n.online ? (s.latched ? s.latch_reason || '' : (s.risk || {}).scene || s.state_text || '') : '终端离线') + '</span></div>' +
            '<div style="display:flex;align-items:center;gap:8px;padding:8px 16px;border-right:3px solid var(--ink)">' + icon('monitor') + '<span>' + esc(n.name) + '</span>' +
            '<span class="tag ' + (n.online ? 't-low' : 't-off') + '">' + (n.online ? '在线' : '离线') + '</span><span class="mut num">' + LG.ago(n.last_seen) + '</span></div>' +
            '<div style="display:flex;align-items:center;gap:8px;padding:8px 16px;border-right:3px solid var(--ink)">' + icon('chip') + '<span>热源硬上限</span><span class="num">' + LG.fmt(n.hard_limit_c, 0, '℃') + '</span></div>' +
            '<div style="display:flex;align-items:center;gap:8px;padding:8px 16px">' + icon('power') + '<span>加热回路</span>' +
            (s.latched ? '<span class="tag t-high">已断电</span>' : (s.link || {}).relay_on === false ? '<span class="tag t-soft">断开</span>' : (s.link || {}).relay_on ? '<span class="tag t-low">通电</span>' : '<span class="tag t-off">未知</span>') + '</div>';
          LG.$('#dkSensors').innerHTML = sensorsHtml(s);
          LG.$('#dkCross').innerHTML = n.online ? crossHtml(s) : '<div class="empty">终端离线，交叉验证暂停</div>';
          LG.$('#dkPpe').innerHTML = n.online ? ppeHtml(s) : '';
          LG.$('#dkEvents').innerHTML = eventsHtml(s, d.commands);
          var v = s.vision || {};
          LG.$('#fps-pano').textContent = v.fps || '';
          LG.$('#dkCut').disabled = !!s.latched;
          LG.$('#dkMute').textContent = '';
          LG.$('#dkMute').insertAdjacentHTML('beforeend', icon('mute') + (s.mute_until ? '静音中 ' + Math.max(0, Math.round(s.mute_until - Date.now() / 1000)) + ' s' : '静音 60 s'));
        }).catch(function (e) {
          if (e.status === 404) { main.innerHTML = '<section class="panel"><div class="ph">' + icon('desk') + esc(path) + '</div><div class="empty">' + esc(e.message) +
            (LG.isAdmin() ? '<div style="margin-top:10px"><a class="btn" href="#/areas">' + icon('monitor') + '登记终端</a></div>' : '') + '</div></section>'; dead = true; online = false; }
          else LG.fail(e);
        });
      });
    }
  });
})();
