"""Near-miss evidence: change one small fact in the documents a CLOSE relied on.

    python tools/near_miss_test.py <institutions folder> [--only bank,emoney] [--out DIR]

stress.py's destroy test makes large changes (drop the document, add £100,
swap the names). These make the smallest change that still breaks the match,
which is what a careless or forged document looks like:

  amount+1.00    every alerted amount in the cited documents is £1.00 higher
  amount+0.01    the same, one penny higher (reported, not pass/fail: a
                 reviewer might accept a penny)
  payee typo     the alerted counterparty's name is misspelled in the cited
                 documents (two letters of its longest word swapped,
                 wherever the full name appears)
  customer typo  the customer's own name is misspelled the same way

For the first and the two typo checks, a case that still closes is a near miss
the system accepted. A list-match close (LIST_MATCH_DIFFERENT_PARTY) rests on
who controls the counterparty, not on the amount, so amount changes on those
are reported but not failed. Each check builds one copy of the institution folder with
every CLOSE case's cited documents changed (each case has its own customer, so
cases do not affect each other), then runs system/run once on the copy.

Generated folders hold development data, so they live in a temporary
directory, and --out (for the list of cases that still closed) must be
outside the repository.
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
RUN = os.path.join(REPO, "system", "run")
INSTITUTIONS = ("bank", "emoney", "investment", "payments_fx")


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def run(folder, out):
    subprocess.run([sys.executable, RUN, folder, out], check=True, capture_output=True)
    return {d["case_id"]: d for d in jsonl(out)}


def money(x):
    return "{:,.2f}".format(x)


def typo(name):
    """Swap two letters in the middle of the name's longest word: 'Hollhurst' -> 'Holhlurst'."""
    words = [w for w in re.findall(r"[A-Za-z]+", name or "") if len(w) >= 5]
    if not words:
        return None
    w = max(words, key=len)
    i = len(w) // 2
    if w[i] == w[i - 1]:
        i += 1
        if i >= len(w) or w[i] == w[i - 1]:
            return None
    t = w[:i - 1] + w[i] + w[i - 1] + w[i + 1:]
    return (w, t)


def plan(folder, base):
    """For each CLOSE: its cited document files, alerted amounts, counterparties and customer name."""
    cases = {c["case_id"]: c for c in jsonl(os.path.join(folder, "cases.jsonl"))}
    alerts = {a["alert_id"]: a for a in jsonl(os.path.join(folder, "alerts.jsonl"))}
    tx = {t["transaction_id"]: t for t in jsonl(os.path.join(folder, "transactions.jsonl"))}
    customers = {c["customer_id"]: c for c in jsonl(os.path.join(folder, "customers.jsonl"))}
    meta = {e["doc_id"]: e for e in jsonl(os.path.join(folder, "evidence.jsonl"))}
    out = {}
    for cid, d in base.items():
        if d["verdict"] != "CLOSE":
            continue
        case = cases[cid]
        cust = customers.get(case["customer_id"], {})
        files = [meta[e]["file"] for e in d["evidence"]
                 if e in meta and meta[e].get("customer_id") == case["customer_id"] and meta[e].get("file")]
        txs = [tx[t] for a in case.get("alert_ids") or [] for t in (alerts.get(a, {}).get("transaction_ids") or [])
               if t in tx]
        parties = sorted(set(t.get("counterparty_name") or "" for t in txs) - {"", cust.get("name") or ""})
        out[cid] = {"files": files, "amounts": sorted(set(t["amount_gbp"] for t in txs)),
                    "parties": parties, "customer": cust.get("name") or "", "code": d["reason_code"]}
    return out


def mutate(folder, files, fn):
    """Apply fn to each file's text; True if any file changed."""
    changed = False
    for f in files:
        p = os.path.join(folder, f)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        new = fn(text)
        if new != text:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)
            changed = True
    return changed


def amount_shift(delta):
    def make(c):
        def fn(text):
            for a in c["amounts"]:
                text = re.sub(r"(?<![\d,.])%s(?![\d])" % re.escape(money(a)), money(round(a + delta, 2)), text)
            return text
        return fn
    return make


def name_typo(key):
    def make(c):
        names = c["parties"] if key == "parties" else [c["customer"]]
        # misspell the full name where it appears, so a first name shared with someone else is left alone
        swaps = [(n, n.replace(s[0], s[1], 1)) for n, s in ((n, typo(n)) for n in names if n) if s]

        def fn(text):
            for full, wrong in swaps:
                text = re.sub(r"\b%s\b" % re.escape(full), wrong, text)
            return text
        return fn
    return make


CHECKS = [
    ("amount+1.00", True, amount_shift(1.00)),
    ("amount+0.01", False, amount_shift(0.01)),
    ("payee typo", True, name_typo("parties")),
    ("customer typo", True, name_typo("customer")),
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--only", default=",".join(INSTITUTIONS))
    ap.add_argument("--out", default=None, help="folder for still_closing.jsonl (outside the repository)")
    a = ap.parse_args(argv)
    if a.out and os.path.abspath(a.out).startswith(REPO + os.sep):
        sys.stderr.write("refusing to write inside the repository: it is public and this is development data\n")
        return 2
    tmp = tempfile.mkdtemp(prefix="nearmiss-")
    failures, report = 0, []
    try:
        print("%-12s %-14s %8s %8s %8s %6s   %s" % ("institution", "change", "applied", "stopped", "closed", "fail",
                                                  "still closing (code: n)"))
        for name in a.only.split(","):
            src = os.path.join(os.path.abspath(a.folder), name)
            base = run(src, os.path.join(tmp, name + "-base.jsonl"))
            todo = plan(src, base)
            for label, strict, make in CHECKS:
                folder = os.path.join(tmp, "%s-%s" % (name, re.sub(r"\W", "", label)))
                shutil.rmtree(folder, ignore_errors=True)
                shutil.copytree(src, folder)
                applied = [cid for cid, c in sorted(todo.items()) if mutate(folder, c["files"], make(c))]
                got = run(folder, os.path.join(tmp, "out.jsonl"))
                still = [cid for cid in applied if got[cid]["verdict"] == "CLOSE"]
                by_code = collections.Counter(todo[cid]["code"] for cid in still)
                counted = [cid for cid in still if strict and not (
                    label.startswith("amount") and todo[cid]["code"] == "LIST_MATCH_DIFFERENT_PARTY")]
                print("%-12s %-14s %8d %8d %8d %6d   %s" % (
                    name, label, len(applied), len(applied) - len(still), len(still), len(counted),
                    ", ".join("%s: %d" % kv for kv in by_code.most_common()) or "-"))
                failures += len(counted)
                for cid in still:
                    report.append({"institution": name, "change": label, "case_id": cid, "strict": cid in counted,
                                   "reason_code": got[cid]["reason_code"], "reason": got[cid]["reason"]})
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, "still_closing.jsonl"), "w", encoding="utf-8") as fh:
                for r in report:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            print("\ncases that still closed: %s" % os.path.join(a.out, "still_closing.jsonl"))
        print("\n%d near misses still closed that should not have" % failures)
        return 1 if failures else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
