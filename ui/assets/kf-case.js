/* The case view, on one real verdict: app.html?inst=bank&case=BK-CS100112 (the queue links here).
   Case Lead explains the decision in the system's own words; each bot shows the records it owns;
   the evidence panel lists the records, the reason sentence by sentence, and the trace. The message
   box answers from this case's reason and records only. */
(function () {
  var K = window.Keystone, KF = window.KF;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var col = $('.k-app__col'), scroller = $('.k-app__scroll'), aside = $('#case');
  var ARROW = ($('.k-handrow svg') || { outerHTML: '' }).outerHTML;
  var DOT = ($('.k-event svg') || { outerHTML: '' }).outerHTML;
  var instBtn = $('.k-app__side > .k-btn'), roster = $$('.k-roster__item');
  var NAMES = roster.map(function (r) { return ($('.k-roster__name', r) || r).textContent.trim(); });
  var tabs = $$('[data-k-tab]', aside), panel = function (k) { return $('[data-k-panel="' + k + '"]', aside); };
  var form = $('.k-ask'), input = form && $('input', form);

  // only what works stays: no attachments, dictation or voice
  $$('.k-iconbtn, .k-voice', form).forEach(function (b) { b.remove(); });

  var inst = KF.inst(), c = null, run = null;
  var cid = KF.param('case');
  if (cid && KF.instOf(cid)) inst = KF.instOf(cid);

  function rec(id) {
    return '<div class="k-event kw-r">' + DOT + '<span><b>' + KF.esc(KF.kind(id)) + '</b> ' + KF.cite(c, id) + '</span></div>';
  }
  function caseView() {
    var lead = KF.lead(c);
    col.innerHTML =
      '<div class="k-msg k-msg--me">' + KF.esc(KF.V[c.verdict].q.replace('%s', c.case_id)) + '</div>' +
      '<div class="k-handrow">' + KF.botHTML('Case Lead') + ARROW + KF.botHTML(lead) +
      '<span><b>' + KF.esc(KF.title(c.reason_code)) + '</b> · ' + KF.esc(c.alert_ids.join(', ')) + '</span><a href="#case" data-kf-open>Open</a></div>' +
      '<div class="k-msgrow">' + KF.botHTML(lead) + '<div><div class="k-msgrow__body"><div class="kf-recs">' +
      c.evidence.map(rec).join('') + '</div></div></div></div>' +
      '<div class="k-msgrow">' + KF.botHTML('Case Lead') + '<div><div class="k-msgrow__body">' +
      '<div class="kw-verdict kw-r">' + KF.chip(c.verdict) + '<code>' + KF.esc(c.reason_code) + '</code></div>' +
      '<p class="kw-reason kw-r">' + KF.withCites(c, c.reason) + '</p></div></div></div>';
    KF.mountBots(col);
  }
  function botView(name) {
    var ids = KF.records(c, name), b = KF.BOTS[name];
    col.innerHTML =
      '<div class="k-msg k-msg--me">What did ' + KF.esc(name) + ' read in ' + KF.esc(c.case_id) + '?</div>' +
      '<div class="k-msgrow">' + KF.botHTML(name, ids.length ? 'done' : 'idle') + '<div><div class="k-msgrow__body">' +
      '<p class="kw-reason">' + KF.esc(name) + ' ' + b.does + '. ' + (ids.length ? 'In this case it read ' + ids.length + (ids.length === 1 ? ' record.' : ' records.') : 'There was nothing of that kind in this case.') + '</p>' +
      (ids.length ? '<div class="kf-recs">' + ids.map(function (id) {
        var s = KF.citing(c, id);
        return '<div class="k-event kw-r">' + DOT + '<span><b>' + KF.esc(KF.kind(id)) + '</b> ' + KF.cite(c, id) +
          (s.length ? '<br><small>' + KF.esc(KF.clip(s[0], 160)) + '</small>' : '') + '</span></div>';
      }).join('') + '</div>' : '') + '</div></div></div>';
    KF.mountBots(col);
  }

  function evidence() {
    var labels = { src: 'Records', abs: 'Reason', trace: 'Trace' };
    tabs.forEach(function (t) { var k = t.getAttribute('data-k-tab'); if (labels[k]) t.textContent = labels[k]; });
    var src = panel('src'), abs = panel('abs'), tr = panel('trace');
    src.setAttribute('aria-label', 'Records');
    src.innerHTML = c.evidence.map(function (id) {
      var s = KF.citing(c, id);
      return '<article class="k-doc"><div class="k-doc__head"><span>' + KF.esc(KF.kind(id)) + '</span><span>' + KF.esc(id) + '</span></div>' +
        (s.length ? s.map(function (x) { return '<p>' + KF.esc(x).split(id).join('<span class="k-hl is-on">' + id + '</span>') + '</p>'; }).join('')
          : '<p>Listed in the evidence. The reason does not quote it.</p>') + '</article>';
    }).join('') + '<p class="k-meta">The site shows each record’s id and the sentences that cite it, not the record itself.</p>';
    abs.setAttribute('aria-label', 'Reason');
    abs.innerHTML = '<article class="k-doc"><div class="k-doc__head"><span>Reason</span><span>' + KF.esc(c.reason_code) + '</span></div>' +
      KF.sentences(c.reason).map(function (x) { return '<p>' + KF.withCites(c, x) + '</p>'; }).join('') + '</article>' +
      '<p class="k-meta">Written by the system from the facts its checks used.' + (run.repeat_identical === true ? ' Run ' + run.repeat_runs + ' times, it wrote the same words each time.' : '') + '</p>';
    function step(bot, title, small, tool) {
      return '<div class="k-trace__step"><div class="k-row">' + KF.botHTML(bot) + '<b>' + KF.esc(title) + '</b>' + '' + '</div><small>' + small + '</small></div>';
    }
    tr.innerHTML = '<div class="k-trace is-on"><span class="k-trace__line"></span>' +
      '<div class="k-trace__step is-claim"><b>' + KF.esc(c.verdict + ' · ' + c.reason_code) + '</b></div>' +
      c.alert_ids.map(function (id) { return step('Payments Bot', 'Alert', 'Raised on this case ' + KF.cite(c, id)); }).join('') +
      c.evidence.map(function (id) {
        var s = KF.citing(c, id);
        return step(KF.owner(id), KF.kind(id), KF.esc(s.length ? KF.clip(s[0], 90) : 'In the evidence') + ' ' + KF.cite(c, id));
      }).join('') +
      step('Case Lead', 'Decided', KF.esc(c.verdict) + ' from ' + c.evidence.length + ' records', true) + '</div>';
    KF.mountBots(aside);
  }

  function rosterState(active) {
    roster.forEach(function (r, i) {
      var name = NAMES[i], n = name === 'Case Lead' ? 1 : KF.records(c, name).length, b = $('[data-k-bot]', r);
      r.setAttribute('aria-current', name === active ? 'true' : 'false');
      r.title = name + ' ' + KF.BOTS[name].does + (name === 'Case Lead' ? '' : ' (' + n + ' in this case)');
      if (b && b._kbot) b._kbot.set(n ? 'done' : 'idle');
    });
  }

  function render() {
    instBtn.firstChild.nodeValue = KF.instInfo(inst).name;
    caseView(); evidence(); rosterState('Case Lead');
    document.title = c.case_id + ' · Keystone';
    var u = new URL(location.href); u.searchParams.set('inst', inst); u.searchParams.set('case', c.case_id); history.replaceState(null, '', u);
    KF.ready();
  }

  // the institution button opens a menu of the four institutions
  var menu = null;
  function closeMenu() { if (menu) { menu.remove(); menu = null; instBtn.setAttribute('aria-expanded', 'false'); } }
  instBtn.setAttribute('aria-haspopup', 'true'); instBtn.setAttribute('aria-expanded', 'false');
  instBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (menu) return closeMenu();
    var r = instBtn.getBoundingClientRect();
    menu = document.createElement('div'); menu.className = 'kf-menu'; menu.setAttribute('role', 'menu');
    menu.style.left = (r.left + scrollX) + 'px'; menu.style.top = (r.bottom + scrollY + 6) + 'px';
    menu.innerHTML = KF.INST.map(function (x) { return '<button type="button" role="menuitem" data-inst="' + x.id + '"' + (x.id === inst ? ' aria-current="true"' : '') + '>' + KF.esc(x.long) + '</button>'; }).join('');
    document.body.appendChild(menu); instBtn.setAttribute('aria-expanded', 'true');
    menu.querySelector('button').focus();
    menu.addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-inst]'); if (!b) return;
      KF.setInst(b.dataset.inst); location.href = 'app.html?inst=' + b.dataset.inst;
    });
  });
  document.addEventListener('click', function (e) { if (menu && !menu.contains(e.target)) closeMenu(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });

  roster.forEach(function (r, i) {
    r.addEventListener('click', function () {
      if (!c) return;
      if (NAMES[i] === 'Case Lead') caseView(); else botView(NAMES[i]);
      rosterState(NAMES[i]); scroller.scrollTop = 0;
    });
  });

  // Open shows the evidence: the drawer on a narrow screen, the panel's first tab on a wide one
  col.addEventListener('click', function (e) {
    var o = e.target.closest('[data-kf-open]'); if (!o) return;
    e.preventDefault();
    var ev = $('.k-app__evbtn');
    if (ev && getComputedStyle(ev).display !== 'none' && aside.getBoundingClientRect().left >= innerWidth - 1) ev.click();
    if (tabs[0]) tabs[0].click();
    aside.scrollIntoView({ block: 'nearest' });
  });

  if (form) form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input.value.trim(); if (!q || !c) return;
    input.value = '';
    col.insertAdjacentHTML('beforeend', '<div class="k-msg k-msg--me">' + KF.esc(q) + '</div>' +
      '<div class="k-msgrow">' + KF.botHTML('Case Lead') + '<div><div class="k-msgrow__body"><p class="kw-reason">' + KF.withCites(c, KF.answer(c, q)) + '</p></div></div></div>');
    KF.mountBots(col);
    scroller.scrollTop = scroller.scrollHeight;
  });

  KF.load(inst).then(function (d) {
    run = d.run;
    c = (cid && d.byId[cid]) || d.decisions[0];
    render();
  }).catch(function (e) { KF.fail(col, e); });
})();
