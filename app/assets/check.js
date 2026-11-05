/* Code check: looks over pasted or typed code before it is rendered.
   Quick check (no render, about a tenth of a second): syntax, a Scene to render, names that do not exist, the engine's import, safety.
   Layout check (runs the scene as the assistant does, a few seconds): errors with their line, overlapping text, content outside the frame.
   The quick check runs after every pause in typing; the layout check runs after a paste, when a file is opened, and on request. */
(function () {
'use strict';
var M = window.MANIMO, pill = document.getElementById('checkPill'), panel = document.getElementById('checkPanel');
if (!M || !pill || !panel) return;
var $ = M.$, esc = M.esc;

var state = { quick: null, deep: null, seq: 0, deepSeq: 0, busy: false, lastLen: 0, lastCode: '', deepFor: '', pkg: { running: false, step: '', error: '' } };
var quickTimer = null, deepTimer = null;

function issuesNow() { return (state.deep && state.deepFor === state.lastCode ? state.deep.issues : state.quick && state.quick.issues) || []; }

function paintPill() {
  var n = issuesNow().length, code = M.getCode();
  if (!code.trim()) { pill.hidden = true; panel.hidden = true; return; }
  pill.hidden = false;
  var checking = state.busy;
  pill.className = 'chk-pill ' + (checking ? 'busy' : n ? 'warn' : 'ok');
  pill.textContent = checking ? 'Checking…' : n ? n + (n === 1 ? ' problem' : ' problems') : 'Code looks good';
  pill.setAttribute('aria-expanded', String(!panel.hidden));
  pill.title = n ? 'Click to see what the check found' : 'Click for details, or to check the layout';
  if (!panel.hidden) paintPanel();
}

function paintPanel() {
  var list = issuesNow(), deepDone = state.deep && state.deepFor === state.lastCode && state.deep.deep;
  var html = '<div class="chk-head"><b>' + (list.length ? 'What the check found' : 'No problems found') + '</b><button class="icon-btn" id="chkClose" aria-label="Close"><svg class="ic"><use href="#i-x"/></svg></button></div>';
  var pk = list.filter(function (i) { return i.kind === 'package'; });
  if (list.length) {
    html += '<ul class="chk-list">' + list.map(function (i) {
      var where = i.line ? '<button class="linkbtn" data-line="' + i.line + '">Line ' + i.line + '</button> ' : '';
      var add = i.kind === 'package' ? ' <button class="btn sm" data-pkg="' + esc(i.module) + '"' + (state.pkg.running ? ' disabled' : '') + '>Install ' + esc(i.package) + '</button>' : '';
      return '<li class="chk-' + esc(i.kind) + '">' + where + esc(i.text) + add + '</li>';
    }).join('') + '</ul>';
    if (state.pkg.running) html += '<p class="help">' + esc(state.pkg.step || 'Installing...') + '</p>';
    else if (state.pkg.error) html += '<p class="help chk-error">' + esc(state.pkg.error) + '</p>';
    else if (pk.length > 1) html += '<div class="chk-bar"><button class="btn sm" data-pkg="*">Install all ' + pk.length + '</button><span class="help">Downloads from the internet (PyPI).</span></div>';
  } else {
    html += '<p class="help">' + (deepDone ? 'The scene ran and nothing overlaps or leaves the frame.' : 'The code reads correctly and every name exists. Check the layout to run the scene and look for overlapping text.') + '</p>';
  }
  if (state.deep && state.deepFor === state.lastCode && state.deep.note) html += '<p class="help">' + esc(state.deep.note) + '</p>';
  html += '<div class="chk-bar"><button class="btn sm" id="chkDeep"' + (state.busy ? ' disabled' : '') + '>' + (deepDone ? 'Check again' : 'Check the layout') + '</button><span class="help">' + (deepDone && state.deep.seconds ? 'About ' + Math.round(state.deep.seconds) + ' s of video.' : 'Takes a few seconds.') + '</span></div>';
  panel.innerHTML = html;
}

function quick() {
  var code = M.getCode(), mine = ++state.seq;
  state.lastCode = code;
  if (!code.trim()) { state.quick = null; paintPill(); return; }
  M.api('/api/ai/check', { code: code }).then(function (r) {
    if (mine !== state.seq) return;
    state.quick = r; paintPill();
    if (state.wantDeep && !r.issues.some(function (i) { return i.kind === 'error' || i.kind === 'safety'; })) deepSoon(600);
  }).catch(function () {});
}

function deep() {
  var code = M.getCode(), mine = ++state.deepSeq;
  if (!code.trim() || state.busy) return;
  state.busy = true; state.wantDeep = false; paintPill();
  M.api('/api/ai/check', { code: code, deep: true, scene: M.selectedScene ? M.selectedScene() : '' }).then(function (r) {
    if (mine !== state.deepSeq) return;
    state.deep = r; state.deepFor = code;
    if (code !== M.getCode()) { state.deepFor = ''; }   // edited while it ran: the result is for older code
  }).catch(function () {}).then(function () { state.busy = false; paintPill(); });
}
function deepSoon(ms) { clearTimeout(deepTimer); deepTimer = setTimeout(function () { if (!M.isRendering()) deep(); }, ms); }

/* called by app.js after every edit */
function edited() {
  var code = M.getCode(), grew = code.length - state.lastLen;
  state.lastLen = code.length;
  clearTimeout(quickTimer); quickTimer = setTimeout(quick, 450);
  state.deep = state.deepFor === code ? state.deep : state.deep;     // kept until the code changes
  if (grew >= 80 || state.lastCode === '') { state.wantDeep = true; }   // a paste, or the first code in an empty editor
  paintPill();
}
function opened() { state.wantDeep = true; state.lastLen = M.getCode().length; clearTimeout(quickTimer); quickTimer = setTimeout(quick, 100); }

/* Install a missing package. The page sends only the code and which import to install; the server works out the package name itself. */
function installPkg(which) {
  var missing = issuesNow().filter(function (i) { return i.kind === 'package' && (which === '*' || i.module === which); });
  if (!missing.length || state.pkg.running) return;
  var odd = missing.filter(function (i) { return !i.known; });
  if (odd.length && !window.confirm(odd.map(function (i) { return i.package; }).join(', ') + ' is not on Manimo\'s list of known libraries.\n\nAnyone can publish a package under any name, and an AI can invent one. Install it only if you know what it is.\n\nInstall anyway?')) return;
  state.pkg = { running: true, step: 'Starting...', error: '' }; paintPill();
  M.api('/api/packages/install', { code: M.getCode(), only: missing.map(function (i) { return i.module; }), confirm_unknown: odd.length > 0 }).then(function () { pollPkg(); })
    .catch(function (e) { state.pkg = { running: false, step: '', error: e.message }; paintPill(); });
}
function pollPkg() {
  fetch('/api/packages').then(function (r) { return r.json(); }).then(function (s) {
    if (s.state === 'running') { state.pkg.step = s.step; paintPill(); setTimeout(pollPkg, 900); return; }
    state.pkg = { running: false, step: '', error: s.state === 'error' ? s.error : '' };
    if (s.state === 'done') M.toast('Installed ' + s.packages.join(', '));
    state.wantDeep = true; quick();
  }).catch(function () { state.pkg = { running: false, step: '', error: 'Lost contact with Manimo.' }; paintPill(); });
}

pill.addEventListener('click', function () { panel.hidden = !panel.hidden; paintPill(); });
panel.addEventListener('click', function (e) {
  if (e.target.closest('#chkClose')) { panel.hidden = true; paintPill(); return; }
  if (e.target.closest('#chkDeep')) { deep(); return; }
  var pb = e.target.closest('[data-pkg]'); if (pb) { installPkg(pb.dataset.pkg); return; }
  var b = e.target.closest('[data-line]'); if (b && M.jumpToLine) M.jumpToLine(parseInt(b.dataset.line, 10));
});
document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) { panel.hidden = true; paintPill(); } });

window.MGXCheck = { edited: edited, opened: opened, deep: deep, issues: issuesNow };
if (M.getCode().trim()) opened();
})();
