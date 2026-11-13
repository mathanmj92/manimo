/* Storyboard: one card per scene. Reorder (drag or the arrows), duplicate, delete, rename, add from a template, render one scene or all.
   The cards are a view of the code: every change is made to the text in the editor (and can be undone with Ctrl+Z). */
(function () {
'use strict';
var M = window.MANIMO, host = document.getElementById('board');
if (!M || !host) return;
var $ = M.$, esc = M.esc;

var st = { on: false, scenes: [], error: '', busy: false, run: null, done: {}, thumbs: {}, drag: null, seq: 0 };
var timer = null, skip = 0;

function api(body) { return M.api('/api/scenes', Object.assign({ code: M.getCode() }, body)); }

/* ---------- loading ---------- */
function refresh() {
  if (!st.on) return;
  var mine = ++st.seq;
  api({ op: 'info' }).then(function (r) { if (mine !== st.seq) return; st.scenes = r.scenes; st.error = ''; paint(); })
    .catch(function (e) { if (mine !== st.seq) return; st.scenes = []; st.error = e.message; paint(); });
}
function changed() {
  if (!st.on) return;
  if (skip) { skip--; return; }               // the change was made by the board itself and has already been painted
  clearTimeout(timer); timer = setTimeout(refresh, 350);
}

/* ---------- status of a scene ---------- */
function problemsIn(sc, next) {
  var list = (window.MGXCheck && window.MGXCheck.issues && window.MGXCheck.issues()) || [];
  return list.filter(function (i) { return i.line && i.line >= sc.line && i.line < (next ? next.line : 1e9); }).length;
}
function status(sc, i) {
  var run = st.run, item = run && run.items && run.items.filter(function (x) { return x.scene === sc.name; })[0];
  if (run && run.state === 'running' && item) {
    if (item.state === 'running') return { k: 'run', t: 'Rendering ' + Math.floor(item.percent || 0) + '%' };
    if (item.state === 'queued') return { k: 'queue', t: 'Waiting' };
  }
  if (run && (run.failed || []).some(function (f) { return f.scene === sc.name; })) return { k: 'bad', t: 'Failed' };
  var n = problemsIn(sc, st.scenes[i + 1]);
  if (n) return { k: 'warn', t: n + (n === 1 ? ' problem' : ' problems') };
  var d = st.done[sc.name];
  if (!d) return { k: 'none', t: 'Not rendered' };
  return d.hash === sc.hash ? { k: 'ok', t: 'Rendered' } : { k: 'stale', t: 'Changed since render' };
}

/* ---------- painting ---------- */
function secs(sc) {
  var d = st.done[sc.name];
  if (d && d.seconds) return d.seconds.toFixed(0) + ' s';
  return sc.est_seconds ? 'about ' + Math.max(1, Math.round(sc.est_seconds)) + ' s' : '';
}
function card(sc, i) {
  var s = status(sc, i), d = st.done[sc.name], busy = st.run && st.run.state === 'running';
  var thumb = d && d.thumb ? '<img src="' + esc(d.thumb) + '" alt="First frame of ' + esc(sc.name) + '" loading="lazy">' : '<span class="bd-ph" aria-hidden="true">' + esc(sc.name.charAt(0).toUpperCase()) + '</span>';
  var meta = [secs(sc), sc.words ? sc.words + ' spoken words' : 'no narration', sc.plays + (sc.plays === 1 ? ' animation' : ' animations')].filter(Boolean).join(' · ');
  var selected = M.selectedScene() === sc.name;
  return '<li class="bd-card' + (selected ? ' sel' : '') + '" draggable="true" data-name="' + esc(sc.name) + '" aria-label="Scene ' + (i + 1) + ': ' + esc(sc.name) + '">' +
    '<div class="bd-thumb">' + thumb + '<span class="bd-n">' + (i + 1) + '</span>' + (d && d.path ? '<button class="bd-play" data-act="play" aria-label="Play ' + esc(sc.name) + ' in the preview"><svg class="ic"><use href="#i-play"/></svg></button>' : '') + '</div>' +
    '<div class="bd-body"><div class="bd-name"><button class="bd-title" data-act="rename" title="Rename this scene">' + esc(sc.name) + '</button><span class="bd-st ' + s.k + '"><i></i>' + esc(s.t) + '</span></div>' +
    '<p class="bd-meta">' + esc(meta) + '</p>' +
    '<div class="bd-acts"><button class="btn sm primary" data-act="render"' + (busy ? ' disabled' : '') + '><svg class="ic sm"><use href="#i-play"/></svg>Render</button>' +
    '<button class="icon-btn sm" data-act="code" aria-label="Show the code" title="Show the code"><svg class="ic sm"><use href="#i-file"/></svg></button>' +
    '<button class="icon-btn sm" data-act="up" aria-label="Move earlier"' + (i === 0 ? ' disabled' : '') + ' title="Move earlier"><span class="bd-arrow" aria-hidden="true">&larr;</span></button>' +
    '<button class="icon-btn sm" data-act="down" aria-label="Move later"' + (i === st.scenes.length - 1 ? ' disabled' : '') + ' title="Move later"><span class="bd-arrow" aria-hidden="true">&rarr;</span></button>' +
    '<button class="icon-btn sm" data-act="dup" aria-label="Duplicate" title="Duplicate"><svg class="ic sm"><use href="#i-copy"/></svg></button>' +
    '<button class="icon-btn sm" data-act="del" aria-label="Delete" title="Delete"><svg class="ic sm"><use href="#i-trash"/></svg></button></div>' +
    '<select class="input sm bd-ask" data-ask aria-label="Ask the assistant about ' + esc(sc.name) + '"><option value="">Ask the assistant…</option><option value="explain">Explain this scene</option><option value="easier">Make it easier</option><option value="harder">Make it harder</option><option value="shorter">Make it shorter</option><option value="takes">Compare two takes…</option></select></div></li>';
}
var templates = null;
function addSelect() {
  var o = '<option value="">Add a scene…</option>' + (templates || []).map(function (t) { return '<option value="' + esc(t.id) + '">' + esc(t.label) + ' (' + esc(t.about) + ')</option>'; }).join('');
  return '<label class="bd-add"><span class="sr-only">Add a scene</span><select id="bdAdd" class="input sm">' + o + '</select></label>';
}
function paint() {
  var busy = st.run && st.run.state === 'running', n = st.scenes.length, head;
  head = '<div class="bd-bar">' + addSelect() + '<span class="spacer"></span><button class="btn sm" data-act="kit" title="A PDF handout, a GIF, or a folder ready to share">Export lesson\u2026</button>' +
    (n > 1 ? '<span class="help">' + n + ' scenes, about ' + Math.max(1, Math.round(st.scenes.reduce(function (a, s) { var d = st.done[s.name]; return a + ((d && d.seconds) || s.est_seconds || 0); }, 0))) + ' s</span>' +
      '<button class="btn sm" data-act="all"' + (busy ? ' disabled' : '') + '><svg class="ic sm"><use href="#i-play"/></svg>Render all</button>' : '') + '</div>';
  var body;
  if (st.error) body = '<p class="bd-empty" role="alert">' + esc(st.error) + '</p>';
  else if (!n) body = '<div class="bd-empty"><b>No scenes yet</b><p>A scene is one part of your video. Add one from the list above, or paste code and it will appear here.</p></div>';
  else body = '<ol class="bd-grid" id="bdGrid">' + st.scenes.map(card).join('') + '</ol><p class="help bd-hint">Drag a card, or use the arrows, to change the order. The video plays the scenes in this order when you render all.</p>';
  host.innerHTML = head + body;
  var sel = $('bdAdd'); if (sel && !(templates && templates.length)) sel.disabled = true;
}

/* ---------- edits (all go through the editor, so Ctrl+Z undoes them) ---------- */
function edit(body, okMsg) {
  if (st.busy) return Promise.resolve();
  st.busy = true;
  return api(body).then(function (r) {
    skip = 1; M.applyCode(r.code); st.scenes = r.scenes; st.error = '';
    if (okMsg) M.toast(okMsg(r));
    paint();
    return r;
  }).catch(function (e) { M.toast(e.message); }).then(function (r) { st.busy = false; return r; });
}
function move(name, to) {
  var order = st.scenes.map(function (s) { return s.name; }), from = order.indexOf(name);
  if (from < 0 || to < 0 || to >= order.length || to === from) return;
  order.splice(to, 0, order.splice(from, 1)[0]);
  edit({ op: 'reorder', order: order }, function () { return 'Moved ' + name + ' to position ' + (to + 1) + '. Undo with Ctrl+Z.'; });
}
function beginRename(li, name) {
  var b = li.querySelector('.bd-title'); if (!b) return;
  var inp = document.createElement('input');
  inp.className = 'input sm bd-rename'; inp.value = name; inp.setAttribute('aria-label', 'New name for ' + name); inp.spellcheck = false;
  b.replaceWith(inp); inp.focus(); inp.select();
  var done = false;
  function finish(save) {
    if (done) return; done = true;
    var v = inp.value.trim();
    if (save && v && v !== name) edit({ op: 'rename', name: name, new_name: v }, function (r) { return 'Renamed to ' + r.name + '.'; }); else paint();
  }
  inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); finish(true); } else if (e.key === 'Escape') { e.preventDefault(); finish(false); } });
  inp.addEventListener('blur', function () { finish(true); });
}

host.addEventListener('click', function (e) {
  var b = e.target.closest('[data-act]'); if (!b) return;
  var li = b.closest('.bd-card'), name = li && li.dataset.name, act = b.dataset.act;
  if (act === 'all') { M.renderScene('__all__'); return; }
  if (act === 'kit') { if (window.MGXKit) window.MGXKit.open(); return; }
  if (!name) return;
  if (act === 'render') M.renderScene(name);
  else if (act === 'code') { var sc = st.scenes.filter(function (s) { return s.name === name; })[0]; show(false); if (sc) M.jumpToLine(sc.line); }
  else if (act === 'up' || act === 'down') move(name, st.scenes.map(function (s) { return s.name; }).indexOf(name) + (act === 'up' ? -1 : 1));
  else if (act === 'dup') edit({ op: 'duplicate', name: name }, function (r) { return 'Copied ' + name + ' as ' + r.name + '.'; });
  else if (act === 'del') { if (window.confirm('Delete the scene ' + name + '? You can undo this with Ctrl+Z in the code.')) edit({ op: 'delete', name: name }, function () { return 'Deleted ' + name + '. Undo with Ctrl+Z.'; }); }
  else if (act === 'rename') beginRename(li, name);
  else if (act === 'play') { var d = st.done[name]; if (d && d.out) { M.setPreview([d.out], 0); M.rightTab('preview'); } }
});
host.addEventListener('change', function (e) {
  if (e.target.matches('[data-ask]')) {
    var kind = e.target.value, li = e.target.closest('.bd-card'); e.target.value = '';
    var sc = li && st.scenes.filter(function (s) { return s.name === li.dataset.name; })[0];
    if (kind && sc && window.MGXTakes) window.MGXTakes.ask(kind, sc);
    return;
  }
  if (e.target.id !== 'bdAdd' || !e.target.value) return;
  var kind = e.target.value; e.target.value = '';
  edit({ op: 'add', kind: kind }, function (r) { return 'Added ' + r.name + ' at the end.'; });
});
/* a plain click on a card marks it as the scene "Start Rendering" will render */
host.addEventListener('dblclick', function (e) { var li = e.target.closest('.bd-card'); if (li && !e.target.closest('button, input')) M.renderScene(li.dataset.name); });

/* drag and drop */
host.addEventListener('dragstart', function (e) {
  var li = e.target.closest && e.target.closest('.bd-card'); if (!li) return;
  st.drag = li.dataset.name; li.classList.add('drag');
  e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', st.drag); } catch (x) {}
});
host.addEventListener('dragend', function () { st.drag = null; host.querySelectorAll('.drag, .over').forEach(function (n) { n.classList.remove('drag', 'over'); }); });
host.addEventListener('dragover', function (e) {
  if (!st.drag) return; var li = e.target.closest('.bd-card'); if (!li) return;
  e.preventDefault(); host.querySelectorAll('.over').forEach(function (n) { n.classList.remove('over'); }); li.classList.add('over');
});
host.addEventListener('drop', function (e) {
  if (!st.drag) return; var li = e.target.closest('.bd-card'); if (!li) return;
  e.preventDefault();
  var names = st.scenes.map(function (s) { return s.name; });
  var name = st.drag; st.drag = null; move(name, names.indexOf(li.dataset.name));
});

/* ---------- rendering progress and finished scenes ---------- */
function progress(run) {
  st.run = run;
  if (run.state === 'running' && st.snapRun !== run) {      // remember what each scene looked like when this render began
    st.snapRun = run;
    api({ op: 'info' }).then(function (r) { st.startHash = {}; r.scenes.forEach(function (s) { st.startHash[s.name] = s.hash; }); }).catch(function () {});
  }
  if (st.on) paint();
}
function rendered(run) {
  st.run = run;
  (run.items || []).forEach(function (it) {
    if (it.state !== 'done') return;
    var out = (run.outputs || []).filter(function (o) { return o.kind !== 'slides' && o.name === it.scene + '.mp4'; })[0];
    if (!out) return;
    var rec = { path: out.path, out: out, seconds: it.seconds || 0, hash: (st.startHash || {})[it.scene] || '' };
    st.done[it.scene] = rec;
    if (out.path) M.api('/api/video-meta', { path: out.path }).then(function (m) { rec.thumb = m.thumb || ''; if (m.seconds) rec.seconds = m.seconds; if (st.on) paint(); }).catch(function () {});
  });
  if (st.on) { refresh(); }
}
/* ---------- showing the board in place of the code ---------- */
function show(on) {
  st.on = !!on;
  host.hidden = !on;
  $('cmHost').style.display = on ? 'none' : '';
  if (on) $('empty').hidden = true; else $('empty').hidden = M.getCode().length > 0;
  $('vwCode').setAttribute('aria-pressed', String(!on)); $('vwBoard').setAttribute('aria-pressed', String(on));
  try { localStorage.setItem('mgx-board', on ? '1' : ''); } catch (e) {}
  if (on) {
    if (!templates) fetch('/api/scenes/templates').then(function (r) { return r.json(); }).then(function (r) { templates = r.templates; paint(); }).catch(function () { templates = []; });
    refresh();
  }
}
$('vwCode').addEventListener('click', function () { show(false); });
$('vwBoard').addEventListener('click', function () { show(true); });

window.MGXBoard = { changed: changed, progress: progress, rendered: rendered, show: show, state: st };
try { if (localStorage.getItem('mgx-board') === '1') setTimeout(function () { show(true); }, 300); } catch (e) {}
})();
