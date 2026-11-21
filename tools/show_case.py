"""Print everything an analyst would read for one case, and nothing the system decided.

    python tools/show_case.py <institutions folder> <case_id> [<case_id> ...]

Shows the case line, its alerts, the customer record, the customer's
transactions (alerted ones marked *, the held payment marked H, those outside
the review window marked .), the full text of every evidence document on file
for the customer, earlier reviews, and any internal-list entries the alerts
name.

It reads the kit's files directly and imports nothing from system/, so a blind
reader sees the evidence and the policy, never a verdict from this system.
Earlier reviews are part of the kit and are shown as the analyst would see them.
"""
import json
import os
import sys

PREFIX = {"BK": "bank", "EM": "emoney", "IV": "investment", "PX": "payments_fx"}


def jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def find_institution(root, case_id):
    guess = PREFIX.get(case_id.split("-")[0])
    names = [guess] if guess else []
    names += [n for n in sorted(os.listdir(root)) if n != guess]
    for name in names:
        folder = os.path.join(root, name)
        for row in jsonl(os.path.join(folder, "cases.jsonl")):
            if row.get("case_id") == case_id:
                return folder, row
    return None, None


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def show(root, case_id, out):
    folder, case = find_institution(root, case_id)
    if not case:
        out.write("case %s not found under %s\n" % (case_id, root))
        return 1
    cust_id = case.get("customer_id")
    alert_ids = list(case.get("alert_ids") or [])
    w = case.get("review_window") or {}
    lo, hi = w.get("from") or "", w.get("to") or ""

    alerts = {a.get("alert_id"): a for a in jsonl(os.path.join(folder, "alerts.jsonl"))}
    customers = {c.get("customer_id"): c for c in jsonl(os.path.join(folder, "customers.jsonl"))}
    txs = [t for t in jsonl(os.path.join(folder, "transactions.jsonl")) if t.get("customer_id") == cust_id]
    txs.sort(key=lambda t: (t.get("booked_at") or "", t.get("transaction_id") or ""))
    docs = [d for d in jsonl(os.path.join(folder, "evidence.jsonl")) if d.get("customer_id") == cust_id]
    docs.sort(key=lambda d: (d.get("dated") or "", d.get("doc_id") or ""))
    reviews = [r for r in jsonl(os.path.join(folder, "previous_reviews.jsonl")) if r.get("customer_id") == cust_id]
    entries = {e.get("entry_id"): e for e in jsonl(os.path.join(folder, "internal_list.jsonl"))}

    p = out.write
    p("=" * 78 + "\nCASE %s  (institution: %s)\n" % (case_id, os.path.basename(folder)) + "=" * 78 + "\n")
    p(dump(case) + "\n")

    alerted, named = set(), []
    p("\n## ALERTS\n")
    for aid in alert_ids:
        a = alerts.get(aid)
        if not a:
            p("\n%s: not found in alerts.jsonl\n" % aid)
            continue
        alerted.update(a.get("transaction_ids") or [])
        entry = (a.get("measured") or {}).get("list_entry")
        if entry and entry not in named:
            named.append(entry)
        p("\n" + dump(a) + "\n")

    p("\n## CUSTOMER\n")
    p(dump(customers.get(cust_id, {"missing": cust_id})) + "\n")

    held = case.get("held_payment_id")
    p("\n## TRANSACTIONS (%d)   * alerted   H held payment   . outside review window %s to %s\n" % (len(txs), lo, hi))
    p("   %-14s %-16s %-4s %-14s %12s  %-30s %-14s %s\n" % (
        "id", "booked", "dir", "channel", "amount_gbp", "counterparty", "country", "reference / other"))
    for t in txs:
        day = (t.get("booked_at") or "")[:10]
        mark = ("*" if t.get("transaction_id") in alerted else " ") + ("H" if t.get("transaction_id") == held else " ")
        if lo and hi and not (lo <= day <= hi):
            mark = mark[0] + (mark[1] if mark[1] != " " else ".")
        extra = [str(t.get("reference") or "")]
        if t.get("counterparty_account"):
            extra.append("acct=%s" % t["counterparty_account"])
        if t.get("location"):
            extra.append("loc=%s" % t["location"])
        if t.get("currency") and t.get("currency") != "GBP":
            extra.append("%s %s" % (t.get("amount"), t.get("currency")))
        known = {"transaction_id", "customer_id", "account_id", "booked_at", "direction", "channel", "amount_gbp",
                 "counterparty_name", "counterparty_account", "counterparty_country", "reference", "location",
                 "currency", "amount"}
        for k in sorted(set(t) - known):
            extra.append("%s=%s" % (k, t[k]))
        p("%s %-14s %-16s %-4s %-14s %12s  %-30s %-14s %s\n" % (
            mark, t.get("transaction_id"), (t.get("booked_at") or "")[:16].replace("T", " "), t.get("direction"),
            t.get("channel"), "%.2f" % float(t.get("amount_gbp") or 0), (t.get("counterparty_name") or "")[:30],
            (t.get("counterparty_country") or "")[:14], "  ".join(e for e in extra if e)))

    p("\n## EVIDENCE DOCUMENTS (%d)\n" % len(docs))
    for d in docs:
        p("\n" + "-" * 78 + "\n%s | %s | %s | dated %s\n" % (d.get("doc_id"), d.get("type"), d.get("title"), d.get("dated")) + "-" * 78 + "\n")
        path = os.path.join(folder, d.get("file") or "")
        p((read(path) if os.path.isfile(path) else "(file %s not found)" % d.get("file")).rstrip() + "\n")

    p("\n## EARLIER REVIEWS (%d)\n" % len(reviews))
    for r in sorted(reviews, key=lambda r: r.get("reviewed_on") or ""):
        p(dump(r) + "\n")

    p("\n## INTERNAL-LIST ENTRIES NAMED BY THE ALERTS (%d)\n" % len(named))
    for e in named:
        p(dump(entries.get(e, {"missing": e})) + "\n")
    p("\n")
    return 0


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    rc = 0
    for cid in argv[2:]:
        rc |= show(argv[1], cid, sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
