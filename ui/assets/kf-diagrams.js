/* Keystone · Financial Crime: the landing page's two moving diagrams.

   False alarms, counted: a hundred alerts, and the false ones go grey once the strip is in view. The
   page's resting state is the end state, so without script or with reduced motion it reads the same.

   The order is the rule: three cases take turns down the three checks. Each stops at the first check
   that decides it, so case A, with a fraud report on file, never reaches the question for the customer. */
(function () {
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (still) return;

  var grid = document.querySelector('[data-fa]');
  if (grid && 'IntersectionObserver' in window) {
    for (var i = 0; i < grid.children.length; i++) grid.children[i].style.setProperty('--i', i);
    grid.classList.add('pre');
    var seen = new IntersectionObserver(function (es) {
      for (var j = 0; j < es.length; j++) if (es[j].isIntersecting) {
        setTimeout(function () { grid.classList.remove('pre'); }, 250);
        seen.disconnect();
      }
    }, { threshold: 0.5 });
    seen.observe(grid);
  }

  var box = document.querySelector('[data-gates]');
  if (box) {
    var gates = [].slice.call(box.querySelectorAll('.kl-gate')), cap = box.querySelector('[data-case]');
    var CASES = [
      { t: '<b>Case A</b> · another bank has reported fraud', stop: 0 },
      { t: '<b>Case B</b> · a solicitor’s letter matches the payment', stop: 1 },
      { t: '<b>Case C</b> · £30,000 paid in, nothing on file', stop: 2 }
    ];
    var n = 0;
    box.classList.add('run');
    (function play() {
      var c = CASES[n++ % CASES.length], k = 0;
      cap.innerHTML = c.t;
      gates.forEach(function (g) { g.classList.remove('pass', 'hit', 'skip', 'never'); });
      (function step() {
        if (k < c.stop) { gates[k++].classList.add('pass'); setTimeout(step, 550); return; }
        gates[k].classList.add('hit');
        for (var j = k + 1; j < gates.length; j++) gates[j].classList.add('skip');
        if (c.stop === 0) gates[gates.length - 1].classList.add('never');
      })();
      setTimeout(play, 3800);
    })();
  }
})();
