/* Caption style for Compose exports: size, position, colour and an optional dark box, with a live preview on a frame of the first clip. */
(function () {
'use strict';
var M = window.MANIMO, btn = document.getElementById('capStyleBtn'), dlg = document.getElementById('capDlg');
if (!M || !btn || !dlg) return;
var $ = M.$, KEY = 'mgx-caption-style';
var DEFAULT = { size: 'medium', position: 'bottom', color: 'white', box: false };
var st = Object.assign({}, DEFAULT);
try { Object.assign(st, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}

function read() { st = { size: $('capSize').value, position: $('capPos').value, color: $('capColor').value, box: $('capBox').checked }; try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }
function write() { $('capSize').value = st.size; $('capPos').value = st.position; $('capColor').value = st.color; $('capBox').checked = !!st.box; }
var timer = null, seq = 0;
function preview() {
  clearTimeout(timer);
  timer = setTimeout(function () {
    var mine = ++seq; $('capMsg').textContent = 'Making the preview…';
    M.api('/api/project/caption-preview', { style: st }).then(function (r) {
      if (mine !== seq) return; $('capImg').src = r.image; $('capMsg').textContent = '';
    }).catch(function (e) { if (mine === seq) { $('capImg').removeAttribute('src'); $('capMsg').textContent = e.message; } });
  }, 250);
}
btn.addEventListener('click', function () { write(); dlg.showModal(); preview(); });
dlg.addEventListener('change', function (e) { if (e.target.closest('select, input')) { read(); preview(); } });

window.MGXCaptions = { style: function () { return st; } };
})();
