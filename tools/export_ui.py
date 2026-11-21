"""Write one JSON file per institution for the UI to load.

    python tools/export_ui.py [--rerun <path to institutions>] [--out <folder>]

Each file holds the run facts and the decisions exactly as the system wrote
them. It is the same shape the Supabase tables hold, so the pages can load
these files today and read Supabase later without changing how they draw.

    {"run": {"run_id", "institution", "output_sha256", "repeat_runs",
             "repeat_identical", "cases", "closes", "rfis", "escalations", "seconds"},
     "decisions": [{"case_id", "alert_ids", "verdict", "reason_code", "reason", "evidence"}, ...]}

The files carry reasons and evidence IDs only. They never carry the text of a
kit record. With --rerun the system is run five more times and the run facts
say whether every run gave the same bytes.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from publish_supabase import INSTITUTIONS, FIELDS, sha256, rerun  # noqa: E402


def main(argv):
    kit = argv[argv.index("--rerun") + 1] if "--rerun" in argv else None
    out_dir = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else os.path.join(ROOT, "export")
    os.makedirs(out_dir, exist_ok=True)
    for institution in INSTITUTIONS:
        path = os.path.join(ROOT, "output", institution + ".jsonl")
        if not os.path.exists(path):
            print("%s: no output file, skipped" % institution)
            continue
        digest = sha256(path)
        with open(path, encoding="utf-8") as fh:
            decisions = [json.loads(line) for line in fh if line.strip()]
        count = lambda v: sum(1 for d in decisions if d["verdict"] == v)
        run = {"run_id": "%s-%s" % (institution, digest[:12]), "institution": institution,
               "output_sha256": digest, "repeat_runs": 0, "repeat_identical": None, "cases": len(decisions),
               "closes": count("CLOSE"), "rfis": count("RFI"), "escalations": count("ESCALATE"), "seconds": None}
        if kit:
            same, secs = rerun(institution, os.path.join(os.path.abspath(kit), institution), digest)
            run.update(repeat_runs=5, repeat_identical=same, seconds=round(secs, 2))
        target = os.path.join(out_dir, institution + ".json")
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"run": run, "decisions": [{k: d[k] for k in FIELDS} for d in decisions]},
                      fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
        print("%s: %d decisions, run %s%s -> %s" % (
            institution, len(decisions), run["run_id"],
            "" if not kit else ", five re-runs %s in %.1fs each" % ("identical" if same else "DIFFER", secs), target))


if __name__ == "__main__":
    main(sys.argv[1:])
