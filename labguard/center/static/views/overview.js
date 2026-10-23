/* 总览：运行概况、处置队列、区域筛选、各实验桌状态（2 秒刷新） */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var st = { room: null, riskOnly: false };

  function riskOrder(lv) { return { high: 0, mid: 1, low: 2, off: 3, none: 4 }[lv]; }

  // 把实验桌（区域树里的 desk）按上级区域分组；没绑定终端的桌也列出来
  function groups(ov) {
    var byArea = {};
    ov.desks.forEach(function (d) { byArea[d.area_id] = d; });
    var out = [], idx = {};
    LG.S.tree.filter(function (a) { return a.kind === 'desk' && a.managed; }).forEach(function (a) {
      var pid = a.parent_id, key = String(pid);
      if (!idx[key]) {
        idx[key] = { id: pid, name: pid != null && LG.areaById(pid) ? LG.pathOf(pid) : '未分组', desks: [] };
        out.push(idx[key]);
      }
      var d = byArea[a.id];
      idx[key].desks.push({ area: a, d: d, lv: LG.deskLevel(d) });
    });
    // 终端绑定到了树里看不到的区域（理论上不会发生），兜底列出
    ov.desks.forEach(function (d) {
      if (!LG.areaById(d.area_id)) {
        if (!idx.x) { idx.x = { id: 'x', name: '其他', desks: [] }; out.push(idx.x); }
        idx.x.desks.push({ area: { id: d.area_id, name: d.path }, d: d, lv: LG.deskLevel(d) });
      }
    });
    out.forEach(function (g) {
      g.worst = g.desks.reduce(function (w, x) { return riskOrder(x.lv) < riskOrder(w) ? x.lv : w; }, 'none');
    });
    return out;
  }

  function statsHtml(s) {
    var cell = function (cls, ic, label, val, extra) {
      return '<div class="stat ' + cls + '">' + icon(ic, 28) + '<div><div>' + label + '</div><div class="big">' + val + (extra || '') + '</div></div></div>';
    };
    return cell('', 'monitor', '终端在线', s.online, '<span style="font-size:16px;color:var(--dim)">/' + s.total + '</span>') +
      cell(s.high ? 's-high' : 'zero', 'alert', '高危', s.high) +
      cell(s.mid ? 's-mid' : 'zero', 'alert', '中危', s.mid) +
      cell(s.low ? 's-low' : 'zero', 'ok', '低危', s.low) +
      cell('', 'offline', '离线', s.offline);
  }

  function queueHtml(ov) {
    var q = ov.desks.filter(function (d) { var lv = LG.deskLevel(d); return lv === 'high' || lv === 'mid'; });
    q.sort(function (a, b) { return riskOrder(LG.deskLevel(a)) - riskOrder(LG.deskLevel(b)); });
    if (!q.length) return '<div class="empty">' + icon('ok', 28) + '<div>无待处置事项</div></div>';
    return q.map(function (d) {
      var lv = LG.deskLevel(d), L = LG.LV[lv];
      var why = (d.events || []).join(' · ') || d.scene || '';
      return '<div class="q-item ' + (lv === 'high' ? 'high' : '') + '"><i class="bar" aria-hidden="true" style="background:' + L.color + '"></i>' +
        '<span class="' + L.tag + '">' + (d.latched ? '断电锁定' : L.text) + '</span>' +
        '<div class="grow" style="flex:1 1 240px"><div style="font-weight:600">' + esc(d.path) + (d.scene ? ' · ' + esc(d.scene) : '') + '</div>' +
        '<div style="color:' + (lv === 'high' ? 'var(--high-deep)' : 'var(--mid-deep)') + '">' + esc(why) + '</div></div>' +
        '<a class="btn" href="#/desk/' + d.area_id + '">' + icon('camera') + '详情</a>' +
        (d.latched ? '' : '<button class="btn dng" data-cut="' + d.area_id + '" data-path="' + esc(d.path) + '">' + icon('power') + '断电</button>') + '</div>';
    }).join('');
  }

  function roomsHtml(gs, total) {
    var b = '<button class="tree' + (st.room == null ? ' on' : '') + '" data-room=""><span class="grow">全部区域</span><span class="num">' + total + '</span></button>';
    return b + gs.map(function (g) {
      return '<button class="tree' + (String(st.room) === String(g.id) ? ' on' : '') + '" data-room="' + g.id + '">' +
        '<i class="dot" aria-hidden="true" style="background:' + LG.LV[g.worst].color + '"></i><span class="grow">' + esc(g.name) + '</span><span class="num">' + g.desks.length + '</span></button>';
    }).join('');
  }

  function desksHtml(gs) {
    var shown = gs.filter(function (g) { return st.room == null || String(g.id) === String(st.room); });
    var html = shown.map(function (g) {
      var ds = g.desks.filter(function (x) { return !st.riskOnly || x.lv === 'high' || x.lv === 'mid'; });
      if (!ds.length) return '';
      return '<div class="roomhd"><span class="hd">' + esc(g.name) + '</span><span class="grow"></span><span class="mut">' + g.desks.length + ' 张实验桌</span></div>' +
        '<div class="deskgrid">' + ds.map(function (x) {
          var d = x.d, L = LG.LV[x.lv];
          var scene = !d ? '未绑定终端' : !d.online ? '终端离线' : (d.latched ? '断电锁定' : d.scene || d.state_text || '');
          var reason = !d ? '在「区域」页登记终端' : !d.online ? '控制盒本地防护运行中' : (d.events || []).join(' · ') || '无风险因素';
          return '<a class="deskcard ' + L.card + '" href="#/desk/' + x.area.id + '"><div class="stripe" style="background:' + L.color + '"></div><div class="in">' +
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span class="hd" style="font-size:16px">' + esc(x.area.name) + '</span>' +
            '<span class="' + L.tag + '">' + (d && d.latched ? '锁定' : L.text) + '</span></div>' +
            '<div style="font-weight:600">' + esc(scene) + '</div><div class="mut" style="min-height:20px">' + esc(reason) + '</div>' +
            '<div class="ft"><span style="display:flex;align-items:center;gap:4px">' + icon('thermo', 16) + '<span class="num">' + (d ? LG.fmt(d.obj_temp, 1, '℃') : '--') + '</span></span>' +
            '<span class="num mut">' + (d ? LG.ago(d.last_seen) : '') + '</span></div></div></a>';
        }).join('') + '</div>';
    }).join('');
    return html || '<div class="empty">' + (LG.S.tree.length ? '当前筛选下无实验桌' : '尚未建立区域' + (LG.isAdmin() ? '，请在「区域」页添加实验室与实验桌' : '')) + '</div>';
  }

  LG.cutPower = function (areaId, path) {
    return LG.confirm('切断加热电源', '<div><b>' + esc(path) + '</b></div><div>终端下次上报时（约 2 秒内）执行断电。</div>' +
      '<div class="mut">' + icon('lock', 16) + ' 软件与远程均不可恢复供电，复电须现场长按控制盒复位键。</div>', '确认断电', true).then(function (ok) {
      if (!ok) return;
      return LG.api('POST', '/api/desks/' + areaId + '/command', { cmd: 'cut_power', confirm: true }).then(function (r) { LG.toast('断电指令已下发\n' + r.note); });
    }).catch(LG.fail);
  };

  LG.view('overview', {
    title: '总览', icon: 'grid',
    render: function (main) {
      main.innerHTML =
        '<section class="panel stats" aria-label="运行概况" id="ovStats"></section>' +
        '<div class="cols"><section class="panel" aria-label="处置队列" style="flex:3 1 520px"><div class="ph">' + icon('alert') + '处置队列<span class="sp"></span><small>按风险等级排序</small></div><div id="ovQueue"></div></section>' +
        '<section class="panel" aria-label="区域筛选" style="flex:1 1 240px"><div class="ph">' + icon('building') + '区域筛选</div><div id="ovRooms"></div></section></div>' +
        '<section class="panel" aria-label="实验桌状态"><div class="ph">' + icon('desk') + '实验桌状态<span class="sp"></span>' +
        '<span class="seg"><button class="btn" data-f="all">全部</button><button class="btn" data-f="risk">中高危</button></span></div><div id="ovDesks"></div></section>';
      var last = null;
      function paint() {
        if (!last) return;
        var gs = groups(last);
        LG.$('#ovStats').innerHTML = statsHtml(last.summary);
        LG.$('#ovQueue').innerHTML = queueHtml(last);
        LG.$('#ovRooms').innerHTML = roomsHtml(gs, gs.reduce(function (n, g) { return n + g.desks.length; }, 0));
        LG.$('#ovDesks').innerHTML = desksHtml(gs);
        LG.$$('[data-f]', main).forEach(function (b) { b.classList.toggle('on', (b.dataset.f === 'risk') === st.riskOnly); });
      }
      main.addEventListener('click', function (e) {
        var t = e.target.closest('[data-room], [data-f], [data-cut]');
        if (!t) return;
        if (t.hasAttribute('data-room')) st.room = t.dataset.room === '' ? null : t.dataset.room;
        else if (t.dataset.f) st.riskOnly = t.dataset.f === 'risk';
        else if (t.dataset.cut) { LG.cutPower(t.dataset.cut, t.dataset.path); return; }
        paint();
      });
      LG.every(2000, function () {
        LG.api('GET', '/api/overview').then(function (ov) { last = ov; paint(); }).catch(LG.fail);
      });
      LG.every(15000, function () { LG.loadTree(true).then(paint); });
    }
  });
})();
