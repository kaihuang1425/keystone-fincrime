# Track 1. Alert triage

A system that reads transaction-monitoring cases and closes the ones the evidence explains. It asks the customer one question when a document is missing. It escalates to the MLRO when the file shows a sign of crime.

Start with [system/README.md](system/README.md). It explains the method in plain language with a worked example.

## Layout

| Path | What it holds |
|---|---|
| `system/` | The scored system. `system/run <institution folder> <output file>` |
| `output/` | The system's answers on the 4,000 development cases |
| `tools/verify.py` | Five-run repeatability, output checks and a leak check |
| `tools/mutation_test.py` | 27 tests that change one fact and check the verdict moves |
| `tools/export_ui.py` | Writes one JSON per institution for the UI, with the run facts |
| `tools/run_drop.py` | Runs the system on an archive or folder of cases in any layout and checks the output. Scores it when the right answers come with it |
| `tools/publish_supabase.py` | Copies finished output into Supabase for the UI and the audit trail |
| `tools/mlro_context.py` | Fetches official-source context with Tavily for corridor escalations |
| `supabase/schema.sql` | The tables the two tools above write to |
| `context/` | The saved Tavily sources |

## Check it yourself

```
python tools/verify.py <path to institutions>
python tools/mutation_test.py <path to institutions>
```

The first command runs every institution five times and compares the output files byte for byte. The second proves that verdicts follow the facts in the documents and not the mere presence of a document.

## Where Supabase and Tavily sit

The brief requires a system that reads only its input folder and gives the same answer on every run. So the decision path uses neither service. Both work on the finished output.

**Supabase** stores each run. A row in `triage_runs` holds the hash of the output file and whether five re-runs matched it. The rows in `triage_decisions` are an exact copy of the output lines. The UI reads the `latest_decisions` view.

```
SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python tools/publish_supabase.py --rerun <path to institutions>
```

**Tavily** answers the MLRO's first question on a corridor escalation, which is what the FATF says about that country now. The tool finds the FATF's newest dated lists and keeps only those, because an old list shown beside the current one can contradict it. Each saved source carries its list date and its URL. The tool does not rule on a country's status. It records whether the passage returned from the newest list names the country. It sends a country name and nothing else. The verdict never uses the result, and every saved row says so.

```
python tools/mlro_context.py <path to institutions>
```

Keys come from environment variables. No key belongs in this repository.

## Before submitting

The grader runs on Linux and calls `system/run` directly. After copying `system/`, `output/` and `.gitattributes` into the public repository, set the executable bit and confirm it.

```
git update-index --chmod=+x system/run
git ls-files -s system/run
```

The second command must print a mode of `100755`.
