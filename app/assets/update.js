/* Updates: looks for a newer Manimo on GitHub, downloads it in the background, and offers to install it.
   Nothing is installed without a click. Settings has two switches (check automatically, download automatically). */
(function () {
'use strict';
var M = window.MANIMO, bar = document.getElementById('updBar');
if (!M || !bar) return;
var $ = M.$, esc = M.esc, poll = null, st = null;
var live = M.TOKEN && M.TOKEN.indexOf('__') !== 0;

function mb(n) { return n ? (n / 1048576).toFixed(0) + ' MB' : ''; }
function paint() {
  var s = st; if (!s) { bar.hidden = true; return; }
  var v = s.latest, html = '';
  if (s.phase === 'available') {
    html = '<span><b>Manimo ' + esc(v) + ' is available.</b> You have ' + esc(s.current) + (s.asset ? ' (' + mb(s.asset.size) + ' download).' : '.') + '</span>' +
      '<span class="upd-acts"><button class="btn sm primary" id="updGet">Download</button><button class="btn sm ghost" id="updSkip">Skip this version</button><button class="icon-btn" id="updHide" aria-label="Hide"><svg class="ic"><use href="#i-x"/></svg></button></span>';
  } else if (s.phase === 'downloading') {
    html = '<span><b>Downloading Manimo ' + esc(v) + '…</b> ' + Math.floor(s.percent || 0) + '%</span><span class="upd-prog"><i style="transform:scaleX(' + ((s.percent || 0) / 100) + ')"></i></span>' +
      '<span class="upd-acts"><button class="btn sm ghost" id="updCancel">Cancel</button></span>';
  } else if (s.phase === 'ready') {
    html = '<span><b>Manimo ' + esc(v) + ' is ready to install.</b> It was checked against its published checksum. Manimo closes while it installs, and your code is kept.</span>' +
      '<span class="upd-acts"><button class="btn sm primary" id="updInstall">Install and restart</button><button class="icon-btn" id="updHide" aria-label="Hide"><svg class="ic"><use href="#i-x"/></svg></button></span>';
  }
  if (s.error && (s.phase === 'available' || s.phase === 'idle')) html = '<span class="upd-err">' + esc(s.error) + '</span><span class="upd-acts"><button class="icon-btn" id="updHide" aria-label="Hide"><svg class="ic"><use href="#i-x"/></svg></button></span>' + (html ? '' : '');
  bar.hidden = !html; bar.innerHTML = html;
  bar.className = 'upd-bar' + (s.phase === 'ready' ? ' ready' : '');
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
  if (id === 'updGet') download();
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
