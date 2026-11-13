/* Narration studio: every spoken line of the lesson as a row you can read, change and hear; a voice and speed for the lesson and for each
   scene; pronunciations; and the assistant rewriting the spoken words (shorter, simpler) without touching the code.
   Everything is saved as ordinary text in the lesson's file (the quoted words in self.say, and # voice / # speed / # say comments). */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('narrDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc;

var st = { lines: [], settings: {}, pron: { pairs: [], defaults: true, builtin: [] }, scene: '', timing: {}, busy: false, timer: null, tseq: 0 };
var saveTimer = null, pending = {};

function call(body) { return M.api('/api/narration', Object.assign({ code: M.getCode() }, body)); }
function msg(t, bad) { var n = $('nrMsg'); n.textContent = t || ''; n.classList.toggle('bad', !!bad); }
function sceneNames() { var seen = []; st.lines.forEach(function (l) { if (seen.indexOf(l.scene) < 0) seen.push(l.scene); }); return seen; }
function rowsOf(scene) { return st.lines.filter(function (l) { return l.scene === scene; }); }

/* ---------- loading ---------- */
function absorb(r) {
  st.lines = r.lines; st.settings = r.settings; st.pron = r.pron;
  var names = sceneNames();
  if (names.indexOf(st.scene) < 0) st.scene = names[0] || '';
}
function load() {
  return call({ op: 'lines' }).then(function (r) { absorb(r); paint(); measure(); }).catch(function (e) { st.lines = []; paint(); msg(e.message, true); });
}
function open() {
  var v = M.lessonVoice(), vs = M.voices();
  $('nrVoice').innerHTML = M.voiceOptions(vs, true); $('nrVoice').value = v.id; $('nrSpeed').value = v.speed; $('nrSpeedOut').textContent = (+v.speed).toFixed(2).replace(/0$/, '') + 'x';
  $('nrVoice').disabled = $('nrSpeed').disabled = $('nrSample').disabled = !vs.length;
  msg(vs.length ? '' : 'The narration voice is not installed in this copy of Manimo, so lines cannot be played.', !vs.length);
  dlg.showModal(); load();
}

/* ---------- timing (measured with the real voice) ---------- */
function measure() {
  clearTimeout(st.timer);
  var scene = st.scene; if (!scene || !rowsOf(scene).length) return;
  var mine = ++st.tseq, v = M.lessonVoice();
  st.timer = setTimeout(function () {
    M.api('/api/script', { code: M.getCode(), scene: scene, voice: v.id, speed: v.speed }).then(function (d) {
      if (mine !== st.tseq) return;
      st.timing[scene] = d; paintTiming();
    }).catch(function () { if (mine === st.tseq) { st.timing[scene] = null; paintTiming(); } });
  }, 500);
}
function words(t) { return t.replace(/[\[\]]/g, '').split(/\s+/).filter(Boolean).length; }
function warnFor(l, t) {
  var w = words(l.text), dur = t ? t.dur : w * 0.35 + 0.4, out = [];
  if (w > 40) out.push('Long line (' + w + ' words). Split it in two so viewers can follow.');
  if (t && t.anim && dur > 6 && dur / Math.max(t.anim, 0.5) >= 4) out.push('Written for a ' + t.anim.toFixed(1) + ' s animation, but it takes ' + dur.toFixed(1) + ' s to say, so the animation will play slowly. Shorten the line or give it more to show.');
  return out;
}
function paintTiming() {
  var t = st.timing[st.scene], rows = rowsOf(st.scene);
  rows.forEach(function (l, i) {
    var row = $('nrRows').querySelector('[data-n="' + l.n + '"]'); if (!row) return;
    var tl = t && t.lines && t.lines[i], est = !tl;
    var dur = tl ? tl.dur : words(l.text) * 0.35 + 0.4;
    row.querySelector('.nr-dur').textContent = (est ? '~' : '') + dur.toFixed(1) + ' s';
    var ws = warnFor(l, tl), b = row.querySelector('.nr-warn');
    b.hidden = !ws.length; b.title = ws.join(' '); b.setAttribute('aria-label', ws.join(' ')); row.classList.toggle('warn', !!ws.length);
    row.querySelector('.nr-why').textContent = ws.join(' ');
  });
  var total = t && t.end ? t.end : null;
  $('nrSceneBar').dataset.end = total ? total.toFixed(1) : '';
  var info = $('nrSceneBar').querySelector('.nr-end'); if (info) info.textContent = total ? 'The scene runs ' + total.toFixed(1) + ' s' + (t.estimated ? ' (estimated)' : '') : '';
}

/* ---------- painting ---------- */
function paint() {
  var names = sceneNames();
  $('nrScenes').hidden = names.length < 2;
  $('nrScenes').innerHTML = names.map(function (n) { return '<button type="button" data-scene="' + esc(n) + '" aria-pressed="' + (n === st.scene) + '">' + esc(n) + '</button>'; }).join('');
  if (!names.length) {
    $('nrSceneBar').innerHTML = ''; $('nrRows').innerHTML = '<li class="nr-empty"><b>No narration in this code yet</b><p>Narration is written in the code as <code>self.say("...")</code>. Ask the assistant for a narrated lesson, or add a line yourself.</p></li>';
  } else {
    var s = st.settings[st.scene] || {}, vs = M.voices();
    $('nrSceneBar').innerHTML = '<label class="pc-l">Voice for this scene<select class="input sm" id="nrSceneVoice"><option value="">Same as the lesson</option>' + M.voiceOptions(vs, false) + '</select></label>' +
      '<label class="pc-l">Speed for this scene<select class="input sm" id="nrSceneSpeed"><option value="">Same as the lesson</option>' + [0.8, 0.9, 1.0, 1.1, 1.2, 1.3].map(function (x) { return '<option value="' + x + '">' + x.toFixed(1) + 'x</option>'; }).join('') + '</select></label><span class="help nr-end" style="align-self:end"></span>';
    $('nrSceneVoice').value = s.voice || ''; $('nrSceneSpeed').value = s.speed == null ? '' : String(s.speed);
    $('nrSceneVoice').disabled = $('nrSceneSpeed').disabled = !vs.length;
    $('nrRows').innerHTML = rowsOf(st.scene).map(function (l) {
      return '<li class="nr-row" data-n="' + l.n + '"><button class="icon-btn" data-play aria-label="Hear this line" title="Hear this line"><svg class="ic sm"><use href="#i-play"/></svg></button>' +
        '<label class="nr-text"><span class="sr-only">Line ' + (l.n + 1) + ' of ' + esc(l.scene) + '</span><textarea class="input" rows="2" spellcheck="true" data-line="' + l.line + '">' + esc(l.text) + '</textarea></label>' +
        '<div class="nr-meta"><span class="nr-dur"></span><button class="nr-warn" type="button" hidden>!</button><button class="linkbtn" data-goto="' + l.line + '">Line ' + l.line + '</button></div><p class="help nr-why"></p></li>';
    }).join('');
  }
  paintPron();
  paintTiming();
}
function paintPron() {
  var p = st.pron;
  $('nrDefaults').checked = p.defaults; $('nrBuiltinCount').textContent = (p.builtin || []).length;
  $('nrPronCount').textContent = p.pairs.length ? '(' + p.pairs.length + ' in this lesson)' : '';
  $('nrPairs').innerHTML = p.pairs.map(pairRow).join('');
}
function pairRow(pr) {
  return '<li class="nr-pair"><input class="input sm" data-w value="' + esc(pr[0]) + '" aria-label="Written word" placeholder="Written, e.g. mu_k" spellcheck="false"><span aria-hidden="true">&rarr;</span>' +
    '<input class="input sm" data-s value="' + esc(pr[1]) + '" aria-label="How it is said" placeholder="Said, e.g. mu k" spellcheck="false"><button class="icon-btn sm" data-hear aria-label="Hear it" title="Hear it"><svg class="ic sm"><use href="#i-play"/></svg></button>' +
    '<button class="icon-btn sm" data-rm aria-label="Remove"><svg class="ic sm"><use href="#i-trash"/></svg></button></li>';
}

/* ---------- editing a line: saved into the code a moment after you stop typing ---------- */
$('nrRows').addEventListener('input', function (e) {
  var ta = e.target.closest('textarea'); if (!ta) return;
  var n = +ta.closest('.nr-row').dataset.n; pending[st.scene + '|' + n] = { scene: st.scene, n: n, text: ta.value };
  ta.classList.remove('bad'); clearTimeout(saveTimer); saveTimer = setTimeout(flush, 700);
});
$('nrRows').addEventListener('focusout', function (e) { if (e.target.closest('textarea')) flush(); });
function flush() {
  clearTimeout(saveTimer);
  var edits = Object.keys(pending).map(function (k) { return pending[k]; }); pending = {};
  if (!edits.length) return Promise.resolve();
  return call({ op: 'set', edits: edits }).then(function (r) {
    M.applyCode(r.code); st.lines = r.lines; msg('');
    edits.forEach(function (ed) { var l = st.lines.filter(function (x) { return x.scene === ed.scene && x.n === ed.n; })[0]; var row = $('nrRows').querySelector('[data-n="' + ed.n + '"]'); if (l && row && ed.scene === st.scene) { var ta = row.querySelector('textarea'); ta.classList.remove('bad'); row.querySelector('[data-goto]').dataset.goto = l.line; row.querySelector('[data-goto]').textContent = 'Line ' + l.line; } });
    paintTiming(); measure();
  }).catch(function (e) {
    msg(e.message, true);
    edits.forEach(function (ed) { var row = $('nrRows').querySelector('[data-n="' + ed.n + '"]'); if (row) row.querySelector('textarea').classList.add('bad'); });
  });
}

/* ---------- playing a line ---------- */
function play(text, extra) {
  var v = M.lessonVoice(), a = $('nrAudio');
  return M.api('/api/voice/preview', Object.assign({ voice: v.id, speed: v.speed, text: text }, extra || {})).then(function (r) { a.src = r.url; return a.play(); });
}
$('nrRows').addEventListener('click', function (e) {
  var g = e.target.closest('[data-goto]'); if (g) { dlg.close(); M.jumpToLine(+g.dataset.goto); return; }
  var b = e.target.closest('[data-play]'); if (!b) return;
  var row = b.closest('.nr-row'), text = row.querySelector('textarea').value;
  b.disabled = true; msg('Making the voice…');
  flush().then(function () { return play(text, { code: M.getCode(), scene: st.scene }); }).then(function () { msg(''); }).catch(function (er) { msg(er.message || 'Could not play the line.', true); }).then(function () { b.disabled = false; });
});
$('nrSample').addEventListener('click', function () {
  var first = rowsOf(st.scene)[0], b = this; b.disabled = true; msg('Making the voice…');
  play(first ? first.text : '', first ? { code: M.getCode(), scene: st.scene } : {}).then(function () { msg(''); }).catch(function (er) { msg(er.message, true); }).then(function () { b.disabled = false; });
});

/* ---------- voice and speed ---------- */
$('nrVoice').addEventListener('change', function () { M.setLessonVoice(this.value, null); measure(); });
$('nrSpeed').addEventListener('input', function () { $('nrSpeedOut').textContent = (+this.value).toFixed(2).replace(/0$/, '') + 'x'; });
$('nrSpeed').addEventListener('change', function () { M.setLessonVoice(null, +this.value); measure(); });
$('nrScenes').addEventListener('click', function (e) { var b = e.target.closest('[data-scene]'); if (!b) return; flush().then(function () { st.scene = b.dataset.scene; paint(); measure(); }); });
dlg.addEventListener('change', function (e) {
  if (e.target.id !== 'nrSceneVoice' && e.target.id !== 'nrSceneSpeed') return;
  var sp = $('nrSceneSpeed').value;
  call({ op: 'scene', scene: st.scene, voice: $('nrSceneVoice').value || null, speed: sp === '' ? null : +sp }).then(function (r) { M.applyCode(r.code); st.lines = r.lines; st.settings = r.settings; msg('Saved for ' + st.scene + '. It is kept as comments above the scene in the code.'); measure(); })
    .catch(function (er) { msg(er.message, true); });
});

/* ---------- pronunciations ---------- */
$('nrPairAdd').addEventListener('click', function () {
  $('nrPairs').insertAdjacentHTML('beforeend', pairRow(['', ''])); $('nrPron').open = true;
  var rows = $('nrPairs').querySelectorAll('.nr-pair'); rows[rows.length - 1].querySelector('[data-w]').focus();
});
$('nrPairs').addEventListener('click', function (e) {
  var li = e.target.closest('.nr-pair'); if (!li) return;
  if (e.target.closest('[data-rm]')) li.remove();
  else if (e.target.closest('[data-hear]')) {
    var said = li.querySelector('[data-s]').value || li.querySelector('[data-w]').value;
    play(said).then(function () { msg(''); }).catch(function (er) { msg(er.message, true); });
  }
});
$('nrPairSave').addEventListener('click', function () {
  var pairs = [].map.call($('nrPairs').querySelectorAll('.nr-pair'), function (li) { return [li.querySelector('[data-w]').value, li.querySelector('[data-s]').value]; });
  flush().then(function () { return call({ op: 'pron', pairs: pairs, defaults: $('nrDefaults').checked }); }).then(function (r) {
    M.applyCode(r.code); st.lines = r.lines; st.pron = r.pron; paint(); measure(); msg('Pronunciations saved in this lesson. Lines are spoken this way from now on.');
  }).catch(function (e) { msg(e.message, true); });
});

/* ---------- the assistant rewrites the spoken words ---------- */
dlg.addEventListener('click', function (e) {
  var b = e.target.closest('[data-ai]'); if (!b || st.busy) return;
  if (!M.aiReady()) { msg('Set up an AI first (Settings, AI assistant).', true); M.openAI(); return; }
  st.busy = true; dlg.querySelectorAll('[data-ai]').forEach(function (x) { x.disabled = true; }); msg('Rewriting the narration…');
  flush().then(function () { return M.api('/api/ai/narration', { code: M.getCode(), style: b.dataset.ai, level: $('nrLevel').value, scene: st.scene }); }).then(function (r) {
    if (r.error) { msg(r.error, true); return; }
    M.applyCode(r.code); st.lines = r.lines; paint(); measure();
    msg(r.changed ? 'Rewrote ' + r.changed + (r.changed === 1 ? ' line' : ' lines') + (r.skipped.length ? '; kept the old words on line ' + r.skipped.join(', ') + ' (a [bracketed] part was lost). ' : '. ') + 'Undo with Ctrl+Z in the code.' : 'Nothing needed changing.');
  }).catch(function (er) { msg(er.message, true); }).then(function () { st.busy = false; dlg.querySelectorAll('[data-ai]').forEach(function (x) { x.disabled = false; }); });
});
$('nrExport').addEventListener('click', function () { flush().then(function () { dlg.close(); M.scriptExport(); }); });
dlg.addEventListener('close', function () { flush(); });

window.MGXNarr = { open: open };
})();
