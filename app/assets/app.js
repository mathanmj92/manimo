/* Manimo UI. Talks to server.py on 127.0.0.1; with no server (opened straight from disk) it runs as a simulated preview. */
(function () {
'use strict';
var TOKEN = window.MANIMO_TOKEN || '';
var DEMO = TOKEN.indexOf('__') === 0;
var $ = function (id) { return document.getElementById(id); };
var root = document.documentElement;
var phone = matchMedia('(max-width: 720px)');
var narrow = matchMedia('(max-width: 1000px)');
var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');

/* ---------------------------------------------------------------- helpers */
function store(k, v) {
  try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {}
  return null;
}
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function fmt(sec) {
  if (sec == null || !isFinite(sec)) return '\u2014';
  sec = Math.max(0, Math.round(sec));
  var m = Math.floor(sec / 60), s = sec % 60;
  return m + ':' + (s < 10 ? '0' : '') + s;
}
function shortPath(p) {
  var parts = p.split(/[\\/]+/).filter(Boolean);
  return parts.length > 3 ? '\u2026\\' + parts.slice(-2).join('\\') : p;
}
function toast(msg) {
  var t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  $('toasts').appendChild(t);
  setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 260); }, 3400);
}
function say(msg) { $('live').textContent = ''; setTimeout(function () { $('live').textContent = msg; }, 30); }
function api(path, body) {
  return fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Token': TOKEN },
    body: body === undefined ? undefined : JSON.stringify(body)
  }).then(function (r) {
    return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'Request failed'); return j; });
  });
}
function openUrl(u) { if (DEMO) { window.open(u, '_blank'); return; } api('/api/open-url', { url: u }).catch(function (e) { toast(e.message); }); }

/* ---------------------------------------------------------------- settings + theme */
var DEFAULTS = { quality: 'h', shape: 'auto', fps: 'auto', encoding: 'balanced', theme: 'system' };
var SHAPE_LABEL = { 'auto': '', '16:9': '16:9', '9:16': '9:16 tall', '1:1': 'square', '4:3': '4:3', '3:4': '3:4' };
var ENC_LABEL = { fast: 'Fastest', balanced: 'Balanced', small: 'Small file' };
var QUALITY = { l: ['480p', '854x480'], m: ['720p', '1280x720'], h: ['1080p', '1920x1080'], k: ['4K', '3840x2160'] };
var QHELP = { l: 'Fast drafts. Good for checking timing.', m: 'A quick, sharp preview.', h: 'Best for most uses. Recommended.', k: 'Highest detail. Takes the longest.' };
var S = Object.assign({}, DEFAULTS);
try { Object.assign(S, JSON.parse(store('mgx-settings') || '{}')); } catch (e) {}
S.theme = store('mgx-theme') || S.theme;
if (S.theme === 'dark') S.theme = 'chalk'; else if (S.theme === 'light') S.theme = 'paper';
var outDir = store('mgx-outdir') || 'C:\\Users\\you\\Videos\\Manimo';
var info = { engines: { manimgx: DEMO ? 'demo' : null, manim: null }, latex: true, version: '', python: '', python_path: '' };

var mq = matchMedia('(prefers-color-scheme: dark)');
var LOOKS = { chalk: 'dark', blueprint: 'dark', paper: 'light', mint: 'light' }, COUNTERPART = { chalk: 'paper', paper: 'chalk', blueprint: 'mint', mint: 'blueprint' };
function currentLook() {
  var t = S.theme === 'dark' ? 'chalk' : S.theme === 'light' ? 'paper' : S.theme;
  if (t === 'system' || !LOOKS[t]) t = mq.matches ? 'chalk' : 'paper';
  return t;
}
function applyTheme(animate) {
  var look = currentLook(), dark = LOOKS[look] === 'dark';
  if (animate && !reduceMotion.matches) { root.classList.add('theme-anim'); setTimeout(function () { root.classList.remove('theme-anim'); }, 300); }
  root.dataset.look = look; root.dataset.theme = LOOKS[look];
  $('themeIcon').setAttribute('href', dark ? '#i-sun' : '#i-moon');
  $('themeBtn').setAttribute('aria-label', dark ? 'Switch to a light look' : 'Switch to a dark look');
}
mq.addEventListener('change', function () { if (S.theme === 'system') applyTheme(true); });
$('themeBtn').addEventListener('click', function () {
  S.theme = COUNTERPART[currentLook()];
  store('mgx-theme', S.theme); applyTheme(true); syncSettingsUI();
});

/* ---------------------------------------------------------------- editor (CodeMirror 6) */
var cm = MGXEditor.create({
  parent: $('cmHost'),
  onChange: function () { cm.clearMarks(); markDirty(); afterEdit(); },
  onCursor: function (l, c) { $('pos').textContent = 'Ln ' + l + ', Col ' + c; },
  onSave: function () { saveFile(false); },
  onRun: function () { $('startBtn').click(); },
  onOpen: function () { openFile(); }
});
var code = { get value() { return cm.getValue(); }, set value(v) { cm.setValue(v); }, focus: function () { cm.focus(); } };

/* A scene is a class with a base called *Scene*, even in a mixin list: class A(Parts, m.Scene): */
var CLASS_RE = /^class\s+(\w+)\s*\(([^)]*)\)\s*:/gm;
function scenesOf(src) {
  var r = [], m;
  CLASS_RE.lastIndex = 0;
  while ((m = CLASS_RE.exec(src))) {
    if (m[2].split(',').some(function (b) { return /(^|\.)\w*Scene\w*$/.test(b.trim()); })) r.push(m[1]);
  }
  return r;
}
function engineOf(src) {
  if (/^\s*(?:from|import)\s+manimgx\b/m.test(src)) return 'manimgx';
  if (/^\s*(?:from|import)\s+manim\b/m.test(src)) return 'manim';
  return 'manimgx';
}
var ALL = '__all__', selScene = '', sceneKey = '';
function syncSceneMenu(names) {
  var key = names.join('|');
  if (selScene !== ALL && names.indexOf(selScene) < 0) selScene = names[names.length - 1] || '';
  if (selScene === ALL && names.length < 2) selScene = names[0] || '';
  if (key !== sceneKey) {
    sceneKey = key;
    $('sceneSel').innerHTML = (names.length > 1 ? '<option value="' + ALL + '">All scenes (' + names.length + ')</option>' : '') +
      names.map(function (n) { return '<option value="' + esc(n) + '">' + esc(n) + '</option>'; }).join('');
  }
  $('sceneSel').value = selScene;
  $('sceneChip').hidden = names.length < 2;
}
$('sceneSel').addEventListener('change', function () { selScene = this.value; store('mgx-scene', selScene); updateStatus(); });

function validity() {
  var v = code.value;
  if (!v.trim()) return { ok: false, msg: 'Add some code to begin.' };
  var sc = scenesOf(v);
  if (!sc.length) return { ok: false, msg: 'No Scene found. Your code needs a class that extends Scene.' };
  return { ok: true, scenes: sc, engine: engineOf(v) };
}
function texLabel() {
  if (!info.latex) return 'Not installed';
  return (info.latex_version || 'Ready') + (info.latex_bundled ? ' · built into Manimo' : ' · found on this PC');
}
function engineReady(name) { return !!(info.engines && info.engines[name]); }
function updateStatus() {
  var v = code.value, chk = validity(), msg = $('sceneMsg');
  msg.className = 'msg';
  syncSceneMenu(chk.scenes || (v.trim() ? scenesOf(v) : []));
  var tag = $('engineTag');
  if (!v.trim()) { msg.textContent = 'No code yet'; tag.textContent = ''; paintStart(); paintDock(); return; }
  if (!chk.ok) { msg.className = 'msg warn'; msg.innerHTML = '<svg class="ic sm"><use href="#i-alert"/></svg>' + esc(chk.msg); tag.textContent = ''; paintStart(); paintDock(); return; }
  var names = chk.scenes;
  msg.textContent = names.length === 1 ? '1 scene: ' + names[0] : names.length + ' scenes found. Rendering ' + (selScene === ALL ? 'all of them' : selScene) + '.';
  tag.textContent = chk.engine === 'manim' ? 'Manim' : 'ManimGX';
  if (chk.engine === 'manim' && !engineReady('manim')) {
    msg.className = 'msg warn';
    msg.innerHTML = '<svg class="ic sm"><use href="#i-alert"/></svg>This code is written for Manim, which is not added yet. Press Start Rendering to add it.';
  } else if (chk.engine === 'manim' && !info.latex && /\b(MathTex|Tex)\s*\(/.test(v)) {
    msg.className = 'msg warn';
    msg.innerHTML = '<svg class="ic sm"><use href="#i-alert"/></svg>This code uses LaTeX (MathTex / Tex), which is not installed on this PC.';
  }
  paintStart(); paintDock();
}
function afterEdit() {
  var v = code.value; if (typeof syncAIChip === 'function') syncAIChip();
  $('empty').hidden = v.length > 0;
  updateStatus(); paintBeats();
  store('mgx-code', v);
  if (window.MGXProject) window.MGXProject.changed();
}
/* the parts of the video: one chip per self.next_section("Name"), click to jump to it in the code */
function paintBeats() {
  var text = code.value, found = [], re = /^[ \t]*self\.next_section\(\s*(['"])(.*?)\1/gm, m;
  while ((m = re.exec(text)) && found.length < 24) found.push({ name: m[2] || 'Part ' + (found.length + 1), line: text.slice(0, m.index).split('\n').length });
  var key = JSON.stringify(found);
  if (paintBeats.key === key) return; paintBeats.key = key;
  $('beats').hidden = !found.length;
  $('beatsList').innerHTML = found.map(function (b, i) { return '<button class="beat" data-line="' + b.line + '" title="Line ' + b.line + '">' + (i + 1) + '. ' + esc(b.name) + '</button>'; }).join('');
}
$('beatsList').addEventListener('click', function (e) { var b = e.target.closest('.beat'); if (b) jumpToLine(parseInt(b.dataset.line, 10)); });
$('learnBtn').addEventListener('click', function () { openDialog('learnDlg'); });
function jumpToLine(n) { cm.jump(n); if (narrow.matches) setView('code'); }
document.addEventListener('click', function (e) {
  var t = e.target.closest('[data-line]'); if (!t) return;
  jumpToLine(parseInt(t.dataset.line, 10));
});

/* ---------------------------------------------------------------- files and sessions */
var EXAMPLES = [
  { name: 'Hello (ManimGX)', file: 'hello_manimgx.py', code:
    'import manimgx as m\n\n\nclass HelloManimo(m.Scene):\n    def construct(self):\n        title = m.Text("Hello, Manimo", font_size=56)\n        circle = m.Circle(color=m.BLUE).scale(1.4)\n        square = m.Square(color=m.YELLOW).scale(1.4)\n\n        self.play(m.Write(title))\n        self.play(title.animate.to_edge(m.UP))\n        self.play(m.Create(circle))\n        self.play(m.Transform(circle, square))\n        self.play(m.FadeOut(circle), m.FadeOut(title))\n        self.wait(0.5)\n' },
  { name: 'Two scenes (try "All scenes")', file: 'two_scenes.py', code:
    'import manimgx as m\n\n\nclass Intro(m.Scene):\n    def construct(self):\n        title = m.Text("Two scenes, one file", font_size=48)\n        self.play(m.Write(title))\n        self.wait(1)\n        self.play(m.FadeOut(title))\n\n\nclass Shapes(m.Scene):\n    def construct(self):\n        dot = m.Dot(color=m.YELLOW)\n        ring = m.Circle(color=m.BLUE).scale(1.6)\n        self.play(m.Create(ring), m.FadeIn(dot))\n        self.play(dot.animate.shift(m.RIGHT * 2))\n        self.play(m.FadeOut(dot), m.FadeOut(ring))\n' },
  { name: 'Hello (Manim Community)', file: 'hello_manim.py', code:
    'from manim import *\n\n\nclass HelloManim(Scene):\n    def construct(self):\n        title = Text("Hello, Manim", font_size=56)\n        circle = Circle(color=BLUE).scale(1.4)\n        self.play(Write(title))\n        self.play(title.animate.to_edge(UP))\n        self.play(Create(circle))\n        self.wait(0.5)\n' }
];
fetch('assets/examples.json').then(function (r) { return r.json(); }).then(function (list) { list.forEach(function (e) { EXAMPLES.push(e); }); }).catch(function () {});   // the tall and square examples
var fileHandle = null, curName = '', dirty = false;
var PY_TYPES = [{ description: 'Python files', accept: { 'text/x-python': ['.py'] } }];
function paintFile() {
  var n = curName || 'Untitled.py';
  if (window.MGXProject && window.MGXProject.active()) n = window.MGXProject.label() + ' / ' + n;
  $('fileName').textContent = n + (dirty ? ' \u2022' : '');
  $('fileChip').title = (dirty ? 'Unsaved changes. ' : '') + 'Press Ctrl+S to save';
  $('editorTitle').textContent = curName || 'Code';
}
function markDirty() { if (!dirty && code.value !== '') { dirty = true; paintFile(); } }
function setCode(text, name, handle) {
  code.value = text; afterEdit();
  curName = name || ''; fileHandle = handle || null; dirty = false; paintFile();
  store('mgx-name', name || '');
}
function discardOk() { return !dirty || window.confirm('You have unsaved changes. Replace them?'); }
function loadFile(f) {
  if (!f) return;
  if (f.size > 1.5e6) { toast('That file is too large to be a script.'); return; }
  if (!discardOk()) return;
  var r = new FileReader();
  r.onload = function () { setCode(String(r.result), f.name); toast('Loaded ' + f.name); };
  r.readAsText(f);
}
function newFile() { if (!discardOk()) return; setCode('', ''); cm.focus(); }
function openFile() {
  if (!window.showOpenFilePicker) { $('fileInput').click(); return; }
  if (!discardOk()) return;
  window.showOpenFilePicker({ types: PY_TYPES }).then(function (hs) {
    return hs[0].getFile().then(function (f) { return f.text().then(function (t) { setCode(t, f.name, hs[0]); toast('Opened ' + f.name); }); });
  }).catch(function (e) { if (e && e.name !== 'AbortError') $('fileInput').click(); });
}
function writeHandle(h, text) { return h.createWritable().then(function (w) { return w.write(text).then(function () { return w.close(); }); }); }
function saveFile(as) {
  if (window.MGXProject && window.MGXProject.active() && curName) { window.MGXProject.flush().then(function () { dirty = false; paintFile(); toast('Saved ' + curName + ' in the project'); }); return; }
  var text = code.value;
  if (!text) { toast('Nothing to save yet'); return; }
  var done = function (name, handle) { curName = name; fileHandle = handle || fileHandle; dirty = false; paintFile(); store('mgx-name', name); toast('Saved ' + name); };
  var download = function () {
    var a = document.createElement('a'), n = curName || 'scene.py';
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/x-python' })); a.download = n; document.body.append(a); a.click(); a.remove(); done(n, null);
  };
  if (fileHandle && !as) {
    writeHandle(fileHandle, text).then(function () { done(curName || fileHandle.name, fileHandle); }).catch(function (e) { toast('Could not save: ' + (e && e.message || e)); });
  } else if (window.showSaveFilePicker) {
    window.showSaveFilePicker({ suggestedName: curName || 'scene.py', types: PY_TYPES })
      .then(function (h) { return writeHandle(h, text).then(function () { done(h.name, h); }); })
      .catch(function (e) { if (e && e.name !== 'AbortError') download(); });
  } else download();
}
window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

function pasteFromClipboard() {
  var fallback = function () { $('empty').hidden = true; cm.focus(); toast('Press Ctrl+V to paste your code'); };
  if (!(navigator.clipboard && navigator.clipboard.readText)) return fallback();
  navigator.clipboard.readText().then(function (t) {
    if (t && t.trim()) { if (discardOk()) { setCode(t, 'Pasted code.py'); toast('Code pasted'); } }
    else { cm.focus(); toast('Clipboard is empty. Copy your code first.'); }
  }).catch(fallback);
}
function loadExample(i) { if (!discardOk()) return; setCode(EXAMPLES[i].code, EXAMPLES[i].file); closeAllDialogs(); }
$('fileInput').addEventListener('change', function (e) { loadFile(e.target.files[0]); e.target.value = ''; });
['openBtn', 'emptyOpen'].forEach(function (id) { $(id).addEventListener('click', openFile); });
$('saveBtn').addEventListener('click', function () { saveFile(false); });
['pasteBtn', 'emptyPaste'].forEach(function (id) { $(id).addEventListener('click', pasteFromClipboard); });
['exampleBtn', 'emptyExample', 'helpExample'].forEach(function (id) { $(id).addEventListener('click', function () { loadExample(0); }); });
$('clearBtn').addEventListener('click', newFile);
$('emptyPaste').addEventListener('click', function () { $('empty').hidden = true; });
var dragDepth = 0;
window.addEventListener('dragenter', function (e) { if (e.dataTransfer && [].indexOf.call(e.dataTransfer.types, 'Files') >= 0) { dragDepth++; $('dropzone').classList.add('show'); } });
window.addEventListener('dragleave', function () { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $('dropzone').classList.remove('show'); });
window.addEventListener('dragover', function (e) { e.preventDefault(); });
window.addEventListener('drop', function (e) { e.preventDefault(); dragDepth = 0; $('dropzone').classList.remove('show'); loadFile(e.dataTransfer.files[0]); });

/* A session is the whole workspace in one small file: code, scene, settings and output folder. */
function sessionObject() {
  return { format: 'manimo-session', version: 1, savedAt: new Date().toISOString(), name: curName, code: code.value, scene: selScene,
           settings: { quality: S.quality, shape: S.shape, fps: S.fps, encoding: S.encoding }, outDir: outDir };
}
function applySession(o) {
  if (!o || o.format !== 'manimo-session' || typeof o.code !== 'string') { toast('That is not a Manimo session file'); return; }
  setCode(o.code, o.name || '');
  if (o.settings) { Object.assign(S, { quality: o.settings.quality || S.quality, shape: o.settings.shape || 'auto', fps: o.settings.fps || S.fps, encoding: o.settings.encoding || S.encoding }); persistSettings(); syncSettingsUI(); }
  if (o.outDir) { outDir = o.outDir; store('mgx-outdir', outDir); renderFolder(); }
  if (o.scene) { selScene = o.scene; updateStatus(); }
  toast('Session opened');
}
function saveSession() {
  var text = JSON.stringify(sessionObject(), null, 2), name = (curName ? curName.replace(/\.py$/i, '') : 'session') + '.manimo';
  var fallback = function () { var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' })); a.download = name; document.body.append(a); a.click(); a.remove(); toast('Session saved as ' + name); };
  if (window.showSaveFilePicker) {
    window.showSaveFilePicker({ suggestedName: name, types: [{ description: 'Manimo session', accept: { 'application/json': ['.manimo'] } }] })
      .then(function (h) { return writeHandle(h, text).then(function () { toast('Session saved'); }); })
      .catch(function (e) { if (e && e.name !== 'AbortError') fallback(); });
  } else fallback();
}
function openSession() {
  if (!discardOk()) return;
  var parse = function (text) { try { applySession(JSON.parse(text)); } catch (e) { toast('Could not read that session file'); } };
  if (window.showOpenFilePicker) {
    window.showOpenFilePicker({ types: [{ description: 'Manimo session', accept: { 'application/json': ['.manimo'] } }] })
      .then(function (hs) { return hs[0].getFile().then(function (f) { return f.text().then(parse); }); })
      .catch(function (e) { if (e && e.name !== 'AbortError') $('sessionInput').click(); });
  } else $('sessionInput').click();
}
$('sessionInput').addEventListener('change', function (e) { var f = e.target.files[0]; e.target.value = ''; if (f) f.text().then(function (t) { try { applySession(JSON.parse(t)); } catch (x) { toast('Could not read that session file'); } }); });
function newSession() {
  if (!discardOk()) return;
  setCode('', ''); selScene = ''; dismissDock(); setPreview([], 0); toast('New session');
}

/* ---------------------------------------------------------------- history (recent renders) */
var history = [];
try { history = JSON.parse(store('mgx-history') || '[]'); } catch (e) { history = []; }
function addHistory(outputs) {
  outputs.forEach(function (o) {
    if (!o.path) return;
    history = history.filter(function (h) { return h.path !== o.path; });
    history.unshift({ name: o.name, path: o.path, kind: o.kind, t: Date.now() });
  });
  history = history.slice(0, 12); store('mgx-history', JSON.stringify(history));
}
function openHistory(h) {
  api('/api/serve-file', { path: h.path }).then(function (r) {
    setPreview([{ name: h.name, path: h.path, kind: h.kind, url: r.url }], 0); if (narrow.matches) setView('preview');
  }).catch(function (e) { toast(e.message); });
}

/* ---------------------------------------------------------------- folder */
function renderFolder() { $('folderLbl').textContent = shortPath(outDir); $('folderChip').title = outDir; $('pathText').textContent = outDir; $('pathText').title = outDir; }
var demoFolders = ['D:\\Renders\\Manimo', 'C:\\Users\\you\\Desktop\\Animations', 'C:\\Users\\you\\Videos\\Manimo'];
function chooseFolder() {
  if (DEMO) { outDir = demoFolders[(demoFolders.indexOf(outDir) + 1) % demoFolders.length]; store('mgx-outdir', outDir); renderFolder(); toast('Output folder set (demo)'); return; }
  toast('Choose a folder in the window that just opened\u2026');
  api('/api/pick-folder', { path: outDir }).then(function (r) { if (r.path) { outDir = r.path; store('mgx-outdir', outDir); renderFolder(); } }).catch(function (e) { toast(e.message); });
}
function openFolder() {
  if (DEMO) { toast('Demo: this opens ' + shortPath(outDir) + ' in File Explorer'); return; }
  api('/api/open-folder', { path: outDir }).catch(function (e) { toast(e.message); });
}
$('folderChip').addEventListener('click', chooseFolder);
$('changeFolder').addEventListener('click', chooseFolder);
$('openFolderBtn').addEventListener('click', openFolder);

/* ---------------------------------------------------------------- settings panel */
var settings = $('settings'), lastOpener = null;
function persistSettings() { var s = Object.assign({}, S); delete s.theme; store('mgx-settings', JSON.stringify(s)); }
function syncSettingsUI() {
  document.querySelectorAll('[data-key]').forEach(function (g) {
    var key = g.dataset.key;
    g.querySelectorAll('[role=radio]').forEach(function (b) { var on = String(S[key]) === b.dataset.v; b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1; });
  });
  $('qualityHelp').textContent = QHELP[S.quality];
  $('quickShape').value = S.shape;
  var ce = engineOf(code.value) === 'manim';
  $('qualityLbl').textContent = QUALITY[S.quality][0] + (SHAPE_LABEL[S.shape] ? ' · ' + SHAPE_LABEL[S.shape] : '') + (S.fps === 'auto' ? '' : ' \u00b7 ' + S.fps + ' fps') + (ce ? '' : ' \u00b7 ' + ENC_LABEL[S.encoding]);
  var e = info.engines || {};
  $('engGx').textContent = e.manimgx ? (e.manimgx === 'demo' ? 'Preview mode' : 'Ready \u00b7 version ' + e.manimgx) : 'Not installed';
  $('engCe').textContent = e.manim ? 'Ready \u00b7 version ' + e.manim : 'Not added yet';
  $('engTex').textContent = texLabel();
  var add = $('addManim'); add.hidden = !!e.manim;
}
$('quickShape').addEventListener('change', function () { S.shape = this.value; persistSettings(); syncSettingsUI(); });
document.querySelectorAll('[data-key]').forEach(function (g) {
  g.addEventListener('click', function (ev) {
    var b = ev.target.closest('[role=radio]'); if (!b) return;
    var k = g.dataset.key; S[k] = (k === 'fps' && b.dataset.v !== 'auto') ? Number(b.dataset.v) : b.dataset.v;
    if (k === 'theme') { store('mgx-theme', S.theme); applyTheme(true); }
    persistSettings(); syncSettingsUI();
  });
  g.addEventListener('keydown', function (ev) {
    var keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!keys[ev.key]) return;
    ev.preventDefault();
    var radios = [].slice.call(g.querySelectorAll('[role=radio]')), i = radios.indexOf(document.activeElement); if (i < 0) i = 0;
    var next = radios[(i + keys[ev.key] + radios.length) % radios.length]; next.focus(); next.click();
  });
});
function setTab(t) {
  settings.querySelectorAll('.set-nav [data-tab]').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === t)); });
  settings.querySelectorAll('[data-pane]').forEach(function (p) { p.hidden = p.dataset.pane !== t; });
}
$('setNav').addEventListener('click', function (e) { var b = e.target.closest('[data-tab]'); if (b) setTab(b.dataset.tab); });
$('setNav').addEventListener('keydown', function (e) {
  var k = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key]; if (!k) return; e.preventDefault();
  var tabs = [].slice.call(this.querySelectorAll('[data-tab]')), i = tabs.indexOf(document.activeElement); if (i < 0) i = 0;
  var n = tabs[(i + k + tabs.length) % tabs.length]; n.focus(); setTab(n.dataset.tab);
});
function fillSettingsExtras() {
  var v = (info && info.voice) || {}, sel = $('setVoice');
  sel.innerHTML = (v.voices || []).map(function (x) { return '<option value="' + esc(x.id) + '">' + esc(x.label + ' · ' + x.accent + ' · ' + x.note) + '</option>'; }).join('');
  sel.disabled = $('setSpeed').disabled = $('setVoiceTry').disabled = !v.available;
  if (v.available) { sel.value = VOICE.id; $('setSpeed').value = String(VOICE.speed); $('setVoiceNote').textContent = 'Used for every self.say and voiceover line. It runs on this PC and needs no internet.'; }
  else $('setVoiceNote').textContent = 'The narration voice is not installed in this copy of Manimo.';
  $('setAIName').textContent = aiLabel();
}
$('setVoice').addEventListener('change', function () { VOICE.id = this.value; store('mgx-voice', VOICE.id); });
$('setSpeed').addEventListener('change', function () { VOICE.speed = parseFloat(this.value) || 1; store('mgx-voice-speed', String(VOICE.speed)); });
$('setVoiceTry').addEventListener('click', function () { closeSettings(false); $('scriptBtn').click(); });
$('setAIBtn').addEventListener('click', function () { closeSettings(false); openAISettings(); });
function openSettings(opener, tab) {
  if (R.state === 'running') { toast('Settings are locked while rendering'); return; }
  closeMenu();
  lastOpener = opener || $('settingsBtn'); syncSettingsUI(); renderFolder(); fillSettingsExtras(); setTab(tab || 'video');
  $('scrim').style.display = 'block';
  settings.hidden = false; settings.classList.remove('leave'); settings.classList.add('enter');
  $('settingsBtn').setAttribute('aria-expanded', 'true');
  var first = settings.querySelector('[role=radio][aria-checked=true]'); if (first) first.focus({ preventScroll: true });
}
function closeSettings(restore) {
  if (settings.hidden) return;
  $('scrim').style.display = '';
  settings.classList.remove('enter'); settings.classList.add('leave');
  $('settingsBtn').setAttribute('aria-expanded', 'false');
  setTimeout(function () { if (settings.classList.contains('leave')) { settings.hidden = true; settings.classList.remove('leave'); } }, 200);
  if (restore !== false && lastOpener) lastOpener.focus({ preventScroll: true });
}
/* quick settings: the gear's first click */
var quick = $('quick');
function aiLabel() {
  var c = AI.cfg || {}; if (!c.configured) return 'Not connected';
  if (c.provider === 'agent') return ((c.agents || []).filter(function (a) { return a.id === c.agent; })[0] || { label: 'Assistant on this PC' }).label;
  return c.provider === 'anthropic' ? 'Claude (API key)' : 'Other model';
}
function openQuick() {
  if (!settings.hidden) { closeSettings(false); }
  closeMenu(); syncSettingsUI();
  $('quickQHelp').textContent = QHELP[S.quality];
  var v = (info && info.voice) || {}, sel = $('quickVoice');
  $('quickVoiceRow').hidden = !v.available;
  sel.innerHTML = (v.voices || []).map(function (x) { return '<option value="' + esc(x.id) + '">' + esc(x.label + ' · ' + x.accent) + '</option>'; }).join('');
  sel.value = VOICE.id;
  $('quickAI').textContent = aiLabel();
  var r = $('settingsBtn').getBoundingClientRect();
  quick.hidden = false; quick.style.top = Math.round(r.bottom + 8) + 'px'; quick.style.right = Math.max(8, Math.round(innerWidth - r.right)) + 'px';
  $('settingsBtn').setAttribute('aria-expanded', 'true');
  var first = quick.querySelector('[role=radio][aria-checked=true]'); if (first) first.focus({ preventScroll: true });
}
function closeQuick(restore) {
  if (quick.hidden) return; quick.hidden = true; $('settingsBtn').setAttribute('aria-expanded', 'false');
  if (restore) $('settingsBtn').focus({ preventScroll: true });
}
$('settingsBtn').addEventListener('click', function () { if (!settings.hidden) { closeSettings(); return; } quick.hidden ? openQuick() : closeQuick(true); });
$('quickMore').addEventListener('click', function () { closeQuick(false); openSettings($('settingsBtn')); });
$('quickLearn').addEventListener('click', function () { closeQuick(false); openDialog('learnDlg'); });
$('quickAIBtn').addEventListener('click', function () { closeQuick(false); openAISettings(); });
$('quickVoice').addEventListener('change', function () { VOICE.id = this.value; store('mgx-voice', VOICE.id); });
quick.addEventListener('click', function () { setTimeout(function () { $('quickQHelp').textContent = QHELP[S.quality]; }, 0); });
document.addEventListener('pointerdown', function (e) { if (!quick.hidden && !quick.contains(e.target) && !e.target.closest('#settingsBtn')) closeQuick(false); });
document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !quick.hidden) { e.preventDefault(); closeQuick(true); } });
$('qualityChip').addEventListener('click', function () { openSettings(this); });
$('settingsClose').addEventListener('click', function () { closeSettings(); });
$('settingsDone').addEventListener('click', function () { closeSettings(); });
$('resetSettings').addEventListener('click', function () { var t = S.theme; S = Object.assign({}, DEFAULTS, { theme: t }); persistSettings(); syncSettingsUI(); toast('Settings reset'); });
document.addEventListener('pointerdown', function (e) {
  if (!settings.hidden && !settings.contains(e.target) && !e.target.closest('#settingsBtn, #qualityChip')) closeSettings(false);
});

/* ---------------------------------------------------------------- layout: tabs and splitter */
function setView(v) {
  $('workspace').dataset.view = v;
  $('tabCode').setAttribute('aria-selected', v === 'code'); $('tabPreview').setAttribute('aria-selected', v === 'preview');
}
$('tabCode').addEventListener('click', function () { setView('code'); });
$('tabPreview').addEventListener('click', function () { setView('preview'); });

(function splitter() {
  var ws = $('workspace'), sp = $('splitter'), pct = parseFloat(store('mgx-split')) || 56;
  function apply(p) { pct = Math.max(32, Math.min(74, p)); ws.style.setProperty('--left', pct + '%'); }
  apply(pct);
  sp.addEventListener('pointerdown', function (e) {
    sp.setPointerCapture(e.pointerId); sp.classList.add('drag'); document.body.style.userSelect = 'none';
    var r = ws.getBoundingClientRect();
    function move(ev) { apply(((ev.clientX - r.left - 12) / (r.width - 24)) * 100); }
    function up() { sp.classList.remove('drag'); document.body.style.userSelect = ''; sp.removeEventListener('pointermove', move); sp.removeEventListener('pointerup', up); store('mgx-split', String(pct)); }
    sp.addEventListener('pointermove', move); sp.addEventListener('pointerup', up);
  });
  sp.addEventListener('keydown', function (e) { if (e.key === 'ArrowLeft') { apply(pct - 2); store('mgx-split', String(pct)); } else if (e.key === 'ArrowRight') { apply(pct + 2); store('mgx-split', String(pct)); } });
  sp.addEventListener('dblclick', function () { apply(56); store('mgx-split', '56'); });
})();

/* ---------------------------------------------------------------- preview */
var P = { list: [], i: 0 };
var film = $('film');
function setPreview(list, i) {
  P.list = list || []; P.i = i || 0;
  var sel = $('previewSel');
  sel.hidden = P.list.length < 2;
  sel.innerHTML = P.list.map(function (o, k) { return '<option value="' + k + '">' + esc(o.name) + '</option>'; }).join('');
  sel.value = String(P.i);
  showPreview();
}
function refitFilm() {          // the video box is exactly the picture, so its edge, border and shadow separate it from the tile around it
  var v = film.querySelector('video'); if (!v) return;
  var pad = 8, cw = film.clientWidth - 2 * pad, ch = film.clientHeight - 2 * pad, vw = v.videoWidth || 16, vh = v.videoHeight || 9;
  if (cw <= 0 || ch <= 0) return;
  var s = Math.min(cw / vw, ch / vh); v.style.width = Math.floor(vw * s) + 'px'; v.style.height = Math.floor(vh * s) + 'px';
}
if (window.ResizeObserver) new ResizeObserver(refitFilm).observe(film);
function showPreview() {
  var o = P.list[P.i];
  film.querySelectorAll('video,iframe').forEach(function (n) { if (n.pause) n.pause(); n.remove(); });
  $('filmEmpty').hidden = !!o;
  $('previewOpen').hidden = !o; $('previewFolder').hidden = !o;
  $('recToggle').hidden = !(o && o.kind !== 'slides' && o.path && !DEMO); recReset(true);
  $('editVidBtn').hidden = !(o && o.kind !== 'slides' && o.path && !DEMO);
  if (!o) { $('previewMsg').textContent = 'Nothing rendered yet'; return; }
  $('previewMsg').textContent = o.name + (o.kind === 'slides' ? ' \u00b7 slideshow' : '');
  if (!o.url) {
    $('filmEmpty').hidden = false;
    $('filmEmpty').querySelector('b').textContent = o.name;
    $('filmEmpty').querySelector('span').textContent = 'In the installed app, the finished video plays right here.';
    return;
  }
  if (o.kind === 'slides') {
    var f = document.createElement('iframe'); f.src = o.url; f.title = 'Slideshow'; f.allow = 'fullscreen'; film.appendChild(f);
  } else {
    var v = document.createElement('video'); v.src = o.url; v.controls = true; v.autoplay = true; v.muted = false; v.playsInline = true; v.preload = 'auto';
    v.addEventListener('error', function () { $('previewMsg').textContent = 'This video could not play here. Use Open to play it in your video player.'; });
    v.addEventListener('loadedmetadata', refitFilm); film.appendChild(v); refitFilm();
    var p = v.play(); if (p && p.catch) p.catch(function () { v.muted = true; v.play().catch(function () {}); });
  }
}
/* ---------------------------------------------------------------- script export */
var SCRIPT = { lines: [], end: 0, scene: '', estimated: true };
var VOICE = { id: store('mgx-voice') || 'am_adam', speed: parseFloat(store('mgx-voice-speed')) || 1 };
function voiceOpts() { return { voice: VOICE.id, speed: VOICE.speed }; }
function fillVoices() {
  var v = (info && info.voice) || {}, sel = $('voiceSel');
  $('voiceRow').hidden = !v.available;
  $('voiceMsg').textContent = v.available ? '' : 'The narration voice is not installed in this copy of Manimo.';
  sel.innerHTML = (v.voices || []).map(function (x) { return '<option value="' + esc(x.id) + '">' + esc(x.label + ' · ' + x.accent + ' · ' + x.note) + '</option>'; }).join('');
  if ((v.voices || []).some(function (x) { return x.id === VOICE.id; })) sel.value = VOICE.id; else VOICE.id = sel.value || 'am_adam';
  $('voiceSpeed').value = String(VOICE.speed);
}
$('voiceSel').addEventListener('change', function () { VOICE.id = this.value; store('mgx-voice', VOICE.id); });
$('voiceSpeed').addEventListener('change', function () { VOICE.speed = parseFloat(this.value) || 1; store('mgx-voice-speed', String(VOICE.speed)); });
$('voicePlay').addEventListener('click', function () {
  var b = this, text = (SCRIPT.lines[0] && SCRIPT.lines[0].text) || '';
  b.disabled = true; $('voiceMsg').textContent = 'Making the voice…';
  api('/api/voice/preview', { voice: VOICE.id, speed: VOICE.speed, text: text }).then(function (r) {
    var a = $('voiceAudio'); a.src = r.url; $('voiceMsg').textContent = ''; return a.play();
  }).catch(function (e) { $('voiceMsg').textContent = e.message || 'Could not play the voice.'; }).then(function () { b.disabled = false; });
});
function scriptStamp(t) { return Math.floor(t / 60) + ':' + ('0' + Math.floor(t % 60)).slice(-2) + '.' + Math.floor((t * 10) % 10); }
$('scriptBtn').addEventListener('click', function () {
  if (DEMO) { toast('Open Manimo from its shortcut to export a script'); return; }
  var dlg = $('scriptDlg'), scene = selScene === ALL ? ((validity().scenes || [])[0] || '') : selScene;
  $('scriptList').innerHTML = ''; $('scriptMsg').textContent = ''; $('scriptNote').textContent = 'Reading the scene…';
  closeMenu(); fillVoices(); dlg.showModal();
  api('/api/script', Object.assign({ code: code.value, scene: scene }, voiceOpts())).then(function (d) {
    SCRIPT = { lines: d.lines || [], end: d.end || 0, scene: d.scene || scene, estimated: d.estimated !== false };
    $('scriptEst').textContent = !SCRIPT.lines.length ? '' : SCRIPT.estimated ? 'Times are estimates (about 0.35 s per word). Save the script to read or record against.' : 'Times are measured from the chosen voice. Change the voice, then press Script again to update them.';
    $('scriptNote').textContent = d.note || (SCRIPT.lines.length + ' line' + (SCRIPT.lines.length === 1 ? '' : 's') + ' in ' + SCRIPT.scene + ', about ' + scriptStamp(SCRIPT.end) + ' long');
    $('scriptList').innerHTML = SCRIPT.lines.map(function (l) { return '<li><time>' + scriptStamp(l.t) + '</time><span>' + esc(l.text) + '</span></li>'; }).join('');
    dlg.querySelectorAll('[data-fmt],#scriptCopy').forEach(function (b) { b.disabled = !SCRIPT.lines.length; });
  }).catch(function (e) { SCRIPT.lines = []; $('scriptNote').textContent = e.message; dlg.querySelectorAll('[data-fmt],#scriptCopy').forEach(function (b) { b.disabled = true; }); });
});
$('scriptCopy').addEventListener('click', function () {
  var t = SCRIPT.lines.map(function (l) { return scriptStamp(l.t) + '  ' + l.text; }).join('\n');
  (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { $('scriptMsg').textContent = 'Copied.'; }, function () { $('scriptMsg').textContent = 'Could not copy. Save it instead.'; });
});
$('scriptDlg').addEventListener('click', function (e) {
  var b = e.target.closest('[data-fmt]'); if (!b) return;
  api('/api/script-save', { fmt: b.dataset.fmt, lines: SCRIPT.lines, end: SCRIPT.end, estimated: SCRIPT.estimated, scene: SCRIPT.scene, out_dir: outDir })
    .then(function (r) { $('scriptMsg').innerHTML = 'Saved <b>' + esc(r.name) + '</b> in your output folder. <button class="linkbtn" id="scriptOpen">Show folder</button>'; $('scriptOpen').onclick = function () { api('/api/open-folder', { path: r.folder }).catch(function () {}); }; })
    .catch(function (err) { $('scriptMsg').textContent = err.message; });
});

/* ---------------------------------------------------------------- narrate: record voice / camera over the video */
var REC = { mic: null, cam: null, ctx: null, raf: 0, mr: null, chunks: [], blob: null, t0: 0, tick: 0, dur: 0, hasCam: false };
function recVideo() { return film.querySelector('video'); }
function recMsg(t) { $('recMsg').textContent = t; }
function recStopStreams() {
  cancelAnimationFrame(REC.raf);
  [REC.mic, REC.cam].forEach(function (s) { if (s) s.getTracks().forEach(function (t) { t.stop(); }); });
  REC.mic = REC.cam = null; if (REC.ctx) { try { REC.ctx.close(); } catch (e) {} REC.ctx = null; }
  $('recLevel').style.transform = 'scaleX(0)'; $('recCamPrev').hidden = true; $('recCamPrev').srcObject = null;
  $('recMic').checked = false; $('recCam').checked = false;
}
function recReset(hidePanel) {
  if (REC.mr && REC.mr.state !== 'inactive') { try { REC.mr.onstop = null; REC.mr.stop(); } catch (e) {} }
  clearInterval(REC.tick); REC.mr = null; REC.blob = null; REC.chunks = [];
  recStopStreams();
  $('recGo').disabled = true; $('recGo').textContent = 'Record'; $('recGo').classList.remove('live'); $('recTime').textContent = '0:00';
  $('recSave').hidden = true; $('recRetry').hidden = true; $('recGo').hidden = false;
  recMsg('Turn on the microphone, press Record, and talk while the video plays. Wear headphones if the video has sound.');
  if (hidePanel) $('rec').hidden = true;
}
function recAvail() { $('recGo').disabled = !(REC.mic || REC.cam) || !!REC.blob; }
function recErr(e, what) {
  var n = e && e.name; recMsg(n === 'NotAllowedError' || n === 'SecurityError' ? 'Windows did not allow the ' + what + '. Turn it on in Windows Settings > Privacy & security, then try again.'
    : n === 'NotFoundError' ? 'No ' + what + ' was found on this PC.' : 'Could not start the ' + what + '.');
}
$('recToggle').addEventListener('click', function () { var p = $('rec'); if (p.hidden) { p.hidden = false; } else recReset(true); });
$('recClose').addEventListener('click', function () { recReset(true); });
$('recMic').addEventListener('change', function () {
  var box = this;
  if (REC.mr && REC.mr.state === 'recording') { box.checked = !!REC.mic; return; }
  if (!box.checked) { if (REC.mic) REC.mic.getTracks().forEach(function (t) { t.stop(); }); REC.mic = null; cancelAnimationFrame(REC.raf); $('recLevel').style.transform = 'scaleX(0)'; recAvail(); return; }
  if (!navigator.mediaDevices) { box.checked = false; return recMsg('Recording is not available in this window.'); }
  navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(function (s) {
    REC.mic = s;
    try {
      REC.ctx = REC.ctx || new (window.AudioContext || window.webkitAudioContext)();
      var an = REC.ctx.createAnalyser(); an.fftSize = 512; REC.ctx.createMediaStreamSource(s).connect(an); var buf = new Uint8Array(an.fftSize);
      (function loop() { an.getByteTimeDomainData(buf); var m = 0; for (var i = 0; i < buf.length; i++) m = Math.max(m, Math.abs(buf[i] - 128)); $('recLevel').style.transform = 'scaleX(' + Math.min(1, m / 60) + ')'; REC.raf = requestAnimationFrame(loop); })();
    } catch (e) {}
    recAvail(); recMsg('Microphone is on. Speak and watch the level bar move, then press Record.');
  }).catch(function (e) { box.checked = false; recErr(e, 'microphone'); });
});
$('recCam').addEventListener('change', function () {
  var box = this;
  if (REC.mr && REC.mr.state === 'recording') { box.checked = !!REC.cam; return; }
  if (!box.checked) { if (REC.cam) REC.cam.getTracks().forEach(function (t) { t.stop(); }); REC.cam = null; $('recCamPrev').hidden = true; $('recCamPrev').srcObject = null; recAvail(); return; }
  if (!navigator.mediaDevices) { box.checked = false; return recMsg('Recording is not available in this window.'); }
  navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360 } }).then(function (s) {
    REC.cam = s; var v = $('recCamPrev'); v.srcObject = s; v.hidden = false; v.play().catch(function () {}); recAvail(); recMsg('Camera is on. It will appear in the corner of the saved video.');
  }).catch(function (e) { box.checked = false; recErr(e, 'camera'); });
});
function recFmt(s) { s = Math.floor(s); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
$('recGo').addEventListener('click', function () {
  var v = recVideo(), go = this;
  if (REC.mr && REC.mr.state === 'recording') { REC.mr.stop(); return; }
  if (!v) return recMsg('The video is not ready.');
  var tracks = [].concat(REC.mic ? REC.mic.getAudioTracks() : [], REC.cam ? REC.cam.getVideoTracks() : []);
  if (!tracks.length) return;
  var stream = new MediaStream(tracks), mime = '';
  ['video/webm;codecs=vp8,opus', 'video/webm', 'audio/webm;codecs=opus', 'audio/webm'].some(function (m) { if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) { mime = m; return true; } });
  if (!window.MediaRecorder) return recMsg('Recording is not supported in this window.');
  if (!REC.cam) mime = mime.indexOf('audio') === 0 ? mime : 'audio/webm';
  try { REC.mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined); } catch (e) { return recMsg('Could not start recording.'); }
  REC.chunks = []; REC.hasCam = !!REC.cam;
  REC.mr.ondataavailable = function (e) { if (e.data && e.data.size) REC.chunks.push(e.data); };
  REC.mr.onstop = function () {
    clearInterval(REC.tick); v.pause(); v.onended = null; v.muted = false;
    REC.dur = v.duration && isFinite(v.duration) ? v.duration : (performance.now() - REC.t0) / 1000;
    REC.blob = new Blob(REC.chunks, { type: REC.mr.mimeType || 'video/webm' });
    recStopStreams();
    go.hidden = true; $('recSave').hidden = false; $('recRetry').hidden = false; $('recGo').classList.remove('live'); go.textContent = 'Record';
    recMsg('Recorded ' + recFmt(REC.dur) + '. Save it onto the video, or discard and try again.');
  };
  v.muted = true; v.currentTime = 0; v.controls = false;
  v.onended = function () { if (REC.mr && REC.mr.state === 'recording') REC.mr.stop(); };
  REC.mr.start(500); REC.t0 = performance.now(); v.play().catch(function () {});
  go.textContent = 'Stop'; go.classList.add('live'); recMsg('Recording. Talk now. It stops when the video ends, or press Stop.');
  REC.tick = setInterval(function () { $('recTime').textContent = recFmt((performance.now() - REC.t0) / 1000); }, 250);
});
$('recRetry').addEventListener('click', function () { var v = recVideo(); if (v) { v.controls = true; v.currentTime = 0; } recReset(false); });
$('recSave').addEventListener('click', function () {
  var o = P.list[P.i], btn = this; if (!o || !REC.blob) return;
  btn.disabled = true; recMsg('Putting your voice on the video. This takes a few seconds…');
  fetch('/api/record?path=' + encodeURIComponent(o.path) + '&cam=' + (REC.hasCam ? 1 : 0) + '&dur=' + REC.dur.toFixed(3), { method: 'POST', headers: { 'X-Token': TOKEN }, body: REC.blob })
    .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'Could not save'); return j; }); })
    .then(function (entry) {
      btn.disabled = false; var list = P.list.concat([entry]); setPreview(list, list.length - 1);
      toast('Saved ' + entry.name);
    }).catch(function (e) { btn.disabled = false; recMsg(e.message); });
});
$('previewSel').addEventListener('change', function () { P.i = parseInt(this.value, 10) || 0; showPreview(); });
$('filmLib').addEventListener('click', function () { if (window.MGXLibrary) window.MGXLibrary.open(); });
$('editVidBtn').addEventListener('click', function () { var o = P.list[P.i]; if (o && o.path && window.MGXProject) window.MGXProject.editVideo(o.path); });
$('previewOpen').addEventListener('click', function () { var o = P.list[P.i]; if (o) playOutput(o); });
$('previewFolder').addEventListener('click', openFolder);
function playOutput(o) {
  if (!o) return;
  if (DEMO || !o.path) { toast('Demo: this opens ' + o.name); return; }
  api('/api/open-file', { path: o.path }).catch(function (e) { toast(e.message); });
}

/* ---------------------------------------------------------------- the dock: progress under the code */
var R = { state: 'idle', kind: 'render', engine: 'manimgx', pct: 0, scene: '', current: 0, res: '', fps: null, videoSec: null, elapsed: 0, eta: null,
          log: [], outputs: [], warnings: [], failed: [], items: [], error: null, scenes: [] };
var dock = $('dock'), built = '', confirming = false, logOpen = false, notesOpen = false, lastSaid = -1, minimizedNote = false;
var INS = { state: 'idle', step: '', elapsed: 0, error: null };

function dockRows() { return dock; }
function barHTML(pct, indet) { return '<div class="dock-row"><div class="bar' + (indet ? ' indet' : '') + '" role="progressbar" aria-label="Progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '"><i style="transform:scaleX(' + (pct / 100) + ')"></i></div></div>'; }
function queueHTML() {
  return R.items.map(function (it, i) {
    var st = it.state === 'done' ? 'done' + (it.seconds ? ' ' + fmt(it.seconds) : '') : it.state === 'running' ? Math.floor(it.percent || 0) + '%' : it.state === 'error' ? 'failed' : it.state === 'cancelled' ? 'stopped' : 'queued';
    return '<li class="q-' + it.state + (i === R.current && R.state === 'running' ? ' cur' : '') + '"><i class="d"></i>' + esc(it.scene) + ' <span class="st">' + st + '</span></li>';
  }).join('');
}
function notesHTML() {
  var w = R.warnings || [];
  if (!w.length) return '';
  return '<button class="disc" id="notesToggle" aria-expanded="' + notesOpen + '"><svg class="ic sm"><use href="#i-chev"/></svg>' + w.length + ' layout note' + (w.length === 1 ? '' : 's') + ' (click one to jump to its line)</button>' +
    '<ul class="notes" id="notesBox"' + (notesOpen ? '' : ' hidden') + '>' + w.map(function (x) {
      return '<li><button data-line="' + x.line + '"><b>Line ' + x.line + '</b><span>' + esc(x.text) + (R.items.length > 1 ? ' (' + esc(x.scene) + ')' : '') + '</span></button></li>'; }).join('') + '</ul>';
}
function logHTML(text) {
  return '<button class="disc" id="logToggle" aria-expanded="' + logOpen + '"><svg class="ic sm"><use href="#i-chev"/></svg>' + (logOpen ? 'Hide details' : 'Show details') + '</button>' +
    '<pre class="log" id="logBox"' + (logOpen ? '' : ' hidden') + '>' + esc(text || 'Waiting for output\u2026') + '</pre>';
}
function applyMarks() {
  var m = {};
  (R.warnings || []).forEach(function (x) { m[x.line] = 'warn'; });
  if (R.error && R.error.line) m[R.error.line] = 'err';
  (R.failed || []).forEach(function (f) { if (f.error && f.error.line) m[f.error.line] = 'err'; });
  cm.setMarks(m);
}
function dockState() { return INS.state === 'running' ? 'installing' : R.state; }

function paintDock() {
  var st = dockState(), many = R.items.length > 1, pct = Math.floor(R.pct);
  dock.dataset.state = st;
  document.title = st === 'running' ? pct + '% \u00b7 Manimo' : st === 'done' ? 'Done \u00b7 Manimo' : 'Manimo';
  var key = st + '|' + (st === 'running' ? many : '') ;
  if (st === 'idle') {
    var chk = validity();
    var line = !code.value.trim() ? 'Add some code to begin' : !chk.ok ? chk.msg : selScene === ALL ? 'Ready to render all ' + chk.scenes.length + ' scenes, one after another' : 'Ready to render ' + selScene;
    dock.innerHTML = '<div class="dock-row"><i class="dot"></i><div class="dock-title" id="dockTitle">' + esc(line) + '</div><span class="dock-meta">' + esc(QUALITY[S.quality][0]) + '</span></div>' + barHTML(0, false);
    built = key; return;
  }
  if (st === 'installing') {
    if (built !== key) { built = key; dock.innerHTML = '<div class="dock-row"><i class="dot"></i><div class="dock-title">Adding Manim\u2026 <small>this downloads about 100 MB, once</small></div><span class="dock-meta" id="insMeta"></span></div>' + barHTML(0, true) + '<div class="dock-body"><p class="dock-line" id="insStep"></p></div>'; }
    $('insMeta').textContent = fmt(INS.elapsed); $('insStep').textContent = INS.step || ''; return;
  }
  if (st === 'running') {
    if (built !== key) {
      built = key; confirming = false;
      dock.innerHTML = '<div class="dock-row"><i class="dot"></i><div class="dock-title" id="dockTitle"></div><span class="dock-pct" id="dPct">0%</span><span class="dock-meta" id="dEta"></span><span id="dCancel"></span></div>' +
        barHTML(0, false) + (many ? '<div class="dock-row"><ul class="queue" id="dQueue" aria-label="Scenes in this render"></ul></div>' : '') +
        '<div class="dock-row"><span class="dock-meta" id="dStats"></span><span class="spacer"></span><span id="dLogToggle"></span></div><div class="dock-body" id="dLog"></div>';
      drawCancel(); $('dLogToggle').innerHTML = ''; $('dLog').innerHTML = logHTML(R.log.join('\n'));
    }
    var name = R.scene || 'animation', ce = R.engine === 'manim';
    $('dockTitle').innerHTML = esc(many ? 'Rendering ' + (R.current + 1) + ' of ' + R.items.length + ': ' + name : (R.pct < 1 ? 'Preparing ' + name + '\u2026' : (R.kind === 'present' ? 'Building slideshow: ' : 'Rendering ') + name)) + (ce ? ' <small>Manim</small>' : '');
    $('dPct').textContent = pct + '%';
    $('dEta').textContent = R.eta == null ? 'Estimating\u2026' : '~' + fmt(R.eta) + ' left';
    var bar = dock.querySelector('.bar'); bar.firstChild.style.transform = 'scaleX(' + (R.pct / 100) + ')'; bar.setAttribute('aria-valuenow', pct);
    if (many) $('dQueue').innerHTML = queueHTML();
    $('dStats').textContent = 'Elapsed ' + fmt(R.elapsed) + ' \u00b7 ' + (R.res || '').replace('x', '\u00d7') + (R.fps ? ' \u00b7 ' + R.fps + ' fps' : '') + (ce ? '' : ' \u00b7 progress is estimated');
    var lb = $('logBox'); if (lb && logOpen) { lb.textContent = R.log.join('\n') || 'Waiting for output\u2026'; lb.scrollTop = lb.scrollHeight; }
    if (pct >= lastSaid + 25) { lastSaid = pct - (pct % 25); say('Rendering ' + pct + ' percent'); }
    return;
  }
  if (built === key + R.outputs.length + R.warnings.length && st !== 'running') return;
  built = key + R.outputs.length + R.warnings.length;
  if (st === 'done') {
    R.videos = R.outputs.filter(function (o) { return o.kind !== 'slides'; });
    var slides = R.outputs.filter(function (o) { return o.kind === 'slides'; })[0], n = R.videos.length, present = R.kind === 'present';
    var heading = present ? 'Your slideshow is ready' : n > 1 ? n + ' videos are ready' : 'Your video is ready';
    var fails = (R.failed || []).map(function (f) { return f.scene; });
    var failLine = (R.failed || []).filter(function (f) { return f.error && f.error.line; })[0];
    var sub = (R.videoSec && n === 1 ? R.videoSec.toFixed(1) + ' s of video \u00b7 ' : '') + 'rendered in ' + fmt(R.elapsed) + ' \u00b7 saved to ' + shortPath(outDir);
    dock.innerHTML = '<div class="dock-row"><span class="badge"><svg class="ic"><use href="#i-check"/></svg></span><div class="dock-title">' + esc(heading) + '<small>' + esc(sub) + '</small></div>' +
      '<div class="dock-actions"><button class="btn primary sm" id="aShow"><svg class="ic sm"><use href="#i-play"/></svg>' + (slides ? 'Show slideshow' : 'Play in preview') + '</button>' +
      '<button class="btn sm" id="aFolder"><svg class="ic sm"><use href="#i-folder"/></svg>Open folder</button><button class="btn ghost sm" id="aAgain">Render again</button><button class="icon-btn" id="aClose" aria-label="Dismiss" title="Dismiss"><svg class="ic sm"><use href="#i-x"/></svg></button></div></div>' + barHTML(100, false) +
      ((fails.length || R.warnings.length) ? '<div class="dock-body">' + (fails.length ? '<p class="dock-line warn">' + fails.length + ' scene' + (fails.length === 1 ? '' : 's') + ' failed: ' + esc(fails.join(', ')) + (failLine ? ' \u00b7 <button class="disc" data-line="' + failLine.error.line + '">show line ' + failLine.error.line + '</button>' : '') + '</p>' : '') + notesHTML() + '</div>' : '');
    $('aShow').onclick = function () { var i = Math.max(0, P.list.indexOf(slides || R.videos[0])); P.i = i; setPreview(P.list, i); if (narrow.matches) setView('preview'); };
    $('aFolder').onclick = openFolder; $('aAgain').onclick = function () { var k = R.kind; startRender(k); }; $('aClose').onclick = dismissDock;
    say(heading + '.');
  } else if (st === 'error') {
    var eline = R.error && R.error.line;
    dock.innerHTML = '<div class="dock-row"><span class="badge bad"><svg class="ic"><use href="#i-alert"/></svg></span><div class="dock-title">' + esc((R.error && R.error.title) || 'The render could not finish.') + '</div>' +
      '<div class="dock-actions"><button class="btn primary sm" id="aRetry">Try again</button>' + (eline ? '<button class="btn sm" data-line="' + eline + '">Show line ' + eline + '</button>' : '') +
      '<button class="btn ghost sm" id="aCopy"><svg class="ic sm"><use href="#i-copy"/></svg>Copy details</button><button class="icon-btn" id="aClose" aria-label="Dismiss"><svg class="ic sm"><use href="#i-x"/></svg></button></div></div>' + barHTML(100, false) +
      '<div class="dock-body">' + notesHTML() + logHTML((R.error && R.error.detail) || R.log.join('\n')) + '</div>';
    $('aRetry').onclick = function () { startRender(R.kind); }; $('aClose').onclick = dismissDock;
    $('aCopy').onclick = function () { var t = (R.error && R.error.detail) || R.log.join('\n'); (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { toast('Details copied'); }, function () { toast('Could not copy. Select the text manually.'); }); };
    say('Render failed. ' + ((R.error && R.error.title) || ''));
  } else if (st === 'cancelled') {
    dock.innerHTML = '<div class="dock-row"><span class="badge neutral"><svg class="ic"><use href="#i-stop"/></svg></span><div class="dock-title">Stopped<small>' + (R.items.length > 1 ? 'Videos finished before you stopped are kept.' : 'Nothing was saved.') + '</small></div>' +
      '<div class="dock-actions"><button class="btn primary sm" id="aRestart">Start over</button><button class="icon-btn" id="aClose" aria-label="Dismiss"><svg class="ic sm"><use href="#i-x"/></svg></button></div></div>' + barHTML(0, false);
    $('aRestart').onclick = function () { startRender(R.kind); }; $('aClose').onclick = dismissDock; say('Render stopped.');
  }
}
function drawCancel() {
  var box = $('dCancel'); if (!box) return;
  if (confirming) {
    box.innerHTML = '<span class="dock-actions"><span style="font-weight:500">Stop this render?</span><button class="btn sm" id="cKeep">Keep going</button><button class="btn sm danger" id="cStop">Stop</button></span>';
    $('cKeep').onclick = function () { confirming = false; drawCancel(); }; $('cStop').onclick = cancelRender; $('cKeep').focus();
  } else {
    box.innerHTML = '<button class="btn sm danger" id="aCancel"><svg class="ic sm"><use href="#i-x"/></svg>Cancel</button>';
    $('aCancel').onclick = function () { confirming = true; drawCancel(); };
  }
}
document.addEventListener('click', function (e) {
  var n = e.target.closest('#notesToggle');
  if (n) { notesOpen = !notesOpen; n.setAttribute('aria-expanded', notesOpen); var nb = $('notesBox'); if (nb) nb.hidden = !notesOpen; return; }
  var t = e.target.closest('#logToggle');
  if (t) {
    logOpen = !logOpen; t.setAttribute('aria-expanded', logOpen); t.lastChild.textContent = logOpen ? 'Hide details' : 'Show details';
    var lb = $('logBox'); lb.hidden = !logOpen;
    if (logOpen) { lb.textContent = (R.state === 'error' && R.error && R.error.detail) || R.log.join('\n') || 'Waiting for output\u2026'; lb.scrollTop = lb.scrollHeight; }
  }
});
function dismissDock() { R.state = 'idle'; built = ''; paintDock(); paintStart(); }

function paintStart() {
  var b = $('startBtn'), running = R.state === 'running', busy = running || INS.state === 'running', chk = validity();
  b.querySelector('use').setAttribute('href', running ? '#i-stop' : '#i-play');
  $('startLbl').innerHTML = running ? 'Rendering <span class="num">' + Math.floor(R.pct) + '%</span>' : selScene === ALL ? 'Render all scenes' : 'Start Rendering';
  $('startKbd').hidden = busy || phone.matches;
  b.setAttribute('aria-disabled', (!busy && !chk.ok) ? 'true' : 'false');
  b.title = running ? 'Click to see progress' : chk.ok ? 'Render (Ctrl+Enter)' : chk.msg;
  var pb = $('presentBtn'), gx = chk.ok && chk.engine === 'manimgx';
  pb.hidden = !gx || busy;
  pb.setAttribute('aria-disabled', selScene === ALL ? 'true' : 'false');
  var pmsg = selScene === ALL ? 'Present: pick one scene first' : 'Present: play this scene as slides';
  pb.setAttribute('data-tip', pmsg); pb.setAttribute('aria-label', pmsg);
}

/* ---------------------------------------------------------------- rendering */
var poller = null, afterInstall = null;
function startRender(kind) {
  kind = kind === 'present' ? 'present' : 'render';
  if (R.state === 'running') return;
  if (INS.state === 'running') { toast('Manim is still being added. One moment.'); return; }
  var chk = validity();
  if (!chk.ok) { toast(chk.msg); if (!code.value.trim()) $('empty').hidden = false; else cm.focus(); return; }
  if (kind === 'present' && selScene === ALL) { toast('Pick one scene in the Scene menu to present it'); return; }
  if (!DEMO && !engineReady(chk.engine)) {
    if (chk.engine === 'manim') {
      if (window.confirm('This code is written for Manim (Community Edition), which is not added yet.\n\nAdd it now? It downloads about 100 MB, once.')) { afterInstall = function () { startRender(kind); }; installManim(); }
      return;
    }
    toast('The ManimGX engine is not installed. Re-run the Manimo installer to repair.'); return;
  }
  closeSettings(false);
  var targets = selScene === ALL ? chk.scenes : [selScene];
  R = { state: 'running', kind: kind, engine: chk.engine, pct: 0, scene: targets[0], current: 0, res: QUALITY[S.quality][1], fps: S.fps === 'auto' ? null : S.fps, videoSec: null,
        elapsed: 0, eta: null, log: [], outputs: [], warnings: [], failed: [], error: null, scenes: chk.scenes,
        items: targets.map(function (s) { return { scene: s, state: 'queued', percent: 0 }; }) };
  cm.clearMarks(); built = ''; lastSaid = -1; confirming = false;
  paintStart(); paintDock(); say('Render started');
  if (DEMO) { simulate(); return; }
  var inProject = !!(window.MGXProject && window.MGXProject.active());
  (inProject ? window.MGXProject.beforeRender() : Promise.resolve())
    .then(function () { return api('/api/render', Object.assign({ code: code.value, scenes: targets, kind: kind, quality: S.quality, shape: S.shape, fps: S.fps, encoding: S.encoding, out_dir: outDir }, voiceOpts(), inProject ? { project_file: curName } : {})); })
    .then(function () { poll(); })
    .catch(function (e) { R.state = 'error'; R.error = { title: e.message, detail: e.message }; built = ''; paintDock(); paintStart(); });
}
function finishRender() {
  applyMarks();
  var vids = R.outputs.filter(function (o) { return o.kind !== 'slides'; }), slides = R.outputs.filter(function (o) { return o.kind === 'slides'; });
  if (window.MGXProject) window.MGXProject.refresh();
  if (R.state === 'done' && R.outputs.length) {
    addHistory(R.outputs);
    var list = slides.concat(vids); setPreview(list, 0); if (!AI.busy) rightTab('preview'); if (narrow.matches) setView('preview');
  }
}
function poll() {
  clearInterval(poller);
  poller = setInterval(function () {
    api('/api/job').then(function (j) {
      R.pct = j.percent || 0; R.scene = j.scene || R.scene; R.res = j.resolution || R.res; R.fps = j.fps || R.fps; R.videoSec = j.video_seconds || null; R.engine = j.engine || R.engine;
      R.elapsed = j.elapsed || R.elapsed; R.eta = j.eta; R.log = j.log || []; R.outputs = j.outputs || []; R.error = j.error;
      R.items = j.items || R.items; R.current = j.current || 0; R.warnings = j.warnings || []; R.failed = j.failed || []; R.kind = j.kind || R.kind;
      if (j.state === 'done' || j.state === 'error' || j.state === 'cancelled') {
        clearInterval(poller); R.state = j.state; if (j.state === 'done') R.pct = 100; built = ''; finishRender();
      }
      paintDock(); paintStart();
    }).catch(function () { /* transient; the next tick retries */ });
  }, 450);
}
function cancelRender() {
  if (DEMO) { clearInterval(sim.t); R.state = 'cancelled'; built = ''; paintDock(); paintStart(); return; }
  api('/api/cancel', {}).then(function () { clearInterval(poller); R.state = 'cancelled'; built = ''; paintDock(); paintStart(); }).catch(function (e) { toast(e.message); });
}
$('startBtn').addEventListener('click', function () {
  if (R.state === 'running') { var c = $('aCancel'); if (c) c.focus(); return; }
  if (R.state !== 'idle') dismissDock();
  startRender();
});
$('presentBtn').addEventListener('click', function () { if (R.state !== 'idle' && R.state !== 'running') dismissDock(); startRender('present'); });

/* simulated render for the standalone preview (no server) */
var sim = { t: null };
function simulate() {
  var per = R.items.map(function () { return 3 + Math.random() * 2; }), total = per.reduce(function (a, b) { return a + b; }, 0), t0 = performance.now(), present = R.kind === 'present';
  clearInterval(sim.t);
  sim.t = setInterval(function () {
    var el = (performance.now() - t0) / 1000, acc = 0, finished = true;
    R.items.forEach(function (it, i) {
      if (el >= acc + per[i]) { it.state = 'done'; it.percent = 100; it.seconds = per[i]; }
      else if (el > acc) { it.state = 'running'; it.percent = 100 * (el - acc) / per[i]; R.current = i; R.scene = it.scene; finished = false; }
      else { it.state = 'queued'; finished = false; }
      acc += per[i];
    });
    R.elapsed = el; R.pct = Math.min(99, 100 * el / total); R.eta = Math.max(total - el, 1);
    if (finished) {
      clearInterval(sim.t); R.state = 'done'; R.pct = 100; R.eta = 0; built = ''; R.videoSec = 17.8;
      R.outputs = present ? [{ name: R.items[0].scene + ' slideshow', path: '', kind: 'slides' }, { name: R.items[0].scene + '.mp4', path: '', kind: 'video' }]
        : R.items.map(function (it) { return { name: it.scene + '.mp4', path: '', kind: 'video' }; });
      R.warnings = [{ scene: R.items[0].scene, line: 6, t: '1.2s', text: "title (Text 'Hello') and circle (Circle): texts overlap" }];
      finishRender();
    }
    paintDock(); paintStart();
  }, 120);
}
window.__manimo = { fail: function () { clearInterval(sim.t); R.state = 'error'; R.error = { title: 'The code uses a name that is not defined. Did you forget the import line at the top?', line: 7, detail: 'NameError: name \'undefined_name\' is not defined' }; applyMarks(); built = ''; paintDock(); paintStart(); } };

/* ---------------------------------------------------------------- adding Manim (Community Edition) */
var insPoller = null;
function installManim() {
  if (DEMO) { toast('Demo: this downloads Manim in the installed app'); return; }
  closeSettings(false);
  api('/api/install-engine', { engine: 'manim' }).then(function () {
    INS = { state: 'running', step: 'Contacting the package index\u2026', elapsed: 0, error: null }; built = ''; paintDock(); paintStart();
    clearInterval(insPoller);
    insPoller = setInterval(function () {
      api('/api/install').then(function (j) {
        INS.step = j.step || INS.step; INS.elapsed = j.elapsed || INS.elapsed;
        if (j.state === 'done' || j.state === 'error') {
          clearInterval(insPoller); INS = { state: j.state, step: '', elapsed: 0, error: j.error || null }; built = '';
          refreshStatus().then(function () {
            if (j.state === 'done') { toast('Manim is ready'); var go = afterInstall; afterInstall = null; paintDock(); paintStart(); if (go) go(); }
            else { afterInstall = null; INS.state = 'idle'; toast(j.error || 'Could not add Manim'); paintDock(); paintStart(); }
          });
        } else paintDock();
      }).catch(function () {});
    }, 700);
  }).catch(function (e) { toast(e.message); });
}
$('addManim').addEventListener('click', installManim);

/* ---------------------------------------------------------------- menus */
var menuEl = $('menu'), openId = null;
function mi(label, key, run, opts) { return Object.assign({ label: label, key: key || '', run: run }, opts || {}); }
function menuItems(id) {
  if (id === 'file') {
    var items = (window.MGXProject ? window.MGXProject.menu() : []).concat([mi('New file', 'Ctrl+N', newFile), mi('Open\u2026', 'Ctrl+O', openFile), mi('Save', 'Ctrl+S', function () { saveFile(false); }), mi('Save as\u2026', 'Ctrl+Shift+S', function () { saveFile(true); }), { sep: true }, mi('My videos\u2026', '', function () { if (window.MGXLibrary) window.MGXLibrary.open(); }), { sep: true }, { head: 'Examples' }]);
    EXAMPLES.forEach(function (ex, i) { items.push(mi(ex.name, '', function () { loadExample(i); })); });
    items.push({ sep: true }, mi('Exit', 'Alt+F4', exitApp));
    return items;
  }
  if (id === 'edit') return [
    mi('Undo', 'Ctrl+Z', function () { cm.run('undo'); }), mi('Redo', 'Ctrl+Y', function () { cm.run('redo'); }), { sep: true },
    mi('Cut', 'Ctrl+X', function () { cm.run('cut'); }), mi('Copy', 'Ctrl+C', function () { cm.run('copy'); }), mi('Paste', 'Ctrl+V', function () { cm.run('paste'); }), { sep: true },
    mi('Select all', 'Ctrl+A', function () { cm.run('selectAll'); }), { sep: true },
    mi('Find\u2026', 'Ctrl+F', function () { cm.run('find'); }), mi('Find and replace\u2026', 'Ctrl+H', function () { cm.run('find'); })
  ];
  if (id === 'session') {
    var s = [mi('New session', '', newSession), mi('Save session\u2026', '', saveSession), mi('Open session\u2026', '', openSession), { sep: true }, { head: 'Recent renders' }];
    if (!history.length) s.push(mi('Nothing rendered yet', '', null, { disabled: true }));
    history.slice(0, 8).forEach(function (h) { s.push(mi(h.name, '', function () { openHistory(h); })); });
    s.push({ sep: true }, mi('Clear history', '', function () { history = []; store('mgx-history', '[]'); toast('History cleared'); }, { disabled: !history.length }), { sep: true },
      { head: 'Your work is saved automatically and comes back next time.' });
    return s;
  }
  return [
    mi('Ask the AI assistant', 'Ctrl+L', function () { rightTab('assistant'); }), mi('AI settings\u2026', '', openAISettings), { sep: true },
    mi('How to use Manimo', 'F1', function () { openDialog('helpDlg'); }), mi('Keyboard shortcuts', '', function () { openDialog('helpDlg'); var l = $('shortcutList'); if (l) l.scrollIntoView({ block: 'start' }); }),
    mi('Learn and commands', '', function () { openDialog('learnDlg'); }), mi('Lesson prompt\u2026', '', openPrompt),
    mi('Report a problem\u2026', '', openReport), mi('Check my setup', '', openSetup), { sep: true },
    mi('ManimGX documentation', '', function () { openUrl('https://manimgx.academa.ai/'); }), mi('Manim documentation', '', function () { openUrl('https://docs.manim.community/'); }), { sep: true },
    mi('About Manimo', '', function () { openDialog('aboutDlg'); })
  ];
}
function openMenu(id, btn) {
  closeSettings(false);
  var items = menuItems(id);
  menuEl.innerHTML = items.map(function (it, i) {
    if (it.sep) return '<div class="m-sep" role="separator"></div>';
    if (it.head) return '<div class="m-head">' + esc(it.head) + '</div>';
    return '<button class="mi" role="menuitem" data-i="' + i + '"' + (it.disabled ? ' aria-disabled="true"' : '') + '><span class="t">' + esc(it.label) + '</span>' + (it.key ? '<span class="k">' + esc(it.key) + '</span>' : '') + '</button>';
  }).join('');
  menuEl._items = items;
  var r = btn.getBoundingClientRect();
  menuEl.hidden = false;
  var w = menuEl.offsetWidth; menuEl.style.left = Math.max(6, Math.min(r.left, innerWidth - w - 6)) + 'px'; menuEl.style.top = (r.bottom + 4) + 'px';
  document.querySelectorAll('.menubtn').forEach(function (b) { b.setAttribute('aria-expanded', String(b === btn)); });
  openId = id;
  var first = menuEl.querySelector('.mi:not([aria-disabled])'); if (first) first.focus({ preventScroll: true });
}
function closeMenu() {
  if (menuEl.hidden) return;
  menuEl.hidden = true; openId = null;
  document.querySelectorAll('.menubtn').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
}
document.querySelectorAll('.menubtn').forEach(function (b) {
  b.addEventListener('click', function () { openId === b.dataset.menu ? closeMenu() : openMenu(b.dataset.menu, b); });
  b.addEventListener('mouseenter', function () { if (openId && openId !== b.dataset.menu) openMenu(b.dataset.menu, b); });
});
menuEl.addEventListener('click', function (e) {
  var b = e.target.closest('.mi'); if (!b || b.getAttribute('aria-disabled') === 'true') return;
  var it = menuEl._items[parseInt(b.dataset.i, 10)]; closeMenu(); if (it && it.run) setTimeout(it.run, 0);
});
menuEl.addEventListener('keydown', function (e) {
  var btns = [].slice.call(menuEl.querySelectorAll('.mi:not([aria-disabled])')), i = btns.indexOf(document.activeElement), tabs = [].slice.call(document.querySelectorAll('.menubtn'));
  var ti = tabs.findIndex(function (b) { return b.dataset.menu === openId; });
  if (e.key === 'ArrowDown') { e.preventDefault(); btns[(i + 1) % btns.length].focus(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); btns[(i - 1 + btns.length) % btns.length].focus(); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); var nb = tabs[(ti + 1) % tabs.length]; openMenu(nb.dataset.menu, nb); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); var pb = tabs[(ti - 1 + tabs.length) % tabs.length]; openMenu(pb.dataset.menu, pb); }
  else if (e.key === 'Escape') { e.preventDefault(); var btn = tabs[ti]; closeMenu(); if (btn) btn.focus(); }
});
document.addEventListener('pointerdown', function (e) { if (!menuEl.hidden && !menuEl.contains(e.target) && !e.target.closest('.menubtn')) closeMenu(); });
window.addEventListener('blur', closeMenu);
function exitApp() {
  if (dirty && !window.confirm('You have unsaved changes. Exit anyway?')) return;
  if (DEMO) { window.close(); return; }
  api('/api/quit', {}).catch(function () { window.close(); });
}

/* ---------------------------------------------------------------- dialogs */
function openDialog(id) { closeMenu(); closeSettings(false); var d = $(id); if (!d.open) d.showModal(); fillAbout(); }
function closeAllDialogs() { document.querySelectorAll('dialog[open]').forEach(function (d) { d.close(); }); }
document.querySelectorAll('dialog.dlg').forEach(function (d) {
  d.addEventListener('click', function (e) { if (e.target === d) d.close(); });
  d.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', function () { d.close(); }); });
});
function fillAbout() {
  var e = info.engines || {};
  $('aboutVersion').textContent = info.version ? 'Version ' + info.version : '';
  $('aboutGx').textContent = e.manimgx && e.manimgx !== 'demo' ? e.manimgx : '';
  $('aboutCe').textContent = e.manim ? e.manim : '(not added)';
  $('aboutPy').textContent = info.python || '';
}
/* learn and reference */
var LEARN_CMDS = [
  ['Every video', [
    ['class Name(m.Scene):', 'Starts one video. The name appears in the scene picker.'],
    ['def construct(self):', 'The steps of the video, from top to bottom.'],
    ['self.play(...)', 'Plays animations together, then waits for them to finish.'],
    ['self.wait(2)', 'Pauses for two seconds.'],
    ['self.next_section("Name")', 'Starts a new part. Present mode pauses here.'],
    ['self.say("Hello [world]", m.Write(x))', 'Speaks the sentence. The bracketed words start the animation.']]],
  ['Shapes and text', [
    ['m.Circle(radius=1, color=m.BLUE)', 'A circle.'], ['m.Square() / m.Rectangle(width=4, height=2)', 'Boxes.'],
    ['m.Line(a, b) / m.Arrow(a, b)', 'A line or arrow between two points.'], ['m.Dot(point)', 'A small dot.'],
    ['m.Text("Hello", font_size=36)', 'Plain text.'], ['m.MathTex(r"x^2 + 1")', 'A formula, typeset like a textbook.'],
    ['m.VGroup(a, b, c)', 'Treats several things as one.']]],
  ['Animations', [
    ['m.Create(x)', 'Draws a shape.'], ['m.Write(x)', 'Writes text or a formula by hand.'], ['m.FadeIn(x) / m.FadeOut(x)', 'Appear and disappear.'],
    ['m.Transform(a, b)', 'Turns a into b.'], ['m.ReplacementTransform(a, b)', 'Turns a into b and removes a.'],
    ['m.Indicate(x)', 'A quick highlight.'], ['x.animate.shift(m.UP)', 'Any change, made smooth.'], ['run_time=2', 'How long an animation takes, in seconds.']]],
  ['Placing things', [
    ['x.shift(m.RIGHT * 2)', 'Move by a step.'], ['x.move_to([1, 2, 0])', 'Put at an exact spot.'], ['x.next_to(y, m.DOWN, buff=0.3)', 'Place beside another thing.'],
    ['x.to_edge(m.UP)', 'Push against a screen edge.'], ['group.arrange(m.DOWN)', 'Stack in a column.'], ['x.scale(2)', 'Twice as big.'],
    ['x.set_color(m.RED)', 'Change colour.'], ['x.set_opacity(0.5)', 'See-through.']]],
  ['Graphs and numbers', [
    ['m.Axes(x_range=[0, 5, 1], y_range=[0, 1, 0.5])', 'Axes with numbers.'], ['axes.c2p(2, 1)', 'Turn a graph point into a screen position.'],
    ['m.ParametricFunction(f, t_range=[0, 5])', 'A curve from a formula.'], ['t = m.ValueTracker(0)', 'A number you can animate.'],
    ['t.animate.set_value(3)', 'Animate that number.'], ['m.always_redraw(lambda: ...)', 'Rebuild a shape every frame.']]]
];
var LEARN_TRY = [
  ['run_time=2', 'Change the 2 to 5. The animation slows down.'], ['color=m.BLUE', 'Replace BLUE with RED, GREEN or YELLOW.'],
  ['font_size=36', 'Try 24, then 48, to see how the text scales.'], ['radius=1.5', 'Make it 0.5 or 3 and watch the circle change.'],
  ['self.wait(1)', 'Add a longer wait before the next step to give viewers time.'], ['m.RIGHT * 2', 'Change 2 to -2 to go the other way.']
];
var LEARN_LINKS = [
  ['3Blue1Brown on YouTube', 'The channel Manim was made for. See what finished videos look like.', 'https://www.youtube.com/@3blue1brown'],
  ['How 3Blue1Brown animates with Manim', 'A behind-the-scenes demo by its creator (search results).', 'https://www.youtube.com/results?search_query=How+I+animate+3Blue1Brown+Manim+demo'],
  ['Manim beginner tutorials', 'Video lessons for Manim Community Edition (search results).', 'https://www.youtube.com/results?search_query=manim+community+edition+tutorial+for+beginners'],
  ['Maths animation tutorials', 'More ideas for what you can make (search results).', 'https://www.youtube.com/results?search_query=manim+python+math+animation+tutorial'],
  ['ManimGX videos', 'Videos about the engine Manimo uses (search results).', 'https://www.youtube.com/results?search_query=manimgx'],
  ['ManimGX documentation', 'Every command and example for the engine in Manimo.', 'https://manimgx.academa.ai/'],
  ['Manim Community documentation', 'Quickstart, tutorials and the full reference.', 'https://docs.manim.community/en/stable/index.html'],
  ['Manim on GitHub', 'The community edition, with example scenes.', 'https://github.com/ManimCommunity/manim'],
  ['Which Manim should I use?', '3Blue1Brown explains the two versions.', 'https://3blue1brown.com/faq']
];
(function () {
  $('learnCmdList').innerHTML = LEARN_CMDS.map(function (g) {
    return '<h4 class="learn-g">' + esc(g[0]) + '</h4><table class="learn-t"><tbody>' + g[1].map(function (r) { return '<tr><td><code>' + esc(r[0]) + '</code></td><td>' + esc(r[1]) + '</td></tr>'; }).join('') + '</tbody></table>';
  }).join('');
  $('learnTryList').innerHTML = LEARN_TRY.map(function (r) { return '<li><code>' + esc(r[0]) + '</code> <span>' + esc(r[1]) + '</span></li>'; }).join('');
  $('learnLinkList').innerHTML = LEARN_LINKS.map(function (r) { return '<button class="learn-link" data-url="' + esc(r[2]) + '"><b>' + esc(r[0]) + '</b><span>' + esc(r[1]) + '</span></button>'; }).join('');
  $('learnBody').addEventListener('click', function (e) {
    var l = e.target.closest('[data-url]'); if (l) { openUrl(l.dataset.url); return; }
    var g = e.target.closest('[data-go]'); if (g) { var t = $(g.dataset.go); if (t) t.scrollIntoView({ block: 'start', behavior: reduceMotion.matches ? 'auto' : 'smooth' }); }
  });
  $('helpLearn').addEventListener('click', function () { $('helpDlg').close(); openDialog('learnDlg'); });
})();
$('aboutPortfolio').addEventListener('click', function () { openUrl('https://mathanmj92.github.io/mathan/'); });
$('aboutSetup').addEventListener('click', openSetup);
function setupLines() {
  var e = info.engines || {};
  return ['Manimo ' + (info.version || '(preview)'), 'Python ' + (info.python || '?') + (info.python_path ? '  (' + info.python_path + ')' : ''),
    'ManimGX: ' + (e.manimgx || 'not installed'), 'Manim Community: ' + (e.manim || 'not added'), 'LaTeX: ' + (info.latex ? (info.latex_version || 'found') + (info.latex_bundled ? ' (built into Manimo)' : ' (found on this PC)') : 'not found (only needed for MathTex with Manim)'),
    'Output folder: ' + outDir, 'Screen: ' + screen.width + '\u00d7' + screen.height + ' at ' + (window.devicePixelRatio || 1) * 100 + '% scaling', 'Window: ' + innerWidth + '\u00d7' + innerHeight, 'Look: ' + (root.dataset.look || root.dataset.theme)];
}
function openSetup() {
  closeAllDialogs();
  var lines = setupLines();
  $('setupText').textContent = lines.join('\n');
  if (navigator.gpu) navigator.gpu.requestAdapter().then(function (a) { if (a && a.info) $('setupText').textContent += '\nGraphics adapter: ' + [a.info.vendor, a.info.architecture, a.info.description].filter(Boolean).join(' ').trim(); }).catch(function () {});
  $('setupDlg').showModal();
}
function reportBody() {
  var what = $('reportWhat').value.trim(), parts = ['Manimo problem report', 'Date: ' + new Date().toString(), '', 'What happened:', what || '(not described)'];
  if ($('reportSetup').checked) parts.push('', 'Setup:', setupLines().join('\n'), 'Project: ' + ((window.MGXProject && window.MGXProject.active()) ? window.MGXProject.label() : 'none'), 'Window: ' + navigator.userAgent);
  if ($('reportLog').checked) { var log = (R.error && R.error.detail) || (R.log || []).slice(-40).join('\n'); parts.push('', 'Last render' + (R.state === 'error' ? ' (it failed)' : '') + ':', log || '(nothing rendered yet)'); }
  if ($('reportCode').checked) parts.push('', 'Code in the editor:', code.value || '(empty)');
  return parts.join('\n');
}
function openReport() { closeAllDialogs(); $('reportMsg').textContent = ''; $('reportText').textContent = reportBody(); $('reportDlg').showModal(); setTimeout(function () { $('reportWhat').focus(); }, 30); }
$('reportDlg').addEventListener('input', function () { $('reportText').textContent = reportBody(); });
$('reportDlg').addEventListener('change', function () { $('reportText').textContent = reportBody(); });
$('reportCopy').addEventListener('click', function () {
  (navigator.clipboard ? navigator.clipboard.writeText(reportBody()) : Promise.reject()).then(function () { $('reportMsg').textContent = 'Copied. Paste it into your message to the author.'; }, function () { $('reportMsg').textContent = 'Could not copy. Open "See exactly what will be in the report" and select the text.'; });
});
$('reportSave').addEventListener('click', function () {
  if (DEMO) { $('reportMsg').textContent = 'Saving works in the installed app.'; return; }
  api('/api/report-save', { text: reportBody() }).then(function (r) {
    $('reportMsg').innerHTML = 'Saved <b>' + esc(r.name) + '</b>. <button class="linkbtn" id="reportFolder">Show folder</button>';
    $('reportFolder').onclick = function () { api('/api/open-folder', { path: r.folder }).catch(function () {}); };
  }).catch(function (e) { $('reportMsg').textContent = e.message; });
});
$('reportMail').addEventListener('click', function () {
  var full = reportBody(), cut = full.length > 1700, body = cut ? full.slice(0, 1700) + '\n\n(The report was cut here. The full report is on your clipboard: paste it below this line.)' : full;
  if (navigator.clipboard) navigator.clipboard.writeText(full).catch(function () {});
  var subject = 'Manimo problem report (version ' + (info.version || '?') + ')';
  var done = function () { $('reportMsg').textContent = 'Your email app should open with the report. If nothing opens, the report is copied: send it to mathannits92@gmail.com.'; };
  if (DEMO) { window.location.href = 'mailto:mathannits92@gmail.com?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body); done(); return; }
  api('/api/mailto', { subject: subject, body: body }).then(done).catch(function (e) { $('reportMsg').textContent = 'Could not open your email app (' + e.message + '). The report is copied: send it to mathannits92@gmail.com.'; });
});
$('reportAuthor').addEventListener('click', function () { openUrl('https://mathanmj92.github.io/mathan/'); });
$('setupCopy').addEventListener('click', function () { (navigator.clipboard ? navigator.clipboard.writeText($('setupText').textContent) : Promise.reject()).then(function () { toast('Copied'); }, function () { toast('Could not copy. Select the text instead.'); }); });
(function shortcuts() {
  var rows = [['Ctrl + Enter', 'Start rendering'], ['Ctrl + S', 'Save the file'], ['Ctrl + Shift + S', 'Save as\u2026'], ['Ctrl + O', 'Open a file'], ['Ctrl + N', 'New file'], ['Ctrl + F', 'Find in the code'], ['Ctrl + H', 'Find and replace'], ['Ctrl + Z / Ctrl + Y', 'Undo / redo'], ['Ctrl + Space', 'Show suggestions while typing'], ['Ctrl + L', 'Open the AI assistant'], ['F1', 'Open this help'], ['Esc', 'Close a menu or panel']];
  $('shortcutList').innerHTML = rows.map(function (r) { return '<dt>' + r[0].split(' + ').map(function (k) { return '<kbd>' + esc(k) + '</kbd>'; }).join(' ') + '</dt><dd>' + esc(r[1]) + '</dd>'; }).join('');
})();

document.addEventListener('keydown', function (e) {
  if (e.defaultPrevented) return;                       // the editor already handled it
  var mod = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
  if (mod && e.key === 'Enter') { e.preventDefault(); $('startBtn').click(); }
  else if (mod && e.shiftKey && k === 's') { e.preventDefault(); saveFile(true); }
  else if (mod && k === 's') { e.preventDefault(); saveFile(false); }
  else if (mod && k === 'o') { e.preventDefault(); openFile(); }
  else if (mod && k === 'n') { e.preventDefault(); newFile(); }
  else if (mod && k === 'l') { e.preventDefault(); rightTab('assistant'); }
  else if (e.key === 'F1') { e.preventDefault(); openDialog('helpDlg'); }
  else if (e.key === 'Escape') { if (!menuEl.hidden) closeMenu(); else if (!settings.hidden) closeSettings(); }
});
phone.addEventListener('change', function () { paintStart(); });
narrow.addEventListener('change', function () { if (!narrow.matches) setView('code'); });

/* ---------------------------------------------------------------- AI assistant */
var AI = { cfg: null, busy: false, msgs: [], live: null, poll: null, draft: '' };
try { AI.msgs = JSON.parse(store('mgx-chat') || '[]'); } catch (e) { AI.msgs = []; }
var rtab = 'preview';
function saveChat() {
  store('mgx-chat', JSON.stringify(AI.msgs.slice(-24).map(function (m) { return { role: m.role, text: m.text || '', code: m.code || '', report: m.report || null, steps: m.steps || null, error: m.error || '' }; })));
}
var mqSide = matchMedia('(max-width: 1280px)');
function setPanel(which, open, focusInput) {
  var ai = which === 'ai', el = ai ? $('aiSide') : $('projSide'), btn = ai ? $('aiBtn') : $('projBtn');
  open = open === undefined ? el.hidden : !!open;
  if (open && mqSide.matches) { var other = ai ? $('projSide') : $('aiSide'); if (!other.hidden) { other.hidden = true; (ai ? $('projBtn') : $('aiBtn')).setAttribute('aria-pressed', 'false'); store('mgx-panel-' + (ai ? 'proj' : 'ai'), '0'); } }
  el.hidden = !open; btn.setAttribute('aria-pressed', String(open)); store('mgx-panel-' + which, open ? '1' : '0');
  if (ai && open) { renderChat(); aiFoot(); if (focusInput !== false) setTimeout(function () { var i = $('chatInput'); if (i && !$('chatCompose').hidden) i.focus(); }, 40); }
  if (!ai && open && window.MGXProject) window.MGXProject.show();
}
function rightTab(which) {      // the preview is always shown; Assistant and Project open as side panels
  if (which === 'assistant') setPanel('ai', true);
  else if (which === 'project') setPanel('proj', true);
  else { showPreview(); if (narrow.matches) setView('preview'); }
}
function aiFoot() {
  var c = AI.cfg, label = !c ? '' : c.provider === 'anthropic' ? 'Claude' : c.provider === 'agent' ? 'The assistant on this PC' : 'Your AI service';
  $('aiFoot').textContent = c && c.configured ? label + ' \u00b7 your request and code go to the service you chose' : 'Not connected yet';
}
$('aiBtn').addEventListener('click', function () { setPanel('ai'); });
$('projBtn').addEventListener('click', function () { setPanel('proj'); });
$('aiClose').addEventListener('click', function () { setPanel('ai', false); $('aiBtn').focus(); });
$('projClose').addEventListener('click', function () { setPanel('proj', false); $('projBtn').focus(); });
function restorePanels() { if (store('mgx-panel-proj') === '1') setPanel('proj', true); if (store('mgx-panel-ai') === '1') setPanel('ai', true, false); }
function aiLoad() {
  if (DEMO) { AI.cfg = { configured: false, demo: true }; renderChat(); return Promise.resolve(); }
  return api('/api/ai/status').then(function (c) { AI.cfg = c; renderChat(); aiFoot(); }).catch(function () { AI.cfg = { configured: false }; renderChat(); });
}

/* a small, safe markdown: paragraphs, bullets, **bold**, `code`; fenced code is shown in the code card instead */
function mdLite(text) {
  var t = String(text || '').replace(/```[\s\S]*?```/g, '').replace(/```[\s\S]*$/, '').trim();
  if (!t) return '';
  var out = [], list = false;
  t.split(/\n/).forEach(function (line) {
    var b = line.match(/^\s*[-*]\s+(.*)$/), s = esc(b ? b[1] : line).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
    if (b) { if (!list) { out.push('<ul>'); list = true; } out.push('<li>' + s + '</li>'); }
    else { if (list) { out.push('</ul>'); list = false; } if (line.trim()) out.push('<p>' + s + '</p>'); }
  });
  if (list) out.push('</ul>');
  return out.join('');
}
function stepsHTML(steps) {
  if (!steps || !steps.length) return '';
  return '<ul class="steps2">' + steps.map(function (s) { return '<li class="' + s.state + '"><i class="d"></i><span>' + esc(s.label) + (s.detail ? ' <small>· ' + esc(s.detail) + '</small>' : '') + '</span></li>'; }).join('') + '</ul>';
}
function reportHTML(r, idx) {
  if (!r) return '';
  var bits = [];
  if (r.clean) {
    bits.push('<b>Checked:</b> ' + (r.plays ? r.plays + ' animations, ' + Math.round(r.seconds) + ' s, ' : '') + 'no errors and no layout problems' + (r.rounds > 1 ? ' (it fixed itself in ' + r.rounds + ' rounds)' : '') + '.' + (r.note ? ' ' + esc(r.note) : '') + (r.skipped ? ' Only the first scenes were checked.' : ''));
    return '<div class="report">' + bits.join('') + '</div>';
  }
  var items = (r.problems || []).slice(0, 6).map(function (p) { return '<li>line ' + p.line + ': ' + esc(p.text) + '</li>'; }).join('');
  if (r.error) items = '<li>' + esc((r.error.text || '').split('\n').slice(-2).join(' ')) + (r.error.line ? ' (line ' + r.error.line + ')' : '') + '</li>' + items;
  return '<div class="report warn"><b>Still has problems after ' + r.rounds + ' round' + (r.rounds === 1 ? '' : 's') + ':</b><ul>' + items + '</ul>' +
    '<p style="margin:6px 0 0"><button class="lnk" data-act="fixrest" data-i="' + idx + '">Ask the assistant to fix these</button></p></div>';
}
function codeCardHTML(m, idx) {
  if (!m.code) return '';
  var n = m.code.split('\n').length - 1;
  return '<div class="codecard"><div class="cc-head"><svg class="ic sm"><use href="#i-file"/></svg><b>Scene code</b><span class="n">' + n + ' lines</span><span class="spacer"></span>' +
    '<button class="btn sm primary" data-act="apply" data-i="' + idx + '">Apply to editor</button><button class="btn sm" data-act="render" data-i="' + idx + '">Apply &amp; render</button><button class="btn sm ghost" data-act="copy" data-i="' + idx + '">Copy</button></div>' +
    '<details><summary>Show code</summary><pre>' + esc(m.code) + '</pre></details></div>';
}
function msgHTML(m, idx) {
  if (m.role === 'user') return '<div class="msg-user">' + esc(m.text) + '</div>';
  var h = '<div class="msg-ai"><span class="who"><svg class="ic sm"><use href="#i-spark"/></svg>Assistant</span>';
  h += stepsHTML(m.steps);
  if (m.error) h += '<div class="msg-err">' + esc(m.error) + '</div>';
  var t = mdLite(m.text); if (t) h += '<div class="txt">' + t + '</div>';
  h += codeCardHTML(m, idx) + reportHTML(m.report, idx) + '</div>';
  return h;
}
var TRY = ['Show why the sum of the first n odd numbers is n squared', 'Explain how a capacitor charges through a resistor', 'Visualise bubble sort on 5, 2, 8, 1, 9'];
function setupHTML() {
  var demo = AI.cfg && AI.cfg.demo;
  return '<div class="setup-card"><h3>Let AI write your animations</h3><p>Describe an idea in plain words and the assistant writes the code, checks it for errors and overlapping text, and fixes what it finds. It follows a built-in guide for clear, explainer-style animation.</p>' +
    (demo ? '<p><b>Open Manimo from its shortcut to connect an AI.</b></p>' : '<button class="btn primary" data-act="connect"><svg class="ic sm"><use href="#i-spark"/></svg>Connect an AI</button><p style="font-size:12.5px;color:var(--text-3)">Works with a Claude API key, or another service, or a model on this PC. Your key stays on this computer, encrypted.</p>') + '</div>';
}
function welcomeHTML() {
  return '<div class="chat-welcome"><h3>What should we animate?</h3><p>Describe the idea, or pick one to try. You can also ask it to explain, fix or improve the code in your editor.</p><div class="try-list">' +
    TRY.map(function (t, i) { return '<button data-try="' + i + '">' + esc(t) + '</button>'; }).join('') + '</div></div>';
}
function renderChat() {
  var log = $('chatLog'), ok = AI.cfg && AI.cfg.configured;
  $('chatCompose').hidden = !ok;
  if (!ok) { log.innerHTML = setupHTML(); return; }
  var h = AI.msgs.length ? AI.msgs.map(msgHTML).join('') : welcomeHTML();
  if (AI.busy) h += '<div class="msg-ai" id="liveBubble"></div>';
  log.innerHTML = h;
  renderLive(); log.scrollTop = log.scrollHeight;
  $('chatModel').textContent = AI.cfg.provider === 'agent' ? ((AI.cfg.agents || []).filter(function (a) { return a.id === AI.cfg.agent; }).map(function (a) { return a.label; })[0] || 'Assistant on this PC') : (AI.cfg.model || '');
  var hasCode = code.value.trim(); $('aiEngineChip').hidden = !!(hasCode && $('useCode').checked);
  var send = $('chatSend'); send.querySelector('use').setAttribute('href', AI.busy ? '#i-stop' : '#i-send'); send.setAttribute('aria-label', AI.busy ? 'Stop' : 'Send');
  $('chatInput').disabled = false;
}
function renderLive() {
  var el = $('liveBubble'); if (!el) return;
  var j = AI.live || { steps: [], text: '' }, text = j.text || '';
  var shown = mdLite(text), lines = (text.match(/```(?:python)?\s*\n([\s\S]*)$/) || [])[1];
  el.innerHTML = '<span class="who"><svg class="ic sm"><use href="#i-spark"/></svg>Assistant <span class="typing"><i></i><i></i><i></i></span></span>' + stepsHTML(j.steps) +
    (shown ? '<div class="txt">' + shown + '</div>' : '') + (lines !== undefined ? '<p class="dock-line">Writing code… ' + (lines.split('\n').length) + ' lines</p>' : '');
  var log = $('chatLog'); if (log.scrollHeight - log.scrollTop - log.clientHeight < 140) log.scrollTop = log.scrollHeight;
}
function stripCode(t) { return String(t || '').replace(/```[\s\S]*?```/g, '[the code was omitted; it is in the editor]').trim(); }
function lastErrorText() {
  if (R.state === 'error' && R.error) return (R.error.detail || R.error.title || '');
  return '';
}
function sendAI(o) {
  if (AI.busy) { api('/api/ai/cancel', {}).catch(function () {}); return; }
  if (DEMO) { toast('Open Manimo from its shortcut to use the assistant'); return; }
  var text = (o.text || '').trim(), hasCode = !!code.value.trim() && $('useCode').checked, mode = o.mode || (hasCode ? 'edit' : 'write');
  if (!text && !o.mode) return;
  if (mode === 'explain' && !hasCode) { toast('There is no code to explain yet'); return; }
  var err = o.error !== undefined ? o.error : lastErrorText();
  if (mode === 'fix' && !err && !text) { toast('There is no error to fix. Describe the problem in the box.'); $('chatInput').focus(); return; }
  var label = text || ({ explain: 'Explain this code', fix: 'Fix the last error', improve: 'Improve the layout' }[mode] || '');
  var history = AI.msgs.slice(-6).map(function (m) { return { role: m.role, text: m.role === 'assistant' ? stripCode(m.text) : m.text }; }).filter(function (m) { return m.text; });
  AI.msgs.push({ role: 'user', text: label });
  var engine = hasCode ? engineOf(code.value) : $('aiEngine').value; store('mgx-ai-engine', $('aiEngine').value);
  AI.busy = true; AI.live = { steps: [], text: '' }; $('chatInput').value = ''; renderChat();
  api('/api/ai/run', { mode: mode, prompt: text, engine: engine, code: hasCode ? code.value : '', use_code: hasCode, selection: cm.selection(), error: err, history: history }).then(function () {
    clearInterval(AI.poll);
    AI.poll = setInterval(function () {
      api('/api/ai/job').then(function (j) { AI.live = j; renderLive(); if (j.state !== 'running') { clearInterval(AI.poll); finishAI(j); } }).catch(function () {});
    }, 350);
  }).catch(function (e) { finishAI({ state: 'error', error: e.message, steps: [] }); });
}
function finishAI(j) {
  AI.busy = false; AI.live = null;
  if (j.state === 'done' && j.final) AI.msgs.push({ role: 'assistant', text: j.final.text, code: j.final.code, report: j.final.report, steps: j.steps });
  else if (j.state === 'cancelled') AI.msgs.push({ role: 'assistant', text: 'Stopped.', steps: j.steps });
  else AI.msgs.push({ role: 'assistant', text: '', error: j.error || 'Something went wrong.', steps: j.steps });
  saveChat(); renderChat(); say('The assistant has finished.');
}
function applyAICode(i, thenRender) {
  var m = AI.msgs[i]; if (!m || !m.code) return;
  cm.replace(m.code);
  var marks = {}; ((m.report && m.report.problems) || []).forEach(function (p) { if (p.line) marks[p.line] = 'warn'; }); if (m.report && m.report.error && m.report.error.line) marks[m.report.error.line] = 'err';
  cm.setMarks(marks); curName = curName || 'ai_scene.py'; paintFile();
  if (narrow.matches) setView('code');
  toast('Applied to the editor. Undo with Ctrl+Z.');
  if (thenRender) setTimeout(function () { startRender(); }, 150);
}
function problemsText(m) {
  var r = m.report || {}, lines = [];
  (r.problems || []).forEach(function (p) { lines.push('line ' + p.line + ': ' + p.text); });
  if (r.error) lines.push((r.error.text || '') + (r.error.line ? ' (line ' + r.error.line + ')' : ''));
  return lines.join('\n');
}
$('chatLog').addEventListener('click', function (e) {
  var b = e.target.closest('[data-act],[data-try]'); if (!b) return;
  if (b.dataset.try !== undefined) { $('chatInput').value = TRY[parseInt(b.dataset.try, 10)]; $('useCode').checked = false; sendAI({ text: $('chatInput').value }); return; }
  var act = b.dataset.act, i = parseInt(b.dataset.i, 10);
  if (act === 'connect') openAISettings();
  else if (act === 'apply') applyAICode(i, false);
  else if (act === 'render') applyAICode(i, true);
  else if (act === 'copy') { var m = AI.msgs[i]; (navigator.clipboard ? navigator.clipboard.writeText(m.code) : Promise.reject()).then(function () { toast('Code copied'); }, function () { toast('Could not copy'); }); }
  else if (act === 'fixrest') { applyAICode(i, false); sendAI({ mode: 'fix', text: 'Fix the remaining problems.', error: problemsText(AI.msgs[i]) }); }
});
$('chatSend').addEventListener('click', function () { sendAI({ text: $('chatInput').value }); });
$('chatInput').addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAI({ text: this.value }); } });
$('chatQuick').addEventListener('click', function (e) {
  var b = e.target.closest('[data-q]'); if (!b) return;
  var q = b.dataset.q;
  if (q === 'prompt') openPrompt();
  else if (q === 'new') { var i = $('chatInput'); i.value = 'Make an animation that explains '; i.focus(); i.setSelectionRange(i.value.length, i.value.length); $('useCode').checked = !code.value.trim() ? true : false; }
  else sendAI({ mode: q, text: '' });
});
/* lesson prompt (assets/prompt.js): open it, and receive a finished prompt in the assistant box */
function openPrompt() { closeMenu(); if (window.MGXPrompt) window.MGXPrompt.open(); }
window.MGXApp = { toast: toast, askAI: function (text) {
  setPanel('ai', true, false); var i = $('chatInput'); i.value = text; $('useCode').checked = false;
  i.focus(); i.setSelectionRange(0, 0); i.scrollTop = 0; toast('Prompt is in the assistant box. Press Enter to send it.');
} };
$('aiNew').addEventListener('click', function () { if (AI.busy) return; AI.msgs = []; saveChat(); renderChat(); });
$('aiSettingsBtn').addEventListener('click', openAISettings);
$('aiEngine').value = store('mgx-ai-engine') || 'manimgx';

/* connection settings */
function openAISettings() {
  if (!AI.cfg || AI.cfg.demo) { toast('Open Manimo from its shortcut to set up the assistant'); return; }
  var c = AI.cfg; closeMenu(); closeSettings(false);
  var sel = $('aiModelSel'), models = c.models || [];
  sel.innerHTML = models.map(function (m) { return '<option value="' + esc(m.id) + '">' + esc(m.label) + '</option>'; }).join('') + '<option value="__custom__">Other model name…</option>';
  var known = models.some(function (m) { return m.id === c.model; });
  sel.value = known ? c.model : '__custom__'; $('aiModelText').value = known ? '' : (c.model || '');
  $('aiKey').value = ''; $('aiUrl').value = c.base_url || ''; $('aiVisual').checked = !!c.visual; $('aiTestMsg').textContent = '';
  var ags = c.agents || [];
  $('aiAgentSel').innerHTML = ags.map(function (a) { return '<option value="' + esc(a.id) + '">' + esc(a.label) + '</option>'; }).join('');
  if (c.agent) $('aiAgentSel').value = c.agent;
  $('aiAgentModel').value = c.agent_model || '';
  $('aiAgentHelp').textContent = ags.length ? 'Found on this PC. It must be signed in already. Each request counts against that account’s usage.' : 'No assistant found. Install Claude Code (or Codex / Gemini CLI), sign in once in a terminal, then reopen this window. Or pick an API key.';
  setProvider(c.provider === 'anthropic' || c.provider === 'openai' || c.provider === 'agent' ? (c.provider === 'anthropic' && !c.has_key && ags.length ? 'agent' : c.provider) : 'agent');
  $('aiKeyHelp').textContent = c.has_key ? 'A key is saved. Leave this empty to keep it.' : '';
  $('aiDlg').showModal();
}
function setProvider(p) {
  document.querySelectorAll('#aiProvider [role=radio]').forEach(function (b) { b.setAttribute('aria-checked', String(b.dataset.v === p)); });
  $('aiProvider').dataset.v = p; $('aiUrlRow').hidden = p !== 'openai'; $('aiGetKey').parentElement.hidden = p !== 'anthropic';
  var ag = p === 'agent'; $('aiAgentRow').hidden = !ag; $('aiKeyRow').hidden = ag; $('aiModelSel').parentElement.hidden = ag; $('aiVisual').closest('.field').hidden = ag;
  $('aiModelSel').hidden = p !== 'anthropic';
  $('aiModelText').hidden = p === 'anthropic' ? $('aiModelSel').value !== '__custom__' : false;
  $('aiModelText').placeholder = p === 'openai' ? 'e.g. gpt-4o or llama3.1' : 'model name';
}
function syncAIChip() { var chip = $('aiEngineChip'); if (chip) chip.hidden = !!(code.value.trim() && $('useCode').checked); }
$('useCode').addEventListener('change', syncAIChip);
$('aiProvider').addEventListener('click', function (e) { var b = e.target.closest('[role=radio]'); if (b) setProvider(b.dataset.v); });
$('aiModelSel').addEventListener('change', function () { $('aiModelText').hidden = this.value !== '__custom__'; });
$('aiGetKey').addEventListener('click', function () { openUrl('https://console.anthropic.com/settings/keys'); });
function saveAISettings(thenTest) {
  var p = $('aiProvider').dataset.v || 'anthropic';
  var model = p === 'anthropic' && $('aiModelSel').value !== '__custom__' ? $('aiModelSel').value : ($('aiModelText').value.trim() || (AI.cfg && AI.cfg.model));
  var body = { provider: p, model: model, base_url: $('aiUrl').value.trim() || undefined, visual: $('aiVisual').checked, agent: $('aiAgentSel').value || undefined, agent_model: $('aiAgentModel').value.trim() };
  if ($('aiKey').value.trim()) body.api_key = $('aiKey').value.trim();
  $('aiTestMsg').textContent = 'Saving…';
  return api('/api/ai/settings', body).then(function (c) {
    AI.cfg = c; $('aiKey').value = ''; renderChat(); aiFoot();
    if (!thenTest) { $('aiDlg').close(); toast('AI settings saved'); return; }
    $('aiTestMsg').textContent = 'Testing the connection…';
    return api('/api/ai/test', {}).then(function (r) { $('aiTestMsg').textContent = r.ok ? 'Connected. The assistant replied: ' + r.reply : r.error; });
  }).catch(function (e) { $('aiTestMsg').textContent = e.message; });
}
$('aiSave').addEventListener('click', function () { saveAISettings(false); });
$('aiTest').addEventListener('click', function () { saveAISettings(true); });
$('aiClearKey').addEventListener('click', function () { api('/api/ai/settings', { api_key: '', clear_key: true }).then(function (c) { AI.cfg = c; renderChat(); $('aiTestMsg').textContent = 'The saved key was removed.'; $('aiKeyHelp').textContent = ''; }); });

/* ---------------------------------------------------------------- start-up */
function setEngine(cls, text) { $('enginePill').className = 'pill engine-pill ' + cls; $('engineText').textContent = text; }
function refreshStatus() {
  if (DEMO) return Promise.resolve();
  return api('/api/status').then(function (s) {
    info.engines = s.engines || { manimgx: s.engine, manim: null }; info.latex = !!s.latex; info.latex_version = s.latex_version || ''; info.latex_bundled = !!s.latex_bundled; info.version = s.version; info.voice = s.voice; info.python = s.python; info.python_path = s.python_path;
    if (!store('mgx-outdir')) { outDir = s.out_dir; renderFolder(); }
    if (info.engines.manimgx) setEngine('ok', 'ManimGX ' + info.engines.manimgx + (info.engines.manim ? ' \u00b7 Manim ' + info.engines.manim : '')); else setEngine('bad', 'ManimGX not installed');
    syncSettingsUI(); updateStatus(); fillAbout();
  });
}
var splashT0 = performance.now();
function hideSplash() {
  var s = $('splash'); if (!s) return;
  setTimeout(function () { s.classList.add('out'); setTimeout(function () { s.remove(); }, 700); }, Math.max(0, 1300 - (performance.now() - splashT0)));
}
function boot() {
  applyTheme(false); syncSettingsUI(); renderFolder(); restorePanels();
  var saved = store('mgx-code');
  if (saved) setCode(saved, store('mgx-name') || ''); else afterEdit();
  var sc = store('mgx-scene'); if (sc) selScene = sc;
  updateStatus(); paintDock();
  if (DEMO) { aiLoad(); setEngine('warn', 'Preview mode'); $('enginePill').title = 'Open Manimo from its shortcut to render for real. Here, rendering is simulated.'; hideSplash(); return; }
  refreshStatus().then(function () { aiLoad(); if (window.MGXProject) window.MGXProject.boot();
    setInterval(function () { api('/api/ping').catch(function () {}); }, 10000);
    setInterval(function () { api('/api/pending').then(function (r) { if (r && r.open_project && window.MGXProject) window.MGXProject.openPath(r.open_project); }).catch(function () {}); }, 2500);
    api('/api/job').then(function (j) { if (j.state === 'running') { R.state = 'running'; R.scenes = j.scenes || []; R.items = j.items || []; built = ''; paintDock(); poll(); } });
  }).catch(function () { setEngine('bad', 'Engine offline'); }).then(hideSplash);
}
window.MANIMO = {
  $: $, api: api, esc: esc, fmt: fmt, toast: toast, say: say, openDialog: openDialog, openUrl: openUrl, store: store, TOKEN: TOKEN, setPreview: setPreview, rightTab: rightTab, narrow: narrow,
  getCode: function () { return code.value; }, getName: function () { return curName; }, setCode: setCode, paintFile: paintFile, startRender: startRender,
  markClean: function () { dirty = false; paintFile(); }, pickFolder: function (p, title) { return api('/api/pick-folder', { path: p, title: title }); },
  settings: function () { return { quality: S.quality, shape: S.shape, fps: S.fps, encoding: S.encoding, voice: VOICE.id, speed: VOICE.speed }; },
  applySettings: function (s) { if (!s) return; if (s.quality) S.quality = s.quality; S.shape = s.shape || 'auto'; if (s.fps) S.fps = s.fps; if (s.encoding) S.encoding = s.encoding; if (s.voice) { VOICE.id = s.voice; store('mgx-voice', VOICE.id); } if (s.speed) { VOICE.speed = s.speed; store('mgx-voice-speed', String(VOICE.speed)); } persistSettings(); syncSettingsUI(); },
  recentVideos: function () { return history.filter(function (h) { return h.kind === 'video' && h.path; }).slice(0, 8); },
  selectScene: function (n) { selScene = n; store('mgx-scene', n); updateStatus(); },
  outDir: function () { return outDir; },
  isRendering: function () { return R.state === 'running'; }, exportsFolderOpen: function (p) { return api('/api/open-folder', { path: p }); }
};
boot();
})();
