"""Fetch public-source context for the MLRO on higher-risk-corridor escalations.

    python tools/mlro_context.py <path to institutions> [--dry-run]

When the system escalates a case as ESC_HIGH_RISK_CORRIDOR, the MLRO's first
question is what the FATF says about that country now. This tool finds the
FATF's newest dated lists with Tavily and saves, for each country, the passage
from those lists and the date they were published.

Four limits keep it honest:
  * It runs after the system and outside it. The verdict never uses it.
  * Only a country name is sent to Tavily. No customer, case or amount leaves.
    The kit's people and companies are invented, so searching their names
    would only find unrelated namesakes.
  * Only the newest list of each kind is kept. The FATF republishes its lists
    after every plenary, and an old list shown beside the current one can
    contradict it. Every saved source carries its list date.
  * The tool does not rule on a country's status. It records whether the
    passage Tavily returned from the newest list names the country, and gives
    the URL so the MLRO reads the list itself.

It uses the `tvly` command line tool, which must be signed in. Results go to
context/mlro_context.json. If SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are
set, they are also upserted into the mlro_context table.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "system"))
from triage import textfacts as tf  # noqa: E402  (date parsing only)

SITE = "fatf-gafi.org"
FOLDER = "/High-risk-and-other-monitored-jurisdictions/"
LISTS = {
    "increased monitoring": ("Jurisdictions under Increased Monitoring", "increased-monitoring"),
    "call for action": ("High-Risk Jurisdictions subject to a Call for Action", "call-for-action"),
}
NOTE = ("Public-source context fetched after the decision. The verdict was reached from the "
        "institution's own files and did not use this. Read the list itself before relying on it.")


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def countries_escalated(kit):
    """Countries named by the TM06 alerts of cases the system escalated for the corridor."""
    found = set()
    for institution in sorted(os.listdir(kit)):
        out = os.path.join(ROOT, "output", institution + ".jsonl")
        alerts_path = os.path.join(kit, institution, "alerts.jsonl")
        if not (os.path.exists(out) and os.path.exists(alerts_path)):
            continue
        alerts = {a["alert_id"]: a for a in jsonl(alerts_path)}
        for d in jsonl(out):
            if d["reason_code"] != "ESC_HIGH_RISK_CORRIDOR":
                continue
            for alert_id in d["alert_ids"]:
                a = alerts.get(alert_id, {})
                if a.get("rule_id") == "TM06":
                    for name in str((a.get("measured") or {}).get("countries") or "").split(","):
                        if name.strip():
                            found.add(name.strip())
    return sorted(found)


def tvly_search(query, max_results=10):
    """One Tavily search limited to the FATF's own site. Returns the result list."""
    tvly = shutil.which("tvly")
    if not tvly:
        raise SystemExit("The tvly command is not installed or not on PATH.")
    with tempfile.TemporaryDirectory(prefix="mlro-context-") as tmp:
        saved = os.path.join(tmp, "result.json")
        subprocess.run([tvly, "search", query, "--depth", "advanced", "--max-results", str(max_results),
                        "--include-domains", SITE, "-o", saved],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       shell=(os.name == "nt"))
        with open(saved, encoding="utf-8") as fh:
            data = json.load(fh)
    results = data.get("results") if isinstance(data, dict) else data
    if isinstance(results, list) and results and isinstance(results[0], dict) and "results" in results[0]:
        results = results[0]["results"]  # one entry per query when several are sent
    return [r for r in (results or []) if r.get("url")]


def newest_lists():
    """The newest dated publication of each FATF list: {kind: (date, title, url)}."""
    year = datetime.date.today().year
    newest = {}
    for kind, (name, slug) in sorted(LISTS.items()):
        for r in tvly_search("FATF %s %d" % (name, year)):
            url, title = r["url"], r.get("title") or ""
            if FOLDER.lower() not in url.lower() or slug not in url.lower():
                continue
            dated = tf.dates(title)
            if not dated:
                continue
            if kind not in newest or dated[0] > newest[kind][0]:
                newest[kind] = (dated[0], title.replace(" - FATF", "").strip(), url)
    return newest


def passage(text, country, width=300):
    """The part of a returned passage around the country's name, or its start."""
    text = re.sub(r"\s+", " ", text or "").strip()
    m = re.search(r"\b%s\b" % re.escape(country), text, re.I)
    if not m:
        return text[:width]
    start = max(0, m.start() - width // 2)
    return text[start:start + width]


def context_for(country, newest):
    sources = []
    for kind, (dated, title, url) in sorted(newest.items()):
        query = "%s %s" % (country, title)
        hit = next((r for r in tvly_search(query, 8) if r["url"].split("?")[0].rstrip("/") == url.rstrip("/")), None)
        text = (hit or {}).get("content") or ""
        sources.append({
            "list": kind, "title": title, "url": url, "list_date": dated.isoformat(),
            "snippet": passage(text, country),
            # true or false describes the returned passage only; null means no passage came back
            "names_country": (bool(re.search(r"\b%s\b" % re.escape(country), text, re.I)) if hit else None),
        })
    as_of = max(s["list_date"] for s in sources) if sources else None
    return {"topic": "country:" + country, "list_date": as_of,
            "query": "%s on the FATF's newest lists" % country, "sources": sources, "note": NOTE,
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}


def main(argv):
    if not argv or argv[0].startswith("--"):
        raise SystemExit(__doc__)
    kit, dry = os.path.abspath(argv[0]), "--dry-run" in argv
    countries = countries_escalated(kit)
    print("countries behind corridor escalations: %s" % (", ".join(countries) or "none"))
    if dry:
        print("dry run, nothing searched")
        return
    newest = newest_lists()
    if not newest:
        raise SystemExit("No dated FATF list was found, so nothing was saved.")
    for kind, (dated, title, url) in sorted(newest.items()):
        print("newest %s list: %s (%s)" % (kind, tf.nice_date(dated), url))
    rows = []
    for country in countries:
        row = context_for(country, newest)
        rows.append(row)
        print("%s: %s" % (country, "; ".join(
            "%s list of %s %s" % (s["list"], tf.nice_date(tf.parse_date(s["list_date"])),
                                  {True: "names it", False: "passage does not name it", None: "no passage returned"}[s["names_country"]])
            for s in row["sources"])))
    os.makedirs(os.path.join(ROOT, "context"), exist_ok=True)
    with open(os.path.join(ROOT, "context", "mlro_context.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        from publish_supabase import post
        post(url, key, "mlro_context", rows, "topic")
        print("saved to context/mlro_context.json and Supabase")
    else:
        print("saved to context/mlro_context.json (no Supabase keys set, so not published)")


if __name__ == "__main__":
    main(sys.argv[1:])
