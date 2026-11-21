/* The case view, on one real verdict: app.html?inst=bank&case=BK-CS100112 (the queue links here).
   Case Lead explains the decision as a one-line summary and a table of the SOP's checks, each marked
   passed, failed or not reached, with the system's own sentences beside them; each bot shows the records it owns;
   the evidence panel lists the records, each with the numbered step of the reason that cites it, and the
   reason as numbered steps. Question buttons ask
   Case Lead what this page can answer from the case itself, and the answers stay when a bot is
   opened and closed. Below them the analyst decides: agree with Keystone's verdict or pick a more
   cautious one, then go to the next undecided case. */
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
  var form = $('.k-ask');

  // only what works stays: no attachments, dictation or voice
  $$('.k-iconbtn, .k-voice', form).forEach(function (b) { b.remove(); });
  // the Trace tab repeated the Records tab, so it goes; the theme switch says what it does
  tabs = tabs.filter(function (t) {
    if (t.getAttribute('data-k-tab') !== 'trace') return true;
    var p = panel('trace'); if (p) p.remove(); t.remove(); return false;
  });
  $$('[data-k-theme]').forEach(function (b) { b.textContent = b.getAttribute('data-k-theme') === 'dark' ? 'Dark' : 'Light'; });

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

  // question buttons replace the free-text box: each one asks something this page can answer from
  // the case's own verdict, reason and records, so there is no guessing at a typed question
  var asks = document.createElement('div');
  asks.className = 'k-suggest kf-asks'; asks.setAttribute('role', 'group'); asks.setAttribute('aria-label', 'Ask Case Lead');
  bar.parentNode.insertBefore(asks, bar);
  if (form) form.remove();
  var QS = [['next', 'What happens next?'], ['mean', 'What does it mean?'], ['records', 'Which records decided it?'], ['same', 'Same answer every time?']];
  var said = [], view = 'Case Lead';
  function n(x) { return Number(x).toLocaleString('en-GB'); }
  function answer(k) {
    if (k === 'mean') return '<b>' + KF.esc(KF.title(c.reason_code)) + '.</b> ' + KF.esc(KF.describe(c.reason_code));
    if (k === 'records') {
      return 'It rests on ' + c.evidence.length + (c.evidence.length === 1 ? ' record: ' : ' records: ') +
        c.evidence.map(function (id) { return KF.esc(KF.kind(id).toLowerCase()) + ' ' + KF.cite(c, id); }).join(', ') + '. Tap one to see where the reason uses it.';
    }
    if (k === 'same') return 'Yes. Keystone decided all ' + n(run.cases) + ' cases at this firm ' + run.repeat_runs + ' times, and every run gave the same verdicts in the same words.';
    var st = standing[c.case_id];
    if (st) return 'Done: ' + KF.esc(KF.DID[st.action] || st.action) + '. Change takes it back, and Next case opens the next one.';
    if (c.verdict === 'CLOSE') return 'If you agree, close the case. Nothing is sent to the customer. If something on file doesn’t add up, send an RFI or escalate instead.';
    if (c.verdict === 'ESCALATE') return 'If you agree, escalate it. The MLRO, the firm’s money laundering reporting officer, decides whether to report it. Nothing is asked of the customer: a question could tip them off.';
    var ask = KF.sentences(c.reason).filter(function (t) { return /^Ask\b/.test(t); });
    return 'If you agree, send the request' + (ask.length ? '. It says: ' + KF.withCites(c, ask.join(' ')) : ' for the document the reason names.') +
      ' If you suspect crime, escalate instead: a question could tip the customer off.';
  }
  function showAsks() {
    asks.innerHTML = QS.filter(function (q) { return q[0] !== 'same' || run.repeat_identical === true; })
      .map(function (q) { return '<button type="button" data-kf-ask="' + q[0] + '">' + q[1] + '</button>'; }).join('');
  }
  asks.addEventListener('click', function (e) {
    var b = e.target.closest('[data-kf-ask]'); if (!b || !c) return;
    var html = '<div class="k-msg k-msg--me">' + KF.esc(b.textContent) + '</div>' +
      '<div class="k-msgrow">' + KF.botHTML('Case Lead') + '<div><div class="k-msgrow__body"><p class="kw-reason">' + answer(b.getAttribute('data-kf-ask')) + '</p></div></div></div>';
    said.push(html);
    if (view !== 'Case Lead') { view = 'Case Lead'; caseView(); rosterState('Case Lead'); }
    else { col.insertAdjacentHTML('beforeend', html); KF.mountBots(col); }
    scroller.scrollTop = scroller.scrollHeight;
  });
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
  /* The decision as a table: the SOP's checks in the order system/triage/decide.py runs them, each
     marked passed, failed or not reached, with the reason's own sentences beside the check they
     belong to. Every mark follows from the verdict and reason code alone: decide.py emits a close
     only when every check passed, an RFI only when there is no sign of crime, and stops at the first
     sign of crime. Checks the case never reached say so rather than guess. */
  var MK = {
    ok: '<span class="k-mk k-mk--ok" aria-hidden="true">✓</span>',
    bad: '<span class="k-mk k-mk--bad" aria-hidden="true">✕</span>',
    off: '<span class="k-mk kf-mk--off" aria-hidden="true">–</span>'
  };
  function checks(x) {
    var s = KF.sentences(x.reason), v = x.verdict, profile = x.reason_code === 'RFI_UPDATED_PROFILE';
    var unread = /could not read/.test(x.reason);
    var pick = function (re) { var out = s.filter(function (t) { return re.test(t); }); s = s.filter(function (t) { return !re.test(t); }); return out; };
    var ask = pick(/^Ask\b/), calm = pick(/^Nothing else (about the account )?is concerning\.?$/i);
    var rest = v === 'CLOSE' ? pick(/^The rest of the money received in the window/) : [];
    var over = profile ? pick(/SOP asks for an updated figure/) : [];
    var times = over.length && /(\d+(?:\.\d+)?) times the declared/.exec(over[0]);
    var limit = over.length && /at (\d+(?:\.\d+)?) times or more/.exec(over[0]);
    var rows = [];
    rows.push(v === 'ESCALATE'
      ? { name: 'Signs of crime', rule: 'Escalate on any sign of crime on file, and never ask the customer.', st: 'bad', word: unread ? 'Not fully read' : 'Found: ' + KF.title(x.reason_code), facts: s }
      : { name: 'Signs of crime', rule: 'Escalate on any sign of crime on file, and never ask the customer.', st: 'ok', word: 'None found', facts: calm.length ? calm : ['None of the signs of crime the SOP lists is on file.'] });
    rows.push(v === 'ESCALATE'
      ? { name: 'Alerts explained', rule: 'A document on file must explain every alert in the case.', st: 'off', word: 'Not needed', facts: ['A sign of crime outranks any explanation.'] }
      : v === 'CLOSE' || profile
        ? { name: 'Alerts explained', rule: 'A document on file must explain every alert in the case.', st: 'ok', word: 'Explained', facts: s }
        : { name: 'Alerts explained', rule: 'A document on file must explain every alert in the case.', st: 'bad', word: 'Not explained', facts: s });
    if (rest.length) rows.push({ name: 'Money left over', rule: 'Money with no document must stay within the alert’s limit.', st: 'ok', word: 'Within the limit', facts: rest });
    var passed = v === 'CLOSE' || profile;
    rows.push({ name: 'New payments left over', rule: 'No payment of £1,000 or more from a party new to the account may be left without a document.',
      st: passed ? 'ok' : 'off', word: passed ? 'None left' : 'Not reached', facts: [] });
    if (inst === 'payments_fx') rows.push({ name: 'Held payment', rule: 'A held payment at or above the SOP’s invoice threshold needs a matching invoice or contract before release.',
      st: passed ? 'ok' : 'off', word: passed ? 'Passed' : 'Not reached', facts: [] });
    if (profile) rows.push({ name: 'Declared figure', rule: 'Own-account money must not take receipts to ' + (limit ? limit[1] : '5') + ' times the declared figure or more.',
      st: 'bad', word: times ? times[1] + ' times' : 'Over the limit', facts: over });
    return { rows: rows, ask: ask };
  }
  function checksHTML(x) {
    var r = checks(x), n = { ok: 0, bad: 0, off: 0 }, profile = x.reason_code === 'RFI_UPDATED_PROFILE';
    var body = r.rows.map(function (row) {
      n[row.st]++;
      return '<tr class="kf-ck--' + row.st + '"><th scope="row"><b>' + KF.esc(row.name) + '</b><span class="k-why">' + KF.esc(row.rule) + '</span></th>' +
        '<td class="kf-ck__res"><span class="kf-ck__in">' + MK[row.st] + '<span>' + KF.esc(row.word) + '</span></span></td>' +
        '<td class="kf-ck__facts">' + (row.facts.length ? row.facts.map(function (t) { return '<p>' + KF.withCites(x, t) + '</p>'; }).join('') : '<p class="kf-ck__none">–</p>') + '</td></tr>';
    }).join('');
    var next = x.verdict === 'CLOSE' ? 'Close the case. Nothing is sent to the customer.'
      : x.verdict === 'ESCALATE' ? 'Escalate to the MLRO. Nothing is asked of the customer, because a question could tip them off.'
      : (r.ask.length ? r.ask.join(' ') : 'Ask the customer for the document the reason names.');
    body += '<tr class="kf-ck--verdict"><th scope="row"><b>Verdict</b><span class="k-why">The first check that fails decides it.</span></th>' +
      '<td class="kf-ck__res">' + KF.chip(x.verdict) + '</td><td class="kf-ck__facts"><p>' + KF.withCites(x, next) + '</p></td></tr>';
    var summary = x.verdict === 'CLOSE' ? 'Nothing on file points to crime, and documents explain every alert.'
      : x.verdict === 'ESCALATE' ? 'A sign of crime is on file, so the MLRO decides and the customer is not asked.'
      : profile ? 'Nothing points to crime, but the customer’s own-account money is far above their declared figure.'
      : 'Nothing points to crime, but something has no document behind it. One request would settle it.';
    var tally = [n.ok + ' passed', n.bad + ' failed'].concat(n.off ? [n.off + ' not reached'] : []).join(' · ');
    return '<p class="kw-reason kw-r kf-sum">' + KF.esc(summary) + ' <span class="kf-tally">' + tally + '</span></p>' +
      '<div class="k-tablewrap kw-r kf-checks"><table class="k-table"><caption class="k-sr">How Keystone decided ' + KF.esc(x.case_id) + '</caption>' +
      '<thead><tr><th scope="col">Check</th><th scope="col">Result</th><th scope="col">What the file shows</th></tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  function caseView() {
    var lead = KF.lead(c);
    col.innerHTML =
      '<div class="k-msg k-msg--me">' + KF.esc(KF.V[c.verdict].q.replace('%s', c.case_id)) + '</div>' +
      '<div class="k-handrow">' + KF.botHTML('Case Lead') + ARROW + KF.botHTML(lead) +
      '<span><b>' + KF.esc(KF.alerts(c)) + '</b> · ' + KF.esc(c.alert_ids.join(', ')) + '</span><a href="#case" data-kf-open>Open</a></div>' +
      '<div class="k-msgrow">' + KF.botHTML(lead) + '<div><div class="k-msgrow__body"><div class="kf-recs">' +
      c.evidence.map(rec).join('') + '</div></div></div></div>' +
      '<div class="k-msgrow">' + KF.botHTML('Case Lead') + '<div><div class="k-msgrow__body">' +
      '<div class="kw-verdict kw-r">' + KF.chip(c.verdict) + '<b class="kf-what">' + KF.esc(KF.title(c.reason_code)) + '</b>' + KF.code(c.reason_code) + '</div>' +
      checksHTML(c) + '</div></div></div>' +
      said.join('');
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
    var labels = { src: 'Records', abs: 'Reason' };
    tabs.forEach(function (t) { var k = t.getAttribute('data-k-tab'); if (labels[k]) t.textContent = labels[k]; });
    var src = panel('src'), abs = panel('abs');
    src.setAttribute('aria-label', 'Records');
    src.innerHTML = c.evidence.map(function (id) {
      var s = KF.citing(c, id);
      return '<article class="k-doc"><div class="k-doc__head"><span>' + KF.esc(KF.kind(id)) + '</span><span>' + KF.esc(id) + '</span></div>' +
        (s.length ? s.map(function (x) {
          return '<p class="kf-cited"><span class="kf-stepn" title="Step ' + KF.stepOf(c, x) + ' of the reason">' + KF.stepOf(c, x) + '</span>' +
            KF.esc(x).split(KF.esc(id)).join('<span class="k-hl is-on">' + KF.esc(id) + '</span>') + '</p>';
        }).join('')
          : '<p>Listed in the evidence. The reason does not quote it.</p>') + '</article>';
    }).join('') + '<p class="k-meta">The site shows each record’s id and the sentences that cite it, not the record itself.</p>';
    abs.setAttribute('aria-label', 'Reason');
    abs.innerHTML = '<article class="k-doc"><div class="k-doc__head"><span>' + KF.esc(KF.title(c.reason_code)) + '</span>' + KF.code(c.reason_code) + '</div>' +
      KF.steps(c) + '</article>' +
      '<p class="k-meta">Written by the system from the facts its checks used.' + (run.repeat_identical === true ? ' Run ' + run.repeat_runs + ' times, it wrote the same words each time.' : '') + '</p>';
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
    caseView(); evidence(); rosterState('Case Lead'); showBar(); showAsks();
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
      view = NAMES[i];
      if (view === 'Case Lead') caseView(); else botView(view);
      rosterState(view); scroller.scrollTop = 0;
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

  Promise.all([KF.load(inst), refresh()]).then(function (r) {
    data = r[0]; run = data.run;
    c = (cid && data.byId[cid]) || data.decisions[0];
    render();
  }).catch(function (e) { KF.fail(col, e); });
})();
