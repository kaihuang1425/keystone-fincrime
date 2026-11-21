"""Read one institution folder into memory."""
import json
import os
import re
from collections import defaultdict

from . import textfacts as tf


def _jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    # utf-8-sig drops a byte-order mark if the file has one and is otherwise plain UTF-8
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue  # one unreadable line must not stop the whole run
            if isinstance(row, dict):
                rows.append(row)
    return rows


class Doc:
    """One document on file, with its facts read once."""

    def __init__(self, meta, text):
        self.id = meta.get("doc_id")
        self.type = meta.get("type") or ""
        self.title = meta.get("title") or ""
        self.dated = tf.parse_date(meta.get("dated") or "")
        self.text = text
        self.body = tf.body(text)
        self.fields = tf.fields(text)
        self.tables = tf.tables(text)
        self.money = tf.money(self.body)
        self.dates = tf.dates(self.body)

    def field(self, *words):
        """The first field whose label contains any of the given words."""
        for want in words:
            for key in self.fields:
                if want in key:
                    return self.fields[key]
        return ""

    def rows(self):
        """All table rows in the document, in order."""
        return [row for table in self.tables for row in table]


class Policy:
    """The numbers the SOP sets that the decisions depend on."""

    def __init__(self, text):
        self.text = text
        m = re.search(r"Higher-risk countries[^:]*:\s*([^\n]+)", text)
        self.high_risk = sorted(c.strip().rstrip(".") for c in m.group(1).split(",")) if m else []
        m = re.search(r"at (\d+(?:\.\d+)?) times the declared", text)
        self.own_account_multiple = float(m.group(1)) if m else 5.0
        m = re.search(r"Payments of £([\d,]+)(?:\.\d+)? or more to anyone other than the client need an invoice", text)
        self.invoice_threshold = float(m.group(1).replace(",", "")) if m else None


class Institution:
    def __init__(self, folder):
        self.folder = folder
        self.cases = _jsonl(os.path.join(folder, "cases.jsonl"))
        self.alerts = {a["alert_id"]: a for a in _jsonl(os.path.join(folder, "alerts.jsonl")) if a.get("alert_id")}
        self.customers = {c["customer_id"]: c for c in _jsonl(os.path.join(folder, "customers.jsonl")) if c.get("customer_id")}
        self.tx_by_customer = defaultdict(list)
        self.tx = {}
        for t in _jsonl(os.path.join(folder, "transactions.jsonl")):
            if not t.get("transaction_id"):
                continue  # a record with no ID cannot be cited or matched
            self.tx_by_customer[t.get("customer_id")].append(t)
            self.tx[t["transaction_id"]] = t
        for rows in self.tx_by_customer.values():
            rows.sort(key=lambda t: (t.get("booked_at") or "", t["transaction_id"]))
        self.evidence_meta = defaultdict(list)
        for e in _jsonl(os.path.join(folder, "evidence.jsonl")):
            self.evidence_meta[e.get("customer_id")].append(e)
        self.reviews = defaultdict(list)
        for r in _jsonl(os.path.join(folder, "previous_reviews.jsonl")):
            self.reviews[r.get("customer_id")].append(r)
        self.list_entries = {e["entry_id"]: e for e in _jsonl(os.path.join(folder, "internal_list.jsonl")) if e.get("entry_id")}
        text = ""
        policy_path = os.path.join(folder, "POLICY.md")
        if os.path.exists(policy_path):
            with open(policy_path, encoding="utf-8-sig", errors="replace") as fh:
                text = fh.read()
        self.policy = Policy(text)

    def docs_for(self, customer_id):
        docs = []
        metas = sorted(self.evidence_meta.get(customer_id, []), key=lambda e: e.get("doc_id") or "")
        for meta in metas:
            path = os.path.join(self.folder, meta.get("file") or "")
            text = ""
            if os.path.isfile(path):
                with open(path, encoding="utf-8-sig", errors="replace") as fh:
                    text = fh.read()
            docs.append(Doc(meta, text))
        return docs
