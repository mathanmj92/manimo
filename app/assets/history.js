/* Version history: a snapshot of the code after a pause in typing and before every render. Open it from Edit, Version history. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('histDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc, timer = null, cur = null;

function key() { return M.getName() || 'untitled'; }
function snap(reason) {
  var code = M.getCode();
  if (!code.trim()) return Promise.resolve();
  return M.api('/api/history/save', { key: key(), code: code, reason: reason }).catch(function () {});
}
function edited() { clearTimeout(timer); timer = setTimeout(function () { snap('Edited'); }, 20000); }

function when(ts) {
  var d = new Date(ts * 1000), today = new Date().toDateString() === d.toDateString();
  return (today ? 'Today' : d.toLocaleDateString()) + ', ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function paintList(items) {
  $('histList').innerHTML = items.length ? items.map(function (s) {
    return '<li><button class="hist-item" data-id="' + esc(s.id) + '" aria-pressed="' + (cur === s.id) + '"><b>' + esc(when(s.ts)) + '</b><span>' + esc(s.reason) + ' · ' + s.lines + ' lines' +
      (s.added || s.removed ? ' · <i class="hist-add">+' + s.added + '</i> <i class="hist-del">−' + s.removed + '</i>' : '') + '</span></button></li>';
  }).join('') : '<li class="help">No versions yet. Manimo saves one when you pause typing and before every render.</li>';
}
function load() {
  return M.api('/api/history/list', { key: key() }).then(function (r) { paintList(r.items); return r.items; });
}
function show(id) {
  cur = id;
  document.querySelectorAll('#histList .hist-item').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.id === id)); });
  M.api('/api/history/get', { key: key(), id: id, code: M.getCode() }).then(function (r) {
    $('histRestore').disabled = r.same; $('histRestore')._code = r.code;
    $('histNote').textContent = r.same ? 'This version is the same as the code in the editor now.' : 'Red lines are only in this version. Green lines are only in the editor now.';
    $('histDiff').innerHTML = r.same ? '' : r.diff.map(function (ln) {
      var c = ln[0] === '+' ? 'add' : ln[0] === '-' ? 'del' : ln[0] === '@' ? 'at' : '';
      return '<span class="' + c + '">' + esc(ln) + '</span>';
    }).join('\n');
  }).catch(function (e) { $('histNote').textContent = e.message; });
}
function open() {
  cur = null; $('histDiff').innerHTML = ''; $('histRestore').disabled = true;
  $('histNote').textContent = 'Pick a version on the left to see what changed.';
  $('histFile').textContent = key();
  snap('Opened history').then(load).then(function (items) { dlg.showModal(); if (items.length > 1) show(items[1].id); });
}
$('histList').addEventListener('click', function (e) { var b = e.target.closest('.hist-item'); if (b) show(b.dataset.id); });
$('histRestore').addEventListener('click', function () {
  var code = this._code; if (!code) return;
  snap('Before restore').then(function () {            // the code being replaced is kept too, so a restore can be undone
    M.setCode(code, M.getName()); dlg.close(); M.toast('Restored. The version you had is kept in the history.');
  });
});

window.MGXHistory = { edited: edited, snap: snap, open: open };
})();
