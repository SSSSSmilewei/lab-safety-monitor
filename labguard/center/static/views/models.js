/* 模型看板：两个视觉模型的架构与训练指标、交叉验证因子、主控决策规则、现场复核准确率 */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var view = {};       // 每个模型：'chart' | 'table'
  var K = { p: 'metrics/precision(B)', r: 'metrics/recall(B)', a: 'metrics/mAP50(B)', b: 'metrics/mAP50-95(B)' };

  function chartHtml(m, idx) {
    var c = m.curves || {}, n = (c.epoch || []).length;
    if (!n) return '<div class="empty">无训练曲线</div>';
    var pts = function (arr) {
      return arr.map(function (v, i) { return (n > 1 ? i / (n - 1) * 600 : 0).toFixed(1) + ',' + ((1 - v) * 200).toFixed(1); }).join(' ');
    };
    var last = n - 1;
    var lab = function (v, cls) { return '<span class="endlbl num" style="top:' + ((1 - v) * 100) + '%">' + v.toFixed(3) + '</span>'; };
    return '<div class="chart" data-chart="' + idx + '"><div class="legend"><span><i style="background:var(--c1)"></i>mAP50</span><span><i style="background:var(--c2)"></i>mAP50-95</span>' +
      '<span class="grow"></span><span class="mut num" data-hover>悬停查看各轮指标</span></div>' +
      '<div class="plot"><div class="yax num"><span>1.0</span><span>0.75</span><span>0.5</span><span>0.25</span><span>0</span></div>' +
      '<svg viewBox="0 0 600 200" preserveAspectRatio="none" aria-hidden="true">' +
      '<path d="M0 0.5 H600 M0 50 H600 M0 100 H600 M0 150 H600" stroke="var(--line-soft)" stroke-width="1" vector-effect="non-scaling-stroke" fill="none"/>' +
      '<path d="M0 199.5 H600" stroke="var(--ink)" stroke-width="2" vector-effect="non-scaling-stroke" fill="none"/>' +
      '<polyline points="' + pts(c[K.a]) + '" fill="none" stroke="var(--c1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>' +
      '<polyline points="' + pts(c[K.b]) + '" fill="none" stroke="var(--c2)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>' +
      lab(c[K.a][last]) + lab(c[K.b][last]) +
      '<div class="cross" hidden></div><i class="dot" data-d="a" style="background:var(--c1);left:100%;top:' + ((1 - c[K.a][last]) * 100) + '%"></i>' +
      '<i class="dot" data-d="b" style="background:var(--c2);left:100%;top:' + ((1 - c[K.b][last]) * 100) + '%"></i>' +
      '<div class="hit">' + c.epoch.map(function (_, i) { return '<div data-i="' + i + '"></div>'; }).join('') + '</div></div>' +
      '<div class="xax num"><span>1</span><span>epoch</span><span>' + n + '</span></div></div>';
  }

  function tableHtml(m) {
    var c = m.curves || {}, n = (c.epoch || []).length, rows = [];
    for (var i = 0; i < n; i += 5) rows.push(i);
    if (n && rows[rows.length - 1] !== n - 1) rows.push(n - 1);
    return '<div class="tbwrap" style="max-height:260px;overflow-y:auto;border-bottom:2px solid var(--ink)"><table class="tb num"><thead><tr><th>epoch</th><th>Precision</th><th>Recall</th><th>mAP50</th><th>mAP50-95</th></tr></thead><tbody>' +
      rows.map(function (i) {
        return '<tr><td>' + (i + 1) + '</td><td>' + c[K.p][i].toFixed(3) + '</td><td>' + c[K.r][i].toFixed(3) + '</td><td>' + c[K.a][i].toFixed(3) + '</td><td>' + c[K.b][i].toFixed(3) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }

  function dsText(m) {
    var d = m.dataset || {}, parts = [];
    if (d.train_images != null) parts.push('训练 ' + d.train_images);
    if (d.val_images != null) parts.push('验证 ' + d.val_images);
    if (d.test_images != null) parts.push('测试 ' + d.test_images);
    if (d.instances != null) parts.push('标注框 ' + d.instances);
    return esc(m.dataset_name || '') + (parts.length ? ' · <span class="num">' + parts.join(' / ') + '</span> 张' : ' · <span class="mut">图片数未填写</span>') +
      (d.source ? '<div class="mut">' + esc(d.source) + '</div>' : '');
  }

  function modelHtml(m, idx) {
    var f = m.final || {}, ta = m.train_args || {}, v = view[m.file] || 'chart';
    var title = (m.role || m.file).replace(/（.*?）/, '');
    return '<section class="panel" style="flex:1 1 520px" aria-label="' + esc(title) + '"><div class="ph">' + icon(/人员/.test(m.role) ? 'goggles' : 'flask') + esc(title) +
      ' · <span class="num" style="font-size:14px">' + esc(m.file) + '</span><span class="sp"></span>' +
      '<span class="seg"><button class="btn' + (v === 'chart' ? ' on' : '') + '" data-view="chart" data-m="' + esc(m.file) + '">曲线</button><button class="btn' + (v === 'table' ? ' on' : '') +
      '" data-view="table" data-m="' + esc(m.file) + '">表格</button></span></div>' +
      '<div class="finals">' + [['Precision', f.precision], ['Recall', f.recall], ['mAP50', f.map50], ['mAP50-95', f.map50_95]].map(function (x) {
        return '<div><div class="mut">' + x[0] + '</div><div class="big">' + LG.fmt(x[1], 3) + '</div></div>';
      }).join('') + '</div>' +
      (v === 'chart' ? chartHtml(m, idx) : tableHtml(m)) +
      '<table class="tb"><tbody>' +
      '<tr><td class="mut" style="width:96px">用途</td><td>' + esc(m.use || '') + '</td></tr>' +
      '<tr><td class="mut">架构</td><td>' + esc(m.architecture || '') + (m.params ? ' · <span class="num">' + (m.params / 1e6).toFixed(2) + ' M</span> 参数' : '') + '</td></tr>' +
      '<tr><td class="mut">数据集</td><td><div style="display:flex;gap:8px;align-items:flex-start;justify-content:space-between"><div>' + dsText(m) + '</div>' +
      (LG.isAdmin() ? '<button class="btn sm" data-ds="' + esc(m.file) + '">' + icon('edit', 14) + '填写</button>' : '') + '</div></td></tr>' +
      '<tr><td class="mut">训练配置</td><td class="num">epochs ' + (ta.epochs || '--') + ' · imgsz ' + (ta.imgsz || '--') + ' · batch ' + (ta.batch || '--') + ' · lr0 ' + (ta.lr0 || '--') +
      (m.trained_at ? ' · ' + esc(String(m.trained_at).slice(0, 10)) : '') + '</td></tr>' +
      '<tr><td class="mut">识别类别</td><td style="line-height:1.9"><span class="num">' + (m.classes || []).length + '</span> 类：' + esc((m.classes || []).join(' · ')) + '</td></tr>' +
      '</tbody></table></section>';
  }

  var STATIC = '<div class="cols">' +
    '<section class="panel" aria-label="交叉验证规则" style="flex:1 1 520px"><div class="ph dk">' + icon('layers') + '交叉验证 · 风险因子权重<span class="sp"></span><small>默认中危 ≥ 30 · 高危 ≥ 70 · 可按区域调整</small></div>' +
    '<table class="tb"><thead><tr><th>数据源</th><th>风险因子</th><th>分值</th></tr></thead><tbody>' +
    [['人员 × 传感器', '加热中台前无人', '70'], ['人员 × 传感器', '加热中人员伏案', '70'], ['人员 × 器皿', '台面有试剂或加热中出现饮食', '60'],
      ['器皿 × 传感器', '加热时台面有不可加热量器', '35'], ['器皿 × 传感器', '加热中器皿靠近桌边', '35'], ['人员 × 传感器', '加热 / 沸腾中未佩戴护目镜或手套', '30–35'],
      ['人员 × 器皿', '台面有器皿时未佩戴防护', '15'], ['温度预测', '干烧风险分 ≥ 0.6 / ≥ 0.3', '70 / 30'], ['规则引擎', '紧急事件或断电锁定 / 警告事件', '100 / 40']].map(function (r) {
      return '<tr><td><span class="tag ' + (/×/.test(r[0]) ? 't-ink' : 't-soft') + '">' + r[0] + '</span></td><td>' + r[1] + '</td><td class="num">' + r[2] + '</td></tr>';
    }).join('') + '</tbody></table></section>' +
    '<section class="panel" aria-label="主控决策规则" style="flex:1 1 520px"><div class="ph rd">' + icon('chip') + '主控决策 · 规则与执行<span class="sp"></span><small>出厂默认值 · 可按区域调整</small></div>' +
    '<table class="tb"><thead><tr><th>编号</th><th>条件</th><th>动作</th></tr></thead><tbody>' +
    [['R1', '热源 ≥ 120℃', 'cut'], ['R2', '≥ 80℃ 且 ≥ 2℃/s', 'warn'], ['R3', '热源 ≥ 50℃ 且无人 · 持续 60 s', 'cut'], ['R4', '无测温 + 可加热器皿 + 无人 + 环境 &gt; 55℃', 'cut'],
      ['R5', '烟雾 ≥ 1800', 'cut'], ['R6–R8', '高湿 · 环境高温 · 量器受热', 'warn'], ['R9', '预测 ≤ 90 s 干烧 · 沸腾无人 300 s', 'warn']].map(function (r) {
      return '<tr><td class="num">' + r[0] + '</td><td>' + r[1] + '</td><td>' + (r[2] === 'cut' ? '<span class="tag t-high">断电</span>' : '<span class="tag t-mid">警告 / 提醒</span>') + '</td></tr>';
    }).join('') +
    '<tr class="bad"><td class="num">固件</td><td>热源 ≥ 150℃ · 烟雾 ≥ 2500 · 心跳中断 30 s</td><td><span class="tag t-high">本地断电</span></td></tr></tbody></table></section></div>';

  function fieldHtml(fd) {
    var acc = fd.reviewed ? (fd.correct / fd.reviewed * 100).toFixed(1) + '%' : '--';
    return '<section class="panel stats" aria-label="现场复核">' +
      '<div class="stat">' + icon('check', 28) + '<div><div class="mut">现场复核准确率</div><div class="big">' + acc + '</div></div></div>' +
      '<div class="stat">' + icon('doc', 28) + '<div><div class="mut">已复核事件</div><div class="big">' + (fd.reviewed || 0) + '</div></div></div>' +
      '<div class="stat">' + icon('ok', 28) + '<div><div class="mut">判定正确</div><div class="big">' + (fd.correct || 0) + '</div></div></div>' +
      '<div class="stat">' + icon('monitor', 28) + '<div><div class="mut">参与终端</div><div class="big">' + (fd.nodes || 0) + '</div></div></div></section>';
  }

  function editDataset(m, reload) {
    var d = m.dataset || {};
    var f = function (k, label) { return '<label class="lbl">' + label + '<input class="fld num" type="number" min="0" data-k="' + k + '" value="' + esc(d[k] == null ? '' : d[k]) + '"></label>'; };
    LG.dialog('数据集信息 · ' + m.file, '<div class="formgrid">' + f('train_images', '训练集图片数') + f('val_images', '验证集图片数') + f('test_images', '测试集图片数') + f('instances', '标注框总数') + '</div>' +
      '<label class="lbl">来源<input class="fld" data-k="source" maxlength="200" value="' + esc(d.source || '') + '"></label>' +
      '<div class="row" style="padding:0;border:0"><button class="btn pri" data-save>' + icon('check', 18) + '保存</button><button class="btn" data-close>取消</button></div>', function (dlg) {
      LG.$('[data-save]', dlg).onclick = function () {
        var body = { file: m.file };
        LG.$$('[data-k]', dlg).forEach(function (i) { body[i.dataset.k] = i.value; });
        LG.api('PUT', '/api/models/dataset', body).then(function () { LG.closeDialog(); LG.toast('已保存'); reload(); }).catch(LG.fail);
      };
    });
  }

  LG.view('models', {
    title: '模型看板', rail: '模型', icon: 'chart',
    render: function (main) {
      LG.setCrumb('<span class="mut">模型看板</span><span class="mut">/</span><b>模型架构与训练指标</b>');
      var card = null;
      function paint() {
        var ms = card.models || [];
        main.innerHTML = '<section class="panel stats" aria-label="系统组成">' +
          ms.map(function (m) {
            return '<div class="stat">' + icon(/人员/.test(m.role) ? 'goggles' : 'flask', 28) + '<div><div class="hd" style="font-size:18px">' + esc((m.role || '').replace(/（.*?）/, '')) + '</div>' +
              '<div class="mut">' + esc((m.architecture || '').split('（')[0]) + ' · ' + (m.classes || []).length + ' 类</div><div class="num" style="font-weight:700">mAP50 ' + LG.fmt((m.final || {}).map50, 3) + '</div></div></div>';
          }).join('') +
          '<div class="stat" style="background:var(--soft2)">' + icon('layers', 28) + '<div><div class="hd" style="font-size:18px">交叉验证系统</div><div class="mut">人员 × 器皿 × 传感器</div><div class="num" style="font-weight:700">三级 · 可按区域调整</div></div></div>' +
          '<div class="stat" style="background:var(--soft2)">' + icon('chip', 28) + '<div><div class="hd" style="font-size:18px">主控决策系统</div><div class="mut">规则 R1–R9 · 固件硬上限</div><div class="num" style="font-weight:700">按区域阈值</div></div></div></section>' +
          (card.missing ? '<div class="panel empty">' + esc(card.missing) + '</div>' : '') +
          '<div class="cols">' + ms.map(modelHtml).join('') + '</div>' + fieldHtml(card.field || {}) + STATIC;
        bind();
      }
      function bind() {
        LG.$$('[data-chart]', main).forEach(function (el) {
          var m = card.models[Number(el.dataset.chart)], c = m.curves, n = c.epoch.length;
          var cross = LG.$('.cross', el), da = LG.$('[data-d="a"]', el), db = LG.$('[data-d="b"]', el), hv = LG.$('[data-hover]', el);
          var at = function (i) {
            var x = (n > 1 ? i / (n - 1) * 100 : 0) + '%';
            cross.hidden = false; cross.style.left = x; da.style.left = x; db.style.left = x;
            da.style.top = (1 - c[K.a][i]) * 100 + '%'; db.style.top = (1 - c[K.b][i]) * 100 + '%';
            hv.textContent = 'epoch ' + (i + 1) + ' · P ' + c[K.p][i].toFixed(3) + ' · R ' + c[K.r][i].toFixed(3) + ' · mAP50 ' + c[K.a][i].toFixed(3) + ' · mAP50-95 ' + c[K.b][i].toFixed(3);
          };
          var hit = LG.$('.hit', el);
          hit.onmouseover = function (e) { if (e.target.dataset.i) at(Number(e.target.dataset.i)); };
          hit.onmouseleave = function () { at(n - 1); cross.hidden = true; hv.textContent = '悬停查看各轮指标'; };
        });
        main.onclick = function (e) {
          var t = e.target.closest('[data-view], [data-ds]');
          if (!t) return;
          if (t.dataset.view) { view[t.dataset.m] = t.dataset.view; paint(); }
          else editDataset(card.models.filter(function (m) { return m.file === t.dataset.ds; })[0], load);
        };
      }
      function load() { LG.api('GET', '/api/models').then(function (c) { card = c; paint(); }).catch(LG.fail); }
      load();
    }
  });
})();
