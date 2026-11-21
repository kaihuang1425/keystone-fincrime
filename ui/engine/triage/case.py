"""One case with everything an analyst would pull up to review it."""
from . import textfacts as tf

SPENDING = ("card", "direct_debit", "standing_order")


class Finding:
    """One thing the review established.

    kind "explain": a document on file accounts for specific transactions.
    kind "flag":    evidence of a sign of crime. Any flag escalates the case.
    kind "gap":     activity with no document behind it, and what to ask for.
    """

    def __init__(self, kind, code, text, docs=(), txs=(), extra=(), covers=(),
                 rules=(), rank=50, ask=""):
        self.kind = kind
        self.code = code
        self.text = text
        self.docs = [d for d in docs if d]
        self.txs = [t for t in txs if t]
        self.extra = [e for e in extra if e]
        self.covers = list(covers)
        self.rules = tuple(rules)
        self.rank = rank
        self.ask = ask


class Case:
    def __init__(self, inst, row):
        self.inst = inst
        self.row = row
        self.id = row.get("case_id")
        self.alert_ids = list(row.get("alert_ids") or [])
        self.alerts = [inst.alerts[a] for a in self.alert_ids if a in inst.alerts]
        self.customer = inst.customers.get(row.get("customer_id")) or {}
        self.name = self.customer.get("name") or ""
        self.is_business = self.customer.get("kind") == "business"
        self.declared = self.customer.get("declared") or {}
        self.txs = inst.tx_by_customer.get(row.get("customer_id"), [])
        self.docs = inst.docs_for(row.get("customer_id"))
        self.reviews = sorted(inst.reviews.get(row.get("customer_id"), []),
                              key=lambda r: r.get("review_id") or "")
        self.policy = inst.policy
        self.held_id = row.get("held_payment_id")
        self.window_from = (row.get("review_window") or {}).get("from") or ""
        seen, ordered = set(), []
        for a in self.alerts:
            for tid in a.get("transaction_ids") or []:
                if tid in inst.tx and tid not in seen:
                    seen.add(tid)
                    ordered.append(inst.tx[tid])
        if self.held_id and self.held_id in inst.tx and self.held_id not in seen:
            ordered.append(inst.tx[self.held_id])
        ordered.sort(key=lambda t: (t.get("booked_at") or "", t["transaction_id"]))
        self.alert_tx = ordered
        self.rules = sorted(set(a.get("rule_id") for a in self.alerts))

    # ---- documents -------------------------------------------------------
    def docs_of(self, *types):
        return [d for d in self.docs if d.type in types]

    def doc(self, *types):
        found = self.docs_of(*types)
        return found[0] if found else None

    def own_register(self):
        """The register extract for the customer's own company, if any."""
        for d in self.docs_of("company_register_extract"):
            if tf.same_name(d.field("company"), self.name) or tf.mentions(d.title, self.name):
                return d
        return None

    def own_directors(self):
        d = self.own_register()
        names = []
        if d:
            for row in d.rows():
                who = row.get("officer") or row.get("person with significant control") or ""
                if who and who not in names:
                    names.append(who)
        return names

    # ---- transactions ----------------------------------------------------
    def alerts_of(self, rule):
        return [a for a in self.alerts if a.get("rule_id") == rule]

    def alert_txs(self, rule):
        out = []
        for a in self.alerts_of(rule):
            for tid in a.get("transaction_ids") or []:
                t = self.inst.tx.get(tid)
                if t and t not in out:
                    out.append(t)
        out.sort(key=lambda t: (t.get("booked_at") or "", t["transaction_id"]))
        return out

    def inbound(self, pool=None):
        return [t for t in (self.alert_tx if pool is None else pool) if t.get("direction") == "in"]

    def outbound(self, pool=None):
        return [t for t in (self.alert_tx if pool is None else pool) if t.get("direction") == "out"]

    def in_window(self, direction=None):
        """Every transaction from the start of the review window on, alerted or not.

        A document can match a payment that no alert happened to list, for
        example the onward payment of a collection when only the payers were
        alerted. Explanations look here for the other leg of a matched pair.
        """
        return [t for t in self.txs if (t.get("booked_at") or "")[:10] >= self.window_from
                and (direction is None or t.get("direction") == direction)]

    def is_self(self, t):
        return tf.same_name(t.get("counterparty_name"), self.name)

    def is_spending(self, t):
        return t.get("direction") == "out" and t.get("channel") in SPENDING

    def find(self, amount=None, direction=None, name=None, pool=None):
        """Transactions matching an amount to the penny and, if given, a party name."""
        hits = []
        for t in (self.alert_tx if pool is None else pool):
            if direction and t.get("direction") != direction:
                continue
            if amount is not None and not tf.close(t.get("amount_gbp"), amount):
                continue
            if name and not same_party(t.get("counterparty_name"), name):
                continue
            hits.append(t)
        return hits

    def high_risk(self, country):
        return bool(country) and country in self.policy.high_risk


def same_party(a, b):
    """Names match, ignoring a trailing 'client account'."""
    strip = lambda s: tf.norm(s).replace(" client account", "")
    return bool(a) and bool(b) and strip(a) == strip(b)


def ids(txs):
    return [t["transaction_id"] for t in txs]


def day(t):
    return tf.nice_date(t.get("booked_at") or "")


def tx_date(t):
    return tf.parse_date((t.get("booked_at") or "")[:10])
