/* Updates: looks for a newer Manimo on GitHub, downloads it in the background, and offers to install it.
   Nothing is installed without a click. Settings has two switches (check automatically, download automatically). */
(function () {
'use strict';
var M = window.MANIMO, bar = document.getElementById('updBar');
if (!M || !bar) return;
var $ = M.$, esc = M.esc, poll = null, st = null;
var live = M.TOKEN && M.TOKEN.indexOf('__') !== 0;

function mb(n) { return n ? (n / 1048576).toFixed(0) + ' MB' : ''; }
var folded = false, foldedFor = '';          // "Run in background": the card folds to a small chip; the download carries on
function xbtn(id, label) { return '<button class="icon-btn" id="' + id + '" aria-label="' + label + '" title="' + label + '"><svg class="ic"><use href="#i-x"/></svg></button>'; }
function paint() {
  var s = st; if (!s) { bar.hidden = true; return; }
  var v = s.latest, html = '', chip = '', key = s.phase + ':' + v;
  if (key !== foldedFor && s.phase !== 'downloading') folded = false;      // a new stage deserves a look
  if (s.phase === 'available') {
    html = '<div class="upd-top"><b>Manimo ' + esc(v) + ' is available</b>' + xbtn('updHide', 'Close') + '</div><p>You have ' + esc(s.current) + (s.asset ? '. The download is ' + mb(s.asset.size) + '.' : '.') + '</p>' +
      '<div class="upd-acts"><button class="btn sm primary" id="updGet">Download</button><button class="btn sm ghost" id="updSkip">Skip this version</button></div>';
  } else if (s.phase === 'downloading') {
    var pc = Math.floor(s.percent || 0);
    html = '<div class="upd-top"><b>Downloading Manimo ' + esc(v) + '</b><span class="upd-pc">' + pc + '%</span></div><div class="upd-prog"><i style="transform:scaleX(' + (pc / 100) + ')"></i></div>' +
      '<p>You can keep working. It checks the file when it finishes.</p><div class="upd-acts"><button class="btn sm" id="updFold">Run in background</button><button class="btn sm ghost" id="updCancel">Cancel</button></div>';
    chip = 'Downloading update ' + pc + '%';
  } else if (s.phase === 'ready') {
    html = '<div class="upd-top"><b>Manimo ' + esc(v) + ' is ready</b>' + xbtn('updFold', 'Later') + '</div><p>Checked against its published checksum. Manimo closes while it installs, and your code is kept.</p>' +
      '<div class="upd-acts"><button class="btn sm primary" id="updInstall">Install and restart</button><button class="btn sm ghost" id="updFold">Later</button></div>';
    chip = 'Update ready to install';
  }
  if (s.error && (s.phase === 'available' || s.phase === 'idle')) html = '<div class="upd-top"><b>Update problem</b>' + xbtn('updHide', 'Close') + '</div><p class="upd-err">' + esc(s.error) + '</p>', chip = '';
  if (!html) { bar.hidden = true; return; }
  bar.hidden = false;
  if (folded && chip) { bar.className = 'upd-pop folded'; bar.innerHTML = '<button class="upd-chip" id="updOpen">' + esc(chip) + '</button>'; }
  else { bar.className = 'upd-pop' + (s.phase === 'ready' ? ' ready' : ''); bar.innerHTML = html; }
}
function apply(s) { st = s; paint(); fillSettings(); if (s.phase === 'downloading' && !poll) poll = setInterval(refresh, 800); if (s.phase !== 'downloading' && poll) { clearInterval(poll); poll = null; } }
function refresh() { return M.api('/api/update/status', {}).then(apply).catch(function () {}); }

function check(force) {
  if (!live) return Promise.resolve();
  return M.api('/api/update/check', { force: !!force }).then(function (s) {
    apply(s);
    if (s.phase === 'available' && s.settings && s.settings.auto_download && !force) return download();
    if (force && s.phase === 'idle' && !s.error) M.toast('Manimo ' + s.current + ' is up to date.');
    if (force && s.error) M.toast(s.error);
  }).catch(function () { if (force) M.toast('Could not check for updates.'); });
}
function download() { return M.api('/api/update/download', {}).then(refresh).catch(function (e) { M.toast(e.message); }); }

bar.addEventListener('click', function (e) {
  var id = (e.target.closest('button') || {}).id;
  if (id === 'updFold') { folded = true; foldedFor = (st.phase + ':' + st.latest); paint(); }
  else if (id === 'updOpen') { folded = false; paint(); }
  else if (id === 'updGet') download();
  else if (id === 'updCancel') M.api('/api/update/cancel', {}).then(refresh);
  else if (id === 'updHide') { bar.hidden = true; }
  else if (id === 'updSkip') M.api('/api/update/skip', { version: st.latest }).then(apply);
  else if (id === 'updInstall') {
    if (M.isRendering()) { M.toast('A render is running. Install the update when it finishes.'); return; }
    M.api('/api/update/install', {}).then(function () { M.toast('Starting the installer…'); setTimeout(function () { M.api('/api/quit', {}).catch(function () {}); }, 1200); }).catch(function (e) { M.toast(e.message); });
  }
});

/* Settings: Files and engines > Updates */
function fillSettings() {
  var a = $('updAuto'), d = $('updDown'); if (!a || !st || !st.settings) return;
  a.checked = !!st.settings.auto_check; d.checked = !!st.settings.auto_download; d.disabled = !a.checked;
  $('updNow').disabled = false; $('updVer').textContent = 'Version ' + (st.current || '');
}
function wireSettings() {
  var a = $('updAuto'), d = $('updDown'), n = $('updNow'); if (!a) return;
  a.addEventListener('change', function () { M.api('/api/update/settings', { auto_check: a.checked }).then(refresh); });
  d.addEventListener('change', function () { M.api('/api/update/settings', { auto_download: d.checked }).then(refresh); });
  n.addEventListener('click', function () { n.disabled = true; check(true).then(function () { n.disabled = false; }); });
}
wireSettings();

window.MGXUpdate = { check: function () { return check(true); } };
if (live) setTimeout(function () { M.api('/api/update/status', {}).then(function (s) { apply(s); if (s.settings.auto_check) check(false); }).catch(function () {}); }, 5000);
})();
