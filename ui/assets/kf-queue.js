/* The alert queue, on the system's real verdicts. Six cases at a time (three closes, one RFI, two
   escalations, in the order the system wrote them); each row opens the case. The RFI card sends the
   system's request, editable first, and Undo takes it back. */
(function () {
  var K = window.Keystone, KF = window.KF;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var list = $('.kq-list'), card = $('[data-kq]'), approve = $('.k-approve'), h1turn = $('h1 .k-turn');
  var headTitle = $('h2', card.firstElementChild), replayBtn = $('[data-kq-replay]');
  var insts = $$('.aq-inst'), ORDER = ['bank', 'payments_fx', 'emoney', 'investment'];
  var msg = $('.k-ticket__msg', approve), codeRow = $$('.k-row', approve)[1], btnRow = $$('.k-row', approve)[2];
  var editBtn = $('.k-btn--text', btnRow), sendBtn = $('.k-btn--primary', btnRow);
  sendBtn.removeAttribute('data-k-approve');

  var inst = KF.inst(), data = null, standing = {}, cursor = 0, shown = [], rfi = null;

  // Next six, beside Replay
  var nextBtn = document.createElement('button');
  nextBtn.type = 'button'; nextBtn.className = 'k-btn k-btn--sm'; nextBtn.textContent = 'Next six';
  replayBtn.parentNode.insertBefore(nextBtn, replayBtn);
  replayBtn.parentNode.style.gap = '8px';

  function pick(d, from) {
    var want = { CLOSE: 3, RFI: 1, ESCALATE: 2 }, out = [], n = d.decisions.length;
    for (var k = 0; k < n && out.length < 6; k++) {
      var c = d.decisions[(from + k) % n];
      if (standing[c.case_id] || !want[c.verdict]) continue;
      want[c.verdict]--; out.push(c);
    }
    return out.sort(function (a, b) { return a.i - b.i; });
  }
  function nextRfi(d, from) {
    var n = d.decisions.length;
    for (var k = 0; k < n; k++) { var c = d.decisions[(from + k) % n]; if (c.verdict === 'RFI' && !standing[c.case_id]) return c; }
    return null;
  }
  function occ(cases) {
    return cases.map(function (c) { return '<i' + (c.verdict === 'RFI' ? ' class="is-ask"' : c.verdict === 'ESCALATE' ? ' class="is-bad"' : '') + '></i>'; }).join('');
  }
  function occLabel(cases) {
    var t = tally(cases); return t.CLOSE + ' closed, ' + t.RFI + ' asked, ' + t.ESCALATE + ' escalated';
  }
  function tally(cases) {
    var t = { CLOSE: 0, RFI: 0, ESCALATE: 0 }; cases.forEach(function (c) { t[c.verdict]++; }); return t;
  }
  function href(c) { return 'app.html?inst=' + inst + '&case=' + encodeURIComponent(c.case_id); }

  function row(c) {
    var st = standing[c.case_id];
    return '<a class="kq-row kw-r" href="' + href(c) + '" data-case="' + KF.esc(c.case_id) + '">' +
      '<span class="kw-swap"><span class="kw-dots"><i></i><i></i><i></i></span>' + KF.mark(c.verdict) + '</span>' +
      '<span><b>' + KF.esc(KF.title(c.reason_code)) + '</b><span class="kq-id">' + KF.esc(c.case_id) + ' · ' + KF.alerts(c) +
      (st ? '<span class="kq-done"> · ' + KF.DID[st.action] + '</span>' : '') + '</span>' +
      '<span class="kq-line"><span class="q">Queued</span><span class="a">Reading ' + c.evidence.length + ' records</span>' +
      '<span class="b">' + KF.esc(KF.clip(KF.sentences(c.reason)[0], 118)) + '</span></span></span>' +
      '<span class="kq-end">' + KF.chip(c.verdict) + '<code>' + KF.esc(c.reason_code) + '</code></span></a>';
  }

  function renderList() {
    var t = tally(shown), run = data.run;
    list.innerHTML = shown.map(row).join('') +
      '<div class="kq-tally kw-r"><span class="k-chip k-chip--ok">✓ ' + t.CLOSE + ' closed</span><span class="k-chip k-chip--ask">? ' + t.RFI + ' asked</span>' +
      '<span class="k-chip k-chip--bad">↑ ' + t.ESCALATE + ' escalated</span>' + repeat(run) + '</div>';
    headTitle.textContent = KF.instInfo(inst).name + ' · queue';
  }

  function renderApprove() {
    rfi = nextRfi(data, cursor);
    if (!rfi) {
      msg.innerHTML = '<small>' + KF.esc(KF.instInfo(inst).name) + '</small>Every RFI in this queue has been sent.';
      codeRow.style.display = 'none'; btnRow.style.display = 'none';
      if (h1turn) h1turn.textContent = 'Nothing left to send.';
      return;
    }
    var s = KF.sentences(rfi.reason), ask = s.filter(function (x) { return /^Ask\b/.test(x); });
    msg.innerHTML = '<small>What to ask · <a href="' + href(rfi) + '">' + KF.esc(rfi.case_id) + '</a></small><span class="kf-draft">' + KF.esc((ask.length ? ask : s.slice(-1)).join(' ')) + '</span>';
    codeRow.innerHTML = KF.chip('RFI') + '<span class="kq-id">' + KF.esc(rfi.reason_code) + '</span>';
    codeRow.style.display = ''; btnRow.style.display = '';
    editBtn.textContent = 'Edit';
    if (h1turn) h1turn.textContent = 'One question to send.';
  }

  function renderInsts(all) {
    insts.forEach(function (el, i) {
      var id = ORDER[i], d = all[i];
      el.setAttribute('role', 'button'); el.tabIndex = 0;
      el.setAttribute('aria-current', id === inst ? 'true' : 'false');
      var cases = id === inst ? shown : pick(d, 0), o = $('.k-occ', el), small = $('small', el);
      if (o) { o.innerHTML = occ(cases); o.setAttribute('aria-label', occLabel(cases)); }
      if (small) small.textContent = d.run.cases.toLocaleString('en-GB') + ' cases';
      if (small) small.title = d.run.closes + ' closed, ' + d.run.rfis + ' asked, ' + d.run.escalations + ' escalated';
    });
  }

  // only what the export proves: identical runs, runs that differed, or nothing when it was not re-run
  function repeat(run) {
    if (run.repeat_identical === true) return '<span class="k-meta">Run ' + run.repeat_runs + ' times: the same in ' + run.repeat_runs + ' of ' + run.repeat_runs + '.</span>';
    if (run.repeat_identical === false) return '<span class="k-meta">Run ' + run.repeat_runs + ' times: the runs did not all match.</span>';
    return '';
  }
  function replay() { list.style.display = 'none'; void list.offsetWidth; list.style.display = ''; }

  function show(id, keepCursor) {
    inst = id; KF.setInst(id);
    return Promise.all([Promise.all(ORDER.map(KF.load)), KF.store.list()]).then(function (r) {
      var all = r[0]; standing = KF.standing(r[1]);
      data = all[ORDER.indexOf(id)];
      if (!keepCursor) cursor = 0;
      shown = pick(data, cursor);
      renderList(); renderApprove(); renderInsts(all);
      KF.ready(); replay();
      var u = new URL(location.href); u.searchParams.set('inst', id); history.replaceState(null, '', u);
    });
  }

  insts.forEach(function (el, i) {
    function go() { if (ORDER[i] !== inst) show(ORDER[i]).catch(function (e) { KF.fail(list, e); }); }
    el.addEventListener('click', go);
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });
  replayBtn.addEventListener('click', replay);
  nextBtn.addEventListener('click', function () {
    if (!shown.length) return;
    cursor = (shown[shown.length - 1].i + 1) % data.decisions.length;
    shown = pick(data, cursor); renderList(); renderApprove(); replay();
  });

  editBtn.addEventListener('click', function () {
    var d = $('.kf-draft', msg); if (!d) return;
    var on = d.getAttribute('contenteditable') === 'true';
    d.setAttribute('contenteditable', on ? 'false' : 'true');
    editBtn.textContent = on ? 'Edit' : 'Done';
    if (!on) { d.focus(); var r = document.createRange(); r.selectNodeContents(d); r.collapse(false); var s = getSelection(); s.removeAllRanges(); s.addRange(r); }
  });

  sendBtn.addEventListener('click', function () {
    var c = rfi, d = $('.kf-draft', msg); if (!c) return;
    var note = d ? d.textContent.trim() : '';
    sendBtn.disabled = true;
    KF.act(data.run, c, 'rfi_sent', note).then(function () {
      standing[c.case_id] = { action: 'rfi_sent' };
      var r = list.querySelector('[data-case="' + c.case_id + '"] .kq-id');
      if (r) r.insertAdjacentHTML('beforeend', '<span class="kq-done"> · RFI sent</span>');
      K.toast('RFI sent for ' + c.case_id + '. Saved in ' + KF.store.where + '.', {
        undo: function () {
          KF.act(data.run, c, 'undone').then(function () {
            delete standing[c.case_id];
            var done = list.querySelector('[data-case="' + c.case_id + '"] .kq-done'); if (done) done.remove();
            renderApprove();
          });
        }
      });
      renderApprove();
    }).catch(function (e) { K.toast('Not sent: ' + e.message, { mark: 'bad' }); }).then(function () { sendBtn.disabled = false; });
  });

  show(inst).catch(function (e) { KF.fail(list, e); });
  K.whenVisible(list, replay);
  setTimeout(function () { $$('header [data-k-bot][data-state="working"]').forEach(function (b) { if (b._kbot) b._kbot.set('done'); }); }, 13500);
})();
