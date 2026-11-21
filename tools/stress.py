"""Stress tests on generated institution folders, each with an answer known by construction.

    python tools/stress.py <path to institutions> [--out DIR] [--only subset,relabel,...]

The development cases carry no labels, so no accuracy figure can be measured.
These tests build whole new institution folders on disk from the kit, in the
kit's exact format, where the right outcome is fixed by how the folder was
made. Each folder is run through system/run from inside a frozen copy of
system/ with full paths, as the brief describes. It is started through the
Python interpreter, so the shebang and the executable bit are not tested here.

  subset    Random 200-case folders, as the unseen sets are. Every line must
            equal the full-folder answer: a verdict may not lean on other cases.
  relabel   Fresh IDs of the same shape, every person-name token swapped for
            another one consistently in every file, and every file's lines
            shuffled. Verdict and reason code must not move.
  shift     As relabel, with every date also moved one year later.
  destroy   For every CLOSE: drop a cited document, add 100 pounds to each of
            its amounts, swap the names in it, or slip a 5,000 pound payment
            from a stranger into the alert. The case must stop closing.
  dropalert For every CLOSE with two or more alerts: remove one alert. The
            evidence still explains the rest, so the case must still close.
  sweep     Own-account cases with one TM01 alert: set received / baseline to
            just under, at and just over the policy multiple. Below closes,
            at or above sends an RFI for an updated profile.
  listdob   For every LIST_MATCH_DIFFERENT_PARTY close, give the person in the
            deciding document the listed party's date of birth, and put the
            listed person in the register as the company's officer and owner.
            It must not close.
  blanktext Not pass/fail: reduce every chat and note to one neutral line and
            show which verdicts move, i.e. which rest on wording alone.

Nothing is written to the kit folder. Generated folders hold development data,
so they stay outside system/ and outside the public repository.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = os.path.abspath(os.path.join(HERE, "..", "system"))
INSTITUTIONS = ["bank", "emoney", "investment", "payments_fx"]
FILES = ["cases", "alerts", "customers", "transactions", "evidence", "previous_reviews", "internal_list"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
ID_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z]{0,3}\d{3,10}\b")
WORD_RE = re.compile(r"\b[A-Za-z]+\b")
MONEY_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?![\d])")
DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)|\b(?:(\d{1,2}) )?(%s) (\d{4})\b" % "|".join(MONTHS))
STOP = set("""Ltd Limited LLP PLC Plc Group Holdings Services Bank Client Account Solicitors Trust The And
Street Road Avenue Close Lane Way Drive Court Place Park House Unit Works Estate Of From To For Dear Sir Madam
United Kingdom Monday Tuesday Wednesday Thursday Friday Saturday Sunday Customer Agent Staff Note""".split())
sys.stdout.reconfigure(encoding="utf-8")


# ---- folders -----------------------------------------------------------------
class Folder:
    """One institution folder held in memory: its JSONL rows, documents and SOP."""

    def __init__(self, path):
        self.rows = {}
        for name in FILES:
            p = os.path.join(path, name + ".jsonl")
            with open(p, encoding="utf-8") as fh:
                self.rows[name] = [json.loads(line) for line in fh if line.strip()]
        self.docs = {}
        for e in self.rows["evidence"]:
            with open(os.path.join(path, e["file"]), encoding="utf-8") as fh:
                self.docs[e["file"]] = fh.read()
        with open(os.path.join(path, "POLICY.md"), encoding="utf-8") as fh:
            self.policy = fh.read()

    def clone(self):
        new = Folder.__new__(Folder)
        new.rows = {k: [json.loads(json.dumps(r)) for r in v] for k, v in self.rows.items()}
        new.docs = dict(self.docs)
        new.policy = self.policy
        return new

    def write(self, path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(os.path.join(path, "evidence"))
        with open(os.path.join(path, "POLICY.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.policy)
        for name in FILES:
            with open(os.path.join(path, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as fh:
                for r in self.rows[name]:
                    fh.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        for e in self.rows["evidence"]:
            with open(os.path.join(path, e["file"]), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self.docs[e["file"]])
        return path

    def keep(self, case_ids):
        """Only the given cases, their alerts, and their customers' records."""
        case_ids = set(case_ids)
        cases = [c for c in self.rows["cases"] if c["case_id"] in case_ids]
        custs = {c["customer_id"] for c in cases}
        f = Folder.__new__(Folder)
        f.policy = self.policy
        f.rows = {"cases": cases,
                  "alerts": [a for a in self.rows["alerts"] if a["case_id"] in case_ids],
                  "internal_list": list(self.rows["internal_list"])}
        for name in ("customers", "transactions", "evidence", "previous_reviews"):
            f.rows[name] = [r for r in self.rows[name] if r.get("customer_id") in custs]
        f.docs = {e["file"]: self.docs[e["file"]] for e in f.rows["evidence"]}
        return f

    def doc_row(self, doc_id):
        for e in self.rows["evidence"]:
            if e["doc_id"] == doc_id:
                return e
        return None


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---- running the system --------------------------------------------------------
def snapshot(dest):
    """Freeze system/ so a parallel edit cannot change the code mid-test."""
    target = os.path.join(dest, "system")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(SYSTEM, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(target)):
        for name in sorted(files):
            with open(os.path.join(root, name), "rb") as fh:
                h.update(name.encode() + fh.read())
    return target, h.hexdigest()[:12]


def run(system, folder_path, out_path):
    proc = subprocess.run([sys.executable, os.path.join(system, "run"), os.path.abspath(folder_path),
                           os.path.abspath(out_path)], cwd=system, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=dict(os.environ, PYTHONHASHSEED="0"))
    if proc.returncode != 0:
        raise SystemExit("system/run failed on %s:\n%s" % (folder_path, proc.stderr.decode("utf-8", "replace")))
    return {o["case_id"]: o for o in jsonl(out_path)}


# ---- relabelling ------------------------------------------------------------------
def id_values(f):
    """Every ID the kit's fields define, so only real IDs are ever renamed."""
    ids = set()
    for c in f.rows["cases"]:
        ids.update([c["case_id"], c["customer_id"]] + list(c["alert_ids"]))
        if c.get("held_payment_id"):
            ids.add(c["held_payment_id"])
    for a in f.rows["alerts"]:
        ids.update([a["alert_id"]] + list(a.get("transaction_ids") or []))
    for c in f.rows["customers"]:
        ids.update([c["customer_id"]] + list(c.get("account_ids") or []))
    for t in f.rows["transactions"]:
        ids.update([t["transaction_id"], t["account_id"]])
    for e in f.rows["evidence"]:
        ids.add(e["doc_id"])
    for r in f.rows["previous_reviews"]:
        ids.add(r["review_id"])
    for e in f.rows["internal_list"]:
        ids.add(e["entry_id"])
    return {i for i in ids if i and ID_RE.fullmatch(i)}


def fresh_ids(ids, rng):
    """A new ID of the same shape for each, never one already in use."""
    used, out = set(ids), {}
    for old in sorted(ids):
        m = re.match(r"^(.*?)(\d+)$", old)
        prefix, digits = m.group(1), len(m.group(2))
        while True:
            new = prefix + str(rng.randint(10 ** (digits - 1), 10 ** digits - 1))
            if new not in used:
                break
        used.add(new)
        out[old] = new
    return out


def name_pool(folders):
    """Person-name tokens safe to swap: forenames and surnames, never ordinary words."""
    lower, policy_words = set(), set()
    names = []
    for f in folders:
        policy_words.update(w.lower() for w in WORD_RE.findall(f.policy))
        for c in f.rows["customers"]:
            if c.get("kind") == "individual":
                names.append(c["name"])
        for e in f.rows["internal_list"]:
            if e.get("kind") == "individual":
                names.append(e["name"])
        for text in f.docs.values():
            lower.update(re.findall(r"\b[a-z]+\b", text))
        for t in f.rows["transactions"]:
            lower.update(re.findall(r"\b[a-z]+\b", (t.get("reference") or "") + " " + (t.get("counterparty_name") or "")))
    tokens = set()
    for n in names:
        for w in WORD_RE.findall(n):
            if (len(w) >= 3 and w[0].isupper() and w[1:].islower() and w not in STOP and w not in MONTHS
                    and w.lower() not in lower and w.lower() not in policy_words):
                tokens.add(w)
    return sorted(tokens)


def name_map(tokens, rng, same_initial=True):
    """A bijection on name tokens. Same initial keeps initials such as 'R FIELD' consistent."""
    groups = collections.defaultdict(list)
    for t in tokens:
        groups[t[0] if same_initial else ""].append(t)
    out = {}
    for _, group in sorted(groups.items()):
        shuffled = group[:]
        rng.shuffle(shuffled)
        for a, b in zip(group, shuffled):
            out[a] = b
            out[a.upper()] = b.upper()
    return out


def sub_words(text, mapping):
    return WORD_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


def sub_ids(text, mapping):
    return ID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


def shift_date_text(text, years):
    def one(m):
        if m.group(1):
            y, mo, d = int(m.group(1)) + years, int(m.group(2)), int(m.group(3))
            if mo == 2 and d == 29:
                d = 28
            return "%04d-%02d-%02d" % (y, mo, d)
        day, month, year = m.group(4), m.group(5), int(m.group(6)) + years
        if day and month == "February" and day == "29":
            day = "28"
        return ("%s %s %d" % (day, month, year)) if day else ("%s %d" % (month, year))
    return DATE_RE.sub(one, text)


def transform(f, ids=None, names=None, years=0, rng=None):
    """Apply an ID map, a name map and a date shift to every row and document."""
    def text(s):
        if ids:
            s = sub_ids(s, ids)
        if names:
            s = sub_words(s, names)
        if years:
            s = shift_date_text(s, years)
        return s

    g = Folder.__new__(Folder)
    g.policy = f.policy
    g.rows = {k: [json.loads(text(json.dumps(r, ensure_ascii=False))) for r in v] for k, v in f.rows.items()}
    g.docs = {}
    for old, new in zip(f.rows["evidence"], g.rows["evidence"]):
        g.docs[new["file"]] = text(f.docs[old["file"]])
    if rng:
        for k in FILES:
            rng.shuffle(g.rows[k])
    return g


# ---- comparing -------------------------------------------------------------------
class Tally:
    def __init__(self, name):
        self.name, self.checked, self.fails = name, 0, []

    def check(self, ok, detail):
        self.checked += 1
        if not ok:
            self.fails.append(detail)

    def line(self):
        return "%-28s %6d checked  %5d failed" % (self.name, self.checked, len(self.fails))


def short(o):
    return "%s:%s" % (o["verdict"], o["reason_code"]) if o else "MISSING"


# ---- the tests --------------------------------------------------------------------
def t_subset(inst, base, full, system, work, report, seeds=(1, 2, 3, 4, 5), n=200):
    tv, te, tr = Tally("subset verdict+code"), Tally("subset evidence"), Tally("subset reason text")
    case_ids = [c["case_id"] for c in base.rows["cases"]]
    for seed in seeds:
        pick = random.Random(seed).sample(case_ids, min(n, len(case_ids)))
        path = base.keep(pick).write(os.path.join(work, "%s_subset%d" % (inst, seed)))
        out = run(system, path, path + ".out.jsonl")
        for cid in pick:
            a, b = full[cid], out.get(cid)
            tv.check(b is not None and short(a) == short(b), (cid, short(a), short(b)))
            if b:
                te.check(a["evidence"] == b["evidence"], (cid, a["evidence"], b["evidence"]))
                tr.check(a["reason"] == b["reason"], (cid,))
    return [tv, te, tr]


def t_relabel(inst, base, full, system, work, report, pool, seed=7, years=0):
    rng = random.Random(seed)
    ids = fresh_ids(id_values(base), rng)
    names = name_map(pool, rng)
    g = transform(base, ids, names, years, rng)
    tag = "shift" if years else "relabel"
    path = g.write(os.path.join(work, "%s_%s" % (inst, tag)))
    out = run(system, path, path + ".out.jsonl")
    back_ids = {v: k for k, v in ids.items()}
    back_names = {v: k for k, v in names.items()}
    tv, te = Tally(tag + " verdict+code"), Tally(tag + " evidence set")
    to, tr = Tally(tag + " evidence order"), Tally(tag + " reason text")
    for cid, a in full.items():
        b = out.get(ids.get(cid, cid))
        tv.check(b is not None and short(a) == short(b), (cid, short(a), short(b)))
        if b:
            ev = [back_ids.get(e, e) for e in b["evidence"]]
            te.check(sorted(ev) == sorted(a["evidence"]), (cid, a["evidence"], ev))
            to.check(ev == a["evidence"], (cid, a["evidence"], ev))
            reason = sub_words(sub_ids(b["reason"], back_ids), back_names)
            if years:
                reason = shift_date_text(reason, -years)
            tr.check(reason == a["reason"], (cid, a["reason"], reason))
    return [tv, te, to, tr]


def cited_docs(base, out_row, customer_id):
    mine = {e["doc_id"] for e in base.rows["evidence"] if e["customer_id"] == customer_id}
    return [e for e in out_row["evidence"] if e in mine]


def bump_money(text):
    """Add 100 to every amount written with pence, keeping the format."""
    def one(m):
        value = float(m.group(1).replace(",", "") + "." + m.group(2)) + 100
        whole = "{:,.2f}".format(value) if "," in m.group(1) or value >= 1000 else "%.2f" % value
        return whole
    head, sep, body = text.partition("\n\n")
    return head + sep + MONEY_RE.sub(one, body) if sep else MONEY_RE.sub(one, text)


def t_destroy(inst, base, full, system, work, report, pool):
    closes = [(c, full[c["case_id"]]) for c in base.rows["cases"] if full[c["case_id"]]["verdict"] == "CLOSE"]
    swap = name_map(pool, random.Random(11), same_initial=False)
    swap = {k: v for k, v in swap.items() if k != v}
    tallies = []
    types = {e["doc_id"]: e["type"] for e in base.rows["evidence"]}

    def mutate(kind, k):
        g = base.clone()
        targets = []
        for c, o in closes:
            docs = cited_docs(base, o, c["customer_id"])
            if len(docs) <= k:
                continue
            doc_id = docs[k]
            row = g.doc_row(doc_id)
            if row is None:
                continue
            if kind == "drop":
                g.rows["evidence"].remove(row)
                g.docs.pop(row["file"], None)
            elif kind == "bump":
                new = bump_money(g.docs[row["file"]])
                if new == g.docs[row["file"]]:
                    continue
                g.docs[row["file"]] = new
            elif kind == "party":
                new = sub_words(g.docs[row["file"]], swap)
                if new == g.docs[row["file"]]:
                    continue
                g.docs[row["file"]] = new
                row["title"] = sub_words(row["title"], swap)
            targets.append((c, o, doc_id))
        live = {e["file"] for e in g.rows["evidence"]}
        g.docs = {p: t for p, t in g.docs.items() if p in live}
        return g, targets

    for kind in ("drop", "bump", "party"):
        for k in range(3):
            g, targets = mutate(kind, k)
            if not targets:
                continue
            path = g.write(os.path.join(work, "%s_destroy_%s%d" % (inst, kind, k)))
            out = run(system, path, path + ".out.jsonl")
            t = Tally("destroy %s doc#%d" % (kind, k + 1))
            for c, o, doc_id in targets:
                b = out[c["case_id"]]
                t.check(b["verdict"] != "CLOSE", (c["case_id"], o["reason_code"], types.get(doc_id), doc_id,
                                                  short(b), b["reason"]))
            tallies.append(t)

    # A 5,000 pound payment from a stranger inside the first alert.
    g = base.clone()
    alerts = {a["alert_id"]: a for a in g.rows["alerts"]}
    txs = {t["transaction_id"]: t for t in g.rows["transactions"]}
    used = id_values(base)
    rng = random.Random(5)
    targets = []
    for c, o in closes:
        a = alerts[c["alert_ids"][0]]
        pool_tx = [txs[i] for i in a.get("transaction_ids") or [] if i in txs]
        plain = [t for t in pool_tx if not (t.get("channel") or "").startswith("fund_")]
        mine = [t for t in g.rows["transactions"] if t["customer_id"] == c["customer_id"]
                and t["direction"] == "in" and not (t.get("channel") or "").startswith(("fund_", "cash"))]
        tmpl = (next((t for t in plain if t["direction"] == "in"), None) or (mine[-1] if mine else None)
                or (plain[0] if plain else None))
        if tmpl is None:
            continue
        new = json.loads(json.dumps(tmpl))
        prefix = re.match(r"^(.*?)\d+$", tmpl["transaction_id"]).group(1)
        while True:
            tid = prefix + str(rng.randint(10 ** 8, 10 ** 9 - 1))
            if tid not in used:
                used.add(tid)
                break
        stamp = dt.datetime.strptime(tmpl["booked_at"], "%Y-%m-%dT%H:%M:%SZ") + dt.timedelta(hours=1)
        new.update(transaction_id=tid, booked_at=stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), amount_gbp=5000.0,
                   amount=5000.0 if new.get("currency") in (None, "GBP") else new.get("amount"),
                   counterparty_name="Quillon Varnstead", counterparty_account=None, reference="TRANSFER")
        g.rows["transactions"].append(new)
        a["transaction_ids"] = list(a["transaction_ids"]) + [tid]
        targets.append((c, o, tid))
    path = g.write(os.path.join(work, "%s_destroy_stranger" % inst))
    out = run(system, path, path + ".out.jsonl")
    t = Tally("destroy stranger 5,000")
    for c, o, tid in targets:
        b = out[c["case_id"]]
        t.check(b["verdict"] != "CLOSE", (c["case_id"], o["reason_code"], "stranger", tid, short(b), b["reason"]))
    tallies.append(t)
    return tallies


def t_dropalert(inst, base, full, system, work, report):
    tallies = []
    for which in (0, -1):
        g = base.clone()
        cases = {c["case_id"]: c for c in g.rows["cases"]}
        targets, gone = [], set()
        for cid, o in full.items():
            c = cases[cid]
            if o["verdict"] == "CLOSE" and len(c["alert_ids"]) >= 2:
                drop = c["alert_ids"][which]
                c["alert_ids"] = [a for a in c["alert_ids"] if a != drop]
                gone.add(drop)
                targets.append((cid, o, drop))
        g.rows["alerts"] = [a for a in g.rows["alerts"] if a["alert_id"] not in gone]
        path = g.write(os.path.join(work, "%s_dropalert%d" % (inst, which)))
        out = run(system, path, path + ".out.jsonl")
        t = Tally("dropalert %s" % ("first" if which == 0 else "last"))
        for cid, o, drop in targets:
            t.check(out[cid]["verdict"] == "CLOSE", (cid, short(o), short(out[cid]), drop))
        tallies.append(t)
    return tallies


def t_sweep(inst, base, full, system, work, report):
    m = re.search(r"at (\d+(?:\.\d+)?) times the declared", base.policy)
    multiple = float(m.group(1)) if m else 5.0
    alerts = {a["alert_id"]: a for a in base.rows["alerts"]}
    pick = [c for c in base.rows["cases"]
            if full[c["case_id"]]["reason_code"] in ("OWN_ACCOUNT", "RFI_UPDATED_PROFILE")
            and len(c["alert_ids"]) == 1 and alerts[c["alert_ids"][0]]["rule_id"] == "TM01"]
    tallies = []
    for ratio in (multiple - 1, multiple - 0.01, multiple, multiple + 0.01, multiple + 1):
        g = base.clone()
        al = {a["alert_id"]: a for a in g.rows["alerts"]}
        for c in pick:
            meas = al[c["alert_ids"][0]]["measured"]
            if ratio <= meas.get("limit_multiple", 0):
                continue
            meas["baseline_gbp"] = round(meas["received_gbp"] / ratio, 2)
            meas["multiple"] = round(meas["received_gbp"] / meas["baseline_gbp"], 2)
        path = g.write(os.path.join(work, "%s_sweep_%s" % (inst, ratio)))
        out = run(system, path, path + ".out.jsonl")
        t = Tally("sweep own-account x%.2f" % ratio)
        for c in pick:
            meas = al[c["alert_ids"][0]]["measured"]
            real = meas["received_gbp"] / meas["baseline_gbp"]
            want = "RFI:RFI_UPDATED_PROFILE" if real >= multiple else "CLOSE:OWN_ACCOUNT"
            got = short(out[c["case_id"]])
            t.check(got == want, (c["case_id"], short(full[c["case_id"]]), "ratio %.4f" % real, want, got))
        tallies.append(t)
    return tallies


BORN_RE = re.compile(r"\b(born |date of birth[:*\s]*|DOB[:*\s]*)(\d{1,2} )?(%s) (\d{4})" % "|".join(MONTHS), re.I)
MONTH_YEAR = re.compile(r"\b(?:\d{1,2} )?(?:%s) \d{4}\b" % "|".join(MONTHS))


def make_listed_officer(text, entry):
    """Put the listed person in the register as the first officer, with the listed birth month."""
    rows = [l for l in text.split("\n") if l.startswith("|") and not l.startswith("|---")]
    officer = None
    for i, line in enumerate(rows):
        if line.lower().startswith("| officer"):
            if i + 1 < len(rows):
                officer = rows[i + 1].split("|")[1].strip()
            break
    if not officer:
        return text
    dob = dt.date.fromisoformat(entry["date_of_birth"])
    born = "%s %d" % (MONTHS[dob.month - 1], dob.year)
    out = []
    for line in text.split("\n"):
        if line.startswith("|") and officer in line:
            line = MONTH_YEAR.sub(born, line.replace(officer, entry["name"]))
        else:
            line = line.replace(officer, entry["name"])
        out.append(line)
    return "\n".join(out)


def t_listdob(inst, base, full, system, work, report):
    entries = {e["entry_id"]: e for e in base.rows["internal_list"]}
    g = base.clone()
    targets = []
    for c in base.rows["cases"]:
        o = full[c["case_id"]]
        if o["reason_code"] != "LIST_MATCH_DIFFERENT_PARTY":
            continue
        listed = [entries[e] for e in o["evidence"] if e in entries and entries[e].get("date_of_birth")]
        if not listed:
            continue
        dob = dt.date.fromisoformat(listed[0]["date_of_birth"])
        changed = False
        for doc_id in cited_docs(base, o, c["customer_id"]):
            row = g.doc_row(doc_id)
            text = g.docs[row["file"]]

            def one(m):
                if m.group(2):
                    return "%s%d %s %d" % (m.group(1), dob.day, MONTHS[dob.month - 1], dob.year)
                return "%s%s %d" % (m.group(1), MONTHS[dob.month - 1], dob.year)
            new = BORN_RE.sub(one, text)
            if row["type"] == "company_register_extract" and listed[0].get("kind") == "individual":
                new = make_listed_officer(new, listed[0])
            if new != text:
                g.docs[row["file"]] = new
                changed = True
        if changed:
            targets.append((c, o, listed[0]["entry_id"]))
    if not targets:
        return []
    path = g.write(os.path.join(work, "%s_listdob" % inst))
    out = run(system, path, path + ".out.jsonl")
    t = Tally("listdob made to match")
    for c, o, entry in targets:
        b = out[c["case_id"]]
        t.check(b["verdict"] != "CLOSE", (c["case_id"], entry, short(b), b["reason"]))
    return [t]


def t_ownname(inst, base, full, system, work, report):
    """Swap only the customer's own name in each cited document of a CLOSE.

    Also counts, per document type, how often the customer's name appears at
    all: a must-name-the-customer rule is only safe for types that always do.
    """
    custs = {c["customer_id"]: c for c in base.rows["customers"]}
    types = {e["doc_id"]: e["type"] for e in base.rows["evidence"]}
    seen = collections.Counter()
    named = collections.Counter()
    tallies = []
    for k in range(2):
        g = base.clone()
        targets = []
        for c in base.rows["cases"]:
            o = full[c["case_id"]]
            if o["verdict"] != "CLOSE":
                continue
            docs = cited_docs(base, o, c["customer_id"])
            if len(docs) <= k:
                continue
            row = g.doc_row(docs[k])
            name = custs[c["customer_id"]]["name"]
            business = custs[c["customer_id"]].get("kind") == "business"
            fresh = "Varnstead Trading Ltd" if business else "Quillon Varnstead"
            text = g.docs[row["file"]]
            new = re.sub(re.escape(name), fresh, text, flags=re.I)
            words = name.split()
            key = words[0] if business else words[-1]
            new = re.sub(r"\b%s\b" % re.escape(key), "Varnstead", new)
            new = re.sub(r"\b%s\b" % re.escape(key.upper()), "VARNSTEAD", new)
            seen[types[docs[k]]] += 1
            if new == text:
                continue
            named[types[docs[k]]] += 1
            g.docs[row["file"]] = new
            targets.append((c, o, docs[k]))
        path = g.write(os.path.join(work, "%s_ownname%d" % (inst, k)))
        out = run(system, path, path + ".out.jsonl")
        t = Tally("ownname doc#%d" % (k + 1))
        for c, o, doc_id in targets:
            b = out[c["case_id"]]
            t.check(b["verdict"] != "CLOSE", (c["case_id"], o["reason_code"], types[doc_id], doc_id, short(b), b["reason"]))
        tallies.append(t)
    report.setdefault("ownname_coverage", {})[inst] = {
        ty: "%d of %d cited name the customer" % (named[ty], seen[ty]) for ty in sorted(seen)}
    return tallies


def t_poscale(inst, base, full, system, work, report):
    """Order-backed closes: scale the invoice by 1.5, or change the PO number in it."""
    types = {e["doc_id"]: e["type"] for e in base.rows["evidence"]}
    tallies = []
    for kind in ("scale", "ponumber"):
        g = base.clone()
        targets = []
        for c in base.rows["cases"]:
            o = full[c["case_id"]]
            if o["verdict"] != "CLOSE":
                continue
            docs = cited_docs(base, o, c["customer_id"])
            if not any(types[d] == "purchase_order" for d in docs):
                continue
            for d in docs:
                if types[d] not in ("supplier_invoice", "invoice"):
                    continue
                row = g.doc_row(d)
                text = g.docs[row["file"]]
                if kind == "scale":
                    new = MONEY_RE.sub(lambda m: "{:,.2f}".format(
                        float(m.group(1).replace(",", "") + "." + m.group(2)) * 1.5), text)
                else:
                    new = re.sub(r"\bPO\s*(\d+)", lambda m: "PO " + str(int(m.group(1)) + 7), text)
                if new != text:
                    g.docs[row["file"]] = new
                    targets.append((c, o, d))
        if not targets:
            continue
        path = g.write(os.path.join(work, "%s_po%s" % (inst, kind)))
        out = run(system, path, path + ".out.jsonl")
        t = Tally("order invoice %s" % kind)
        for c, o, d in targets:
            b = out[c["case_id"]]
            t.check(b["verdict"] != "CLOSE", (c["case_id"], o["reason_code"], types[d], d, short(b), b["reason"]))
        tallies.append(t)
    return tallies


FREE_TEXT = ("support_chat", "staff_note", "customer_email", "email", "customer_letter", "contact_note")


def t_blanktext(inst, base, full, system, work, report):
    """Not pass/fail. Shows which verdicts rest on the wording of chats and notes.

    Every free-text document keeps its header but its body becomes one neutral
    line. A verdict that moves depends on how the text is worded, so a reworded
    chat in an unseen case could move it too. ESCALATE or RFI turning into
    CLOSE would mean free text alone was blocking a close, which is fine; a
    CLOSE turning into anything else means free text was needed to close.
    """
    g = base.clone()
    touched = set()
    for e in g.rows["evidence"]:
        if e["type"] in FREE_TEXT:
            text = g.docs[e["file"]]
            cut = text.find("\n\n", text.find("**Dated:**")) if "**Dated:**" in text else text.find("\n\n")
            head = text[:cut] if cut > 0 else text.split("\n")[0]
            g.docs[e["file"]] = head + "\n\n**Customer:** Thank you.\n\n**Agent:** You are welcome.\n"
            touched.add(e["customer_id"])
    path = g.write(os.path.join(work, "%s_blanktext" % inst))
    out = run(system, path, path + ".out.jsonl")
    moves = collections.Counter()
    t = Tally("blanktext verdict held")
    for c in base.rows["cases"]:
        if c["customer_id"] not in touched:
            continue
        a, b = full[c["case_id"]], out[c["case_id"]]
        moves["%s -> %s" % (short(a), short(b))] += a["verdict"] != b["verdict"]
        t.check(a["verdict"] == b["verdict"], (c["case_id"], short(a), short(b)))
    report.setdefault("blanktext", {})[inst] = {k: v for k, v in moves.items() if v}
    return [t]


# ---- main ------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kit", help="path to the kit's institutions folder")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "track1-stress"))
    ap.add_argument("--only", default="subset,relabel,shift,destroy,dropalert,sweep,listdob,blanktext,ownname,poscale")
    ap.add_argument("--inst", default=",".join(INSTITUTIONS))
    args = ap.parse_args()
    tests = args.only.split(",")
    out_root = os.path.abspath(args.out)
    work = os.path.join(out_root, "gen")
    os.makedirs(work, exist_ok=True)
    system, code_hash = snapshot(out_root)
    print("system snapshot %s  (tests: %s)" % (code_hash, ", ".join(tests)))
    folders = {i: Folder(os.path.join(args.kit, i)) for i in args.inst.split(",")}
    pool = name_pool(folders.values())
    print("person-name tokens swapped: %d" % len(pool))
    report = {"system": code_hash, "results": {}}
    started = time.time()
    for inst, base in folders.items():
        full = run(system, os.path.join(args.kit, inst), os.path.join(work, inst + "_full.out.jsonl"))
        print("\n== %s  (%d cases: %s)" % (inst, len(full), dict(collections.Counter(o["verdict"] for o in full.values()))))
        tallies = []
        if "subset" in tests:
            tallies += t_subset(inst, base, full, system, work, report)
        if "relabel" in tests:
            tallies += t_relabel(inst, base, full, system, work, report, pool)
        if "shift" in tests:
            tallies += t_relabel(inst, base, full, system, work, report, pool, seed=8, years=1)
        if "destroy" in tests:
            tallies += t_destroy(inst, base, full, system, work, report, pool)
        if "dropalert" in tests:
            tallies += t_dropalert(inst, base, full, system, work, report)
        if "sweep" in tests:
            tallies += t_sweep(inst, base, full, system, work, report)
        if "listdob" in tests:
            tallies += t_listdob(inst, base, full, system, work, report)
        if "blanktext" in tests:
            tallies += t_blanktext(inst, base, full, system, work, report)
        if "ownname" in tests:
            tallies += t_ownname(inst, base, full, system, work, report)
        if "poscale" in tests:
            tallies += t_poscale(inst, base, full, system, work, report)
        for t in tallies:
            print("  " + t.line())
        report["results"][inst] = {t.name: {"checked": t.checked, "failed": len(t.fails), "fails": t.fails}
                                   for t in tallies}
    with open(os.path.join(out_root, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
    total = sum(r["checked"] for v in report["results"].values() for r in v.values())
    failed = sum(r["failed"] for v in report["results"].values() for r in v.values())
    print("\n%d checks on generated folders, %d failed, %.0fs. Details: %s" % (
        total, failed, time.time() - started, os.path.join(out_root, "report.json")))


if __name__ == "__main__":
    main()
