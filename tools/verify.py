"""Prove the system is fit to submit.

    python tools/verify.py <path to institutions>

Checks, for all four institutions:
  1. five runs under five different hash seeds give byte-identical output;
  2. the system is run from inside system/ with full paths, as the organisers do;
  3. every case has exactly one line, the reason code belongs to the verdict,
     and every cited ID exists in that case's own files;
  4. nothing from the development cases (names, IDs) appears in the system's code;
  5. how long a run takes.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = os.path.abspath(os.path.join(HERE, "..", "system"))
ROOT = os.path.abspath(sys.argv[1])
INSTITUTIONS = ["bank", "emoney", "investment", "payments_fx"]
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
failures = []


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def fail(msg):
    failures.append(msg)
    print("  FAIL " + msg)


tmp = tempfile.mkdtemp(prefix="triage-verify-")
dev_tokens = set()
for inst in INSTITUTIONS:
    folder = os.path.join(ROOT, inst)
    print("== %s" % inst)
    hashes, seconds = set(), []
    for seed in ("0", "1", "42", "2026", "987654"):
        out = os.path.join(tmp, "%s_%s.jsonl" % (inst, seed))
        env = dict(os.environ, PYTHONHASHSEED=seed)
        start = time.time()
        proc = subprocess.run([sys.executable, os.path.join(SYSTEM, "run"), folder, out], cwd=SYSTEM, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        seconds.append(time.time() - start)
        if proc.returncode != 0:
            fail("run exited %d: %s" % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-300:]))
            continue
        with open(out, "rb") as fh:
            hashes.add(hashlib.sha256(fh.read()).hexdigest())
    print("  five runs, %d distinct output file(s), %.1fs per run of %d cases"
          % (len(hashes), sum(seconds) / len(seconds), len(jsonl(os.path.join(folder, "cases.jsonl")))))
    if len(hashes) != 1:
        fail("outputs differ between runs")

    cases = jsonl(os.path.join(folder, "cases.jsonl"))
    rows = jsonl(os.path.join(tmp, "%s_0.jsonl" % inst))
    docs_of, tx_of = {}, {}
    for e in jsonl(os.path.join(folder, "evidence.jsonl")):
        docs_of.setdefault(e["customer_id"], set()).add(e["doc_id"])
    for t in jsonl(os.path.join(folder, "transactions.jsonl")):
        tx_of.setdefault(t["customer_id"], set()).add(t["transaction_id"])
    list_ids = set(e["entry_id"] for e in jsonl(os.path.join(folder, "internal_list.jsonl")))
    by_id = {}
    for r in rows:
        by_id.setdefault(r.get("case_id"), []).append(r)
    counts = {}
    for c in cases:
        got = by_id.get(c["case_id"], [])
        if len(got) != 1:
            fail("%s has %d lines" % (c["case_id"], len(got)))
            continue
        r = got[0]
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        if list(r.keys()) != ["case_id", "alert_ids", "verdict", "reason_code", "reason", "evidence"]:
            fail("%s has the wrong fields" % c["case_id"])
        if r["alert_ids"] != c["alert_ids"]:
            fail("%s alert_ids differ" % c["case_id"])
        if r["reason_code"] not in CODES.get(r["verdict"], set()):
            fail("%s: code %s does not belong to %s" % (c["case_id"], r["reason_code"], r["verdict"]))
        known = docs_of.get(c["customer_id"], set()) | tx_of.get(c["customer_id"], set()) | list_ids
        for e in r["evidence"]:
            if e not in known:
                fail("%s cites %s, which is not in the case's files" % (c["case_id"], e))
        if not r["evidence"]:
            fail("%s cites no evidence" % c["case_id"])
        # count sentence ends strictly: any full stop followed by a new sentence, except "INV. NO. 123"
        text = re.sub(r"\b(INV|Inv|NO|No|REF|Ref)\.", r"\1", r["reason"])
        sentences = len(re.findall(r"[.!?][\"')]?(?:\s+(?=[A-Z\"£0-9])|\s*$)", text))
        if not 2 <= sentences <= 4:
            fail("%s reason has %d sentences" % (c["case_id"], sentences))
    print("  %d lines for %d cases: %s" % (len(rows), len(cases), ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    published = os.path.join(SYSTEM, "..", "output", "%s.jsonl" % inst)
    if os.path.exists(published):
        same = open(published, "rb").read() == open(os.path.join(tmp, "%s_0.jsonl" % inst), "rb").read()
        print("  output/%s.jsonl %s what the system produces now" % (inst, "matches" if same else "DOES NOT match"))
        if not same:
            fail("output/%s.jsonl is stale" % inst)

    for c in jsonl(os.path.join(folder, "customers.jsonl")):
        dev_tokens.add(c["name"])
        dev_tokens.add(c["customer_id"])
    for c in cases:
        dev_tokens.add(c["case_id"])
    for e in jsonl(os.path.join(folder, "evidence.jsonl")):
        dev_tokens.add(e["doc_id"])
    for e in jsonl(os.path.join(folder, "internal_list.jsonl")):
        dev_tokens.add(e["name"])
        dev_tokens.add(e["entry_id"])
    for t in jsonl(os.path.join(folder, "transactions.jsonl")):
        if t.get("counterparty_name"):
            dev_tokens.add(t["counterparty_name"])

print("== nothing from the development cases in system/")
code = ""
for base, _, files in os.walk(SYSTEM):
    if "__pycache__" in base:
        continue
    for name in sorted(files):
        with open(os.path.join(base, name), encoding="utf-8", errors="replace") as fh:
            code += "\n" + fh.read()
leaks = sorted(tok for tok in dev_tokens if tok and len(tok) > 5 and tok in code
               and re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(tok), code))
if leaks:
    fail("development tokens in system/: %s" % ", ".join(leaks[:10]))
else:
    print("  checked %d names and IDs: none found" % len(dev_tokens))

print("\n%s" % ("ALL CHECKS PASSED" if not failures else "%d CHECK(S) FAILED" % len(failures)))
sys.exit(1 if failures else 0)
