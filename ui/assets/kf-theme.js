/* Keystone · Financial Crime: one light or dark theme across every page.

   Load this in <head>, before the stylesheets paint, so no page flashes the wrong theme. Pages open
   dark; a visitor's choice is kept in local storage and followed on every page (landing, queue,
   case view, phone, drop). Any [data-kf-theme-toggle] button flips it, and the case view's
   [data-k-theme] buttons set it. Parts that must stay dark (the landing photo) carry their own
   data-theme="dark". */
(function () {
  var KEY = 'kf-theme', root = document.documentElement;

  function saved() { try { var t = localStorage.getItem(KEY); return t === 'light' || t === 'dark' ? t : null; } catch (e) { return null; } }
  function save(t) { try { localStorage.setItem(KEY, t); } catch (e) {} }
  function current() { return root.getAttribute('data-theme') || 'dark'; }

  function apply(t) {
    root.setAttribute('data-theme', t);
    var btns = document.querySelectorAll('[data-kf-theme-toggle]');
    for (var i = 0; i < btns.length; i++) {
      var next = t === 'dark' ? 'light' : 'dark';
      btns[i].setAttribute('aria-label', 'Switch to ' + next + ' mode');
      btns[i].setAttribute('title', 'Switch to ' + next + ' mode');
      btns[i].setAttribute('aria-pressed', t === 'light' ? 'true' : 'false');
    }
    var seg = document.querySelectorAll('[data-k-theme]');
    for (var j = 0; j < seg.length; j++) seg[j].setAttribute('aria-pressed', String(seg[j].getAttribute('data-k-theme') === t));
  }
  function set(t) {
    root.classList.add('kf-theming');
    save(t); apply(t);
    setTimeout(function () { root.classList.remove('kf-theming'); }, 400);
  }

  apply(saved() || 'dark');

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-kf-theme-toggle]');
    if (btn) return set(current() === 'dark' ? 'light' : 'dark');
    var seg = e.target.closest && e.target.closest('[data-k-theme]');
    if (seg) set(seg.getAttribute('data-k-theme'));
  });
  // another tab changed the theme: follow it
  window.addEventListener('storage', function (e) { if (e.key === KEY && saved()) apply(saved()); });
  document.addEventListener('DOMContentLoaded', function () { apply(current()); });
})();
