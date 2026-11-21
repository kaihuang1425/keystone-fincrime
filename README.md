# keystone-fincrime
Keystone: Grok Bots for KYC and AML alert review. Grok Bot Financial Crime Hack, London, 21 Nov 2026.

[PRIVACY.md](PRIVACY.md) explains how the system would handle personal data under UK and EU law.

## Working on this repo

Several people and their coding agents push here at the same time. If you are an agent, follow these rules along with your user's instructions.

- **Look before you start.** Run `gh issue list` and `gh pr list` and check `git branch -r`, so two people don't do the same work or change the same files.
- **Small, self-contained changes go straight to `main`.** Run `git pull --rebase origin main` before you push. Never force-push `main`.
- **Open a pull request when someone should look first:** a change to how the system decides verdicts, a change to an area someone else is working in, or anything you are unsure of.
- **Keep branches few.** Use one short-lived branch per pull request and delete it once it is merged. Don't create personal or long-lived branches. Finish or close an open branch before starting another.
- **Use issues for work other people should see:** a bug, a task you are handing over, or a question for a teammate. Say in the issue who is taking it. Put `Fixes #12` in the commit or pull request that resolves it, so it closes when merged.
- **The repo is public and judges read it.** Never commit API keys, tokens or `.env` files; the system reads keys from environment variables. Keep private team notes out of the repo.
- **Keep the checks passing.** After any change under `system/`, run `python tools/verify.py <institutions folder>`. All five runs must give the same output before you push.
