/* Keystone · Financial Crime: runs the scored system inside this browser tab.

   Python comes from Pyodide (CPython 3.12 compiled to WebAssembly). The system's own files come from
   ../engine/, copied from system/ and tools/run_drop.py by tools/sync_ui_engine.py; each one is checked
   against the sha256 in ../engine/manifest.json before it runs. Dropped files are written to Pyodide's
   in-memory disk and never sent anywhere. */
var PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
importScripts(PYODIDE + 'pyodide.js');

var py = null, booting = null, browser = null;

function post(msg, transfer) { self.postMessage(msg, transfer || []); }

async function sha256(text) {
  var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
}

function boot() {
  if (booting) return booting;
  booting = (async function () {
    post({ type: 'status', step: 'python' });
    py = await loadPyodide({
      indexURL: PYODIDE,
      stdout: function () {},
      stderr: function (line) { post({ type: 'log', text: line }); }
    });
    post({ type: 'status', step: 'engine' });
    var res = await fetch('../engine/manifest.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('engine/manifest.json answered ' + res.status);
    var man = await res.json();
    for (var i = 0; i < man.files.length; i++) {
      var f = man.files[i];
      var r = await fetch('../engine/' + f.path + '?v=' + f.sha256.slice(0, 12));
      if (!r.ok) throw new Error('engine/' + f.path + ' answered ' + r.status);
      var text = await r.text();
      if (await sha256(text) !== f.sha256) throw new Error('engine/' + f.path + ' does not match its manifest entry');
      var dir = '/engine/' + f.path.split('/').slice(0, -1).join('/');
      py.FS.mkdirTree(dir);
      py.FS.writeFile('/engine/' + f.path, text);
    }
    py.runPython('import sys\nsys.path.insert(0, "/engine")\nimport browser');
    browser = py.globals.get('browser');
    post({ type: 'ready', engine: man.engine, files: man.files.length, python: py.runPython('import sys; sys.version.split()[0]') });
  })();
  booting.catch(function (e) { post({ type: 'error', where: 'boot', text: String(e && e.message || e) }); });
  return booting;
}

function writeDrop(files) {
  browser.reset();
  files.forEach(function (f) {
    var clean = f.path.replace(/\\/g, '/').split('/').filter(function (p) { return p && p !== '.' && p !== '..'; });
    if (!clean.length) return;
    var dir = '/drop/' + clean.slice(0, -1).join('/');
    py.FS.mkdirTree(dir);
    py.FS.writeFile('/drop/' + clean.join('/'), new Uint8Array(f.buf));
  });
}

self.onmessage = async function (e) {
  var m = e.data;
  try {
    await boot();
    if (m.type === 'boot') return;
    if (m.type === 'drop') {
      writeDrop(m.files);
      post({ type: 'found', found: JSON.parse(browser.prepare()) });
    } else if (m.type === 'run') {
      var found = JSON.parse(m.found);
      for (var i = 0; i < found.institutions.length; i++) {
        (function (idx) {
          post({ type: 'start', index: idx });
          var tick = function (n) { post({ type: 'progress', index: idx, done: n }); };
          var out = browser.run(idx, tick);
          post({ type: 'result', result: JSON.parse(out) });
        })(i);
      }
      post({ type: 'score', score: JSON.parse(browser.score()) });
    } else if (m.type === 'again') {
      for (var j = 0; j < m.count; j++) {
        post({ type: 'again-start', index: j });
        var res = browser.run.callKwargs(j, { again: true });
        post({ type: 'again', result: JSON.parse(res) });
      }
      post({ type: 'again-done' });
    } else if (m.type === 'zip') {
      var path = browser.zip_answers(m.summary);
      var bytes = py.FS.readFile(path);
      post({ type: 'zip', bytes: bytes.buffer }, [bytes.buffer]);
    }
  } catch (err) {
    post({ type: 'error', where: m.type, text: String(err && err.message || err) });
  }
};
