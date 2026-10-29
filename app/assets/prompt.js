/* Lesson prompt: fill in the marked places, copy it or send it to the assistant, or pick one from the library.
   All text comes from assets/prompts.json (template, fields, library, followups): adding a library entry is a JSON-only change. */
(function () {
'use strict';
var dlg = document.getElementById('promptDlg'), body = document.getElementById('promptBody');
if (!dlg || !body) return;

var D = null, loading = null, built = false;
var inputs = {}, customs = {}, subj = 'All';
var pre, note, libList, libFilter;

function h(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
function toast(m) { if (window.MGXApp) window.MGXApp.toast(m); }
function copyText(text, done) {
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
  else done(false);
}
function flash(btn, ok, fail, label) { btn.textContent = ok ? 'Copied' : fail; setTimeout(function () { btn.textContent = label; }, 2200); }

function load() {
  if (D) return Promise.resolve(D);
  if (!loading) loading = fetch('assets/prompts.json').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (j) { D = j; return j; }, function (e) { loading = null; throw e; });
  return loading;
}

function fieldValue(f) {
  if (f.type === 'select') { var v = inputs[f.key].value; return (f.custom && v === f.custom) ? customs[f.key].value.trim() : v; }
  return inputs[f.key].value.trim();
}
function current() { var v = {}; D.fields.forEach(function (f) { v[f.key] = fieldValue(f); }); return v; }
function defaults() { var v = {}; D.fields.forEach(function (f) { v[f.key] = f.default || ''; }); return v; }

/* The template with [KEY] places replaced. html=true gives a fragment with filled / auto / missing places marked. */
function build(values, html) {
  var parts = D.template.split(/\[([A-Z]+)\]/), byKey = {}, out = html ? document.createDocumentFragment() : '';
  D.fields.forEach(function (f) { byKey[f.key] = f; });
  for (var i = 0; i < parts.length; i++) {
    if (i % 2 === 0) { if (html) out.appendChild(document.createTextNode(parts[i])); else out += parts[i]; continue; }
    var f = byKey[parts[i]], raw;
    if (!f) { raw = '[' + parts[i] + ']'; if (html) out.appendChild(document.createTextNode(raw)); else out += raw; continue; }
    var val = (values[f.key] || '').trim(), cls = 'ph';
    if (!val && f.empty) { val = f.empty; cls = 'ph-auto'; }
    else if (!val) { val = '[' + f.key + ']'; cls = 'ph-miss'; }
    if (html) out.appendChild(h('span', cls, val)); else out += val;
  }
  return out;
}
function render() { pre.textContent = ''; pre.appendChild(build(current(), true)); }

function setValue(f, value) {
  var el = inputs[f.key];
  if (f.type === 'select') {
    if (f.options.indexOf(value) >= 0 || value === f.custom) { el.value = value; customs[f.key] && (customs[f.key].hidden = value !== f.custom); }
    else if (f.custom) { el.value = f.custom; customs[f.key].hidden = false; customs[f.key].value = value; }
  } else el.value = value;
}
function entryValues(e) {
  var v = defaults();
  var map = { TOPIC: e.topic, AUDIENCE: e.audience, LENGTH: e.length, EQUATIONS: e.equations, EXTRAS: e.extras };
  Object.keys(map).forEach(function (k) { if (map[k] != null && map[k] !== '') v[k] = map[k]; });
  return v;
}
function useEntry(e) {
  var v = entryValues(e);
  D.fields.forEach(function (f) { setValue(f, v[f.key]); });
  render();
}

function section(title, id) { var s = h('section', 'pr-sec'); var t = h('h3', 'help-h', title); if (id) t.id = id; s.appendChild(t); return s; }

function buildForm(parent) {
  var form = h('div', 'pr-form');
  D.fields.forEach(function (f) {
    var wrap = h('div', 'field'), id = 'pf-' + f.key, el;
    var lab = h('label', 'lbl', f.label); lab.setAttribute('for', id); wrap.appendChild(lab);
    if (f.type === 'select') {
      el = h('select', 'input'); var opts = f.options.slice(); if (f.custom) opts.push(f.custom);
      opts.forEach(function (o) { var op = h('option', null, o); op.value = o; el.appendChild(op); });
      el.value = f.default;
    } else {
      el = h(f.type === 'area' ? 'textarea' : 'input', 'input'); if (f.type === 'area') el.rows = 2; else el.type = 'text';
      el.value = f.default || ''; if (f.placeholder) el.placeholder = f.placeholder;
      el.spellcheck = false; el.autocomplete = 'off';
    }
    el.id = id; el.addEventListener('input', render); inputs[f.key] = el; wrap.appendChild(el);
    if (f.custom) {
      var c = h('input', 'input pr-custom'); c.type = 'text'; c.hidden = true; c.placeholder = 'Describe the look you want'; c.setAttribute('aria-label', f.label + ', in your own words');
      c.addEventListener('input', render); customs[f.key] = c; wrap.appendChild(c);
      el.addEventListener('change', function () { c.hidden = el.value !== f.custom; if (!c.hidden) c.focus(); render(); });
    }
    if (f.hint) wrap.appendChild(h('p', 'help', f.hint));
    form.appendChild(wrap);
  });
  parent.appendChild(form);
}

function buildAll() {
  body.textContent = '';
  body.appendChild(h('p', 'pr-lead', 'Fill in the marked places and you get one prompt that makes an AI write a clear, runnable lesson. Copy it into any AI model, or send it to the assistant in Manimo.'));

  var s1 = section('Build your prompt', 'prBuild'); buildForm(s1);
  pre = h('pre', 'pr-pre'); pre.setAttribute('tabindex', '0'); pre.setAttribute('aria-label', 'Prompt preview');
  var legend = h('p', 'help pr-legend'); legend.appendChild(h('span', 'ph', 'Filled in')); legend.appendChild(document.createTextNode(' '));
  legend.appendChild(h('span', 'ph-auto', 'Left blank, the AI chooses')); legend.appendChild(document.createTextNode(' '));
  legend.appendChild(h('span', 'ph-miss', '[TOPIC] Still to fill in'));
  var bar = h('div', 'pr-bar'), copy = h('button', 'btn', 'Copy prompt'), ask = h('button', 'btn primary', 'Use in Ask AI');
  copy.type = ask.type = 'button';
  note = h('span', 'pr-note'); note.setAttribute('role', 'status');
  copy.addEventListener('click', function () {
    var v = current(), missing = !v.TOPIC;
    copyText(build(v, false), function (ok) {
      note.textContent = ok ? (missing ? 'Copied. The [TOPIC] place is still empty: add your topic first.' : 'Prompt copied. Paste it into your AI model.') : 'Select the prompt text and copy it.';
    });
  });
  ask.addEventListener('click', function () {
    var v = current();
    if (!v.TOPIC) { note.textContent = 'Write your topic first, then send it.'; inputs.TOPIC.focus(); return; }
    if (!window.MGXApp) return;
    dlg.close(); window.MGXApp.askAI(build(v, false));
  });
  bar.appendChild(copy); bar.appendChild(ask); bar.appendChild(note);
  s1.appendChild(h('div', 'lbl pr-prevlbl', 'Your prompt')); s1.appendChild(pre); s1.appendChild(legend); s1.appendChild(bar);
  body.appendChild(s1);

  var s2 = section('Prompt library', 'prLib');
  s2.appendChild(h('p', 'help', 'Ready topics. Open one in the builder to change it, or copy it as it is.'));
  libFilter = h('div', 'pr-filter'); libFilter.setAttribute('role', 'group'); libFilter.setAttribute('aria-label', 'Filter by subject');
  libList = h('ul', 'pr-lib');
  var subjects = ['All']; D.library.forEach(function (e) { if (subjects.indexOf(e.subject) < 0) subjects.push(e.subject); });
  subjects.forEach(function (name) {
    var b = h('button', 'chip sm', name); b.type = 'button'; b.setAttribute('aria-pressed', String(name === subj));
    b.addEventListener('click', function () { subj = name; Array.prototype.forEach.call(libFilter.children, function (x) { x.setAttribute('aria-pressed', String(x === b)); }); drawLib(); });
    libFilter.appendChild(b);
  });
  s2.appendChild(libFilter); s2.appendChild(libList); body.appendChild(s2);
  drawLib();

  var s3 = section('Follow-up prompts', 'prFollow');
  s3.appendChild(h('p', 'help', 'Use these after the first answer. Replace the marked place with your code or error.'));
  D.followups.forEach(function (f) {
    var d = h('details', 'pr-fu'), sm = h('summary', null, f.title), p = h('pre', 'pr-pre', f.text), b = h('button', 'btn sm', 'Copy'); b.type = 'button';
    p.setAttribute('tabindex', '0');
    b.addEventListener('click', function () { copyText(f.text, function (ok) { flash(b, ok, 'Select the text', 'Copy'); }); });
    d.appendChild(sm); d.appendChild(p); d.appendChild(b); s3.appendChild(d);
  });
  body.appendChild(s3);
  render(); built = true;
}

function drawLib() {
  libList.textContent = '';
  D.library.filter(function (e) { return subj === 'All' || e.subject === subj; }).forEach(function (e) {
    var li = h('li', 'pr-item'), left = h('div', 'pr-item-t'), t = h('h4', null, e.title); t.appendChild(h('span', 'pr-tag', e.subject));
    left.appendChild(t); left.appendChild(h('p', null, e.line));
    var acts = h('div', 'pr-acts'), open = h('button', 'btn sm', 'Open in builder'), cp = h('button', 'btn sm', 'Copy prompt');
    open.type = cp.type = 'button';
    open.setAttribute('aria-label', 'Open ' + e.title + ' in the builder'); cp.setAttribute('aria-label', 'Copy the prompt for ' + e.title);
    open.addEventListener('click', function () {
      useEntry(e); note.textContent = 'Filled in: ' + e.title + '. Change anything you like.';
      var s = document.getElementById('prBuild'); if (s) s.scrollIntoView({ block: 'start' }); inputs.TOPIC.focus();
    });
    cp.addEventListener('click', function () { copyText(build(entryValues(e), false), function (ok) { flash(cp, ok, 'Select it in the builder', 'Copy prompt'); }); });
    acts.appendChild(open); acts.appendChild(cp); li.appendChild(left); li.appendChild(acts); libList.appendChild(li);
  });
}

function open() {
  if (!dlg.open) dlg.showModal();
  if (built) { inputs.TOPIC.focus(); return Promise.resolve(); }
  body.textContent = ''; body.appendChild(h('p', 'pr-lead', 'Loading…'));
  return load().then(function () { buildAll(); inputs.TOPIC.focus(); }, function () {
    body.textContent = ''; body.appendChild(h('p', 'pr-lead', 'The prompt library could not be loaded. Close this window and try again, or restart Manimo.'));
  });
}

dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
dlg.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', function () { dlg.close(); }); });
window.MGXPrompt = { open: open };
})();
