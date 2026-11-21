/* Keystone · Financial Crime: light and dark on the landing page.

   Load this in <head>, before the stylesheets paint, so the page never flashes the wrong theme.
   The page opens dark. A visitor's own choice is kept in local storage and wins on later visits.
   Any [data-kf-theme-toggle] button flips the theme. */
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
  }

  apply(saved() || 'dark');

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
