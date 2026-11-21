/* The case view, on one real verdict: app.html?inst=bank&case=BK-CS100112 (the queue links here).
   Case Lead explains the decision in the system's own words; each bot shows the records it owns;
   the evidence panel lists the records, the reason sentence by sentence, and the trace. The message
   box answers from this case's reason and records only. Above it the analyst decides: agree with
   Keystone's verdict or pick another, then go to the next undecided case. */
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

  var inst = KF.inst(), c = null, run = null, data = null, standing = {};
  var cid = KF.param('case');
  if (cid && KF.instOf(cid)) inst = KF.instOf(cid);

  // back to the queue, top left
  var back = document.createElement('a');
  back.className = 'k-btn k-btn--sm k-btn--text kf-back';
  back.innerHTML = '<span aria-hidden="true">←</span> Queue';
  $('.k-app__head').insertBefore(back, $('.k-app__head').firstChild);

  // the analyst's decision, above the message box: Keystone's verdict is the one primary button, and
  // text buttons beside it change it only towards more caution. A close can become an RFI or an
  // escalation, an RFI an escalation. An escalation is never turned into a question to the customer
  // (that could tip off a suspect) and is never closed here; the MLRO's Send back covers that.
  var bar = document.createElement('section');
  bar.className = 'k-approve kf-decide'; bar.setAttribute('aria-label', 'Your decision');
  if (form) form.parentNode.insertBefore(bar, form);
  var DO = {
    CLOSE: { act: 'closed', main: 'Close the case', alt: 'Close', did: 'Closed' },
    RFI: { act: 'rfi_sent', main: 'Send the request', alt: 'Send an RFI', did: 'RFI sent for' },
    ESCALATE: { act: 'escalated', main: 'Escalate to the MLRO', alt: 'Escalate', did: 'Escalated' }
  };
  var SAFER = { CLOSE: ['ESCALATE', 'RFI'], RFI: ['ESCALATE'], ESCALATE: [] };
  var VERDICT_OF = { closed: 'CLOSE', rfi_sent: 'RFI', escalated: 'ESCALATE', escalation_taken: 'ESCALATE', sent_back: 'ESCALATE' };
  var TICK = (K.icons && K.icons.tick) || '';

  function caseHref(x) { return 'app.html?inst=' + inst + '&case=' + encodeURIComponent(x.case_id); }
  function nextCase() {
    var n = data.decisions.length;
    for (var k = 1; k < n; k++) { var x = data.decisions[(c.i + k) % n]; if (!standing[x.case_id]) return x; }
    return null;
  }
  function showBar() {
    var st = standing[c.case_id];
    bar.classList.remove('is-busy');
    if (!st) {
      bar.innerHTML = KF.botHTML('Case Lead', 'waiting') + '<div class="k-approve__actions">' +
        SAFER[c.verdict].map(function (v) {
          return '<button type="button" class="k-btn k-btn--text" data-kf-do="' + v + '"><span>' + DO[v].alt + '</span>' + TICK + '</button>';
        }).join('') +
        '<button type="button" class="k-btn k-btn--primary" data-kf-do="' + c.verdict + '"><span>' + DO[c.verdict].main + '</span>' + TICK + '</button></div>';
    } else {
      var v = VERDICT_OF[st.action] || c.verdict, nx = nextCase();
      bar.innerHTML = KF.botHTML('Case Lead', 'done') + '<div class="k-approve__actions">' +
        '<span class="k-chip k-chip--' + KF.V[v].cls + '">' + KF.V[v].mk + ' ' + KF.esc(KF.DID[st.action] || st.action) + '</span>' +
        '<button type="button" class="k-btn k-btn--text" data-kf-change>Change</button>' +
        (nx ? '<a class="k-btn k-btn--primary" href="' + caseHref(nx) + '">Next case <span class="k-arr">→</span></a>'
            : '<a class="k-btn k-btn--primary" href="queue.html?inst=' + inst + '">Back to the queue <span class="k-arr">→</span></a>') + '</div>';
    }
    KF.mountBots(bar);
  }
  function refresh() {
    return KF.store.list().then(function (rows) { standing = KF.standing(rows); });
  }
  function decide(v, btn) {
    var x = c, ask = KF.sentences(x.reason).filter(function (t) { return /^Ask\b/.test(t); });
    var note = v !== x.verdict ? 'Keystone said ' + x.verdict : (v === 'RFI' && ask.length ? ask.join(' ') : null);
    bar.classList.add('is-busy');
    KF.act(run, x, DO[v].act, note).then(function () {
      btn.style.width = btn.offsetWidth + 'px'; void btn.offsetWidth; btn.classList.add('is-done');
      return refresh().then(function () {
        setTimeout(function () {
          if (c !== x) return;
          showBar();
          K.toast(DO[v].did + ' ' + x.case_id + '. Saved in ' + KF.store.where + '.', { undo: function () { undo(x); } });
        }, 520);
      });
    }).catch(function (e) { bar.classList.remove('is-busy'); K.toast('Not saved: ' + e.message, { mark: 'bad' }); });
  }
  function undo(x) {
    if (!standing[x.case_id]) return;
    KF.act(run, x, 'undone').then(refresh).then(function () { if (c === x) showBar(); });
  }
  bar.addEventListener('click', function (e) {
    if (bar.classList.contains('is-busy')) return;
    var b = e.target.closest('[data-kf-do]');
    if (b) return decide(b.getAttribute('data-kf-do'), b);
    if (e.target.closest('[data-kf-change]')) undo(c);
  });

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
    caseView(); evidence(); rosterState('Case Lead'); showBar();
    back.href = 'queue.html?inst=' + inst;
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

  Promise.all([KF.load(inst), refresh()]).then(function (r) {
    data = r[0]; run = data.run;
    c = (cid && data.byId[cid]) || data.decisions[0];
    render();
  }).catch(function (e) { KF.fail(col, e); });
})();
