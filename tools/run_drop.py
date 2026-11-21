"""Run the system on test data dropped in any shape, and score it when the right answers come with it.

    python tools/run_drop.py <zip, tar or folder> [more ...] [--labels FILE] [--out DIR] [--runs N]

The organisers say their unseen cases arrive as institution folders holding the
same files as the development kit. This tool does not assume how they are
packed. It unpacks zips and tars, nested ones too, into a temporary folder,
treats every folder holding cases.jsonl as one institution, and runs
system/run on each one the way the grader does: from inside system/, with full
paths. It then checks each output (one line per case, the reason code belongs
to the verdict, every cited ID exists in that case's files) and compares
repeated runs byte for byte.

Scoring needs the right answers, and the development kit has none. Pass them
with --labels, or include a file whose name says it holds them (label, answer,
gold, truth, expected, solution). Each record needs a case ID and a verdict; a
reason code is optional. JSON lines, a JSON list or map, CSV and TSV are read,
and the usual key spellings are accepted. Without labels the tool reports the
checks and the verdict split, and no accuracy figure.

Costs follow the brief's table (rows: right verdict, columns: verdict sent):

               CLOSE   RFI   ESCALATE
    CLOSE        0      3       3
    RFI         10      0       2
    ESCALATE    10      3       0

A case with no output line counts as ESCALATE. The verdict score is the share of
the escalate-everything cost the system saves: 1 - cost / escalate_all_cost.

Answers go to <input>-answers/ next to each input, or to --out. Nothing in
system/ or output/ is touched. Other scripts can call score(labels, output).
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = os.path.abspath(os.path.join(HERE, "..", "system"))
DEV_OUTPUT = os.path.abspath(os.path.join(HERE, "..", "output"))
RUN = os.path.join(SYSTEM, "run")

VERDICTS = ("CLOSE", "RFI", "ESCALATE")
COST = {
    "CLOSE": {"CLOSE": 0, "RFI": 3, "ESCALATE": 3},
    "RFI": {"CLOSE": 10, "RFI": 0, "ESCALATE": 2},
    "ESCALATE": {"CLOSE": 10, "RFI": 3, "ESCALATE": 0},
}
CODES = {
    "CLOSE": {"COLLECTION_DOCUMENTED", "BUSINESS_RECORDS_RECONCILE", "DOCUMENTED_EVENT", "INVOICE_MATCHES",
              "OWN_ACCOUNT", "GROUP_COMPANY", "THIRD_PARTY_DOCUMENTED", "REFUND_OF_EARLIER_PAYMENT",
              "RETURNING_CUSTOMER", "LIST_MATCH_DIFFERENT_PARTY", "WITHIN_PROFILE"},
    "RFI": {"RFI_PURPOSE_DOCUMENTS", "RFI_BUSINESS_RECORDS", "RFI_SOURCE_OF_FUNDS", "RFI_COUNTERPARTY_DETAILS",
            "RFI_UPDATED_PROFILE"},
    "ESCALATE": {"ESC_MULE_ACTIVITY", "ESC_STRUCTURING", "ESC_UNEXPLAINED_FUNDS", "ESC_PASS_THROUGH",
                 "ESC_INVOICE_MISMATCH", "ESC_HIGH_RISK_CORRIDOR", "ESC_ACCOUNT_MISUSE", "ESC_THIRD_PARTY_FUNDING",
                 "ESC_EARLY_REDEMPTION", "ESC_LISTED_PARTY"},
}
VERDICT_OF_CODE = {code: v for v, codes in CODES.items() for code in codes}
FIELDS = ["case_id", "alert_ids", "verdict", "reason_code", "reason", "evidence"]
KIT_FILES = ("POLICY.md", "cases.jsonl", "alerts.jsonl", "customers.jsonl", "transactions.jsonl",
             "evidence.jsonl", "previous_reviews.jsonl", "internal_list.jsonl")
ARCHIVES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
TABLES = (".jsonl", ".json", ".csv", ".tsv")
LABEL_NAME = re.compile(r"label|answer|gold|truth|expected|solution", re.I)
SKIP_DIRS = ("__MACOSX", "evidence", "output")
MAX_UNPACKED = 8 * 1024 ** 3

CASE_KEYS = ("caseid", "case", "id")
# Spellings that name the right answer come first, so a results file that holds both the
# verdict sent and the expected one is scored against the expected one, never against itself.
RIGHT_VERDICT_KEYS = ("expectedverdict", "goldverdict", "trueverdict", "correctverdict", "rightverdict",
                      "groundtruth", "expected", "gold", "truth", "label", "answer", "target")
RIGHT_CODE_KEYS = ("expectedreasoncode", "goldreasoncode", "truereasoncode", "correctreasoncode",
                   "rightreasoncode")
VERDICT_KEYS = RIGHT_VERDICT_KEYS + ("verdict", "decision", "outcome")
CODE_KEYS = RIGHT_CODE_KEYS + ("reasoncode", "code")
VERDICT_WORDS = {"CLOSE": "CLOSE", "CLOSED": "CLOSE", "RFI": "RFI", "REQUESTFORINFORMATION": "RFI",
                 "REQUESTINFORMATION": "RFI", "ESCALATE": "ESCALATE", "ESCALATED": "ESCALATE",
                 "ESCALATION": "ESCALATE", "ESC": "ESCALATE"}


class DropError(Exception):
    pass


def jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------- unpacking

def archive_stem(path):
    name = os.path.basename(path.rstrip("/\\"))
    low = name.lower()
    for ext in sorted(ARCHIVES, key=len, reverse=True):
        if low.endswith(ext):
            return name[: -len(ext)] or "drop"
    return os.path.splitext(name)[0] or name


def is_archive(path):
    if not os.path.isfile(path):
        return False
    if path.lower().endswith(ARCHIVES) or zipfile.is_zipfile(path):
        return True
    try:
        return tarfile.is_tarfile(path)
    except (OSError, tarfile.TarError):
        return False


def _member_ok(name):
    name = name.replace("\\", "/")
    return not (name.startswith("/") or re.match(r"[A-Za-z]:", name) or ".." in name.split("/"))


def unpack(archive, dest):
    """Unpack one zip or tar into dest. Refuses any member whose path would leave dest, and skips links."""
    os.makedirs(dest, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            bad = [i.filename for i in infos if not _member_ok(i.filename)]
            if bad:
                raise DropError("%s has paths that leave the folder, e.g. %r" % (archive, bad[0]))
            if sum(i.file_size for i in infos) > MAX_UNPACKED:
                raise DropError("%s would unpack to more than 8 GB" % archive)
            for info in infos:
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue
                zf.extract(info, dest)
        return
    try:
        with tarfile.open(archive) as tf:
            members = tf.getmembers()
            bad = [m.name for m in members if not _member_ok(m.name)]
            if bad:
                raise DropError("%s has paths that leave the folder, e.g. %r" % (archive, bad[0]))
            members = [m for m in members if m.isfile() or m.isdir()]
            if sum(m.size for m in members) > MAX_UNPACKED:
                raise DropError("%s would unpack to more than 8 GB" % archive)
            if hasattr(tarfile, "data_filter"):
                tf.extractall(dest, members=members, filter="data")
            else:
                tf.extractall(dest, members=members)
    except tarfile.TarError as exc:
        raise DropError("%s is not a zip or tar file I can read (%s)" % (archive, exc))


def _walk(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                         and not d.endswith("-answers"))
        yield base, dirs, sorted(f for f in files if not f.startswith("._"))


def unpack_nested(root, into, notes, depth=3):
    """Unpack archives found under root into the folder `into`, then the ones those contain, a few levels deep."""
    seen = set()
    search = [root]
    for _ in range(depth):
        found = [os.path.join(base, f) for r in search for base, _, files in _walk(r)
                 for f in files if f.lower().endswith(ARCHIVES)]
        found = [p for p in found if p not in seen]
        if not found:
            return
        search = []
        for path in found:
            seen.add(path)
            # one numbered slot per archive, so a flat bank.zip still unpacks into a folder called bank
            target = os.path.join(into, str(len(seen)), archive_stem(path))
            try:
                unpack(path, target)
                search.append(target)
            except (DropError, OSError, zipfile.BadZipFile) as exc:
                notes.append("skipped %s: %s" % (os.path.relpath(path, root), exc))


def find_institutions(roots):
    found, seen = [], set()
    for root in roots:
        for base, _, files in _walk(root):
            key = os.path.normcase(os.path.realpath(base))
            if "cases.jsonl" in files and key not in seen:
                seen.add(key)
                found.append((root, base))
    return found


def name_folders(found, fallback):
    """A short, unique name per institution folder: its own name, or more of its path when two clash."""
    names = []
    for root, base in found:
        names.append(fallback if os.path.normpath(base) == os.path.normpath(root) else os.path.basename(base))
    for i, name in enumerate(names):
        if names.count(name) > 1:
            root, base = found[i]
            rel = os.path.relpath(base, root)
            names[i] = re.sub(r"[\\/]+", "-", rel if rel != "." else fallback)
    return names


# ---------------------------------------------------------------- running and checking

def run_system(folder, out_path, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    start = time.time()
    proc = subprocess.run([sys.executable, RUN, folder, out_path], cwd=SYSTEM, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stderr.decode("utf-8", "replace").strip(), time.time() - start


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def check_output(folder, out_path):
    """What a grader would count against the output: missing or extra lines, wrong fields,
    codes outside their verdict, and cited IDs that are not in the case's own files."""
    cases = jsonl(os.path.join(folder, "cases.jsonl"))
    rows = jsonl(out_path)
    docs_of, tx_of = {}, {}
    for e in jsonl(os.path.join(folder, "evidence.jsonl")):
        docs_of.setdefault(e.get("customer_id"), set()).add(e.get("doc_id"))
    for t in jsonl(os.path.join(folder, "transactions.jsonl")):
        tx_of.setdefault(t.get("customer_id"), set()).add(t.get("transaction_id"))
    list_ids = set(e.get("entry_id") for e in jsonl(os.path.join(folder, "internal_list.jsonl")))
    by_id = {}
    for r in rows:
        by_id.setdefault(r.get("case_id"), []).append(r)
    problems, counts = [], {}
    for c in cases:
        got = by_id.get(c.get("case_id"), [])
        if len(got) != 1:
            problems.append("%s has %d output lines" % (c.get("case_id"), len(got)))
            continue
        r = got[0]
        counts[r.get("verdict")] = counts.get(r.get("verdict"), 0) + 1
        if list(r.keys()) != FIELDS:
            problems.append("%s has fields %s" % (c.get("case_id"), list(r.keys())))
        if r.get("alert_ids") != c.get("alert_ids"):
            problems.append("%s lists different alert IDs from the case" % c.get("case_id"))
        if r.get("reason_code") not in CODES.get(r.get("verdict"), ()):
            problems.append("%s: %s does not belong to %s" % (c.get("case_id"), r.get("reason_code"), r.get("verdict")))
        known = docs_of.get(c.get("customer_id"), set()) | tx_of.get(c.get("customer_id"), set()) | list_ids
        unknown = [e for e in r.get("evidence") or [] if e not in known]
        if unknown:
            problems.append("%s cites %s, not in the case's files" % (c.get("case_id"), ", ".join(unknown[:3])))
        if not r.get("evidence"):
            problems.append("%s cites no evidence" % c.get("case_id"))
    extra = set(by_id) - set(c.get("case_id") for c in cases)
    if extra:
        problems.append("%d output lines for cases not in cases.jsonl" % len(extra))
    return cases, rows, problems, counts


# ---------------------------------------------------------------- labels and scoring

def _norm_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _verdict(value):
    if not isinstance(value, str):
        return None
    return VERDICT_WORDS.get(re.sub(r"[^A-Z]", "", value.upper()))


def _verdict_and_code(keys):
    verdict = code = None
    for k in VERDICT_KEYS:
        value = keys.get(k)
        if isinstance(value, dict):
            verdict, code = _verdict_and_code({_norm_key(a): b for a, b in value.items()})
            if verdict:
                break
        elif _verdict(value):
            verdict = _verdict(value)
            break
    # with the verdict sent also present, a bare reason_code is the one sent, not the right one
    both = "verdict" in keys and any(k in keys for k in RIGHT_VERDICT_KEYS)
    if code is None:
        for k in (RIGHT_CODE_KEYS if both else CODE_KEYS):
            value = keys.get(k)
            if isinstance(value, str) and value.strip():
                code = value.strip().upper()
                break
    if verdict is None and code in VERDICT_OF_CODE:
        verdict = VERDICT_OF_CODE[code]
    return verdict, code


def label_of(record):
    """(case_id, verdict, reason_code or None) from one record, whatever its key spellings; None if it has no verdict."""
    if not isinstance(record, dict):
        return None
    keys = {_norm_key(k): v for k, v in record.items()}
    case = next((str(keys[k]).strip() for k in CASE_KEYS if isinstance(keys.get(k), (str, int))), None)
    verdict, code = _verdict_and_code(keys)
    return (case, verdict, code) if case and verdict else None


def read_records(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    low = path.lower()
    if low.endswith((".csv", ".tsv")):
        tabbed = low.endswith(".tsv") or text.count("\t") > text.count(",")
        return list(csv.DictReader(io.StringIO(text), dialect="excel-tab" if tabbed else "excel"))
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        if label_of(data):
            return [data]
        for k in ("cases", "labels", "answers", "results", "data", "items", "records"):
            if isinstance(data.get(k), list):
                return data[k]
        return [dict(v, case_id=v.get("case_id", k)) if isinstance(v, dict) else {"case_id": k, "verdict": v}
                for k, v in data.items()]
    return data if isinstance(data, list) else []


def load_labels(paths, notes=None):
    """{case_id: (verdict, reason_code, source file)} from every readable label file given."""
    notes = notes if notes is not None else []
    labels = {}
    for path in paths:
        files = [os.path.join(b, f) for b, _, fs in os.walk(path) for f in sorted(fs)
                 if f.lower().endswith(TABLES)] if os.path.isdir(path) else [path]
        for f in files:
            try:
                records = read_records(f)
            except (OSError, ValueError, csv.Error) as exc:
                notes.append("could not read %s as labels: %s" % (f, exc))
                continue
            got = clash = 0
            for rec in records:
                lab = label_of(rec)
                if not lab:
                    continue
                case, verdict, code = lab
                if case in labels and labels[case][:2] != (verdict, code):
                    clash += 1
                    continue
                labels.setdefault(case, (verdict, code, f))
                got += 1
            shown = os.path.join(os.path.basename(os.path.dirname(f)), os.path.basename(f))
            notes.append("%s: %d label(s) read from %d record(s)%s" % (
                shown, got, len(records), ", %d clashed with an earlier file and were ignored" % clash if clash else ""))
    return labels


def tally(case_ids, labels, sent):
    """Score the verdicts sent for the labelled cases among case_ids. sent: {case_id: (verdict, reason_code)}."""
    confusion = {r: {c: 0 for c in VERDICTS} for r in VERDICTS}
    n = cost = base = right = wrongful = closable = closed = codes_known = codes_right = missing = 0
    mistakes = []
    for cid in case_ids:
        if cid not in labels:
            continue
        truth, truth_code = labels[cid][0], labels[cid][1]
        got, got_code = sent.get(cid, (None, None))
        if got not in VERDICTS:
            missing += 1
            got, got_code = "ESCALATE", None
        n += 1
        confusion[truth][got] += 1
        c = COST[truth][got]
        cost += c
        base += COST[truth]["ESCALATE"]
        if truth == "CLOSE":
            closable += 1
            closed += got == "CLOSE"
        elif got == "CLOSE":
            wrongful += 1
        if got == truth:
            right += 1
            if truth_code:
                codes_known += 1
                codes_right += got_code == truth_code
        if got != truth or (truth_code and got_code != truth_code):
            mistakes.append({"case_id": cid, "right_verdict": truth, "right_reason_code": truth_code,
                             "sent_verdict": got, "sent_reason_code": got_code, "cost": c})
    return {
        "labelled": n, "verdicts_right": right, "wrongful_closes": wrongful,
        "closable": closable, "closable_closed": closed, "cost": cost,
        "cost_per_case": round(cost / n, 4) if n else None, "escalate_all_cost": base,
        "verdict_score": round(1 - cost / base, 4) if base else None,
        "reason_codes_labelled": codes_known, "reason_codes_right": codes_right,
        "missing_lines": missing, "confusion": confusion, "mistakes": mistakes,
    }


def score(labels_path, output_path):
    """Score one output file against one labels file or folder. Every labelled case counts;
    a labelled case with no output line counts as ESCALATE."""
    labels = load_labels([labels_path])
    sent = {r.get("case_id"): (r.get("verdict"), r.get("reason_code")) for r in jsonl(output_path)}
    return tally(sorted(labels), labels, sent)


def find_label_files(roots):
    found = []
    for root in roots:
        for base, _, files in _walk(root):
            for f in files:
                if f in KIT_FILES or not f.lower().endswith(TABLES):
                    continue
                if LABEL_NAME.search(f) or LABEL_NAME.search(os.path.basename(base)):
                    found.append(os.path.join(base, f))
    return found


# ---------------------------------------------------------------- report

def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "n/a"


def print_score(title, s):
    print("  %s: %d labelled case(s)" % (title, s["labelled"]))
    if not s["labelled"]:
        return
    print("    wrongful closes        %d" % s["wrongful_closes"])
    print("    closable cases closed  %d of %d (%s)" % (s["closable_closed"], s["closable"], pct(s["closable_closed"], s["closable"])))
    print("    verdicts right         %d of %d (%s)" % (s["verdicts_right"], s["labelled"], pct(s["verdicts_right"], s["labelled"])))
    print("    cost                   %d, %.3f a case (escalating everything would cost %d)"
          % (s["cost"], s["cost_per_case"], s["escalate_all_cost"]))
    if s["verdict_score"] is not None:
        print("    verdict score          %.1f%% of the escalate-everything cost saved" % (100 * s["verdict_score"]))
    if s["reason_codes_labelled"]:
        print("    reason codes right     %d of %d right verdicts that carry a labelled code"
              % (s["reason_codes_right"], s["reason_codes_labelled"]))
    if s["missing_lines"]:
        print("    missing lines          %d, counted as ESCALATE" % s["missing_lines"])
    print("    right verdict -> sent   CLOSE    RFI  ESCALATE")
    for r in VERDICTS:
        print("      %-21s %6d %6d %9d" % (r, s["confusion"][r]["CLOSE"], s["confusion"][r]["RFI"], s["confusion"][r]["ESCALATE"]))


def handle(inp, args, single):
    path = os.path.abspath(inp)
    if not os.path.exists(path):
        print("!! %s does not exist" % inp)
        return 1
    stem = archive_stem(path) if os.path.isfile(path) else os.path.basename(path.rstrip("/\\"))
    if args.out:
        out_dir = os.path.abspath(args.out if single else os.path.join(args.out, stem))
    else:
        out_dir = os.path.join(os.path.dirname(path.rstrip("/\\")), stem + "-answers")
    for protected in (SYSTEM, DEV_OUTPUT):
        try:
            inside = os.path.normcase(os.path.commonpath([out_dir, protected])) == os.path.normcase(protected)
        except ValueError:  # different drives
            inside = False
        if inside:
            print("!! refusing to write answers inside %s" % protected)
            return 1
    print("== %s" % inp)
    notes = []
    tmp = tempfile.mkdtemp(prefix="drop-")
    try:
        if os.path.isfile(path):
            if not is_archive(path):
                print("!! %s is a file but not a zip or tar" % inp)
                return 1
            root = os.path.join(tmp, "top", stem)
            unpack(path, root)
        else:
            root = path
        inner = os.path.join(tmp, "inner")  # archives found inside the drop unpack here
        unpack_nested(root, inner, notes)
        roots = [r for r in (root, inner) if os.path.isdir(r)]
        found = find_institutions(roots)
        if not found:
            print("!! no folder holding cases.jsonl. Files found:")
            listed = [os.path.relpath(os.path.join(b, f), r) for r in roots for b, _, fs in _walk(r) for f in fs]
            for f in listed[:25]:
                print("     " + f)
            if len(listed) > 25:
                print("     ... and %d more" % (len(listed) - 25))
            for n in notes:
                print("   " + n)
            return 1
        names = name_folders(found, stem)
        os.makedirs(out_dir, exist_ok=True)
        stale = os.path.join(out_dir, "mistakes.jsonl")
        if os.path.exists(stale):
            os.remove(stale)

        label_paths = [os.path.abspath(p) for p in args.labels] or find_label_files(roots)
        labels = load_labels(label_paths, notes) if label_paths else {}

        status, summary, all_ids, sent = 0, {"input": path, "runs": args.runs, "institutions": []}, [], {}
        for (root, folder), name in zip(found, names):
            out = os.path.join(out_dir, name + ".jsonl")
            code, err, secs = run_system(folder, out)
            missing_files = [f for f in KIT_FILES if not os.path.exists(os.path.join(folder, f))]
            entry = {"name": name, "folder": os.path.relpath(folder, root), "answers": out,
                     "exit_code": code, "stderr": err, "seconds": round(secs, 2), "missing_files": missing_files}
            summary["institutions"].append(entry)
            if code != 0:
                status = 1
                print("  %-12s run FAILED (exit %d): %s" % (name, code, err[-300:]))
                continue
            hashes = {sha256(out)}
            for k in range(1, args.runs):
                again = os.path.join(tmp, "%s.run%d.jsonl" % (name, k))
                run_system(folder, again, seed=str(1000 + 7 * k))
                hashes.add(sha256(again) if os.path.exists(again) else "missing")
            cases, rows, problems, counts = check_output(folder, out)
            entry.update({"cases": len(cases), "verdicts": counts, "identical_runs": len(hashes) == 1,
                          "sha256": sha256(out), "problems": problems})
            if problems or len(hashes) != 1:
                status = 1
            print("  %-12s %5d cases   %s   %s   %.1fs a run   %s" % (
                name, len(cases), "  ".join("%s %d" % (v, counts.get(v, 0)) for v in VERDICTS),
                ("%d runs identical" % args.runs if args.runs > 1 else "1 run") if len(hashes) == 1 else "RUNS DIFFER",
                secs, "checks ok" if not problems else "%d PROBLEM(S)" % len(problems)))
            for p in problems[:5]:
                print("               - " + p)
            if missing_files:
                print("               missing from the folder (read as empty): %s" % ", ".join(missing_files))
            ids = [c.get("case_id") for c in cases]
            all_ids += ids
            here = {r.get("case_id"): (r.get("verdict"), r.get("reason_code")) for r in rows}
            sent.update(here)
            if labels:
                entry["score"] = {k: v for k, v in tally(ids, labels, here).items() if k != "mistakes"}

        for n in notes:
            print("  " + n)
        if not label_paths:
            print("  no labels found, so no accuracy figure. Pass the right answers with --labels FILE.")
        elif labels:
            print("  labels from: %s" % ", ".join(sorted(set(os.path.basename(v[2]) for v in labels.values()))))
            for entry in summary["institutions"]:
                if entry.get("score", {}).get("labelled"):
                    print_score(entry["name"], entry["score"])
            total = tally(all_ids, labels, sent)
            unmatched = len(set(labels) - set(all_ids))
            summary["score"] = {k: v for k, v in total.items() if k != "mistakes"}
            if sum(1 for e in summary["institutions"] if e.get("score", {}).get("labelled")) > 1:
                print_score("all institutions", total)
            if unmatched:
                print("  %d label(s) name cases that are not in this drop and were left out" % unmatched)
            if total["labelled"] and not total["mistakes"]:
                print("  !! every labelled case matches the system's answer exactly. Check the labels are not a"
                      " copy of a system output before quoting this.")
            with open(os.path.join(out_dir, "mistakes.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
                for m in total["mistakes"]:
                    fh.write(json.dumps(m, ensure_ascii=False) + "\n")
        else:
            print("  label files were found but no record had a case ID and a verdict, so no accuracy figure.")
        summary["notes"] = notes
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("  answers in %s" % out_dir)
        return status
    except (DropError, zipfile.BadZipFile, OSError) as exc:
        print("!! %s" % exc)
        return 1
    finally:
        if args.keep:
            print("  unpacked copy kept in %s" % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Run the system on a drop of test data and score it if labels come with it.")
    ap.add_argument("inputs", nargs="+", help="zip, tar or folder of institution folders, in any layout")
    ap.add_argument("--labels", action="append", default=[], help="file or folder of right answers (repeatable)")
    ap.add_argument("--out", help="where to write the answers (default: <input>-answers next to the input)")
    ap.add_argument("--runs", type=int, default=2, help="runs per institution to compare byte for byte (default 2)")
    ap.add_argument("--keep", action="store_true", help="keep the unpacked copy and print where it is")
    args = ap.parse_args(argv)
    args.runs = max(1, args.runs)
    status = 0
    for inp in args.inputs:
        status |= handle(inp, args, single=len(args.inputs) == 1)
    return status


if __name__ == "__main__":
    sys.exit(main())
