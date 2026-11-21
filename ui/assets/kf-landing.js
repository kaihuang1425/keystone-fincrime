/* Keystone · Financial Crime: the landing page, on the system's real verdicts.

   The hero's live line shows the bank's first two closes, first RFI and first escalation, one at a time,
   in the order the system wrote them (the way the queue page picks). The reason under the five runs is the
   first close's own, as numbered steps, with a link to that case. Nothing is random, so every visit shows the same cases in the same words, and each
   line opens its case. The page ships the same four cases as a fallback, so a slow load shows them too. */
(function () {
  var KF = window.KF;
  var live = document.querySelector('.lp-live'), reason = document.querySelector('.kl-reason');
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!KF || !live) { document.documentElement.classList.remove('kf-wait'); return; }

  var INST = 'bank';
  var fallback = setTimeout(KF.ready, 1500);

  function pick(d) {
    var want = { CLOSE: 2, RFI: 1, ESCALATE: 1 }, out = [];
    for (var i = 0; i < d.decisions.length && out.length < 4; i++) {
      var c = d.decisions[i];
      if (want[c.verdict]) { want[c.verdict]--; out.push(c); }
    }
    return out;
  }
  function row(c, k) {
    return '<a class="lp-live__row' + (k === 0 ? ' is-on' : '') + '" href="app.html?inst=' + INST + '&amp;case=' + encodeURIComponent(c.case_id) + '">' +
      KF.chip(c.verdict) + '<b>' + KF.esc(KF.title(c.reason_code)) + '</b><code>' + KF.esc(c.case_id) + '</code></a>';
  }
  // the reason as numbered steps, one sentence each: each record it cites and each amount lit in turn
  // across the steps, and the records each step names beside it
  function lit(c) {
    var ids = c.evidence.map(function (e) { return KF.esc(e).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
    var re = new RegExp('(' + ids.concat(['£[\\d,]+\\.\\d{2}']).join('|') + ')', 'g'), n = 0;
    return KF.stepItems(c, { text: function (x) {
      return KF.esc(x).replace(re, function (m) {
        return n < 6 ? '<span class="kw-hl" style="--d: ' + (0.2 + 0.4 * n++).toFixed(1) + 's;">' + m + '</span>' : m;
      });
    } });
  }
  // one line at a time; it holds while the pointer or focus is on it, so it can be clicked
  var at = 0, held = false;
  live.addEventListener('mouseenter', function () { held = true; });
  live.addEventListener('mouseleave', function () { held = false; });
  live.addEventListener('focusin', function () { held = true; });
  live.addEventListener('focusout', function () { held = false; });
  if (!still) setInterval(function () {
    var rows = live.children;
    if (held || rows.length < 2) return;
    rows[at % rows.length].classList.remove('is-on');
    at = (at + 1) % rows.length;
    rows[at].classList.add('is-on');
  }, 2800);

  KF.load(INST).then(function (d) {
    var cases = pick(d);
    if (cases.length < 4) throw new Error('fewer than four verdicts in data/' + INST + '.json');
    at = 0;
    live.innerHTML = cases.map(row).join('');
    live.setAttribute('aria-label', KF.instInfo(INST).name + ': the first four decisions, in the order the system wrote them');
    var close = cases.filter(function (c) { return c.verdict === 'CLOSE'; })[0];
    if (reason && close) {
      reason.innerHTML = lit(close);
      var open = document.querySelector('.kl-open');
      if (open) { open.href = 'app.html?inst=' + INST + '&case=' + encodeURIComponent(close.case_id); open.hidden = false; }
    }
  }).catch(function (e) {
    console.error(e); // the shipped lines stay
  }).then(function () {
    clearTimeout(fallback);
    KF.ready();
  });
})();
