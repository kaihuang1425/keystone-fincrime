/* Keystone · Financial Crime: the phone scene on the landing page.

   A miniature of phone.html, playing the MLRO's first escalation from data/bank.json in the order the
   system wrote it (the case the real phone page opens on). The bots read their records, the reason
   arrives with its records named, a tap on one shows the sentence that cites it, the MLRO takes the
   case, and the next escalation moves up. About 16 seconds, then it starts again. It plays only while
   on screen. The drawn markup is the same case, so the scene still plays if the verdicts fail to load.

   Steps are classes on the frame that only move forward (s1 to s6), plus flags for things that open
   and close (mk, pop, gone, toast). Tapping the frame opens the real phone page on that case. */
(function () {
  var el = document.getElementById('scene-phone');
  if (!el) return;
  var KF = window.KF, K = window.Keystone;
  var $ = function (s) { return el.querySelector(s); };
  var ticket = $('[data-ticket]'), records = $('[data-records]'), chips = $('[data-chips]'), pop = $('[data-pop]');
  var apTitle = $('[data-ap-title]'), apCode = $('[data-ap-code]'), approve = $('.k-approve'), take = $('[data-take]');
  var firstChip = function () { return chips.querySelector('.lp-tapme') || chips.querySelector('.lp-chip'); };
  var toastText = $('[data-toast]'), next = $('[data-next]');
  var steps = document.querySelector('.lp-steps[data-for="scene-phone"]');
  var ticketHTML = ticket.innerHTML, nextHTML = next.innerHTML;
  var bots = {};
  Array.prototype.forEach.call(el.querySelectorAll('[data-k-bot]'), function (b) { bots[b.getAttribute('data-name')] = b; });
  var order = ['Payments Bot', 'Screening Bot', 'Document Bot', 'Match Bot'], busy = order.slice(0, 3);
  var reduce = false;
  try { reduce = document.documentElement.getAttribute('data-k-motion') === 'system' && matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  function bot(name, state) {
    var b = bots[name]; if (!b) return;
    var c = (K && K.bot) ? K.bot(b) : null;
    if (c && c.set) c.set(state); else b.setAttribute('data-state', state);
  }
  function step(n) {
    for (var i = 1; i <= n; i++) el.classList.add('s' + i);
    if (steps) Array.prototype.forEach.call(steps.children, function (li) {
      li.classList.toggle('on', n >= +li.getAttribute('data-k'));
    });
  }
  function flag(f, on) { el.classList.toggle(f, on !== false); }
  function tap(node) {
    if (!node) return;
    node.classList.remove('tap'); void node.offsetWidth; node.classList.add('tap');
  }

  /* ---------- the case, from the real verdicts ---------- */
  function fill(d) {
    var list = d.decisions.filter(function (x) { return x.verdict === 'ESCALATE'; });
    var c = list[0]; if (!c) return;
    var s = KF.sentences(c.reason);
    ticketHTML = '<small>' + KF.esc(c.case_id) + ' · ' + KF.alerts(c) + ' · 1 of ' + list.length + '</small>' + KF.amounts(KF.clip(s[0], 200));
    records.textContent = c.evidence.length + (c.evidence.length === 1 ? ' record supports it' : ' records support it');
    var pick = c.evidence.slice(0, 3);
    // tap the record whose sentence the ticket does not already show
    var shown = KF.clip(s[0], 200), tapId = pick.filter(function (id) {
      return KF.citing(c, id).some(function (x) { return x !== s[0]; });
    })[0] || pick[0];
    chips.innerHTML = pick.map(function (id) { return '<span class="lp-chip' + (id === tapId ? ' lp-tapme' : '') + '">' + KF.esc(id) + '</span>'; }).join('') +
      (c.evidence.length > 3 ? '<span>and ' + (c.evidence.length - 3) + ' more</span>' : '');
    var cited = KF.citing(c, tapId).filter(function (x) { return x !== shown; });
    pop.innerHTML = KF.esc(cited.length ? cited.join(' ') : 'Listed in the evidence for this decision.') +
      '<small>' + KF.esc(tapId) + ' · ' + KF.esc(KF.kind(tapId)) + '</small>';
    apTitle.textContent = KF.title(c.reason_code);
    apCode.textContent = c.reason_code;
    toastText.textContent = KF.DID.escalation_taken + ': ' + c.case_id + '.';
    busy = order.filter(function (name) { return KF.records(c, name).length; });
    var n = list[1];
    if (n) nextHTML = '<small>' + KF.esc(n.case_id) + ' · ' + KF.alerts(n) + ' · 1 of ' + (list.length - 1) + '</small>' + KF.amounts(KF.clip(KF.sentences(n.reason)[0], 140));
    el.href = 'phone.html?inst=bank&case=' + encodeURIComponent(c.case_id);
    el.setAttribute('aria-label', 'Animation of the phone view. The bots read the records on escalation ' + c.case_id +
      ', the reason names each record, a tap on ' + tapId + ' shows the sentence that cites it, and the MLRO takes the case. Opens the phone view on this case.');
  }

  /* ---------- the story ---------- */
  var timers = [], playing = false;
  function at(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function clear() { timers.forEach(clearTimeout); timers = []; }
  // back to the start at once: the screen fades out before a loop ends, so the snap is never seen
  function reset() {
    el.classList.add('rs');
    el.className = el.className.replace(/\b(s\d|mk|pop|gone|toast|out)\b/g, '').replace(/\s+/g, ' ').trim();
    approve.classList.remove('is-gone');
    ticket.innerHTML = ''; next.innerHTML = '';
    Object.keys(bots).forEach(function (n) { bot(n, 'idle'); });
    if (steps) Array.prototype.forEach.call(steps.children, function (li) { li.classList.remove('on'); });
    void el.offsetWidth;
    el.classList.remove('rs');
  }
  function finish() {
    clear(); reset();
    ticket.innerHTML = ticketHTML;
    busy.forEach(function (n) { bot(n, 'done'); }); bot('Case Lead', 'waiting');
    step(4); flag('mk');
  }
  function play() {
    clear(); reset();
    at(300, function () { step(1); ticket.innerHTML = ticketHTML; bot('Case Lead', 'working'); });
    busy.forEach(function (name, i) {
      at(500 + i * 700, function () { bot(name, 'working'); });
      at(1150 + i * 700, function () { bot(name, 'done'); });
    });
    var t = 500 + busy.length * 700;
    at(t + 200, function () { step(2); });
    at(t + 900, function () { flag('mk'); });
    at(t + 1800, function () { tap(firstChip()); });
    at(t + 2000, function () { flag('pop'); });
    at(t + 5000, function () { flag('pop', false); });
    at(t + 5300, function () { step(3); bot('Case Lead', 'waiting'); });
    at(t + 5900, function () { step(4); });
    at(t + 7400, function () { tap(take); });
    at(t + 7800, function () { flag('gone'); approve.classList.add('is-gone'); step(5); flag('toast'); bot('Case Lead', 'done'); });
    at(t + 8800, function () { next.innerHTML = nextHTML; step(6); });
    at(t + 10800, function () { flag('toast', false); });
    at(t + 12500, function () { flag('out'); });
    at(t + 13000, play);
  }
  function start() { if (playing) return; playing = true; if (reduce) finish(); else play(); }
  function stop() { if (!playing) return; playing = false; clear(); }

  finish();
  if (KF && KF.load) KF.load('bank').then(fill).catch(function (e) { console.error(e); }).then(function () { if (!playing) finish(); });
  if (reduce || !('IntersectionObserver' in window)) { start(); return; }
  var inView = false;
  new IntersectionObserver(function (es) {
    es.forEach(function (e) { inView = e.isIntersecting; if (inView && !document.hidden) start(); else stop(); });
  }, { threshold: 0.35 }).observe(el);
  document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); else if (inView) start(); });
})();

/* The five runs under "same answer every run" show the bank's real output fingerprint, from the run
   facts tools/export_ui.py wrote beside the verdicts. */
(function () {
  var KF = window.KF, cells = document.querySelectorAll('[data-sha]');
  if (!KF || !KF.load || !cells.length) return;
  KF.load('bank').then(function (d) {
    var sha = d.run && d.run.output_sha256;
    if (!sha || !d.run.repeat_identical) return;
    Array.prototype.forEach.call(cells, function (c) { c.textContent = sha.slice(0, 12); });
  }).catch(function () {});
})();
