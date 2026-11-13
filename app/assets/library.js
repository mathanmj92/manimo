/* My videos: every finished video in the output folder, with a cover picture, length and size.
   Play it in the preview, edit it in Compose, or show it in its folder. Covers are made once by the server and kept. */
(function () {
'use strict';
var dlg = document.getElementById('libDlg'), grid = document.getElementById('libGrid');
if (!dlg || !grid) return;
var M = window.MANIMO, $ = M.$, esc = M.esc;
var dirEl = $('libDir'), msg = $('libMsg'), seq = 0;
var lib = { items: [], cards: [], picked: {} };

function stamp(t) { t = Math.round(t || 0); return Math.floor(t / 60) + ':' + ('0' + (t % 60)).slice(-2); }
function mb(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB'; }
function when(ts) {
  var d = new Date(ts * 1000), now = new Date(), day = 86400000, diff = (new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / day;
  var hm = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return diff === 0 ? 'Today ' + hm : diff === 1 ? 'Yesterday ' + hm : d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + hm;
}
function btn(label, icon, cls) { return '<button class="btn sm ' + (cls || 'ghost') + '" title="' + label + '" aria-label="' + label + '"><svg class="ic sm"><use href="#' + icon + '"/></svg><span>' + label + '</span></button>'; }

function card(v) {
  var li = document.createElement('li'); li.className = 'lib-card'; li.dataset.path = v.path;
  li.innerHTML = '<label class="lib-pick" title="Select this video"><input type="checkbox" aria-label="Select ' + esc(v.name) + '"></label><div class="lib-thumb" role="img" aria-label="Cover picture of ' + esc(v.name) + '"><span class="lib-len"></span></div>' +
    '<div class="lib-info"><b title="' + esc(v.name) + '">' + esc(v.name.replace(/\.[^.]+$/, '')) + '</b><small class="lib-meta">' + esc(when(v.mtime)) + ' · ' + mb(v.size) + '</small></div>' +
    '<div class="lib-acts">' + btn('Play', 'i-play', 'primary') + btn('Edit', 'i-scissors') + btn('Folder', 'i-folder') + '</div>';
  li.querySelector('.lib-pick input').onchange = function () { if (this.checked) lib.picked[v.path] = true; else delete lib.picked[v.path]; paintSel(); };
  var acts = li.querySelectorAll('.lib-acts .btn');
  acts[0].onclick = function () { dlg.close(); M.api('/api/serve-file', { path: v.path }).then(function (r) { M.setPreview([{ name: v.name, path: v.path, kind: 'video', url: r.url }], 0); if (M.narrow.matches) M.rightTab('preview'); }).catch(function (e) { M.toast(e.message); }); };
  acts[1].onclick = function () { dlg.close(); if (window.MGXProject) window.MGXProject.editVideo(v.path); };
  acts[2].onclick = function () { M.api('/api/open-folder', { path: v.path }).catch(function () {}); };
  return li;
}

function fillMeta(items, cards, mine) {          // one picture at a time, so the window stays responsive
  var i = 0;
  (function next() {
    if (mine !== seq || i >= items.length || !dlg.open) return;
    var v = items[i], li = cards[i]; i++;
    M.api('/api/video-meta', { path: v.path }).then(function (m) {
      if (mine !== seq) return;
      var t = li.querySelector('.lib-thumb');
      if (m.thumb) t.style.backgroundImage = 'url("' + m.thumb + '")';
      if (m.width && m.height) { t.style.aspectRatio = '16 / 9'; t.dataset.shape = m.height > m.width ? 'tall' : m.width === m.height ? 'square' : 'wide'; }
      t.querySelector('.lib-len').textContent = m.seconds ? stamp(m.seconds) : '';
      if (m.width) li.querySelector('.lib-meta').textContent += ' · ' + m.width + '×' + m.height;
    }).catch(function () {}).then(next);
  })();
}

/* search, sort and select (the cards are kept; only their order and visibility change) */
function arrange() {
  var q = $('libSearch').value.trim().toLowerCase(), how = $('libSort').value;
  var sorted = lib.cards.slice().sort(function (a, b) {
    var x = a._v, y = b._v;
    return how === 'old' ? x.mtime - y.mtime : how === 'name' ? x.name.localeCompare(y.name) : how === 'big' ? y.size - x.size : y.mtime - x.mtime;
  });
  var shown = 0;
  sorted.forEach(function (li) { var hit = !q || li._v.name.toLowerCase().indexOf(q) >= 0; li.hidden = !hit; if (hit) shown++; grid.appendChild(li); });
  if (lib.cards.length) msg.textContent = q ? shown + ' of ' + lib.cards.length + ' videos match.' : msg.dataset.base || msg.textContent;
}
function paintSel() {
  var n = Object.keys(lib.picked).length;
  $('libSelBar').hidden = !n; $('libSelCount').textContent = n + (n === 1 ? ' selected' : ' selected');
}
$('libSearch').addEventListener('input', function () { msg.dataset.base = msg.dataset.base || msg.textContent; arrange(); });
$('libSort').addEventListener('change', arrange);
$('libClear').addEventListener('click', function () { lib.picked = {}; grid.querySelectorAll('.lib-pick input').forEach(function (c) { c.checked = false; }); paintSel(); });
$('libDelete').addEventListener('click', function () {
  var paths = Object.keys(lib.picked); if (!paths.length) return;
  if (!window.confirm('Move ' + paths.length + (paths.length === 1 ? ' video' : ' videos') + ' to the Recycle Bin?\n\nYou can restore ' + (paths.length === 1 ? 'it' : 'them') + ' from the Recycle Bin.')) return;
  M.api('/api/library/delete', { dir: dirEl.title || dirEl.textContent, paths: paths }).then(function (r) {
    lib.cards = lib.cards.filter(function (li) { if (lib.picked[li._v.path]) { li.remove(); return false; } return true; });
    lib.picked = {}; paintSel(); msg.dataset.base = lib.cards.length + (lib.cards.length === 1 ? ' video' : ' videos') + ', ' + $('libSort').selectedOptions[0].textContent.toLowerCase() + '.'; msg.textContent = 'Moved ' + r.deleted + (r.deleted === 1 ? ' video' : ' videos') + ' to the Recycle Bin.';
  }).catch(function (e) { msg.textContent = e.message; });
});

function open() {
  var mine = ++seq, dir = M.outDir ? M.outDir() : '';
  grid.innerHTML = ''; lib = { items: [], cards: [], picked: {} }; $('libSearch').value = ''; msg.dataset.base = ''; paintSel(); msg.textContent = 'Looking for your videos…';
  M.openDialog ? dlg.showModal() : dlg.showModal();
  M.api('/api/library', { dir: dir }).then(function (r) {
    if (mine !== seq) return;
    dirEl.textContent = r.dir; dirEl.title = r.dir;
    if (!r.videos.length) { msg.textContent = 'No videos here yet. Press Start Rendering and your first video will appear in this folder.'; return; }
    msg.textContent = msg.dataset.base = r.total > r.videos.length ? 'Showing the newest ' + r.videos.length + ' of ' + r.total + ' videos.' : r.total + (r.total === 1 ? ' video' : ' videos') + '.';
    lib.items = r.videos; lib.picked = {};
    lib.cards = r.videos.map(function (v) { var li = card(v); li._v = v; return li; });
    arrange(); paintSel();
    fillMeta(r.videos, lib.cards, mine);
  }).catch(function (e) { msg.textContent = e.message || 'Could not read the folder.'; });
}
$('libFolder').onclick = function () { M.api('/api/open-folder', { path: dirEl.title || dirEl.textContent }).catch(function () {}); };
dlg.addEventListener('close', function () { seq++; });
window.MGXLibrary = { open: open };
})();
