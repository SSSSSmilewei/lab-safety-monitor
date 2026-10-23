/* 账号与授权（管理员）：账号列表、混合粒度授权（整栋 / 整间 / 单桌）、角色权限、审计日志 */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var st = { sel: null, open: {} };

  function descendants(id) {
    var out = [];
    (function walk(p) { LG.children(p).forEach(function (a) { out.push(a.id); walk(a.id); }); })(id);
    return out;
  }
  function scopeText(u) {
    if (u.role === 'admin') return '全部区域';
    if (!u.grants.length) return '未授权';
    return u.grants.map(function (g) { return LG.pathOf(g).split(' / ').slice(-2).join(' / '); }).join(' · ');
  }

  var MATRIX = [['查看状态 · 画面 · 事件', '全部区域', '授权范围内'], ['远程断电 · 静音', 'ok', '授权范围内'], ['安全助手问答 · 安全报告', 'ok', '授权范围内'],
    ['阈值配置 · 语音配置', 'ok', '授权范围内'], ['模型数据集信息', 'ok', 'no'], ['区域 · 终端 · 账号管理', 'ok', 'no'], ['远程通电', 'no', 'no']];

  LG.view('access', {
    title: '账号与授权', rail: '账号', icon: 'access', admin: true,
    render: function (main) {
      LG.setCrumb('<span class="mut">系统管理</span><span class="mut">/</span><b>账号与授权</b>');
      var users = [], draft = null, auditHtml = '<div class="empty">加载中…</div>';

      function grantTree(u) {
        if (u.role === 'admin') return '<div class="empty">管理员默认拥有全部区域权限</div>';
        var g = draft;
        var html = '';
        (function walk(pid, depth, covered) {
          LG.children(pid).forEach(function (a) {
            var direct = g.indexOf(a.id) >= 0, inherit = covered;
            var kids = LG.children(a.id), partial = !direct && !inherit && descendants(a.id).some(function (d) { return g.indexOf(d) >= 0; });
            var open = kids.length && (st.open[a.id] != null ? st.open[a.id] : (a.kind === 'group' || partial));
            var note = direct ? '<span class="tag t-ink">已授权</span>' : inherit ? '<span class="tag t-soft">含于上级</span>' : partial ? '<span class="tag t-mid">部分</span>' : '';
            html += '<div class="row" style="padding-left:' + (12 + depth * 22) + 'px;background:' + (direct ? 'var(--soft)' : '#fff') + '">' +
              (kids.length ? '<button class="btn sm flat" data-open="' + a.id + '" aria-label="' + (open ? '收起' : '展开') + '" style="padding:0 4px">' + (open ? '−' : '+') + '</button>' : '<span style="width:28px"></span>') +
              '<label class="chk grow"><input type="checkbox" data-g="' + a.id + '"' + (direct || inherit ? ' checked' : '') + (inherit ? ' disabled' : '') + '>' +
              '<span>' + esc(a.name) + '</span><span class="mut" style="font-weight:normal;font-size:12px">' + LG.KIND[a.kind] + '</span></label>' + note + '</div>';
            if (open) walk(a.id, depth + 1, inherit || direct);
          });
        })(null, 0, false);
        return html || '<div class="empty">尚未建立区域</div>';
      }

      function deskCount() {
        var set = {};
        draft.forEach(function (g) { [g].concat(descendants(g)).forEach(function (id) { var a = LG.areaById(id); if (a && a.kind === 'desk') set[id] = 1; }); });
        return Object.keys(set).length;
      }

      function paint() {
        var u = users.filter(function (x) { return x.id === st.sel; })[0] || users.filter(function (x) { return x.role !== 'admin'; })[0] || users[0];
        if (u && st.sel !== u.id) { st.sel = u.id; draft = u.grants.slice(); }
        var changed = u && JSON.stringify(draft.slice().sort()) !== JSON.stringify(u.grants.slice().sort());
        main.innerHTML =
          '<div class="cols"><section class="panel" aria-label="账号列表" style="flex:3 1 520px"><div class="ph">' + icon('user') + '账号列表<span class="sp"></span>' +
          '<button class="btn sm" id="aNew">' + icon('plus', 14) + '新建账号</button></div><div class="tbwrap"><table class="tb" style="min-width:600px"><thead><tr><th>姓名</th><th>用户名</th><th>角色</th><th>授权范围</th><th>状态</th><th><span class="sr">操作</span></th></tr></thead><tbody>' +
          users.map(function (x) {
            return '<tr class="' + (x.id === st.sel ? 'sel' : '') + '"><td style="font-weight:600">' + esc(x.display_name) + (x.ui_style === 'pixel' ? ' <span class="tag t-soft" title="界面风格：像素">像素</span>' : '') + '</td>' +
              '<td class="num">' + esc(x.username) + '</td><td><span class="tag ' + (x.role === 'admin' ? 't-ink' : 't-soft') + '">' + (x.role === 'admin' ? '管理员' : '教师') + '</span></td>' +
              '<td>' + esc(scopeText(x)) + '</td><td>' + (x.active ? (x.must_change ? '<span class="tag t-mid">待改密</span>' : '<span class="tag t-low">启用</span>') : '<span class="tag t-off">停用</span>') + '</td>' +
              '<td style="white-space:nowrap">' + (x.role === 'admin' ? '' : '<button class="btn sm' + (x.id === st.sel ? ' on' : '') + '" data-sel="' + x.id + '">' + icon('tree', 14) + '授权</button> ') +
              '<button class="btn sm flat" data-edit="' + x.id + '">' + icon('edit', 14) + '编辑</button></td></tr>';
          }).join('') + '</tbody></table></div></section>' +
          '<section class="panel" aria-label="角色权限" style="flex:2 1 320px"><div class="ph dk">' + icon('key') + '角色权限</div><table class="tb"><thead><tr><th>权限项</th><th>管理员</th><th>教师</th></tr></thead><tbody>' +
          MATRIX.map(function (r) {
            var c = function (v) { return v === 'ok' ? icon('check', 16) : v === 'no' ? '<span class="mut">' + icon('x', 16) + '</span>' : esc(v); };
            return '<tr><td>' + r[0] + '</td><td>' + c(r[1]) + '</td><td>' + c(r[2]) + '</td></tr>';
          }).join('') + '</tbody></table></section></div>' +
          '<div class="cols"><section class="panel" aria-label="授权范围" style="flex:3 1 520px"><div class="ph">' + icon('tree') + '授权范围<span class="sp"></span><small>' + (u ? esc(u.display_name) : '') + ' · 勾选上级即包含其下全部实验桌</small></div>' +
          '<div id="aTree" style="max-height:520px;overflow-y:auto">' + (u ? grantTree(u) : '') + '</div>' +
          (u && u.role !== 'admin' ? '<div class="row foot"><button class="btn pri" id="aSave"' + (changed ? '' : ' disabled') + '>' + icon('check') + '保存授权</button>' +
            '<span class="mut">生效实验桌 <span class="num">' + deskCount() + '</span> 张</span></div>' : '') + '</section>' +
          '<section class="panel" aria-label="审计日志" style="flex:2 1 320px"><div class="ph">' + icon('doc') + '审计日志</div><div id="aAudit" style="max-height:560px;overflow-y:auto">' + auditHtml + '</div></section></div>';
      }

      function loadAudit() {
        return LG.api('GET', '/api/audit?n=60').then(function (rows) {
          var tagOf = function (a) { return /断电/.test(a) ? 't-high' : /失败|删除/.test(a) ? 't-mid' : 't-soft'; };
          auditHtml = rows.map(function (r) {
            return '<div class="row" style="align-items:flex-start"><span class="num mut">' + LG.time(r.ts) + '</span><span class="tag ' + tagOf(r.action) + '">' + esc(r.action) + '</span>' +
              '<span class="grow" style="flex:1 1 160px;word-break:break-all">' + esc(r.user) + (r.detail ? '<span class="mut"> · ' + esc(r.detail.length > 120 ? r.detail.slice(0, 120) + '…' : r.detail) + '</span>' : '') + '</span></div>';
          }).join('') || '<div class="empty">暂无记录</div>';
        });
      }
      function load() {
        return Promise.all([LG.api('GET', '/api/users'), LG.loadTree(true), loadAudit()]).then(function (r) {
          users = r[0];
          var u = users.filter(function (x) { return x.id === st.sel; })[0];
          draft = u ? u.grants.slice() : null;
          if (!u) st.sel = null;
          paint();
        }).catch(LG.fail);
      }

      function userForm(u) {
        var isNew = !u;
        u = u || { username: '', display_name: '', role: 'teacher', active: 1, ui_style: 'standard' };
        LG.dialog(isNew ? '新建账号' : '编辑账号 · ' + u.display_name,
          '<div class="formgrid"><label class="lbl">用户名<input class="fld num" id="fUser" value="' + esc(u.username) + '"' + (isNew ? '' : ' disabled') + ' maxlength="32" placeholder="字母、数字、下划线"></label>' +
          '<label class="lbl">姓名<input class="fld" id="fName" value="' + esc(u.display_name) + '" maxlength="32"></label>' +
          '<label class="lbl">角色<select class="fld" id="fRole"><option value="teacher"' + (u.role === 'teacher' ? ' selected' : '') + '>教师</option><option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>管理员</option></select></label>' +
          '<label class="lbl">界面风格<select class="fld" id="fStyle"><option value="standard">标准</option><option value="pixel"' + (u.ui_style === 'pixel' ? ' selected' : '') + '>像素（旧版）</option></select></label></div>' +
          (isNew ? '<label class="lbl">初始密码（留空则随机生成）<input class="fld" id="fPw" type="text" autocomplete="off"></label><div class="mut">首次登录须修改密码。</div>' :
            '<label class="chk"><input type="checkbox" id="fActive"' + (u.active ? ' checked' : '') + '>启用账号</label>') +
          '<div class="row" style="padding:0;border:0"><button class="btn pri" data-save>' + icon('check', 18) + '保存</button>' +
          (isNew ? '' : '<button class="btn" data-reset>' + icon('key', 18) + '重置密码</button>' + (u.id === LG.S.me.id ? '' : '<button class="btn dng" data-del>' + icon('trash', 18) + '删除</button>')) +
          '<button class="btn" data-close>取消</button></div>', function (d) {
          LG.$('[data-save]', d).onclick = function () {
            var body = { display_name: LG.$('#fName', d).value.trim(), role: LG.$('#fRole', d).value, ui_style: LG.$('#fStyle', d).value };
            var p;
            if (isNew) {
              body.username = LG.$('#fUser', d).value.trim(); body.password = LG.$('#fPw', d).value;
              p = LG.api('POST', '/api/users', body).then(function (r) {
                st.sel = r.id;
                return LG.api('PATCH', '/api/users/' + r.id, { ui_style: body.ui_style }).then(function () {
                  LG.secret('账号已创建', '初始密码（只显示这一次）', r.initial_password, '用户名 ' + body.username + '，首次登录须修改密码。');
                });
              });
            } else {
              body.active = LG.$('#fActive', d).checked;
              p = LG.api('PATCH', '/api/users/' + u.id, body).then(function (r) {
                LG.closeDialog(); LG.toast('已保存');
                if (u.id === LG.S.me.id) { LG.S.me.ui_style = r.ui_style; LG.S.me.display_name = r.display_name; LG.applyStyle(); }
              });
            }
            p.then(load).catch(LG.fail);
          };
          var rb = LG.$('[data-reset]', d);
          if (rb) rb.onclick = function () {
            LG.api('POST', '/api/users/' + u.id + '/reset_password').then(function (r) {
              LG.secret('密码已重置', '临时密码（只显示这一次）', r.initial_password, u.display_name + ' 下次登录须修改密码，现有登录已失效。');
            }).catch(LG.fail);
          };
          var db = LG.$('[data-del]', d);
          if (db) db.onclick = function () {
            LG.closeDialog();
            LG.confirm('删除账号', '<div>' + esc(u.display_name) + '（' + esc(u.username) + '）及其授权将被删除。</div>', '删除', true).then(function (ok) {
              if (ok) LG.api('DELETE', '/api/users/' + u.id).then(function () { st.sel = null; load(); }).catch(LG.fail);
            });
          };
        });
      }

      main.onclick = function (e) {
        var t = e.target.closest('[data-sel], [data-edit], [data-open], #aNew, #aSave');
        if (!t) return;
        if (t.dataset.sel) { st.sel = Number(t.dataset.sel); draft = users.filter(function (x) { return x.id === st.sel; })[0].grants.slice(); paint(); }
        else if (t.dataset.edit) userForm(users.filter(function (x) { return x.id === Number(t.dataset.edit); })[0]);
        else if (t.dataset.open) { var id = Number(t.dataset.open), a = LG.$('[data-open="' + id + '"]'); st.open[id] = a.textContent === '+'; paint(); }
        else if (t.id === 'aNew') userForm(null);
        else if (t.id === 'aSave') {
          LG.api('PUT', '/api/users/' + st.sel + '/grants', { areas: draft }).then(function () { LG.toast('授权已保存'); load(); }).catch(LG.fail);
        }
      };
      main.onchange = function (e) {
        var id = e.target.dataset && Number(e.target.dataset.g);
        if (!id) return;
        if (e.target.checked) {
          var sub = descendants(id);
          draft = draft.filter(function (g) { return sub.indexOf(g) < 0; });     // 勾选上级后，下级的单独授权就多余了
          draft.push(id);
        } else draft = draft.filter(function (g) { return g !== id; });
        paint();
      };
      load();
    }
  });
})();
