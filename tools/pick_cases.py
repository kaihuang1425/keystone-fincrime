"""Pick development cases for a blind second reading, the same ones every time.

    python tools/pick_cases.py <institutions folder> [--n 40] [--out ../labels/candidates.csv]

Takes n/4 cases per institution, in this order of priority:
  1. cases from groups that tools/report.py marks !! (cases with the same rules
     and documents that received different verdicts or codes), one per
     different answer in the group;
  2. cases the system closed, spread across as many reason codes as possible;
  3. two RFI and two ESCALATE cases.
Ties are broken by a sha256 of the case ID, so the choice is fixed but spread out.

The file holds case_id and institution only. It holds no verdicts, so it can be
handed to a blind reader. It belongs outside the repository, with other labels.
"""
import argparse
import collections
import csv
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "system"))
from triage.loader import Institution  # noqa: E402
from triage.decide import safe_decide  # noqa: E402

INSTITUTIONS = ("bank", "emoney", "investment", "payments_fx")


def h(cid):
    return hashlib.sha256(cid.encode()).hexdigest()


def pick(inst, k):
    results = []
    for row in inst.cases:
        r = safe_decide(inst, row)
        t = r.get("_trace") or {}
        group = ("+".join(t.get("rules") or []), ",".join(t.get("docs") or []))
        results.append((r["case_id"], r["verdict"], r["reason_code"], group))
    results.sort(key=lambda x: h(x[0]))
    chosen, why = [], {}

    def take(cid, reason):
        if cid not in why and len(chosen) < k:
            chosen.append(cid)
            why[cid] = reason

    # 1. split groups: one case per distinct answer, smallest groups first (they are the odd ones out)
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for cid, v, code, g in results:
        groups[g][(v, code)].append(cid)
    split = [g for g in groups if len(groups[g]) > 1]
    split.sort(key=lambda g: (sum(len(x) for x in groups[g].values()), h("|".join(g))))
    budget = max(1, k // 2)
    for g in split:
        for ans in sorted(groups[g], key=lambda a: (len(groups[g][a]), a)):
            if len(chosen) >= budget:
                break
            take(groups[g][ans][0], "split")
    # 2. closes, one per reason code in turn
    by_code = collections.defaultdict(list)
    for cid, v, code, g in results:
        if v == "CLOSE":
            by_code[code].append(cid)
    while len(chosen) < k - 4 and any(by_code.values()):
        for code in sorted(by_code):
            if by_code[code] and len(chosen) < k - 4:
                take(by_code[code].pop(0), "close")
    # 3. two RFI, two ESCALATE (fill with closes if short)
    for verdict in ("RFI", "ESCALATE"):
        n = 0
        for cid, v, code, g in results:
            if v == verdict and n < 2 and cid not in why:
                take(cid, verdict.lower())
                n += 1
    for cid, v, code, g in results:
        take(cid, "fill")
    return chosen, why


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", default=os.path.join("..", "labels", "candidates.csv"))
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    repo = os.path.abspath(os.path.join(HERE, ".."))
    if out.startswith(repo + os.sep):
        sys.stderr.write("refusing to write %s inside the repository; labels live outside it\n" % out)
        return 2
    k = a.n // len(INSTITUTIONS)
    rows, tally = [], collections.Counter()
    for name in INSTITUTIONS:
        chosen, why = pick(Institution(os.path.join(a.folder, name)), k)
        for cid in chosen:
            rows.append((cid, name))
            tally[(name, why[cid])] += 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "institution"])
        w.writerows(rows)
    print("wrote %d cases to %s" % (len(rows), out))
    for name in INSTITUTIONS:
        print("  %-12s %s" % (name, ", ".join("%s %d" % (r, tally[(name, r)]) for r in
                                            ("split", "close", "rfi", "escalate", "fill") if tally[(name, r)])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
