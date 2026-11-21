/* Keystone · Financial Crime: the landing page, on the system's real verdicts.

   The canvas draws four invented rows in the hero and an invented reason under the five runs. Here they
   become the bank's first two closes, first RFI and first escalation, in the order the system wrote them
   (the way the queue page picks), and the reason is the first close's own. Nothing is random, so every
   visit shows the same cases in the same words, and each row opens its case. If the verdicts are slow or
   missing, the drawn rows show instead of an empty panel. */
(function () {
  var KF = window.KF;
  var list = document.querySelector('.lp-q'), reason = document.querySelector('.kl-reason');
  if (!KF || !list) { document.documentElement.classList.remove('kf-wait'); return; }

  var INST = 'bank';
  var TIMING = [[0.3, 0.9, 2.3], [0.45, 2.6, 4], [0.6, 4.3, 5.7], [0.75, 6, 7.4]]; // --d, --w, --m, as drawn
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
    var t = TIMING[k];
    return '<a class="kq-row kw-r" href="app.html?inst=' + INST + '&amp;case=' + encodeURIComponent(c.case_id) + '"' +
      ' style="--d: ' + t[0] + 's; --w: ' + t[1] + 's; --m: ' + t[2] + 's;">' +
      '<span class="kw-swap"><span class="kw-dots"><i></i><i></i><i></i></span>' + KF.mark(c.verdict) + '</span>' +
      '<span><b>' + KF.esc(KF.title(c.reason_code)) + '</b><span class="kq-line"><span class="q">Queued</span>' +
      '<span class="a">Reading ' + c.evidence.length + ' records</span>' +
      '<span class="b">' + KF.esc(c.case_id) + ' · ' + KF.alerts(c) + '</span></span></span>' +
      '<span class="kq-end">' + KF.chip(c.verdict) + '<code>' + KF.esc(c.reason_code) + '</code></span></a>';
  }
  // the reason, with each record it cites and each amount lit in turn
  function lit(c) {
    var ids = c.evidence.map(function (e) { return KF.esc(e).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
    var re = new RegExp('(' + ids.concat(['£[\\d,]+\\.\\d{2}']).join('|') + ')', 'g'), n = 0;
    return KF.esc(c.reason).replace(re, function (m) {
      return n < 6 ? '<span class="kw-hl" style="--d: ' + (0.2 + 0.4 * n++).toFixed(1) + 's;">' + m + '</span>' : m;
    });
  }

  KF.load(INST).then(function (d) {
    var cases = pick(d);
    if (cases.length < 4) throw new Error('fewer than four verdicts in data/' + INST + '.json');
    list.innerHTML = cases.map(row).join('');
    list.setAttribute('aria-label', KF.instInfo(INST).name + ': the first four verdicts, in the order the system wrote them');
    var close = cases.filter(function (c) { return c.verdict === 'CLOSE'; })[0];
    if (reason && close) reason.innerHTML = lit(close);
  }).catch(function (e) {
    console.error(e); // the drawn rows stay
  }).then(function () {
    clearTimeout(fallback);
    KF.ready();
  });
})();
