/* Manimo landing page: theme toggle, the hero scene (a sine wave grows out of a circle), the lesson-prompt builder and library, voice samples, copy-email. No tracking, no third parties. */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.add('js');
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var NS = 'http://www.w3.org/2000/svg';

  /* ---------- theme: follows the system until the visitor picks one ---------- */
  var toggle = document.getElementById('theme');
  var meta = document.querySelector('meta[name="theme-color"]');
  function effective() { return root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'); }
  function paint() {
    var t = effective();
    if (toggle) { toggle.setAttribute('aria-pressed', String(t === 'light')); toggle.setAttribute('aria-label', t === 'light' ? 'Switch to dark mode' : 'Switch to light mode'); }
    if (meta) meta.setAttribute('content', t === 'light' ? '#f4f7f9' : '#0e1316');
  }
  if (toggle) toggle.addEventListener('click', function () {
    var next = effective() === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('manimo-theme', next); } catch (e) {}
    paint();
  });
  matchMedia('(prefers-color-scheme: light)').addEventListener('change', paint);
  paint();

  /* ---------- the hero scene ---------- */
  var svg = document.getElementById('scene');
  if (svg) {
    var CX = 150, CY = 190, R = 100, OX = 290, K = 43, TAU = Math.PI * 2;
    var curve = document.getElementById('sc-curve'), radius = document.getElementById('sc-radius');
    var dot = document.getElementById('sc-dot'), tip = document.getElementById('sc-tip'), link = document.getElementById('sc-link');
    var pauseBtn = document.getElementById('scene-pause'), replayBtn = document.getElementById('scene-replay');
    var RUN = 7000, HOLD = 1800, t0 = 0, paused = false, pausedAt = 0, raf = 0;
    function at(theta) {
      var dx = CX + R * Math.cos(theta), dy = CY - R * Math.sin(theta), tx = OX + K * theta;
      radius.setAttribute('x2', dx); radius.setAttribute('y2', dy);
      dot.setAttribute('cx', dx); dot.setAttribute('cy', dy);
      tip.setAttribute('cx', tx); tip.setAttribute('cy', dy);
      link.setAttribute('x1', dx); link.setAttribute('y1', dy); link.setAttribute('x2', tx); link.setAttribute('y2', dy);
      var d = 'M' + OX + ' ' + CY, n = Math.max(2, Math.ceil(theta / TAU * 90));
      for (var i = 1; i <= n; i++) { var a = theta * i / n; d += ' L' + (OX + K * a).toFixed(1) + ' ' + (CY - R * Math.sin(a)).toFixed(1); }
      curve.setAttribute('d', d);
    }
    function frame(now) {
      var e = now - t0, cycle = RUN + HOLD, m = e < 0 ? 0 : e % cycle;
      at(Math.min(m / RUN, 1) * TAU);
      raf = requestAnimationFrame(frame);
    }
    function play() { paused = false; t0 += performance.now() - pausedAt; raf = requestAnimationFrame(frame); setLabel(); }
    function pause() { paused = true; pausedAt = performance.now(); cancelAnimationFrame(raf); setLabel(); }
    function setLabel() { if (pauseBtn) pauseBtn.textContent = paused ? 'Play' : 'Pause'; }
    if (reduce) {
      at(TAU);
      if (pauseBtn) pauseBtn.hidden = true; if (replayBtn) replayBtn.hidden = true;
    } else {
      t0 = performance.now() + 1400; /* let the circle draw first */
      at(0); raf = requestAnimationFrame(frame);
      if (pauseBtn) pauseBtn.addEventListener('click', function () { paused ? play() : pause(); });
      if (replayBtn) replayBtn.addEventListener('click', function () { t0 = performance.now(); if (paused) { paused = false; setLabel(); raf = requestAnimationFrame(frame); } });
    }
  }

  /* ---------- the lesson prompt: fill in the marked places, copy, or pick one from the library ---------- */
  var D = window.MANIMO_PROMPTS;
  function copyText(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    else done(false);
  }
  function h(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  if (D && document.getElementById('pfields')) {
    var form = document.getElementById('pfields'), pre = document.getElementById('pre'), pnote = document.getElementById('pnote');
    var inputs = {}, customs = {};
    function fieldValue(f) {
      if (f.type === 'select') { var v = inputs[f.key].value; return (f.custom && v === f.custom) ? customs[f.key].value.trim() : v; }
      return inputs[f.key].value.trim();
    }
    function build(values, html) {
      var parts = D.template.split(/\[([A-Z]+)\]/), byKey = {}, out = html ? document.createDocumentFragment() : '';
      D.fields.forEach(function (f) { byKey[f.key] = f; });
      for (var i = 0; i < parts.length; i++) {
        if (i % 2 === 0) { if (html) out.appendChild(document.createTextNode(parts[i])); else out += parts[i]; continue; }
        var f = byKey[parts[i]];
        if (!f) { var raw = '[' + parts[i] + ']'; if (html) out.appendChild(document.createTextNode(raw)); else out += raw; continue; }
        var val = (values[f.key] || '').trim(), cls = 'ph';
        if (!val && f.empty) { val = f.empty; cls = 'ph-auto'; }
        else if (!val) { val = '[' + f.key + ']'; cls = 'ph-miss'; }
        if (html) out.appendChild(h('span', cls, val)); else out += val;
      }
      return out;
    }
    function current() { var v = {}; D.fields.forEach(function (f) { v[f.key] = fieldValue(f); }); return v; }
    function render() { pre.textContent = ''; pre.appendChild(build(current(), true)); }
    D.fields.forEach(function (f) {
      var wrap = h('div'), id = 'pf-' + f.key, el;
      var lab = h('label', null, f.label); lab.setAttribute('for', id); wrap.appendChild(lab);
      if (f.type === 'select') {
        el = h('select'); var opts = f.options.slice(); if (f.custom) opts.push(f.custom);
        opts.forEach(function (o) { var op = h('option', null, o); op.value = o; el.appendChild(op); });
        el.value = f.default;
      } else {
        el = h(f.type === 'area' ? 'textarea' : 'input'); if (f.type !== 'area') el.type = 'text';
        el.value = f.default || ''; if (f.placeholder) el.placeholder = f.placeholder;
      }
      el.id = id; el.addEventListener('input', render); inputs[f.key] = el; wrap.appendChild(el);
      if (f.custom) {
        var c = h('input', 'custom'); c.type = 'text'; c.hidden = true; c.placeholder = 'Describe the look you want'; c.setAttribute('aria-label', f.label + ', in your own words');
        c.addEventListener('input', render); customs[f.key] = c; wrap.appendChild(c);
        el.addEventListener('change', function () { c.hidden = el.value !== f.custom; if (!c.hidden) c.focus(); render(); });
      }
      if (f.hint) wrap.appendChild(h('span', 'hint', f.hint));
      form.appendChild(wrap);
    });
    form.removeChild(form.firstChild); /* the no-JavaScript message */
    render();
    var pcopy = document.getElementById('pcopy');
    pcopy.addEventListener('click', function () {
      var v = current(), missing = !v.TOPIC;
      copyText(build(v, false), function (ok) {
        pnote.textContent = ok ? (missing ? 'Copied. The [TOPIC] place is still empty: add your topic first.' : 'Prompt copied. Paste it into your AI model.') : 'Select the prompt text and copy it.';
      });
    });
    function useEntry(e) {
      var map = { TOPIC: e.topic, AUDIENCE: e.audience || '', LENGTH: e.length, EQUATIONS: e.equations, EXTRAS: e.extras };
      D.fields.forEach(function (f) { if (map[f.key] != null && map[f.key] !== '') { inputs[f.key].value = map[f.key]; } });
      render();
    }
    /* library */
    var list = document.getElementById('plib'), filter = document.getElementById('lib-filter'), subj = 'All';
    function drawLib() {
      list.textContent = '';
      D.library.filter(function (e) { return subj === 'All' || e.subject === subj; }).forEach(function (e) {
        var li = h('li'), left = h('div'), t = h('h3', null, e.title); t.appendChild(h('span', 'tag', e.subject));
        left.appendChild(t); left.appendChild(h('p', null, e.line));
        var acts = h('div', 'acts'), open = h('button', 'btn btn-line', 'Open in builder'), cp = h('button', 'btn btn-gold', 'Copy prompt');
        open.type = cp.type = 'button';
        open.setAttribute('aria-label', 'Open ' + e.title + ' in the builder'); cp.setAttribute('aria-label', 'Copy the prompt for ' + e.title);
        open.addEventListener('click', function () { useEntry(e); document.getElementById('prompt').scrollIntoView({ behavior: reduce ? 'auto' : 'smooth' }); pnote.textContent = 'Filled in: ' + e.title + '. Change anything you like.'; });
        cp.addEventListener('click', function () {
          var v = {}; D.fields.forEach(function (f) { v[f.key] = f.type === 'select' ? f.default : (f.default || ''); });
          v.TOPIC = e.topic; v.LENGTH = e.length; v.EQUATIONS = e.equations; v.EXTRAS = e.extras; if (e.audience) v.AUDIENCE = e.audience;
          copyText(build(v, false), function (ok) { cp.textContent = ok ? 'Copied' : 'Select it in the builder'; setTimeout(function () { cp.textContent = 'Copy prompt'; }, 2200); });
        });
        acts.appendChild(open); acts.appendChild(cp); li.appendChild(left); li.appendChild(acts); list.appendChild(li);
      });
    }
    var subjects = ['All']; D.library.forEach(function (e) { if (subjects.indexOf(e.subject) < 0) subjects.push(e.subject); });
    subjects.forEach(function (name) {
      var b = h('button', null, name); b.type = 'button'; b.setAttribute('aria-pressed', String(name === subj));
      b.addEventListener('click', function () { subj = name; Array.prototype.forEach.call(filter.children, function (x) { x.setAttribute('aria-pressed', String(x === b)); }); drawLib(); });
      filter.appendChild(b);
    });
    drawLib();
    /* follow-up prompts */
    var fu = document.getElementById('followups');
    D.followups.forEach(function (f) {
      var d = h('details'), s2 = h('summary', null, f.title), pr = h('pre', null, f.text), b = h('button', 'btn btn-line', 'Copy'); b.type = 'button';
      b.addEventListener('click', function () { copyText(f.text, function (ok) { b.textContent = ok ? 'Copied' : 'Select the text'; setTimeout(function () { b.textContent = 'Copy'; }, 2200); }); });
      d.appendChild(s2); d.appendChild(pr); d.appendChild(b); fu.appendChild(d);
    });
  }

  /* ---------- voice samples: one plays at a time ---------- */
  var current = null;
  function stop(btn) {
    if (!btn) return;
    var a = btn._audio; if (a) { a.pause(); a.currentTime = 0; }
    btn.setAttribute('aria-pressed', 'false'); btn.querySelector('use').setAttribute('href', '#i-play');
    btn.setAttribute('aria-label', 'Play the ' + btn.dataset.name + ' sample');
    var m = btn.closest('li').querySelector('.meter i'); if (m) m.style.width = '0';
  }
  document.querySelectorAll('.play').forEach(function (btn) {
    var audio = new Audio(); audio.preload = 'none'; audio.src = btn.dataset.src; btn._audio = audio;
    audio.addEventListener('timeupdate', function () { var m = btn.closest('li').querySelector('.meter i'); if (m && audio.duration) m.style.width = (100 * audio.currentTime / audio.duration) + '%'; });
    audio.addEventListener('ended', function () { stop(btn); current = null; });
    btn.addEventListener('click', function () {
      if (current === btn) { stop(btn); current = null; return; }
      stop(current); current = btn;
      btn.setAttribute('aria-pressed', 'true'); btn.querySelector('use').setAttribute('href', '#i-pause'); btn.setAttribute('aria-label', 'Stop the ' + btn.dataset.name + ' sample');
      audio.play().catch(function () { stop(btn); current = null; });
    });
  });

  /* ---------- copy the contact address ---------- */
  var copy = document.getElementById('copy-mail'), note = document.getElementById('copy-note');
  if (copy) copy.addEventListener('click', function () {
    var addr = copy.dataset.mail;
    function done(ok) { if (note) note.textContent = ok ? 'Address copied.' : 'Select the address above and copy it.'; }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(addr).then(function () { done(true); }, function () { done(false); });
    else done(false);
  });
})();
