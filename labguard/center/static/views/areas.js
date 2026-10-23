/* 区域与终端（管理员）：楼栋 / 房间 / 实验桌三级树，批量建桌，终端登记、绑定、换密钥 */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var st = { sel: null };
  var CHILD = { group: ['group', 'room', 'desk'], room: ['desk'], desk: [] };
  var KIND_IC = { group: 'building', room: 'flask', desk: 'desk' };

  function tokenDialog(title, token) {
    var url = location.protocol + '//' + location.host;
    LG.secret(title, '节点密钥（只显示这一次）', token,
      '填写到该终端 labguard/config.yaml：center.url: ' + url + '，center.node_token: 上面的密钥（或环境变量 LABGUARD_NODE_TOKEN），重启终端程序后生效。');
  }

  LG.view('areas', {
    title: '区域与终端', rail: '区域', icon: 'building', admin: true,
    render: function (main) {
      LG.setCrumb('<span class="mut">系统管理</span><span class="mut">/</span><b>区域与终端</b>');
      var nodes = [];

      function treeHtml() {
        var rows = LG.flatTree();
        if (!rows.length) return '<div class="empty">尚未建立区域</div>';
        return rows.map(function (x) {
          var a = x.a, n = a.node;
          var badge = a.kind !== 'desk' ? '' : n ? '<span class="' + LG.LV[LG.deskLevel(n)].tag + '">' + LG.LV[LG.deskLevel(n)].text + '</span>' : '<span class="tag t-off">未绑定</span>';
          return '<button class="tree' + (a.id === st.sel ? ' on' : '') + '" data-area="' + a.id + '" style="padding-left:' + (12 + x.depth * 18) + 'px">' + icon(KIND_IC[a.kind], 16) +
            '<span class="grow">' + esc(a.name) + '</span>' + badge + '</button>';
        }).join('');
      }

      function detailHtml() {
        var a = LG.areaById(st.sel);
        if (!a) {
          return '<section class="panel"><div class="ph">' + icon('plus') + '新建顶层区域</div><div class="pad formgrid">' +
            '<label class="lbl">名称<input class="fld" id="nName" maxlength="40" placeholder="如：化学楼"></label>' +
            '<label class="lbl">类型<select class="fld" id="nKind"><option value="group">楼栋 / 分组</option><option value="room">房间</option></select></label>' +
            '<div style="align-self:end"><button class="btn pri" id="nAdd">' + icon('plus') + '新建</button></div></div></section>';
        }
        var kids = LG.children(a.id), canChild = CHILD[a.kind];
        var node = nodes.filter(function (n) { return n.area_id === a.id; })[0];
        var free = nodes.filter(function (n) { return n.area_id == null; });
        var html = '<section class="panel"><div class="ph">' + icon(KIND_IC[a.kind]) + esc(a.name) + '<span class="sp"></span><small>' + LG.KIND[a.kind] + ' · ' + esc(LG.pathOf(a.id)) + '</small></div>' +
          '<div class="pad formgrid"><label class="lbl">名称<input class="fld" id="eName" maxlength="40" value="' + esc(a.name) + '"></label>' +
          '<label class="lbl">备注<input class="fld" id="eNote" maxlength="200" value="' + esc(a.note || '') + '"></label></div>' +
          '<div class="row foot"><button class="btn pri" id="eSave">' + icon('check') + '保存</button>' +
          '<button class="btn dng" id="eDel"' + (kids.length || node ? ' disabled title="请先删除下级区域或解绑终端"' : '') + '>' + icon('trash') + '删除</button>' +
          '<span class="mut">下级 <span class="num">' + kids.length + '</span> 个</span></div></section>';
        if (a.kind === 'room' || a.kind === 'desk') {
          var L = a.layout || {};
          html += '<section class="panel"><div class="ph">' + icon('plan') + '平面图位置<span class="sp"></span><small>' + (a.kind === 'room' ? '占所在楼层' : '占所在房间') + '的百分比 · ' + (a.layout ? '手动' : '自动排布') + '</small></div>' +
            '<div class="pad formgrid">' + [['x', '左边距'], ['y', '上边距'], ['w', '宽度'], ['h', '高度']].map(function (f) {
              return '<label class="lbl">' + f[1] + ' %<input class="fld num" id="L' + f[0] + '" type="number" min="0" max="100" step="0.5" value="' + (L[f[0]] != null ? L[f[0]] : '') + '"></label>';
            }).join('') + '</div>' +
            '<div class="row foot"><button class="btn pri" id="lSave">' + icon('check') + '保存位置</button><button class="btn" id="lAuto"' + (a.layout ? '' : ' disabled') + '>' + icon('reset') + '恢复自动排布</button></div></section>';
        }
        if (canChild.length) {
          html += '<section class="panel"><div class="ph">' + icon('plus') + '添加下级</div><div class="pad formgrid">' +
            '<label class="lbl">名称<input class="fld" id="cName" maxlength="40" placeholder="' + (a.kind === 'group' ? '如：A实验室' : '如：1号桌') + '"></label>' +
            '<label class="lbl">类型<select class="fld" id="cKind">' + canChild.map(function (k) { return '<option value="' + k + '"' + (k === (a.kind === 'group' ? 'room' : 'desk') ? ' selected' : '') + '>' + LG.KIND[k] + '</option>'; }).join('') + '</select></label>' +
            '<div style="align-self:end"><button class="btn pri" id="cAdd">' + icon('plus') + '添加</button></div></div>' +
            '<div class="row head">批量添加实验桌</div><div class="pad formgrid">' +
            '<label class="lbl">名称格式<input class="fld" id="bPat" value="{n}号桌" maxlength="40"></label>' +
            '<label class="lbl">起始编号<input class="fld num" id="bFrom" type="number" min="1" value="' + (kids.length + 1) + '"></label>' +
            '<label class="lbl">结束编号<input class="fld num" id="bTo" type="number" min="1" value="' + (kids.length + 8) + '"></label>' +
            '<div style="align-self:end"><button class="btn" id="bAdd">' + icon('layers') + '批量添加</button></div></div></section>';
        }
        if (a.kind === 'desk') {
          html += '<section class="panel"><div class="ph dk">' + icon('monitor') + '终端</div>' + (node ?
            '<div class="row"><b>' + esc(node.name) + '</b><span class="tag ' + (node.online ? 't-low' : 't-off') + '">' + (node.online ? '在线' : '离线') + '</span>' +
            '<span class="mut num">' + esc(node.last_ip || '') + ' · ' + LG.ago(node.last_seen) + ' · 密钥 …' + esc(node.token_hint) + '</span></div>' +
            '<div class="row"><button class="btn" data-unbind="' + node.id + '">' + icon('x') + '解绑</button><button class="btn" data-rotate="' + node.id + '">' + icon('key') + '更换密钥</button></div>' :
            '<div class="pad formgrid"><label class="lbl">新终端名称<input class="fld" id="tName" maxlength="40" placeholder="如：LG-' + esc(a.name) + '"></label>' +
            '<div style="align-self:end"><button class="btn pri" id="tAdd">' + icon('plus') + '登记并绑定</button></div>' +
            (free.length ? '<label class="lbl">或绑定已登记终端<select class="fld" id="tFree">' + free.map(function (n) { return '<option value="' + n.id + '">' + esc(n.name) + '</option>'; }).join('') + '</select></label>' +
              '<div style="align-self:end"><button class="btn" id="tBind">' + icon('check') + '绑定</button></div>' : '') + '</div>') + '</section>';
        }
        return html;
      }

      function nodesHtml() {
        if (!nodes.length) return '<div class="empty">尚未登记终端</div>';
        return '<div class="tbwrap"><table class="tb" style="min-width:760px"><thead><tr><th>终端</th><th>绑定实验桌</th><th>状态</th><th>最近上报</th><th>地址</th><th>热源 / 烟雾硬上限</th><th>上报次数</th><th><span class="sr">操作</span></th></tr></thead><tbody>' +
          nodes.map(function (n) {
            return '<tr><td style="font-weight:600">' + esc(n.name) + '<div class="mut num" style="font-size:12px;font-weight:normal">…' + esc(n.token_hint) + '</div></td><td>' + esc(n.path) + '</td>' +
              '<td><span class="tag ' + (n.online ? 't-low' : 't-off') + '">' + (n.online ? '在线' : '离线') + '</span></td><td class="num">' + LG.ago(n.last_seen) + '</td>' +
              '<td class="num">' + esc(n.last_ip || '--') + (n.web_port ? ':' + n.web_port : '') + '</td><td class="num">' + LG.fmt(n.hard_limit_c, 0, '℃') + ' / ' + (n.smoke_limit_raw || '--') + '</td>' +
              '<td class="num">' + (n.report_count || 0) + '</td><td style="white-space:nowrap"><button class="btn sm flat" data-rotate="' + n.id + '">' + icon('key', 14) + '换密钥</button> ' +
              '<button class="btn sm flat" data-delnode="' + n.id + '" aria-label="删除终端">' + icon('trash', 14) + '</button></td></tr>';
          }).join('') + '</tbody></table></div>';
      }

      function paint() {
        main.innerHTML = '<div class="cols"><section class="panel" aria-label="区域树" style="flex:1 1 280px"><div class="ph">' + icon('tree') + '区域树<span class="sp"></span>' +
          '<button class="btn sm" id="aTop">' + icon('plus', 14) + '顶层</button></div></section>' +
          '<div style="flex:2 1 480px;display:flex;flex-direction:column;gap:16px;min-width:0" id="aDetail">' + detailHtml() + '</div></div>' +
          '<section class="panel" aria-label="终端列表"><div class="ph">' + icon('monitor') + '终端列表<span class="sp"></span><small>离线超过 10 s 视为离线</small></div>' + nodesHtml() + '</section>';
        var treeBox = document.createElement('div');
        treeBox.style.cssText = 'max-height:640px;overflow-y:auto';
        treeBox.innerHTML = treeHtml();
        LG.$('.panel[aria-label="区域树"]', main).appendChild(treeBox);
      }

      function load() {
        return Promise.all([LG.loadTree(true), LG.api('GET', '/api/nodes')]).then(function (r) { nodes = r[1]; paint(); }).catch(LG.fail);
      }
      function after(msg) { return function () { LG.toast(msg); return load(); }; }
      function val(id) { var e = LG.$('#' + id); return e ? e.value.trim() : ''; }

      main.onclick = function (e) {
        var t = e.target.closest('button, [data-area]');
        if (!t) return;
        var a = LG.areaById(st.sel);
        if (t.dataset.area) { st.sel = Number(t.dataset.area); paint(); return; }
        switch (t.id) {
          case 'aTop': st.sel = null; paint(); return;
          case 'nAdd': LG.api('POST', '/api/areas', { name: val('nName'), parent_id: null, kind: val('nKind') }).then(function (r) { st.sel = r.id; })
            .then(after('已新建')).catch(LG.fail); return;
          case 'eSave': LG.api('PATCH', '/api/areas/' + a.id, { name: val('eName'), note: val('eNote') }).then(after('已保存')).catch(LG.fail); return;
          case 'eDel': LG.confirm('删除区域', '<div>' + esc(LG.pathOf(a.id)) + '</div><div class="mut">该区域的阈值、授权与语音设置一并删除。</div>', '删除', true).then(function (ok) {
            if (ok) LG.api('DELETE', '/api/areas/' + a.id).then(function () { st.sel = a.parent_id; }).then(after('已删除')).catch(LG.fail);
          }); return;
          case 'cAdd': LG.api('POST', '/api/areas', { name: val('cName'), parent_id: a.id, kind: val('cKind') }).then(after('已添加')).catch(LG.fail); return;
          case 'bAdd': LG.api('POST', '/api/areas/batch_desks', { parent_id: a.id, pattern: val('bPat'), start: Number(val('bFrom')), end: Number(val('bTo')) })
            .then(function (r) { LG.toast('已添加 ' + r.created.length + ' 张实验桌'); return load(); }).catch(LG.fail); return;
          case 'tAdd': LG.api('POST', '/api/nodes', { name: val('tName') || 'LG-' + a.name, area_id: a.id }).then(function (r) { tokenDialog('终端已登记', r.token); return load(); }).catch(LG.fail); return;
          case 'lSave': LG.api('PATCH', '/api/areas/' + a.id, { layout: { x: Number(val('Lx')), y: Number(val('Ly')), w: Number(val('Lw')), h: Number(val('Lh')) } })
            .then(after('位置已保存')).catch(LG.fail); return;
          case 'lAuto': LG.api('PATCH', '/api/areas/' + a.id, { layout: null }).then(after('已恢复自动排布')).catch(LG.fail); return;
          case 'tBind': LG.api('PATCH', '/api/nodes/' + val('tFree'), { area_id: a.id }).then(after('已绑定')).catch(LG.fail); return;
        }
        var d = t.dataset;
        if (d.unbind) LG.api('PATCH', '/api/nodes/' + d.unbind, { area_id: null }).then(after('已解绑')).catch(LG.fail);
        else if (d.rotate) LG.confirm('更换节点密钥', '<div>旧密钥立即失效，终端需填写新密钥后才能继续上报。</div>', '更换').then(function (ok) {
          if (ok) LG.api('POST', '/api/nodes/' + d.rotate + '/rotate').then(function (r) { tokenDialog('密钥已更换', r.token); return load(); }).catch(LG.fail);
        });
        else if (d.delnode) {
          var n = nodes.filter(function (x) { return x.id === Number(d.delnode); })[0];
          LG.confirm('删除终端', '<div>' + esc(n.name) + '</div><div class="mut">终端本机的安全判断与断电不受影响，只是不再接入总后台。</div>', '删除', true).then(function (ok) {
            if (ok) LG.api('DELETE', '/api/nodes/' + n.id).then(after('已删除')).catch(LG.fail);
          });
        }
      };
      load();
    }
  });
})();
