/* Quick start: three steps shown once under the toolbar. Each ticks itself; Skip hides it for good; Help, Show the quick start brings it back. */
(function () {
'use strict';
var M = window.MANIMO, box = document.getElementById('qsStrip');
if (!M || !box) return;
var esc = M.esc, KEY = 'mgx-quickstart';
var st = { hide: false, code: false, ai: false, render: false };
try { Object.assign(st, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}
function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }

function step(n, done, title, body) {
  return '<li class="qs-step' + (done ? ' done' : '') + '"><span class="qs-n" aria-hidden="true">' + (done ? '✓' : n) + '</span><div><b>' + esc(title) + (done ? '<span class="sr-only"> (done)</span>' : '') + '</b><span class="qs-b">' + body + '</span></div></li>';
}
function paint() {
  if (st.hide) { box.hidden = true; return; }
  if (M.getCode().trim()) st.code = true;
  if (M.aiReady()) st.ai = true;
  var all = st.code && st.ai && st.render;
  box.hidden = false;
  box.innerHTML = '<ol class="qs-steps">' +
    step(1, st.code, 'Get some code', st.code ? 'Your code is in the editor.' : '<button class="linkbtn" data-qs="prompt">Prompt library</button> · <button class="linkbtn" data-qs="paste">Paste code</button> · <button class="linkbtn" data-qs="example">Try an example</button>') +
    step(2, st.ai, 'Connect an AI (optional)', st.ai ? 'The assistant is ready.' : '<button class="linkbtn" data-qs="ai">Set it up</button> · <button class="linkbtn" data-qs="noai">Not now</button>') +
    step(3, st.render, 'Render your first video', st.render ? 'Your video is in the preview.' : '<button class="linkbtn" data-qs="render">Start rendering</button> (Ctrl+Enter)') +
    '</ol>' + (all ? '<span class="qs-done" role="status">You are set. Find this again in Help.</span>' : '') +
    '<button class="btn ghost sm" data-qs="skip">' + (all ? 'Close' : 'Skip') + '</button>';
  save();
  if (all) setTimeout(function () { st.hide = true; save(); box.hidden = true; }, 6000);
}
box.addEventListener('click', function (e) {
  var b = e.target.closest('[data-qs]'); if (!b) return;
  var a = b.dataset.qs;
  if (a === 'prompt') M.openPrompt();
  else if (a === 'paste') M.pasteCode();
  else if (a === 'example') M.tryExample();
  else if (a === 'ai') M.openAI();
  else if (a === 'noai') { st.ai = true; paint(); }
  else if (a === 'render') document.getElementById('startBtn').click();
  else if (a === 'skip') { st.hide = true; save(); box.hidden = true; }
});
var ai = document.getElementById('aiDlg'); if (ai) ai.addEventListener('close', function () { setTimeout(paint, 600); });

window.MGXQuick = {
  changed: function () { if (!st.hide && !st.code && M.getCode().trim()) paint(); },
  rendered: function () { if (!st.render) { st.render = true; paint(); } },
  show: function () { st.hide = false; paint(); }
};
setTimeout(paint, 800);       // after the app has loaded its saved code and the assistant's status
})();
