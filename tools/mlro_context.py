"""Fetch public-source context for the MLRO on higher-risk-corridor escalations.

    python tools/mlro_context.py <path to institutions> [--dry-run]

When the system escalates a case as ESC_HIGH_RISK_CORRIDOR, the MLRO's first
question is what the official position on that country is today. This tool
looks that up with Tavily on official sites and saves the sources.

Three limits keep it honest:
  * It runs after the system and outside it. The verdict never uses it.
  * Only a country name is sent to Tavily. No customer, case or amount leaves.
    The kit's people and companies are invented, so searching their names
    would only find unrelated namesakes.
  * Every source is saved with its URL, and the note says the verdict did not
    rely on it.

It uses the `tvly` command line tool, which must be signed in. Results go to
context/mlro_context.json. If SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are
set, they are also upserted into the mlro_context table.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
OFFICIAL = "fatf-gafi.org,gov.uk"
NOTE = ("Public-source context fetched after the decision. The verdict was reached from the "
        "institution's own files and did not use this.")


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


def search(country):
    query = "%s FATF high-risk or increased monitoring jurisdiction current status" % country
    tvly = shutil.which("tvly")
    if not tvly:
        raise SystemExit("The tvly command is not installed or not on PATH.")
    with tempfile.TemporaryDirectory(prefix="mlro-context-") as tmp:
        saved = os.path.join(tmp, "result.json")
        subprocess.run([tvly, "search", query, "--depth", "advanced", "--max-results", "5",
                        "--include-domains", OFFICIAL, "-o", saved],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       shell=(os.name == "nt"))
        with open(saved, encoding="utf-8") as fh:
            data = json.load(fh)
    results = data.get("results") if isinstance(data, dict) else data
    if isinstance(results, list) and results and isinstance(results[0], dict) and "results" in results[0]:
        results = results[0]["results"]  # one entry per query when several are sent
    sources = [{"title": r.get("title"), "url": r.get("url"), "snippet": (r.get("content") or "")[:300]}
               for r in (results or []) if r.get("url")]
    return query, sources


def main(argv):
    if not argv or argv[0].startswith("--"):
        raise SystemExit(__doc__)
    kit, dry = os.path.abspath(argv[0]), "--dry-run" in argv
    countries = countries_escalated(kit)
    print("countries behind corridor escalations: %s" % (", ".join(countries) or "none"))
    if dry:
        print("dry run, nothing searched")
        return
    rows = []
    for country in countries:
        query, sources = search(country)
        rows.append({"topic": "country:" + country, "query": query, "sources": sources, "note": NOTE,
                     "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})
        print("%s: %d official sources" % (country, len(sources)))
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
