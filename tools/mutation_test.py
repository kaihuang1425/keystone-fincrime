"""Mutation tests: change one fact on file and check the verdict moves for the right reason.

A system can reach the right answer for the wrong reason, for example by
closing whenever a document of the right type is present. These tests take a
real development case, alter exactly one fact in memory (an amount, an
account holder, a date of birth, a date), and assert the decision changes the
way the SOP says it should. Nothing is written to the kit folder.

    python tools/mutation_test.py <path to institutions>
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "system"))
from triage.loader import Institution, Doc  # noqa: E402
from triage.decide import safe_decide  # noqa: E402
from triage import textfacts as tf  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = sys.argv[1]
NOISE = ("due_diligence_summary", "proof_of_address", "contact_note")
_cache = {}


def inst(name):
    if name not in _cache:
        _cache[name] = Institution(os.path.join(ROOT, name))
    return _cache[name]


class Mutant:
    """An institution with some documents, customers or list entries altered in memory."""

    def __init__(self, base, edit_doc=None, drop_types=(), customer=None, meta=None):
        self.__dict__.update(base.__dict__)
        self._base, self._edit, self._drop, self._meta = base, edit_doc, drop_types, meta
        if customer:
            self.customers = dict(base.customers)
            self.customers.update(customer)

    def docs_for(self, customer_id):
        out = []
        for d in self._base.docs_for(customer_id):
            if d.type in self._drop:
                continue
            text, dated = d.text, None
            if self._edit:
                text = self._edit(d, text)
            m = {"doc_id": d.id, "type": d.type, "title": d.title,
                 "dated": d.dated.isoformat() if d.dated else ""}
            if self._meta:
                m = self._meta(d, m)
            out.append(Doc(m, text))
        return out


def find_case(I, rules, doc_types, verdict=None, code=None):
    for row in I.cases:
        alerts = sorted(I.alerts[a]["rule_id"] for a in row["alert_ids"])
        if "+".join(alerts) != rules:
            continue
        types = sorted(d.type for d in I.docs_for(row["customer_id"])
                       if d.type not in NOISE and not d.id.startswith("INC-"))
        if all(t in types for t in doc_types):
            r = safe_decide(I, row)
            if (verdict is None or r["verdict"] == verdict) and (code is None or r["reason_code"] == code):
                return row, r
    raise SystemExit("no case found for %s %s" % (rules, doc_types))


def bump_money(text):
    """Add £100 to every amount in a document."""
    return re.sub(r"£([\d,]+\.\d{2})", lambda m: tf.gbp(float(m.group(1).replace(",", "")) + 100), text)


results = []


def check(name, institution, rules, doc_types, before, after, **mutation):
    I = inst(institution)
    row, r0 = find_case(I, rules, doc_types, verdict=before[0], code=before[1])
    r1 = safe_decide(Mutant(I, **mutation), row)
    ok = (r1["verdict"], r1["reason_code"]) == after or (after[1] is None and r1["verdict"] == after[0])
    results.append(ok)
    print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", name, row["case_id"], r0["verdict"],
                                            r0["reason_code"], r1["verdict"], r1["reason_code"]))
    if not ok:
        print("      expected %s/%s\n      %s" % (after[0], after[1], r1["reason"]))


only = lambda t, fn: (lambda d, text: fn(text) if d.type == t else text)

# 1. the amount in the solicitor's letter no longer matches the payment
check("estate letter states a different amount", "bank", "TM01", ["solicitor_letter"],
      ("CLOSE", "DOCUMENTED_EVENT"), ("RFI", "RFI_SOURCE_OF_FUNDS"),
      edit_doc=only("solicitor_letter", bump_money))

# 2. the letter is dated after the money arrived
check("estate letter dated after the payment", "bank", "TM01", ["solicitor_letter"],
      ("CLOSE", "DOCUMENTED_EVENT"), ("RFI", "RFI_SOURCE_OF_FUNDS"),
      meta=lambda d, m: dict(m, dated="2027-01-01") if d.type == "solicitor_letter" else m)

# 3. the statement names a different account holder
check("statement held by someone else", "bank", "TM02", ["bank_statement"],
      ("CLOSE", "OWN_ACCOUNT"), ("RFI", None),
      edit_doc=only("bank_statement", lambda t: re.sub(r"(\*\*Account holder:\*\*) .*", r"\1 Jordan Example", t)))

# 4. the statement is for a different account number
check("statement for a different account", "bank", "TM02", ["bank_statement"],
      ("CLOSE", "OWN_ACCOUNT"), ("RFI", None),
      edit_doc=only("bank_statement", lambda t: re.sub(r"\d{2}-\d{2}-\d{2} \d{8}", "00-00-00 00000000", t)))

# 5. the same own-account transfer at 5 times declared income or more
I = inst("bank")
row, _ = find_case(I, "TM01+TM02", ["bank_statement"], "CLOSE", "OWN_ACCOUNT")
a = [I.alerts[x] for x in row["alert_ids"] if I.alerts[x]["rule_id"] == "TM01"][0]
saved = dict(a["measured"])
a["measured"] = dict(saved, baseline_gbp=saved["received_gbp"] / 6.0, multiple=6.0)
r = safe_decide(I, row)
a["measured"] = saved
ok = (r["verdict"], r["reason_code"]) == ("RFI", "RFI_UPDATED_PROFILE")
results.append(ok)
print("%s %-58s %s: CLOSE/OWN_ACCOUNT -> %s/%s" % ("PASS" if ok else "FAIL", "own-account transfer at 6x declared income", row["case_id"], r["verdict"], r["reason_code"]))

# 6. and the reverse: an updated-profile case below 5 times closes
row, _ = find_case(I, "TM01", ["bank_statement"], "RFI", "RFI_UPDATED_PROFILE")
a = [I.alerts[x] for x in row["alert_ids"] if I.alerts[x]["rule_id"] == "TM01"][0]
saved = dict(a["measured"])
a["measured"] = dict(saved, baseline_gbp=saved["received_gbp"] / 4.0, multiple=4.0)
r = safe_decide(I, row)
a["measured"] = saved
ok = (r["verdict"], r["reason_code"]) == ("CLOSE", "OWN_ACCOUNT")
results.append(ok)
print("%s %-58s %s: RFI/RFI_UPDATED_PROFILE -> %s/%s" % ("PASS" if ok else "FAIL", "own-account transfer at 4x declared income", row["case_id"], r["verdict"], r["reason_code"]))

# 7. the booking confirmation is not on file
check("trip collection with no booking on file", "bank", "TM02+TM04", ["booking_confirmation"],
      ("CLOSE", "COLLECTION_DOCUMENTED"), ("RFI", "RFI_PURPOSE_DOCUMENTS"),
      drop_types=("booking_confirmation",))

# 8. the car in the sale receipt is not the car the customer insured
check("sale receipt for a different vehicle", "bank", "TM01+TM05", ["vehicle_sale_receipt"],
      ("CLOSE", "DOCUMENTED_EVENT"), ("RFI", "RFI_SOURCE_OF_FUNDS"),
      edit_doc=only("insurance_schedule", lambda t: re.sub(r"registration [A-Z]{2}\d{2} [A-Z]{3}", "registration ZZ99 ZZZ", t)))

# 9. the hospital invoice is for a different amount: an undocumented payment to a higher-risk country
check("hospital invoice does not match the payment", "bank", "TM06", ["hospital_invoice"],
      ("CLOSE", "INVOICE_MATCHES"), ("ESCALATE", "ESC_HIGH_RISK_CORRIDOR"),
      edit_doc=only("hospital_invoice", bump_money))

# 10. takings records that do not reconcile to the deposits
check("collection reports do not match the deposits", "bank", "TM03", ["cash_collection_reports"],
      ("CLOSE", "BUSINESS_RECORDS_RECONCILE"), ("RFI", "RFI_BUSINESS_RECORDS"),
      edit_doc=only("cash_collection_reports", bump_money))

# 11. gift letter: the donor's date of birth decides a list match both ways
I = inst("investment")
row, r0 = find_case(I, "TM08+TM22", ["gift_letter"], "CLOSE", "LIST_MATCH_DIFFERENT_PARTY")
entry_id = [I.alerts[x]["measured"]["list_entry"] for x in row["alert_ids"] if I.alerts[x]["rule_id"] == "TM22"][0]
listed = tf.nice_date(I.list_entries[entry_id]["date_of_birth"])
doc = [d for d in I.docs_for(row["customer_id"]) if d.type == "gift_letter"][0]
born = [d for d in doc.dates if d.year <= doc.dated.year - 16][0]
r1 = safe_decide(Mutant(I, edit_doc=only("gift_letter", lambda t: t.replace(tf.nice_date(born), listed))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("ESCALATE", "ESC_LISTED_PARTY")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "gift donor's birth date changed to the listed one", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

row, r0 = find_case(I, "TM08+TM22", ["gift_letter"], "ESCALATE", "ESC_LISTED_PARTY")
doc = [d for d in I.docs_for(row["customer_id"]) if d.type == "gift_letter"][0]
born = [d for d in doc.dates if d.year <= doc.dated.year - 16][0]
r1 = safe_decide(Mutant(I, edit_doc=only("gift_letter", lambda t: t.replace(tf.nice_date(born), "3 March 1988"))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("CLOSE", "LIST_MATCH_DIFFERENT_PARTY")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "gift donor's birth date changed to a different one", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 12. a gift letter that gives no date of birth cannot settle a list match
r1 = safe_decide(Mutant(I, edit_doc=only("gift_letter", lambda t: t.replace(tf.nice_date(born), "an unstated date"))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("RFI", "RFI_COUNTERPARTY_DETAILS")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "gift letter with no date of birth", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 13. the same letter worded differently still decides the same way
r1 = safe_decide(Mutant(I, edit_doc=only("gift_letter", lambda t: t.replace(tf.nice_date(born), born.strftime("%B %d, %Y").replace(" 0", " ")))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("ESCALATE", "ESC_LISTED_PARTY")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "birth date written 'Month D, YYYY'", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 14. a company whose listed controller really is a different person (different birth month)
check("register shows a different birth month", "bank", "TM22", ["significant_control_register"],
      ("ESCALATE", "ESC_LISTED_PARTY"), ("CLOSE", "LIST_MATCH_DIFFERENT_PARTY"),
      edit_doc=lambda d, t: re.sub(r"\| (January|February|March|April|May|June|July|August|September|October|November|December) (19\d\d) \|",
                                   lambda m: "| %s %s |" % ("January" if m.group(1) != "January" else "June", int(m.group(2)) - 9), t)
      if d.type in ("significant_control_register", "company_register_extract") else t)

# 15. payments firm: a contract schedule whose stage amounts do not match
check("contract schedule amounts differ", "payments_fx", "TM03", ["contract_schedule"],
      ("CLOSE", "INVOICE_MATCHES"), ("RFI", "RFI_PURPOSE_DOCUMENTS"),
      edit_doc=only("contract_schedule", bump_money))

# 16. payments firm: the payer is not in the group structure chart
check("payer missing from the group chart", "payments_fx", "TM08", ["group_structure"],
      ("CLOSE", "GROUP_COMPANY"), ("RFI", "RFI_COUNTERPARTY_DETAILS"),
      edit_doc=only("group_structure", lambda t: re.sub(r"\| ([A-Z][\w ]+ Group Holdings Ltd) \|", "| Unrelated Holdings Ltd |", t)))

# 17. payments firm: an invoice to a higher-risk country with no supply contract behind it
check("higher-risk supplier invoice without a contract", "payments_fx", "TM06", ["supply_contract"],
      ("CLOSE", "INVOICE_MATCHES"), ("ESCALATE", "ESC_HIGH_RISK_CORRIDOR"),
      drop_types=("supply_contract",))

# 17b. payments firm: a held payment of £10,000 or more whose invoice does not match is not released
check("held payment above the invoice threshold, invoice differs", "payments_fx", "TM02+TM08", ["carrier_invoice"],
      ("CLOSE", "INVOICE_MATCHES"), ("RFI", "RFI_PURPOSE_DOCUMENTS"),
      edit_doc=only("carrier_invoice", bump_money))

# 17c. a wrong close costs more than a question: one undocumented payment from a stranger blocks a close
I = inst("bank")
row, r0 = find_case(I, "TM01", ["solicitor_letter"], "CLOSE", "DOCUMENTED_EVENT")
a = [I.alerts[x] for x in row["alert_ids"] if I.alerts[x]["rule_id"] == "TM01"][0]
real = I.tx[a["transaction_ids"][-1]]
stranger = dict(real, transaction_id="TEST-STRANGER", amount_gbp=5000.0, amount=5000.0,
                counterparty_name="Unknown Example Party", counterparty_account="00-00-00 11111111",
                reference="PAYMENT")
I.tx["TEST-STRANGER"] = stranger
a["transaction_ids"].append("TEST-STRANGER")
r1 = safe_decide(I, row)
a["transaction_ids"].remove("TEST-STRANGER")
del I.tx["TEST-STRANGER"]
ok = (r1["verdict"], r1["reason_code"]) == ("RFI", "RFI_PURPOSE_DOCUMENTS")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "documented case plus one undocumented £5,000 from a stranger", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 18. a refund with no sign the customer ever paid the venue
I = inst("emoney")
row, r0 = find_case(I, "TM06", ["venue_email"], "CLOSE", "REFUND_OF_EARLIER_PAYMENT")
saved_reviews, saved_tx = I.reviews[row["customer_id"]], I.tx_by_customer[row["customer_id"]]
I.reviews[row["customer_id"]] = []
I.tx_by_customer[row["customer_id"]] = [t for t in saved_tx if t["direction"] == "in" or t["channel"] == "card"]
r1 = safe_decide(I, row)
I.reviews[row["customer_id"]], I.tx_by_customer[row["customer_id"]] = saved_reviews, saved_tx
ok = r1["verdict"] == "ESCALATE"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "refund from a higher-risk country with no earlier payment", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 19. a sale receipt with the two names swapped: the customer is now the buyer, so it explains nothing
I = inst("emoney")
row, r0 = find_case(I, "TM05", ["sale_receipt"], "CLOSE", "DOCUMENTED_EVENT")
me = I.customers[row["customer_id"]]["name"]


def swap_parties(text, mine=me):
    others = [n for n in re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text) if n != mine and " " in n
              and n.split()[0] not in ("Sale", "Bike", "Carbon", "Road", "Bill", "Receipt", "Document", "Total", "Sold")]
    if not others:
        return text
    other = max(sorted(set(others)), key=others.count)
    return text.replace(mine, "\0").replace(other, mine).replace("\0", other)


r1 = safe_decide(Mutant(I, edit_doc=only("sale_receipt", swap_parties)), row)
ok = (r1["verdict"], r1["reason_code"]) == ("RFI", "RFI_SOURCE_OF_FUNDS")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "sale receipt with seller and buyer swapped", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 20. a sale receipt that names someone else as seller, while only the advert names the customer
r1 = safe_decide(Mutant(I, edit_doc=only("sale_receipt", lambda t: t.replace(me, "Jo Example"))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("RFI", "RFI_SOURCE_OF_FUNDS")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "sale receipt in another seller's name", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 21. an insurer's letter addressed to a named person who is not the customer
I = inst("bank")
for row in I.cases:
    docs = [d for d in I.docs_for(row["customer_id"]) if d.type == "insurer_letter"]
    name = I.customers[row["customer_id"]]["name"]
    if docs and re.search(r"Dear\s+%s" % re.escape(name), docs[0].text):
        break
r0 = safe_decide(I, row)
r1 = safe_decide(Mutant(I, edit_doc=only("insurer_letter", lambda t: t.replace(name, "Jo Example"))), row)
ok = r0["verdict"] == "CLOSE" and r1["verdict"] == "RFI"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "insurer letter addressed to someone else", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 22. a credit note made out to another company, for a refund from a higher-risk country
I = inst("payments_fx")
row, r0 = find_case(I, "TM06+TM08", ["credit_note"], "CLOSE", "REFUND_OF_EARLIER_PAYMENT")
name = I.customers[row["customer_id"]]["name"]
r1 = safe_decide(Mutant(I, edit_doc=only("credit_note", lambda t: t.replace(name, "Other Example Ltd"))), row)
ok = r1["verdict"] == "ESCALATE"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "credit note made out to another company", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 23. a documented collection still closes when only one of its two alerts fired
I = inst("bank")
row, r0 = find_case(I, "TM02+TM04", ["booking_confirmation"], "CLOSE", "COLLECTION_DOCUMENTED")
only_tm04 = dict(row, alert_ids=[a for a in row["alert_ids"] if I.alerts[a]["rule_id"] == "TM04"])
r1 = safe_decide(I, only_tm04)
ok = (r1["verdict"], r1["reason_code"]) == ("CLOSE", "COLLECTION_DOCUMENTED")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "collection with only the many-payers alert", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 24. when the customer gave two stories for cash, the reason lists them in the order they were told
row, r0 = find_case(I, "TM01+TM02+TM05", ["support_chat"], "ESCALATE", "ESC_UNEXPLAINED_FUNDS")
chats = sorted((d for d in I.docs_for(row["customer_id"]) if d.type == "support_chat"), key=lambda d: (str(d.dated), d.id))
cited = re.findall(r"CHT-\d+", r0["reason"])
ok = len(chats) >= 2 and cited[:2] == [chats[0].id, chats[1].id]
results.append(ok)
print("%s %-58s %s: chats cited %s, dated order %s" % ("PASS" if ok else "FAIL", "two cash stories are given in date order", row["case_id"], cited[:2], [c.id for c in chats[:2]]))

# 25. a personal customer moves money between two own accounts, but only one statement is on file
I = inst("bank")
row, r0 = find_case(I, "TM02", ["bank_statement"], "CLOSE", "OWN_ACCOUNT")
first = sorted(d.id for d in I.docs_for(row["customer_id"]) if d.type == "bank_statement")[0]
r1 = safe_decide(Mutant(I, edit_doc=lambda d, t: "" if d.id == first else t), row)
ok = r1["verdict"] == "RFI"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "two own accounts, one statement missing", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 26. own money arrives in a dormant account with a statement on file but no identity re-verification
check("dormant account, statement but no re-verification", "bank", "TM07", ["bank_statement", "reverification_record"],
      ("CLOSE", "RETURNING_CUSTOMER"), ("RFI", "RFI_SOURCE_OF_FUNDS"),
      drop_types=("reverification_record",))

# 27. cash paid back in, but the customer's own figure in the chat differs from the deposit
check("cash paid back in, chat gives a different figure", "bank", "TM01+TM05", ["support_chat"],
      ("CLOSE", "WITHIN_PROFILE"), ("RFI", "RFI_SOURCE_OF_FUNDS"),
      edit_doc=only("support_chat", bump_money))

# 28. a documented reason for selling a fund does not cover a stranger's payment in the same alert
I = inst("investment")
row, r0 = find_case(I, "TM10", ["redundancy_letter"], "CLOSE", "DOCUMENTED_EVENT")
a = I.alerts[row["alert_ids"][0]]
real = I.tx[a["transaction_ids"][-1]]
I.tx["TEST-STRANGER-2"] = dict(real, transaction_id="TEST-STRANGER-2", direction="in", channel="faster_payment",
                               amount_gbp=5000.0, amount=5000.0, counterparty_name="Unknown Example Party",
                               counterparty_account="00-00-00 22222222", reference="PAYMENT")
a["transaction_ids"].append("TEST-STRANGER-2")
r1 = safe_decide(I, row)
a["transaction_ids"].remove("TEST-STRANGER-2")
del I.tx["TEST-STRANGER-2"]
ok = r1["verdict"] == "RFI"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "fund sale documented, plus a stranger's £5,000", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 29. a customer order that is addressed to another company
I = inst("payments_fx")
for row in I.cases:
    name = I.customers[row["customer_id"]]["name"]
    orders = [d for d in I.docs_for(row["customer_id"]) if d.type == "purchase_order"]
    if orders and re.search(r"Dear\s+%s" % re.escape(name), orders[0].text):
        break
r0 = safe_decide(I, row)
r1 = safe_decide(Mutant(I, edit_doc=only("purchase_order", lambda t: t.replace(name, "Other Example Ltd"))), row)
ok = r0["verdict"] == "CLOSE" and r1["verdict"] == "RFI"
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "customer order addressed to another company", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

# 30. takings records headed with another company's name
I = inst("bank")
row, r0 = find_case(I, "TM03", ["cash_collection_reports"], "CLOSE", "BUSINESS_RECORDS_RECONCILE")
name = I.customers[row["customer_id"]]["name"]
r1 = safe_decide(Mutant(I, edit_doc=only("cash_collection_reports", lambda t: t.replace(name, "Other Example Ltd"))), row)
ok = (r1["verdict"], r1["reason_code"]) == ("RFI", "RFI_BUSINESS_RECORDS")
results.append(ok)
print("%s %-58s %s: %s/%s -> %s/%s" % ("PASS" if ok else "FAIL", "collection reports headed with another company", row["case_id"], r0["verdict"], r0["reason_code"], r1["verdict"], r1["reason_code"]))

print("\n%d of %d mutation tests passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
