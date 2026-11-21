/* Keystone · Financial Crime: the pages' data.

   Verdicts come from data/<institution>.json, written by tools/export_ui.py from output/. They hold
   the system's own words only: verdict, reason code, reason, alert ids and evidence ids. No record
   text from the kit is on the site, so a citation shows its id and the sentence of the reason that
   cites it.

   What the analyst does (close, send an RFI, escalate, take or send back an escalation, undo) goes to Supabase's
   analyst_actions table when assets/kf-config.js names a project, and to this browser's storage until
   then. Undo adds an 'undone' row; nothing is ever edited or deleted. */
(function () {
  var KF = window.KF = {};

  KF.INST = [
    { id: 'bank', name: 'Bank', long: 'Bank' },
    { id: 'payments_fx', name: 'Payments and FX', long: 'Payments and FX firm' },
    { id: 'emoney', name: 'E-money', long: 'E-money firm' },
    { id: 'investment', name: 'Investment', long: 'Investment firm' }
  ];
  function inst(id) { for (var i = 0; i < KF.INST.length; i++) if (KF.INST[i].id === id) return KF.INST[i]; return null; }
  KF.instInfo = inst;
  var params = new URLSearchParams(location.search);
  KF.param = function (k) { return params.get(k); };
  KF.inst = function () {
    var p = params.get('inst');
    if (inst(p)) return p;
    try { var s = localStorage.getItem('kf-inst'); if (inst(s)) return s; } catch (e) {}
    return 'bank';
  };
  KF.setInst = function (id) { try { localStorage.setItem('kf-inst', id); } catch (e) {} };
  KF.instOf = function (caseId) {
    var p = { BK: 'bank', EM: 'emoney', IV: 'investment', PX: 'payments_fx' }[String(caseId).slice(0, 2)];
    return p || null;
  };

  /* ---------- verdicts ---------- */
  var cache = {};
  KF.load = function (id) {
    if (!cache[id]) {
      cache[id] = fetch('data/' + id + '.json').then(function (r) {
        if (!r.ok) throw new Error('data/' + id + '.json answered ' + r.status);
        return r.json();
      }).then(function (d) {
        d.byId = {};
        d.decisions.forEach(function (c, i) { c.i = i; d.byId[c.case_id] = c; });
        return d;
      });
    }
    return cache[id];
  };

  /* ---------- words ---------- */
  KF.esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]; });
  };
  KF.V = {
    CLOSE: { cls: 'ok', mk: '✓', word: 'CLOSE', did: 'close', q: 'Why did %s close?' },
    RFI: { cls: 'ask', mk: '?', word: 'RFI', did: 'need a document', q: 'Why does %s need a document?' },
    ESCALATE: { cls: 'bad', mk: '↑', word: 'ESCALATE', did: 'go to the MLRO', q: 'Why was %s escalated?' }
  };
  KF.chip = function (v) { var x = KF.V[v]; return '<span class="k-chip k-chip--' + x.cls + '">' + x.mk + ' ' + x.word + '</span>'; };
  KF.mark = function (v) { var x = KF.V[v]; return '<span class="k-mk k-mk--' + x.cls + '">' + x.mk + '</span>'; };
  KF.title = function (code) {
    var t = code.replace(/^(RFI|ESC)_/, '').toLowerCase().replace(/_/g, ' ');
    return t.charAt(0).toUpperCase() + t.slice(1);
  };
  KF.sentences = function (text) {
    return String(text).split(/(?<=[.!?]["”’]?)\s+(?=[A-Z£"“‘])/).filter(Boolean);
  };
  KF.clip = function (s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1).replace(/[\s,;:]+\S*$/, '') + '…' : s; };
  KF.alerts = function (c) { return c.alert_ids.length + (c.alert_ids.length === 1 ? ' alert' : ' alerts'); };

  /* ---------- records: kind and owner, read from the id alone ---------- */
  var DOCS = { EML: 'Email', CHT: 'Chat with the customer', INV: 'Invoice', RPT: 'Report from another bank', STM: 'Statement', KYC: 'KYC record', REG: 'Register extract', RCT: 'Receipt', LET: 'Letter', LTR: 'Letter' };
  KF.kind = function (id) {
    if (/^[A-Z]{2}-AL\d/.test(id)) return 'Alert';
    if (/^[A-Z]{2}-T\d/.test(id)) return 'Transaction';
    if (/^[A-Z]{2}-L\d/.test(id)) return 'List entry';
    if (/^[A-Z]{2}-R\d/.test(id)) return 'Earlier review';
    return DOCS[id.split('-')[0]] || 'Document';
  };
  KF.owner = function (id) {
    var k = KF.kind(id);
    if (k === 'Alert' || k === 'Transaction' || k === 'Earlier review') return 'Payments Bot';
    if (k === 'List entry' || k === 'KYC record' || k === 'Register extract') return 'Match Bot';
    if (k === 'Report from another bank') return 'Screening Bot';
    return 'Document Bot';
  };
  KF.BOTS = {
    'Case Lead': { shape: 'shield', color: 'chief', does: 'decides the case from what the others found' },
    'Payments Bot': { shape: 'card', color: 'pink', does: 'reads the alerts, transactions and earlier reviews' },
    'Document Bot': { shape: 'doc', color: 'blue', does: 'reads the documents on file' },
    'Screening Bot': { shape: 'lens', color: 'green', does: 'reads reports of crime from other banks' },
    'Match Bot': { shape: 'venn', color: 'teal', does: 'compares parties with list entries, KYC and registers' }
  };
  KF.botHTML = function (name, state) {
    var b = KF.BOTS[name];
    return '<span data-k-bot data-shape="' + b.shape + '" data-color="' + b.color + '" data-state="' + (state || 'done') + '" data-name="' + name + '"></span>';
  };
  KF.records = function (c, bot) {
    var ids = c.alert_ids.concat(c.evidence);
    return bot ? ids.filter(function (id) { return KF.owner(id) === bot; }) : ids;
  };
  KF.lead = function (c) {
    if (c.verdict === 'ESCALATE' && c.evidence.some(function (id) { return KF.owner(id) === 'Screening Bot'; })) return 'Screening Bot';
    if (/LIST|LISTED/.test(c.reason_code) || c.evidence.some(function (id) { return KF.kind(id) === 'List entry'; })) return 'Match Bot';
    if (c.evidence.some(function (id) { return KF.owner(id) === 'Document Bot'; })) return 'Document Bot';
    return 'Payments Bot';
  };
  KF.mountBots = function (root) {
    var K = window.Keystone;
    if (K && K.bot) Array.prototype.forEach.call(root.querySelectorAll('[data-k-bot]'), function (n) { K.bot(n); });
  };

  /* ---------- citations: the id and the sentence of the reason that cites it ---------- */
  KF.citing = function (c, id) { return KF.sentences(c.reason).filter(function (s) { return s.indexOf(id) > -1; }); };
  KF.cite = function (c, id) {
    var s = KF.citing(c, id);
    var pop = s.length ? s.join(' ') : (KF.kind(id) === 'Alert' ? 'One of the alerts on this case.' : 'Listed in the evidence for this decision. The reason does not quote it.');
    return '<button type="button" class="k-cite">' + KF.esc(id) + '<span class="k-cite__pop">' + KF.esc(pop) +
      '<small>' + KF.esc(KF.kind(id)) + ' · ' + KF.esc(c.case_id) + '</small></span></button>';
  };
  KF.withCites = function (c, text) {
    var ids = KF.records(c).slice().sort(function (a, b) { return b.length - a.length; });
    var html = KF.esc(text);
    if (!ids.length) return html;
    var re = new RegExp('\\b(' + ids.map(function (i) { return i.replace(/[-]/g, '\\-'); }).join('|') + ')\\b', 'g');
    return html.replace(re, function (id) { return KF.cite(c, id); });
  };
  KF.amounts = function (text) { return KF.esc(text).replace(/£[\d,]+(?:\.\d\d)?/g, '<span class="kw-hl">$&</span>'); };

  /* ---------- Case Lead answers from the case's own reason and records, nothing else ---------- */
  var STOP = 'what which when where with that this have from does were will would about your there their them they case cases please could should tell show give'.split(' ');
  KF.answer = function (c, q) {
    var ql = q.toLowerCase(), s = KF.sentences(c.reason), all = KF.records(c);
    var named = all.filter(function (id) { return ql.indexOf(id.toLowerCase()) > -1; });
    if (named.length) {
      var hit = s.filter(function (x) { return named.some(function (id) { return x.indexOf(id) > -1; }); });
      return hit.length ? hit.join(' ') : named.map(function (id) { return id + ' is ' + (KF.kind(id) === 'Alert' ? 'one of the alerts on this case.' : 'in the evidence, as ' + KF.kind(id).toLowerCase() + ', but the reason does not quote it.'); }).join(' ');
    }
    if (/\balerts?\b/.test(ql)) return 'This case has ' + KF.alerts(c) + ': ' + c.alert_ids.join(', ') + '.';
    if (/\b(records?|evidence|documents?|proof|sources?)\b/.test(ql)) {
      return 'The decision rests on ' + c.evidence.length + ' records: ' + c.evidence.map(function (id) { return id + ' (' + KF.kind(id).toLowerCase() + ')'; }).join(', ') + '.';
    }
    if (/\b(verdict|decision|outcome|result|code)\b/.test(ql)) return c.verdict + ', ' + c.reason_code + '. ' + s[0];
    if (/\b(why|reason|because|explain)\b/.test(ql)) return c.reason;
    var words = (ql.match(/[a-z0-9£][a-z0-9£,.']{3,}/g) || []).filter(function (w) { return STOP.indexOf(w) < 0; });
    var best = 0, picks = [];
    s.forEach(function (x) {
      var xl = x.toLowerCase(), n = words.filter(function (w) { return xl.indexOf(w.replace(/[,.]+$/, '')) > -1; }).length;
      if (n > best) { best = n; picks = [x]; } else if (n && n === best) picks.push(x);
    });
    if (best) return picks.join(' ');
    return 'I can only answer from this case’s reason and records. Ask why, about the alerts, or about a record such as ' + (c.evidence[0] || c.alert_ids[0]) + '.';
  };

  /* ---------- the analyst's actions ---------- */
  var KEY = 'kf-actions-v1', mem = [];
  var local = {
    where: 'this browser',
    list: function () {
      try { return Promise.resolve(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return Promise.resolve(mem.slice()); }
    },
    add: function (a) {
      return local.list().then(function (all) {
        a.created_at = new Date().toISOString();
        all.push(a);
        try { localStorage.setItem(KEY, JSON.stringify(all)); } catch (e) { mem = all; }
        return a;
      });
    }
  };
  var cfg = window.KF_SUPABASE, remote = null;
  if (cfg && cfg.url && cfg.anonKey) {
    var head = { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey };
    var ok = function (r) { if (!r.ok) throw new Error('Supabase answered ' + r.status); return r.json(); };
    remote = {
      where: 'Supabase',
      list: function () {
        return fetch(cfg.url + '/rest/v1/analyst_actions?select=run_id,case_id,action,note,created_at&order=id.asc', { headers: head }).then(ok);
      },
      add: function (a) {
        return fetch(cfg.url + '/rest/v1/analyst_actions', {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json', Prefer: 'return=representation' }, head),
          body: JSON.stringify(a)
        }).then(ok).then(function (rows) { return rows[0] || a; });
      }
    };
  }
  // Supabase when it answers; this browser's storage when it does not, so the pages always work.
  // Rows that fell back to this browser are read alongside Supabase's, in time order, so an action
  // Supabase refused still shows.
  KF.store = {
    where: remote ? 'Supabase' : 'this browser',
    list: function () {
      if (!remote) return local.list();
      return Promise.all([
        remote.list().catch(function (e) { console.warn('Keystone: ' + e.message + '; using this browser instead.'); KF.store.where = 'this browser'; return []; }),
        local.list()
      ]).then(function (r) {
        return r[1].length ? r[0].concat(r[1]).sort(function (a, b) { return Date.parse(a.created_at) - Date.parse(b.created_at); }) : r[0];
      });
    },
    add: function (a) {
      if (!remote) return local.add(a);
      return remote.add(a).catch(function (e) { console.warn('Keystone: ' + e.message + '; saved in this browser instead.'); KF.store.where = 'this browser'; return local.add(a); });
    }
  };
  KF.act = function (run, c, action, note) {
    return KF.store.add({ run_id: run.run_id, case_id: c.case_id, action: action, note: note || null });
  };
  // each case's standing action, after undos: 'undone' cancels the latest action still standing
  KF.standing = function (rows) {
    var by = {};
    rows.forEach(function (a) {
      var st = by[a.case_id] || (by[a.case_id] = []);
      if (a.action === 'undone') st.pop(); else st.push(a);
    });
    var out = {};
    Object.keys(by).forEach(function (k) { if (by[k].length) out[k] = by[k][by[k].length - 1]; });
    return out;
  };
  KF.DID = { closed: 'Closed', rfi_sent: 'RFI sent', escalated: 'Escalated to the MLRO', escalation_taken: 'Taken by the MLRO', sent_back: 'Sent back' };

  KF.fail = function (where, e) {
    console.error(e);
    document.documentElement.classList.remove('kf-wait');
    if (where) where.innerHTML = '<p class="k-meta">The verdicts could not be loaded (' + KF.esc(e.message) + ').</p>';
  };
  KF.ready = function () { document.documentElement.classList.remove('kf-wait'); };
})();
