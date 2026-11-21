"""Damage one institution folder at a time and check the system still answers safely.

    python tools/damage_test.py <institutions folder> [--institution emoney]

The unseen files come from the organisers' own export, so a stray byte-order
mark, a cut-off line or a record with no ID is possible. Any of those used to
stop system/run before it wrote a line, which zeroes the institution.

For each kind of damage the folder is copied to a temporary directory, damaged
in one way, and run through system/run. Every check needs exit code 0 and
exactly one line per case. Then:

  same    the output must equal the undamaged run byte for byte
  one     the damaged case is escalated and every other line is unchanged
  safer   no case may move towards CLOSE: not to CLOSE from RFI or ESCALATE,
          and not from ESCALATE to RFI (losing information may only move a
          case towards a person)

Nothing is written to the kit folder or to the repository.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "..", "system", "run")


def run(folder, out):
    p = subprocess.run([sys.executable, RUN, folder, out], capture_output=True, text=True)
    lines = []
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    return p.returncode, lines, p.stderr.strip().splitlines()[-1:] or [""]


def append(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def prepend_bom(path):
    with open(path, "rb") as fh:
        data = fh.read()
    with open(path, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + data)


def crlf(folder):
    for name in os.listdir(folder):
        if name.endswith(".jsonl"):
            p = os.path.join(folder, name)
            with open(p, "rb") as fh:
                data = fh.read()
            with open(p, "wb") as fh:
                fh.write(data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def extra_field(folder):
    p = os.path.join(folder, "customers.jsonl")
    with open(p, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            r["field_added_later"] = "x"
            fh.write(json.dumps(r) + "\n")


def drop_list_entry(folder):
    """Remove every list entry an alert names, keeping the rest of the file."""
    named = set()
    with open(os.path.join(folder, "alerts.jsonl"), encoding="utf-8") as fh:
        for l in fh:
            if l.strip():
                e = (json.loads(l).get("measured") or {}).get("list_entry")
                if e:
                    named.add(e)
    p = os.path.join(folder, "internal_list.jsonl")
    with open(p, encoding="utf-8") as fh:
        keep = [l for l in fh if l.strip() and json.loads(l).get("entry_id") not in named]
    with open(p, "w", encoding="utf-8") as fh:
        fh.writelines(keep)


def unloadable(folder):
    """customers.jsonl becomes a folder, so the institution cannot be read at all."""
    p = os.path.join(folder, "customers.jsonl")
    os.remove(p)
    os.makedirs(p)


def cut_case_line(folder):
    """Cut the sixth case line short, after its case ID and first alert ID."""
    p = os.path.join(folder, "cases.jsonl")
    with open(p, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    row = json.loads(lines[5])
    cut = lines[5].index(row["alert_ids"][0]) + len(row["alert_ids"][0]) + 1
    lines[5] = lines[5][:cut]
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return row["case_id"]


DAMAGE = [
    # name, check, what it does
    ("truncated transaction line", "same", lambda f: append(os.path.join(f, "transactions.jsonl"), '{"transaction_id": "X\n')),
    ("alert with no alert_id", "same", lambda f: append(os.path.join(f, "alerts.jsonl"), '{"case_id": "NONE", "rule_id": "TM01"}\n')),
    ("byte-order mark on cases.jsonl", "same", lambda f: prepend_bom(os.path.join(f, "cases.jsonl"))),
    ("JSON array line in customers.jsonl", "same", lambda f: append(os.path.join(f, "customers.jsonl"), "[1, 2, 3]\n")),
    ("CRLF line endings", "same", crlf),
    ("unknown extra field", "same", extra_field),
    ("transaction with no transaction_id", "same", lambda f: append(os.path.join(f, "transactions.jsonl"), '{"customer_id": "NONE", "amount_gbp": 1}\n')),
    ("cut-off line in cases.jsonl", "one", cut_case_line),
    ("internal_list.jsonl missing", "safer", lambda f: os.remove(os.path.join(f, "internal_list.jsonl"))),
    ("named list entries missing", "safer", drop_list_entry),
    ("folder cannot be loaded", "safer", unloadable),
]


RANK = {"CLOSE": 0, "RFI": 1, "ESCALATE": 2}


def verdicts(lines):
    out = {}
    for l in lines:
        d = json.loads(l)
        out[d["case_id"]] = d["verdict"]
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--institution", default="emoney")
    a = ap.parse_args(argv)
    src = os.path.join(os.path.abspath(a.folder), a.institution)
    if not os.path.isfile(os.path.join(src, "cases.jsonl")):
        sys.stderr.write("no cases.jsonl in %s\n" % src)
        return 2
    tmp = tempfile.mkdtemp(prefix="damage-")
    try:
        code, base, _ = run(src, os.path.join(tmp, "base.jsonl"))
        if code != 0 or not base:
            print("FAIL the undamaged folder does not run (exit %d)" % code)
            return 1
        base_v = verdicts(base)
        failed = 0
        for i, (name, check, damage) in enumerate(DAMAGE):
            folder = os.path.join(tmp, "f%d" % i)
            shutil.copytree(src, folder)
            hit = damage(folder)
            code, lines, last = run(folder, os.path.join(tmp, "out%d.jsonl" % i))
            problems = []
            if code != 0:
                problems.append("exit %d (%s)" % (code, last[0][:100]))
            if len(lines) != len(base):
                problems.append("%d lines for %d cases" % (len(lines), len(base)))
            if not problems and check == "same" and lines != base:
                problems.append("%d lines differ from the undamaged run" % sum(x != y for x, y in zip(lines, base)))
            if not problems and check == "one":
                v = verdicts(lines)
                if v.get(hit) != "ESCALATE":
                    problems.append("%s is %s, not ESCALATE" % (hit, v.get(hit)))
                others = [x for x, y in zip(lines, base) if json.loads(y)["case_id"] != hit and x != y]
                if others:
                    problems.append("%d other lines changed" % len(others))
                note = "%s escalated, the other %d lines identical" % (hit, len(base) - 1)
            elif not problems and check == "safer":
                v = verdicts(lines)
                down = sorted(c for c in v if RANK[v[c]] < RANK.get(base_v.get(c), 0))
                if down:
                    problems.append("%d cases moved towards CLOSE, e.g. %s %s -> %s"
                                    % (len(down), down[0], base_v.get(down[0]), v[down[0]]))
                moved = sum(v[c] != base_v.get(c) for c in v)
                note = "%d cases moved towards a person, none towards CLOSE" % moved if moved else "no change"
            else:
                note = "identical"
            if problems:
                failed += 1
                print("FAIL %-38s %s" % (name, "; ".join(problems)))
            else:
                print("ok   %-38s %s" % (name, note))
        print("\n%d of %d damage checks passed on %s" % (len(DAMAGE) - failed, len(DAMAGE), a.institution))
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
