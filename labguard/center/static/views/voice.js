/* 语音提醒：按区域为「事件 × 语气」指定音频（合成或教师录音），终端上报时自动同步 */
(function () {
  'use strict';
  var LG = window.LG, esc = LG.esc, icon = LG.icon;
  var st = { area: null, tone: 'gentle', voice: 'zh-CN-XiaoxiaoNeural', rate: 0 };
  var audio = null;

  function play(id) {
    if (audio) audio.pause();
    audio = new Audio('/api/voice/' + id + '/audio');
    audio.play().catch(function () { LG.toast('无法播放该音频', true); });
  }

  function areaOptions() {
    var opts = LG.isAdmin() ? [{ id: 0, label: '全局默认' }] : [];
    LG.flatTree(function (a) { return a.managed; }).forEach(function (x) {
      opts.push({ id: x.a.id, label: new Array(x.depth + 1).join('　') + x.a.name + '（' + LG.KIND[x.a.kind] + '）' });
    });
    return opts;
  }

  LG.view('voice', {
    title: '语音提醒', rail: '语音', icon: 'speaker',
    render: function (main) {
      LG.setCrumb('<span class="mut">语音提醒</span><span class="mut">/</span><b>语音包配置</b>');
      var opts = areaOptions();
      if (!opts.length) { main.innerHTML = '<div class="panel empty">无可配置的区域</div>'; return; }
      if (st.area == null || !opts.some(function (o) { return o.id === st.area; })) st.area = opts[0].id;
      var info = null, map = null;

      function assetById(id) { return info.assets.filter(function (a) { return a.id === id; })[0]; }
      function srcTag(a) {
        if (!a) return '<span class="tag t-off">内置提示音</span>';
        return a.source === 'upload' ? '<span class="tag t-ink">' + icon('mic', 14) + '录音</span>' : '<span class="tag t-soft">' + icon('chip', 14) + '合成</span>';
      }

      function paint() {
        var kinds = info.kinds, tone = st.tone;
        var ownMap = {};
        (map.own || []).forEach(function (m) { ownMap[m.kind + '|' + m.tone] = m.asset_id; });
        var rows = Object.keys(kinds).map(function (k) {
          var aid = (map.resolved[k] || {})[tone], a = aid ? assetById(aid) : null, own = ownMap[k + '|' + tone] != null;
          var text = a && a.text ? a.text : kinds[k][tone];
          return '<tr><td style="font-weight:600;white-space:nowrap">' + esc(kinds[k].name) + '</td><td>' + esc(text) +
            (a ? '<div class="mut" style="font-size:12px">' + esc(a.name) + (own ? '' : ' · 继承') + '</div>' : '') + '</td><td>' + srcTag(a) + '</td>' +
            '<td style="white-space:nowrap">' + (a ? '<button class="btn sm flat" data-play="' + a.id + '" aria-label="试听">' + icon('play', 14) + '</button> ' : '') +
            '<button class="btn sm flat" data-synth="' + k + '"' + (info.tts_available ? '' : ' disabled title="总后台未安装 edge-tts"') + '>' + icon('chip', 14) + '合成</button> ' +
            '<button class="btn sm flat" data-pick="' + k + '">' + icon('layers', 14) + '选择</button>' +
            (own ? ' <button class="btn sm flat" data-unset="' + k + '" aria-label="恢复继承">' + icon('reset', 14) + '</button>' : '') + '</td></tr>';
        }).join('');
        var voices = Object.keys(info.voices).map(function (v) {
          var p = info.voices[v].split(' · ');
          return '<button class="tree' + (st.voice === v ? ' on' : '') + '" data-voice="' + v + '"><span class="grow">' + esc(p[0]) + '</span><span class="sub">' + esc(p[1] || '') + '</span></button>';
        }).join('');
        var lib = info.assets.length ? info.assets.map(function (a) {
          return '<div class="row">' + srcTag(a) + '<span class="grow" style="font-weight:600">' + esc(a.name) + '</span><span class="mut" style="font-size:12px">' + esc(a.created_by) + '</span>' +
            '<button class="btn sm flat" data-play="' + a.id + '" aria-label="试听">' + icon('play', 14) + '</button>' +
            '<button class="btn sm flat" data-del="' + a.id + '" aria-label="删除">' + icon('trash', 14) + '</button></div>';
        }).join('') : '<div class="empty">暂无素材</div>';

        main.innerHTML =
          '<section class="panel stats" aria-label="语气策略">' +
          '<div class="stat"><span class="tag t-low" style="height:28px">低危</span><div><div style="font-weight:600">静默</div><div class="mut">仅终端屏幕提示</div></div></div>' +
          '<div class="stat"><span class="tag t-mid" style="height:28px">中危 · 提醒 / 警告</span><div><div style="font-weight:600">温和提醒</div><div class="mut">按间隔重复</div></div></div>' +
          '<div class="stat" style="background:var(--high-bg)"><span class="tag t-high" style="height:28px">高危 · 紧急</span><div><div style="font-weight:600">严厉干预</div><div style="color:var(--high-deep)">立即播放 · 蜂鸣器联动</div></div></div></section>' +
          '<div class="cols"><section class="panel" aria-label="播报文案" style="flex:3 1 560px"><div class="ph">' + icon('speaker') + '播报文案<span class="sp"></span>' +
          '<label class="sr" for="vArea">区域</label><select class="fld" id="vArea" style="width:auto;min-height:28px;color:var(--ink)">' +
          opts.map(function (o) { return '<option value="' + o.id + '"' + (o.id === st.area ? ' selected' : '') + '>' + esc(o.label) + '</option>'; }).join('') + '</select>' +
          '<span class="seg"><button class="btn' + (tone === 'gentle' ? ' on' : '') + '" data-tone="gentle">温和提醒</button><button class="btn' + (tone === 'stern' ? ' on' : '') + '" data-tone="stern">严厉干预</button></span></div>' +
          '<div class="tbwrap"><table class="tb" style="min-width:600px"><thead><tr><th>事件</th><th>文案</th><th>音源</th><th><span class="sr">操作</span></th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
          '<div class="row foot mut">' + icon('send', 16) + '保存即生效，终端下次上报时自动同步' + (info.tts_available ? '' : ' · 总后台未安装 edge-tts，仅可上传音频') + '</div></section>' +
          '<div style="flex:2 1 340px;display:flex;flex-direction:column;gap:16px;min-width:0">' +
          '<section class="panel" aria-label="合成音色"><div class="ph">' + icon('chip') + '合成音色<span class="sp"></span><small>edge-tts</small></div>' + voices +
          '<div class="pad"><label class="lbl">语速（%）<input class="fld num" type="number" id="vRate" step="10" min="-50" max="50" value="' + st.rate + '"></label></div></section>' +
          '<section class="panel" aria-label="教师录音"><div class="ph dk">' + icon('mic') + '教师录音</div><form class="pad" id="vUp" style="display:flex;flex-direction:column;gap:10px">' +
          '<div class="formgrid"><label class="lbl">事件<select class="fld" id="uKind">' + Object.keys(kinds).map(function (k) { return '<option value="' + k + '">' + esc(kinds[k].name) + '</option>'; }).join('') + '</select></label>' +
          '<label class="lbl">语气<select class="fld" id="uTone"><option value="gentle">温和提醒</option><option value="stern"' + (tone === 'stern' ? ' selected' : '') + '>严厉干预</option></select></label></div>' +
          '<label class="lbl">名称<input class="fld" id="uName" maxlength="40" placeholder="如：张老师 · 未戴护目镜"></label>' +
          '<div class="lbl">音频文件<div style="display:flex;gap:8px;align-items:center"><label class="btn" style="flex:0 0 auto">' + icon('upload', 16) + '选择文件' +
          '<input class="sr" id="uFile" type="file" accept="audio/mpeg,audio/wav,audio/ogg,audio/flac,.mp3,.wav,.ogg,.flac"></label><span class="mut grow" id="uFileName" style="font-weight:normal">未选择</span></div></div>' +
          '<label class="chk"><input type="checkbox" id="uConsent">已取得录音者本人授权</label>' +
          '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button class="btn pri" type="submit" id="uGo" disabled>' + icon('upload') + '上传并应用</button>' +
          '<span class="mut">MP3 / WAV / OGG / FLAC · ≤ 5 MB</span></div></form></section>' +
          '<section class="panel" aria-label="素材库"><div class="ph">' + icon('doc') + '素材库<span class="sp"></span><small class="num">' + info.assets.length + '</small></div>' +
          '<div style="max-height:320px;overflow-y:auto">' + lib + '</div></section></div></div>';

        LG.$('#vArea').onchange = function (e) { st.area = Number(e.target.value); reload(); };
        LG.$('#vRate').onchange = function (e) { st.rate = Math.max(-50, Math.min(50, Number(e.target.value) || 0)); };
        LG.$('#uConsent').onchange = function (e) { LG.$('#uGo').disabled = !e.target.checked; };
        LG.$('#uFile').onchange = function (e) {
          var f = e.target.files[0];
          LG.$('#uFileName').textContent = f ? f.name + ' · ' + (f.size / 1024 / 1024).toFixed(2) + ' MB' : '未选择';
          if (f && !LG.$('#uName').value) LG.$('#uName').value = f.name.replace(/\.[^.]+$/, '');
        };
        LG.$('#vUp').onsubmit = function (e) {
          e.preventDefault();
          var f = LG.$('#uFile').files[0];
          if (!f) return LG.toast('请选择音频文件', true);
          if (f.size > 5 * 1024 * 1024) return LG.toast('音频超过 5 MB', true);
          var name = LG.$('#uName').value.trim() || f.name.replace(/\.[^.]+$/, ''), kind = LG.$('#uKind').value, t = LG.$('#uTone').value;
          f.arrayBuffer().then(function (buf) {
            return LG.api('POST', '/api/voice/upload?consent=1&name=' + encodeURIComponent(name), undefined, buf);
          }).then(function (a) { return setMap(kind, t, a.id); }).then(function () { LG.toast('已上传并应用'); }).catch(LG.fail);
        };
      }

      function setMap(kind, tone, assetId) {
        return LG.api('PUT', '/api/voice/map/' + st.area, { kind: kind, tone: tone, asset_id: assetId }).then(function (m) { map = m; return refreshInfo(); });
      }
      function refreshInfo() { return LG.api('GET', '/api/voice').then(function (i) { info = i; paint(); }); }
      function reload() {
        return Promise.all([LG.api('GET', '/api/voice'), LG.api('GET', '/api/voice/map/' + st.area)]).then(function (r) { info = r[0]; map = r[1]; paint(); }).catch(LG.fail);
      }

      function synth(kind) {
        var k = info.kinds[kind], text = k[st.tone];
        LG.dialog('合成语音 · ' + k.name, '<label class="lbl">文案（≤ 120 字）<textarea class="fld" id="sText" maxlength="120" rows="3">' + esc(text) + '</textarea></label>' +
          '<div class="mut">音色 ' + esc(info.voices[st.voice]) + ' · 语速 ' + (st.rate >= 0 ? '+' : '') + st.rate + '% · ' + (st.tone === 'gentle' ? '温和提醒' : '严厉干预') + '</div>' +
          '<div class="row" style="padding:0;border:0"><button class="btn pri" data-go>' + icon('chip', 18) + '合成并应用</button><button class="btn" data-close>取消</button></div>', function (d) {
          LG.$('[data-go]', d).onclick = function () {
            var b = this; b.disabled = true; b.textContent = '合成中…';
            LG.api('POST', '/api/voice/tts', { text: LG.$('#sText', d).value, voice: st.voice, rate: (st.rate >= 0 ? '+' : '') + st.rate + '%',
              name: k.name + ' · ' + (st.tone === 'gentle' ? '温和' : '严厉') + ' · ' + info.voices[st.voice].split(' · ')[0] })
              .then(function (a) { LG.closeDialog(); play(a.id); return setMap(kind, st.tone, a.id); })
              .then(function () { LG.toast('已合成并应用'); })
              .catch(function (e) { b.disabled = false; b.textContent = '合成并应用'; LG.fail(e); });
          };
        });
      }
      function pick(kind) {
        if (!info.assets.length) return LG.toast('素材库为空，请先合成或上传', true);
        LG.dialog('选择素材 · ' + info.kinds[kind].name, '<div style="max-height:50vh;overflow-y:auto;border:2px solid var(--ink)">' + info.assets.map(function (a) {
          return '<div class="row">' + srcTag(a) + '<span class="grow">' + esc(a.name) + '</span><button class="btn sm flat" data-play="' + a.id + '" aria-label="试听">' + icon('play', 14) + '</button>' +
            '<button class="btn sm pri" data-use="' + a.id + '">使用</button></div>';
        }).join('') + '</div>', function (d) {
          d.onclick = function (e) {
            var t = e.target.closest('[data-play], [data-use]'); if (!t) return;
            if (t.dataset.play) play(Number(t.dataset.play));
            else { LG.closeDialog(); setMap(kind, st.tone, Number(t.dataset.use)).then(function () { LG.toast('已应用'); }).catch(LG.fail); }
          };
        });
      }

      main.onclick = function (e) {
        var t = e.target.closest('[data-play], [data-synth], [data-pick], [data-unset], [data-voice], [data-tone], [data-del]');
        if (!t) return;
        var d = t.dataset;
        if (d.play) play(Number(d.play));
        else if (d.synth) synth(d.synth);
        else if (d.pick) pick(d.pick);
        else if (d.unset) setMap(d.unset, st.tone, null).catch(LG.fail);
        else if (d.voice) { st.voice = d.voice; paint(); }
        else if (d.tone) { st.tone = d.tone; paint(); }
        else if (d.del) {
          var a = assetById(Number(d.del));
          LG.confirm('删除素材', '<div>' + esc(a.name) + '</div><div class="mut">引用该素材的事件将恢复为继承或内置提示音。</div>', '删除', true).then(function (ok) {
            if (ok) LG.api('DELETE', '/api/voice/' + a.id).then(reload).catch(LG.fail);
          });
        }
      };
      reload();
    }
  });
})();
