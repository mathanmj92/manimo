/* Plan as cards: the assistant's plan opens as editable cards (name, what the viewer sees, narration) before any code is written.
   "Write one scene at a time" asks for each scene separately, so a problem in scene 4 redoes only scene 4, not the whole file. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('planDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc;
var plan = null, run = null;

/* ---------- reading and showing the plan ---------- */
function open(text) {
  M.api('/api/scenes', { op: 'plan', text: text }).then(function (p) {
    if (!p.scenes.length) { M.toast('Could not read the scenes from that plan. Edit it in the chat instead.'); return; }
    plan = p; paint(); dlg.showModal();
  }).catch(function (e) { M.toast(e.message); });
}
function paint() {
  $('pcTitle').value = plan.title; $('pcFor').value = plan.audience; $('pcLook').value = plan.look;
  var n = plan.scenes.length;
  $('pcList').innerHTML = plan.scenes.map(function (s, i) {
    return '<li class="pc-card" data-i="' + i + '"><div class="pc-head"><span class="pc-n">' + (i + 1) + '</span>' +
      '<input class="input sm pc-name" data-f="name" value="' + esc(s.name) + '" aria-label="Name of scene ' + (i + 1) + '" spellcheck="false">' +
      '<button class="icon-btn sm" data-a="up" aria-label="Move earlier"' + (i === 0 ? ' disabled' : '') + '><span aria-hidden="true">&uarr;</span></button>' +
      '<button class="icon-btn sm" data-a="down" aria-label="Move later"' + (i === n - 1 ? ' disabled' : '') + '><span aria-hidden="true">&darr;</span></button>' +
      '<button class="icon-btn sm" data-a="del" aria-label="Delete scene ' + (i + 1) + '"' + (n === 1 ? ' disabled' : '') + '><svg class="ic sm"><use href="#i-trash"/></svg></button></div>' +
      '<label class="pc-l">What the viewer sees<textarea class="input" data-f="sees" rows="2" spellcheck="true">' + esc(s.sees) + '</textarea></label>' +
      '<label class="pc-l">Narration (spoken)<textarea class="input" data-f="narration" rows="2" spellcheck="true">' + esc(s.narration) + '</textarea></label></li>';
  }).join('');
  $('pcCount').textContent = n + (n === 1 ? ' scene' : ' scenes');
}
$('pcList').addEventListener('input', function (e) {
  var li = e.target.closest('.pc-card'), f = e.target.dataset.f; if (!li || !f) return;
  plan.scenes[+li.dataset.i][f] = e.target.value;
});
$('pcList').addEventListener('click', function (e) {
  var b = e.target.closest('[data-a]'); if (!b) return;
  var i = +b.closest('.pc-card').dataset.i, a = b.dataset.a, sc = plan.scenes;
  if (a === 'del' && sc.length > 1) sc.splice(i, 1);
  else if (a === 'up' && i > 0) sc.splice(i - 1, 0, sc.splice(i, 1)[0]);
  else if (a === 'down' && i < sc.length - 1) sc.splice(i + 1, 0, sc.splice(i, 1)[0]);
  paint();
  var again = $('pcList').querySelector('.pc-card[data-i="' + (a === 'up' ? i - 1 : a === 'down' ? i + 1 : Math.min(i, sc.length - 1)) + '"] [data-a="' + (a === 'del' ? 'down' : a) + '"]'); if (again && !again.disabled) again.focus();
});
$('pcAdd').addEventListener('click', function () {
  plan.scenes.push({ name: 'New scene', sees: '', narration: '' }); paint();
  var last = $('pcList').lastElementChild; if (last) { last.scrollIntoView({ block: 'nearest' }); last.querySelector('.pc-name').select(); }
});
['pcTitle', 'pcFor', 'pcLook'].forEach(function (id) { $(id).addEventListener('input', function () { plan[{ pcTitle: 'title', pcFor: 'audience', pcLook: 'look' }[id]] = this.value; }); });

/* ---------- the plan as text, and the requests ---------- */
function className(label, taken) {
  var base = (String(label).match(/[A-Za-z0-9]+/g) || []).map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join('').slice(0, 40) || 'Scene';
  if (/^\d/.test(base)) base = 'Scene' + base;
  var name = base, n = 2; while (taken.indexOf(name) >= 0) name = base + (n++);
  return name;
}
function sceneLine(s, i, cls) { return (i + 1) + '. ' + (cls || s.name) + ' - ' + (s.sees || s.name) + (s.narration ? ' Narration: ' + s.narration : ''); }
function planText() {
  var names = [], lines = ['Title: ' + plan.title, 'For: ' + plan.audience, 'Look: ' + plan.look, 'Scenes:'];
  plan.scenes.forEach(function (s, i) { var c = className(s.name, names); names.push(c); lines.push(sceneLine(s, i, c)); });
  return lines.join('\n');
}
function writeAll() {
  dlg.close();
  M.sendAI({ text: 'The plan below is approved. Write the complete scene file: one scene class for each planned scene, in order, with its narration, following the plan exactly.\n\n' + planText(), noSolve: true });
}

/* one scene per request; each finished scene is put in the editor before the next is asked for */
function step() {
  var i = run.i, s = plan.scenes[i], cls = run.names[i], first = i === 0;
  M.toast('Writing scene ' + (i + 1) + ' of ' + plan.scenes.length + ': ' + s.name);
  var head = 'Lesson plan (approved):\n' + planText() + '\n\n';
  var text = first
    ? head + 'Write the file for scene 1 only: the imports and the class ' + cls + '. Do not write the other scenes yet.'
    : head + 'The file already has scenes 1 to ' + i + '. Add scene ' + (i + 1) + ' as a new class ' + cls + ' at the end of the file, exactly as planned. Keep every existing scene unchanged. Return the complete file.';
  M.sendAI({ text: text, noSolve: true, fresh: first, keep: !first, mode: first ? 'write' : 'edit' });
}
function writeSeries() {
  if (M.getCode().trim() && !window.confirm('This replaces the code in the editor with the new lesson. Undo with Ctrl+Z.\n\nContinue?')) return;
  var names = []; plan.scenes.forEach(function (s) { names.push(className(s.name, names)); });
  run = { i: 0, names: names, scenes: plan.scenes.length };
  dlg.close(); step();
}
function stop(msg) { run = null; if (msg) M.toast(msg); }
/* called by the assistant when a request ends; idx is the position of its reply */
function finished(idx) {
  if (!run) return;
  var m = M.aiMsgs()[idx], n = run.scenes, i = run.i;
  if (!m || m.error || !m.code) { stop('Stopped at scene ' + (i + 1) + ' of ' + n + '. ' + (m && m.error ? m.error : 'No code came back.') + ' Ask again from the chat; the earlier scenes are in the editor.'); return; }
  M.applyAI(idx, false);
  var r = m.report;
  if (r && r.clean === false) { stop('Scene ' + (i + 1) + ' of ' + n + ' still has problems after the assistant’s own checks. Use “Ask the assistant to fix these”, then ask for the next scene.'); return; }
  if (i + 1 >= n) {
    stop(); M.toast('All ' + n + ' scenes are written. Opening the storyboard.');
    if (window.MGXBoard) window.MGXBoard.show(true);
    return;
  }
  run.i = i + 1; setTimeout(function () { if (run) step(); }, 500);
}

$('pcAll').addEventListener('click', writeAll);
$('pcSeries').addEventListener('click', writeSeries);
$('pcCancel').addEventListener('click', function () { dlg.close(); });

window.MGXPlan = { open: open, finished: finished, running: function () { return !!run; }, stop: stop };
})();
