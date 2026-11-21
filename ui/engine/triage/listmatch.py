"""Internal-list matches (TM22): is the counterparty the listed party or not?

A match on one detail does not prove identity. We compare every identity fact
on file about the matched party (date of birth, the dates they held office or
control, the registered address) with the list entry, and reach one of three
answers: the same party, a different party, or nothing on file settles it.
"""
import re

from . import textfacts as tf
from .case import Finding, same_party, day, tx_date

gbp = tf.gbp


def _born(text):
    """A birth date as (year, month, day or None) from '2 March 1980' or 'March 1980'."""
    d = tf.parse_date(text or "")
    if d:
        return (d.year, d.month, d.day)
    my = tf.month_years(text or "")
    if my:
        return (my[0][0], my[0][1], None)
    return None


def _first_sentence(text):
    """The first sentence of a list entry's reason, for quoting."""
    return re.split(r"(?<=[.!?])\s+", (text or "").strip())[0].rstrip(".")


def _same_birth(a, b):
    """Two birth dates agree on every part both of them give."""
    if not a or not b:
        return None
    if a[0] != b[0] or a[1] != b[1]:
        return False
    if a[2] is not None and b[2] is not None and a[2] != b[2]:
        return False
    return True


def _people(case, company):
    """Officers and controllers of the matched company, from the registers on file."""
    people = []
    for doc in case.docs_of("company_register_extract", "significant_control_register"):
        if not tf.mentions(doc.text, company) or tf.same_name(doc.field("company"), case.name):
            continue
        for row in doc.rows():
            name = row.get("officer") or row.get("person") or row.get("person with significant control") or ""
            if not name:
                continue
            ended = tf.parse_date(row.get("resigned") or row.get("ceased") or "")
            people.append({
                "name": name, "born": _born(row.get("born") or ""), "doc": doc,
                "role": "controller" if doc.type == "significant_control_register" or "control" in row else "officer",
                "ended": ended, "born_text": (row.get("born") or "").strip(),
                "what": (row.get("control") or row.get("role") or "").strip(),
            })
    return people


def _entry_missing(case, alert, m, entry_id):
    """The alert names a list entry that cannot be read: escalate, since it cannot be ruled out."""
    txs = [case.inst.tx[t] for t in alert.get("transaction_ids") or [] if t in case.inst.tx]
    t = txs[0] if txs else None
    party = (t or {}).get("counterparty_name") or (m.get("matched_party") or "the counterparty")
    pay = ("the %s %s %s on %s" % (gbp(t["amount_gbp"]), "payment to" if t["direction"] == "out" else "receipt from",
                                    party, day(t))) if t else "the payment"
    text = ("%s matched internal list entry %s on %s, but that entry is not in the internal list on file, so "
            "%s cannot be checked against the listed party's details. Until it is, %s cannot be ruled out as "
            "the listed party." % (pay[0].upper() + pay[1:], entry_id or "(no ID given)",
                                   m.get("matched_on") or "one detail", party, party))
    return Finding("flag", "ESC_LISTED_PARTY", text, txs=[t["transaction_id"]] if t else [], rank=5)


def review(case, explains):
    """One Finding per TM22 alert: flag (same party), explain (different party) or gap."""
    out = []
    for alert in case.alerts_of("TM22"):
        m = alert.get("measured") or {}
        entry = case.inst.list_entries.get(m.get("list_entry")) or {}
        entry_id = entry.get("entry_id") or m.get("list_entry")
        if not entry.get("name"):
            # The entry the alert names is not on file, so there is nothing to compare against.
            # Without it a register naming anyone would read as "a different party": never close on that.
            out.append(_entry_missing(case, alert, m, entry_id))
            continue
        listed = entry.get("name") or ""
        listed_born = _born(entry.get("date_of_birth") or "")
        txs = [case.inst.tx[t] for t in alert.get("transaction_ids") or [] if t in case.inst.tx]
        t = txs[0] if txs else None
        party = (t or {}).get("counterparty_name") or (m.get("matched_party") or "")
        paid_on = tx_date(t) if t else None
        tx_ids = [t["transaction_id"]] if t else []
        pay = ("the %s %s %s on %s" % (gbp(t["amount_gbp"]), "payment to" if t["direction"] == "out" else "receipt from",
                                        party, day(t))) if t else "the payment"
        paper = [f for f in explains if t and t["transaction_id"] in f.covers]
        paper_note = ""
        if paper:
            paper_note = " %s documents the payment itself." % paper[0].docs[0]

        # 1. the counterparty is a person who states their own date of birth
        same, different = None, None
        for doc in case.docs_of("gift_letter"):
            if not (party and tf.mentions(doc.text, party)):
                continue
            # a date in the letter at least 16 years before it was written is a birth date,
            # however the writer phrased it ("born 2 March 1980", "DOB: 2 March 1980")
            births = [d for d in doc.dates if doc.dated and d.year <= doc.dated.year - 16]
            if len(set(births)) != 1:
                continue
            said = tf.nice_date(births[0])
            verdict = _same_birth((births[0].year, births[0].month, births[0].day), listed_born)
            if verdict is True:
                same = ("%s gives %s's date of birth as %s, the same as list entry %s (%s, born %s, listed as \"%s\")"
                        % (doc.id, party, said, entry_id, listed, tf.nice_date(entry.get("date_of_birth")),
                           _first_sentence(entry.get("reason"))), [doc.id])
            elif verdict is False:
                different = ("%s gives %s's date of birth as %s, but the listed %s in entry %s was born %s"
                             % (doc.id, party, said, listed, entry_id, tf.nice_date(entry.get("date_of_birth"))),
                             [doc.id])

        # 2. the counterparty is a company: who runs and controls it?
        people = _people(case, party) if party else []
        named = [p for p in people if tf.same_name(p["name"], listed)]
        if named and same is None and different is None:
            agree = [p for p in named if _same_birth(p["born"], listed_born) is True]
            clash = [p for p in named if _same_birth(p["born"], listed_born) is False]
            if agree:
                active = [p for p in agree if not p["ended"] or (paid_on and p["ended"] >= paid_on)]
                docs = sorted(set(p["doc"].id for p in agree))
                if active:
                    p = sorted(active, key=lambda p: (p["role"] != "controller", p["doc"].id))[0]
                    until = ("until %s, after %s" % (tf.nice_date(p["ended"]), pay)) if p["ended"] else (
                        "and still did at %s" % pay)
                    left = [q for q in agree if q["ended"] and paid_on and q["ended"] < paid_on]
                    resigned = (" %s shows they resigned as director on %s, before the payment, but control had not passed"
                                % (left[0]["doc"].id, tf.nice_date(left[0]["ended"]))) if left else ""
                    same = ("%s shows %s, born %s, held control of %s (%s) %s. That matches list entry %s (%s, born %s, "
                            "listed as \"%s\"), so the listed party still controlled the company when it was paid.%s"
                            % (p["doc"].id, p["name"], p["born_text"], party, p["what"] or p["role"], until, entry_id,
                               listed, tf.nice_date(entry.get("date_of_birth")), _first_sentence(entry.get("reason")), resigned),
                            docs)
                else:
                    p = sorted(agree, key=lambda p: (str(p["ended"]), p["doc"].id))[-1]
                    left_note = ("%s shows %s, who matches list entry %s, left %s on %s, shortly before %s. The "
                                 "registers do not show who controls the company now, so the match is not settled "
                                 "and nothing else is concerning."
                                 % (p["doc"].id, p["name"], entry_id, party, tf.nice_date(p["ended"]), pay))
                    ask = ("Ask the customer who they dealt with at %s and for its current register of directors "
                           "and people with significant control." % party)
                    out.append(Finding("gap", "RFI_COUNTERPARTY_DETAILS", left_note, docs=docs, txs=tx_ids,
                                       extra=[entry_id], rank=5, ask=ask))
                    continue
            elif clash:
                p = clash[0]
                different = ("%s gives the %s of %s a birth date of %s, but the listed %s in entry %s was born %s"
                             % (p["doc"].id, p["role"], party, p["born_text"], listed, entry_id,
                                tf.nice_date(entry.get("date_of_birth"))), [p["doc"].id])
        elif people and same is None and different is None:
            # the listed person is not among the company's officers or controllers
            p = people[0]
            office = p["doc"].field("registered office")
            where = ""
            if office and entry.get("address"):
                where = " Its registered office is %s; the list entry gives %s." % (office, entry["address"])
            names = sorted(set(q["name"] for q in people))
            different = ("%s names %s%s as the %s of %s. The listed %s (entry %s) is not among them.%s"
                         % (p["doc"].id, " and ".join(names),
                            ", born %s," % p["born_text"] if p["born_text"] and len(names) == 1 else "",
                            "only director and owner" if len(names) == 1 else "directors and owners",
                            party, listed, entry_id, where),
                         sorted(set(q["doc"].id for q in people)))

        if same:
            if " still controlled the company" in same[0]:
                text = "%s.%s" % (same[0].rstrip("."), paper_note)
            else:
                text = "%s. So %s came from a party on the internal list.%s" % (same[0].rstrip("."), pay, paper_note)
            out.append(Finding("flag", "ESC_LISTED_PARTY", text, docs=same[1] + [d for f in paper for d in f.docs],
                               txs=tx_ids, extra=[entry_id], rank=5))
        elif different:
            text = "%s. The match was on %s only, so the counterparty is a different party.%s" % (
                different[0].rstrip("."), m.get("matched_on") or "one detail", paper_note)
            out.append(Finding("explain", "LIST_MATCH_DIFFERENT_PARTY", text,
                               docs=different[1] + [d for f in paper for d in f.docs], txs=tx_ids,
                               extra=[entry_id], covers=tx_ids, rules=("TM22",), rank=5))
        else:
            what = "date of birth" if entry.get("kind") != "business" else "company number"
            text = ("%s matched internal list entry %s (%s) on %s alone. Nothing on file gives %s's %s or "
                    "address, or says what the payment was for, so the match cannot be settled either way "
                    "and nothing else is concerning."
                    % (pay[0].upper() + pay[1:], entry_id, listed, m.get("matched_on") or "one detail", party, what))
            ask = ("Ask the customer who %s is and what the %s was for, with an invoice, receipt or letter "
                   "that shows %s's full name, %s and address." % (party, gbp(t["amount_gbp"]) if t else "payment",
                                                                   party, what))
            out.append(Finding("gap", "RFI_COUNTERPARTY_DETAILS", text, txs=tx_ids, extra=[entry_id], rank=5, ask=ask))
    return out
