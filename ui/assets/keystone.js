/* @ds-bundle: {"format":4,"namespace":"Keystone","components":[{"name":"AppShell"},{"name":"BotAvatar"},{"name":"Roster"},{"name":"Thread"},{"name":"ActionFeed"},{"name":"Handoff"},{"name":"Routine"},{"name":"Approval"},{"name":"Takeover"},{"name":"Toast"},{"name":"Citation"},{"name":"SourcePeek"},{"name":"ExtractionTable"},{"name":"Trace"},{"name":"Chip"},{"name":"Metrics"},{"name":"PropertyCard"},{"name":"EPC"},{"name":"Compliance"},{"name":"RentRoll"},{"name":"Ticket"},{"name":"Covenant"},{"name":"Map"},{"name":"Button"},{"name":"AskBar"},{"name":"Loader"},{"name":"TitleCard"}]} */
/* Keystone helpers: a vanilla script, no framework. Assigns window.Keystone.
   Bots: Keystone.bot(el, opts) and Keystone.mount(root). Motion: count, flip, type, fly, toast, feed,
   relay, scene, loader, reveal, liveRow, sla. Behaviours wired by data attributes: approve, switch, cite. */
(function () {
  'use strict';
  var K = window.Keystone = window.Keystone || {};
  var NS = 'http://www.w3.org/2000/svg';
  /* Motion plays on every device, Reduce Motion included (house choice). <html data-k-motion="system"> honours the OS. */
  var reduce = false;
  try { reduce = document.documentElement.getAttribute('data-k-motion') === 'system' && window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
  var uid = 0;

  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function rand(a, b) { return a + Math.random() * (b - a); }
  K.wait = wait;

  /* ---------------- shapes ---------------- */
  function flower() {
    var n = 7, R = 33, cx = 50, cy = 52, d = '';
    for (var i = 0; i <= n; i++) {
      var a = (-90 + 360 / (2 * n) + i * 360 / n) * Math.PI / 180;
      var x = (cx + R * Math.cos(a)).toFixed(2), y = (cy + R * Math.sin(a)).toFixed(2);
      d += i === 0 ? 'M' + x + ' ' + y : 'A17 17 0 0 1 ' + x + ' ' + y;
    }
    return d + 'Z';
  }
  var SHAPES = {
    house: { d: 'M44 11a9 9 0 0 1 12 0l30 26c3 2.6 4 5 4 9v36c0 6-4 10-10 10H20c-6 0-10-4-10-10V46c0-4 1-6.4 4-9z', face: [57, 62] },
    circle: { d: 'M50 10a42 42 0 1 1 0 84a42 42 0 1 1 0-84z', face: [61, 38] },
    squircle: { d: 'M36 12h28a26 26 0 0 1 26 26v28a26 26 0 0 1-26 26H36a26 26 0 0 1-26-26V38a26 26 0 0 1 26-26z', face: [58, 44] },
    drop: { d: 'M50 6C59 21 85 40 85 58a35 35 0 0 1-70 0C15 40 41 21 50 6z', face: [53, 62] },
    cloud: { d: 'M28 84a18 18 0 0 1-5-35a22 22 0 0 1 34-21a20 20 0 0 1 30 20a19 19 0 0 1-9 36z', face: [57, 56] },
    flower: { d: flower(), face: [57, 46] },
    pill: { d: 'M36 28h28a26 26 0 0 1 0 52H36a26 26 0 0 1 0-52z', face: [60, 52] },
    triangle: { d: 'M50 12c5 0 8 3 11 8l28 50c5 9 0 18-10 18H21c-10 0-15-9-10-18l28-50c3-5 6-8 11-8z', face: [52, 62] }
  };
  K.shapes = Object.keys(SHAPES);
  K.colors = ['chief', 'blue', 'pink', 'orange', 'green', 'violet', 'teal'];
  K.states = ['idle', 'working', 'thinking', 'waiting', 'blocked', 'done'];

  /* ---------------- the bot avatar ---------------- */
  function build(host, shape) {
    var s = SHAPES[shape] || SHAPES.circle, id = 'kspec' + (++uid);
    var svg = el('svg', { viewBox: '0 0 100 100', 'aria-hidden': 'true', focusable: 'false' });
    var defs = el('defs', {}, svg);
    var lg = el('linearGradient', { id: id, x1: '0', y1: '0', x2: '1', y2: '1' }, defs);
    for (var i = 1; i <= 5; i++) el('stop', { offset: ((i - 1) / 4).toFixed(2), style: 'stop-color:var(--spectrum-' + i + ')' }, lg);
    el('circle', { 'class': 'k-b-halo', cx: '50', cy: '52', r: '47' }, svg);
    var all = el('g', { 'class': 'k-b-all' }, svg);
    el('circle', { 'class': 'k-b-comet', cx: '50', cy: '56', r: '30', stroke: 'url(#' + id + ')', 'stroke-dasharray': '34 155' }, all);
    var dots = el('g', { 'class': 'k-b-dots' }, all);
    el('circle', { cx: '29', cy: '56', r: '6.5' }, dots);
    el('circle', { cx: '71', cy: '56', r: '6.5' }, dots);
    el('rect', { 'class': 'k-b-bar', x: '44.5', y: '28', width: '11', height: '36', rx: '5.5' }, all);
    var wrap = el('g', { 'class': 'k-b-wrap' }, all);
    var bob = el('g', { 'class': 'k-b-bob' }, wrap);
    el('path', { 'class': 'k-b-body', d: s.d }, bob);
    var face = el('g', { transform: 'translate(' + s.face[0] + ' ' + s.face[1] + ')' }, bob);
    var look = el('g', { 'class': 'k-b-look' }, face);
    var eyes = el('g', { 'class': 'k-b-eyes' }, look);
    var le = el('g', { 'class': 'k-b-eye' }, eyes);
    el('rect', { x: '-12.5', y: '-8', width: '9', height: '20', rx: '4.5' }, le);
    var re = el('g', { 'class': 'k-b-eye' }, eyes);
    el('rect', { x: '3.5', y: '-12', width: '9', height: '20', rx: '4.5' }, re);
    var sp = el('g', { 'class': 'k-b-sparks' }, all);
    for (var j = 0; j < 6; j++) el('circle', { 'class': 'k-b-spark', cx: '50', cy: '56', r: '3.6', style: '--a:' + (j * 60 + 20) + 'deg' }, sp);
    host.appendChild(svg);
    return { svg: svg, look: look, eyes: [le, re] };
  }

  K.bot = function (host, o) {
    if (!host) return null;
    if (host._kbot) return host._kbot;
    o = o || {};
    var shape = o.shape || host.getAttribute('data-shape') || 'circle';
    var color = o.color || host.getAttribute('data-color') || 'blue';
    host.classList.add('k-bot');
    host.setAttribute('data-shape', shape);
    host.setAttribute('data-color', color);
    if (o.size) host.style.setProperty('--size', typeof o.size === 'number' ? o.size + 'px' : o.size);
    var parts = build(host, shape);
    var timer = null, blinkT = null, state = null, sayEl = null, side = 1;

    function setLook(x, y) { parts.look.style.transform = 'translate(' + x + 'px,' + y + 'px)'; }
    function blink() {
      if (reduce) return;
      parts.eyes.forEach(function (e) { e.classList.add('is-blink'); });
      setTimeout(function () { parts.eyes.forEach(function (e) { e.classList.remove('is-blink'); }); }, 120);
    }
    function loopBlink() {
      clearTimeout(blinkT);
      if (reduce) return;
      blinkT = setTimeout(function () { if (state === 'idle' || state === 'working' || state === 'waiting') blink(); loopBlink(); }, rand(2600, 5200));
    }
    function glance() {
      clearTimeout(timer);
      if (reduce) return;
      if (state === 'idle') { setLook(rand(-5, 6).toFixed(1), rand(-6, 4).toFixed(1)); timer = setTimeout(glance, rand(1400, 3400)); }
      else if (state === 'working') { setLook(rand(2, 7).toFixed(1), rand(-8, -3).toFixed(1)); timer = setTimeout(glance, rand(500, 1100)); }
      else if (state === 'waiting') { side = -side; setLook(6 * side, 1); timer = setTimeout(glance, 1600); }
    }
    function set(next) {
      if (K.states.indexOf(next) < 0) next = 'idle';
      state = next;
      host.setAttribute('data-state', next);
      clearTimeout(timer);
      if (next === 'done') setLook(-6, 6);
      else if (next === 'thinking' || next === 'blocked') setLook(0, 0);
      else if (next === 'working') setLook(4, -6);
      else setLook(2, -2);
      if (next === 'idle' || next === 'working' || next === 'waiting') timer = setTimeout(glance, next === 'idle' ? 900 : 300);
      return ctl;
    }
    function ack() {
      host.classList.remove('is-ack'); void host.getBoundingClientRect(); host.classList.add('is-ack');
      setTimeout(function () { host.classList.remove('is-ack'); }, 460);
      return ctl;
    }
    function say(text) {
      if (text == null) text = '';
      host.setAttribute('data-say', text);
      if (!sayEl) { sayEl = document.createElement('span'); sayEl.className = 'k-b-say'; sayEl.setAttribute('role', 'tooltip'); host.appendChild(sayEl); }
      sayEl.textContent = text;
      if (text) { if (!host.hasAttribute('tabindex')) host.setAttribute('tabindex', '0'); host.setAttribute('aria-label', (host.getAttribute('data-name') || 'Bot') + ': ' + text); }
      return ctl;
    }
    var ctl = { el: host, set: set, ack: ack, say: say, blink: blink, look: setLook, get state() { return state; },
      destroy: function () { clearTimeout(timer); clearTimeout(blinkT); } };
    host._kbot = ctl;
    if (!host.hasAttribute('role')) host.setAttribute('role', 'img');
    if (!host.hasAttribute('aria-label')) host.setAttribute('aria-label', (o.name || host.getAttribute('data-name') || 'Bot'));
    set(o.state || host.getAttribute('data-state') || 'idle');
    loopBlink();
    var s0 = o.say || host.getAttribute('data-say'); if (s0) say(s0);
    return ctl;
  };
  K.mount = function (root) {
    return qa('[data-k-bot]', root).map(function (n) { return K.bot(n); });
  };

  /* ---------------- text motion ---------------- */
  K.count = function (node, to, o) {
    o = o || {};
    var from = o.from != null ? o.from : 0, dec = o.dec || 0, ms = reduce ? 1 : (o.ms || 850);
    var pre = o.prefix || '', suf = o.suffix || '', t0 = performance.now();
    var fmt = function (v) { return pre + v.toLocaleString('en-GB', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf; };
    return new Promise(function (res) {
      (function tick(t) {
        var p = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - p, 3);
        node.textContent = fmt(from + (to - from) * e);
        if (p < 1) requestAnimationFrame(tick); else res();
      })(t0);
    });
  };
  K.flip = function (node, text) {
    node.textContent = text;
    node.classList.remove('k-flip'); void node.offsetWidth; node.classList.add('k-flip');
  };
  K.type = function (node, text, ms) {
    ms = reduce ? 0 : (ms || 26);
    var field = /^(INPUT|TEXTAREA)$/.test(node.tagName);
    var put = function (v) { if (field) node.value = v; else node.textContent = v; };
    put(''); if (!field) node.classList.add('k-caret');
    return new Promise(function (res) {
      var i = 0;
      (function step() {
        put(text.slice(0, ++i));
        if (i < text.length) setTimeout(step, ms); else { node.classList.remove('k-caret'); res(); }
      })();
    });
  };
  K.status = function (node, text, working) {
    var t = q('.k-say__text', node) || node;
    K.flip(t, text);
    node.classList.toggle('is-working', !!working);
  };

  /* a chip that travels from one element to another: handoffs and citations */
  K.fly = function (from, to, html, o) {
    o = o || {};
    var a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
    var chip = document.createElement('div');
    chip.className = 'k-fly' + (o.cite ? ' k-fly--cite' : '');
    chip.innerHTML = html;
    document.body.appendChild(chip);
    var w = chip.offsetWidth, h = chip.offsetHeight;
    var x0 = a.left + a.width / 2 - w / 2, y0 = a.top + a.height / 2 - h / 2;
    var x1 = b.left + b.width / 2 - w / 2, y1 = b.top + b.height / 2 - h / 2;
    var lift = o.lift != null ? o.lift : -36;
    if (reduce || !chip.animate) { chip.remove(); return Promise.resolve(); }
    var anim = chip.animate([
      { transform: 'translate(' + x0 + 'px,' + y0 + 'px) scale(.6)', opacity: 0 },
      { transform: 'translate(' + x0 + 'px,' + y0 + 'px) scale(1)', opacity: 1, offset: .15 },
      { transform: 'translate(' + ((x0 + x1) / 2) + 'px,' + (Math.min(y0, y1) + lift) + 'px) scale(1)', opacity: 1, offset: .55 },
      { transform: 'translate(' + x1 + 'px,' + y1 + 'px) scale(.85)', opacity: 1, offset: .92 },
      { transform: 'translate(' + x1 + 'px,' + y1 + 'px) scale(.5)', opacity: 0 }
    ], { duration: o.ms || 760, easing: 'cubic-bezier(.65,0,.35,1)' });
    return new Promise(function (res) { anim.onfinish = function () { chip.remove(); res(); }; });
  };

  /* ---------------- toast ---------------- */
  K.toast = function (text, o) {
    o = o || {};
    var box = q('.k-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'k-toasts'; box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div'), ms = o.ms || 5000;
    t.className = 'k-toast'; t.style.setProperty('--ms', ms + 'ms');
    var mark = o.mark === false ? '' : '<span class="k-mk k-mk--' + (o.mark || 'ok') + '">' + ({ ok: '✓', ask: '?', bad: '✕' }[o.mark || 'ok']) + '</span>';
    t.innerHTML = mark + '<span></span>';
    t.querySelector('span:last-child').textContent = text;
    var closed = false;
    function close() { if (closed) return; closed = true; t.classList.add('is-out'); setTimeout(function () { t.remove(); }, 320); }
    if (o.undo) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = o.undoLabel || 'Undo';
      b.addEventListener('click', function () { o.undo(); close(); });
      t.appendChild(b);
    }
    box.appendChild(t);
    setTimeout(close, ms);
    return { close: close };
  };

  /* ---------------- action feed ---------------- */
  K.feed = function (node, rows, o) {
    o = o || {};
    var list = q('.k-feed__list', node) || node, i = 0, max = o.max || 7, every = o.every || 1100, timer, stopped = false;
    function push() {
      if (stopped) return;
      if (i >= rows.length) { timer = setTimeout(function () { list.innerHTML = ''; i = 0; push(); }, 2200); return; }
      var r = rows[i++], row = document.createElement('div');
      row.className = 'k-feed__row is-now';
      row.innerHTML = '<b></b><span></span>';
      row.firstChild.textContent = r[0]; row.lastChild.textContent = r[1] || '';
      var prev = q('.is-now', list); if (prev) prev.classList.remove('is-now');
      list.appendChild(row);
      while (list.children.length > max) list.removeChild(list.firstChild);
      timer = setTimeout(push, every);
    }
    push();
    return { stop: function () { stopped = true; clearTimeout(timer); } };
  };

  /* ---------------- visibility helper ---------------- */
  function whenVisible(node, on, off) {
    if (!('IntersectionObserver' in window)) { on(); return; }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) on(); else if (off) off(); }); }, { threshold: .25 });
    io.observe(node);
  }
  K.whenVisible = whenVisible;

  /* ---------------- scene: the product as a story ---------------- */
  K.scene = function (root, o) {
    var timers = [], running = false;
    var s = {
      root: root,
      at: function (ms, fn) { timers.push(setTimeout(fn, reduce ? 0 : ms)); },
      step: function (n) { for (var i = 1; i <= (o.steps || 9); i++) root.classList.toggle('s' + i, i <= n); },
      flag: function (name, on) { root.classList.toggle(name, on !== false); }
    };
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function run() {
      clear(); if (o.reset) o.reset(s); s.step(0);
      o.play(s);
      if (o.loop) timers.push(setTimeout(run, o.loop));
    }
    whenVisible(root, function () { if (!running) { running = true; run(); } }, function () { running = false; clear(); if (o.finish) o.finish(s); });
    return { replay: run, stop: clear };
  };

  /* ---------------- handoff relay ---------------- */
  K.relay = function (root, o) {
    o = o || {};
    var nodes = qa('.k-relay__node', root), every = o.every || 1800, timers = [], running = false;
    var bots = nodes.map(function (n) { return K.bot(q('[data-k-bot], .k-bot', n)); });
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function at(ms, fn) { timers.push(setTimeout(fn, ms)); }
    function run() {
      clear();
      nodes.forEach(function (n, i) { n.classList.remove('is-on'); bots[i].set('idle'); var sm = q('small', n); if (sm && n.dataset.idle) sm.textContent = n.dataset.idle; });
      nodes.forEach(function (n, i) {
        var t = 300 + i * every;
        at(t, function () {
          n.classList.add('is-on'); bots[i].ack(); bots[i].set('working');
          var sm = q('small', n); if (sm && n.dataset.doing) K.flip(sm, n.dataset.doing);
        });
        at(t + every * .62, function () {
          bots[i].set('done');
          var sm = q('small', n); if (sm && n.dataset.done) K.flip(sm, n.dataset.done);
          if (nodes[i + 1]) K.fly(bots[i].el, bots[i + 1].el, n.dataset.pass || 'Handoff', { ms: every * .34 });
        });
      });
      at(300 + nodes.length * every + 2600, run);
    }
    whenVisible(root, function () { if (!running) { running = true; run(); } }, function () { running = false; clear(); });
    return { replay: run, stop: clear };
  };

  /* ---------------- rows, meters, sla ---------------- */
  K.liveRow = function (tbody, html) {
    var tr = document.createElement('tr'); tr.className = 'is-new'; tr.innerHTML = html;
    tbody.insertBefore(tr, tbody.firstChild);
    setTimeout(function () { tr.classList.remove('is-new'); }, 1700);
    return tr;
  };
  K.sla = function (svgEl, total, left) {
    var fg = q('.k-sla__fg', svgEl); if (fg) fg.style.strokeDashoffset = String(100 - Math.max(0, Math.min(100, left / total * 100)));
  };

  /* ---------------- loader: topping out ---------------- */
  K.loader = function (o) {
    o = o || {};
    var steps = o.steps || [['Reading the leases', '14 leases'], ['Checking the rent roll', '48 units'], ['Citing every figure', '212 sources']];
    var inline = !!o.el, root = document.createElement('div');
    root.className = 'k-loader' + (inline ? ' k-loader--inline' : '');
    root.setAttribute('role', 'status'); root.setAttribute('aria-live', 'polite');
    var floors = '';
    for (var i = 0; i < steps.length; i++) floors += '<i style="--k:' + i + '"></i>';
    root.innerHTML = '<div class="k-loader__box"><div class="k-loader__tower">' + floors + '<span class="k-loader__cap"></span><span class="k-loader__tag">0%</span></div>' +
      '<div class="k-loader__steps"><div class="k-loader__list"></div><div class="k-loader__now"></div></div></div>';
    (inline ? o.el : document.body).appendChild(root);
    var fl = qa('.k-loader__tower i', root), tag = q('.k-loader__tag', root), now = q('.k-loader__now', root), list = q('.k-loader__list', root);
    var p = 0, target = .86, ready = false, done = 0, t0 = performance.now(), dur = o.ms || 1600;
    now.textContent = steps[0][0];
    function draw() {
      var n = steps.length;
      fl.forEach(function (f, i) { f.style.setProperty('--f', Math.max(0, Math.min(1, p * n - i)).toFixed(3)); });
      tag.textContent = Math.round(p * 100) + '%';
      tag.style.bottom = (p * 100).toFixed(1) + '%';
      while (done < n && p >= (done + 1) / n - .001) {
        var row = document.createElement('div'); row.className = 'k-loader__done';
        row.innerHTML = '<span class="k-mk k-mk--ok is-pop">✓</span><span></span><em></em>';
        row.children[1].textContent = steps[done][0]; row.children[2].textContent = steps[done][1] || '';
        list.appendChild(row); done++;
        if (done < n) K.flip(now, steps[done][0]);
      }
    }
    function frame(t) {
      var k = Math.min(1, (t - t0) / dur);
      var goal = ready ? 1 : target * (1 - Math.pow(1 - k, 3));
      p += (goal - p) * (ready ? .14 : .2);
      if (ready && 1 - p < .004) p = 1;
      draw();
      if (p < 1) requestAnimationFrame(frame); else finish();
    }
    function finish() {
      root.classList.add('is-ready'); K.flip(now, o.readyText || 'Ready');
      setTimeout(function () {
        root.classList.add('is-gone');
        setTimeout(function () { if (o.loop && inline) { root.remove(); K.loader(o); } else root.remove(); if (o.onDone) o.onDone(); }, 700);
      }, o.hold || 700);
    }
    requestAnimationFrame(frame);
    var max = setTimeout(function () { ready = true; }, o.max || 8000);
    var api = { done: function () { clearTimeout(max); ready = true; }, el: root };
    if (o.wait && o.wait.then) o.wait.then(api.done, api.done);
    else if (!o.manual) setTimeout(api.done, o.after || 2200);
    return api;
  };

  /* ---------------- reveal on scroll (rise out of a blur) ---------------- */
  K.reveal = function (root) {
    if (reduce || !('IntersectionObserver' in window)) return;
    var vh = window.innerHeight;
    var items = qa('[data-k-reveal]', root).filter(function (n) { return n.getBoundingClientRect().top > vh; });
    items.forEach(function (n) { n.classList.add('k-reveal', 'is-pre'); });
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e, i) { if (e.isIntersecting) { setTimeout(function () { e.target.classList.remove('is-pre'); }, i * 40); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    items.forEach(function (n) { io.observe(n); });
  };

  /* ---------------- behaviours wired by data attributes ---------------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    var ap = t.closest && t.closest('[data-k-approve]');
    if (ap) {
      var card = ap.closest('.k-approve');
      ap.style.width = ap.offsetWidth + 'px'; void ap.offsetWidth;
      ap.classList.add('is-done');
      if (card) {
        card.dispatchEvent(new CustomEvent('k:approve', { bubbles: true }));
        setTimeout(function () {
          card.classList.add('is-gone');
          K.toast(ap.getAttribute('data-k-approve') || 'Approved. Logged to the audit trail.', {
            undo: function () { card.classList.remove('is-gone'); ap.classList.remove('is-done'); ap.style.width = ''; card.dispatchEvent(new CustomEvent('k:undo', { bubbles: true })); }
          });
        }, 520);
      }
      return;
    }
    var dm = t.closest && t.closest('[data-k-dismiss]');
    if (dm) {
      var c2 = dm.closest('.k-approve');
      if (c2) { c2.classList.add('is-gone'); K.toast(dm.getAttribute('data-k-dismiss') || 'Dismissed.', { mark: false, undo: function () { c2.classList.remove('is-gone'); } }); }
      return;
    }
    var tab = t.closest && t.closest('[data-k-tab]');
    if (tab) {
      var box = tab.closest('[data-k-tabs]') || document;
      qa('[data-k-tab]', box).forEach(function (b) { b.setAttribute('aria-pressed', String(b === tab)); });
      qa('[data-k-panel]', box).forEach(function (p) { p.classList.toggle('is-off', p.getAttribute('data-k-panel') !== tab.getAttribute('data-k-tab')); });
      return;
    }
    var th = t.closest && t.closest('[data-k-theme]');
    if (th) {
      var host = th.closest('[data-theme]') || document.documentElement;
      host.setAttribute('data-theme', th.getAttribute('data-k-theme'));
      qa('[data-k-theme]', th.parentNode).forEach(function (b) { b.setAttribute('aria-pressed', String(b === th)); });
      return;
    }
    var tg = t.closest && t.closest('[data-k-toggle]');
    if (tg) {
      var app = tg.closest('.k-app') || document.querySelector('.k-app');
      if (app) app.classList.toggle('is-' + tg.getAttribute('data-k-toggle'));
      return;
    }
    var sw = t.closest && t.closest('.k-switch');
    if (sw) {
      var on = sw.getAttribute('aria-checked') !== 'true';
      sw.setAttribute('aria-checked', String(on));
      var r = sw.closest('.k-routine'); if (r) r.classList.toggle('is-on', on);
      sw.dispatchEvent(new CustomEvent('k:toggle', { bubbles: true, detail: { on: on } }));
      return;
    }
    var ci = t.closest && t.closest('.k-cite');
    qa('.k-cite.is-open').forEach(function (n) { if (n !== ci) n.classList.remove('is-open'); });
    if (ci && !(t.closest('.k-cite__pop'))) ci.classList.toggle('is-open');
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') qa('.k-cite.is-open').forEach(function (n) { n.classList.remove('is-open'); }); });
  /* open a citation's popover towards the side with room, so it never runs off screen */
  function aim(e) {
    var c = e.target.closest && e.target.closest('.k-cite');
    if (c) c.classList.toggle('is-right', c.getBoundingClientRect().left + 316 > document.documentElement.clientWidth);
  }
  document.addEventListener('mouseover', aim);
  document.addEventListener('focusin', aim);
  document.addEventListener('pointerdown', aim);

  /* ---------------- icons (24px grid, 1.75 stroke, currentColor) ---------------- */
  var I = function (p) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + '</svg>'; };
  K.icons = {
    doc: I('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>'),
    clock: I('<circle cx="12" cy="12" r="9"/><path class="k-hand" d="M12 7v5l3 2"/>'),
    check: I('<path d="M5 12.5l4.2 4.2L19 7"/>'),
    route: I('<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5"/>'),
    spark: I('<path d="M12 3c.5 4.5 2.5 6.5 7 7-4.5.5-6.5 2.5-7 7-.5-4.5-2.5-6.5-7-7 4.5-.5 6.5-2.5 7-7z"/>'),
    wrench: I('<path d="M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.5-7.5"/><path d="M14.5 6.5L17 4l3 3-2.5 2.5"/>'),
    shield: I('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>'),
    pin: I('<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>'),
    plus: I('<path d="M12 5v14M5 12h14"/>'),
    mic: I('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
    send: I('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    gear: I('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>'),
    building: I('<path d="M4 21V5l8-2v18M12 8l8 2v11M8 8h.01M8 12h.01M8 16h.01M16 13h.01M16 17h.01"/>'),
    globe: I('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z"/>'),
    cursor: '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M1 1l11 5-4.5 1.5L6 12z"/></svg>',
    tick: '<svg class="k-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7"/></svg>'
  };
  /* fill every [data-k-icon] placeholder */
  K.paint = function (root) {
    qa('[data-k-icon]', root).forEach(function (n) { if (!n.firstChild) n.innerHTML = K.icons[n.getAttribute('data-k-icon')] || ''; });
    qa('[data-k-approve]', root).forEach(function (b) { if (!q('.k-check', b)) b.insertAdjacentHTML('beforeend', K.icons.tick); });
  };
  function boot() { K.paint(document); K.mount(document); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
