"""Red flags: evidence on file that points to crime. Any one of them escalates.

Once there is suspicion the case goes to the MLRO, and the customer is not
asked anything further, because asking risks tipping them off.
"""
import re

from . import textfacts as tf
from .case import Finding, same_party, ids, day, tx_date

gbp = tf.gbp


def _customer_lines(chat):
    """What the customer said in a chat, as one string."""
    said = []
    for line in chat.text.splitlines():
        m = re.match(r"\s*\*\*Customer:?\*\*:?\s*(.*)", line)
        if m:
            said.append(m.group(1).strip())
    return " ".join(said)


def _quote(text, limit=110):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[:cut.rfind(" ")] + "..."


def _sentence_with(text, pattern, limit=280):
    """The first sentence of a note or chat that matches the pattern, ready to quote.

    Reasons quote what the file says. They never restate it in fixed words,
    because a paraphrase can claim more than the note actually records.
    """
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "")) if s.strip()]
    for s in parts:
        if re.search(pattern, s, re.I):
            return _quote(s, limit).rstrip(".").replace('"', "'")
    return _quote(parts[0], limit).rstrip(".").replace('"', "'") if parts else ""


# ---------------------------------------------------------------- mule activity
def fraud_reports(case):
    reports = case.docs_of("sending_bank_fraud_report")
    if not reports:
        return []
    named, txs = [], []
    for doc in reports:
        for t in case.inbound(case.txs):
            if any(tf.close(t["amount_gbp"], m) for m in doc.money) and tf.mentions(doc.text, t.get("counterparty_name") or ""):
                bank = re.sub(r"^Fraud report from ", "", doc.title or "") or "the sending bank"
                named.append("%s (%s) from %s reports that %s paid %s on %s and was scammed"
                             % (doc.id, tf.nice_date(doc.dated), bank, t["counterparty_name"],
                                gbp(t["amount_gbp"]), day(t)))
                txs.append(t["transaction_id"])
                break
    if not named:
        named = ["%s is a fraud report from a sending bank about a payment into this account" % d.id for d in reports]
    docs = [d.id for d in reports]
    job = ""
    passing_on = r"pay into my account|send it on|pass it on|forward|crypto|as my wages|payments? assistant"
    for chat in case.docs_of("support_chat"):
        said = _customer_lines(chat)
        if re.search(passing_on, said, re.I):
            docs.append(chat.id)
            job = ' In %s the customer says "%s".' % (
                chat.id, _sentence_with(said, r"pay into my account|send it on|pass it on|forward|crypto"))
            break
    for doc in case.docs_of("device_export"):
        docs.append(doc.id)
    onward = [t for t in case.outbound() if not case.is_spending(t) and t.get("counterparty_name")]
    dest = ""
    if onward:
        top = max(onward, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
        total = sum(t["amount_gbp"] for t in onward if same_party(t.get("counterparty_name"), top.get("counterparty_name")))
        dest = " %s was then paid on to %s." % (gbp(total), top["counterparty_name"])
        txs.append(top["transaction_id"])
    payers = len(set(tf.norm(t.get("counterparty_name") or "") for t in case.inbound()
                     if t.get("counterparty_name") and not case.is_self(t)))
    text = ("%s.%s The account took money from %d different payers in the window.%s"
            % (", and ".join(named[:2]), job, payers, dest))
    return [Finding("flag", "ESC_MULE_ACTIVITY", text, docs=docs, txs=txs, rank=10)]


def mule_admission(case):
    """The customer says in their own words that they pass on money for someone else."""
    if case.docs_of("sending_bank_fraud_report"):
        return []  # already covered by the fraud reports
    for chat in case.docs_of("support_chat"):
        said = _customer_lines(chat)
        if not re.search(r"pay into my account|send it on|pass it on|forward it|as my wages|crypto account", said, re.I):
            continue
        payers = sorted(set(t["counterparty_name"] for t in case.inbound()
                            if t.get("counterparty_name") and not case.is_self(t)))
        onward = [t for t in case.outbound() if not case.is_spending(t) and t.get("counterparty_name")]
        if len(payers) < 2 or not onward:
            continue
        top = max(onward, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
        text = ('In %s the customer says "%s". %d different people paid into the account in the window and '
                "money was sent on to %s. The account is being used to receive and pass on other people's money."
                % (chat.id, _sentence_with(said, r"pay into my account|send it on|pass it on|forward|crypto"), len(payers), top["counterparty_name"]))
        return [Finding("flag", "ESC_MULE_ACTIVITY", text, docs=[chat.id],
                        txs=ids(case.inbound())[:3] + [top["transaction_id"]], rank=11)]
    return []


# ---------------------------------------------------------------- account misuse
def shared_device(case):
    for doc in case.docs_of("device_export"):
        for row in doc.rows():
            users = [u.strip() for u in (row.get("customers who logged in from it") or "").split(",") if u.strip()]
            if len(users) < 2:
                continue
            countries = row.get("login countries") or ""
            incoming = [t for t in case.inbound() if t.get("counterparty_name") and not case.is_self(t)]
            onward = [t for t in case.outbound() if not case.is_spending(t) and t.get("counterparty_name")]
            flow = ""
            txs = []
            if incoming and onward:
                top = max(onward, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
                same = [t for t in onward if same_party(t.get("counterparty_name"), top.get("counterparty_name"))]
                flow = (" In the same period %d other people paid %s into the account and %s went out "
                        "to %s within hours of each receipt."
                        % (len(set(tf.norm(t["counterparty_name"]) for t in incoming)),
                           gbp(sum(t["amount_gbp"] for t in incoming)), gbp(sum(t["amount_gbp"] for t in same)),
                           top["counterparty_name"]))
                txs = ids(incoming)[:3] + ids(same)[:2]
            text = ("%s shows device %s, first seen %s, was used to log in to %d different customers' "
                    "accounts (%s) from %s.%s Someone other than the customer appears to be operating "
                    "the account."
                    % (doc.id, row.get("device") or "", row.get("first seen") or "", len(users),
                       ", ".join(users), countries, flow))
            return [Finding("flag", "ESC_ACCOUNT_MISUSE", text, docs=[doc.id], txs=txs, rank=20)]
    return []


# ---------------------------------------------------------------- structuring
_THRESHOLD_TALK = re.compile(
    r"aggregat|exempt|threshold|limit|avoid|requirement|report|verif|combin|added (?:up|together)|"
    r"(?:below|under|beneath|less than|smaller)\b|break(?:ing)? (?:down|up)|split|separat|"
    r"\bask|inquir|enquir|question|wanted to know", re.I)


def structuring(case):
    """A member of staff recorded the customer asking how to stay under a limit.

    The note is read loosely on purpose. Staff do not write a note about
    just-under-the-limit transactions unless the customer's behaviour stood
    out, so any note that talks about amounts or limits counts.
    """
    alerts = case.alerts_of("TM03")
    if not alerts:
        return []
    for doc in case.docs_of("staff_note"):
        if not (_THRESHOLD_TALK.search(doc.body) or doc.money):
            continue
        m = alerts[0].get("measured") or {}
        txs = case.alert_txs("TM03")
        count = m.get("count") or m.get("payments") or len(txs)
        where = ""
        if m.get("locations"):
            where = " across %d locations" % m["locations"]
        if m.get("beneficiary"):
            where = " to %s" % m["beneficiary"]
        low, high = min(t["amount_gbp"] for t in txs), max(t["amount_gbp"] for t in txs)
        docs = [doc.id]
        extra = ""
        inv = case.doc("invoice")
        if inv and inv.money and m.get("total_gbp") and tf.close(max(inv.money), m["total_gbp"]):
            docs.append(inv.id)
            extra = (" %s is a single invoice for %s, the sum of the payments, so one debt was paid "
                     "in parts that each stay under the limit." % (inv.id, gbp(max(inv.money))))
        accounts = case.doc("management_accounts")
        if accounts and accounts.money and m.get("total_gbp"):
            turnover = tf.money(accounts.field("turnover") or "")
            if turnover and m["total_gbp"] > turnover[0] * 0.5:
                docs.append(accounts.id)
                extra += (" %s gives turnover of %s for the whole year, against %s paid in over these "
                          "days." % (accounts.id, gbp(turnover[0]), gbp(m["total_gbp"])))
        noted = _sentence_with(doc.body, r"aggregat|exempt|threshold|below|under|beneath|split|break|avoid|"
                                         r"added (?:up|together)|combin|limit")
        text = ('%s, a staff note dated %s, records "%s". The alert covers %d transactions '
                "of %s to %s%s, %s in total, each just under the limit.%s"
                % (doc.id, tf.nice_date(doc.dated), noted, count, gbp(low), gbp(high), where,
                   gbp(m.get("total_gbp") or sum(t["amount_gbp"] for t in txs)), extra))
        return [Finding("flag", "ESC_STRUCTURING", text, docs=docs, txs=ids(txs)[:5], rank=15)]
    return []


# ---------------------------------------------------------------- unexplained funds
def dissolved_payer(case):
    """Money said to be from a company that the register shows no longer existed."""
    for doc in case.docs_of("company_register_extract"):
        status = doc.field("status")
        if "dissolved" not in status.lower():
            continue
        gone = tf.parse_date(status)
        company = doc.field("company") or ""
        paid = [t for t in case.inbound(case.txs) if same_party(t.get("counterparty_name"), company)
                and (not gone or (tx_date(t) and tx_date(t) > gone))]
        if not paid:
            continue
        docs, story = [doc.id], ""
        refs = sorted(set((t.get("reference") or "").strip() for t in paid if t.get("reference")))
        accounts = sorted(set(t.get("counterparty_account") or "" for t in paid))
        for chat in case.docs_of("support_chat"):
            said = _customer_lines(chat)
            if said:
                docs.append(chat.id)
                story = ' In %s the customer calls the money "%s", which does not fit the payment reference %s.' % (
                    chat.id, _sentence_with(said, r"loan|gift|friend|family|borrow|invest|cousin|payment|money|sav"), "/".join(refs) if refs else "given")
                break
        onward = [t for t in case.outbound() if not case.is_spending(t) and t.get("counterparty_name")
                  and not case.is_self(t)]
        moved = ""
        txs = ids(paid)[:3]
        if onward:
            top = max(onward, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
            moved = " %s then went to %s%s on %s." % (
                gbp(top["amount_gbp"]), top["counterparty_name"],
                " in %s" % top["counterparty_country"] if top.get("counterparty_country") not in (None, "United Kingdom") else "",
                day(top))
            txs.append(top["transaction_id"])
        text = ("%s shows %s was dissolved on %s, yet %d payments totalling %s arrived in its name "
                "after that%s.%s%s"
                % (doc.id, company, tf.nice_date(gone) if gone else "an earlier date", len(paid),
                   gbp(sum(t["amount_gbp"] for t in paid)),
                   ", from %d different accounts" % len(accounts) if len(accounts) > 1 else "", story, moved))
        return [Finding("flag", "ESC_UNEXPLAINED_FUNDS", text, docs=docs, txs=txs, rank=25)]
    return []


_SOURCES = (("a sale", r"\bsell|\bsold|\bsale"), ("a gift", r"\bgift"), ("a loan", r"\bloan|\bborrow"),
            ("savings", r"\bsavings?\b|\bsaved"), ("wages", r"\bwages|\bsalary|\btips"),
            ("winnings", r"\bwinnings|\bwon\b"), ("an inheritance", r"\binherit"))


def unexplained_cash(case, covered):
    """Cash with shifting explanations that was sent on within days."""
    cash = [t for t in case.inbound() if t.get("channel") in ("cash_deposit", "cash_topup")
            and t["transaction_id"] not in covered]
    if not cash or not case.alerts_of("TM02"):
        return []
    onward = [t for t in case.outbound() if not case.is_spending(t) and t.get("counterparty_name")
              and not case.is_self(t) and (t.get("booked_at") or "") >= (cash[0].get("booked_at") or "")]
    if not onward:
        return []
    stories, docs = [], []
    # in the order the customer said them, so "first ... and then ..." is true
    for chat in sorted(case.docs_of("support_chat"), key=lambda c: (str(c.dated or ""), c.id)):
        said = _customer_lines(chat)
        for label, pattern in _SOURCES:
            if re.search(pattern, said, re.I) and label not in stories:
                stories.append(label)
        if said:
            docs.append(chat.id)
    top = max(onward, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
    total = sum(t["amount_gbp"] for t in cash)
    conflict = ""
    if len(stories) >= 2:
        conflict = " Across %s the customer gave different sources for the cash, first %s." % (
            " and ".join(docs), " and then ".join(stories))
    elif docs:
        conflict = " The only explanation is the customer's word in %s, with no document behind it." % " and ".join(docs)
    text = ("%s in cash was paid in over %d deposit%s (%s to %s) with nothing on file showing where it "
            "came from.%s %s was then sent to %s%s on %s."
            % (gbp(total), len(cash), "" if len(cash) == 1 else "s", day(cash[0]), day(cash[-1]), conflict,
               gbp(top["amount_gbp"]), top["counterparty_name"],
               " in %s" % top["counterparty_country"] if top.get("counterparty_country") not in (None, "United Kingdom") else "",
               day(top)))
    return [Finding("flag", "ESC_UNEXPLAINED_FUNDS", text, docs=docs,
                    txs=ids(cash)[:3] + [top["transaction_id"]], rank=45)]


# ---------------------------------------------------------------- pass-through
def linked_companies(case):
    """Money that arrives from third parties and leaves to companies the customer's
    own director controls."""
    directors = case.own_directors() if case.is_business else [case.name]
    if not directors:
        return []
    linked = []
    for doc in case.docs_of("company_register_extract"):
        company = doc.field("company")
        if not company or tf.same_name(company, case.name):
            continue
        people = [row.get("officer") or row.get("person with significant control") or "" for row in doc.rows()]
        if any(tf.same_name(p, d) for p in people for d in directors):
            linked.append((doc, company))
    if not linked:
        return []
    paid = [(doc, company, t) for doc, company in linked for t in case.outbound(case.txs)
            if same_party(t.get("counterparty_name"), company) and (t.get("booked_at") or "")[:10] >= case.window_from]
    if not paid:
        return []
    director = next(d for d in directors)
    incoming = [t for t in case.inbound() if t.get("counterparty_name") and not case.is_self(t)
                and not any(same_party(t.get("counterparty_name"), c) for _, c in linked)]
    new_payers = [t for t in incoming if not any(
        same_party(o.get("counterparty_name"), t.get("counterparty_name")) and (o.get("booked_at") or "")[:10] < case.window_from
        for o in case.txs)]
    docs = sorted(set(d.id for d, _, _ in paid))
    own = case.own_register()
    if own:
        docs.append(own.id)  # the document that names the customer's own director
    parts = []
    for doc, company, t in paid[:2]:
        inc = doc.field("incorporated")
        parts.append("%s to %s on %s (%s shows %s is its director and owner%s)"
                     % (gbp(t["amount_gbp"]), company, day(t), doc.id, director,
                        ", incorporated %s" % inc if inc else ""))
    contract = case.doc("consulting_contract")
    cover = ""
    if contract:
        docs.append(contract.id)
        client = contract.field("client")
        fee = contract.money[0] if contract.money else None
        cover = (" The only contract on file, %s, is with %s for %s, and none of the payers is that client."
                 % (contract.id, client or "a different client", gbp(fee) if fee else "a small fee"))
        review = next((r for r in case.reviews if client and tf.mentions(r.get("note") or "", client)), None)
        if review:
            cover += " Review %s covered that one fee only." % review.get("review_id")
    src = ""
    if new_payers:
        src = "%s came in from %d payers with no history on the account (%s), and " % (
            gbp(sum(t["amount_gbp"] for t in new_payers)),
            len(set(tf.norm(t["counterparty_name"]) for t in new_payers)),
            ", ".join(sorted(set(t["counterparty_name"] for t in new_payers))[:3]))
    text = ("%swithin two days the account paid %s. The money passes through to companies the "
            "customer's own director controls.%s" % (src, " and ".join(parts), cover))
    text = text[0].upper() + text[1:]
    return [Finding("flag", "ESC_PASS_THROUGH", text, docs=docs,
                    txs=ids(new_payers)[:3] + [t["transaction_id"] for _, _, t in paid[:2]], rank=30)]


# ---------------------------------------------------------------- third-party funding
def commission_pool(case):
    """A third party funds payouts to many people who share a few addresses."""
    for doc in case.docs_of("payment_file"):
        rows = doc.rows()
        counts, shown = {}, {}
        for row in rows:
            raw = (row.get("address") or "").strip()
            addr = tf.norm(raw)  # count addresses the way explain._shared_addresses does
            if addr:
                counts[addr] = counts.get(addr, 0) + 1
                shown.setdefault(addr, raw)
        if not counts or max(counts.values()) < 3:
            continue
        funders = [t for t in case.inbound() if t.get("counterparty_name") and not case.is_self(t)]
        fund = ""
        txs = []
        if funders:
            f = max(funders, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
            fund = "%s paid %s into the account on %s (reference %s). " % (
                f["counterparty_name"], gbp(f["amount_gbp"]), day(f), f.get("reference") or "none")
            txs.append(f["transaction_id"])
        payees = [t for t in case.outbound() if any(tf.same_name(row.get("payee") or "", t.get("counterparty_name")) for row in rows)]
        txs += ids(payees)[:3]
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        text = ("%s%s, the payment file dated %s, lists %d individual payees but only %d addresses "
                "between them, with %d listed at %s. The client's declared business is \"%s\", which "
                "does not involve paying commission to individuals funded by another company."
                % (fund, doc.id, tf.nice_date(doc.dated), len(rows), len(counts), top[1], shown[top[0]],
                   (case.customer.get("business_activity") or "").rstrip(".")))
        return [Finding("flag", "ESC_THIRD_PARTY_FUNDING", text, docs=[doc.id], txs=txs, rank=40)]
    return []


def third_party_investing(case, covered):
    """An investment account used for other people's money."""
    if not any(t.get("channel") in ("fund_subscription", "fund_redemption") for t in case.txs):
        return []
    payouts = [t for t in case.outbound() if t.get("channel") not in ("fund_subscription",)
               and t.get("counterparty_name") and not case.is_self(t) and t["transaction_id"] not in covered]
    deposits = [t for t in case.inbound() if t.get("channel") not in ("fund_redemption",)
                and t.get("counterparty_name") and not case.is_self(t) and t["transaction_id"] not in covered]
    admission, docs = "", []
    for chat in case.docs_of("support_chat"):
        said = _customer_lines(chat)
        if re.search(r"invest(?:ing)? (?:for|through)|to invest for|through mine|for a few people|"
                     r"cannot open an account|can't open an account", said, re.I):
            admission = ' In %s the customer says "%s".' % (
                chat.id, _sentence_with(said, r"invest(?:ing)? (?:for|through)|to invest for|through mine|for a few people|open an account"))
            docs.append(chat.id)
            break
    if not payouts and not admission:
        return []
    redemption = case.alerts_of("TM10")
    txs = ids(deposits)[:3] + ids(payouts)[:2]
    if redemption and payouts:
        m = redemption[0].get("measured") or {}
        p = payouts[-1]
        text = ("Units in %s bought for %s were sold back %s days later for %s, and the %s was paid "
                "out to %s on %s, not to the customer.%s"
                % (m.get("fund") or "a fund", gbp(m.get("bought_gbp") or 0), m.get("held_days"),
                   gbp(m.get("redeemed_gbp") or 0), gbp(p["amount_gbp"]), p["counterparty_name"], day(p), admission))
        return [Finding("flag", "ESC_EARLY_REDEMPTION", text, docs=docs,
                        txs=ids(case.alert_txs("TM10"))[-2:] + [p["transaction_id"]], rank=32)]
    parts = []
    if deposits:
        parts.append("%d deposits totalling %s came from other people (%s)" % (
            len(deposits), gbp(sum(t["amount_gbp"] for t in deposits)),
            ", ".join(sorted(set(t["counterparty_name"] for t in deposits))[:3])))
    if payouts:
        p = payouts[-1]
        parts.append("%s was withdrawn to %s on %s, not to an account in the customer's name" % (
            gbp(p["amount_gbp"]), p["counterparty_name"], day(p)))
    joined = ". ".join(p[0].upper() + p[1:] for p in parts)
    text = "%s.%s" % (joined, admission) if parts else admission.strip()
    return [Finding("flag", "ESC_THIRD_PARTY_FUNDING", text, docs=docs, txs=txs, rank=40)]


# ---------------------------------------------------------------- invoices that do not fit
_STOP = set("and the for of from with one two three four five uk ltd limited co goods services service "
            "imports import buys sells stock suppliers supplier overseas firms shops clients client "
            "order first second shipment consignment quarterly".split())


def _words(text):
    return set(w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP)


def invoice_mismatch(case):
    """Invoices on file that do not support what the money was for."""
    if not case.is_business:
        return []
    activity = case.customer.get("business_activity") or ""
    expected = case.declared.get("expected_countries") or []
    for doc in case.docs_of("supplier_invoices"):
        if case.docs_of("staff_note"):
            continue  # judged with the staff note, as a corridor question
        supplier = doc.field("supplier")
        country = supplier.split(",")[-1].strip() if "," in supplier else ""
        goods = " ".join((row.get("goods") or "") for row in doc.rows())
        problems = []
        if goods and not (_words(goods) & _words(activity)):
            sample = (doc.rows()[0].get("goods") or "").strip()
            problems.append('the goods invoiced ("%s") have nothing to do with the declared business, "%s"'
                            % (sample, activity.rstrip(".")))
        if country and expected and country not in expected:
            problems.append("the supplier is in %s, which is not among the countries the client declared (%s)"
                            % (country, ", ".join(expected)))
        late = [d for row in doc.rows() for d in tf.dates(row.get("dated") or "") if doc.dated and d > doc.dated]
        funding = [t for t in case.inbound() if case.is_self(t) and t.get("counterparty_account")]
        if not problems:
            continue
        fund = ""
        txs = []
        if funding:
            f = max(funding, key=lambda t: (t["amount_gbp"], t["transaction_id"]))
            fund = " They are the only support for the %s paid in on %s." % (gbp(f["amount_gbp"]), day(f))
            txs = [f["transaction_id"]]
        text = ("%s holds %d invoices from %s totalling %s, but %s.%s%s"
                % (doc.id, len(doc.rows()), supplier or "the supplier", gbp(sum(doc.money)),
                   ". Also, ".join(problems), fund,
                   " One invoice is dated after the document it appears in." if late else ""))
        return [Finding("flag", "ESC_INVOICE_MISMATCH", text, docs=[doc.id], txs=txs, rank=35)]
    return []


# ---------------------------------------------------------------- high-risk corridor
def high_risk_corridor(case, covered):
    """Payments to or from a higher-risk country that nothing on file explains."""
    open_txs = [t for t in case.alert_txs("TM06") if t["transaction_id"] not in covered]
    if not open_txs:
        return []
    m = (case.alerts_of("TM06")[0].get("measured") or {})
    country = m.get("countries") or open_txs[0].get("counterparty_country") or "a higher-risk country"
    outward = [t for t in open_txs if t["direction"] == "out"]
    inward = [t for t in open_txs if t["direction"] == "in"]
    docs, notes = [], []
    for doc in case.docs_of("staff_note"):
        docs.append(doc.id)
        notes.append('%s, a staff note dated %s, records "%s"' % (
            doc.id, tf.nice_date(doc.dated),
            _sentence_with(doc.body, r"unable|unwilling|could not|couldn't|cannot|did not|no (?:reason|explanation)|justif|\bwhy\b")))
    for doc in case.docs_of("supplier_invoices"):
        goods = sorted(set((row.get("goods") or "").strip() for row in doc.rows() if row.get("goods")))
        activity = (case.customer.get("business_activity") or "").rstrip(".")
        if goods and not (_words(" ".join(goods)) & _words(activity)):
            docs.append(doc.id)
            notes.append('the invoices in %s are for "%s", which does not fit the declared business, "%s"'
                         % (doc.id, goods[0], activity))
    for chat in case.docs_of("support_chat"):
        said = _customer_lines(chat)
        if said:
            docs.append(chat.id)
            notes.append('the only explanation is the customer\'s word in %s ("%s"), with no document' % (chat.id, _sentence_with(said, r"loan|gift|friend|family|borrow|invest|cousin|payment|money|sav")))
            break
    funders = [t for t in case.inbound() if t.get("counterparty_name") and not case.is_self(t)
               and t not in open_txs and t["transaction_id"] not in covered
               and not same_party(t.get("counterparty_name"), case.customer.get("employer"))]
    recent = [t for t in funders if not any(
        same_party(o.get("counterparty_name"), t.get("counterparty_name")) and (o.get("booked_at") or "")[:10] < case.window_from
        for o in case.txs)]
    parts = []
    if outward:
        payees = sorted(set(t["counterparty_name"] for t in outward if t.get("counterparty_name")))
        parts.append("%s went to %s in %d payment%s to %s" % (
            gbp(sum(t["amount_gbp"] for t in outward)), country, len(outward), "" if len(outward) == 1 else "s",
            ", ".join(payees[:4])))
    if inward:
        payers = sorted(set(t["counterparty_name"] for t in inward if t.get("counterparty_name")))
        parts.append("%s came from %s, sent by %s" % (gbp(sum(t["amount_gbp"] for t in inward)), country, ", ".join(payers[:4])))
    lead = " and ".join(parts)
    lead = lead[0].upper() + lead[1:] if lead else "Payments moved to or from %s" % country
    fund = ""
    if recent and outward:
        fund = " The money came from %d people with no earlier history on the account (%s) in the days before." % (
            len(set(tf.norm(t["counterparty_name"]) for t in recent)),
            ", ".join(sorted(set(t["counterparty_name"] for t in recent))[:3]))
    declared = ", ".join(case.declared.get("expected_countries") or []) or "none"
    text = ("%s, a higher-risk country the customer did not declare (the declared countries are %s).%s %s."
            % (lead, declared, fund, (notes[0][0].upper() + notes[0][1:]) if notes else
               "Nothing on file documents who the other parties are or what the payments are for"))
    if len(notes) > 1:
        text += " Also, %s." % notes[1]
    return [Finding("flag", "ESC_HIGH_RISK_CORRIDOR", text, docs=docs,
                    txs=ids(open_txs)[:4] + ids(recent)[:2], rank=38)]
