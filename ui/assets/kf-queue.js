/* The alert queue, on the system's real verdicts. Twenty cases at a time, in the order the system
   wrote them, or twenty of one verdict when a filter is on. Each row says what was decided once: a
   plain title, the case ID and alert count, the first sentence of the reason and one chip; the reason
   code sits in the chip's tooltip and in the case view. Each row opens the case. The institutions are
   tabs with their case count and how many people have decided; the heading counts what is left. The RFI card sends the system's request, editable first, and Undo takes
   it back. The rows play their reading animation on the first visit in a tab, and stay still after. */
(function () {
  var K = window.Keystone, KF = window.KF;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var list = $('.kq-list'), card = $('[data-kq]'), approve = $('.k-approve'), h1 = $('h1'), h1turn = $('h1 .k-turn');
  var headTitle = $('h2', card.firstElementChild), replayBtn = $('[data-kq-replay]');
  var insts = $$('.aq-inst'), ORDER = ['bank', 'payments_fx', 'emoney', 'investment'];
  var msg = $('.k-ticket__msg', approve), codeRow = $$('.k-row', approve)[1], btnRow = $$('.k-row', approve)[2];
  var editBtn = $('.k-btn--text', btnRow), sendBtn = $('.k-btn--primary', btnRow);
  sendBtn.removeAttribute('data-k-approve');

  var PAGE = 20;
  var inst = KF.inst(), all = null, data = null, standing = {}, cursor = 0, shown = [], rfi = null, filter = 'ALL';

  // the reading animation plays once per visit: after the first queue in this tab, rows arrive still
  var seen = false;
  try { seen = sessionStorage.getItem('kf-queue-seen') === '1'; sessionStorage.setItem('kf-queue-seen', '1'); } catch (e) {}
  function still() { list.classList.add('kf-still'); }
  if (seen) still();

  // the bots in the header say who they are
  $$('header [data-k-bot]').forEach(function (b) {
    var name = b.getAttribute('data-name'), x = KF.BOTS[name];
    if (x) { b.title = name + ' ' + x.does; b.setAttribute('aria-label', name); }
  });

  // filters by verdict, then Next six, where Replay was
  var bar = replayBtn.parentNode;
  var seg = document.createElement('div');
  seg.className = 'k-seg kf-filter'; seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Show');
  seg.innerHTML = [['ALL', 'All'], ['CLOSE', '✓ Close'], ['RFI', '? RFI'], ['ESCALATE', '↑ Escalate']].map(function (f) {
    return '<button type="button" data-f="' + f[0] + '" aria-pressed="' + (f[0] === filter) + '">' + f[1] + '</button>';
  }).join('');
  var nextBtn = document.createElement('button');
  nextBtn.type = 'button'; nextBtn.className = 'k-btn k-btn--sm'; nextBtn.textContent = 'Next ' + PAGE;
  bar.replaceChild(seg, replayBtn); bar.appendChild(nextBtn);
  bar.style.gap = '8px';

  function pick(d, from) {
    var out = [], n = d.decisions.length;
    for (var k = 0; k < n && out.length < PAGE; k++) {
      var c = d.decisions[(from + k) % n];
      if (standing[c.case_id] || (filter !== 'ALL' && c.verdict !== filter)) continue;
      out.push(c);
    }
    return out.sort(function (a, b) { return a.i - b.i; });
  }
  function nextRfi(d, from) {
    var n = d.decisions.length;
    for (var k = 0; k < n; k++) { var c = d.decisions[(from + k) % n]; if (c.verdict === 'RFI' && !standing[c.case_id]) return c; }
    return null;
  }
  function tally(cases) {
    var t = { CLOSE: 0, RFI: 0, ESCALATE: 0 }; cases.forEach(function (c) { t[c.verdict]++; }); return t;
  }
  function decided(id) {
    return Object.keys(standing).filter(function (k) { return KF.instOf(k) === id; }).length;
  }
  function href(c) { return 'app.html?inst=' + inst + '&case=' + encodeURIComponent(c.case_id); }
  function n(x) { return Number(x).toLocaleString('en-GB'); }

  function row(c) {
    var st = standing[c.case_id];
    return '<a class="kq-row kw-r" href="' + href(c) + '" data-case="' + KF.esc(c.case_id) + '">' +
      // the reason in words leads; the system's sentence follows in a quieter tone; the case facts
      // sit underneath as small tags, so each kind of detail looks different
      '<span class="kq-main"><b>' + KF.esc(KF.title(c.reason_code)) + '</b>' +
      '<span class="kq-line"><span class="q">Queued</span><span class="a">Reading ' + c.evidence.length + ' records</span>' +
      '<span class="b">' + KF.esc(KF.sentences(c.reason)[0]) + '</span></span>' +
      '<span class="kq-meta"><span class="kq-tag kq-tag--id">' + KF.esc(c.case_id) + '</span><span class="kq-tag">' + KF.alerts(c) + '</span>' +
      (st ? '<span class="kq-tag kq-tag--done kq-done">' + KF.DID[st.action] + '</span>' : '') + '</span></span>' +
      '<span class="kq-end" title="' + KF.esc(c.reason_code + ': ' + KF.describe(c.reason_code)) + '">' + KF.chip(c.verdict) + '</span></a>';
  }

  function renderList() {
    var run = data.run;
    list.innerHTML = shown.length
      ? shown.map(row).join('') + '<div class="kq-tally kw-r">' + repeat(run) + '</div>'
      : '<p class="k-meta kf-empty">Every case here has been decided.</p>';
    headTitle.textContent = KF.instInfo(inst).name + ' · queue';
  }

  function renderApprove() {
    rfi = nextRfi(data, cursor);
    if (!rfi) {
      msg.innerHTML = '<small>' + KF.esc(KF.instInfo(inst).name) + '</small>Every RFI in this queue has been sent.';
      codeRow.style.display = 'none'; btnRow.style.display = 'none';
      return;
    }
    var s = KF.sentences(rfi.reason), ask = s.filter(function (x) { return /^Ask\b/.test(x); });
    msg.innerHTML = '<small>What to ask · <a href="' + href(rfi) + '">' + KF.esc(rfi.case_id) + '</a></small><span class="kf-draft">' + KF.esc((ask.length ? ask : s.slice(-1)).join(' ')) + '</span>';
    codeRow.innerHTML = KF.chip('RFI') + '<span class="kq-id" title="' + KF.esc(KF.describe(rfi.reason_code)) + '">' + KF.esc(rfi.reason_code) + '</span>';
    codeRow.style.display = ''; btnRow.style.display = '';
    editBtn.textContent = 'Edit';
  }

  // each institution is a tab: its name, its case count and how many people have decided
  function renderInsts() {
    insts.forEach(function (el, i) {
      var id = ORDER[i], r = all[i].run, done = decided(id);
      el.setAttribute('role', 'button'); el.tabIndex = 0;
      el.setAttribute('aria-current', id === inst ? 'true' : 'false');
      el.setAttribute('title', n(r.closes) + ' closed, ' + n(r.rfis) + ' asked, ' + n(r.escalations) + ' escalated');
      el.innerHTML = '<b>' + KF.esc(KF.instInfo(id).name) + '</b><small>' + n(r.cases) + ' cases' + (done ? ' · ' + n(done) + ' decided' : '') + '</small>';
    });
    var left = data.run.cases - decided(inst);
    if (h1) h1.textContent = left ? n(left) + ' cases to review.' : 'Every case reviewed.';
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
      all = r[0]; standing = KF.standing(r[1]);
      data = all[ORDER.indexOf(id)];
      if (!keepCursor) cursor = 0;
      shown = pick(data, cursor);
      renderList(); renderApprove(); renderInsts();
      KF.ready(); replay();
      var u = new URL(location.href); u.searchParams.set('inst', id); history.replaceState(null, '', u);
    });
  }

  insts.forEach(function (el, i) {
    function go() { if (ORDER[i] !== inst) { still(); show(ORDER[i]).catch(function (e) { KF.fail(list, e); }); } }
    el.addEventListener('click', go);
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });
  seg.addEventListener('click', function (e) {
    var b = e.target.closest('[data-f]'); if (!b || !data) return;
    filter = b.getAttribute('data-f');
    $$('[data-f]', seg).forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
    still(); cursor = 0; shown = pick(data, cursor); renderList();
  });
  nextBtn.addEventListener('click', function () {
    if (!shown.length) return;
    cursor = (shown[shown.length - 1].i + 1) % data.decisions.length;
    still(); shown = pick(data, cursor); renderList(); renderApprove();
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
      var r = list.querySelector('[data-case="' + c.case_id + '"] .kq-meta');
      if (r) r.insertAdjacentHTML('beforeend', '<span class="kq-tag kq-tag--done kq-done">RFI sent</span>');
      K.toast('RFI sent for ' + c.case_id + '. Saved in ' + KF.store.where + '.', {
        undo: function () {
          KF.act(data.run, c, 'undone').then(function () {
            delete standing[c.case_id];
            var done = list.querySelector('[data-case="' + c.case_id + '"] .kq-done'); if (done) done.remove();
            renderApprove(); renderInsts();
          });
        }
      });
      renderApprove(); renderInsts();
    }).catch(function (e) { K.toast('Not sent: ' + e.message, { mark: 'bad' }); }).then(function () { sendBtn.disabled = false; });
  });

  show(inst).catch(function (e) { KF.fail(list, e); });
  K.whenVisible(list, function () { if (!list.classList.contains('kf-still')) replay(); });
  setTimeout(function () { $$('header [data-k-bot][data-state="working"]').forEach(function (b) { if (b._kbot) b._kbot.set('done'); }); }, seen ? 400 : 13500);
})();
