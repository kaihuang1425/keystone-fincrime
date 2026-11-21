/* The MLRO's phone, on the system's real escalations: one at a time, oldest first. Take the case and
   Send back are saved; the toast shows the latest action on any page and Undo takes it back. The
   message box answers from the case's reason and records only. */
(function () {
  var KF = window.KF;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var frame = $('.ks-fit > div'), botsRow = frame.children[0], body = frame.children[1];
  var toastBox = frame.children[2], toast = $('.k-toast', toastBox), form = $('.k-ask', frame), input = form && $('input', form);
  var ticket = $('.k-ticket__msg', body), why = $('.kw-row', body), approve = $('.k-approve', body);
  var headB = $('#ph-ap', approve), headSmall = $('.k-grow small', approve), headChip = $('.k-chip', approve);
  var sendBack = $('.k-approve__actions .k-btn--text', approve), take = $('.k-approve__actions .k-btn--primary', approve);
  take.removeAttribute('data-k-approve');
  $$('.k-iconbtn, .k-voice', form).forEach(function (b) { b.remove(); });

  var inst = KF.inst(), data = null, rows = [], standing = {}, c = null;
  var cid = KF.param('case');
  if (cid && KF.instOf(cid)) inst = KF.instOf(cid);

  // Keystone's escalations no analyst has changed, and any case an analyst escalated
  function waiting() {
    return data.decisions.filter(function (x) {
      var st = standing[x.case_id];
      return st ? st.action === 'escalated' : x.verdict === 'ESCALATE';
    });
  }

  function botStates() {
    $$('[data-k-bot]', botsRow).forEach(function (b) {
      var name = b.getAttribute('data-name');
      if (!b._kbot) return;
      if (name === 'Case Lead') b._kbot.set(c ? 'waiting' : 'done');
      else b._kbot.set(c && KF.records(c, name).length ? 'done' : 'idle');
    });
  }

  function render() {
    var list = waiting();
    if (!c || list.indexOf(c) < 0) c = list[0] || null;
    var reply = $('.kf-reply', frame); if (reply) reply.remove();
    if (!c) {
      ticket.innerHTML = '<small>' + KF.esc(KF.instInfo(inst).name) + '</small>No escalations are waiting.';
      why.style.display = 'none'; approve.style.display = 'none';
      botStates(); return;
    }
    why.style.display = ''; approve.style.display = '';
    var n = list.indexOf(c) + 1, href = 'app.html?inst=' + inst + '&amp;case=' + encodeURIComponent(c.case_id);
    // the reason as numbered steps: the first two, each held to three lines, and the rest in the case view;
    // one step when two would run under the toast or off the frame
    var head = '<small>' + KF.esc(c.case_id) + ' · ' + KF.alerts(c) + ' · ' + (n || 1) + ' of ' + list.length + '</small>';
    var stepped = function (max) {
      ticket.innerHTML = head + KF.steps(c, { max: max, cls: 'kf-steps--compact', text: KF.amounts,
        more: function (k) { return '<a href="' + href + '">and ' + k + ' more</a>'; } });
    };
    stepped(2);
    var pick = c.evidence.slice(0, 3);
    why.children[1].innerHTML ='<b>' + c.evidence.length + ' records support it</b><small>' +
      pick.map(function (id) { return KF.cite(c, id); }).join(' ') + (c.evidence.length > 3 ? ' and ' + (c.evidence.length - 3) + ' more' : '') + '</small>';
    headB.textContent = KF.title(c.reason_code);
    headSmall.textContent = c.reason_code; headSmall.title = KF.describe(c.reason_code);
    if (!fits()) stepped(1);
    botStates();
    var u = new URL(location.href); u.searchParams.set('inst', inst); u.searchParams.set('case', c.case_id); history.replaceState(null, '', u);
  }

  // the column's last line ends above the toast and inside the frame
  function fits() {
    var last = body.lastElementChild, limit = body.getBoundingClientRect().bottom;
    if (!last) return true;
    if (toastBox.style.display !== 'none') limit = Math.min(limit, toast.getBoundingClientRect().top - 6);
    return last.getBoundingClientRect().bottom <= limit;
  }

  // the in-frame toast: the latest action on any page, with Undo
  function showLatest() {
    return KF.store.list().then(function (all) {
      standing = KF.standing(all);
      var last = null;
      Object.keys(standing).forEach(function (k) { var a = standing[k]; if (!last || a.created_at > last.created_at) last = a; });
      if (!last) { toastBox.style.display = 'none'; return; }
      toastBox.style.display = '';
      toast.innerHTML = '<span class="k-mk k-mk--ok">✓</span><span></span><button type="button">Undo</button>';
      toast.children[1].textContent = KF.DID[last.action] + ': ' + last.case_id + '. Saved in ' + KF.store.where + '.';
      toast.lastChild.addEventListener('click', function () {
        var inst2 = KF.instOf(last.case_id) || inst;
        KF.load(inst2).then(function (d) {
          var x = d.byId[last.case_id]; if (!x) return;
          return KF.act(d.run, x, 'undone').then(function () {
            return showLatest().then(function () { if (inst2 === inst && x.verdict === 'ESCALATE') c = x; render(); });
          });
        });
      });
    });
  }

  function decide(action) {
    if (!c) return;
    var x = c;
    take.disabled = sendBack.disabled = true;
    KF.act(data.run, x, action).then(function () { return showLatest(); }).then(function () { c = null; render(); })
      .catch(function (e) { toast.children[1].textContent = 'Not saved: ' + e.message; })
      .then(function () { take.disabled = sendBack.disabled = false; });
  }
  take.addEventListener('click', function () { decide('escalation_taken'); });
  sendBack.addEventListener('click', function () { decide('sent_back'); });

  if (form) form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = input.value.trim(); if (!q || !c) return;
    input.value = '';
    var old = $('.kf-reply', frame); if (old) old.remove();
    form.insertAdjacentHTML('beforebegin', '<p class="kf-reply"><b>Case Lead:</b> ' + KF.withCites(c, KF.clip(KF.answer(c, q), 260)) + '</p>');
  });

  Promise.all([KF.load(inst), showLatest()]).then(function (r) {
    data = r[0];
    if (cid && data.byId[cid] && waiting().indexOf(data.byId[cid]) > -1) c = data.byId[cid];
    render(); KF.ready();
  }).catch(function (e) { KF.fail(ticket, e); });
})();
