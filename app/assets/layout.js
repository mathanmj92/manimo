/* The VS Code layout's two extra bars: the activity bar (open a view) and the status bar (what is happening, and shortcuts).
   Both are plain buttons that press the page's existing controls, so every layout does the same things. */
(function () {
'use strict';
var M = window.MANIMO, bar = document.getElementById('actBar'), sb = document.getElementById('statusBar');
if (!M || !bar || !sb) return;
var $ = M.$;

var ACT = {
  proj: function () { $('projBtn').click(); },
  ai: function () { $('aiBtn').click(); },
  prompt: function () { if (window.MGXPrompt) window.MGXPrompt.open(); },
  videos: function () { if (window.MGXLibrary) window.MGXLibrary.open(); },
  voice: function () { M.openSettings('voice'); },
  settings: function () { $('settingsBtn').click(); }
};
bar.addEventListener('click', function (e) { var b = e.target.closest('[data-act]'); if (b && ACT[b.dataset.act]) ACT[b.dataset.act](); });

var SB = {
  sbEngine: function () { $('enginePill').click(); },
  sbQuality: function () { $('settingsBtn').click(); },
  sbVoice: function () { M.openSettings('voice'); },
  sbProblems: function () { $('checkPill').click(); },
  sbUpdate: function () { var c = document.getElementById('updOpen'); if (c) c.click(); }
};
sb.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b && SB[b.id]) SB[b.id](); });

function text(id) { var e = $(id); return e ? e.textContent.trim() : ''; }
function paint() {
  if (document.getElementById('app').dataset.layout !== 'vscode') return;
  bar.querySelector('[data-act=proj]').classList.toggle('on', $('projBtn').getAttribute('aria-pressed') === 'true');
  bar.querySelector('[data-act=ai]').classList.toggle('on', $('aiBtn').getAttribute('aria-pressed') === 'true');
  $('sbEngine').textContent = text('engineText') || 'Engine';
  $('sbQuality').textContent = text('qualityLbl');
  var name = M.voiceName();
  $('sbVoice').textContent = name ? 'Voice: ' + name : '';
  $('sbVoice').hidden = !name;
  var pill = $('checkPill'), pb = $('sbProblems'); pb.hidden = pill.hidden; if (!pill.hidden) pb.textContent = pill.textContent;
  var upd = $('updBar'), ub = $('sbUpdate'), chip = document.getElementById('updOpen');
  ub.hidden = upd.hidden || !chip; if (chip) ub.textContent = chip.textContent;
  $('sbPos').textContent = text('pos');
}
setInterval(paint, 500);
paint();
})();
