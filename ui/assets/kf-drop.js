/* Keystone · Financial Crime: the drop page.

   The visitor drops a zip, a tar or a folder. assets/kf-drop-worker.js runs the scored system on it in
   this tab (Python through Pyodide), so the files are not uploaded. Every string that comes from the
   drop (names, IDs, reasons, notes) is escaped before it reaches the page. A score appears only when
   the drop holds right answers, and it says what it was measured on. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return KF.esc(s == null ? '' : s); };
  var fmt = function (n) { return Number(n).toLocaleString('en-GB'); };
  var pl = function (n, one, many) { return fmt(n) + ' ' + (n === 1 ? one : (many || one + 's')); };
  var VS = ['CLOSE', 'RFI', 'ESCALATE'];
  var MAX_BYTES = 1500 * 1024 * 1024;

  var worker = null, ready = false, busy = false, queued = null, engine = null, python = '';
  var found = null, results = [], score = null, again = [];
  var view = { inst: 0, v: 'ALL', shown: 50 };
  var lead = null;

  /* ---------- the Case Lead says what the screen can't show yet ---------- */
  function say(text, state) {
    var el = $('kd-say');
    if (window.Keystone && Keystone.flip) Keystone.flip(el, text); else el.textContent = text;
    if (lead && state) lead.set(state);
  }
  function fail(text) {
    var el = $('kd-err');
    el.textContent = text;
    el.hidden = false;
    busy = false;
    $('kd-drop').classList.remove('is-busy');
    say('Stopped', 'blocked');
  }
  function clearError() { $('kd-err').hidden = true; $('kd-err').textContent = ''; }

  /* ---------- the engine ---------- */
  function start() {
    try {
      worker = new Worker('assets/kf-drop-worker.js');
    } catch (e) {
      fail('This browser cannot start the engine: ' + (e && e.message || e) + '.');
      return;
    }
    worker.onerror = function (e) {
      if (e && e.preventDefault) e.preventDefault();
      fail('The engine did not load' + (e && e.message ? ' (' + e.message + ')' : '') +
        '. Python comes from cdn.jsdelivr.net, so check the connection and reload the page.');
    };
    worker.onmessage = function (e) { on(e.data); };
    worker.postMessage({ type: 'boot' });
  }

  function on(m) {
    if (m.type === 'status') {
      say(m.step === 'python' ? 'Loading Python, once' : 'Checking the engine files', 'working');
    } else if (m.type === 'ready') {
      ready = true; engine = m.engine; python = m.python;
      $('kd-engine').title = 'Python ' + python + ' · engine ' + engine;  // kept for debugging, not shown
      if (queued) { var q = queued; queued = null; send(q); } else say('Ready for your cases', 'idle');
    } else if (m.type === 'found') {
      showFound(m.found);
    } else if (m.type === 'start') {
      var inst = found.institutions[m.index];
      say('Deciding ' + inst.name + ', ' + pl(inst.cases, 'case'), 'working');
    } else if (m.type === 'progress') {
      var bar = document.querySelector('[data-bar="' + m.index + '"]');
      if (bar) bar.style.setProperty('--p', Math.min(100, 100 * m.done / Math.max(1, found.institutions[m.index].cases)) + '%');
    } else if (m.type === 'result') {
      results[m.result.index] = m.result;
      fillRow(m.result);
    } else if (m.type === 'score') {
      score = m.score;
      finish();
    } else if (m.type === 'again-start') {
      say('Running ' + found.institutions[m.index].name + ' again', 'working');
    } else if (m.type === 'again') {
      again[m.result.index] = m.result;
    } else if (m.type === 'again-done') {
      var same = again.filter(function (a) { return a && a.same; }).length;
      $('kd-again-out').textContent = 'Second run: the same bytes at ' + same + ' of ' + again.length + ' institution' + (again.length === 1 ? '' : 's') + '.';
      busy = false; $('kd-drop').classList.remove('is-busy');
      say(same === again.length ? 'Both runs agree' : 'The runs differ', same === again.length ? 'done' : 'blocked');
    } else if (m.type === 'zip') {
      var blob = new Blob([m.bytes], { type: 'application/zip' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'keystone-answers.zip';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    } else if (m.type === 'error') {
      fail(m.where === 'boot' ? 'The engine did not load: ' + m.text : 'The run stopped: ' + m.text);
    } else if (m.type === 'log' && window.console) {
      console.debug('[engine]', m.text);
    }
  }

  /* ---------- one intake for drag and drop, the zip picker and the folder picker ---------- */
  function readEntry(entry, prefix) {
    if (entry.isFile) {
      return new Promise(function (res, rej) { entry.file(function (f) { res([{ path: prefix + entry.name, file: f }]); }, rej); });
    }
    if (!entry.isDirectory) return Promise.resolve([]);
    var reader = entry.createReader(), kids = [];
    return new Promise(function (res, rej) {
      (function more() {
        reader.readEntries(function (batch) {
          if (batch.length) { kids = kids.concat(Array.prototype.slice.call(batch)); more(); return; }
          Promise.all(kids.map(function (k) { return readEntry(k, prefix + entry.name + '/'); }))
            .then(function (lists) { res([].concat.apply([], lists)); }, rej);
        }, rej);
      })();
    });
  }
  function fromList(list) {
    return Array.prototype.map.call(list, function (f) { return { path: f.webkitRelativePath || f.name, file: f }; });
  }
  function take(items) {
    if (busy) return;
    items = items.filter(function (x) { return x && x.file; });
    if (!items.length) { fail('Nothing to read in that drop.'); return; }
    var bytes = items.reduce(function (n, x) { return n + x.file.size; }, 0);
    if (bytes > MAX_BYTES) { fail('That drop is ' + fmt(Math.round(bytes / 1048576)) + ' MB. This page reads up to 1,500 MB; use tools/run_drop.py for more.'); return; }
    clearError(); reset(); busy = true;
    $('kd-drop').classList.add('is-busy');
    say('Reading ' + fmt(items.length) + ' file' + (items.length === 1 ? '' : 's'), 'working');
    Promise.all(items.map(function (x) {
      return x.file.arrayBuffer().then(function (buf) { return { path: x.path, buf: buf }; });
    })).then(function (files) {
      if (ready) send(files); else { queued = files; say('Loading Python, once. Your files are waiting', 'working'); }
    }, function (e) { fail('Could not read the files: ' + (e && e.message || e) + '.'); });
  }
  function send(files) {
    say('Looking for institution folders', 'working');
    worker.postMessage({ type: 'drop', files: files }, files.map(function (f) { return f.buf; }));
  }
  function reset() {
    found = null; results = []; score = null; again = [];
    view = { inst: 0, v: 'ALL', shown: 50 };
    ['kd-found', 'kd-score', 'kd-cases', 'kd-done'].forEach(function (id) { $(id).hidden = true; });
    $('kd-score').innerHTML = ''; $('kd-insts').innerHTML = ''; $('kd-rows').innerHTML = '';
    $('kd-files').hidden = true; $('kd-files').innerHTML = ''; $('kd-again-out').textContent = '';
    $('kd-pick-zip').classList.add('k-btn--primary');
  }

  /* ---------- what was found, and the run ---------- */
  function showFound(f) {
    found = f;
    var n = f.institutions.length;
    $('kd-found').hidden = false;
    var note = [];
    if (!n) {
      $('kd-found-h').innerHTML = 'No institution folder. <span class="k-turn">Nothing holds cases.jsonl.</span>';
      var list = $('kd-files');
      list.innerHTML = f.sample_files.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') +
        (f.files_seen > f.sample_files.length ? '<li>… and ' + fmt(f.files_seen - f.sample_files.length) + ' more</li>' : '');
      list.hidden = !f.sample_files.length;
      note.push(f.files_seen ? 'These are the files found. Each institution needs its own folder holding cases.jsonl.' : 'The drop held no files.');
      f.notes.forEach(function (x) { note.push(x); });
      $('kd-found-note').textContent = note.join(' ');
      busy = false; $('kd-drop').classList.remove('is-busy');
      say('No cases to decide', 'blocked');
      return;
    }
    var total = f.institutions.reduce(function (s, x) { return s + x.cases; }, 0);
    $('kd-found-h').innerHTML = pl(total, 'case') + ' in ' + pl(n, 'institution') + '.' +
      (f.labels ? ' <span class="k-turn">' + pl(f.labels, 'right answer') + ' to score ' + (total === 1 ? 'it' : 'them') + ' on.</span>' : '');
    $('kd-insts').innerHTML = f.institutions.map(function (x, i) {
      return '<tr data-row="' + i + '"><td><b>' + esc(x.name) + '</b><span class="kd-sub">' + esc(x.shown) + '</span></td>' +
        '<td class="kd-num">' + fmt(x.cases) + '</td>' +
        '<td data-cell="split"><div class="kd-bar" role="progressbar" aria-label="Deciding ' + esc(x.name) + '" data-bar="' + i + '"><i></i></div></td>' +
        '<td data-cell="checks"><span class="k-meta">Queued</span></td>' +
        '<td class="kd-num kd-mobile-hide" data-cell="time"></td><td class="kd-mobile-hide" data-cell="sha"></td></tr>';
    }).join('');
    if (f.label_files.length) note.push('Right answers read from ' + f.label_files.join(', ') + '.');
    f.institutions.forEach(function (x) {
      if (x.missing.length) note.push(x.name + ' has no ' + x.missing.join(', ') + ', so those are read as empty.');
    });
    f.notes.forEach(function (x) { if (!/label\(s\) read from/.test(x)) note.push(x); });
    $('kd-found-note').textContent = note.join(' ');
    worker.postMessage({ type: 'run', found: JSON.stringify(f) });
  }

  function split(v) {
    var c = function (k) { return v[k] || 0; };
    return '<div class="kd-split"><div class="k-occ" role="img" aria-label="' + c('CLOSE') + ' closed, ' + c('RFI') + ' asked, ' + c('ESCALATE') + ' escalated">' +
      (c('CLOSE') ? '<i style="flex:' + c('CLOSE') + '"></i>' : '') + (c('RFI') ? '<i class="is-ask" style="flex:' + c('RFI') + '"></i>' : '') +
      (c('ESCALATE') ? '<i class="is-bad" style="flex:' + c('ESCALATE') + '"></i>' : '') + '</div>' +
      '<small><span>✓ ' + fmt(c('CLOSE')) + '</span><span>? ' + fmt(c('RFI')) + '</span><span>↑ ' + fmt(c('ESCALATE')) + '</span></small></div>';
  }

  function fillRow(r) {
    var row = document.querySelector('[data-row="' + r.index + '"]');
    if (!row) return;
    row.querySelector('[data-cell="split"]').innerHTML = split(r.verdicts);
    row.querySelector('[data-cell="checks"]').innerHTML = r.exit_code !== 0 ? '<span class="kd-bad">✕ run failed</span>' :
      r.problem_count ? '<span class="kd-bad" title="' + esc(r.problems.join('\n')) + '">✕ ' + fmt(r.problem_count) + ' problem' + (r.problem_count === 1 ? '' : 's') + '</span>' :
      '<span class="kd-ok">✓ One line a case</span><span class="kd-sub">codes fit, IDs exist</span>';
    row.querySelector('[data-cell="time"]').textContent = r.seconds.toFixed(1) + ' s';
    row.querySelector('[data-cell="sha"]').innerHTML = '<span class="kd-mono" title="sha256 ' + esc(r.sha256) + '">' + esc(r.sha256.slice(0, 12)) + '</span>';
  }

  function finish() {
    busy = false;
    $('kd-drop').classList.remove('is-busy');
    var total = results.reduce(function (s, r) { return s + (r ? r.cases : 0); }, 0);
    say('Decided ' + pl(total, 'case'), 'done');
    renderScore();
    renderCases();
    $('kd-done').hidden = false;
    $('kd-pick-zip').classList.remove('k-btn--primary');
  }

  /* ---------- the score: only with right answers, and saying what it was measured on ---------- */
  function pct(a, b) { return b ? (100 * a / b).toFixed(1) + '%' : 'n/a'; }
  function renderScore() {
    var el = $('kd-score');
    if (!score) {
      el.innerHTML = '';
      el.hidden = true;
      return;
    }
    var t = score.total, files = found.label_files.join(', ') || 'the dropped answers';
    var how = 'Measured on ' + fmt(t.labelled) + ' dropped case' + (t.labelled === 1 ? '' : 's') + ' with answers from ' + files;
    var head = (t.wrongful_closes ? fmt(t.wrongful_closes) + ' wrongful close' + (t.wrongful_closes === 1 ? '' : 's') + '.' : 'No wrongful closes.') +
      ' <span class="k-turn">' + (t.closable ? fmt(t.closable_closed) + ' of ' + pl(t.closable, 'closable case') + ' closed.' : 'None of the answered cases is closable.') + '</span>';
    var tile = function (label, val, cls, sub) {
      return '<div class="k-metric"><span class="k-metric__label">' + label + '</span><span class="k-metric__val' + (cls ? ' ' + cls : '') + '">' + val + '</span>' +
        '<div class="k-row"><span class="k-metric__how">' + sub + '</span></div></div>';
    };
    var html = '<h2 class="h2">' + head + '</h2>' +
      '<div class="k-metrics">' +
      tile('Wrongful closes', fmt(t.wrongful_closes), t.wrongful_closes ? 'is-bad' : 'is-ok', 'Closed a case that needed an RFI or an escalation') +
      tile('Closable cases closed', pct(t.closable_closed, t.closable), '', fmt(t.closable_closed) + ' of ' + fmt(t.closable)) +
      tile('Verdict score', t.verdict_score == null ? 'n/a' : (100 * t.verdict_score).toFixed(1) + '%', '', 'Share of the escalate-everything cost saved') +
      tile('Cost a case', t.cost_per_case == null ? 'n/a' : t.cost_per_case.toFixed(3), '', fmt(t.cost) + ' in all; escalating everything costs ' + fmt(t.escalate_all_cost)) +
      '</div>' +
      '<p class="kd-note">' + esc(how) + '. Costs are the brief\'s table: a wrongful close 10, a closable case not closed 3, an RFI on a case that should escalate 3, an escalation on a case that needed an RFI 2.' +
      (t.missing_lines ? ' ' + fmt(t.missing_lines) + ' answered case' + (t.missing_lines === 1 ? ' had' : 's had') + ' no output line and count as ESCALATE.' : '') +
      (score.unmatched ? ' ' + fmt(score.unmatched) + ' answer' + (score.unmatched === 1 ? ' names a case' : 's name cases') + ' not in the drop and ' + (score.unmatched === 1 ? 'is' : 'are') + ' left out.' : '') +
      (t.reason_codes_labelled ? ' Reason codes right: ' + fmt(t.reason_codes_right) + ' of ' + fmt(t.reason_codes_labelled) + ' right verdicts that carry a code.' : '') + '</p>';
    if (score.copy_warning) {
      html += '<p class="kd-err">Every answered case matches the system exactly. Check the answers are not a copy of a system output before quoting this.</p>';
    }
    html += '<div class="k-tablewrap"><table class="k-table"><thead><tr><th>Right verdict</th>' +
      VS.map(function (v) { return '<th class="kd-num">Sent ' + v + '</th>'; }).join('') + '</tr></thead><tbody>' +
      VS.map(function (r) {
        return '<tr><td>' + KF.chip(r) + '</td>' + VS.map(function (c) {
          var n = t.confusion[r][c];
          return '<td class="kd-num">' + (r === c ? '<b>' + fmt(n) + '</b>' : fmt(n)) + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</tbody></table></div>';
    var ms = t.mistakes.slice(0, 50);
    if (ms.length) {
      html += '<h3 class="h3">The costliest disagreements</h3><div class="k-tablewrap"><table class="k-table"><thead><tr><th>Case</th><th>Right</th><th>Sent</th><th class="kd-num">Cost</th></tr></thead><tbody>' +
        ms.map(function (m) {
          return '<tr><td class="kd-mono">' + esc(m.case_id) + '</td><td>' + KF.chip(m.right_verdict) + (m.right_reason_code ? '<span class="kd-sub">' + esc(m.right_reason_code) + '</span>' : '') +
            '</td><td>' + KF.chip(m.sent_verdict) + (m.sent_reason_code ? '<span class="kd-sub">' + esc(m.sent_reason_code) + '</span>' : '') + '</td><td class="kd-num">' + m.cost + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        (t.mistakes.length > ms.length ? '<p class="kd-note">The first 50 of ' + fmt(t.mistakes.length) + ', costliest first. All of them are in the download.</p>' : '');
    }
    el.innerHTML = html;
    el.hidden = false;
  }

  /* ---------- every verdict, with its records ---------- */
  function renderCases() {
    var have = results.filter(Boolean);
    if (!have.length) return;
    $('kd-cases').hidden = false;
    $('kd-inst-seg').innerHTML = have.length < 2 ? '' : have.map(function (r) {
      return '<button type="button" data-inst="' + r.index + '" aria-pressed="' + (r.index === view.inst) + '">' + esc(r.name) + '</button>';
    }).join('');
    $('kd-inst-seg').hidden = have.length < 2;
    $('kd-v-seg').innerHTML = ['ALL'].concat(VS).map(function (v) {
      return '<button type="button" data-v="' + v + '" aria-pressed="' + (v === view.v) + '">' + (v === 'ALL' ? 'All' : KF.V[v].mk + ' ' + v) + '</button>';
    }).join('');
    drawRows();
  }
  function drawRows() {
    var r = results[view.inst] || results.filter(Boolean)[0];
    if (!r) return;
    var rows = r.rows.filter(function (x) { return view.v === 'ALL' || x.verdict === view.v; });
    var show = rows.slice(0, view.shown);
    $('kd-rows').innerHTML = show.map(function (x) {
      var ev = (x.evidence || []), more = ev.length > 6 ? ' +' + (ev.length - 6) : '';
      return '<tr><td class="kd-mono">' + esc(x.case_id) + '<span class="kd-sub">' + esc((x.alert_ids || []).length) + ' alert' + ((x.alert_ids || []).length === 1 ? '' : 's') + '</span></td>' +
        '<td>' + (KF.V[x.verdict] ? KF.chip(x.verdict) : esc(x.verdict)) + '<span class="kd-sub">' + esc(x.reason_code) + '</span></td>' +
        '<td><span class="kd-reason" title="' + esc(x.reason) + '">' + esc(x.reason) + '</span></td>' +
        '<td class="kd-mobile-hide"><span class="kd-ids">' + ev.slice(0, 6).map(esc).join(' · ') + esc(more) + '</span></td></tr>';
    }).join('');
    $('kd-more').hidden = rows.length <= show.length;
    $('kd-shown').textContent = fmt(show.length) + ' of ' + fmt(rows.length) + ' at ' + r.name;
  }

  /* ---------- wiring ---------- */
  function wire() {
    lead = window.Keystone && Keystone.bot ? Keystone.bot($('kd-lead')) : null;
    var zone = $('kd-drop'), depth = 0;
    zone.addEventListener('dragenter', function (e) { e.preventDefault(); depth++; if (!busy) zone.classList.add('is-over'); });
    zone.addEventListener('dragover', function (e) { e.preventDefault(); e.dataTransfer.dropEffect = busy ? 'none' : 'copy'; });
    zone.addEventListener('dragleave', function () { depth = Math.max(0, depth - 1); if (!depth) zone.classList.remove('is-over'); });
    zone.addEventListener('drop', function (e) {
      e.preventDefault(); depth = 0; zone.classList.remove('is-over');
      if (busy) return;
      var dt = e.dataTransfer, entries = [];
      // entries must be taken synchronously, before the drop event ends
      if (dt.items && dt.items.length && dt.items[0].webkitGetAsEntry) {
        for (var i = 0; i < dt.items.length; i++) { var en = dt.items[i].webkitGetAsEntry(); if (en) entries.push(en); }
      }
      if (entries.length) {
        Promise.all(entries.map(function (en) { return readEntry(en, ''); }))
          .then(function (lists) { take([].concat.apply([], lists)); }, function (err) { fail('Could not read the drop: ' + (err && err.message || err) + '.'); });
      } else {
        take(fromList(dt.files));
      }
    });
    // a drop outside the zone must not open the file in the tab
    window.addEventListener('dragover', function (e) { e.preventDefault(); });
    window.addEventListener('drop', function (e) { e.preventDefault(); });
    $('kd-pick-zip').addEventListener('click', function () { $('kd-zip').click(); });
    $('kd-pick-dir').addEventListener('click', function () { $('kd-dir').click(); });
    $('kd-zip').addEventListener('change', function () { take(fromList(this.files)); this.value = ''; });
    $('kd-dir').addEventListener('change', function () { take(fromList(this.files)); this.value = ''; });
    $('kd-inst-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-inst]'); if (!b) return;
      view.inst = Number(b.getAttribute('data-inst')); view.shown = 50; renderCases();
    });
    $('kd-v-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-v]'); if (!b) return;
      view.v = b.getAttribute('data-v'); view.shown = 50; renderCases();
    });
    $('kd-more').addEventListener('click', function () { view.shown += 50; drawRows(); });
    $('kd-download').addEventListener('click', function () {
      worker.postMessage({ type: 'zip', summary: JSON.stringify(summary(), null, 2) + '\n' });
    });
    $('kd-again').addEventListener('click', function () {
      if (busy || !results.length) return;
      busy = true; again = []; $('kd-drop').classList.add('is-busy'); $('kd-again-out').textContent = '';
      worker.postMessage({ type: 'again', count: results.length });
    });
  }
  function summary() {
    var t = score && score.total;
    return {
      made_by: 'ui/drop.html, running system/run in the browser', engine: engine, python: python,
      institutions: results.filter(Boolean).map(function (r) {
        return { name: r.name, cases: r.cases, verdicts: r.verdicts, sha256: r.sha256, seconds: r.seconds, problems: r.problem_count };
      }),
      right_answers_from: found ? found.label_files : [],
      score: t ? (function () { var o = {}; Object.keys(t).forEach(function (k) { if (k !== 'mistakes') o[k] = t[k]; }); o.mistakes = t.mistakes; return o; })() : null
    };
  }

  function boot() { wire(); start(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.KFDrop = { take: take };
})();
