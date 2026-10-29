/* Manimo projects and the video editor. Uses the small bridge app.js exposes as window.MANIMO. */
(function () {
'use strict';
var M = window.MANIMO; if (!M) return;
var $ = M.$, api = M.api, esc = M.esc, toast = M.toast, fmt = M.fmt;

var PR = { open: false, name: '', path: '', scenes: [], timeline: { clips: [], audio: [], size: 'auto', fps: 30 }, media: {}, recent: [], files: [], defaultParent: '' };
var curFile = '', loading = false, saveTimer = null;
var SHAPE_RATIO = { '16:9': [16, 9], '9:16': [9, 16], '1:1': [1, 1], '4:3': [4, 3], '3:4': [3, 4] };
function uid() { return 'i' + Math.random().toString(36).slice(2, 9); }
function baseName(p) { return String(p).split(/[\\/]/).filter(Boolean).pop() || p; }
function clean(tl) {
  tl = tl || {}; tl.clips = (tl.clips || []).map(function (c) { c.id = c.id || uid(); return c; }); tl.audio = (tl.audio || []).map(function (a) { a.id = a.id || uid(); a.kind = a.kind || 'voice'; return a; }); tl.cams = (tl.cams || []).map(function (k) { k.id = k.id || uid(); return k; });
  tl.size = SHAPE_RATIO[tl.size] ? tl.size : 'auto'; tl.fps = tl.fps === 60 ? 60 : 30; return tl;
}

/* ---------------------------------------------------------------- state */
function apply(st) {
  PR.recent = st.recent || []; PR.defaultParent = st.default_parent || PR.defaultParent;
  if (!st.open) { PR.open = false; PR.name = ''; PR.path = ''; PR.scenes = []; PR.files = []; return false; }
  var changed = st.path !== PR.path || !PR.open;
  if (changed) PR.quick = false;
  PR.open = true; PR.name = st.name; PR.path = st.path; PR.scenes = st.scenes || []; PR.media = st.media || {}; PR.files = st.files || []; PR.timeline = clean(st.timeline);
  return changed;
}
function refresh() {
  if (!PR.open) return Promise.resolve();
  return api('/api/project/state', { settings: M.settings() }).then(function (st) { apply(st); paintPane(); if (!$('vedit').hidden) veRefreshMedia(); }).catch(function () {});
}
function entered(st) {
  var changed = apply(st);
  if (changed) { M.applySettings(st.settings); curFile = ''; loadFirstScene(); }
  refresh(); M.rightTab('project'); M.paintFile();
}
function loadFirstScene() {
  var want = M.store('mgx-proj-file:' + PR.path), file = PR.files.indexOf(want) >= 0 ? want : PR.files[0];
  if (file) openScene(file); else { loading = true; M.setCode('', ''); loading = false; }
}
function openScene(file) {
  return flush().then(function () { return api('/api/project/scene-read', { file: file }); }).then(function (r) {
    loading = true; M.setCode(r.code, r.file); loading = false; curFile = r.file; M.markClean(); M.store('mgx-proj-file:' + PR.path, r.file); paintPane();
  }).catch(function (e) { toast(e.message); });
}
function flush() {
  clearTimeout(saveTimer); saveTimer = null;
  if (!PR.open || !curFile || loading) return Promise.resolve();
  return api('/api/project/scene-write', { file: curFile, code: M.getCode() }).then(function () { M.markClean(); }).catch(function (e) { toast('Could not save: ' + e.message); });
}
function changed() {
  if (!PR.open || !curFile || loading) return;
  clearTimeout(saveTimer); saveTimer = setTimeout(function () { flush().then(refresh); }, 900);
}

/* ---------------------------------------------------------------- New / open / close */
var composeFlow = false;
function newDlg(forCompose) {
  composeFlow = forCompose === true; var rv = composeFlow ? M.recentVideos() : [];
  $('projRecentRow').hidden = !rv.length; $('projRecentLbl').textContent = 'Add my ' + rv.length + ' recent video' + (rv.length === 1 ? '' : 's') + ' to it';
  $('projNewTitle').textContent = composeFlow ? 'Start a project to compose in' : 'New project';
  $('projName').value = ''; $('projNewMsg').textContent = ''; $('projParent').textContent = PR.defaultParent || ''; $('projParent').title = PR.defaultParent || '';
  $('projNewDlg').showModal(); setTimeout(function () { $('projName').focus(); }, 30);
}
$('projPick').addEventListener('click', function () {
  M.pickFolder(PR.defaultParent, 'Choose where to create the project').then(function (r) { if (r.path) { PR.defaultParent = r.path; $('projParent').textContent = r.path; $('projParent').title = r.path; } });
});
function createProject() {
  var name = $('projName').value.trim() || 'My lesson';
  $('projNewMsg').textContent = 'Creating…';
  var wantRecent = composeFlow && !$('projRecentRow').hidden && $('projRecent').checked, flow = composeFlow;
  flush().then(function () { return api('/api/project/new', { name: name, parent: PR.defaultParent }); }).then(function (st) {
    $('projNewDlg').close(); entered(st); toast('Created ' + st.name);
    if (!flow) return;
    var list = wantRecent ? M.recentVideos().slice().reverse() : [];
    return list.reduce(function (chain, v) { return chain.then(function () { return api('/api/project/import', { path: v.path }).then(function (r) { pendingImports.push(r.src); }).catch(function () {}); }); }, Promise.resolve())
      .then(function () { return refresh(); }).then(function () { openEditor(); });
  })
    .catch(function (e) { $('projNewMsg').textContent = e.message; });
}
$('projCreate').addEventListener('click', createProject);
$('projName').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); createProject(); } });
function openPath(p) {
  flush().then(function () { return api('/api/project/open', { path: p }); }).then(function (st) { entered(st); toast('Opened ' + st.name); }).catch(function (e) { toast(e.message); });
}
function openDlg() {
  toast('Choose the project folder (the one that holds project.mo)…');
  M.pickFolder(PR.defaultParent, 'Open a Manimo project: pick its folder').then(function (r) { if (r.path) openPath(r.path); });
}
function closeProject() {
  flush().then(function () { return api('/api/project/close', {}); }).then(function (st) { apply(st); curFile = ''; M.paintFile(); paintPane(); toast('Project closed'); }).catch(function (e) { toast(e.message); });
}

/* ---------------------------------------------------------------- the Project tab */
var STATUS = { ok: ['Up to date', 'ok'], stale: ['Out of date', 'stale'], none: ['Not rendered', 'none'] };
function paintPane() {
  var el = $('projectPane'); if (!el || el.hidden && !PR.open && !el.dataset.painted) { /* paint lazily */ }
  if (!el) return; el.dataset.painted = '1';
  if (!PR.open) {
    el.innerHTML = '<div class="proj-empty"><svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="var(--accent)"/><path d="M5.5 20.5c3.2 0 3.2-9 6.5-9s3.2 9 6.5 9 3.2-9 6.5-9" fill="none" stroke="var(--on-accent)" stroke-width="2.4" stroke-linecap="round"/></svg>' +
      '<h3>Keep a whole lesson in one place</h3><p>A project holds every scene, video and recording together. Cut them into one finished video with the editor.</p>' +
      '<div class="proj-btns"><button class="btn primary" data-act="new">New project</button><button class="btn" data-act="open">Open project</button></div>' +
      (PR.recent.length ? '<h4 class="proj-sub">Recent</h4><ul class="proj-recent">' + PR.recent.slice(0, 6).map(function (p) { return '<li><button class="linkbtn" data-act="recent" data-path="' + esc(p) + '" title="' + esc(p) + '">' + esc(baseName(p)) + '</button></li>'; }).join('') + '</ul>' : '') + '</div>';
    return;
  }
  var stale = PR.scenes.filter(function (s) { return s.scene && s.status !== 'ok'; }).length, rendered = PR.scenes.filter(function (s) { return s.render; }).length;
  function ib(act, sym, tip, extra) { return '<button class="tb-icon sm tip' + (extra && extra.right ? ' tip-right' : '') + '" data-act="' + act + '"' + (extra && extra.i != null ? ' data-i="' + extra.i + '"' : '') + (extra && extra.file ? ' data-file="' + esc(extra.file) + '"' : '') + ' data-tip="' + esc(tip) + '" aria-label="' + esc(tip) + '"' + (extra && extra.off ? ' disabled' : '') + '><svg class="ic"><use href="#' + sym + '"/></svg>' + (extra && extra.badge ? '<i class="badge">' + extra.badge + '</i>' : '') + '</button>'; }
  el.innerHTML = '<div class="proj-head"><div class="proj-title"><b>' + esc(PR.name) + '</b><span class="proj-path" title="' + esc(PR.path) + '">' + esc(PR.path) + '</span></div></div>' +
    '<div class="proj-actions">' + ib('newscene', 'i-plus', 'New scene') +
    ib('renderStale', 'i-refresh', stale ? 'Render what changed (' + stale + ')' : 'Everything is up to date', { off: !stale, badge: stale || 0 }) +
    ib('folder', 'i-folder', 'Open the project folder') + ib('close', 'i-x', 'Close the project', { right: true }) + '</div>' +
    '<ul class="proj-list">' + PR.scenes.map(function (s, i) {
      var st = STATUS[s.status] || STATUS.none, cur = s.file === curFile;
      return '<li class="proj-row' + (cur ? ' cur' : '') + '"><button class="proj-main" data-act="openScene" data-file="' + esc(s.file) + '" title="Open ' + esc(s.file) + ' in the editor">' +
        '<i class="dot ' + st[1] + '"></i><span class="pn"><b>' + esc(s.scene || s.file) + '</b><small>' + esc(s.file) + '</small></span>' +
        '<span class="ps">' + (s.scene ? st[0] + (s.seconds ? ' \u00b7 ' + fmt(s.seconds) : '') : 'No scene class') + '</span></button>' +
        '<span class="proj-row-btns">' + (s.render ? ib('addClip', 'i-plus', 'Add this video to the Compose timeline', { i: i, right: true }) : '') +
        ib('more', 'i-more', 'Rename or delete ' + s.file, { file: s.file, right: true }) + '</span></li>';
    }).join('') + '</ul>' +
    '<p class="help proj-foot">Press <b>Compose</b> in the top bar to join your rendered scenes into one video. Your code saves here as you type.</p>';
}function sceneRenderQueue(items) {
  var q = items.slice(), total = q.length;
  function next() {
    if (!q.length) { toast('Rendered ' + total + ' scene' + (total === 1 ? '' : 's')); refresh(); return; }
    var it = q.shift();
    openScene(it.file).then(function () {
      M.selectScene(it.scene); M.startRender('render');
      var t = setInterval(function () { if (!M.isRendering()) { clearInterval(t); setTimeout(next, 400); } }, 700);
    });
  }
  next();
}
$('projectPane').addEventListener('click', function (e) {
  var b = e.target.closest('[data-act]'); if (!b) return; var a = b.dataset.act;
  if (a === 'new') newDlg(); else if (a === 'open') openDlg(); else if (a === 'recent') openPath(b.dataset.path);
  else if (a === 'close') closeProject();
  else if (a === 'folder') M.exportsFolderOpen(PR.path);
  else if (a === 'openScene') openScene(b.dataset.file);
  else if (a === 'edit') openEditor();
  else if (a === 'renderStale') {
    if (M.isRendering()) { toast('A render is already running'); return; }
    sceneRenderQueue(PR.scenes.filter(function (s) { return s.scene && s.status !== 'ok'; }));
  } else if (a === 'newscene') {
    var n = window.prompt('Name the new scene file (for example "limits"):', ''); if (!n) return;
    api('/api/project/scene-new', { name: n }).then(function (r) { return refresh().then(function () { return openScene(r.file); }); }).catch(function (er) { toast(er.message); });
  } else if (a === 'addClip') { var s = PR.scenes[parseInt(b.dataset.i, 10)]; if (s && s.render) { addClip(s.render, s.scene); toast('Added ' + (s.scene || s.file) + ' to the timeline'); } }
  else if (a === 'more') {
    var file = b.dataset.file, pick = window.prompt('Type "rename" to rename ' + file + ', or "delete" to remove it (a copy is kept in the project\'s .trash folder):', '');
    if (pick === 'rename') {
      var nn = window.prompt('New name for ' + file + ':', file.replace(/\.py$/, '')); if (!nn) return;
      flush().then(function () { return api('/api/project/scene-rename', { file: file, name: nn }); }).then(function (r) { if (curFile === file) curFile = r.file; return refresh(); }).catch(function (er) { toast(er.message); });
    } else if (pick === 'delete') {
      if (!window.confirm('Remove ' + file + ' from the project? A copy stays in the .trash folder.')) return;
      api('/api/project/scene-delete', { file: file }).then(function () { if (curFile === file) { curFile = ''; } return refresh().then(function () { if (!curFile) loadFirstScene(); }); }).catch(function (er) { toast(er.message); });
    }
  }
});

/* ---------------------------------------------------------------- Compose: the video editor */
var INFO = {}, PPS = 48, LBL = 92, sel = null, playing = false, tNow = 0, total = 0, tick = null, curIdx = -1, auds = {}, saveTl = null, rec = null, exportPoll = null;
var undoS = [], redoS = [], lastSnap = '', pendingImports = [];
var V = $('veVideo'), CAM = $('veCam'), FR = $('veFrame'), SCR = $('veScreen');
function fitFrame() {            // size the picture box to the video's own shape, centred on the tile
  var cw = SCR.clientWidth - 8, ch = SCR.clientHeight - 8; if (cw <= 0 || ch <= 0) return;
  var r = SHAPE_RATIO[PR.timeline.size], vw, vh;            // the chosen export shape; "auto" is the first clip's own shape
  if (r) { vw = r[0]; vh = r[1]; } else { var c0 = PR.timeline.clips[0], i0 = c0 && INFO[c0.src]; vw = (i0 && i0.width) || V.videoWidth || 16; vh = (i0 && i0.height) || V.videoHeight || 9; }
  var s = Math.min(cw / vw, ch / vh);
  FR.style.width = Math.floor(vw * s) + 'px'; FR.style.height = Math.floor(vh * s) + 'px';
}
V.addEventListener('loadedmetadata', fitFrame); if (window.ResizeObserver) new ResizeObserver(fitFrame).observe(SCR);
function T() { return PR.timeline; }
function mediaUrl(src) { return PR.media[src] && PR.media[src].url; }
function dur(src) { return (INFO[src] && INFO[src].duration) || 0; }
function tc(t) { t = Math.max(0, t); var m = Math.floor(t / 60), s = t - m * 60; return m + ':' + (s < 10 ? '0' : '') + s.toFixed(1); }
function clipLen(c) { var d = dur(c.src), end = c.out != null ? Math.min(c.out, d || c.out) : d; return Math.max(0.1, end - c.in); }
function layout() { var t = 0; T().clips.forEach(function (c) { c._len = clipLen(c); c._at = t; t += c._len; }); total = t; return t; }
function audLen(a) { var d = Math.max(0.3, dur(a.src) - (a.in || 0)); return a.kind === 'music' && a.loop ? Math.max(d, total - a.start) : d; }
function camLen(k) { return Math.max(0.3, dur(k.src) - (k.in || 0)); }
function endAll() { var m = total; T().audio.forEach(function (a) { m = Math.max(m, a.start + audLen(a)); }); T().cams.forEach(function (k) { m = Math.max(m, k.start + camLen(k)); }); return m; }
function ensureInfo() {
  var all = T().clips.concat(T().audio, T().cams).map(function (x) { return x.src; });
  var need = all.filter(function (s, i) { return !INFO[s] && all.indexOf(s) === i && PR.media[s]; });
  return Promise.all(need.map(function (s) { return api('/api/project/media-info', { src: s }).then(function (r) { INFO[s] = r; }).catch(function () { INFO[s] = { duration: 0 }; }); }));
}
function cleanTl() {
  var tl = T();
  return { size: tl.size, fps: tl.fps,
    clips: tl.clips.map(function (c) { return { id: c.id, src: c.src, label: c.label, in: c.in, out: c.out, fade: !!c.fade }; }),
    audio: tl.audio.map(function (a) { return { id: a.id, src: a.src, label: a.label, start: a.start, volume: a.volume, in: a.in || 0, kind: a.kind || 'voice', loop: !!a.loop }; }),
    cams: tl.cams.map(function (k) { return { id: k.id, src: k.src, label: k.label, start: k.start, in: k.in || 0, corner: k.corner || 'br', size: k.size || 28, volume: k.volume == null ? 1 : k.volume }; }) };
}
function scheduleSaveTl() {
  clearTimeout(saveTl);
  saveTl = setTimeout(function () { api('/api/project/timeline', { timeline: cleanTl() }).catch(function (e) { toast('Could not save the timeline: ' + e.message); }); }, 500);
}
function commit() {   // call after every finished change: saves it and remembers it for Undo
  var s = JSON.stringify(cleanTl());
  if (s !== lastSnap) { if (lastSnap) { undoS.push(lastSnap); if (undoS.length > 80) undoS.shift(); } redoS = []; lastSnap = s; scheduleSaveTl(); }
  paintAll();
}
function restore(s) {
  var o = JSON.parse(s); T().clips = o.clips; T().audio = o.audio; T().cams = o.cams; lastSnap = s; clean(T());
  if (sel && !selItem()) sel = null; layout(); paintAll(); scheduleSaveTl(); seek(Math.min(tNow, total));
}
function undo() { if (!undoS.length) return; redoS.push(lastSnap); restore(undoS.pop()); }
function redo() { if (!redoS.length) return; undoS.push(lastSnap); restore(redoS.pop()); }
$('veUndo').addEventListener('click', undo); $('veRedo').addEventListener('click', redo);
function selItem() { if (!sel) return null; var l = sel.kind === 'c' ? T().clips : sel.kind === 'k' ? T().cams : T().audio; return l.filter(function (x) { return x.id === sel.id; })[0] || null; }
function labelFor(src, scene) { if (scene) return scene; var f = baseName(src).replace(/\.[^.]+$/, ''); return f.indexOf('__') > 0 ? f.split('__')[1] : f; }
function renderedList() { return PR.scenes.filter(function (s) { return s.render && PR.media[s.render]; }); }
function addClipRaw(src, scene) { T().clips.push({ id: uid(), src: src, label: labelFor(src, scene), in: 0, out: null, fade: false }); }
function addClip(src, scene) { addClipRaw(src, scene); ensureInfo().then(function () { layout(); commit(); if (T().clips.length === 1) seek(0); }); }
function addSound(src, start, kind, label) {
  var music = kind === 'music', a = { id: uid(), src: src, label: label || labelFor(src), start: start == null ? tNow : start, volume: music ? 0.35 : 1, in: 0, kind: music ? 'music' : 'voice', loop: music };
  T().audio.push(a); sel = { kind: 'a', id: a.id }; ensureInfo().then(function () { layout(); commit(); });
}
function addCam(src, start, label) {
  var k = { id: uid(), src: src, label: label || 'Camera', start: start == null ? tNow : start, in: 0, corner: 'br', size: 28, volume: 1 };
  T().cams.push(k); sel = { kind: 'k', id: k.id }; ensureInfo().then(function () { layout(); commit(); });
}
function updateNew() {
  var n = renderedList().filter(function (r) { return !T().clips.some(function (c) { return c.src === r.render; }); }).length, b = $('veNew');
  b.hidden = !n || !T().clips.length; b.textContent = '+ Add ' + n + ' new render' + (n === 1 ? '' : 's');
}
$('veNew').addEventListener('click', function () { renderedList().forEach(function (r) { if (!T().clips.some(function (c) { return c.src === r.render; })) addClipRaw(r.render, r.scene); }); ensureInfo().then(function () { layout(); commit(); }); });

function openEditor() {
  if (!PR.open) return;
  flush().then(refresh).then(function () {
    $('vedit').hidden = false; $('veProj').textContent = PR.name; document.body.classList.add('ve-open'); $('veExp').hidden = true;
    if (!lastSnap) lastSnap = JSON.stringify(cleanTl());
    var added = 0;
    if (!T().clips.length) { renderedList().forEach(function (r) { addClipRaw(r.render, r.scene); added++; }); }
    pendingImports.splice(0).forEach(function (s) { addClipRaw(s); added++; });
    return ensureInfo().then(function () {
      layout(); if (added) commit(); else paintAll(); seek(Math.min(tNow, total)); setTimeout(function () { $('veClose').focus(); }, 30);
      if (added) toast('Added ' + added + ' video' + (added === 1 ? '' : 's') + ' from your project');
    });
  });
}
function closeEditor() {
  pause(); stopRec(true); $('vedit').hidden = true; document.body.classList.remove('ve-open'); closeVeMenu();
  if (PR.quick && !exportPoll) api('/api/project/close', {}).then(function (st) { apply(st); PR.quick = false; paintPane(); }).catch(function () {});   // a one-video edit leaves no project open
}
function editVideo(path) {      // Edit video: open one finished video in Compose, with or without a project
  return flush().then(function () { return api('/api/project/edit-video', { path: path }); }).then(function (st) {
    apply(st); PR.quick = !!st.quick; paintPane();
    var already = T().clips.some(function (c) { return c.src === st.src; }), covered = !T().clips.length && renderedList().some(function (r) { return r.render === st.src; });
    if (!already && !covered) pendingImports.push(st.src);
    openEditor();
  }).catch(function (e) { toast(e.message); });
}
function veRefreshMedia() { ensureInfo().then(function () { layout(); paintAll(); }); }
$('veClose').addEventListener('click', closeEditor);
$('composeBtn').addEventListener('click', function () { compose(); });
function compose() { if (PR.open) { openEditor(); return; } newDlg(true); }

/* drawing */
function tick1(span) { return span <= 20 ? 1 : span <= 90 ? 5 : span <= 300 ? 15 : span <= 900 ? 30 : 60; }
function blk(cls, it, left, w, icon, extra) {
  var on = sel && sel.id === it.id, kind = cls === 've-clip' ? 'c' : cls === 've-cb' ? 'k' : 'a';
  return '<div class="' + cls + (on ? ' on' : '') + '" data-kind="' + kind + '" data-id="' + it.id + '" style="left:' + (left * PPS) + 'px;width:' + Math.max(20, w * PPS) + 'px" title="' + esc(it.label) + '">' +
    (kind === 'c' ? '<i class="h h-l" data-h="l"></i>' : '<svg class="ic sm"><use href="#' + icon + '"/></svg>') + '<span>' + esc(it.label || '') + (extra || '') + '</span>' + (kind === 'c' ? '<i class="h h-r" data-h="r"></i>' : '') + '</div>';
}
function paintTl() {
  var len = Math.max(endAll(), 5), width = Math.max(560, Math.ceil((len + 8) * PPS)), tl = $('veTl');
  tl.style.width = (LBL + width) + 'px';
  ['veRuler', 'veLaneV', 'veLaneK', 'veLaneA', 'veLaneM'].forEach(function (id) { $(id).style.width = width + 'px'; });
  var step = tick1(len), ruler = '';
  for (var s = 0; s <= len + 8; s += step) ruler += '<span style="left:' + (s * PPS) + 'px">' + fmt(s) + '</span>';
  $('veRuler').innerHTML = ruler;
  $('veLaneV').innerHTML = T().clips.map(function (c) { return blk('ve-clip', c, c._at, c._len, '', c.fade ? ' · fade' : ''); }).join('');
  $('veLaneK').innerHTML = T().cams.map(function (k) { return blk('ve-cb', k, k.start, camLen(k), 'i-camera'); }).join('');
  $('veLaneA').innerHTML = T().audio.filter(function (a) { return a.kind !== 'music'; }).map(function (a) { return blk('ve-snd', a, a.start, audLen(a), 'i-mic'); }).join('');
  $('veLaneM').innerHTML = T().audio.filter(function (a) { return a.kind === 'music'; }).map(function (a) { return blk('ve-snd music', a, a.start, audLen(a), 'i-music', a.loop ? ' · loops' : ''); }).join('');
  $('veEmpty').hidden = T().clips.length > 0; moveHead();
}
function moveHead() { $('veHead').style.left = (tNow * PPS) + 'px'; }
function paintTime() { $('veTime').textContent = tc(tNow) + ' / ' + tc(total); }
function targetClip() {
  var it = selItem(); if (it && sel.kind === 'c') return it;
  var i = clipAt(tNow); return i >= 0 ? T().clips[i] : null;
}
function paintTools() {
  var it = selItem(), clipSel = it && sel.kind === 'c', c = targetClip();
  $('veSplit').disabled = !c; $('veTrimL').disabled = !c; $('veTrimR').disabled = !c; $('veDup').disabled = !clipSel; $('veFade').disabled = !clipSel; $('veDel').disabled = !it;
  $('veFade').classList.toggle('on', !!(clipSel && it.fade)); $('veUndo').disabled = !undoS.length; $('veRedo').disabled = !redoS.length;
  $('veExport').disabled = !T().clips.length; updateNew();
}
function paintInsp() {
  var el = $('veInsp'), it = selItem();
  if (!it) { el.innerHTML = '<h3>Nothing selected</h3><p class="help">Click a block on the timeline to edit it. Drag a block to move it, or drag the edges of a video clip to trim it.</p><p class="help">New here? Press <b>Video</b> to add your scenes, <b>Music</b> for background sound, and <b>Export video</b> when you are happy.</p>'; return; }
  if (sel.kind === 'c') {
    var d = dur(it.src);
    el.innerHTML = '<h3><svg class="ic sm"><use href="#i-film"/></svg>Video clip</h3><label class="lbl" for="ciL">Name</label><input class="input" id="ciL" value="' + esc(it.label) + '">' +
      '<div class="ve-two"><div><label class="lbl" for="ciI">Starts (s)</label><input class="input" id="ciI" type="number" min="0" step="0.1" value="' + it.in.toFixed(1) + '"></div>' +
      '<div><label class="lbl" for="ciO">Ends (s)</label><input class="input" id="ciO" type="number" min="0" step="0.1" value="' + (it.out != null ? it.out : d).toFixed(1) + '"></div></div>' +
      '<p class="help">The original is ' + tc(d) + ' long. This clip plays ' + tc(it._len || 0) + '.</p>';
  } else if (sel.kind === 'k') {
    el.innerHTML = '<h3><svg class="ic sm"><use href="#i-camera"/></svg>Camera</h3><label class="lbl" for="kiS">Starts at (s)</label><input class="input" id="kiS" type="number" min="0" step="0.1" value="' + it.start.toFixed(1) + '">' +
      '<span class="lbl">Where it sits</span><div class="ve-opts" id="kiC">' + [['tl', 'Top left'], ['tr', 'Top right'], ['bl', 'Bottom left'], ['br', 'Bottom right']].map(function (o) { return '<button data-c="' + o[0] + '" aria-pressed="' + (it.corner === o[0]) + '">' + o[1] + '</button>'; }).join('') + '</div>' +
      '<label class="lbl" for="kiZ">Size</label><input id="kiZ" type="range" min="12" max="55" step="1" value="' + it.size + '"><label class="lbl" for="kiV">Volume</label><input id="kiV" type="range" min="0" max="2" step="0.05" value="' + it.volume + '">';
  } else {
    el.innerHTML = '<h3><svg class="ic sm"><use href="#' + (it.kind === 'music' ? 'i-music' : 'i-mic') + '"/></svg>' + (it.kind === 'music' ? 'Background music' : 'Voice-over') + '</h3><label class="lbl" for="aiL">Name</label><input class="input" id="aiL" value="' + esc(it.label) + '">' +
      '<label class="lbl" for="aiS">Starts at (s)</label><input class="input" id="aiS" type="number" min="0" step="0.1" value="' + it.start.toFixed(1) + '"><label class="lbl" for="aiV">Volume</label><input id="aiV" type="range" min="0" max="2" step="0.05" value="' + it.volume + '">' +
      (it.kind === 'music' ? '<label class="chk"><input type="checkbox" id="aiLoop"' + (it.loop ? ' checked' : '') + '> Repeat to fill the whole video</label>' : '');
  }
}
function paintAll() { layout(); paintTl(); paintInsp(); paintTime(); paintTools(); $('veShape').value = T().size; fitFrame(); }
$('veShape').addEventListener('change', function () { T().size = this.value; commit(); });
var SHARE = { yt: { size: '16:9', q: 'high', caps: false }, reel: { size: '9:16', q: 'high', caps: true }, post: { size: '1:1', q: 'high', caps: true }, chat: { size: 'auto', q: 'share', caps: false } };
$('veShare').addEventListener('change', function () {      // one choice sets the shape, the quality and the captions together
  var s = SHARE[this.value]; if (!s) return;
  T().size = s.size; $('vePreset').value = s.q; $('veCaps').checked = s.caps; commit();
});
$('veInsp').addEventListener('input', function (e) {
  var t = e.target, it = selItem(); if (!it) return;
  if (sel.kind === 'c') {
    if (t.id === 'ciL') it.label = t.value;
    else if (t.id === 'ciI' || t.id === 'ciO') {
      var d = dur(it.src), iv = parseFloat($('ciI').value), ov = parseFloat($('ciO').value); if (!isFinite(iv) || !isFinite(ov)) return;
      iv = Math.max(0, Math.min(iv, d - 0.2)); ov = Math.max(iv + 0.2, Math.min(ov, d)); it.in = iv; it.out = ov >= d - 0.01 ? null : ov;
    }
  } else if (sel.kind === 'k') {
    if (t.id === 'kiS') it.start = Math.max(0, parseFloat(t.value) || 0); else if (t.id === 'kiZ') it.size = parseInt(t.value, 10); else if (t.id === 'kiV') it.volume = parseFloat(t.value);
  } else {
    if (t.id === 'aiL') it.label = t.value; else if (t.id === 'aiS') it.start = Math.max(0, parseFloat(t.value) || 0); else if (t.id === 'aiV') { it.volume = parseFloat(t.value); if (auds[it.id]) auds[it.id].volume = Math.min(1, it.volume); }
  }
  layout(); paintTl(); paintTime(); updateCam(tNow);
});
$('veInsp').addEventListener('change', function (e) {
  var it = selItem(); if (it && e.target.id === 'aiLoop') it.loop = e.target.checked;
  commit();
});
$('veInsp').addEventListener('click', function (e) { var b = e.target.closest('#kiC [data-c]'), it = selItem(); if (b && it && sel.kind === 'k') { it.corner = b.dataset.c; commit(); updateCam(tNow); } });

/* tools */
function removeSel() {
  var it = selItem(); if (!it) return;
  if (sel.kind === 'c') T().clips = T().clips.filter(function (x) { return x !== it; }); else if (sel.kind === 'k') T().cams = T().cams.filter(function (x) { return x !== it; }); else T().audio = T().audio.filter(function (x) { return x !== it; });
  sel = null; layout(); commit(); seek(Math.min(tNow, total));
}
$('veDel').addEventListener('click', removeSel);
$('veDup').addEventListener('click', function () {
  var it = selItem(); if (!it || sel.kind !== 'c') return; var i = T().clips.indexOf(it), n = { id: uid(), src: it.src, label: it.label + ' copy', in: it.in, out: it.out, fade: it.fade };
  T().clips.splice(i + 1, 0, n); sel = { kind: 'c', id: n.id }; layout(); commit();
});
$('veFade').addEventListener('click', function () { var it = selItem(); if (!it || sel.kind !== 'c') return; it.fade = !it.fade; commit(); });
$('veSplit').addEventListener('click', function () {
  layout(); var i = clipAt(tNow); if (i < 0) { toast('Move the playhead over a clip first'); return; }
  var c = T().clips[i], off = tNow - c._at; if (off < 0.15 || off > c._len - 0.15) { toast('Move the playhead further inside the clip'); return; }
  var b = { id: uid(), src: c.src, label: c.label + ' (2)', in: c.in + off, out: c.out, fade: false }; c.out = c.in + off; T().clips.splice(i + 1, 0, b); sel = { kind: 'c', id: b.id }; layout(); commit();
});
function trimTo(which) {
  layout(); var c = targetClip(); if (!c) { toast('Select a clip first'); return; }
  var off = tNow - c._at; if (off < 0.1 || off > c._len - 0.1) { toast('Move the playhead inside the clip you want to trim'); return; }
  if (which === 'l') c.in = c.in + off; else c.out = c.in + off;
  sel = { kind: 'c', id: c.id }; layout(); commit(); seek(Math.min(tNow, total));
}
$('veTrimL').addEventListener('click', function () { trimTo('l'); }); $('veTrimR').addEventListener('click', function () { trimTo('r'); });

/* dragging on the timeline: select, move, trim */
var drag = null;
function laneX(ev) { return ev.clientX - $('veLaneV').getBoundingClientRect().left; }
$('veTl').addEventListener('pointerdown', function (e) {
  var item = e.target.closest('[data-kind]'), x = laneX(e);
  if (!item) { if (e.target.closest('#veRuler, .ve-lane')) { sel = null; paintAll(); seek(Math.max(0, x / PPS)); drag = { seek: true }; $('veTl').setPointerCapture(e.pointerId); } return; }
  sel = { kind: item.dataset.kind, id: item.dataset.id }; var it = selItem(); if (!it) return;
  drag = { kind: sel.kind, id: it.id, x0: e.clientX, h: e.target.dataset.h || '', in0: it.in || 0, out0: sel.kind === 'c' ? (it.out != null ? it.out : dur(it.src)) : 0, start0: it.start || 0, moved: false };
  paintAll(); $('veTl').setPointerCapture(e.pointerId); e.preventDefault();
});
$('veTl').addEventListener('pointermove', function (e) {
  if (!drag) return;
  if (drag.seek) { seek(Math.max(0, laneX(e) / PPS)); return; }
  var dx = (e.clientX - drag.x0) / PPS; if (Math.abs(e.clientX - drag.x0) > 3) drag.moved = true; if (!drag.moved) return;
  var it = selItem(); if (!it) return;
  if (drag.kind === 'c' && drag.h === 'l') { it.in = Math.max(0, Math.min(drag.in0 + dx, drag.out0 - 0.2)); layout(); paintTl(); paintInsp(); paintTime(); }
  else if (drag.kind === 'c' && drag.h === 'r') { var o = Math.max(it.in + 0.2, Math.min(drag.out0 + dx, dur(it.src))); it.out = o >= dur(it.src) - 0.01 ? null : o; layout(); paintTl(); paintInsp(); paintTime(); }
  else if (drag.kind === 'c') {
    var pt = laneX(e) / PPS; drag.target = T().clips.filter(function (k) { return k.id !== it.id && k._at + k._len / 2 < pt; }).length;
    var el = $('veLaneV').querySelector('[data-id="' + it.id + '"]'); if (el) { el.style.transform = 'translateX(' + (e.clientX - drag.x0) + 'px)'; el.classList.add('lift'); }
  } else { it.start = Math.max(0, drag.start0 + dx); paintTl(); paintInsp(); }
});
$('veTl').addEventListener('pointerup', function () {
  if (!drag) return; var d = drag; drag = null; if (d.seek) { paintAll(); return; }
  if (d.kind === 'c' && !d.h && d.moved && d.target != null) { var cl = T().clips, i = cl.findIndex(function (k) { return k.id === d.id; }); if (i >= 0 && d.target !== i) { var m = cl.splice(i, 1)[0]; cl.splice(Math.min(d.target, cl.length), 0, m); } }
  layout(); commit(); if (d.moved) seek(Math.min(tNow, total));
});

/* playback */
function clipAt(t) { var cl = T().clips; for (var i = 0; i < cl.length; i++) if (t >= cl[i]._at && t < cl[i]._at + cl[i]._len - 0.001) return i; return -1; }
function setVideoTime(el, tt) { if (el.readyState >= 1) el.currentTime = tt; else el.addEventListener('loadedmetadata', function () { el.currentTime = tt; }, { once: true }); }
function loadClip(i, offset) { var c = T().clips[i], url = mediaUrl(c.src); curIdx = i; if (!url) return; if (V.dataset.src !== url) { V.src = url; V.dataset.src = url; } setVideoTime(V, c.in + offset); }
function audEl(a) { var el = auds[a.id]; if (!el) { el = new Audio(mediaUrl(a.src)); el.preload = 'auto'; auds[a.id] = el; } el.volume = Math.min(1, a.volume); return el; }
function syncAudio(t, play) {
  T().audio.forEach(function (a) {
    if (!mediaUrl(a.src)) return; var el = audEl(a), d = audLen(a), inside = t >= a.start && t < a.start + d && t <= total + 0.05;
    el.loop = !!(a.kind === 'music' && a.loop);
    if (play && inside) { if (el.paused) { el.currentTime = ((t - a.start) + (a.in || 0)) % Math.max(0.5, dur(a.src) || 1e9); el.play().catch(function () {}); } } else if (!el.paused) el.pause();
  });
}
function updateCam(t) {
  if (rec && rec.kind === 'cam') return;
  var k = T().cams.filter(function (x) { return t >= x.start && t < x.start + camLen(x); })[0];
  if (!k || !mediaUrl(k.src)) { CAM.hidden = true; if (!CAM.paused) CAM.pause(); return; }
  var url = mediaUrl(k.src), want = (t - k.start) + (k.in || 0); CAM.hidden = false; CAM.className = 've-cam c-' + (k.corner || 'br'); CAM.style.width = (k.size || 28) + '%'; CAM.muted = false; CAM.volume = Math.min(1, k.volume == null ? 1 : k.volume);
  if (CAM.dataset.src !== url) { CAM.src = url; CAM.dataset.src = url; setVideoTime(CAM, want); }
  else if (Math.abs(CAM.currentTime - want) > 0.4) CAM.currentTime = want;
  if (playing && CAM.paused) CAM.play().catch(function () {}); else if (!playing && !CAM.paused) CAM.pause();
}
function seek(t) {
  layout(); tNow = Math.max(0, Math.min(t, Math.max(total, 0)));
  var i = clipAt(tNow); if (i >= 0) loadClip(i, tNow - T().clips[i]._at); else if (!T().clips.length) { V.removeAttribute('src'); delete V.dataset.src; }
  if (playing && i >= 0) V.play().catch(function () {});
  Object.keys(auds).forEach(function (k) { auds[k].pause(); }); if (playing) syncAudio(tNow, true);
  updateCam(tNow); moveHead(); paintTime(); paintTools();
}
function setPlayIcon() { $('vePlayIcon').setAttribute('href', playing ? '#i-pause' : '#i-play'); $('vePlay').setAttribute('aria-label', playing ? 'Pause' : 'Play'); }
function play() {
  if (!T().clips.length) { toast('Add a video to the timeline first'); return; }
  if (tNow >= total - 0.05) seek(0);
  playing = true; setPlayIcon(); var i = clipAt(tNow); if (i < 0) { seek(0); i = 0; }
  V.play().catch(function () {}); clearInterval(tick);
  tick = setInterval(function () {
    var c = T().clips[curIdx]; if (!c) return;
    tNow = c._at + (V.currentTime - c.in);
    if (V.currentTime >= c.in + c._len - 0.04 || V.ended) {
      if (curIdx + 1 < T().clips.length) { loadClip(curIdx + 1, 0); V.play().catch(function () {}); tNow = T().clips[curIdx]._at; } else { pause(); tNow = total; if (rec) stopRec(false); }
    }
    syncAudio(tNow, playing); updateCam(tNow); moveHead(); paintTime();
    var sc = $('veScroll'), x = tNow * PPS + LBL; if (x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = x - 120;
  }, 40);
}
function pause() { playing = false; setPlayIcon(); clearInterval(tick); V.pause(); CAM.pause(); Object.keys(auds).forEach(function (k) { auds[k].pause(); }); }
$('vePlay').addEventListener('click', function () { playing ? pause() : play(); });
$('veBack').addEventListener('click', function () { seek(0); $('veScroll').scrollLeft = 0; });
$('veFwd').addEventListener('click', function () { layout(); var n = T().clips.filter(function (c) { return c._at > tNow + 0.05; })[0]; seek(n ? n._at : total); });
$('veZoom').addEventListener('input', function () { PPS = parseInt(this.value, 10) || 48; paintAll(); });

/* menus for Video / Music / Camera */
function closeVeMenu() { $('veMenu').hidden = true; }
function showMenu(btn, rows) {
  var m = $('veMenu'); if (!m.hidden && m.dataset.for === btn.id) { closeVeMenu(); return; }
  m.innerHTML = rows.join(''); m.dataset.for = btn.id; var r = btn.getBoundingClientRect(); m.hidden = false; m.style.left = Math.max(8, Math.min(Math.round(r.left), innerWidth - 300)) + 'px'; m.style.top = Math.round(r.bottom + 6) + 'px';
}
function mediaOf(filter) { return Object.keys(PR.media).filter(function (k) { return !/\.srt$/i.test(k) && k.indexOf('exports/') !== 0 && filter(k, PR.media[k]); }); }
function item(label, attrs, icon) { return '<button class="m-item" role="menuitem" ' + attrs + '>' + (icon ? '<svg class="ic sm"><use href="#' + icon + '"/></svg>' : '') + esc(label) + '</button>'; }
$('veAddVideo').addEventListener('click', function () {
  var rows = ['<div class="m-head">Rendered scenes</div>'], r = renderedList(), others = mediaOf(function (k, e) { return e.type === 'video' && k.indexOf('renders/') !== 0; });
  if (r.length) rows.push(item('Add every rendered scene, in order', 'data-add="all"', 'i-film'));
  r.forEach(function (s) { rows.push(item(s.scene + '  (' + s.file + ')', 'data-add="v" data-src="' + esc(s.render) + '" data-scene="' + esc(s.scene) + '"', 'i-plus')); });
  if (!r.length) rows.push('<div class="m-item dis">Nothing rendered yet. Press Start Rendering first.</div>');
  if (others.length) { rows.push('<div class="m-head">Other videos</div>'); others.forEach(function (k) { rows.push(item(baseName(k), 'data-add="v" data-src="' + esc(k) + '"', 'i-plus')); }); }
  rows.push('<div class="m-sep"></div>', item('Import a video file…', 'data-add="import-v"', 'i-export')); showMenu(this, rows);
});
$('veAddMusic').addEventListener('click', function () {
  var rows = ['<div class="m-head">Background music</div>'], s = mediaOf(function (k, e) { return e.type === 'audio' && !/voiceover/i.test(k); });
  s.forEach(function (k) { rows.push(item(baseName(k), 'data-add="music" data-src="' + esc(k) + '"', 'i-music')); });
  if (!s.length) rows.push('<div class="m-item dis">No music in the project yet.</div>');
  rows.push('<div class="m-sep"></div>', item('Import a music file…', 'data-add="import-m"', 'i-export')); showMenu(this, rows);
});
$('veAddCam').addEventListener('click', function () {
  if (rec && rec.kind === 'cam') { stopRec(false); return; }
  var rows = ['<div class="m-head">Yourself on camera</div>', item('Record with my camera', 'data-add="cam-rec"', 'i-camera')], s = mediaOf(function (k, e) { return e.type === 'video' && k.indexOf('renders/') !== 0; });
  s.forEach(function (k) { rows.push(item('Use ' + baseName(k), 'data-add="cam" data-src="' + esc(k) + '"', 'i-plus')); });
  rows.push('<div class="m-sep"></div>', item('Import a video of me…', 'data-add="import-c"', 'i-export')); showMenu(this, rows);
});
$('veMenu').addEventListener('click', function (e) {
  var b = e.target.closest('[data-add]'); if (!b) return; var k = b.dataset.add; closeVeMenu();
  if (k === 'v') addClip(b.dataset.src, b.dataset.scene);
  else if (k === 'music') addSound(b.dataset.src, 0, 'music');
  else if (k === 'cam') addCam(b.dataset.src, tNow);
  else if (k === 'all') { renderedList().forEach(function (s) { addClipRaw(s.render, s.scene); }); ensureInfo().then(function () { layout(); commit(); }); }
  else if (k === 'cam-rec') startRec('cam');
  else if (k.indexOf('import') === 0) api('/api/project/import-pick', {}).then(function (r) {
    if (!r.src) return;
    return refresh().then(function () {
      var t = PR.media[r.src];
      if (k === 'import-m' || (t && t.type === 'audio' && k !== 'import-v')) addSound(r.src, 0, 'music'); else if (k === 'import-c') addCam(r.src, tNow); else addClip(r.src);
      toast('Added ' + baseName(r.src));
    });
  }).catch(function (er) { toast(er.message); });
});
document.addEventListener('pointerdown', function (e) { if (!$('veMenu').hidden && !e.target.closest('#veMenu, .ve-tool')) closeVeMenu(); });

/* recording: voice-over and camera */
function setRecUi() {
  $('veRec').classList.toggle('live', !!rec && rec.kind === 'voice'); $('veAddCam').classList.toggle('live', !!rec && rec.kind === 'cam');
  $('veRec').querySelector('span').textContent = rec && rec.kind === 'voice' ? 'Stop' : 'Voice-over'; $('veAddCam').querySelector('span').textContent = rec && rec.kind === 'cam' ? 'Stop' : 'Camera';
}
function stopRec(discard) {
  if (!rec) return; var r = rec; rec = null; setRecUi(); r.discard = !!discard; try { r.mr.stop(); } catch (e) {} r.stream.getTracks().forEach(function (t) { t.stop(); }); pause();
  if (r.kind === 'cam') { CAM.srcObject = null; CAM.dataset.src = ''; CAM.muted = false; updateCam(tNow); }
}
function startRec(kind) {
  if (rec) { toast('Stop the current recording first'); return; }
  if (!T().clips.length) { toast('Add a video to the timeline first, then record over it'); return; }
  if (!navigator.mediaDevices || !window.MediaRecorder) { toast('Recording is not available in this window'); return; }
  var want = kind === 'cam' ? { audio: { echoCancellation: true, noiseSuppression: true }, video: { width: 1280, height: 720 } } : { audio: { echoCancellation: true, noiseSuppression: true } };
  navigator.mediaDevices.getUserMedia(want).then(function (stream) {
    var chunks = [], mr = new MediaRecorder(stream), start = tNow, r = { mr: mr, stream: stream, kind: kind, discard: false };
    mr.ondataavailable = function (ev) { if (ev.data && ev.data.size) chunks.push(ev.data); };
    mr.onstop = function () {
      if (r.discard || !chunks.length) return; var blob = new Blob(chunks, { type: kind === 'cam' ? 'video/webm' : 'audio/webm' });
      toast('Saving your ' + (kind === 'cam' ? 'camera clip' : 'voice-over') + '…');
      fetch('/api/project/recording?name=' + (kind === 'cam' ? 'camera' : 'voiceover') + '.webm&convert=' + (kind === 'cam' ? 'video' : 'audio'), { method: 'POST', headers: { 'X-Token': M.TOKEN }, body: blob })
        .then(function (res) { return res.json().then(function (j) { if (!res.ok) throw new Error(j.error || 'Could not save'); return j; }); })
        .then(function (j) { return refresh().then(function () { if (kind === 'cam') addCam(j.src, start, 'Me on camera'); else addSound(j.src, start, 'voice', 'Voice-over'); toast('Added at ' + tc(start)); }); })
        .catch(function (er) { toast(er.message); });
    };
    rec = r; setRecUi(); mr.start(500);
    if (kind === 'cam') { CAM.srcObject = stream; CAM.muted = true; CAM.hidden = false; CAM.className = 've-cam c-br'; CAM.style.width = '28%'; CAM.play().catch(function () {}); }
    play();
  }).catch(function (er) { toast(er && er.name === 'NotAllowedError' ? 'Windows did not allow the ' + (kind === 'cam' ? 'camera' : 'microphone') + '. Check Settings > Privacy & security.' : 'No ' + (kind === 'cam' ? 'camera' : 'microphone') + ' was found.'); });
}
$('veSpeak').addEventListener('click', function () { pause(); $('speakMsg').textContent = 'The voice is made on this computer. It is added to the Voice lane at the playhead.'; $('speakDlg').showModal(); setTimeout(function () { $('speakText').focus(); }, 30); });
$('speakGo').addEventListener('click', function () {
  var b = this, text = $('speakText').value.trim(), start = tNow, s = M.settings();
  if (!text) { $('speakMsg').textContent = 'Type the words to speak first.'; return; }
  b.disabled = true; $('speakMsg').textContent = 'Making the voice\u2026';
  api('/api/project/narrate', { text: text, voice: s.voice, speed: s.speed }).then(function (j) {
    return refresh().then(function () { return ensureInfo(); }).then(function () { addSound(j.src, start, 'voice', 'Narration'); $('speakDlg').close(); toast('Added at ' + tc(start)); });
  }).catch(function (e) { $('speakMsg').textContent = e.message; }).then(function () { b.disabled = false; });
});
$('veCover').addEventListener('click', function () {
  layout(); var cs = T().clips; if (!cs.length) { toast('Add a video first'); return; }
  var c = cs.filter(function (x) { return tNow >= x._at && tNow < x._at + x._len; })[0] || cs[cs.length - 1];
  api('/api/project/cover', { src: c.src, at: (c.in || 0) + Math.max(0, tNow - c._at) }).then(function (r) {
    toast('Cover saved in the exports folder: ' + r.name);
  }).catch(function (e) { toast(e.message); });
});$('veRec').addEventListener('click', function () { if (rec && rec.kind === 'voice') stopRec(false); else startRec('voice'); });

/* export */
$('veExport').addEventListener('click', function () {
  if (!T().clips.length) { toast('Add a video to the timeline first'); return; }
  pause(); clearTimeout(saveTl);
  var box = $('veExp'); box.hidden = false; box.innerHTML = '<p>Starting…</p><div class="bar"><i style="transform:scaleX(0)"></i></div>';
  api('/api/project/timeline', { timeline: cleanTl() }).then(function () { return api('/api/project/export', { preset: $('vePreset').value, captions: $('veCaps').checked }); }).then(function () {
    clearInterval(exportPoll);
    exportPoll = setInterval(function () {
      api('/api/project/export').then(function (j) {
        if (j.state === 'running') { box.innerHTML = '<p>Making your video… ' + Math.floor(j.percent || 0) + '%</p><div class="bar"><i style="transform:scaleX(' + ((j.percent || 0) / 100) + ')"></i></div>'; }
        else {
          clearInterval(exportPoll); exportPoll = null;
          if (j.state === 'done') {
            box.innerHTML = '<p><b>Done.</b> ' + esc(j.file.name) + ' (' + fmt(j.seconds) + ')</p><p class="help">Chapters' + (j.subtitles ? ' and subtitles' : '') + ' were saved next to it.</p><button class="btn sm" id="veShow">Show folder</button>';
            $('veShow').onclick = function () { M.exportsFolderOpen(PR.path + '\\exports'); }; refresh();
          } else box.innerHTML = '<p class="err">' + esc(j.error || 'The export stopped.') + '</p>';
        }
      }).catch(function () { clearInterval(exportPoll); exportPoll = null; });
    }, 600);
  }).catch(function (e) { box.innerHTML = '<p class="err">' + esc(e.message) + '</p>'; });
});

/* keyboard */
document.addEventListener('keydown', function (e) {
  if ($('vedit').hidden) return; var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || '')), k = e.key.toLowerCase();
  if (e.key === 'Escape') { if (!$('veMenu').hidden) closeVeMenu(); else closeEditor(); e.preventDefault(); return; }
  if ((e.ctrlKey || e.metaKey) && k === 'z') { if (!typing) { e.preventDefault(); if (e.shiftKey) redo(); else undo(); } return; }
  if ((e.ctrlKey || e.metaKey) && k === 'y') { if (!typing) { e.preventDefault(); redo(); } return; }
  if (typing) return;
  if (e.key === ' ') { e.preventDefault(); playing ? pause() : play(); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); seek(tNow - (e.shiftKey ? 5 : 1)); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); seek(tNow + (e.shiftKey ? 5 : 1)); }
  else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); removeSel(); }
  else if (k === 's' && !e.ctrlKey && !e.metaKey) $('veSplit').click();
  else if (e.key === '[') trimTo('l'); else if (e.key === ']') trimTo('r');
});

/* ---------------------------------------------------------------- bridge back to app.js */
window.MGXProject = {
  active: function () { return PR.open && !PR.quick; },
  editVideo: editVideo,
  label: function () { return PR.name; },
  changed: changed, flush: flush, refresh: refresh, openPath: openPath,
  beforeRender: function () { return flush().then(function () { return api('/api/project/settings', M.settings()).catch(function () {}); }); },
  show: function () { paintPane(); if (PR.open) refresh(); },
  menu: function () {
    var items = [{ label: 'New project…', key: '', run: newDlg }, { label: 'Open project…', key: '', run: openDlg }];
    if (PR.recent.length) { items.push({ head: 'Recent projects' }); PR.recent.slice(0, 5).forEach(function (p) { items.push({ label: baseName(p), key: '', run: function () { openPath(p); } }); }); }
    if (PR.open) items.push({ label: 'Compose…', key: '', run: openEditor }, { label: 'Close project', key: '', run: closeProject });
    items.push({ sep: true }); return items;
  },
  boot: function () {
    if (!M.TOKEN || M.TOKEN.indexOf('__') === 0) return;
    var q = new URLSearchParams(location.search).get('project');
    api('/api/project').then(function (st) {
      if (q) { apply(st); paintPane(); history.replaceState(null, '', location.pathname); openPath(q); }
      else if (st.open) { entered(st); }
      else { apply(st); paintPane(); }
    }).catch(function () {});
  }
};
paintPane();
})();
