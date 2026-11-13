/* Command palette (Ctrl+K): type a few letters to find and run any menu command. "?" opens the keyboard shortcuts. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('palDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc, input = $('palInput'), list = $('palList'), count = $('palCount');
var GROUPS = [['file', 'File'], ['edit', 'Edit'], ['view', 'View'], ['session', 'Session'], ['help', 'Help']];
var all = [], shown = [], sel = 0;

function collect() {
  var out = [{ label: 'Start rendering', group: 'Render', key: 'Ctrl+Enter', run: function () { $('startBtn').click(); } },
             { label: 'Check the layout', group: 'Code', key: '', run: function () { if (window.MGXCheck) window.MGXCheck.deep(); } },
             { label: 'Settings', group: 'View', key: '', run: function () { M.openSettings(); } }];
  GROUPS.forEach(function (g) {
    var head = '';
    M.menuItems(g[0]).forEach(function (it) {
      if (it.head) { head = /^(Layout|Interface size|Examples|Recent renders)$/.test(it.head) ? it.head : ''; return; }
      if (it.sep) { head = ''; return; }
      if (!it.run || it.disabled || /^Find a command/.test(it.label)) return;
      var label = it.label.replace(/^[✓ \s]+/, '');
      out.push({ label: head && head !== 'Examples' && head !== 'Recent renders' ? head + ': ' + label : label, group: g[1], key: it.key || '', run: it.run });
    });
  });
  return out;
}

/* higher is better; -1 means no match. Every word typed must appear in the text; a match at the start of the label or of a word ranks first. */
function score(q, text) {
  if (!q) return 0;
  var t = text.toLowerCase(), total = 0, words = q.split(/\s+/);
  for (var k = 0; k < words.length; k++) {
    var i = t.indexOf(words[k]);
    if (i < 0) return -1;
    total += i === 0 ? 300 : (t[i - 1] === ' ' || t[i - 1] === ':' ? 200 : 100) - Math.min(i, 90);
  }
  return total / words.length;
}

function paint() {
  var q = input.value.trim().toLowerCase();
  shown = all.map(function (it) { return { it: it, s: Math.max(score(q, it.label), score(q, it.group + ' ' + it.label) - 1) }; })
             .filter(function (x) { return x.s >= 0; });
  if (q) shown.sort(function (a, b) { return b.s - a.s; });
  shown = shown.slice(0, 40).map(function (x) { return x.it; });
  sel = Math.min(sel, Math.max(0, shown.length - 1));
  list.innerHTML = shown.length ? shown.map(function (it, i) {
    return '<li class="pal-item" role="option" id="pal-' + i + '" data-i="' + i + '" aria-selected="' + (i === sel) + '"><span class="pal-g">' + esc(it.group) + '</span><span class="pal-t">' + esc(it.label) + '</span>' + (it.key ? '<kbd>' + esc(it.key) + '</kbd>' : '') + '</li>';
  }).join('') : '<li class="pal-none">Nothing matches. Try another word.</li>';
  input.setAttribute('aria-activedescendant', shown.length ? 'pal-' + sel : '');
  count.textContent = shown.length + (shown.length === 1 ? ' command' : ' commands');
  var cur = list.querySelector('[aria-selected="true"]'); if (cur) cur.scrollIntoView({ block: 'nearest' });
}

function open() {
  if (dlg.open) return;
  M.closeMenus();
  all = collect(); sel = 0; input.value = '';
  dlg.showModal(); paint(); input.focus();
}
function run(i) {
  var it = shown[i]; if (!it) return;
  dlg.close();
  setTimeout(it.run, 0);          // after the dialog has closed, so a command that opens another dialog works
}

input.addEventListener('input', function () { sel = 0; paint(); });
input.addEventListener('keydown', function (e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); sel = (sel + 1) % Math.max(1, shown.length); paint(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); sel = (sel - 1 + shown.length) % Math.max(1, shown.length); paint(); }
  else if (e.key === 'Enter') { e.preventDefault(); run(sel); }
});
list.addEventListener('click', function (e) { var li = e.target.closest('[data-i]'); if (li) run(parseInt(li.dataset.i, 10)); });
list.addEventListener('mousemove', function (e) { var li = e.target.closest('[data-i]'); if (li && +li.dataset.i !== sel) { sel = +li.dataset.i; paint(); } });
dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });

/* capture phase, so the shortcut works while the cursor is in the code editor */
document.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k') { e.preventDefault(); e.stopPropagation(); open(); return; }
  if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    var t = e.target;
    if (t.closest && t.closest('input, textarea, select, [contenteditable="true"], .cm-editor')) return;   // typing a question mark
    if (document.querySelector('dialog[open]')) return;
    e.preventDefault(); M.openDialog('helpDlg'); var l = $('shortcutList'); if (l) l.scrollIntoView({ block: 'start' });
  }
}, true);

window.MGXPalette = { open: open, score: score };
})();
