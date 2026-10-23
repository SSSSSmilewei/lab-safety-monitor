/* 总览：运行概况、处置队列、区域筛选、各实验桌状态（2 秒刷新） */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var st = { room: null, riskOnly: false, mode: 'list' };
  try { st.mode = localStorage.getItem('lg.ov.mode') === 'map' ? 'map' : 'list'; } catch (e) { /* 浏览器禁用存储时用默认 */ }
  // 分层上报视角：building 实验楼 / teacher 实验室 / student 学生端；null = 按账号角色（管理员看实验楼，教师看实验室）
  var TIERS = { building: '实验楼', teacher: '实验室', student: '学生端' };
  var TIER_NOTE = { building: '仅断电锁定与紧急事件', teacher: '加热、温度、烟雾、断电与呼叫', student: '与实验台提醒一致' };
  try { st.tier = TIERS[localStorage.getItem('lg.ov.tier')] ? localStorage.getItem('lg.ov.tier') : null; } catch (e) { st.tier = null; }

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
    var q = ov.desks.filter(function (d) { var lv = LG.deskLevel(d); return d.call || lv === 'high' || lv === 'mid'; });
    // 终端求助排最前，其余按风险等级
    q.sort(function (a, b) { return (b.call ? 1 : 0) - (a.call ? 1 : 0) || riskOrder(LG.deskLevel(a)) - riskOrder(LG.deskLevel(b)); });
    if (!q.length) return '<div class="empty">' + icon('ok', 28) + '<div>无待处置事项</div></div>';
    return q.map(function (d) {
      var lv = LG.deskLevel(d), L = LG.LV[lv];
      var why = (d.reasons && d.reasons.length ? d.reasons : d.events || []).join(' · ') || d.scene || '';
      if (d.call) why = d.call.who + '在终端上呼叫教师（' + LG.ago(d.call.ts) + '）' + (why ? ' · ' + why : '');
      return '<div class="q-item ' + (lv === 'high' || d.call ? 'high' : '') + '"><i class="bar" aria-hidden="true" style="background:' + (d.call ? 'var(--high)' : L.color) + '"></i>' +
        '<span class="' + (d.call ? 'tag t-high' : L.tag) + '">' + (d.call ? '求助' : d.latched ? '断电锁定' : L.text) + '</span>' +
        '<div class="grow" style="flex:1 1 240px"><div style="font-weight:600">' + esc(d.path) + (d.scene ? ' · ' + esc(d.scene) : '') + '</div>' +
        '<div style="color:' + (lv === 'high' ? 'var(--high-deep)' : 'var(--mid-deep)') + '">' + esc(why) + '</div></div>' +
        (d.call ? '<button class="btn" data-ack="' + d.area_id + '">' + icon('ok') + '已知晓</button>' : '') +
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
          var reason = !d ? '在「区域」页登记终端' : !d.online ? '控制盒本地防护运行中' : (d.call ? '呼叫教师 · ' : '') + ((d.events || []).join(' · ') || (d.call ? '' : '无风险因素'));
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

  // ---------------- 平面图 ----------------
  // 楼层 = 直接包含「房间」的区域；房间、实验桌的位置来自区域的 layout（上级的百分比），没设置时自动排布
  function autoRooms(n) {          // 房间沿走廊两侧排布：上排 4–44%，走廊 46–54%，下排 56–96%
    var top = Math.ceil(n / 2), out = [];
    for (var i = 0; i < n; i++) {
      var row = i < top ? 0 : 1, k = row ? i - top : i, cnt = row ? n - top : top;
      var w = (96 - 2 * (cnt - 1)) / cnt;
      out.push({ x: 2 + k * (w + 2), y: row ? 56 : 4, w: w, h: 40 });
    }
    return out;
  }
  function autoDesks(n) {          // 与 tools/center_demo.py 的 desk_boxes() 相同：两列，留出过道
    var cols = n === 1 ? 1 : 2, rows = Math.max(1, Math.ceil(n / cols)), out = [];
    var w = (84 - 8 * (cols - 1)) / cols, h = (76 - 8 * (rows - 1)) / rows;
    for (var i = 0; i < n; i++) out.push({ x: 8 + (i % cols) * (w + 8), y: 16 + Math.floor(i / cols) * (h + 8), w: w, h: h });
    return out;
  }
  function box(b) { return 'left:' + b.x + '%;top:' + b.y + '%;width:' + b.w + '%;height:' + b.h + '%'; }

  function mapHtml(ov) {
    var byArea = {};
    ov.desks.forEach(function (d) { byArea[d.area_id] = d; });
    var rooms = LG.S.tree.filter(function (a) { return a.kind === 'room'; });
    var floors = [];
    rooms.forEach(function (r) { if (floors.indexOf(r.parent_id) < 0) floors.push(r.parent_id); });
    if (st.room != null) {
      var sel = LG.areaById(Number(st.room));
      floors = floors.filter(function (f) { return sel && (sel.parent_id === f || sel.id === f); });
    }
    if (!floors.length) return '<div class="empty">' + (rooms.length ? '当前筛选下无平面图' : '尚未建立房间' + (LG.isAdmin() ? '，请在「区域」页添加' : '')) + '</div>';
    return '<div class="plans">' + floors.map(function (fid) {
      var rs = rooms.filter(function (r) { return r.parent_id === fid; });
      var auto = autoRooms(rs.length);
      var cells = rs.map(function (r, i) {
        var ds = LG.children(r.id).filter(function (a) { return a.kind === 'desk' && a.managed; });
        var dauto = autoDesks(ds.length);
        var lvs = ds.map(function (a) { return LG.deskLevel(byArea[a.id]); });
        var worst = lvs.reduce(function (w, lv) { return riskOrder(lv) < riskOrder(w) ? lv : w; }, 'none');
        var on = st.room != null && String(st.room) === String(r.id);
        var tiles = ds.map(function (a, j) {
          var d = byArea[a.id], lv = lvs[j], L = LG.LV[lv];
          var dim = st.riskOnly && lv !== 'high' && lv !== 'mid';
          var tip = LG.pathOf(a.id) + ' · ' + (!d ? '未绑定终端' : !d.online ? '终端离线' : (d.latched ? '断电锁定' : L.text + (d.scene ? ' · ' + d.scene : '')));
          return '<a class="pdesk lv-' + lv + (dim ? ' dim' : '') + '" href="#/desk/' + a.id + '" style="' + box(a.layout || dauto[j]) + '" title="' + esc(tip) + '">' +
            '<span class="pn">' + esc(a.name.replace(/号桌$/, '')) + '</span>' +
            '<span class="pv num">' + (d && d.latched ? icon('lock', 14) : d && d.online && d.obj_temp != null ? Math.round(d.obj_temp) + '℃' : (d && d.online ? '' : L.text)) + '</span>' +
            '<span class="sr">' + esc(tip) + '</span></a>';
        }).join('');
        return '<div class="proom' + (on ? ' on' : '') + (ds.length ? '' : ' empty-room') + '" style="' + box(r.layout || auto[i]) + '">' +
          '<div class="prh"><span class="hd">' + esc(r.name) + '</span>' + (ds.length ? '<i class="dot" aria-hidden="true" style="background:' + LG.LV[worst].color + '"></i>' : '') +
          '</div><div class="prin">' + tiles + '</div></div>';
      }).join('');
      return '<div class="pfloor"><div class="roomhd">' + icon('plan', 16) + '<span class="hd">' + esc(fid != null && LG.areaById(fid) ? LG.pathOf(fid) : '未分组') + '</span><span class="grow"></span>' +
        '<span class="mut">' + rs.length + ' 间</span></div>' +
        '<div class="planwrap"><div class="plan"><div class="corr" aria-hidden="true"><span>走廊</span></div>' + cells + '</div></div></div>';
    }).join('') + '</div><div class="row plegend">' + ['high', 'mid', 'low', 'off', 'none'].map(function (lv) {
      return '<span class="pkey lv-' + lv + '"></span><span>' + LG.LV[lv].text + '</span>';
    }).join('') + '<span class="grow"></span><span class="mut">示意布局 · 点击实验桌查看画面</span></div>';
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
        '<div class="cols"><section class="panel" aria-label="处置队列" style="flex:3 1 520px"><div class="ph">' + icon('alert') + '处置队列<span class="sp"></span><small id="ovTierNote"></small>' +
        '<span class="seg" aria-label="上报层级">' + Object.keys(TIERS).map(function (k) { return '<button class="btn" data-tier="' + k + '">' + TIERS[k] + '</button>'; }).join('') + '</span></div><div id="ovQueue"></div></section>' +
        '<section class="panel" aria-label="区域筛选" style="flex:1 1 240px"><div class="ph">' + icon('building') + '区域筛选</div><div id="ovRooms"></div></section></div>' +
        '<section class="panel" aria-label="实验桌状态"><div class="ph">' + icon('desk') + '实验桌状态<span class="sp"></span>' +
        '<span class="seg"><button class="btn" data-m="list" aria-label="列表">' + icon('list', 16) + '列表</button><button class="btn" data-m="map" aria-label="平面图">' + icon('plan', 16) + '平面图</button></span>' +
        '<span class="seg"><button class="btn" data-f="all">全部</button><button class="btn" data-f="risk">中高危</button></span></div><div id="ovDesks"></div></section>';
      var last = null;
      function paint() {
        if (!last) return;
        var gs = groups(last);
        LG.$('#ovStats').innerHTML = statsHtml(last.summary);
        LG.$('#ovQueue').innerHTML = queueHtml(last);
        LG.$('#ovRooms').innerHTML = roomsHtml(gs, gs.reduce(function (n, g) { return n + g.desks.length; }, 0));
        var box = LG.$('#ovDesks'), sx = LG.$$('.planwrap', box).map(function (w) { return w.scrollLeft; });
        box.innerHTML = st.mode === 'map' ? mapHtml(last) : desksHtml(gs);
        LG.$$('.planwrap', box).forEach(function (w, i) { w.scrollLeft = sx[i] || 0; });   // 窄屏横向滚动位置在刷新后保留
        LG.$$('[data-f]', main).forEach(function (b) { b.classList.toggle('on', (b.dataset.f === 'risk') === st.riskOnly); });
        LG.$$('[data-m]', main).forEach(function (b) { b.classList.toggle('on', b.dataset.m === st.mode); });
        LG.$$('[data-tier]', main).forEach(function (b) { b.classList.toggle('on', b.dataset.tier === last.tier); });
        LG.$('#ovTierNote').textContent = (TIERS[last.tier] || '') + '视角 · ' + (TIER_NOTE[last.tier] || '');
      }
      main.addEventListener('click', function (e) {
        var t = e.target.closest('[data-room], [data-f], [data-m], [data-cut], [data-tier], [data-ack]');
        if (!t) return;
        if (t.dataset.tier) {
          st.tier = t.dataset.tier;
          try { localStorage.setItem('lg.ov.tier', st.tier); } catch (x) { /* 忽略 */ }
          refresh();
          return;
        }
        if (t.dataset.m) {
          st.mode = t.dataset.m;
          try { localStorage.setItem('lg.ov.mode', st.mode); } catch (x) { /* 忽略 */ }
        } else if (t.hasAttribute('data-room')) st.room = t.dataset.room === '' ? null : t.dataset.room;
        else if (t.dataset.f) st.riskOnly = t.dataset.f === 'risk';
        else if (t.dataset.cut) { LG.cutPower(t.dataset.cut, t.dataset.path); return; }
        else if (t.dataset.ack) {
          LG.api('POST', '/api/desks/' + t.dataset.ack + '/call_ack').then(function () {
            LG.toast('已确认求助'); return LG.api('GET', '/api/overview');
          }).then(function (ov) { last = ov; paint(); }).catch(LG.fail);
          return;
        }
        paint();
      });
      function refresh() {
        LG.api('GET', '/api/overview' + (st.tier ? '?tier=' + st.tier : '')).then(function (ov) { last = ov; paint(); }).catch(LG.fail);
      }
      LG.every(2000, refresh);
      LG.every(15000, function () { LG.loadTree(true).then(paint); });
    }
  });
})();
