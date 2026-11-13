/* Ask about one scene: explain it, make it easier, harder or shorter, or compare two takes of it side by side and keep the one you like.
   Only the scene's own code is sent as the focus, and the assistant is told to change nothing else. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('takeDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc;
var run = null, cur = null;

var EDITS = {
  easier: 'Make the scene NAME easier to follow for students: simpler words in the narration, one idea at a time, and a little slower.',
  harder: 'Make the scene NAME deeper for stronger students: add the next step of reasoning, or a short check at the end.',
  shorter: 'Make the scene NAME about a third shorter: keep the key idea, drop repetition and anything a viewer does not need.'
};
var KEEP = ' Change only the class NAME. Keep its name and every other scene exactly as it is. Return the complete file.';

function blockOf(sc) { return M.getCode().split('\n').slice(sc.start - 1, sc.end).join('\n'); }
function sub(t, name) { return t.replace(/NAME/g, name); }

function ask(kind, sc) {
  if (!M.aiReady()) { M.toast('Set up an AI first (Settings, AI assistant).'); M.openAI(); return; }
  if (kind === 'takes') { openTakes(sc); return; }
  M.rightTab('assistant');
  if (kind === 'explain') {
    M.sendAI({ mode: 'explain', text: 'Explain the scene ' + sc.name + ' in plain language for someone who does not know Python: what the viewer sees, in order, and why each step is there.', selection: blockOf(sc), noSolve: true, keep: true });
  } else if (EDITS[kind]) {
    M.sendAI({ mode: 'edit', text: sub(EDITS[kind] + KEEP, sc.name), selection: blockOf(sc), noSolve: true, keep: true });
  }
}

/* ---------- two takes ---------- */
function openTakes(sc) {
  cur = sc; run = null;
  $('takeTitle').textContent = 'Compare two takes of ' + sc.name;
  $('takeAsk').value = $('takeAsk').value || 'Show this scene a different way that is clearer for students.';
  $('takeAskRow').hidden = false; $('takeStatus').textContent = ''; $('takeCols').innerHTML = ''; $('takeGo').disabled = false;
  dlg.showModal(); $('takeAsk').focus();
}
function prompt(i) {
  var req = $('takeAsk').value.trim(), n = cur.name;
  return (i === 0 ? 'Rewrite the scene ' + n + ' as asked: ' + req + ' Keep the overall approach of the current scene, but improve it.'
                  : 'Rewrite the scene ' + n + ' as asked: ' + req + ' Use a clearly different visual approach from the current scene (a different layout or picture), so it can be compared.') + KEEP.replace(/NAME/g, n);
}
function step() {
  $('takeStatus').textContent = 'Writing take ' + (run.i + 1) + ' of 2…';
  M.sendAI({ mode: 'edit', text: prompt(run.i), selection: blockOf(cur), noSolve: true, keep: true });
}
$('takeGo').addEventListener('click', function () {
  if (!$('takeAsk').value.trim()) { $('takeStatus').textContent = 'Say what should be different.'; return; }
  this.disabled = true; $('takeAskRow').hidden = true;
  run = { i: 0, takes: [] }; step();
});
function stop(msg) { run = null; $('takeStatus').textContent = msg || ''; $('takeGo').disabled = false; $('takeAskRow').hidden = false; }
function finished(idx) {
  if (!run) return;
  var m = M.aiMsgs()[idx];
  if (!m || m.error || !m.code) { stop('Take ' + (run.i + 1) + ' failed. ' + (m && m.error ? m.error : 'No code came back.') + ' Try again.'); return; }
  run.takes.push({ code: m.code, clean: !m.report || m.report.clean !== false });
  if (run.i === 0) { run.i = 1; setTimeout(function () { if (run) step(); }, 400); return; }
  var takes = run.takes; run = null; show(takes);
}

function col(title, note, code, name, keep) {
  return '<section class="tk-col"><h3>' + esc(title) + '</h3><div class="tk-img" data-img><span class="help">Looking…</span></div><p class="help tk-note" data-note>' + esc(note || '') + '</p>' +
    '<details><summary>Show the code</summary><pre class="tk-code">' + esc(code) + '</pre></details>' + (keep ? '<button class="btn sm primary" data-keep="' + keep + '" type="button">Keep ' + esc(title.toLowerCase()) + '</button>' : '<span class="help">What you have now</span>') + '</section>';
}
function show(takes) {
  $('takeStatus').textContent = 'Looking at each one…';
  $('takeCols').innerHTML = col('Now', '', M.getCode().split('\n').slice(cur.start - 1, cur.end).join('\n'), cur.name, '') + col('Take A', takes[0].clean ? '' : 'Still has problems after the assistant’s own checks.', blockFrom(takes[0].code), cur.name, 'a') + col('Take B', takes[1].clean ? '' : 'Still has problems after the assistant’s own checks.', blockFrom(takes[1].code), cur.name, 'b');
  cur.takes = takes;
  var cols = $('takeCols').querySelectorAll('.tk-col'), codes = [M.getCode(), takes[0].code, takes[1].code], i = 0;
  (function next() {
    if (i >= 3) { $('takeStatus').textContent = 'Pick one to keep, or close this to keep what you have.'; return; }
    var c = cols[i], k = i; i++;
    M.api('/api/scene-preview', { code: codes[k], scene: cur.name }).then(function (r) {
      c.querySelector('[data-img]').innerHTML = r.image ? '<img src="' + esc(r.image) + '" alt="Frames of ' + esc(cur.name) + ', ' + (k ? 'take ' + 'AB'[k - 1] : 'now') + '">' : '<span class="help">No picture</span>';
      var bits = []; if (r.seconds) bits.push(Math.round(r.seconds) + ' s'); if (r.plays) bits.push(r.plays + ' animations');
      if (r.error) bits.push('Problem: ' + r.error); else if (r.problems && r.problems.length) bits.push(r.problems.length + ' layout ' + (r.problems.length === 1 ? 'note' : 'notes'));
      var n = c.querySelector('[data-note]'); n.textContent = (n.textContent ? n.textContent + ' ' : '') + bits.join(' · ');
    }).catch(function (e) { c.querySelector('[data-img]').innerHTML = '<span class="help">' + esc(e.message) + '</span>'; }).then(next);
  })();
}
function blockFrom(code) {
  var m = new RegExp('^class\\s+' + cur.name + '\\b[\\s\\S]*?(?=^class\\s|$(?![\\s\\S]))', 'm').exec(code);       // up to the next class, or the end of the text
  return m ? m[0].trimEnd() : '';
}
$('takeCols').addEventListener('click', function (e) {
  var b = e.target.closest('[data-keep]'); if (!b || !cur || !cur.takes) return;
  var take = cur.takes[b.dataset.keep === 'a' ? 0 : 1];
  M.api('/api/scenes', { code: M.getCode(), op: 'replace', name: cur.name, take: take.code }).then(function (r) {
    M.applyCode(r.code); dlg.close(); M.toast('Kept take ' + b.dataset.keep.toUpperCase() + ' for ' + cur.name + '. Undo with Ctrl+Z.');
  }).catch(function (er) { $('takeStatus').textContent = er.message; });
});

window.MGXTakes = { ask: ask, finished: finished, running: function () { return !!run; }, stop: function (m) { stop(m); } };
})();
