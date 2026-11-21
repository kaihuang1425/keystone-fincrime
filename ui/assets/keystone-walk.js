/* Keystone walkthrough. Loaded after keystone.js, with keystone-walk.css.
   Turns a [data-kw] block into a story that plays itself: one tab per step, each tab carrying its own
   progress line, one panel per step. Showing a panel restarts its staged reveal (the .kw-r pieces and
   their --d delays). It plays only while on screen, and picking a step by hand pauses it.

   Markup: .kw[data-kw] > .kw-tabs > .kw-tab[style="--dur: 7s"] (one per step), a .kw-count,
   [data-kw-prev] [data-kw-play] [data-kw-next], and .kw-stage > .kw-panel (one per step).
   URL switches for recording: ?step=3 opens on step 3, ?hold starts paused. */
(function () {
  function init(root) {
    if (!root || root._kw) return;
    var tabs = [].slice.call(root.querySelectorAll('.kw-tab')), panels = [].slice.call(root.querySelectorAll('.kw-panel'));
    if (!tabs.length || tabs.length !== panels.length) return;
    root._kw = true;
    var count = root.querySelector('.kw-count'), playBtn = root.querySelector('[data-kw-play]');
    var q = location.search, m = q.match(/[?&]step=(\d+)/);
    var cur = 0, paused = root.classList.contains('is-paused') || /[?&]hold\b/.test(q), visible = true, seen = false;
    var acc = 0, last = performance.now(), bot = null, botDone = true;

    function dur(i) { return (parseFloat(tabs[i].style.getPropertyValue('--dur')) || 7) * 1000; }
    function paint() {
      root.classList.toggle('is-paused', paused || !visible);
      if (playBtn) { playBtn.textContent = paused ? 'Play' : 'Pause'; playBtn.setAttribute('aria-label', paused ? 'Play the walkthrough' : 'Pause the walkthrough'); }
    }
    function show(i, byUser) {
      cur = (i + tabs.length) % tabs.length; acc = 0;
      if (byUser) paused = true;
      tabs.forEach(function (t, k) { t.setAttribute('aria-selected', 'false'); t.classList.toggle('is-done', k < cur); t.tabIndex = k === cur ? 0 : -1; });
      void tabs[cur].offsetWidth;                       // restarts the tab's progress line
      tabs[cur].setAttribute('aria-selected', 'true');
      panels.forEach(function (p, k) { p.hidden = k !== cur; });
      var p = panels[cur]; p.hidden = true; void p.offsetWidth; p.hidden = false;   // restarts the staged reveal
      var name = tabs[cur].querySelector('b');
      if (count) count.textContent = 'Step ' + (cur + 1) + ' of ' + tabs.length + ' · ' + (name ? name.textContent : '');
      var el = p.querySelector('.kw-con__head [data-k-bot]');
      bot = el && el._kbot ? el._kbot : null; botDone = true;
      if (bot) {
        if (!el.hasAttribute('data-kw-rest')) el.setAttribute('data-kw-rest', el.getAttribute('data-state') || 'idle');
        var rest = el.getAttribute('data-kw-rest');
        bot.ack(); bot.set(rest);
        botDone = rest !== 'working';                   // a working bot finishes just before its step ends
      }
      var sc = tabs[cur].parentNode;
      if (sc.scrollWidth > sc.clientWidth) sc.scrollTo({ left: tabs[cur].offsetLeft - sc.clientWidth / 2 + tabs[cur].offsetWidth / 2, behavior: 'smooth' });
      paint();
    }
    function tick(now) {
      requestAnimationFrame(tick);
      var dt = Math.min(now - last, 100); last = now;   // a tab left in the background does not skip steps
      if (paused || !visible) return;
      acc += dt;
      if (!botDone && acc >= dur(cur) - 1300) { botDone = true; bot.set('done'); }
      if (acc >= dur(cur)) show(cur + 1, false);
    }
    tabs.forEach(function (t, k) { t.addEventListener('click', function () { show(k, true); }); });
    tabs[0].parentNode.addEventListener('keydown', function (e) {
      var k = e.key;
      if (k !== 'ArrowRight' && k !== 'ArrowLeft' && k !== 'Home' && k !== 'End') return;
      e.preventDefault();
      show(k === 'ArrowRight' ? cur + 1 : k === 'ArrowLeft' ? cur - 1 : k === 'Home' ? 0 : tabs.length - 1, true);
      tabs[cur].focus();
    });
    var prev = root.querySelector('[data-kw-prev]'), next = root.querySelector('[data-kw-next]');
    if (prev) prev.addEventListener('click', function () { show(cur - 1, true); });
    if (next) next.addEventListener('click', function () { show(cur + 1, true); });
    if (playBtn) playBtn.addEventListener('click', function () { paused = !paused; if (!paused && acc >= dur(cur) - 50) show(cur + 1, false); paint(); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          visible = e.isIntersecting && e.intersectionRatio > 0.3;
          if (visible && !seen) { seen = true; show(cur, false); }   // the first step plays once it is in view
          paint();
        });
      }, { threshold: [0, 0.3, 0.6] }).observe(root);
    }
    document.addEventListener('visibilitychange', function () { if (!document.hidden) show(cur, false); });   // the step and its line restart together
    show(m ? Math.max(0, Math.min(tabs.length - 1, +m[1] - 1)) : 0, false);
    requestAnimationFrame(tick);
  }
  function mount() { [].forEach.call(document.querySelectorAll('[data-kw]'), init); }
  if (window.Keystone) window.Keystone.walk = init;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(mount, 0); }); else setTimeout(mount, 0);
})();
