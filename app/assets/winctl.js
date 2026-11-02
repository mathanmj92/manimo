/* Minimize / maximize / close in Manimo's own top bar. They show only when the desktop window has hidden Windows' own title bar. */
(function () {
  'use strict';
  var M = window.MANIMO, bar = document.getElementById('winCtl'), head = document.querySelector('.titlebar');
  if (!M || !bar || !head) return;

  function act(a) { return M.api('/api/window', { action: a }).catch(function () {}); }

  bar.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.win === 'close') M.exit(); else act(b.dataset.win);
  });

  // drag the window by the empty part of the bar; double-click it to maximize or restore
  var down = null;
  head.addEventListener('pointerdown', function (e) {
    down = (e.button !== 0 || bar.hidden || e.target.closest('button, .menubar, .pill, a, input')) ? null : { x: e.clientX, y: e.clientY };
  });
  head.addEventListener('pointermove', function (e) {
    if (!down || !(e.buttons & 1)) { down = null; return; }
    if (Math.abs(e.clientX - down.x) + Math.abs(e.clientY - down.y) < 4) return;   // a plain click or double-click is not a drag
    down = null; act('drag');
  });
  head.addEventListener('pointerup', function () { down = null; });
  head.addEventListener('dblclick', function (e) {
    if (bar.hidden || e.target.closest('button, .menubar, .pill, a, input')) return;
    act('max');
  });

  function show() { bar.hidden = false; document.documentElement.classList.add('custom-chrome'); }
  var tries = 0;
  (function ask() {
    fetch('/api/chrome').then(function (r) { return r.json(); }).then(function (r) {
      if (r.custom) show(); else if (++tries < 12) setTimeout(ask, 1000);
    }).catch(function () {});
  })();
})();
