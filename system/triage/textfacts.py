"""Pull typed facts out of the free-text documents.

The documents on file are written in varying layouts and wordings, so nothing
here depends on a fixed label or phrase. We read every pound amount, every
date, every account reference, every `**Label:** value` pair and every
Markdown table, and the checks elsewhere compare those facts with the
transactions.
"""
import re
from datetime import date

MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december"]
MONTHS = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}
_M = "|".join(MONTH_NAMES)
_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
_TH = r"(?:st|nd|rd|th)?"

_MONEY = re.compile(r"(?:£|\bGBP)\s?%s|\b%s\s?(?:pounds\b|GBP\b)" % (_NUM, _NUM))
_DMY = re.compile(r"\b(\d{1,2})%s\s+(?:of\s+)?(%s),?\s+(\d{4})\b" % (_TH, _M), re.I)
_MDY = re.compile(r"\b(%s)\s+(\d{1,2})%s,\s*(\d{4})\b" % (_M, _TH), re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_MONTH_YEAR = re.compile(r"\b(%s)\s+(\d{4})\b" % _M, re.I)
_SORT_ACCT = re.compile(r"\b(\d{2}-\d{2}-\d{2})\s+(\d{8})\b")
_ENDING = re.compile(r"\bending\s+(\d{3,6})\b", re.I)
_FIELD = re.compile(r"^\s*(?:[*\-]\s+)?\*\*([^*:]+?):?\*\*:?\s*(.*)$")


def money(text):
    """Every pound amount in the text, in order, as floats."""
    return [float((a or b).replace(",", "")) for a, b in _MONEY.findall(text or "")]


def _all_dates(text):
    """(position, date) for every full date in the text, in any common format."""
    found = []
    for m in _DMY.finditer(text):
        found.append((m.start(), int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))))
    for m in _MDY.finditer(text):
        found.append((m.start(), int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))))
    for m in _ISO.finditer(text):
        found.append((m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _SLASH.finditer(text):  # day first, as written in the UK
        found.append((m.start(), int(m.group(3)), int(m.group(2)), int(m.group(1))))
    out = []
    for pos, y, mo, d in sorted(found):
        try:
            out.append((pos, date(y, mo, d)))
        except ValueError:
            continue
    return out


def parse_date(text):
    """The first full date in the text, or None."""
    found = _all_dates(text or "")
    return found[0][1] if found else None


def dates(text):
    """Every full date in the text, in order."""
    return [d for _, d in _all_dates(text or "")]


def month_years(text):
    """Every month-and-year, such as 'March 1980', as (year, month). Full dates count too."""
    return [(int(m.group(2)), MONTHS[m.group(1).lower()])
            for m in _MONTH_YEAR.finditer(text or "")]


def account_refs(text):
    """Account references, normalised: 'NN-NN-NN NNNNNNNN' or 'ending NNNN'."""
    refs = ["%s %s" % (a, b) for a, b in _SORT_ACCT.findall(text or "")]
    refs += ["ending %s" % e for e in _ENDING.findall(text or "")]
    return refs


def same_account(a, b):
    """True when two pieces of text name the same account."""
    if not a or not b:
        return False
    ra, rb = account_refs(a), account_refs(b)
    if ra and rb:
        return any(x == y for x in ra for y in rb)
    return False


def fields(text):
    """`**Label:** value` pairs with lower-cased labels. The first value wins."""
    out = {}
    for line in (text or "").splitlines():
        m = _FIELD.match(line)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip().strip("*").strip()
            if key not in out and val:
                out[key] = val
    return out


def tables(text):
    """Markdown tables as lists of row dicts keyed by lower-cased header."""
    result, header, rows = [], None, []
    for line in (text or "").splitlines() + [""]:
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if header is None:
                header = [c.lower() for c in cells]
            elif all(set(c) <= set("-: ") for c in cells):
                continue
            else:
                rows.append({header[i]: (cells[i] if i < len(cells) else "")
                             for i in range(len(header))})
        else:
            if header is not None:
                result.append(rows)
            header, rows = None, []
    return result


def body(text):
    """The document without its title, ID and date lines, as one paragraph."""
    keep = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        low = s.lower()
        if low.startswith("**document id") or low.startswith("**dated"):
            continue
        keep.append(s)
    return " ".join(keep)


def norm(s):
    """Case-, punctuation- and spacing-insensitive form of a name."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def same_name(a, b):
    return bool(a) and bool(b) and norm(a) == norm(b)


def mentions(text, name):
    """True when the name appears in the text as whole words."""
    n = norm(name)
    return bool(n) and (" %s " % n) in (" %s " % norm(text))


def close(a, b, tol=0.005):
    """Two amounts are the same to the penny."""
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def gbp(x):
    return "£{:,.2f}".format(float(x))


def nice_date(d):
    """'5 August 2026' from a date or an ISO timestamp."""
    if isinstance(d, str):
        d = parse_date(d[:10])
    if not d:
        return ""
    return "%d %s %d" % (d.day, MONTH_NAMES[d.month - 1].capitalize(), d.year)
