# Keystone UI

The interface for the transaction-monitoring system: plain HTML pages on one design system. No build step and no framework. Each page loads the files in `assets/` and nothing else, plus Geist from Google Fonts.

## Open it

Serve the folder rather than double-clicking, so the scripts behave as they do on a host:

```bash
python -m http.server 8080 --directory ui
```

Then go to http://localhost:8080/queue.html.

## Pages

| Page | Shows |
|---|---|
| `walk-monitoring.html` | One case in five steps that play themselves: alert, records, evidence, rule, verdict. `?step=3` opens on a step, `?hold` starts paused |
| `queue.html` | The system's real verdicts, six at a time, for any of the four institutions. Each row opens its case. The RFI card shows what the system says to ask; Edit changes it, Send the request saves it, and Undo takes it back. `?inst=emoney` picks an institution |
| `app.html` | One real case: why it closed, needs a document or was escalated, in the system's own reason. Each bot shows the records it owns; the evidence panel lists the records, the reason sentence by sentence and the trace. The message box answers from that case's reason and records only. `?case=BK-CS100112` opens a case |
| `phone.html` | The real escalations reaching the MLRO, one at a time. Take the case and Send back are saved; the toast shows the latest action from any page, with Undo |
| `landing.html` | What it does: the three rules Track 1 tests, each drawn as a loop, and the measured figures |
| `title-card.html`, `end-card.html` | 1920 × 1080 cards for the video; add `?raw` to record at full size |
| `drop.html` | Drop a zip, a tar or a folder of cases in any layout. The scored system decides them inside the browser tab, and the files are not uploaded. When the drop holds right answers, the brief's score shows with what it was measured on |

## What is real

`queue.html`, `app.html` and `phone.html` show the system's verdicts on the development cases. They read `data/<institution>.json`, which `tools/export_ui.py` writes from `output/`:

```bash
python tools/export_ui.py --rerun <path to the kit's institutions folder> --out ui/data
```

Run it from the repo root whenever `output/` changes. `--rerun` runs the system five more times on the kit's cases to record whether every run gave the same output and how long it took; without it those facts are empty, and the pages leave the claim out. The files hold the system's own words only: verdict, reason code, reason, alert IDs and evidence IDs. No record text from the kit is on the site, so a citation chip shows its ID and the sentence of the reason that cites it. The reasons do name the kit's invented people and amounts, as `output/` does.

`walk-monitoring.html`, `landing.html` and the video cards use invented examples to explain the rules, and say so.

## The drop page and its engine

`drop.html` runs the scored system on whatever the visitor drops, inside the browser tab. `assets/kf-drop-worker.js` loads Python 3.12 through Pyodide from cdn.jsdelivr.net, then each file in `engine/`, and checks every file against its sha256 in `engine/manifest.json` before running it. `engine/` holds copies of `system/run`, `system/triage/` and `tools/run_drop.py`. `engine/browser.py` is the page's own driver: it calls `system/run`'s `main()` for each institution folder and scores with the functions in `tools/run_drop.py`, so the page and the command line give the same answers and figures. On the 4,000 development cases the page's four answer files were byte-identical to `output/` (checked 21 Nov). The dropped files stay in the tab's memory and are not uploaded.

The copies go stale when `system/` or `tools/run_drop.py` changes. Refresh them from the repo root before committing:

```bash
python tools/sync_ui_engine.py
python tools/sync_ui_engine.py --check   # exits 1 when engine/ differs from system/
```

## Where the analyst's actions are kept

Sending an RFI, taking or sending back an escalation, and undoing are saved as rows of `analyst_actions` (see `supabase/schema.sql`). Undo adds an `undone` row; nothing is edited or deleted. Until `assets/kf-config.js` names a Supabase project, the rows are kept in the browser's local storage, so each browser sees its own. To share them, run `supabase/schema.sql` in the project and set its URL and anon key in `assets/kf-config.js`. The anon key is public by design, and row level security lets it read and insert only. Never put the service role key in this folder: it is published.

`assets/kf-data.js` holds the data and the store; `kf-queue.js`, `kf-case.js` and `kf-phone.js` drive the three pages; `kf.css` adds the few styles they need.

## The design system

`RULES.md` holds the design rules: the house rules, every micro-interaction and every component. `assets/keystone.css` and `assets/keystone.js` are the base. `assets/fincrime.css` is the theme. `assets/keystone-walk.css` and `assets/keystone-walk.js` add the walkthrough, the staged reveals and the queue that works itself.

Verdicts use the brief's own words with one glyph each: ✓ CLOSE, ? RFI, ↑ ESCALATE, with the reason code beside in mono. Every verdict on screen carries the records it rests on.
