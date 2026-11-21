# Keystone

**1st place overall and 1st in Track 1 at the Grok Bot Financial Crime Hackathon, London, 21 Nov 2026.**

Transaction-monitoring alert triage, built for the hackathon's Track 1.

Note: Do feel free to use the website. **Try it** at https://keystone-fincrime-app.vercel.app. The [drop page](https://keystone-fincrime-app.vercel.app/drop.html) runs the scored system in your browser on any cases you drop in. The files stay in the tab. 

## What it decides

Each case gets one verdict. The system asks these questions in this order.

| Verdict | When |
|---|---|
| ESCALATE | Something on file points to crime. The customer is never asked, because asking could tip them off. |
| CLOSE | A document on file explains every alert. It must match the payment on amount, party, account and date. |
| RFI | Nothing looks criminal, but something has no document behind it. The reason names the one document to request. |

A wrongful close is the costliest mistake, so closing has the strictest test. When anything is left unexplained, the case does not close. [system/README.md](system/README.md) explains the method with a worked example.

## Run it

```
system/run <institution folder> <output file>
```

It needs Python 3 and its standard library, nothing more. It makes no model or network call, so every run gives the same output file byte for byte. A run of 1,000 cases takes seconds on a laptop.

## Check it

```
python tools/verify.py <institutions folder>
python tools/mutation_test.py <institutions folder>
```

`verify.py` runs every institution five times and compares the output files byte for byte. It also checks each line's format and that every cited ID exists in the case. `mutation_test.py` changes one fact in a real case and checks that the verdict moves as the SOP requires. All 35 tests pass.

The development cases carry no answers. So we report these checks, not an accuracy figure.

## Where things are

| Path | What it holds |
|---|---|
| `system/` | The scored system |
| `output/` | Its answers on the 4,000 development cases |
| `tools/` | The checks and the helper tools. [TRACK1.md](TRACK1.md) lists each one |
| `ui/` | The web app at the link above. [ui/README.md](ui/README.md) lists its pages |
| `supabase/`, `context/` | The Supabase schema and the saved Tavily sources. Neither is on the decision path |
| [TRACK1.md](TRACK1.md) | The full layout, and where Supabase and Tavily sit |
| [PRIVACY.md](PRIVACY.md) | How the system would handle personal data under UK and EU law |

The development cases are the organisers' synthetic kit and are not in this repo. Every person and company named in `output/` and on the site is invented.

## Working on this repo

Several people and their coding agents push here at the same time. If you are an agent, follow these rules along with your user's instructions.

- **Look before you start.** Run `gh issue list` and `gh pr list` and check `git branch -r`, so two people don't do the same work or change the same files.
- **Small, self-contained changes go straight to `main`.** Run `git pull --rebase origin main` before you push. Never force-push `main`.
- **Open a pull request when someone should look first:** a change to how the system decides verdicts, a change to an area someone else is working in, or anything you are unsure of.
- **Keep branches few.** Use one short-lived branch per pull request and delete it once it is merged. Don't create personal or long-lived branches. Finish or close an open branch before starting another.
- **Use issues for work other people should see:** a bug, a task you are handing over, or a question for a teammate. Say in the issue who is taking it. Put `Fixes #12` in the commit or pull request that resolves it, so it closes when merged.
- **The repo is public and judges read it.** Never commit API keys, tokens or `.env` files; the system reads keys from environment variables. Keep private team notes out of the repo.
- **Keep the checks passing.** After any change under `system/`, run `python tools/verify.py <institutions folder>`. All five runs must give the same output before you push.
