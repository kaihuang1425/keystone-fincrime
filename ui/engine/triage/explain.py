"""Explanations: documents on file that account for specific transactions.

Every function here returns Findings of kind "explain". A document never
explains anything by being present. It explains a transaction only when its
own facts (amount, party, account, date) match that transaction.
"""
import re

from . import textfacts as tf
from .case import Finding, same_party, ids, day, tx_date

gbp = tf.gbp


def _party(t):
    return (t.get("counterparty_name") or "").replace(" client account", "")


def _names(doc, t):
    """The document names the transaction's counterparty."""
    return bool(_party(t)) and tf.mentions(doc.text, _party(t))


def _for_someone_else(doc, case, labels):
    """A recipient field on the document names someone other than the customer.

    Letters are worded freely and often do not name the customer at all, so a
    missing name proves nothing. A named recipient who is someone else does.
    """
    for label in labels:
        value = doc.field(label)
        if value and not tf.mentions(value, case.name):
            return True
    return False


_GENERIC_SALUTATION = set(
    "sir madam sirs customer client tenant employee colleague colleagues beneficiary guest investor student "
    "policyholder claimant applicant member subscriber resident leaseholder holder account valued former "
    "team sales accounts finance procurement department payable director directors shareholder partner "
    "partners supplier buyer seller borrower executor executors trustee trustees friend friends all "
    "mr mrs ms miss mx dr prof professor messrs esq and or the our of to at for in on behalf attention attn "
    "family household both everyone whom it may concern".split())


def _addressed_to_another(doc, case):
    """The letter opens 'Dear <name>' and that name is a specific someone who is not the customer.

    'Dear Tenant' or 'Dear Sir/Madam' names nobody and proves nothing either way.
    'Dear Jo Example' on a letter in another customer's file is not that customer's letter.
    """
    m = re.search(r"^\W*Dear\s+([^,\n:]+)", doc.text, re.M | re.I)
    if not m:
        return False
    suffixes = {"ltd", "limited", "llp", "plc", "co", "company", "inc"}  # shared by unrelated companies

    def words(s):
        return set(w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 1) - suffixes

    named, own = words(m.group(1)) - _GENERIC_SALUTATION, words(case.name)
    if not named:
        return False
    # The customer's letter uses only words from the customer's name ("Dear Mr Field"), or
    # carries the whole name ("Dear Sam Field and Alex Field"). Sharing "Furniture Imports"
    # with the customer does not make "Dear Other Furniture Imports Ltd" the customer's letter.
    return not (named <= own or own <= named)


def _customer_is_buyer(doc, case):
    """A sale receipt puts the customer on the paying side: 'to <customer>', 'Buyer: <customer>'
    or 'received from <customer>'. Such a receipt shows the customer spent money, not received it."""
    name = re.escape(case.name)
    return bool(re.search(r"\bbuyer\W{0,6}%s\b|\bto\s+%s\b|\breceived\s+from\s+%s\b" % (name, name, name),
                          doc.text, re.I))


def _dated_by(doc, t, slack=0):
    """The document is dated no later than the transaction (plus slack days)."""
    d, when = doc.dated, tx_date(t)
    return bool(d and when) and (d - when).days <= slack


# ---------------------------------------------------------------- one-off events
# "the estate of the late Jo Example": the letter itself says whose estate it is about
_ESTATE_NAMED = re.compile(r"(?i:estate\s+of\s+(?:the\s+late\s+)?)(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?[A-Z][\w.'-]+\s+[A-Z][\w'-]+")


def one_off_events(case):
    """A letter from the payer states the amount that then arrived."""
    out = []
    kinds = {
        "solicitor_letter": "a letter from %s confirming a distribution of %s from an estate",
        "insurer_letter": "a letter from %s accepting an insurance claim and confirming a payment of %s",
        "settlement_letter": "a letter from %s confirming a settlement payment of %s",
        "completion_statement": "a completion statement from %s showing %s due to the customer from a property sale",
    }
    for doc in case.docs_of(*sorted(kinds)):
        if _addressed_to_another(doc, case):
            continue
        if doc.type == "insurer_letter" and not tf.mentions(doc.text, case.name):
            continue  # an insurer names the person it pays, so a letter without the name is not this customer's
        for t in case.inbound():
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            if not _names(doc, t) or not _dated_by(doc, t):
                continue
            detail = ""
            ref = t.get("reference") or ""
            m = re.search(r"ESTATE OF (.+)", ref, re.I)
            if m:
                if tf.mentions(doc.text, m.group(1)):
                    detail = ", the estate of %s" % m.group(1).title()
                elif not tf.mentions(doc.text, m.group(1).split()[-1]) and _ESTATE_NAMED.search(doc.text):
                    continue  # the payment names one estate and the letter names another
            m = re.search(r"CLAIM\W*(\d+)", ref, re.I)
            if m:
                quoted = re.findall(r"CLAIM[^\w£]*(\d+)", doc.text, re.I)
                if m.group(1) in quoted:
                    detail = ", reference CLAIM %s" % m.group(1)
                elif any(len(q) >= 4 for q in quoted) and m.group(1) not in re.findall(r"\d+", doc.text):
                    continue  # the letter quotes a claim number and the payment's number is nowhere in it
            if doc.type == "completion_statement":
                if _for_someone_else(doc, case, ("client",)):
                    continue
                prop = doc.field("property")
                detail = ", for %s" % prop if prop else ""
            text = ("%s, dated %s, is %s%s. The same amount arrived from %s on %s (%s)."
                    % (doc.id, tf.nice_date(doc.dated), kinds[doc.type] % (_party(t), gbp(t["amount_gbp"])),
                       detail, t["counterparty_name"], day(t), t["transaction_id"]))
            out.append(Finding("explain", "DOCUMENTED_EVENT", text, docs=[doc.id],
                               txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                               rules=("TM01", "TM07", "TM08"), rank=30))
    return out


# ---------------------------------------------------------------- cash from a sale
_REG = re.compile(r"\b[A-Z]{2}\d{2}\s?[A-Z]{3}\b")


def cash_sales(case):
    """A signed sale receipt for the same amount as the cash paid in."""
    out = []
    for doc in case.docs_of("vehicle_sale_receipt", "sale_receipt"):
        advert = case.doc("advert")
        # the receipt itself must name the customer, and as the seller, not the buyer
        if not tf.mentions(doc.text, case.name) or _customer_is_buyer(doc, case):
            continue
        if _for_someone_else(doc, case, ("seller",)):
            continue
        for t in case.inbound():
            if t.get("channel") not in ("cash_deposit", "cash_topup"):
                continue
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money) or not _dated_by(doc, t):
                continue
            docs, proof = [doc.id], ""
            regs = _REG.findall(doc.text)
            schedule = case.doc("insurance_schedule")
            if regs:
                if not (schedule and regs[0] in schedule.text and tf.mentions(schedule.text, case.name)):
                    continue  # nothing shows the customer owned the vehicle sold
                docs.append(schedule.id)
                proof = " %s shows %s insured the same vehicle, %s." % (schedule.id, case.name, regs[0])
            if advert and tf.mentions(advert.text, case.name):
                docs.append(advert.id)
                proof += " %s is the advert for the item." % advert.id
            buyer = doc.field("buyer")
            text = ("%s, dated %s, is a signed receipt for %s in cash paid to %s%s. "
                    "The same amount was paid in on %s.%s"
                    % (doc.id, tf.nice_date(doc.dated), gbp(t["amount_gbp"]), case.name,
                       " by %s" % buyer if buyer else "", day(t), proof))
            out.append(Finding("explain", "DOCUMENTED_EVENT", text, docs=docs,
                               txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                               rules=("TM01", "TM05"), rank=30))
    return out


def cash_redeposit(case):
    """Cash paid back in after an earlier withdrawal of the same amount that the
    institution's own records show and an earlier review already looked at."""
    out = []
    chats = case.docs_of("support_chat")
    for t in case.inbound():  # any alerted cash paid in, whichever rule raised it
        if t.get("channel") not in ("cash_deposit", "cash_topup"):
            continue
        earlier = [w for w in case.txs
                   if w.get("direction") == "out" and w.get("channel") == "cash_withdrawal"
                   and tf.close(w["amount_gbp"], t["amount_gbp"])
                   and (w.get("booked_at") or "") < (t.get("booked_at") or "")]
        chat = next((c for c in chats if any(tf.close(t["amount_gbp"], m) for m in c.money)), None)
        if chat is None and chats and not any(c.money for c in chats):
            chat = chats[0]  # the customer gave no figure, so nothing contradicts the records
        review = next((r for r in case.reviews
                       if r.get("rule_id") == "TM05" and "withdraw" in (r.get("note") or "").lower()
                       and earlier and (r.get("reviewed_on") or "") >= (earlier[-1].get("booked_at") or "")[:10]), None)
        if not (earlier and chat and review):
            continue
        w = earlier[-1]
        text = ("The account's own history shows %s withdrawn in cash on %s (%s), which review %s "
                "closed on %s. In %s the customer says the purchase fell through, and the %s paid "
                "in on %s is the same amount coming back."
                % (gbp(w["amount_gbp"]), day(w), w["transaction_id"], review.get("review_id"),
                   tf.nice_date(review.get("reviewed_on")), chat.id, gbp(t["amount_gbp"]), day(t)))
        out.append(Finding("explain", "WITHIN_PROFILE", text, docs=[chat.id],
                           txs=[t["transaction_id"], w["transaction_id"]],
                           extra=[review.get("review_id")], covers=[t["transaction_id"]],
                           rules=("TM01", "TM05"), rank=35))
    return out


# ---------------------------------------------------------------- loan and purchase
def loan_and_purchase(case):
    out = []
    loan, invoice = case.doc("loan_agreement"), case.doc("dealer_invoice")
    if loan and tf.mentions(loan.text, case.name) and not _for_someone_else(loan, case, ("borrower",)):
        for t in case.inbound():
            if any(tf.close(t["amount_gbp"], m) for m in loan.money) and _names(loan, t) and _dated_by(loan, t):
                text = ("%s is a loan agreement between %s and %s for %s, and that amount arrived "
                        "from the lender on %s." % (loan.id, case.name, _party(t), gbp(t["amount_gbp"]), day(t)))
                out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[loan.id],
                                   txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                                   rules=("TM01", "TM02"), rank=42))
    if invoice and not _for_someone_else(invoice, case, ("customer", "bill to", "buyer")):
        for t in case.outbound():
            if any(tf.close(t["amount_gbp"], m) for m in invoice.money) and _names(invoice, t) and _dated_by(invoice, t, 1):
                item = invoice.field("vehicle", "description", "goods")
                text = ("%s is an invoice from %s to %s for %s%s, paid on %s."
                        % (invoice.id, _party(t), case.name, gbp(t["amount_gbp"]),
                           " (%s)" % item if item else "", day(t)))
                out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[invoice.id],
                                   txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                                   rules=("TM01", "TM02"), rank=40))
    return out


# ---------------------------------------------------------------- own accounts
def _holders(doc):
    raw = doc.field("account holder")
    return [h.strip() for h in re.split(r"\s+and\s+|,|&", raw) if h.strip()]


def own_accounts(case):
    """A statement on file shows the customer holds the account on the other side."""
    out = []
    statements = case.docs_of("bank_statement")
    for doc in statements:
        holders = _holders(doc)
        if not any(tf.same_name(h, case.name) for h in holders):
            continue
        joint = len(holders) > 1
        account_name = doc.field("account name")
        hits = []
        for t in case.txs:
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            acct = t.get("counterparty_account") or ""
            if not tf.same_account(doc.text, acct):
                continue
            who = t.get("counterparty_name") or ""
            if not (tf.same_name(who, case.name) or (account_name and tf.same_name(who, account_name))):
                continue
            when, dated = tx_date(t), doc.dated
            if dated and when and abs((dated - when).days) > 45:
                continue
            hits.append(t)
        for t in hits:
            covers = [t["transaction_id"]]
            chain = ""
            if t["direction"] == "out" and case.is_business:
                # a business client funds its account from its own bank as a matter of course, so
                # funding that was moved straight on to this documented account is the same transfer.
                # A personal customer's other account needs its own statement.
                for f in case.inbound():
                    gap = (tx_date(t) - tx_date(f)).days if tx_date(t) and tx_date(f) else 99
                    if (case.is_self(f) and f.get("counterparty_account") and 0 <= gap <= 5
                            and f["amount_gbp"] >= t["amount_gbp"] * 0.999
                            and t["amount_gbp"] >= f["amount_gbp"] * 0.9):
                        covers.append(f["transaction_id"])
                        chain = (" It was funded by %s from the customer's own bank on %s (%s)."
                                 % (gbp(f["amount_gbp"]), day(f), f["transaction_id"]))
            holder_text = ("%s and %s hold it jointly" % (holders[0], holders[1]) if joint
                           else "%s holds it" % case.name)
            verb = "received from" if t["direction"] == "in" else "sent to"
            acct = t.get("counterparty_account") or ""
            acct = acct if acct.lower().startswith(("account", "iban")) else "account " + acct
            text = ("%s is a statement from %s for %s and shows %s. It records the %s "
                    "%s that account on %s (%s).%s"
                    % (doc.id, doc.field("bank") or (doc.title.split(" from ")[-1] if " from " in doc.title else "the other bank"), acct,
                       holder_text, gbp(t["amount_gbp"]), verb, day(t), t["transaction_id"], chain))
            code, docs, rank = "OWN_ACCOUNT", [doc.id], 20
            letter = case.doc("customer_letter")
            if (letter and t["direction"] == "out" and letter.dated and tx_date(t) and letter.dated <= tx_date(t)
                    and tf.same_account(letter.text, t.get("counterparty_account") or "")):
                # the customer told the institution in advance where withdrawals should go
                code, docs, rank = "WITHIN_PROFILE", [letter.id, doc.id], 19
                text = ("%s is the customer's letter of %s saying they have moved abroad and asking for "
                        "withdrawals to go to their account %s. %s"
                        % (letter.id, tf.nice_date(letter.dated),
                           (t.get("counterparty_account") or "").replace("account ", ""), text))
            email = case.doc("customer_email")
            if email and tf.same_account(email.text, t.get("counterparty_account") or ""):
                docs.append(email.id)
                text += " %s is the customer's email of %s about the same transfer and the same account." % (
                    email.id, tf.nice_date(email.dated))
            contract = case.doc("employment_contract")
            abroad = (t.get("counterparty_country") or "United Kingdom") != "United Kingdom"
            if (contract and abroad and t["direction"] == "in" and tf.mentions(contract.text, case.name)
                    and contract.dated and tx_date(t) and contract.dated <= tx_date(t)):
                docs.append(contract.id)
                text += (" %s is the customer's employment contract, dated %s, for work in %s paid into a "
                         "local account." % (contract.id, tf.nice_date(contract.dated), t["counterparty_country"]))
            out.append(Finding("explain", code, text, docs=docs, txs=covers,
                               covers=covers, rules=("TM01", "TM02", "TM06", "TM07", "TM08"), rank=rank))
    return out


def returning_customer(case):
    """A dormant account: the customer was re-verified before the money moved."""
    doc = case.doc("reverification_record")
    if not doc or not case.alerts_of("TM07"):
        return []
    first = min((tx_date(t) for t in case.alert_txs("TM07") if tx_date(t)), default=None)
    if not (doc.dated and first and doc.dated <= first):
        return []
    said = ""
    m = re.search(r"The (?:customer|directors?) said ([^.]+)\.", doc.body)
    if m:
        said = " and records that the customer said %s" % m.group(1)
    text = ("%s shows identity was re-verified on %s, before the dormant account was used again%s."
            % (doc.id, tf.nice_date(doc.dated), said))
    return [Finding("explain", "RETURNING_CUSTOMER", text, docs=[doc.id], rules=("TM07",), rank=10)]


# ---------------------------------------------------------------- refunds
def refunds(case):
    out = []
    for doc in case.docs_of("venue_email", "credit_note"):
        if _addressed_to_another(doc, case) or _for_someone_else(doc, case, ("customer", "client", "bill to", "buyer")):
            continue
        for t in case.inbound():
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            if not _names(doc, t) or not _dated_by(doc, t):
                continue
            payer = _party(t)
            paid_before = [p for p in case.txs if p["direction"] == "out"
                           and same_party(p.get("counterparty_name"), payer)
                           and (p.get("booked_at") or "") < (t.get("booked_at") or "")
                           and p["amount_gbp"] >= t["amount_gbp"] - 0.005]
            review = next((r for r in case.reviews if tf.mentions(r.get("note") or "", payer)
                           and (r.get("reviewed_on") or "") <= (t.get("booked_at") or "")[:10]), None)
            if not (paid_before or review):
                continue  # nothing shows the customer ever paid this party
            basis, extra, txs = "", [], [t["transaction_id"]]
            if paid_before:
                p = paid_before[-1]
                basis = " The customer paid %s to %s on %s (%s)." % (gbp(p["amount_gbp"]), payer, day(p), p["transaction_id"])
                txs.append(p["transaction_id"])
            if review:
                basis += " Review %s on %s covered the original payment to %s." % (
                    review.get("review_id"), tf.nice_date(review.get("reviewed_on")), payer)
                extra.append(review.get("review_id"))
            ref = re.search(r"BOOKING\s*\d+", t.get("reference") or "", re.I)
            text = ("%s from %s, dated %s, confirms a refund of %s%s. The same amount arrived from "
                    "%s on %s.%s"
                    % (doc.id, payer, tf.nice_date(doc.dated), gbp(t["amount_gbp"]),
                       " for %s" % ref.group(0).upper() if ref and tf.norm(ref.group(0)) in tf.norm(doc.text) else "",
                       payer, day(t), basis))
            out.append(Finding("explain", "REFUND_OF_EARLIER_PAYMENT", text, docs=[doc.id], txs=txs,
                               extra=extra, covers=[t["transaction_id"]],
                               rules=("TM01", "TM02", "TM06", "TM08"), rank=15))
    doc = case.doc("cancellation_confirmation")
    if doc and not _addressed_to_another(doc, case):
        for t in case.in_window("out"):
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            if not (case.is_self(t) and tf.same_account(doc.text, t.get("counterparty_account") or "")):
                continue
            paid_in = [f for f in case.in_window("in") if tf.close(f["amount_gbp"], t["amount_gbp"])
                       and case.is_self(f) and f.get("counterparty_account") == t.get("counterparty_account")
                       and (f.get("booked_at") or "") <= (t.get("booked_at") or "")]
            if not paid_in:
                continue
            f = paid_in[0]
            text = ("%s confirms the customer cancelled within the cooling-off period and that the "
                    "%s subscription received on %s was returned to account %s, held in the "
                    "customer's name. The refund on %s went to the account the money came from."
                    % (doc.id, gbp(t["amount_gbp"]), day(f), t.get("counterparty_account"), day(t)))
            out.append(Finding("explain", "REFUND_OF_EARLIER_PAYMENT", text, docs=[doc.id],
                               txs=[f["transaction_id"], t["transaction_id"]],
                               covers=[f["transaction_id"], t["transaction_id"]],
                               rules=("TM01", "TM02"), rank=15))
    return out


def tenancy_deposits(case):
    """A deposit returned by one letting agent and a holding deposit paid to the next."""
    out = []
    for doc in case.docs_of("deposit_return_letter", "holding_deposit_receipt"):
        if _addressed_to_another(doc, case):
            continue
        want = "in" if doc.type == "deposit_return_letter" else "out"
        for t in case.in_window():
            if t["direction"] != want or not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            if not _names(doc, t) or not _dated_by(doc, t, 1):
                continue
            what = ("the return of a tenancy deposit of %s from %s" if want == "in"
                    else "a holding deposit of %s paid to %s") % (gbp(t["amount_gbp"]), _party(t))
            text = "%s, dated %s, confirms %s, which matches the payment on %s." % (
                doc.id, tf.nice_date(doc.dated), what, day(t))
            out.append(Finding("explain", "DOCUMENTED_EVENT", text, docs=[doc.id],
                               txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                               rules=("TM01", "TM02"), rank=30))
    return out


# ---------------------------------------------------------------- collections
def collections(case):
    """Money collected from named people for one booking, then paid to the supplier."""
    doc = case.doc("booking_confirmation")
    if not doc or not tf.mentions(doc.text, case.name) or _for_someone_else(doc, case, ("lead traveller",)):
        return []
    travellers = [m.strip() for m in re.findall(r"^\s*\d+\.\s+(.+?)\s*$", doc.text, re.M)]
    if not travellers or not doc.money:
        return []
    per_person, total = doc.money[0], max(doc.money)
    paid = [t for t in case.in_window("in")
            if tf.close(t["amount_gbp"], per_person)
            and any(tf.same_name(t.get("counterparty_name"), n) for n in travellers)]
    onward = [t for t in case.in_window("out")
              if tf.close(t["amount_gbp"], total)
              and (tf.same_account(doc.text, t.get("counterparty_account") or "") or _names(doc, t))]
    if not paid or not onward:
        return []
    t = onward[0]
    trip = doc.field("trip")
    text = ("%s is a booking for %s%s at %s each, %s in total, with %s as lead traveller. "
            "%d of the people who paid in are named travellers and each paid %s. The %s paid to %s "
            "on %s matches the booking total and the account on the confirmation."
            % (doc.id, "%d travellers" % len(travellers), " (%s)" % trip if trip else "",
               gbp(per_person), gbp(total), case.name, len(paid), gbp(per_person),
               gbp(t["amount_gbp"]), _party(t), day(t)))
    covers = ids(paid) + ids(onward)
    return [Finding("explain", "COLLECTION_DOCUMENTED", text, docs=[doc.id],
                    txs=ids(onward) + ids(paid)[:4], covers=covers,
                    rules=("TM01", "TM02", "TM04"), rank=12)]


# ---------------------------------------------------------------- business records
def business_records(case):
    """Each cash deposit equals one line of the customer's own takings records."""
    out = []
    for doc in case.docs_of("cash_collection_reports", "cash_reconciliation", "takings_book"):
        heading = doc.text.strip().splitlines()[0] if doc.text.strip() else ""
        named = re.search(r"\b(?:from|by|of)\s+(.+?(?:Ltd|Limited|LLP|plc|PLC))\b", heading)
        if named and not tf.mentions(named.group(1), case.name):
            continue  # the records are headed with another company's name
        rows = doc.rows()
        cash = [t for t in case.inbound() if t.get("channel") in ("cash_deposit", "cash_topup")]
        used, matched = set(), []
        for t in cash:
            for i, row in enumerate(rows):
                if i in used:
                    continue
                cells = list(row.values())
                amounts = [m for c in cells for m in tf.money(c)]
                # the banked amount is the row total, the largest figure on the line
                banked = tf.money(row.get("total") or row.get("cash counted") or row.get("cash topped up") or "")
                if not banked or not tf.close(t["amount_gbp"], banked[0]):
                    continue
                if banked[0] > max(amounts) + 0.005:
                    continue
                row_dates = [d for c in cells for d in tf.dates(c)]
                when = tx_date(t)
                if row_dates and when and not any(0 <= (when - d).days <= 3 for d in row_dates):
                    continue
                used.add(i)
                matched.append(t)
                break
        if not matched or len(matched) < len(cash):
            continue
        label = {"cash_collection_reports": "machine collection reports",
                 "cash_reconciliation": "cash reconciliation sheets",
                 "takings_book": "daily takings book"}[doc.type]
        docs = [doc.id]
        support = ""
        for extra_type, words in (("cash_handling_procedure", "sets out that each site banks its own takings separately"),
                                  ("ticket_report", "gives the event dates and confirms gate and bar sales were in cash")):
            extra_doc = case.doc(extra_type)
            if extra_doc:
                docs.append(extra_doc.id)
                support = " %s %s." % (extra_doc.id, words)
        total = sum(t["amount_gbp"] for t in matched)
        text = ("%s, the customer's %s, lists %d amounts that match the %d cash deposits line by "
                "line, from %s on %s to %s on %s, %s in total.%s"
                % (doc.id, label, len(matched), len(matched), gbp(matched[0]["amount_gbp"]),
                   day(matched[0]), gbp(matched[-1]["amount_gbp"]), day(matched[-1]), gbp(total), support))
        out.append(Finding("explain", "BUSINESS_RECORDS_RECONCILE", text, docs=docs,
                           txs=ids(matched)[:6], covers=ids(matched),
                           rules=("TM01", "TM03", "TM05"), rank=12))
    return out


# ---------------------------------------------------------------- invoices and contracts
def invoices(case):
    """An invoice, contract schedule or payment file matches amount and payee."""
    out = []
    contract = case.doc("supply_contract")
    for doc in case.docs_of("hospital_invoice", "supplier_invoice", "carrier_invoice", "invoice", "receipt"):
        if _for_someone_else(doc, case, ("buyer", "bill to", "customer")):
            continue  # an invoice made out to another party does not explain this customer's payment
        for t in case.outbound():
            if not any(tf.close(t["amount_gbp"], m) for m in doc.money):
                continue
            if not _names(doc, t) or not _dated_by(doc, t, 1):
                continue
            country = t.get("counterparty_country")
            docs, support = [doc.id], ""
            if case.high_risk(country):
                # a payment to a higher-risk country needs more than the payee's own invoice
                if doc.type == "hospital_invoice":
                    patient = doc.field("patient")
                    chat = next((c for c in case.docs_of("support_chat")
                                 if patient and (tf.mentions(c.text, patient) or _names(c, t))), None)
                    family = patient and tf.norm(patient).split(" ")[-1] == tf.norm(case.name).split(" ")[-1]
                    if not (patient and tf.mentions(t.get("reference") or "", patient) and (chat or family)):
                        continue
                    support = " The payment reference names the patient, %s." % patient
                    if chat:
                        docs.append(chat.id)
                        support = (" The payment reference and the customer's account in %s both name the "
                                   "patient, %s." % (chat.id, patient))
                elif contract and _names(contract, t) and _dated_by(contract, t) and tf.mentions(contract.text, case.name):
                    docs.append(contract.id)
                    support = " %s, dated %s, is the supply contract with %s that the invoice falls under." % (
                        contract.id, tf.nice_date(contract.dated), _party(t))
                else:
                    continue
            what = doc.field("treatment", "goods", "service", "description")
            kind = "a receipt" if doc.type == "receipt" else "an invoice"
            text = ("%s is %s from %s%s for %s, dated %s. The payment of %s to %s on %s matches it.%s"
                    % (doc.id, kind, _party(t), " for %s" % what.rstrip(".") if what else "", gbp(t["amount_gbp"]),
                       tf.nice_date(doc.dated), gbp(t["amount_gbp"]), _party(t), day(t), support))
            out.append(Finding("explain", "INVOICE_MATCHES", text, docs=docs, txs=[t["transaction_id"]],
                               covers=[t["transaction_id"]],
                               rules=("TM01", "TM02", "TM06", "TM07", "TM08"), rank=40))
    # invoices the customer issued, matched to the payers
    for doc in case.docs_of("freight_invoices"):
        if not tf.mentions(doc.text, case.name):
            continue
        hits = []
        for row in doc.rows():
            amounts = [m for c in row.values() for m in tf.money(c)]
            for t in case.inbound():
                if t in hits or not any(tf.close(t["amount_gbp"], m) for m in amounts):
                    continue
                if any(tf.same_name(c, t.get("counterparty_name")) for c in row.values()):
                    hits.append(t)
                    break
        if hits:
            text = ("%s lists the invoices %s issued, and %d of them match the payers and amounts "
                    "received, namely %s." % (doc.id, case.name, len(hits),
                                       " and ".join("%s from %s" % (gbp(t["amount_gbp"]), t["counterparty_name"]) for t in hits[:3])))
            out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[doc.id], txs=ids(hits)[:5],
                               covers=ids(hits), rules=("TM02", "TM08"), rank=41))
    # staged payments under a contract schedule
    for doc in case.docs_of("contract_schedule"):
        rows, used, hits = doc.rows(), set(), []
        for t in case.outbound():
            if not _names(doc, t):
                continue
            for i, row in enumerate(rows):
                amounts = [m for c in row.values() for m in tf.money(c)]
                due = [d for c in row.values() for d in tf.dates(c)]
                when = tx_date(t)
                if i in used or not any(tf.close(t["amount_gbp"], m) for m in amounts):
                    continue
                if due and when and not any(abs((when - d).days) <= 3 for d in due):
                    continue
                used.add(i)
                hits.append(t)
                break
        if hits and doc.dated and all(_dated_by(doc, t) for t in hits):
            project = doc.field("project")
            text = ("%s, dated %s, is the payment schedule for the contract with %s%s. Its %d stages "
                    "match the %d payments by amount and due date, from %s on %s to %s on %s."
                    % (doc.id, tf.nice_date(doc.dated), _party(hits[0]), " (%s)" % project if project else "",
                       len(rows), len(hits), gbp(hits[0]["amount_gbp"]), day(hits[0]),
                       gbp(hits[-1]["amount_gbp"]), day(hits[-1])))
            out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[doc.id], txs=ids(hits)[:5],
                               covers=ids(hits), rules=("TM03",), rank=40))
    # a payment file listing each payee and amount
    for doc in case.docs_of("payment_file"):
        rows = doc.rows()
        if _shared_addresses(rows):
            continue  # handled as a red flag
        hits = []
        for row in rows:
            cells = list(row.values())
            amounts = [m for c in cells for m in tf.money(c)]
            for t in case.outbound():
                if t in hits:
                    continue
                if any(tf.same_name(c, t.get("counterparty_name")) for c in cells) and any(
                        tf.close(t["amount_gbp"], m) for m in amounts):
                    hits.append(t)
                    break
        if hits and len(hits) >= 0.9 * len(rows):
            title = doc.title or "payment file"
            text = ("%s, the %s dated %s, lists %d payees with a contract reference and amount each. "
                    "%d of the alerted payments match a line by name and amount, for example %s to %s."
                    % (doc.id, title.lower(), tf.nice_date(doc.dated), len(rows), len(hits),
                       gbp(hits[0]["amount_gbp"]), hits[0]["counterparty_name"]))
            out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[doc.id], txs=ids(hits)[:5],
                               covers=ids(hits), rules=("TM02", "TM04"), rank=40))
    return out


def _shared_addresses(rows):
    """Different payees listed at the same address."""
    seen = {}
    for row in rows:
        addr = tf.norm(row.get("address") or "")
        if addr:
            seen[addr] = seen.get(addr, 0) + 1
    return bool(seen) and max(seen.values()) >= 3


def funded_orders(case):
    """A customer order and the supplier's invoice for it explain a jump in funding."""
    order, invoice = case.doc("purchase_order"), case.doc("supplier_invoice")
    if not (order and invoice and case.alerts_of("TM01")):
        return []
    if _for_someone_else(invoice, case, ("buyer", "customer", "bill to")):
        return []
    if _addressed_to_another(order, case):
        return []
    ref = re.search(r"\bPO\s*\d+", order.text)
    if not (ref and tf.norm(ref.group(0)) in tf.norm(invoice.text)):
        return []
    if not (order.money and invoice.money and max(order.money) >= max(invoice.money)):
        return []
    supplier = invoice.field("supplier")
    country = supplier.split(",")[-1].strip() if "," in supplier else ""
    if country and country not in (case.declared.get("expected_countries") or []):
        return []
    cost = max(invoice.money)
    out = []
    for f in case.inbound():
        gap_ok = order.dated and tx_date(f) and 0 <= (tx_date(f) - order.dated).days <= 60
        if case.is_self(f) and f.get("counterparty_account") and gap_ok and cost <= f["amount_gbp"] <= cost * 1.1:
            text = ("%s is a customer order under %s worth %s, dated %s. %s is the pro forma invoice "
                    "from %s for the same order, %s. The %s the client paid in on %s is the money to "
                    "pay that invoice."
                    % (order.id, ref.group(0), gbp(max(order.money)), tf.nice_date(order.dated), invoice.id,
                       supplier or "the supplier", gbp(cost), gbp(f["amount_gbp"]), day(f)))
            out.append(Finding("explain", "INVOICE_MATCHES", text, docs=[order.id, invoice.id],
                               txs=[f["transaction_id"]], covers=[f["transaction_id"]],
                               rules=("TM01",), rank=40))
    return out


# ---------------------------------------------------------------- third parties
def third_parties(case):
    out = []
    for doc in case.docs_of("gift_letter"):
        for t in case.inbound():
            if (any(tf.close(t["amount_gbp"], m) for m in doc.money) and _names(doc, t) and _dated_by(doc, t)
                    and tf.mentions(doc.text, case.name)):
                rel = re.search(r"to my (\w+)", doc.body)
                text = ("%s is a signed gift letter from %s, dated %s, giving %s to %s%s with no "
                        "repayment and no interest in the account. The same amount arrived from %s on %s."
                        % (doc.id, _party(t), tf.nice_date(doc.dated), gbp(t["amount_gbp"]), case.name,
                           ", their %s," % rel.group(1) if rel else "", _party(t), day(t)))
                out.append(Finding("explain", "THIRD_PARTY_DOCUMENTED", text, docs=[doc.id],
                                   txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                                   rules=("TM01", "TM08"), rank=25))
    advice, agreement = case.doc("remittance_advice"), case.doc("factoring_agreement")
    if advice and agreement:
        for t in case.inbound():
            if (any(tf.close(t["amount_gbp"], m) for m in advice.money) and _names(advice, t)
                    and _names(agreement, t) and tf.mentions(agreement.text, case.name)
                    and not _for_someone_else(advice, case, ("client",))
                    and _dated_by(agreement, t)):
                text = ("%s is an invoice finance agreement between %s and %s, dated %s, under which "
                        "advances are paid into this account. %s is the remittance advice for the %s "
                        "received on %s."
                        % (agreement.id, case.name, _party(t), tf.nice_date(agreement.dated), advice.id,
                           gbp(t["amount_gbp"]), day(t)))
                out.append(Finding("explain", "THIRD_PARTY_DOCUMENTED", text, docs=[agreement.id, advice.id],
                                   txs=[t["transaction_id"]], covers=[t["transaction_id"]],
                                   rules=("TM01", "TM02", "TM08"), rank=25))
    chart = case.doc("group_structure")
    if chart:
        rows = chart.rows()
        owner_of = {}
        for row in rows:
            owner_of[tf.norm(row.get("company") or "")] = tf.norm(row.get("owner") or row.get("owned by") or "")
        mine = owner_of.get(tf.norm(case.name))
        for t in case.inbound():
            payer = tf.norm(t.get("counterparty_name") or "")
            related = mine and (payer == mine or (payer in owner_of and owner_of[payer] == mine))
            if not related or not (chart.dated and tx_date(t) and chart.dated <= tx_date(t)):
                continue
            docs = [chart.id]
            note = ""
            email = next((e for e in case.docs_of("email") if _names(e, t)), None)
            if email:
                docs.append(email.id)
                note = " %s is the owner's instruction that %s would fund this month's supplier payment." % (
                    email.id, t["counterparty_name"])
            how = ("owns %s" % case.name if payer == mine else "has the same owner as %s" % case.name)
            text = ("%s, the group structure chart dated %s, shows %s %s. %s paid %s into the account "
                    "on %s (%s), so the payer is a company in the same group.%s"
                    % (chart.id, tf.nice_date(chart.dated), t["counterparty_name"], how, t["counterparty_name"],
                       gbp(t["amount_gbp"]), day(t), t["transaction_id"], note))
            out.append(Finding("explain", "GROUP_COMPANY", text, docs=docs, txs=[t["transaction_id"]],
                               covers=[t["transaction_id"]], rules=("TM01", "TM02", "TM08"), rank=18))
    return out


# ---------------------------------------------------------------- early redemption
def documented_redemption(case):
    """A fund sold early for a documented personal reason, with nothing paid to anyone else."""
    if not case.alerts_of("TM10"):
        return []
    letter, email = case.doc("redundancy_letter"), case.doc("customer_email")
    sells = [t for t in case.alert_txs("TM10") if t.get("channel") == "fund_redemption"]
    if not (letter and email and sells) or _addressed_to_another(letter, case):
        return []
    sold = tx_date(sells[-1])
    employer = case.customer.get("employer") or ""
    if not (letter.dated and email.dated and sold and letter.dated <= email.dated <= sold):
        return []
    if employer and not tf.mentions(letter.text, employer):
        return []
    later_out = [t for t in case.txs if t["direction"] == "out" and t.get("channel") not in ("fund_subscription",)
                 and (t.get("booked_at") or "") >= (sells[-1].get("booked_at") or "") and not case.is_self(t)]
    if later_out:
        return []
    text = ("%s is a letter from %s dated %s confirming the customer's role was made redundant. "
            "In %s, dated %s, the customer asks to sell the fund to cover living costs. The units "
            "were sold on %s for %s and nothing was paid to anyone else."
            % (letter.id, employer or "the employer", tf.nice_date(letter.dated), email.id,
               tf.nice_date(email.dated), day(sells[-1]), gbp(sells[-1]["amount_gbp"])))
    return [Finding("explain", "DOCUMENTED_EVENT", text, docs=[letter.id, email.id],
                    txs=ids(case.alert_txs("TM10"))[:4],
                    covers=ids(t for t in case.alert_txs("TM10")
                               if t.get("channel") in ("fund_subscription", "fund_redemption")),
                    rules=("TM10",), rank=30)]


ALL = (own_accounts, returning_customer, one_off_events, cash_sales, cash_redeposit,
       loan_and_purchase, refunds, tenancy_deposits, collections, business_records,
       invoices, funded_orders, third_parties, documented_redemption)


def run(case):
    found = []
    for fn in ALL:
        found.extend(fn(case))
    return found
