"""Copy the system's finished output into Supabase.

    python tools/publish_supabase.py [--rerun <path to institutions>] [--dry-run]

This runs after the system and outside it. system/run never calls Supabase,
so the scored path stays offline and repeatable. What lands in Supabase is
an exact copy of output/<institution>.jsonl plus a hash of each file, which
gives the UI real results to show and gives a reviewer an audit trail.

With --rerun the system is run five more times on the given folders and the
record says whether every run produced the same bytes.

Keys come from the environment and are never written to a file:
    SUPABASE_URL                 https://<project>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    the service role key (server side only)

Create the tables first with supabase/schema.sql.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
INSTITUTIONS = ["bank", "emoney", "investment", "payments_fx"]
FIELDS = ("case_id", "alert_ids", "verdict", "reason_code", "reason", "evidence")
BATCH = 500


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def rerun(institution, folder, expected, times=5):
    """Run the system again and compare each output with the published one."""
    identical, seconds = True, []
    with tempfile.TemporaryDirectory(prefix="triage-rerun-") as tmp:
        for i in range(times):
            out = os.path.join(tmp, "%s_%d.jsonl" % (institution, i))
            env = dict(os.environ, PYTHONHASHSEED=str(i * 7919))
            start = time.time()
            subprocess.run([sys.executable, "-B", os.path.join(ROOT, "system", "run"), folder, out],
                           cwd=os.path.join(ROOT, "system"), env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            seconds.append(time.time() - start)
            identical = identical and sha256(out) == expected
    return identical, sum(seconds) / len(seconds)


def post(url, key, table, rows, conflict):
    """Upsert rows through Supabase's REST interface."""
    for i in range(0, len(rows), BATCH):
        body = json.dumps(rows[i:i + BATCH]).encode("utf-8")
        req = urllib.request.Request(
            "%s/rest/v1/%s?on_conflict=%s" % (url.rstrip("/"), table, conflict), data=body, method="POST",
            headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"})
        try:
            urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as exc:
            raise SystemExit("Supabase refused %s rows %d-%d: %s %s"
                             % (table, i, i + len(rows[i:i + BATCH]), exc.code, exc.read().decode("utf-8", "replace")[:300]))


def main(argv):
    dry = "--dry-run" in argv
    kit = argv[argv.index("--rerun") + 1] if "--rerun" in argv else None
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not dry and not (url and key):
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or pass --dry-run.")
    for institution in INSTITUTIONS:
        path = os.path.join(ROOT, "output", institution + ".jsonl")
        if not os.path.exists(path):
            print("%s: no output file, skipped" % institution)
            continue
        digest = sha256(path)
        run_id = "%s-%s" % (institution, digest[:12])
        with open(path, encoding="utf-8") as fh:
            decisions = [json.loads(line) for line in fh if line.strip()]
        counts = {v: sum(1 for d in decisions if d["verdict"] == v) for v in ("CLOSE", "RFI", "ESCALATE")}
        run = {"run_id": run_id, "institution": institution, "output_sha256": digest, "repeat_runs": 0,
               "repeat_identical": None, "cases": len(decisions), "closes": counts["CLOSE"],
               "rfis": counts["RFI"], "escalations": counts["ESCALATE"], "seconds": None}
        if kit:
            same, secs = rerun(institution, os.path.join(os.path.abspath(kit), institution), digest)
            run.update(repeat_runs=5, repeat_identical=same, seconds=round(secs, 2))
        rows = [dict({k: d[k] for k in FIELDS}, run_id=run_id, institution=institution) for d in decisions]
        print("%s: run %s, %d decisions (%d close, %d RFI, %d escalate)%s"
              % (institution, run_id, len(rows), counts["CLOSE"], counts["RFI"], counts["ESCALATE"],
                 "" if not kit else ", five re-runs %s" % ("identical" if run["repeat_identical"] else "DIFFER")))
        if dry:
            continue
        post(url, key, "triage_runs", [run], "run_id")
        post(url, key, "triage_decisions", rows, "run_id,case_id")
    print("dry run, nothing sent" if dry else "published")


if __name__ == "__main__":
    main(sys.argv[1:])
