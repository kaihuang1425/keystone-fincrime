# Keystone UI

The interface for the transaction-monitoring system: plain HTML pages on one design system. No build step and no framework. Each page loads the files in `assets/` and nothing else, plus Geist from Google Fonts.

## Open it

Serve the folder rather than double-clicking, so the scripts behave as they do on a host:

```bash
python -m http.server 8080 --directory ui
```

Then go to http://localhost:8080/walk-monitoring.html.

## Pages

| Page | Shows |
|---|---|
| `walk-monitoring.html` | One case in five steps that play themselves: alert, records, evidence, rule, verdict. `?step=3` opens on a step, `?hold` starts paused |
| `app.html` | The case view: why a case closed, the comparison row by row, the verdict last, and the evidence behind it |
| `queue.html` | The alert queue worked one case after another to CLOSE, RFI or ESCALATE, and one RFI for the analyst to send |
| `phone.html` | An escalation reaching the MLRO on a phone, with nothing asked of the customer |
| `landing.html` | What it does, in three verdicts |
| `title-card.html`, `end-card.html` | 1920 × 1080 cards for the video; add `?raw` to record at full size |

## What is real

The cases on these pages are synthetic examples written in the kit's ID formats, so the interface can be seen before the system's output is wired in. They are not taken from the development cases, and nothing here is read by `system/`. To show real results, render the lines of `output/*.jsonl` into the same markup: the verdict chip, the reason code, the reason, and one citation chip per evidence ID.

## The design system

`RULES.md` holds the design rules: the house rules, every micro-interaction and every component. `assets/keystone.css` and `assets/keystone.js` are the base. `assets/fincrime.css` is the theme. `assets/keystone-walk.css` and `assets/keystone-walk.js` add the walkthrough, the staged reveals and the queue that works itself.

Verdicts use the brief's own words with one glyph each: ✓ CLOSE, ? RFI, ↑ ESCALATE, with the reason code beside in mono. Every verdict on screen carries the records it rests on.
