/* Keystone · Financial Crime: light and dark on the landing page.

   Load this in <head>, before the stylesheets paint, so the page never flashes the wrong theme.
   The visitor's own choice is kept in local storage; until they make one, the page follows the
   system setting and keeps following it. Any [data-kf-theme-toggle] button flips the theme. */
(function () {
  var KEY = 'kf-theme', root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;

  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function save(t) { try { localStorage.setItem(KEY, t); } catch (e) {} }
  function system() { return mq && mq.matches ? 'light' : 'dark'; }
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
  }

  apply(saved() || system());

  if (mq) {
    var follow = function () { if (!saved()) apply(system()); };
    if (mq.addEventListener) mq.addEventListener('change', follow); else if (mq.addListener) mq.addListener(follow);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-kf-theme-toggle]');
    if (!btn) return;
    var next = current() === 'dark' ? 'light' : 'dark';
    root.classList.add('kf-theming');
    save(next);
    apply(next);
    setTimeout(function () { root.classList.remove('kf-theming'); }, 400);
  });
  document.addEventListener('DOMContentLoaded', function () { apply(current()); });
})();
