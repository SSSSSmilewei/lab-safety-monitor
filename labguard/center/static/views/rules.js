/* 主控决策 · 阈值配置：按区域选方案、逐项覆盖、硬件上限校验、交叉验证（问答）参数 */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var META = null;          // /api/presets
  var CUT = { 'rules.dry_burn_c': 1, 'rules.unattended_heating_cut_s': 1, 'rules.smoke_raw': 1 };
  var CENTER_MAX = { 'rules.dry_burn_c': 300, 'rules.smoke_raw': 4000 };   // 总后台放宽到的上限；各终端再按自己的控制盒校验
  var RANGE_TEXT = { 'rules.dry_burn_c': '80–硬上限−5', 'rules.smoke_raw': '300–硬上限−100' };
  var st = { sel: null };

  function bare(label) { return label.replace(/（.*?）/g, '').trim(); }
  function unitOf(label) { var m = bare(label).match(/\s(℃\/s|℃|%|s)$/); return m ? m[1] : ''; }
  function shortLabel(label) { return bare(label).replace(/\s(℃\/s|℃|%|s)$/, ''); }

  function areaList() {
    var items = LG.flatTree(function (a) { return a.managed; });
    return items.map(function (x) {
      return '<button class="tree' + (x.a.id === st.sel ? ' on' : '') + '" data-area="' + x.a.id + '">' +
        '<span class="grow" style="padding-left:' + (x.depth * 14) + 'px">' + esc(x.a.name) + '</span><span class="sub">' + LG.KIND[x.a.kind] + '</span></button>';
    }).join('') || '<div class="empty">无可配置的区域</div>';
  }

  function load(main) {
    var id = st.sel;
    var area = LG.areaById(id);
    var parentP = area && area.parent_id != null && LG.areaById(area.parent_id) && LG.areaById(area.parent_id).managed ?
      LG.api('GET', '/api/profiles/' + area.parent_id).catch(function () { return null; }) : Promise.resolve(null);
    return Promise.all([LG.api('GET', '/api/profiles/' + id), parentP]).then(function (res) {
      var prof = res[0], parent = res[1];
      var std = META.presets.standard.rules;
      var inherited = {};
      if (parent) inherited = Object.assign({}, std, parent.resolved.rules);
      else {   // 看不到上级（只被授权了这一级）：用本级合并结果里不属于本级的项 + 出厂默认
        inherited = Object.assign({}, std);
        Object.keys(prof.resolved.rules).forEach(function (k) { if (!(k in prof.own.rules)) inherited[k] = prof.resolved.rules[k]; });
      }
      var srcName = function (k) {
        if (parent) return parent.resolved.sources[k] || '出厂默认';
        return prof.resolved.sources[k] && !(k in prof.own.rules) ? prof.resolved.sources[k] : '出厂默认';
      };
      paint(main, { prof: prof, inherited: inherited, srcName: srcName, draft: Object.assign({}, prof.own.rules), preset: prof.own.preset || '', errors: {} });
    });
  }

  function paint(main, m) {
    var spec = META.spec, std = META.presets.standard.rules;
    var keys = Object.keys(spec);
    var changed = JSON.stringify(m.draft) !== JSON.stringify(m.prof.own.rules) || m.preset !== (m.prof.own.preset || '');
    var presets = Object.keys(META.presets).map(function (pid) {
      var p = META.presets[pid];
      return '<button class="preset' + (m.preset === pid ? ' on' : '') + '" data-preset="' + pid + '"><span class="hd">' + esc(p.name) + '</span><small>' + esc(p.desc) + '</small></button>';
    }).join('');
    var rows = keys.map(function (k) {
      var s = spec[k], own = k in m.draft, val = own ? m.draft[k] : m.inherited[k];
      var nodeDefault = !own && val == null;      // 识别类参数没有出厂方案值，沿用各终端 config.yaml
      var hi = CENTER_MAX[k] || s.max, num = Number(val);
      var bad = m.errors[k] || (own && (isNaN(num) || num < s.min || num > hi) ? '超出允许范围' : '');
      var base = std[k], diff = num - base;
      var unit = unitOf(s.label);
      return '<tr class="' + (bad ? 'bad' : '') + '"><td class="mut">' + esc(s.group) + '</td>' +
        '<td><span style="display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap">' + esc(shortLabel(s.label)) + (CUT[k] ? '<span class="tag t-high">断电</span>' : '') + '</span>' +
        (bad ? '<div style="color:var(--high-deep);font-size:12px">' + esc(bad) + '</div>' : '') + '</td>' +
        '<td><label style="display:inline-flex;align-items:center;gap:6px"><span class="sr">' + esc(s.label) + '</span>' +
        '<input class="fld num numin' + (bad ? ' bad' : '') + '" type="number" step="any" data-k="' + k + '" value="' + esc(val == null ? '' : val) + '"' +
        (nodeDefault ? ' placeholder="终端默认"' : '') + '><span class="mut">' + unit + '</span></label></td>' +
        '<td>' + (own ? '<span class="tag t-ink">本级</span>' : '<span class="mut">' + (nodeDefault ? '终端默认' : esc(m.srcName(k))) + '</span>') + '</td>' +
        '<td class="num mut">' + (base == null ? '—' : base) + '</td><td class="num mut">' + (RANGE_TEXT[k] || s.min + '–' + s.max) + '</td>' +
        '<td>' + (Math.abs(diff) < 1e-9 || isNaN(diff) ? '<span class="mut">—</span>' : '<span class="tag t-soft">' + (diff > 0 ? '放宽 +' : '收紧 ') + (Math.round(diff * 10) / 10) + '</span>') + '</td>' +
        '<td>' + (own ? '<button class="btn sm flat" data-inherit="' + k + '">' + icon('reset', 14) + '继承</button>' : '') + '</td></tr>';
    }).join('');

    var limits = m.prof.nodes.length ? m.prof.nodes.map(function (n) {
      var w = Object.keys(n.warnings || {});
      return '<tr class="' + (w.length ? 'bad' : '') + '"><td>' + esc(n.path) + '</td><td>' + esc(n.node) + '</td><td class="num">' + LG.fmt(n.hard_limit_c, 0, '℃') + '</td>' +
        '<td class="num">' + (n.smoke_limit_raw || '--') + '</td><td>' + (w.length ? w.map(function (k) { return '<div class="tag t-high" style="height:auto;white-space:normal;margin:2px 0">' + icon('x', 14) + esc(n.warnings[k]) + '</div>'; }).join('') :
        '<span class="tag t-low">' + icon('check', 14) + '全部生效</span>') + '</td><td>' + (n.online ? '<span class="tag t-low">在线</span>' : '<span class="tag t-off">离线</span>') + '</td></tr>';
    }).join('') : '<tr><td colspan="6" class="mut">该区域下暂无已上报的终端</td></tr>';

    var A = META.agent_spec, av = function (k, d) { return k in m.draft ? m.draft[k] : (k in m.inherited ? m.inherited[k] : d); };
    var sel = function (k, opts) {
      return '<select class="fld" data-k="' + k + '"><option value="">继承</option>' + opts.map(function (o) {
        return '<option value="' + o[0] + '"' + (String(av(k, '')) === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
      }).join('') + '</select>';
    };
    var agent = '<div class="pad formgrid">' +
      '<label class="lbl">推理线路' + sel('agent.route', [['auto', '自动（远程 → 本地 → 规则模板）'], ['remote', '远程 API'], ['local', '本地模型'], ['off', '规则模板']]) + '</label>' +
      '<label class="lbl">采样温度 0–1<input class="fld num" type="number" step="0.1" min="0" max="1" data-k="agent.temperature" placeholder="继承" value="' + esc(av('agent.temperature', '')) + '"></label>' +
      '<label class="lbl">回答长度上限 200–1500<input class="fld num" type="number" step="50" min="200" max="1500" data-k="agent.max_tokens" placeholder="继承" value="' + esc(av('agent.max_tokens', '')) + '"></label>' +
      '<label class="lbl">自动生成处置建议' + sel('agent.min_level', [['NOTICE', '提醒及以上'], ['WARNING', '警告及以上'], ['CRITICAL', '仅紧急']]) + '</label>' +
      '<label class="lbl" style="grid-column:1 / -1">本实验室补充规程（≤ 500 字）<textarea class="fld" rows="2" maxlength="500" data-k="agent.extra_prompt" placeholder="继承">' + esc(av('agent.extra_prompt', '')) + '</textarea></label></div>';

    LG.$('#rlBody').innerHTML =
      '<section class="panel" aria-label="阈值方案"><div class="ph">' + icon('layers') + '阈值方案<span class="sp"></span><small>' + esc(m.prof.path) + '</small></div><div class="presets">' + presets + '</div></section>' +
      '<section class="panel" aria-label="阈值明细"><div class="ph">' + icon('sliders') + '阈值明细<span class="sp"></span><small>对照列：常规化学实验室（出厂默认）</small></div>' +
      '<div class="tbwrap"><table class="tb" style="min-width:860px"><thead><tr><th>类别</th><th>参数</th><th>本区域取值</th><th>来源</th><th>出厂默认</th><th>允许范围</th><th>差异</th><th><span class="sr">操作</span></th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="row foot"><button class="btn pri" id="rlSave"' + (changed ? '' : ' disabled') + '>' + icon('send') + '保存并下发</button>' +
      '<button class="btn" id="rlClear"' + (Object.keys(m.prof.own.rules).length || m.prof.own.preset ? '' : ' disabled') + '>' + icon('reset') + '清除本级设置</button>' +
      '<span class="mut">本级覆盖 <span class="num">' + Object.keys(m.draft).length + '</span> 项' + (m.prof.own.updated ? ' · 最近修改 ' + esc(m.prof.own.updated_by) + ' ' + LG.time(m.prof.own.updated) : '') + '</span></div></section>' +
      '<section class="panel" aria-label="硬件上限校验"><div class="ph rd">' + icon('chip') + '硬件上限校验<span class="sp"></span><small>控制盒固件限值 · 不可远程修改</small></div>' +
      '<div class="tbwrap"><table class="tb" style="min-width:640px"><thead><tr><th>实验桌</th><th>终端</th><th>热源硬上限</th><th>烟雾硬上限</th><th>结果</th><th>状态</th></tr></thead><tbody>' + limits + '</tbody></table></div></section>' +
      '<section class="panel" aria-label="交叉验证参数"><div class="ph dk">' + icon('chat') + '安全助手参数<span class="sp"></span><small>仅影响问答与处置建议，不参与断电</small></div>' + agent + '</section>';

    var body = LG.$('#rlBody');
    body.oninput = function (e) {
      var k = e.target.dataset && e.target.dataset.k;
      if (!k) return;
      var v = e.target.value;
      if (k in META.spec) { if (v === '') delete m.draft[k]; else m.draft[k] = Number(v); }
      else if (v === '') delete m.draft[k];
      else m.draft[k] = (k === 'agent.temperature' || k === 'agent.max_tokens') ? Number(v) : v;
      delete m.errors[k];
      if (e.target.tagName === 'SELECT') paint(main, m);
      else { LG.$('#rlSave').disabled = false; }
    };
    body.onchange = function (e) { if (e.target.dataset && e.target.dataset.k in META.spec) paint(main, m); };
    body.onclick = function (e) {
      var t = e.target.closest('[data-preset], [data-inherit], #rlSave, #rlClear');
      if (!t) return;
      if (t.dataset.preset) {
        var p = META.presets[t.dataset.preset];
        var keep = {};
        Object.keys(m.draft).forEach(function (k) { if (!(k in META.spec)) keep[k] = m.draft[k]; });   // 方案只替换阈值，不动助手参数
        m.preset = t.dataset.preset; m.draft = Object.assign(keep, p.rules); m.errors = {};
        paint(main, m);
      } else if (t.dataset.inherit) { delete m.draft[t.dataset.inherit]; delete m.errors[t.dataset.inherit]; paint(main, m); }
      else if (t.id === 'rlSave') {
        LG.api('PUT', '/api/profiles/' + st.sel, { preset: m.preset, rules: m.draft }).then(function (prof) {
          m.prof = prof; m.draft = Object.assign({}, prof.own.rules); m.errors = {};
          LG.toast('已保存，终端约 2 秒内生效'); paint(main, m);
        }).catch(function (x) {
          if (x.detail && x.detail.errors) { m.errors = x.detail.errors; paint(main, m); }
          LG.fail(x);
        });
      } else if (t.id === 'rlClear') {
        LG.confirm('清除本级设置', '<div>' + esc(m.prof.path) + ' 的阈值与助手参数将全部恢复为继承上级。</div>', '清除').then(function (ok) {
          if (!ok) return;
          LG.api('PUT', '/api/profiles/' + st.sel, { preset: '', rules: {} }).then(function () { LG.toast('已清除'); load(main); }).catch(LG.fail);
        });
      }
    };
  }

  LG.view('rules', {
    title: '阈值配置', rail: '阈值', icon: 'sliders',
    render: function (main) {
      LG.setCrumb('<span class="mut">主控决策</span><span class="mut">/</span><b>阈值配置</b>');
      var first = LG.flatTree(function (a) { return a.managed; })[0];
      if (st.sel == null || !LG.areaById(st.sel) || !LG.areaById(st.sel).managed) st.sel = first ? first.a.id : null;
      main.innerHTML = '<div class="cols"><section class="panel" aria-label="配置对象" style="flex:1 1 240px"><div class="ph">' + icon('tree') + '配置对象<span class="sp"></span><small>逐级继承</small></div>' +
        '<div id="rlTree">' + areaList() + '</div></section><div id="rlBody" style="flex:999 1 640px;display:flex;flex-direction:column;gap:16px;min-width:0"></div></div>';
      if (st.sel == null) { LG.$('#rlBody').innerHTML = '<div class="panel empty">无可配置的区域</div>'; return; }
      LG.$('#rlTree').onclick = function (e) {
        var t = e.target.closest('[data-area]'); if (!t) return;
        st.sel = Number(t.dataset.area); LG.$('#rlTree').innerHTML = areaList(); load(main).catch(LG.fail);
      };
      (META ? Promise.resolve(META) : LG.api('GET', '/api/presets').then(function (p) { META = p; return p; }))
        .then(function () { return load(main); }).catch(LG.fail);
    }
  });
})();
