/* Export lesson: a handout PDF (the solved problem, the narration as steps, optional pictures from the videos, the Manimo brand at the end),
   a GIF of a scene, a share folder, and the teacher's brand (name, logo, colour) used on the handout. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('kitDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc;
var st = { tab: 'pdf', scenes: [], brand: null, logo: '', poll: null, filled: false };

function msg(t, bad) { var n = $('kitMsg'); n.textContent = t || ''; n.classList.toggle('bad', !!bad); }
function title() { var t = $('kitTitle').value.trim(); return t || 'Lesson'; }
function videos() { return (window.MGXBoard && window.MGXBoard.state.done) || {}; }

/* ---------- opening ---------- */
function open() {
  if (!M.getCode().trim()) { M.toast('Add some code first.'); return; }
  M.api('/api/scenes', { code: M.getCode(), op: 'info' }).then(function (r) {
    st.scenes = r.scenes; fillDefaults(); paintScenes(); tab(st.tab); $('kitProgress').hidden = true; $('kitResult').innerHTML = ''; msg('');
    dlg.showModal();
  }).catch(function (e) { M.toast(e.message); });
  M.api('/api/brand').then(function (b) { st.brand = b; st.logo = b.logo; paintBrand(); }).catch(function () {});
}
function fillDefaults() {
  if (!$('kitTitle').value) { var n = (M.getName() || 'Lesson').replace(/\.py$/i, '').replace(/[_-]+/g, ' ').trim(); $('kitTitle').value = n.charAt(0).toUpperCase() + n.slice(1); }
  var solved = M.lastSolved();
  if (solved && !st.filled) { $('kitProblem').value = solved.problem; $('kitSolution').value = solved.solution; st.filled = true; }
}
$('kitUseSolved').addEventListener('click', function () {
  var s = M.lastSolved(); if (!s) { msg('There is no solved problem in the assistant chat yet. Paste the problem and its solution here instead.', true); return; }
  $('kitProblem').value = s.problem; $('kitSolution').value = s.solution; msg('Filled in from the assistant’s last solved problem.');
});

/* ---------- tabs and scene lists ---------- */
function tab(t) {
  st.tab = t;
  dlg.querySelectorAll('[data-kt]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.kt === t)); });
  dlg.querySelectorAll('[data-kp]').forEach(function (p) { p.hidden = p.dataset.kp.split(' ').indexOf(t) < 0; });
  dlg.querySelectorAll('[data-kq]').forEach(function (n) { n.hidden = n.dataset.kq.split(' ').indexOf(t) < 0; });
  $('kitShared').hidden = t === 'brand' || t === 'gif';
  $('kitGo').hidden = t === 'brand'; $('kitGo').textContent = { pdf: 'Make the PDF', pptx: 'Make the slides', gif: 'Make the GIF', share: 'Make the share folder' }[t] || '';
}
dlg.querySelector('.kit-tabs').addEventListener('click', function (e) { var b = e.target.closest('[data-kt]'); if (b) tab(b.dataset.kt); });

function rendered(name) { var d = videos()[name]; return !!(d && d.path); }
function paintScenes() {
  var rows = st.scenes.map(function (s) {
    var r = rendered(s.name);
    return '<label class="kit-scene"><input type="checkbox" data-scene="' + esc(s.name) + '" checked><span>' + esc(s.name) + '</span><small>' + (r ? 'rendered' : 'not rendered in this session') + '</small></label>';
  }).join('');
  $('kitPdfScenes').innerHTML = rows; $('kitShareScenes').innerHTML = rows;
  $('kitGifScene').innerHTML = st.scenes.map(function (s) { return '<option value="' + esc(s.name) + '">' + esc(s.name) + '</option>'; }).join('');
  $('kitNoScenes').hidden = !!st.scenes.length;
}
function picked(box) { return [].map.call(box.querySelectorAll('input:checked'), function (i) { return i.dataset.scene; }); }
function sceneList(names) { return names.map(function (n) { return { name: n, video: (videos()[n] || {}).path || '' }; }); }

/* ---------- running an export ---------- */
function run(url, body, label) {
  var p = $('kitProgress'); p.hidden = false; $('kitResult').innerHTML = ''; $('kitGo').disabled = true; msg('');
  $('kitProgText').textContent = label; $('kitBar').style.transform = 'scaleX(.03)';
  M.api(url, Object.assign({ out_dir: M.outDir() }, body)).then(function () {
    clearInterval(st.poll);
    st.poll = setInterval(function () {
      fetch('/api/kit/job').then(function (r) { return r.json(); }).then(function (j) {
        $('kitProgText').textContent = j.step || label; $('kitBar').style.transform = 'scaleX(' + Math.max(0.03, (j.percent || 0) / 100) + ')';
        if (j.state === 'running') return;
        clearInterval(st.poll); $('kitGo').disabled = false; p.hidden = true;
        if (j.state === 'error') { msg(j.error, true); return; }
        done(j);
      });
    }, 700);
  }).catch(function (e) { $('kitGo').disabled = false; p.hidden = true; msg(e.message, true); });
}
function done(j) {
  var open = j.kind === 'folder' ? '<button class="btn sm primary" data-open="folder">Show the folder</button>' : '<button class="btn sm primary" data-open="file">Open ' + esc(j.kind.toUpperCase()) + '</button><button class="btn sm" data-open="folder">Show in folder</button>';
  var extra = '';
  if (j.missing && j.missing.length) extra += '<p class="help bad">No video was found for ' + esc(j.missing.join(', ')) + ', so it has no pictures. Render it (Storyboard, Render) and export again.</p>';
  if (j.note) extra += '<p class="help">' + esc(j.note) + '</p>';
  if (j.blank && j.blank.length) extra += '<p class="help bad">No clear picture was found for: ' + esc(j.blank.join('; ')) + '. Those steps are text only.</p>';
  if (j.pages) extra += '<p class="help">' + j.pages + ' pages.</p>';
  if (j.slides) extra += '<p class="help">' + j.slides + ' slides. The narration is in the speaker notes.</p>';
  if (j.files) extra += '<p class="help">' + esc(j.files.join(', ')) + '</p>';
  $('kitResult').innerHTML = '<p><b>Done.</b> ' + esc(j.name) + '</p><div class="dlg-row">' + open + '</div>' + extra;
  $('kitResult').dataset.file = j.file; M.toast(j.name + ' is ready');
}
$('kitResult').addEventListener('click', function (e) {
  var b = e.target.closest('[data-open]'); if (!b) return; var f = this.dataset.file;
  if (b.dataset.open === 'file') M.api('/api/open-file', { path: f }).catch(function (er) { msg(er.message, true); });
  else M.api('/api/open-folder', { path: b.dataset.open === 'folder' && !/\.[A-Za-z0-9]{2,4}$/.test(f) ? f : M.outDir() }).catch(function (er) { msg(er.message, true); });
});

$('kitGo').addEventListener('click', function () {
  if (st.tab === 'pdf' || st.tab === 'pptx') {
    var names = picked($('kitPdfScenes')); if (!names.length) { msg('Tick at least one scene.', true); return; }
    var v = M.lessonVoice(), pdf = st.tab === 'pdf';
    run(pdf ? '/api/kit/pdf' : '/api/kit/pptx', { code: M.getCode(), title: title(), audience: $('kitAudience').value, problem: $('kitProblem').value, solution: $('kitSolution').value, frames: $('kitFrames').value,
      light: $('kitLight').checked, figure: $('kitFigure').checked && !!$('kitProblem').value.trim(), scenes: sceneList(st.scenes.map(function (s) { return s.name; })), only: names, voice: v.id, speed: v.speed,
      size: pdf ? $('kitSize').value : 'large', large_print: pdf && $('kitLarge').checked, slides: pdf ? undefined : $('kitSlides').value }, pdf ? 'Making the handout…' : 'Making the slides…');
  } else if (st.tab === 'gif') {
    var g = $('kitGifScene').value; if (!g) { msg('There is no scene to make a GIF from.', true); return; }
    run('/api/kit/gif', { scene: g, video: (videos()[g] || {}).path || '', start: +$('kitGifStart').value || 0, seconds: +$('kitGifSecs').value || 8, width: +$('kitGifWidth').value }, 'Making the GIF…');
  } else if (st.tab === 'share') {
    var sn = picked($('kitShareScenes')); if (!sn.length) { msg('Tick at least one scene.', true); return; }
    run('/api/kit/share', { title: title(), description: $('kitDesc').value, scenes: sceneList(sn) }, 'Making the share folder…');
  }
});

/* ---------- brand ---------- */
function paintBrand() {
  var b = st.brand || {}; $('kitBrandName').value = b.name || ''; $('kitBrandTag').value = b.tagline || ''; $('kitBrandColor').value = b.accent || '#1fa5bd';
  $('kitLogoPrev').innerHTML = st.logo ? '<img src="' + esc(st.logo) + '" alt="Your logo">' : '<span class="help">No logo yet</span>';
}
function shrink(file, max) {
  return new Promise(function (ok, no) {
    var img = new Image(), url = URL.createObjectURL(file);
    img.onload = function () {
      var s = Math.min(1, max / Math.max(img.width, img.height)), c = document.createElement('canvas'); c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); ok(c.toDataURL('image/png'));
    };
    img.onerror = function () { URL.revokeObjectURL(url); no(new Error('That file is not a picture Manimo can read.')); };
    img.src = url;
  });
}
$('kitLogoFile').addEventListener('change', function () {
  var f = this.files[0]; if (!f) return;
  shrink(f, 320).then(function (d) { st.logo = d; paintBrand(); msg('Press Save brand to keep it.'); }).catch(function (e) { msg(e.message, true); });
});
$('kitLogoClear').addEventListener('click', function () { st.logo = ''; paintBrand(); });
$('kitBrandSave').addEventListener('click', function () {
  M.api('/api/brand', { name: $('kitBrandName').value, tagline: $('kitBrandTag').value, accent: $('kitBrandColor').value, logo: st.logo }).then(function (b) { st.brand = b; msg('Brand saved. It appears at the top of your handouts.'); })
    .catch(function (e) { msg(e.message, true); });
});

window.MGXKit = { open: open };
})();
