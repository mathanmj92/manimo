/* Conversations: every chat with the assistant is kept on this PC under the lesson it was about. Search them, pin the ones worth keeping, and open an old one to carry on. */
(function () {
'use strict';
var M = window.MANIMO, dlg = document.getElementById('chatsDlg');
if (!M || !dlg) return;
var $ = M.$, esc = M.esc;
var timer = null, scope = 'lesson';

function key() { return M.chatKey(); }

/* saved a moment after each reply, so closing the app never loses a conversation */
function save() {
  clearTimeout(timer);
  timer = setTimeout(function () {
    var c = M.chatState();
    if (!c.msgs.some(function (m) { return m.role === 'user'; })) return;
    M.api('/api/chats/save', { id: c.id, key: key(), msgs: c.msgs }).then(function (r) { if (r.id && r.id !== c.id) M.setChatId(r.id); }).catch(function () {});
  }, 800);
}

function when(ts) {
  var d = new Date(ts * 1000), now = new Date(), same = d.toDateString() === now.toDateString();
  return same ? 'Today ' + d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : d.toLocaleDateString([], { day: 'numeric', month: 'short', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' });
}
function load() {
  var q = $('chatsSearch').value.trim();
  return M.api('/api/chats/list', { key: scope === 'lesson' ? key() : null, q: q }).then(function (r) {
    var cur = M.chatState().id;
    $('chatsList').innerHTML = r.items.length ? r.items.map(function (c) {
      return '<li class="ch-item' + (c.id === cur ? ' now' : '') + '" data-id="' + esc(c.id) + '"><div class="ch-main"><b>' + (c.pinned ? '<span class="ch-pin" title="Pinned">★</span> ' : '') + esc(c.title) + '</b>' +
        '<small>' + esc(when(c.updated)) + ' · ' + c.n + (c.n === 1 ? ' message' : ' messages') + (scope === 'all' ? ' · ' + esc(c.key) : '') + (c.id === cur ? ' · open now' : '') + '</small>' +
        (c.snippet ? '<p class="ch-snip">' + esc(c.snippet) + '</p>' : '') + '</div>' +
        '<div class="ch-acts"><button class="btn sm primary" data-a="open" type="button">Open</button><button class="btn sm ghost" data-a="pin" type="button">' + (c.pinned ? 'Unpin' : 'Pin') + '</button><button class="icon-btn sm" data-a="del" aria-label="Delete this conversation"><svg class="ic sm"><use href="#i-trash"/></svg></button></div></li>';
    }).join('') : '<li class="help ch-none">' + (q ? 'No conversation matches that.' : scope === 'lesson' ? 'No saved conversations for this lesson yet. Your chats are saved here automatically.' : 'No saved conversations yet.') + '</li>';
    $('chatsScope').textContent = scope === 'lesson' ? 'Showing: ' + key() : 'Showing: every lesson';
  }).catch(function (e) { $('chatsList').innerHTML = '<li class="help">' + esc(e.message) + '</li>'; });
}
function open() { $('chatsSearch').value = ''; dlg.showModal(); load(); $('chatsSearch').focus(); }

$('chatsSearch').addEventListener('input', function () { clearTimeout(open.t); open.t = setTimeout(load, 200); });
$('chatsToggle').addEventListener('click', function () { scope = scope === 'lesson' ? 'all' : 'lesson'; this.textContent = scope === 'lesson' ? 'Show every lesson' : 'Show this lesson only'; load(); });
$('chatsList').addEventListener('click', function (e) {
  var b = e.target.closest('[data-a]'); if (!b) return;
  var li = b.closest('.ch-item'), id = li.dataset.id;
  if (b.dataset.a === 'open') {
    if (M.aiBusy()) { M.toast('Wait for the assistant to finish first.'); return; }
    M.api('/api/chats/get', { id: id }).then(function (c) { M.setChat(c.id, c.msgs); dlg.close(); M.rightTab('assistant'); M.toast('Opened: ' + c.title); }).catch(function (er) { M.toast(er.message); });
  } else if (b.dataset.a === 'pin') {
    M.api('/api/chats/pin', { id: id, pinned: b.textContent === 'Pin' }).then(load);
  } else if (b.dataset.a === 'del') {
    if (window.confirm('Delete this conversation? This cannot be undone.')) M.api('/api/chats/delete', { id: id }).then(function () { if (M.chatState().id === id) M.setChatId(null); load(); });
  }
});

window.MGXChats = { save: save, open: open };
})();
