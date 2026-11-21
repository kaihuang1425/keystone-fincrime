"""Turn the findings on a case into one verdict, reason code, reason and evidence list.

The order of the three questions is the whole algorithm:

1. Is there evidence of a sign of crime?            -> ESCALATE
2. Does a document explain every alert in the case?  -> CLOSE
   (own-account transfers at 5x the declared figure  -> RFI for an updated profile)
3. Otherwise nothing is suspicious but something is undocumented -> RFI,
   naming the one document that would settle it.
"""
import re

from . import textfacts as tf
from . import explain, flags, listmatch
from .case import Case, Finding, same_party, ids, day

gbp = tf.gbp
VERDICT_OF = {"ESC": "ESCALATE", "RFI": "RFI"}


def verdict_for(code):
    return VERDICT_OF.get(code.split("_")[0], "CLOSE")


# ------------------------------------------------------------------ is an alert explained?
def resolved(alert, case, explains, covered):
    """True when documents on file account for what this alert measured."""
    rule = alert.get("rule_id")
    m = alert.get("measured") or {}
    txs = [case.inst.tx[t] for t in alert.get("transaction_ids") or [] if t in case.inst.tx]
    able = [f for f in explains if rule in f.rules]
    if not able:
        return False
    is_open = lambda t: t["transaction_id"] not in covered
    money_in = [t for t in txs if t["direction"] == "in"]
    moved_out = [t for t in txs if t["direction"] == "out" and not case.is_spending(t)]
    if rule == "TM22":
        return any(f.code == "LIST_MATCH_DIFFERENT_PARTY" for f in able)
    if rule == "TM01":
        explained = sum(t["amount_gbp"] for t in money_in if not is_open(t))
        limit = (m.get("limit_multiple") or 0) * (m.get("baseline_gbp") or 0)
        return explained > 0 and (m.get("received_gbp") or 0) - explained <= limit + 0.005
    if rule == "TM02":
        if all(is_open(t) for t in txs):
            return False
        # money the client pays in from its own bank is not third-party money
        left_in = sum(t["amount_gbp"] for t in money_in if is_open(t) and not (case.is_business and case.is_self(t)))
        left_out = sum(t["amount_gbp"] for t in moved_out if is_open(t))
        return left_in < 2000 or left_out < (m.get("limit_share") or 0.8) * left_in
    if rule == "TM04":
        unknown = set(tf.norm(t.get("counterparty_name") or "") for t in txs if is_open(t))
        return len(unknown) < len(set(tf.norm(t.get("counterparty_name") or "") for t in txs)) and len(unknown) <= (m.get("limit") or 0)
    if rule == "TM07":
        reverified = any(f.code == "RETURNING_CUSTOMER" for f in able)
        left = [t for t in txs if not case.is_spending(t) and is_open(t)
                and not (reverified and case.is_business and case.is_self(t))]
        # a statement shows whose account the money came from. Only a re-verification shows
        # that the person now using the dormant account is the customer.
        own_money = [t for t in txs if case.is_self(t) and not case.is_spending(t)]
        if own_money and not reverified:
            return False
        return not left and any(not is_open(t) for t in txs)
    # TM03, TM05, TM06, TM08, TM10: every alerted transaction must be documented
    return bool(txs) and all(not is_open(t) for t in txs)


# ------------------------------------------------------------------ what to ask for
def _largest(txs):
    return max(txs, key=lambda t: (t["amount_gbp"], t["transaction_id"])) if txs else None


def _shares_surname(case, t):
    if case.is_business:
        return False
    surname = tf.norm(case.name).split(" ")[-1:] if case.name else []
    return bool(surname) and surname[0] in tf.norm(t.get("counterparty_name") or "").split(" ")


_ONE_OFF = re.compile(r"solicitor|conveyanc|assurance|insurance|estate|settlement|sale proceeds|claim", re.I)


def gap(case, open_alerts, covered):
    """The RFI: what is undocumented, and the one thing to ask the customer for."""
    rules = [a.get("rule_id") for a in open_alerts]
    is_open = lambda t: t["transaction_id"] not in covered
    pool = []
    for a in open_alerts:
        for t in case.alert_txs(a.get("rule_id")):
            if t not in pool and is_open(t):
                pool.append(t)
    money_in = [t for t in pool if t["direction"] == "in"]
    moved_out = [t for t in pool if t["direction"] == "out" and not case.is_spending(t)]
    known_payers = lambda t: any(
        same_party(o.get("counterparty_name"), t.get("counterparty_name")) and o.get("counterparty_account") == t.get("counterparty_account")
        and (o.get("booked_at") or "")[:10] < case.window_from for o in case.txs)
    new_in = [t for t in money_in if not known_payers(t)] or money_in
    new_out = [t for t in moved_out if not known_payers(t)] or moved_out
    big_in, big_out = _largest(new_in), _largest(new_out)

    def finding(code, text, ask, txs):
        return Finding("gap", code, text, txs=ids(txs), ask=ask)

    if "TM10" in rules:
        m = case.alerts_of("TM10")[0].get("measured") or {}
        text = ("Units in %s bought for %s were sold back after %s days for %s, inside the %s-day limit. "
                "The proceeds stayed in the customer's own account and nothing was paid to anyone else, "
                "but nothing on file says why the units were sold so soon."
                % (m.get("fund"), gbp(m.get("bought_gbp") or 0), m.get("held_days"), gbp(m.get("redeemed_gbp") or 0), m.get("limit_days")))
        ask = "Ask the customer why they sold the units so soon and for a document that shows the reason, such as a letter from an employer or a bill they had to pay."
        return finding("RFI_PURPOSE_DOCUMENTS", text, ask, case.alert_txs("TM10"))

    if "TM03" in rules:
        txs = case.alert_txs("TM03")
        m = case.alerts_of("TM03")[0].get("measured") or {}
        low, high = min(t["amount_gbp"] for t in txs), max(t["amount_gbp"] for t in txs)
        if m.get("beneficiary"):
            text = ("%d payments of %s to %s went to %s between %s and %s, %s in total, each under the "
                    "£10,000 point where an invoice is needed. The references (%s) read like stages of one "
                    "job, but no contract or invoice is on file."
                    % (len(txs), gbp(low), gbp(high), m["beneficiary"], day(txs[0]), day(txs[-1]),
                       gbp(m.get("total_gbp") or 0), ", ".join(t.get("reference") or "" for t in txs[:2])))
            ask = "Ask the client for the contract or invoice with %s and its payment schedule, showing each stage and amount." % m["beneficiary"]
            return finding("RFI_PURPOSE_DOCUMENTS", text, ask, txs)
        text = ("%d cash deposits of %s to %s were paid in between %s and %s, %s in total, each just under "
                "the reporting limit. No takings or collection records are on file to match them."
                % (len(txs), gbp(low), gbp(high), day(txs[0]), day(txs[-1]), gbp(m.get("total_gbp") or 0)))
        ask = "Ask the customer for the takings or collection records behind each of these deposits."
        return finding("RFI_BUSINESS_RECORDS", text, ask, txs)

    if "TM04" in rules:
        a = case.alerts_of("TM04")[0]
        m = a.get("measured") or {}
        txs = [t for t in case.alert_txs("TM04") if is_open(t)]
        new = [t for t in txs if not known_payers(t)] or txs
        names = sorted(set(t.get("counterparty_name") or "" for t in new))
        refs = sorted(set(t.get("reference") or "" for t in new if t.get("reference")))
        if case.is_business:
            text = ("%d payees were paid in the 30 days, over the limit of %d. %d of them are new to the "
                    "account, for example %s, each paid %s to %s with reference %s. No payment file or "
                    "contracts are on file for them."
                    % (m.get("distinct_counterparties") or len(names), m.get("limit") or 0, len(names), ", ".join(names[:3]),
                       gbp(min(t["amount_gbp"] for t in new)), gbp(max(t["amount_gbp"] for t in new)), refs[0] if refs else "none"))
            ask = "Ask the client for the payment file and the contracts behind these payees, showing who each person is and what they are paid for."
            return finding("RFI_BUSINESS_RECORDS", text, ask, new[:5])
        onward = ""
        if big_out:
            onward = " %s then went to %s on %s (reference %s)." % (gbp(big_out["amount_gbp"]), big_out["counterparty_name"], day(big_out), big_out.get("reference") or "none")
        text = ("%d different people paid the account in the 30 days, over the limit of %d, for example %s. "
                "The references (%s) point to one shared purchase.%s No booking or other document is on file."
                % (m.get("distinct_counterparties") or len(names), m.get("limit") or 0, ", ".join(names[:3]),
                   ", ".join(refs[:3]), onward))
        ask = ("Ask the customer for the booking confirmation or invoice%s, naming the people who paid and the amount each owed."
               % (" from %s" % big_out["counterparty_name"] if big_out else ""))
        return finding("RFI_PURPOSE_DOCUMENTS", text, ask, new[:4] + ([big_out] if big_out else []))

    if "TM05" in rules:
        t = case.alert_txs("TM05")[0]
        said = ""
        for chat in case.docs_of("support_chat"):
            words = flags._customer_lines(chat)
            source = [s for s in re.split(r"(?<=[.!?])\s+", words) if re.search(
                r"\bfrom\b|\bsell|\bsold|\bsale|\bgift|\bsavings?|\bloan|\bwon\b|\binherit", s, re.I)]
            if source:
                said = ' In %s the customer says "%s" but no receipt is on file.' % (chat.id, flags._quote(source[0], 110).rstrip("."))
                break
        text = ("%s in cash was paid in on %s at %s, above the limit for the customer's type.%s Nothing else "
                "about the account is concerning." % (gbp(t["amount_gbp"]), day(t), t.get("location") or "a branch", said))
        ask = "Ask the customer for proof of where the cash came from, such as a signed sale receipt naming the buyer, the item and the price."
        f = finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])
        f.docs = [c.id for c in case.docs_of("support_chat")][:1]
        return f

    if "TM08" in rules:
        txs = [t for t in case.alert_txs("TM08") if is_open(t)]
        t = _largest(txs)
        payers = sorted(set(x.get("counterparty_name") or "" for x in txs))
        if case.is_business and len(payers) >= 2:
            text = ("%s came in from %d companies that are not the client (%s) and %s was paid out within "
                    "48 hours. The references (%s) look like the client's own invoice numbers, which fits its "
                    "business, but no invoices are on file."
                    % (gbp(sum(x["amount_gbp"] for x in txs)), len(payers), ", ".join(payers[:3]),
                       gbp(big_out["amount_gbp"]) + " to " + big_out["counterparty_name"] if big_out else "money",
                       ", ".join(x.get("reference") or "" for x in txs[:2])))
            ask = ("Ask the client for the invoices it issued to %s and the invoice from %s for the payment out."
                   % (", ".join(payers[:3]), big_out["counterparty_name"] if big_out else "the payee"))
            return finding("RFI_BUSINESS_RECORDS", text, ask, txs[:4] + ([big_out] if big_out else []))
        who, ref = t.get("counterparty_name") or "a third party", t.get("reference") or "none"
        if _ONE_OFF.search(who + " " + ref) or _shares_surname(case, t):
            joint = _shares_surname(case, t) and not _ONE_OFF.search(who + " " + ref)
            text = ("%s arrived from %s on %s (reference %s). The account name is not the customer's and "
                    "nothing on file shows %s. Nothing else is concerning."
                    % (gbp(t["amount_gbp"]), who, day(t), ref,
                       "the customer holds that account" if joint else "what the payment is for"))
            ask = ("Ask the customer for a statement for account %s showing who holds it." % (t.get("counterparty_account") or who)
                   if joint else
                   "Ask the customer for the document behind the payment from %s, such as the completion statement or the payer's letter stating the amount." % who)
            return finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])
        text = ("%s arrived from %s on %s (reference %s). %s is not the customer and nothing on file says "
                "who it is or why it paid. Nothing else is concerning." % (gbp(t["amount_gbp"]), who, day(t), ref, who))
        ask = "Ask the customer who %s is and what the payment was for, with the agreement or letter behind it." % who
        return finding("RFI_COUNTERPARTY_DETAILS", text, ask, [t])

    if "TM07" in rules:
        m = case.alerts_of("TM07")[0].get("measured") or {}
        moved = [x for x in case.alert_txs("TM07") if not case.is_spending(x)]
        t = big_in or big_out or _largest(pool) or _largest(moved) or case.alert_tx[0]
        if t["transaction_id"] in covered and not case.is_business:
            text = ("The account was unused for %s days, then %s arrived on %s from an account in the "
                    "customer's own name. A statement on file shows the customer holds that account, but "
                    "identity has not been re-verified since the account went quiet. Nothing else is concerning."
                    % (m.get("dormant_days"), gbp(t["amount_gbp"]), day(t)))
            ask = "Ask the customer to complete identity re-verification before the account is used again."
            return finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])
        if case.is_business:
            pay = " and %s was paid to %s on %s (reference %s)" % (gbp(big_out["amount_gbp"]), big_out["counterparty_name"], day(big_out), big_out.get("reference") or "none") if big_out else ""
            text = ("The account was unused for %s days, then %s came in from the client's own bank on %s%s. "
                    "Nothing on file says why trading stopped or what the payment is for."
                    % (m.get("dormant_days"), gbp(t["amount_gbp"]), day(t), pay))
            ask = "Ask the client why the account was unused and for the invoice or order behind the payment%s." % (
                " to %s" % big_out["counterparty_name"] if big_out else "")
            return finding("RFI_PURPOSE_DOCUMENTS", text, ask, [x for x in (big_in, big_out) if x])
        where = t.get("counterparty_country") or ""
        text = ("The account was unused for %s days, then %s arrived on %s from an account in the customer's "
                "name%s (%s). No statement shows the customer holds that account and identity has not been "
                "re-checked." % (m.get("dormant_days"), gbp(t["amount_gbp"]), day(t),
                                 " in %s" % where if where and where != "United Kingdom" else "", t.get("counterparty_account") or "no account given"))
        ask = "Ask the customer for a statement for that account showing they hold it and the transfer leaving it."
        return finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])

    if "TM02" in rules and big_out and big_in and case.is_self(big_in) and case.is_self(big_out):
        acct = big_in.get("counterparty_account") or "the other account"
        text = ("%s arrived on %s from an account in the customer's own name (%s, reference %s) and %s went back "
                "to an account in the same name on %s (reference %s). Nothing on file confirms why the money was "
                "returned or shows the customer holds that account. Nothing else is concerning."
                % (gbp(big_in["amount_gbp"]), day(big_in), acct, big_in.get("reference") or "none",
                   gbp(big_out["amount_gbp"]), day(big_out), big_out.get("reference") or "none"))
        ask = ("Ask the customer for the document behind the return of the money, such as the cancellation "
               "confirmation, and a statement for %s showing they hold it." % acct)
        return finding("RFI_PURPOSE_DOCUMENTS", text, ask, [big_in, big_out])

    if "TM02" in rules and big_out and big_in:
        text = ("%s arrived from %s on %s (reference %s) and %s went to %s on %s (reference %s). Both look "
                "like ordinary payments, but no document on file shows what either was for."
                % (gbp(big_in["amount_gbp"]), big_in["counterparty_name"], day(big_in), big_in.get("reference") or "none",
                   gbp(big_out["amount_gbp"]), big_out["counterparty_name"], day(big_out), big_out.get("reference") or "none"))
        ask = ("Ask the customer for the agreement or letter from %s and the invoice or receipt from %s."
               % (big_in["counterparty_name"], big_out["counterparty_name"]))
        return finding("RFI_PURPOSE_DOCUMENTS", text, ask, [big_in, big_out])

    t = big_in or _largest(pool) or (case.alert_tx[0] if case.alert_tx else None)
    if t is None:
        return finding("RFI_PURPOSE_DOCUMENTS", "The alerts name no transactions that a document on file explains.",
                       "Ask the customer what the alerted activity was for, with documents.", [])
    who, ref = t.get("counterparty_name") or "an unnamed source", t.get("reference") or "none"
    m = (case.alerts_of("TM01")[0].get("measured") or {}) if case.alerts_of("TM01") else {}
    times = " That took receipts to %.1f times the declared figure of %s." % (m.get("multiple") or 0, gbp(m.get("baseline_gbp") or 0)) if m else ""
    if case.is_business and case.is_self(t):
        text = ("The client paid in %s from its own bank on %s (account %s), far above its usual funding.%s "
                "Nothing on file shows what the money is for." % (gbp(t["amount_gbp"]), day(t), t.get("counterparty_account") or "not given", times))
        ask = "Ask the client what this funding is for, with the order or supplier invoice it will pay."
        return finding("RFI_PURPOSE_DOCUMENTS", text, ask, [t])
    if case.is_self(t):
        text = ("%s arrived on %s from an account in the customer's own name (%s, reference %s).%s No statement "
                "on file shows the customer holds that account." % (gbp(t["amount_gbp"]), day(t), t.get("counterparty_account") or "no account given", ref, times))
        ask = "Ask the customer for a statement for that account showing they hold it and the transfer leaving it."
        return finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])
    text = ("%s arrived from %s on %s (reference %s).%s The payer and reference look ordinary, but no document "
            "on file confirms what the money is." % (gbp(t["amount_gbp"]), who, day(t), ref, times))
    ask = "Ask the customer for the letter or agreement from %s that states the amount and what it is for." % who.replace(" client account", "")
    return finding("RFI_SOURCE_OF_FUNDS", text, ask, [t])


# ------------------------------------------------------------------ wording
_ABBREVIATION = re.compile(r"\b(?:INV|Inv|NO|No|REF|Ref|e\.g|i\.e)\.$")


def _sentences(text):
    """Split text into sentences, without breaking inside 'INV. NO. 123'."""
    out, start = [], 0
    text = text.strip()
    for m in re.finditer(r"(?<=[.!?])[\"')]?\s+(?=[A-Z\"£0-9])", text):
        if _ABBREVIATION.search(text[start:m.start()]):
            continue
        piece = text[start:m.start()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _compose(parts, limit=4):
    """Join finding texts into at most `limit` sentences, keeping the most important first."""
    out = []
    for i, text in enumerate(parts):
        for s in _sentences(text):
            if len(out) >= limit:
                break
            out.append(s.rstrip("."))
        if len(out) >= limit:
            break
    return ". ".join(out) + "."


MATERIAL = 1000.0  # the smallest money limit any of the four SOPs sets


def undocumented_remainder(case, covered):
    """Alerted money that a close would leave with no document behind it.

    A wrong close costs far more than an unnecessary question, so a case closes
    only when nothing material is left over. A payment is left over when no
    document covers it, it is not everyday spending, it is at least £1,000, and
    the other party has never appeared on the account before the review window.
    For a personal customer, money from an account in their own name that has
    never appeared before counts too, because the SOP treats such an account as
    theirs only when a document shows it.
    """
    left = []
    before = [o for o in case.txs if (o.get("booked_at") or "")[:10] < case.window_from]
    for t in case.alert_tx:
        if t["transaction_id"] in covered or case.is_spending(t) or t["amount_gbp"] < MATERIAL:
            continue
        who, acct = t.get("counterparty_name"), t.get("counterparty_account")
        if case.is_self(t):
            seen = any(o.get("counterparty_account") == acct for o in before)
            if not case.is_business and acct and not seen:
                left.append(t)
        elif not (who and any(same_party(o.get("counterparty_name"), who) for o in before)):
            left.append(t)
    return left


def remainder_gap(case, left):
    t = _largest(left)
    who = t.get("counterparty_name") or "an unnamed party"
    verb = "arrived from" if t["direction"] == "in" else "went to"
    text = ("%s %s %s on %s (reference %s) with no document behind it, and that party has no earlier "
            "history on the account. The other alerted activity is documented and nothing is suspicious, "
            "but the case cannot close while this payment is unexplained."
            % (gbp(t["amount_gbp"]), verb, who, day(t), t.get("reference") or "none"))
    ask = "Ask the customer who %s is and what the payment was for, with a document that shows it." % who
    return Finding("gap", "RFI_PURPOSE_DOCUMENTS", text, txs=ids(left), ask=ask)


def held_payment_gap(case, covered):
    """Payments firm: a held payment at or above the SOP's invoice threshold, to anyone
    other than the client, is not released without a matching invoice or contract on file."""
    limit = case.policy.invoice_threshold
    t = case.inst.tx.get(case.held_id) if case.held_id else None
    if not (limit and t) or t["amount_gbp"] < limit or case.is_self(t) or t["transaction_id"] in covered:
        return None
    payee = t.get("counterparty_name") or "the payee"
    text = ("The held payment of %s to %s on %s (reference %s) is at or above %s, the point where the SOP "
            "needs an invoice or contract on file before release. No document on file matches its amount "
            "and payee. Nothing else is concerning."
            % (gbp(t["amount_gbp"]), payee, day(t), t.get("reference") or "none", gbp(limit)))
    ask = "Ask the client for the invoice or contract from %s that this payment settles." % payee
    return Finding("gap", "RFI_PURPOSE_DOCUMENTS", text, txs=[t["transaction_id"]], ask=ask)


def _evidence(findings, case, tx_cap=None):
    """Documents first, then list entries, then the few transactions the reason names."""
    docs, extra, txs = [], [], []
    valid_docs = set(d.id for d in case.docs)
    for f in findings:
        for d in f.docs:
            if d in valid_docs and d not in docs:
                docs.append(d)
        for e in f.extra:
            if e in case.inst.list_entries and e not in extra:
                extra.append(e)
        for t in f.txs:
            if t in case.inst.tx and t not in txs:
                txs.append(t)
    if tx_cap is None:
        tx_cap = 2 if docs else 4
    return docs + extra + txs[:tx_cap]


# ------------------------------------------------------------------ the decision
def decide(inst, row):
    case = Case(inst, row)
    explains = explain.run(case)
    identity = listmatch.review(case, explains)
    explains += [f for f in identity if f.kind == "explain"]
    covered = set(t for f in explains for t in f.covers)

    red = [f for f in identity if f.kind == "flag"]
    red += flags.fraud_reports(case) + flags.mule_admission(case) + flags.shared_device(case) + flags.structuring(case)
    red += flags.dissolved_payer(case) + flags.linked_companies(case) + flags.commission_pool(case)
    red += flags.invoice_mismatch(case) + flags.third_party_investing(case, covered)
    red += flags.unexplained_cash(case, covered)

    open_alerts = [a for a in case.alerts if not resolved(a, case, explains, covered)]
    if any(a.get("rule_id") == "TM06" for a in open_alerts):
        red += flags.high_risk_corridor(case, covered)

    if red:
        red.sort(key=lambda f: (f.rank, f.code))
        code = red[0].code
        lines = _sentences(red[0].text)[:4]
        # a second sign of crime adds a line only when it brings a new fact
        for f in red[1:2]:
            for s in _sentences(f.text):
                amounts = tf.money(s)
                repeats = amounts and all(gbp(a) in " ".join(lines) for a in amounts)
                if len(lines) < 4 and not repeats and s not in lines:
                    lines.append(s)
        reason = ". ".join(s.rstrip(".") for s in lines) + "."
        return _result(case, code, reason, _evidence(red[:2], case), red, explains, open_alerts)

    held = held_payment_gap(case, covered)
    leftover = undocumented_remainder(case, covered) if not open_alerts else []
    if not open_alerts and case.alerts and not held and not leftover:
        used = [f for f in explains if set(f.covers) & set(ids(case.alert_tx)) or f.code in ("RETURNING_CUSTOMER",)]
        used.sort(key=lambda f: (f.rank, f.docs[0] if f.docs else "", f.code))
        main = used[0]
        tm01 = case.alerts_of("TM01")
        own = [f for f in used if f.code == "OWN_ACCOUNT"]
        if tm01 and own and main.code in ("OWN_ACCOUNT", "RETURNING_CUSTOMER"):
            m = tm01[0].get("measured") or {}
            ratio = (m.get("received_gbp") or 0) / (m.get("baseline_gbp") or 1)
            if ratio >= case.policy.own_account_multiple:
                basis = "volume" if case.is_business else "income"
                text = ("%s The transfer is between the customer's own accounts, so nothing is suspicious, but it "
                        "takes receipts in the window to %s, %.1f times the declared %s of %s, and the SOP asks "
                        "for an updated figure at %g times or more. Ask the customer for an updated expected "
                        "monthly %s and what has changed."
                        % (_compose([own[0].text], 2), gbp(m.get("received_gbp") or 0), ratio, basis,
                           gbp(m.get("baseline_gbp") or 0), case.policy.own_account_multiple, basis))
                evidence = _evidence(own, case)
                profile = case.doc("due_diligence_summary")  # where the declared figure is recorded
                if profile:
                    evidence.insert(len([e for e in evidence if e in set(d.id for d in case.docs)]), profile.id)
                return _result(case, "RFI_UPDATED_PROFILE", text, evidence, red, explains, open_alerts)
        # lead with the main ground, add one line for each further document, then the remainder
        keep = 3 if (len(used) == 1 or main.code == "LIST_MATCH_DIFFERENT_PARTY") else 2
        lines = _sentences(main.text)[:keep]
        for f in used[1:3]:
            first = _sentences(f.text)[:1]
            if first and first[0] not in lines:
                lines += first
        if tm01:
            m = tm01[0].get("measured") or {}
            explained = sum(t["amount_gbp"] for t in case.alert_txs("TM01") if t["direction"] == "in" and t["transaction_id"] in covered)
            rest = (m.get("received_gbp") or 0) - explained
            if rest > 0.005:
                lines = lines[:3] + ["The rest of the money received in the window, %s, is within %g times the declared %s"
                                     % (gbp(rest), m.get("limit_multiple") or 0, gbp(m.get("baseline_gbp") or 0))]
        if len(lines) < 3:
            names = sorted(set("%s (%s)" % (a.get("rule_id"), (a.get("rule_name") or "").lower()) for a in case.alerts))
            lines.append("That accounts for every transaction behind the %s alert%s, and nothing else in the "
                         "case is unexplained" % (" and ".join(names), "" if len(case.alerts) == 1 else "s"))
        reason = ". ".join(s.rstrip(".") for s in lines[:4]) + "."
        return _result(case, main.code, reason, _evidence(used[:4], case), red, explains, open_alerts)

    gaps = [f for f in identity if f.kind == "gap"]
    if not gaps and held and not open_alerts:
        gaps = [held]
    if not gaps and leftover:
        gaps = [remainder_gap(case, leftover)]
    if not gaps:
        gaps = [gap(case, open_alerts or case.alerts, covered)]
    g = gaps[0]
    support = [f for f in explains if set(f.covers) & set(ids(case.alert_tx))]
    reason = _compose([g.text], 3).rstrip(".") + ". " + g.ask
    return _result(case, g.code, reason, _evidence([g] + support[:1], case), red, explains, open_alerts)


def _result(case, code, reason, evidence, red, explains, open_alerts):
    reason = re.sub(r"\s+", " ", reason).strip()
    return {
        "case_id": case.id,
        "alert_ids": case.alert_ids,
        "verdict": verdict_for(code),
        "reason_code": code,
        "reason": reason,
        "evidence": evidence,
        "_trace": {
            "rules": case.rules,
            "docs": sorted(d.type for d in case.docs if d.type not in ("due_diligence_summary", "proof_of_address", "contact_note")),
            "flags": [f.code for f in red],
            "explains": sorted(set(f.code for f in explains)),
            "open": [a.get("rule_id") for a in open_alerts],
        },
    }


def _ids(value):
    """The string IDs in a list field; anything else is ignored."""
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def _not_on_file(inst, row):
    """Alerts the case names, and transactions those alerts name, that could not be read."""
    missing = []
    for a in _ids(row.get("alert_ids")):
        alert = inst.alerts.get(a)
        if alert is None:
            missing.append(a)
            continue
        missing += [t for t in _ids(alert.get("transaction_ids")) if t not in inst.tx]
    return missing


def _unassessed(inst, row, why, error=None):
    alert_ids = _ids(row.get("alert_ids"))
    txs = []
    for a in alert_ids:
        txs += [t for t in _ids((inst.alerts.get(a) or {}).get("transaction_ids")) if t in inst.tx][:2]
    out = {
        "case_id": row.get("case_id"), "alert_ids": alert_ids, "verdict": "ESCALATE",
        "reason_code": "ESC_UNEXPLAINED_FUNDS",
        "reason": ("The system could not read %s, so this case has not been fully assessed. It is passed to the "
                   "MLRO for a manual review and must not be closed automatically." % why),
        "evidence": (txs or alert_ids)[:4],
        "_trace": {"error": error or why},
    }
    return out


def safe_decide(inst, row):
    """Never drop a case, and never decide one below ESCALATE on records that could not all be read."""
    try:
        result = decide(inst, row)
    except Exception as exc:  # a case we cannot read is escalated, never closed
        return _unassessed(inst, row, "this case's records (%s)" % type(exc).__name__,
                           "%s: %s" % (type(exc).__name__, exc))
    missing = _not_on_file(inst, row)
    if missing and result["verdict"] != "ESCALATE":
        # the verdict rests only on the alerts and payments that happened to load: a missing one
        # could be what explains the case, or what makes it suspicious, so a person decides
        return _unassessed(inst, row, "%s, which the alerts name but which %s not on file"
                           % (", ".join(missing[:3]) + (" and others" if len(missing) > 3 else ""),
                              "is" if len(missing) == 1 else "are"))
    return result
