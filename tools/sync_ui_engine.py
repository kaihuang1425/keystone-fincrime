"""Copy the scored system into ui/engine/ so the drop page runs the same code in the browser.

    python tools/sync_ui_engine.py          # copy and write ui/engine/manifest.json
    python tools/sync_ui_engine.py --check  # exit 1 if ui/engine/ differs from system/ and tools/run_drop.py

The site is served from ui/ alone, so ui/drop.html cannot read system/ directly. This copies
system/run, every file in system/triage/ and tools/run_drop.py into ui/engine/, and lists each
file with its sha256 in manifest.json. The page checks every file it loads against that list and
shows the combined fingerprint. ui/engine/browser.py is the page's own driver and is listed too,
but it is never overwritten.

Run it after any change to system/ or tools/run_drop.py, before committing, or the page runs
older rules than the grader does.
"""
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ENGINE = os.path.join(ROOT, "ui", "engine")
OWN = ["browser.py"]  # lives in ui/engine/, not copied from anywhere


def sources():
    pairs = [(os.path.join(ROOT, "system", "run"), "run")]
    triage = os.path.join(ROOT, "system", "triage")
    for name in sorted(os.listdir(triage)):
        if name.endswith(".py"):
            pairs.append((os.path.join(triage, name), "triage/" + name))
    pairs.append((os.path.join(ROOT, "tools", "run_drop.py"), "run_drop.py"))
    return pairs


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def manifest():
    files = [{"path": dest, "sha256": digest(src)} for src, dest in sources()]
    files += [{"path": name, "sha256": digest(os.path.join(ENGINE, name))} for name in OWN]
    engine = hashlib.sha256("".join(f["path"] + f["sha256"] for f in files).encode()).hexdigest()
    return {"note": "Written by tools/sync_ui_engine.py. Copies of system/ and tools/run_drop.py.",
            "engine": engine, "files": files}


def main(argv):
    want = manifest()
    if "--check" in argv:
        stale = []
        for src, dest in sources():
            path = os.path.join(ENGINE, dest)
            if not os.path.exists(path) or digest(path) != digest(src):
                stale.append(dest)
        listed = os.path.join(ENGINE, "manifest.json")
        if not os.path.exists(listed) or json.load(open(listed, encoding="utf-8")) != want:
            stale.append("manifest.json")
        extra = set()
        for base, _, names in os.walk(os.path.join(ENGINE, "triage")):
            extra |= {"triage/" + n for n in names if n.endswith(".py")}
        extra -= {d for _, d in sources()}
        stale += sorted(extra)
        print("ui/engine/ is up to date" if not stale else "ui/engine/ is stale: " + ", ".join(stale))
        return 1 if stale else 0
    shutil.rmtree(os.path.join(ENGINE, "triage"), ignore_errors=True)
    for src, dest in sources():
        path = os.path.join(ENGINE, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(src, path)
    with open(os.path.join(ENGINE, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(want, fh, indent=2)
        fh.write("\n")
    print("copied %d files into ui/engine/, engine %s" % (len(want["files"]) - len(OWN), want["engine"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
