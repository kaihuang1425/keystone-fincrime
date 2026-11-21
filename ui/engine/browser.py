"""The drop page's driver. Runs inside the browser (Pyodide) on files the visitor drops; nothing leaves the page.

The worker writes the dropped files under /drop, then calls prepare(), run(i) for each institution
folder found, and score(). Verdicts come from system/run's own main() and the triage/ package, copied
here by tools/sync_ui_engine.py. Unpacking, the output checks and the scoring come from
tools/run_drop.py, so the page and the command line give the same answers and the same figures.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import time
import zipfile

ENGINE = os.path.dirname(os.path.abspath(__file__))
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)
sys.dont_write_bytecode = True

import run_drop as rd  # noqa: E402

DROP, WORK, OUT = "/drop", "/work", "/answers"
state = {"found": [], "labels": {}, "results": {}}


def _system_run():
    """system/run as a module, loaded fresh, so its main() is exactly what the grader calls."""
    loader = importlib.machinery.SourceFileLoader("system_run", os.path.join(ENGINE, "run"))
    spec = importlib.util.spec_from_loader("system_run", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def reset():
    for d in (DROP, WORK, OUT):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    state.update(found=[], labels={}, results={})


def _shown(path):
    for base in (os.path.join(WORK, "top"), os.path.join(WORK, "inner"), DROP):
        if path.startswith(base + "/"):
            rel = os.path.relpath(path, base).split("/")
            return "/".join(rel[1:] if base != DROP and rel[0].isdigit() else rel)
    return os.path.basename(path)


def prepare():
    """Find the institution folders and any right answers in the drop. Returns JSON."""
    notes, roots, nested_from, loose = [], [DROP], [], []
    for i, name in enumerate(sorted(os.listdir(DROP))):
        path = os.path.join(DROP, name)
        if os.path.isdir(path):
            nested_from.append(path)
        elif rd.is_archive(path):
            target = os.path.join(WORK, "top", str(i), rd.archive_stem(path))
            try:
                rd.unpack(path, target)
                roots.append(target)
                nested_from.append(target)
            except (rd.DropError, OSError, zipfile.BadZipFile) as exc:
                notes.append("Could not open %s: %s" % (name, str(exc).replace(path, name)))
        elif name.lower().endswith(rd.TABLES) and name not in rd.KIT_FILES:
            loose.append(path)  # a table dropped on its own is meant as answers, whatever its name
    inner = os.path.join(WORK, "inner")
    for path in nested_from:
        rd.unpack_nested(path, inner, notes)
    if os.path.isdir(inner):
        roots.append(inner)

    found = rd.find_institutions(roots)
    names = []
    for root, base in found:
        name = os.path.basename(base) if base != DROP else "your-files"
        if name in names:
            name = "%s-%d" % (name, len(names) + 1)
        names.append(name)

    label_files = sorted(set(loose + rd.find_label_files(roots)))
    label_notes = []
    labels = rd.load_labels(label_files, label_notes) if label_files else {}
    notes += [n for n in label_notes if not n.endswith(": 0 label(s) read from 0 record(s)")]

    state["found"] = []
    for (root, base), name in zip(found, names):
        cases = rd.jsonl(os.path.join(base, "cases.jsonl"))
        state["found"].append({
            "name": name, "folder": base, "shown": _shown(base) if base != DROP else "dropped files",
            "cases": len(cases), "missing": [f for f in rd.KIT_FILES if not os.path.exists(os.path.join(base, f))],
        })
    state["labels"] = labels
    every = [os.path.relpath(os.path.join(b, f), r) for r in roots for b, _, fs in rd._walk(r) for f in fs]
    return json.dumps({
        "institutions": [{k: v for k, v in e.items() if k != "folder"} for e in state["found"]],
        "labels": len(labels),
        "label_files": [_shown(p) for p in label_files],
        "notes": notes,
        "files_seen": len(every),
        "sample_files": sorted(every)[:20],
    })


def run(index, progress=None, every=25, again=False):
    """Run system/run on one institution folder. Returns JSON with the verdicts and the checks."""
    entry = state["found"][index]
    mod = _system_run()
    decide = mod.safe_decide
    count = [0]

    def counted(inst, row):
        result = decide(inst, row)
        count[0] += 1
        if progress is not None and count[0] % every == 0:
            progress(count[0])
        return result

    mod.safe_decide = counted
    out = os.path.join(OUT if not again else WORK, entry["name"] + (".jsonl" if not again else ".again.jsonl"))
    start = time.time()
    code = mod.main(["run", entry["folder"], out])
    seconds = time.time() - start
    with open(out, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if again:
        first = state["results"].get(index, {}).get("sha256")
        return json.dumps({"index": index, "sha256": sha, "same": sha == first, "seconds": round(seconds, 2)})
    cases, rows, problems, counts = rd.check_output(entry["folder"], out)
    state["results"][index] = {"sha256": sha, "rows": rows, "ids": [c.get("case_id") for c in cases]}
    return json.dumps({
        "index": index, "name": entry["name"], "exit_code": code, "cases": len(cases),
        "verdicts": counts, "problems": problems[:20], "problem_count": len(problems),
        "seconds": round(seconds, 2), "sha256": sha,
        "rows": [{k: r.get(k) for k in rd.FIELDS} for r in rows],
    })


def score():
    """The brief's cost table against the right answers in the drop. Returns JSON, or null with no answers."""
    labels = state["labels"]
    if not labels:
        return json.dumps(None)
    per, all_ids, sent = [], [], {}
    for index, res in sorted(state["results"].items()):
        here = {r.get("case_id"): (r.get("verdict"), r.get("reason_code")) for r in res["rows"]}
        s = rd.tally(res["ids"], labels, here)
        s.pop("mistakes")
        per.append({"name": state["found"][index]["name"], "score": s})
        all_ids += res["ids"]
        sent.update(here)
    total = rd.tally(all_ids, labels, sent)
    total["mistakes"].sort(key=lambda m: (-m["cost"], m["case_id"]))
    return json.dumps({"total": total, "per": per, "unmatched": len(set(labels) - set(all_ids)),
                       "copy_warning": bool(total["labelled"]) and total["verdicts_right"] == total["labelled"]
                       and total["reason_codes_right"] == total["reason_codes_labelled"]})


def zip_answers(summary_json):
    """Every answer file plus the page's summary, as /answers.zip for the download button."""
    path = "/answers.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(OUT)):
            zf.write(os.path.join(OUT, name), name)
        zf.writestr("summary.json", summary_json)
    return path
