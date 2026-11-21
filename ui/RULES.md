# Keystone rules · Financial Crime

Design rules for the app's interface. Load `assets/keystone.css` and `assets/keystone.js`.

Keystone is our team's design system, re-cut for the Grok Bot London Financial Crime Hackathon, Saturday 21 November 2026. It was first built for a real estate hackathon nine days earlier. The look, the bots and the motion are the same; the words and the cast are new. It fits both tracks, transaction monitoring and sanctions screening, because both have the same shape: a system reads an alert with its records, reaches one of three outcomes with a reason code, cites the records it relied on, and hands a person whatever it can't settle. It keeps the house rules from our AgentVerse winner, Trial Match (calm dark ground, two-beat headlines, sourced numbers, the product drawn in code, motion that means something), and speaks Grok Bot's visual language: simple shapes with two pill eyes, one colour per bot, and the avatar's motion as its status.

## House rules

1. **The avatar is the status.** A bot's motion says what it is doing (idle, working, thinking, waiting, blocked, done). Never add a spinner or status dot beside it. This is how Grok Bot itself shows state.
2. **Every verdict carries its records.** A verdict without its reason code and the IDs it rests on does not ship, and neither does a figure or a date without a `.k-cite`. Both briefs score the evidence behind a decision; make it visible on every screen.
3. **Nothing is closed on a guess.** The system closes or clears only what the evidence settles, on its own, and says why. Everything else reaches a person: an RFI to send, an escalation for the MLRO, a hit to review. That handover goes through an Approval card and ends in a toast with Undo.
4. **One colour per bot, for the whole demo.** Bot colours (`bot-blue`, `bot-pink` …) mean who. Status colours (`ok`, `ask`, `bad`, `info`) mean what. Never use a bot colour for status or a status colour for a bot.
5. **Status always has a glyph.** ✓ closed or cleared, ? needs a person, ↑ escalated, = confirmed match; ✕ only for a check that failed. Colour alone is never the signal.
6. **The spectrum is the bots' breath.** `spectrum-1` … `spectrum-5` appear only in the thinking trail, the loader and a live progress line. Never on text, cards or buttons.
7. **Headlines have two beats.** A plain statement, then a turn in `ink-4` (tension) or a resolution in `ink`. Big, weight 500, tight tracking.
8. **Show the product working, drawn in code.** Use scenes (`Keystone.scene`) with the demo's real data instead of screenshots or screen recordings on the landing page.
9. **Say what is real.** `.k-honest--synthetic` on every screen of made-up data; `--simulated` on anything faked; `--public` with dataset and date on real open data. Every record in the kit is invented by Diligent, and the label says so: "Invented data · Diligent dev set". Check any name from the kit before it goes on a public page or into the video, and keep off anything that reads as a real person or company.
10. **Blocked is a feature.** When a bot gets stuck, show it (`blocked` + Takeover) and recover on stage. A visible recovery beats a perfect run.
11. **Use the brief's words for a verdict.** CLOSE, RFI and ESCALATE in Track 1; DIFFERENT_ENTITY, SAME_ENTITY and REVIEW in Track 2. Never a synonym, and always with a reason code that belongs to it.
12. **The same answer every run.** Rules decide, and the screen says so (`Rules, not AI`). Where a model reads a document, show what it read.

## Content fundamentals

**Voice.** Plain British English a reader takes in within five seconds. One idea per sentence. Calm, specific, no exclamation marks, no emoji. Name things the way the briefs do: alert, case, hit, verdict, reason code, evidence, SOP, RFI, MLRO, internal list, tipping off, system of record, verified legal name. The people this is built for do the work for a living, so a wrong term costs more than a plain one.

**Headlines** are two beats: "Every alert, closed safely. *Every reason cited.*" / "Closed on evidence. *Never on a guess.*" / "One alert explained. *One needs a document.*"

**Let the layout explain.** Before adding a sub-line, caption, summary chip or helper sentence, check whether something on screen already says it. A bot's motion says its state. A ✓, ? or ✕ says the check. An arrow between two avatars says a handoff, a switch says on or off, and an Approve button says a person is needed. A value with no citation was worked out, not quoted. Keep figures, dates, citations, the reason behind a ? or ✕, honesty labels and controls. Cut everything else.

**Bots speak** in short present-tense lines and always say what they need: "Reading INV-7291", "Waiting on you: send the RFI". They speak only while the screen can't show it yet; once the answer lands, the answer and the bot's motion say the rest. Name each bot by its job (Document Bot, Payments Bot, Web Bot, Screening Bot, Match Bot) and tag it with what is really behind it in `.k-tool`: Grok Bot, Supabase, Tavily, or "Rules, not AI" for plain code. A partner being on the list is not a reason to tag it.

**Numbers.** UK formats: £3,150.72, £20,000 a month, 14 March 1986, 09:14. IDs appear exactly as the files write them (BK-CS112964, INV-7291, KYC-997803). A date quoted from a record keeps the record's format inside the document and ours in the field. Counts beat scores: "5 of 5 runs agree", "0 wrongly closed of 40 checked", not "94% confident" or "risk score 62". Pair a good number with a bad one. A vendor's figure says it is a vendor's figure; your own result says how you measured it.

**Honesty.** Never invent quotes, testimonials or outcomes. The kit's records are invented by Diligent; say so on every screen that shows them. Check any name from the kit before it goes on a public page or into the video: at least one reads as a real company. The system never calls anyone guilty. It says a hit "is the customer" or "is a different entity", and that a case is escalated "to the MLRO", never "sanctioned", "fraudster" or "criminal". Every limit comes from the institution's own `POLICY.md`. A number we have not measured stays a `[n]` placeholder.

**Avoid:** revolutionise, seamless, leverage, empower, unlock, cutting-edge, game-changing, AI-powered (as a selling point), robust, holistic, solution (as a noun), "simply", "just", and long dashes as a crutch.

## Visual foundations

**Grounds and surfaces.** Page on `ground`; alternate bands and the roster on `ground-2`; cards and tables on `surface`; bubbles, chips and inputs on `surface-2`; raised controls on `surface-3`. Depth comes from tone, not borders: a card's only edge is a 1px inset `hairline`. `line` divides rows; `line-strong` outlines controls (3:1 on every surface).

**Ink.** `ink` for headlines and body; `ink-2` for leads and bot bubbles; `ink-3` for meta, table heads and mono sources (all 4.5:1 or better on every surface in both themes); `ink-4` only for the grey second beat of a headline at 24px and up.

**Action.** `primary` is ink: the one Approve or Send pill per view, and the person's own message bubble, with `on-primary` text. Links, citations and focus use `info` and `focus`.

**Status.** `ok`, `ask`, `bad`, `info`, each with a `-soft` fill and full-strength text of the same hue. `live` only on the pulsing LIVE dot of genuinely live data.

**Bots.** `bot-chief` (white on dark, ink on light, with `bot-chief-eye`), and six identity colours with white `bot-eye`: `bot-blue`, `bot-pink`, `bot-orange`, `bot-green`, `bot-violet`, `bot-teal`. Each has a `-deep` twin for duotone title cards, with `on-deep` text.

**EPC.** `epc-a` … `epc-g` stay in the tokens, but nothing at this hackathon uses them.

**Type.** Geist for everything (`--font-sans`), Geist Mono for citations, IDs, timings and tool tags (`--font-mono`). Styles: `display` 64, `h1` 44, `h2` 30, `h3` 20 (all 500, tight tracking), `lead` 19, `body` 16, `small` 14, `caption` 12.5; data in `bignum` 72/300, `figure` 22/500, `mono` 13, `mono-sm` 11.5, `label` 11 caps. Tabular figures wherever numbers change. Headings balance.

**Shape and space.** Every button, switch and pill is fully round (`radius-pill`). Cards `radius-lg`, approvals and title cards `radius-xl`, inputs and documents `radius-sm`, chips `radius-xs`. Spacing steps `space-1` (4px) to `space-24` (96px); 16px minimum page gutter.

**Elevation.** Flat by default. `shadow-float` only on toasts, popovers and flying chips; `shadow-window` only on an app window placed on the stage ground.

**Layout.** Build the demo app on AppShell: Roster and routines (268px, `ground-2`), the conversation with Case Lead (up to 760px, composer pinned to the bottom), and Evidence (392px, tabs for Source, Compare and Trace). Below 1180px evidence slides in over the conversation; below 760px the roster becomes a strip of avatars, the chat header and composer stick, and evidence opens as a bottom sheet.

**Desktop and mobile are built separately.** Write layout CSS in two ranges that never overlap: `@media (min-width: 761px)` for desktop and tablet, `@media (max-width: 760px)` for phones. Only colour, type and the inside of components are shared. Never put layout sizes in inline styles (they cannot change per range), never let a phone rule depend on a desktop rule, and never reuse a class name for a different job (the headline's grey beat is `.k-turn`; a chat row is `.k-msgrow`). Every screen has a phone layout of its own, not a shrunken desktop: below 760px the type steps down (`display` 40, `h1` 30, `h2` 24, `h3` 18) and fixed boards such as the video cards reflow to portrait.

**Themes.** Dark (stage) is the default for the video, the landing page and the stage screen. Light (desk) is a full theme for an ops app or a washed-out projector: switch `data-theme="light"` on the root. Both pass the same contrast rules.

**Focus.** A solid 2px `focus` ring with a 2px gap on every interactive element.

## The bots

**Construction.** A body shape plus two white pill eyes, tilted 22°, sitting high and to the right (looking up, curious). Eight shapes: `house` (the chief only), `circle`, `squircle`, `drop`, `cloud`, `flower`, `pill`, `triangle`. One shape and one colour per bot. Draw them with `Keystone.bot` or `[data-k-bot]`; never as images or emoji.

**The cast.** Case Lead (`house` + `chief`) is the one bot people talk to; it routes work to up to six specialists, like Grok Bot's chief-of-staff pattern (Grok Bot group chats take six bots). Defaults, as the canvas draws them: Document Bot `doc blue` reads the documents on file; Payments Bot `card pink` reads the alert and the transactions; Web Bot `browser orange` reads search results and drops namesakes; Screening Bot `lens green` reads the list entry or the hit's profile; Match Bot `venn teal` compares names, dates and countries by the SOP's rules. Show four at most; keep the pairs stable. The canvas draws Case Lead as a `shield`; `keystone.js` draws the original eight shapes, so in the app each new shape falls back to the one it replaced (shield to house, doc to squircle, card to cloud, browser to drop, lens to flower, venn to triangle).

**States.** `idle` breathes and glances; `ack()` hops when work arrives; `working` widens its eyes and rocks; `thinking` folds into its own three dots with a spectrum trail; `waiting` drifts its eyes and pulses an `ask` halo; `blocked` spins down into a "!"; `done` pops back with happy eyes and sparks. Put the current action in `data-say`: hover or focus reveals it (progressive disclosure).

**Respect the hosts' brands.** Keystone borrows Grok Bot's public avatar grammar so our bots feel native beside it. It does not use the Grok Bot or SpaceXSI logos or wordmarks, and our product is never presented as a SpaceXSI product. Credit it as text: "Built with Grok Bot and Cursor". The same goes for Diligent: no logo, no wordmark, and nothing that suggests our product is theirs or has their backing. Their published figures appear only as cited vendor figures.

## Motion

Use `ease-out` for almost everything, `ease-spring` for things that pop (hops, checks, badges, the done pop), `ease-glance` for things that travel (eyes, flying chips, highlight sweeps), `ease-exit` for things that leave. Durations: `dur-tap` press, `dur-flip` a changing line, `dur-ack` a hop, `dur-reveal` a block rising out of a blur, `dur-relay` one handoff, `dur-loop` a scene.

Every movement means something: a bot's state, a value travelling from its source, a check confirming, a number counting to its value. Blocks rise out of a blur; status lines flip up; a working line shimmers. Animate only transform, opacity and filter. Scenes and relays play only while on screen. Motion plays on every device, including phones set to Reduce Motion: the motion is the bots' status, and a phone with Reduce Motion on would otherwise show a frozen demo. To honour the OS setting instead, put `data-k-motion="system"` on `<html>`; every loop then stops on its final frame, which still reads (the dots, the "!", the happy eyes). Hover effects are scoped so a tap on a touch screen never leaves a button stuck in its hover state. The micro-interactions section lists every movement.

## Iconography

Inline stroke icons on a 24px grid, 1.75 stroke, round caps and joins, `currentColor` (`Keystone.icons`: doc, clock, check, route, spark, wrench, shield, pin, plus, mic, send, gear, building, globe, cursor). Use `doc` for document citations, `globe` for web sources and `shield` for a policy or a held payment. No emoji in the interface; the ✓ ? ✕ glyphs inside status marks are the one exception. There are no logo files: the product name is set in Geist 500 until the team has a mark, and sponsor names appear as `.k-tool` text, never as logos.

## Using it in code

The CSS and JavaScript are the original Keystone's, unchanged. Load the fonts, then `keystone.css`, then `keystone.js` (it defines `window.Keystone`, mounts every `[data-k-bot]` and wires approvals, switches and citations by data attribute). Both are in `assets/`. The same folder has `fincrime.css` (the canvas's cooler grounds and its financial crime pieces), and `keystone-walk.css` with `keystone-walk.js` for the walkthrough; load them after Keystone. In React or Next.js, import the CSS once globally, keep the class names, and call `Keystone.bot(ref.current)` in an effect. With Tailwind, map tokens into the theme (`colors: { ground: 'var(--ground)' }`) and keep the component classes. Copy markup from the pages in this folder rather than retyping it.

## Renamed for this hackathon

Four components do a new job here. Their class names are the original ones, because the CSS has not changed.

| Called here | Keystone component | Classes | Job |
|---|---|---|---|
| Checks | Compliance | `.k-comply` | The alerts in a case or the hits in an alert, each with its outcome and its records |
| Meter | Covenant | `.k-meter` | A figure against a line the customer or the SOP set: money in against declared turnover |
| Queue | RentRoll | `.k-table`, `.k-raw`, `Keystone.liveRow` | The queue of cases or alerts, each with its verdict, updating as the run goes |
| Case | Ticket | `.k-ticket` | What a person is handed: the drafted RFI, an escalation, a hit to review |

The ExtractionTable is used as the Compare table: one row per ground (name, date of birth, location) or per alert, with both sides and Agrees, Contradicts or Can't compare in words. PropertyCard, EPC and Map are not used. The Loader keeps its bars and hides its roof cap (`.k-loader__cap{display:none}`).

# Micro-interactions

Every movement in Keystone, what triggers it, how it moves, what it tells the viewer and which of the five judging criteria it serves (execution, a working prototype, whether it solves the problem, creativity, UX). All are built into `keystone.css` and `keystone.js`; the last column says how to call them.

## The bots

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Glance and blink | Bot is idle | Eyes jump to a new spot every 1.4–3.4 s on `ease-glance`; a 120 ms blink every 3–5 s; body breathes over 4.8 s | It is alive and listening | UX | `set('idle')` |
| Acknowledge | A task reaches the bot | One hop on `ease-spring` (`dur-ack`): squash, rise 14px, land; eyes grow 25% | Got it | UX | `ack()` |
| Working | A tool or browser step runs | Eyes 18% larger, looking up-right; body rocks ±4° every 0.85 s; quick glances every 0.5–1.1 s | Busy, making progress | UX | `set('working')` |
| Thinking | A model call is out | Body folds to a dot in 420 ms; two grey dots join; the three wave every 1.1 s; a spectrum trail circles every 1.15 s | Reasoning, nothing to see yet | UX | `set('thinking')` |
| Waiting on you | It needs an answer or approval | Eyes drift side to side every 1.6 s; slow ±2° lean; an `ask` halo pulses every 2.4 s | Your move | Solves the problem | `set('waiting')` |
| Blocked | It cannot continue | Spins 540° while shrinking (620 ms), the bar of a "!" springs up from the dot, then a wiggle every 2.6 s | Help needed | Execution | `set('blocked')` + Takeover |
| Done | The job finished | Pops from 25% to 109% to 100% (700 ms spring); eyes turn upright and happy; six sparks fly out | Finished | UX | `set('done')` |
| Current action | Hover or focus on an avatar | A tooltip rises 4px in 160 ms | What exactly it is doing | UX | `say(text)` |

## Status and progress

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Status flip | A bot's line changes | The new line rises 6px out of a 3px blur in 320 ms | Something changed | UX | `Keystone.flip(el, text)` |
| Working shimmer | While the line is live | A light runs through the text every 1.8 s | Still going | UX | `Keystone.status(el, text, true)` |
| Action feed | Each step completes | A row rises out of a blur; the newest shimmers; old rows fade under a mask | Reassurance, step by step | Working prototype | `Keystone.feed(el, rows)` |
| Count up | A number arrives | Counts to its value in 850 ms, ease-out cubic, tabular | The size of the thing | Solves the problem | `Keystone.count(el, to, opts)` |
| Loading steps | The app loads its data | Bars fill with the spectrum, one per step; a % tag rides up; steps tick into a list; the screen slides up at Ready. The original's roof cap is hidden here | The product is working, not loading | Working prototype | `Keystone.loader(opts)` + `.k-loader__cap{display:none}` |
| Rise out of blur | A block scrolls in | 28px rise and 8px blur clearing in 480 ms | Read this next | UX | `Keystone.reveal()` + `data-k-reveal` |

## Evidence

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Citation peek | Hover, focus or tap a `.k-cite` | The source line drops in under it in 160 ms | Where this came from | Solves the problem | built in |
| Highlight sweep | A source phrase is found | A blue marker grows left to right across the phrase in 700 ms | This exact phrase | Solves the problem | `.k-hl.is-on` |
| Value flight | A value is extracted | A mono chip arcs from the passage to its field in 760 ms; the field pulses once as it lands | The value and its source are linked | Creativity | `Keystone.fly(from, to, html, { cite: true })` |
| Trace draw | A trace opens | A blue line draws down the chain in 1.2 s; steps light 250 ms apart | The chain of custody | Solves the problem | `.k-trace.is-on` |
| Live row | A new record arrives | The row slides in from 6px above with a blue wash that fades over 1.6 s | Live data, just now | Working prototype | `Keystone.liveRow(tbody, html)` |
| Cleaned value | A messy value is normalised | The raw string sits struck through in mono beside the clean value ("SMITH, John" beside John Smith) | What the bot changed | Solves the problem | `.k-raw` |

## Decisions

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Approve | Approve is pressed | The pill collapses to a circle and a check draws in 420 ms; the card folds away (480 ms, `ease-exit`); a toast springs in | Decided and logged | Solves the problem | `data-k-approve="toast text"` |
| Learning saved | A learnt rule is kept | Same as Approve; the bot's rule count bumps | The bot just got better | Creativity | `data-k-approve` + `.k-count-bump` |
| Toast and Undo | Any action | Springs up from 16px; a hairline shrinks over 5 s; Undo restores | It happened, and it can be undone | UX | `Keystone.toast(text, { undo })` |
| Routine switch | A routine is turned on | The knob springs across in 320 ms; the clock hand turns once in 900 ms | Scheduled work | Solves the problem | `.k-switch` |
| Takeover | Take over is pressed | The bot's screen gets a focus-blue ring, a cursor glides in; Hand back sets the bot to done with a toast | The person stepped in, then delegated again | Execution | `.k-takeover.is-yours` |
| Press | Any button | Shrinks to 96% in 160 ms; the primary lifts 1px on hover; an arrow nudges 3px | Tactile, responsive | UX | built in |
| Voice | The voice button is live | Five bars bounce at staggered phases | Listening | UX | `.k-voice.is-live` |

## The two tracks

The same CSS as the real estate version, doing new jobs. The class names have not changed.

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Verdict lands | A case or a hit is decided | The verdict chip pops in on `ease-spring`; the reason code flips in beside it | Decided, and on what ground | Solves the problem | `.k-chip` + `Keystone.flip` |
| Open alert pulse | An alert in the case is not yet explained | A rose ring pulses from its mark every 2 s | This one is not settled | Solves the problem | `.k-comply__row.is-bad` |
| Explained sweep | A document explains an alert | A green light sweeps the row in 1.1 s; the mark pops to ✓ | Explained | Working prototype | `.is-fixed` |
| Line crossed | A figure is measured against a line | The fill eases in 1 s; amber when a person is needed, rose past the limit; the value flips | How far past the line | Solves the problem | `.k-meter`, `.is-ask`, `.is-bad` |
| Handover | A case is handed to a person | Chips pop in 120 ms apart: the verdict, the reason code, who it goes to | Whose move it is | Solves the problem | `.k-ticket__tags` |
| Decide-by ring | A decision has a deadline | A ring empties as the time runs down | How long you have | UX | `.k-sla` |

Not used at this hackathon: the EPC bars, the map's pin drop and the tower fill. They stay in the CSS; leave them off the screen.

## Walkthrough and staged motion

A story told in numbered steps that plays itself, with the source on the left and what the system concludes on the right. It lives in `keystone-walk.css` and `keystone-walk.js`, loaded after Keystone.

Its shape follows the organisers' own "What is financial crime?" explainer: steps that advance by themselves, a tab that shows how long each step has left, pieces that arrive in reading order, and the verdict held for the last beat. The drawing, the timing and the code are ours.

| Interaction | Trigger | Motion | Tells the viewer | Serves | Call |
|---|---|---|---|---|---|
| Step progress | A step is on screen | The tab's own line fills left to right over the step's length, in the spectrum; finished steps keep a full grey line | How long this step has left | UX | `.kw-tab` with `--dur` |
| Staged reveal | A step opens | Each piece rises 10px out of a 4px blur in 450 ms, in reading order, at its own `--d` | Read this, then this | UX | `.kw-r` with `--d` |
| Resolving mark | A fact is being read | Three dots bounce where the mark will be; at `--m` they shrink away and the mark pops in on the spring | Found, or needs a person | Solves the problem | `.kw-swap` with `--m` |
| Cued highlight | A source phrase is about to be used | The marker sweeps across it in 700 ms, just before the row that cites it appears | This phrase, then that row | Solves the problem | `.kw-hl` with `--d` |
| Path draw | Records are followed one to the next | Each dot's line draws down from the one before in 350 ms; the last dot fills | The route through the systems | Creativity | `.kw-path__step` |
| Deciding row | A comparison settles it | The row that decides takes the info wash, and its word turns to ink | This is the ground | Solves the problem | `.kw-cmp.is-key` |
| Verdict lands | The step's last beat | The verdict block scales from 94% through 102% to rest on the spring, after at least a second of quiet | Decided | Solves the problem | `.kw-verdict.kw-r` |
| Runs agree | The system is run again | One mark per run pops in, 120 ms apart | The same answer every time | Execution | `.kw-runs` |
| Queue works itself | The queue is on screen | Each case waits as Queued, shows what is being checked from `--w`, then at `--m` its mark resolves, its result line rises and its verdict chip pops in with the reason code; a tally of the three verdicts lands last | The work is being done, one case at a time | Working prototype | `.kq-row` with `--w` and `--m` |

**Timing.** A step lasts 7 to 9 seconds. Pieces arrive about 0.8 s apart. A mark resolves 0.7 s after its row arrives. Nothing new appears in a step's last 1.5 s, so the verdict can be read.

**Behaviour.** It plays only while on screen. A tab left in the background does not skip steps. Picking a step by hand, or with the arrow keys, pauses it. `?step=3` opens on a step and `?hold` starts paused, for recording one step at a time.

## Rules for new motion

- One meaning per movement. If you can't say what it tells the viewer in four words, cut it.
- Animate only transform, opacity, filter and background-position. Keep blurs at 8px or less on large areas.
- Loops play only while on screen (`Keystone.whenVisible`, `Keystone.scene`).
- Motion plays everywhere, Reduce Motion included (the house choice). With `data-k-motion="system"` on `<html>` the OS setting wins and every bot state still reads from its final frame.
- Test on an iPhone before the demo: Safari runs all of this, and a tap must never leave a hover state behind.

# Components

Every Keystone component, with the job it does at the financial crime hackathon. The markup and class names are the original Keystone's and work with the unchanged `keystone.css` and `keystone.js`. The examples use IDs in the format of the brief's own sample. Copy working markup from the pages in this folder.

## AppShell

The whole demo app in one frame: the bot roster on the left, the conversation with Case Lead in the middle, and the evidence for the last answer on the right. On phones it becomes a bot strip, a sticky chat header, a pinned composer and an evidence sheet.

**Use it** as the root of the demo app. It fills the window (`100dvh`) and each column scrolls on its own.

**Parts.**
- `.k-app` root, with `data-theme` for Stage (dark) or Desk (light).
- `.k-app__side`: `.k-side__brand`, a queue switcher button ("Bank · 1,000 cases"), `.k-side__section` with the Roster, `.k-side__section.is-routines` with `.k-rrow` rows (clock icon, name, schedule in mono, a `.k-switch--sm`), and `.k-side__foot` with `.k-me`, the analyst's name and a `.k-seg` theme switch (`data-k-theme="dark"` / `"light"`).
- `.k-app__main`: `.k-app__head` with a centred `.k-chathead` pill (Case Lead's avatar and name) and `.k-app__headend` (the invented-data label and an "Evidence" button with `data-k-toggle="evidence"`); `.k-app__scroll > .k-app__col` holding the person's `.k-msg--me`, `.k-handrow` handoffs (two avatars, an arrow, the case) and `.k-msgrow` rows (avatar gutter, `.k-msgrow__who`, `.k-msgrow__body` with prose, cards or an Approval); `.k-app__dock` with suggestions and the AskBar.
- `.k-app__scrim` and `.k-app__aside[data-k-tabs]`: `.k-panelhead`, a `.k-seg.k-seg--fill` of `[data-k-tab]` buttons, and one `.k-tabpanel[data-k-panel]` per tab: Source, Compare and Trace. Tool tags (`.k-tool`) belong in the Trace, where provenance is the point.

**Behaviour (built in, by data attribute).** `[data-k-tab]` switches panels inside its `[data-k-tabs]` box; `[data-k-theme]` sets the theme on the nearest `[data-theme]`; `[data-k-toggle="evidence"]` opens and closes the evidence panel below 1180px.

**Widths.** Above 1180px: three columns (268 / fluid / 392). 760 to 1180px: the evidence slides in over the conversation. Below 760px: the roster becomes a strip of avatars, routines and the profile footer hide, the chat header and the composer stick, and evidence opens as a sheet.

**Keep the chrome quiet.** No status line in the header, no sub-lines in the roster, no section labels, no counts in the panel head, no fine print under the composer. Keep one Approval waiting at a time, and scroll the conversation to the newest turn when it arrives.

## Roster

The sidebar list of bots: who is on the team, with each avatar's motion saying what it is doing now.

**Markup.** `nav.k-roster > button.k-roster__item` holding a `[data-k-bot]`, a `.k-grow` with `.k-roster__name` (and an optional `.k-roster__sub`), and an optional `.k-badge` count of items waiting on the person. The chief sits first; the selected bot gets `aria-current="true"`.

**Behaviour.** When the work changes, change the avatar state (`bot.set`) and its hover text (`bot.say`). Add a `.k-roster__sub` only for something motion can't show, such as the record a bot is reading ("INV-7291"), keep it under 40 characters, and change it with `Keystone.flip(sub, text)`.

## BotAvatar

A bot's face: its shape and colour say which bot it is, its motion says what it is doing, so nobody needs a separate status light.

**Markup.** `<span data-k-bot data-shape="squircle" data-color="blue" data-name="Document Bot" data-state="working" data-say="Reading INV-7291"></span>`. `Keystone.mount()` runs on load and draws every `[data-k-bot]`. Size with `--size` (default 40px; roster 32, thread 20 to 32, relay 56).

**Control it.** `const b = Keystone.bot(el)` returns `{ set(state), ack(), say(text), look(x, y), blink() }`. Call `b.ack()` the moment work arrives, then `b.set('working')`.

| State | Looks like | Use when |
|---|---|---|
| `idle` | slow breath, eyes glance and blink | nothing to do; the default |
| `ack()` | one hop, wide eyes | a task just arrived (a one-beat class, not a state) |
| `working` | eyes wide and up, a steady rock | a tool call or browsing step is running |
| `thinking` | folds into three dots, a spectrum trail circles | a model call is out and nothing is visible yet |
| `waiting` | eyes drift, amber halo | the bot needs a person: an answer, an approval |
| `blocked` | spins into the dot of a "!", then wiggles | it cannot continue: a login, a missing document. Show Takeover beside it |
| `done` | pops back, happy eyes, sparks | a job finished; settle to `idle` after a few seconds |

**The cast, as the canvas draws it.** Case Lead `shield chief`, Document Bot `doc blue`, Payments Bot `card pink`, Web Bot `browser orange`, Screening Bot `lens green`, Match Bot `venn teal`. `keystone.js` draws the original eight shapes, so in the app each new shape falls back to the one it replaced: shield to `house`, doc to `squircle`, card to `cloud`, browser to `drop`, lens to `flower`, venn to `triangle`. One bot per job; never recolour a bot mid-demo. People get `circle` + `chief` only in the Handoff's last node, labelled "You".

**Don't** add a spinner, dots or a status dot next to an avatar. The avatar is the status.

## Thread

A conversation with a bot: the person's message in an ink bubble, the bot's answer in prose with citations, and inline events for what the bot did along the way.

**Use it** for the main column. Prose when the answer is a sentence; a structured component (Compare table, Meter, Approval) when the answer is data. Two to four sentences, then a component. Never a wall of text.

**Parts.** `.k-msg.k-msg--me`, `.k-msgrow` (avatar, `.k-msgrow__who`, `.k-msgrow__body`), `.k-from` (small avatar + name + a `.k-say` status line), `.k-handrow`, `.k-event` (an icon, a bold verb, a detail). Every finding in a bot's answer carries a `.k-cite`.

**Status line.** `Keystone.status(sayEl, 'Comparing dates of birth', true)` flips the line and shimmers it while working. Remove it when the answer lands.

**Inline events** record what a bot did on its own: "Read 3 documents", "Messaged Match Bot", "Wrote 200 verdicts". They are the evidence of Grok Bot at work; show them.

## AskBar

The composer for talking to Case Lead: suggestion chips above a pill field with attach and dictate, and the round voice button beside it.

**Markup.** `.k-suggest` buttons; `form.k-ask > .k-ask__field` (attach `.k-iconbtn`, `label.k-sr`, `input`, dictate) + `.k-voice`. Handle `submit` with `preventDefault()`.

**Suggestions** are real questions the demo can answer ("Why was BK-CS112964 closed?"). Tapping one types it in.

## Citation

A small mono chip after any finding that names its source; hover, focus or tap shows the line it came from.

**Use it** on every figure, date and match: in prose, tables, tiles and toasts. It is the visible form of "explainable, auditable, and defensible".

**Markup.** `<button class="k-cite">{doc icon}INV-7291<span class="k-cite__pop">The line, paraphrased or quoted.<small>Invoice · Diligent dev set · invented</small></span></button>`. Use the globe icon for web sources.

**Rules.** The label is the record's own ID, exactly as the files write it ("INV-7291", "KYC-997803", "BK-L37007"), never "Source". These are the same IDs the system writes in `evidence`. The pop names the kind of record and says the data is invented. If there is no source, there is no finding: show an ask chip instead.

## SourcePeek

The traceability moment: a source document beside the fields taken from it. The passage highlights and its value flies into the field with its citation.

**Use it** once, as the hero scene: an invoice, a register extract, an identity check, a hit's profile.

**Parts.** `article.k-doc` with `.k-doc__head` and text where each source phrase is a `.k-hl`; a column of `.k-field` (label + `.k-field__val`).

**Script.** Add `.is-on` to a `.k-hl`, then `Keystone.fly(hl, field, '2 Nov 1971', { cite: true })`, then fill the value with a `.k-cite` and replay `.is-landed`. Pace: 0.8 s to highlight, 0.8 s to fly, 1.2 s to read. A value the bot worked out gets an ask chip, not a citation.

## ExtractionTable (here: the Compare table)

One row per ground the SOP names, with both sides and whether they agree.

**Use it** in Track 2 for name, date of birth, location, time and type; in Track 1 for the alerts in a case and what explains each.

**Markup.** `.k-tablewrap > table.k-table` with columns Ground, The hit (the value and a `.k-cite`, with the customer's in `.k-why`) and a last column that says Agrees, Contradicts or Can't compare in words. Do not use ✓ and ✕ here: in Track 2 a contradiction is what clears a hit. Rows that leave it to a person get `tr.is-ask`. A cleaned value shows its raw form in `.k-raw` ("SMITH, John").

**Rules.** Follow the SOP, not a tally: one contradiction clears, agreement on the named grounds confirms, anything else is `REVIEW`. A ground that can't be compared says so, never a guess and never a silent pass.

## Covenant (here: the Meter)

A figure against a line: money in against what the customer declared, or an amount against a limit the SOP sets.

**Markup.** `.k-meter` with `--t` (the line's position), `.k-meter__top` (label + `.k-meter__val`), `.k-meter__bar > .k-meter__fill` (set `width`) + `.k-meter__line[data-label="declared £20,000"]`, and `.k-meter__foot` with one sentence and a `.k-cite` to the policy clause. Add `.is-ask` or `.is-bad` to colour the fill.

**Write** what the figure means in one sentence: "Money in is 2.7 times what the bakery declared." Take every limit from the institution's `POLICY.md`, never from memory. If the line sits at the right edge, right-align its label so it stays inside the card.

## Compliance (here: Checks)

A list of the alerts in a case, or the hits in an alert, each with its outcome and its records.

**Use it** to show why a case got its one verdict: every alert explained means CLOSE, and one unexplained alert decides the case. An open row pulses rose; an explained one sweeps green and ticks.

**Markup.** `.k-comply > .k-comply__row` (`.is-bad`, `.is-ask`, `.is-fixed`) with a `.k-mk`, a `b` + `small` (the finding and its reason), and `.k-comply__due` in mono holding the source or a small action button.

**Rows.** One per alert or hit: what fired in `b`, what explains it or fails to in `small`, and the reason code in `.k-comply__due`.

**Honesty.** Every limit and clause comes from the institution's own `POLICY.md`.

## RentRoll (here: the Queue)

The queue of cases or alerts, each with its verdict, updating as the run goes.

**Markup.** `.k-table` with the case or alert ID in mono, the customer (with `.k-raw` struck through when a messy name was normalised), the rules or hits, and a verdict chip. Insert a new row with `Keystone.liveRow(tbody, html)`: it slides in with a blue wash that fades.

**Rules.** The chip is the verdict in the brief's words (✓ CLOSE, ? RFI, ↑ ESCALATE; ✓ DIFFERENT_ENTITY, ? REVIEW, = SAME_ENTITY) with the reason code beside it in mono. `.k-live` only while a run is really in progress.

## Ticket (here: the Case)

What a person is handed when the system will not close: the drafted RFI, an escalation, or a hit to review.

**Use it** for the one question to ask a customer, the summary an MLRO receives, or a `REVIEW` hit with everything gathered so far.

**Parts.** `.k-ticket__msg` (the drafted request or the summary, with who it goes to in `small`), optional `.k-ticket__tags`, a `dl` plan (each line with its `.k-cite`, a `.k-sla` decide-by ring), and one primary button.

**Rules.** An RFI asks for exactly one document or answer. An escalation never shows a question to the customer: asking at that point risks tipping them off. Urgency is a chip with a glyph, never red text alone.

## Approval

The handover to a person: a card with what is proposed, its records, and one button. Approving folds the card into the audit trail with Undo.

**Use it** for what the system must not do alone: sending an RFI to a customer, passing a case to the MLRO, settling a `REVIEW` hit, saving a learnt rule. Do not put one on a CLOSE the evidence already settled; that is the work the system is there to take away.

**Markup.** `section.k-approve` with `.k-approve__head` (avatar in `waiting` + title + source line), the change (`.k-diff` with `.k-del` / `.k-add` rows, each with a `.k-cite`), and `.k-approve__actions`: a text button (Escalate or Dismiss), an Edit ghost button, and one primary `data-k-approve="RFI sent. The case waits for one document."`.

**Behaviour (built in).** Approve morphs into a drawn check, the card folds away, and a toast confirms with Undo. Events: `k:approve`, `k:undo` on the card.

**Learning variant.** `.k-learn` with a spark icon: "Learnt from your edit" and the rule in plain words. Approving it is how a policy changes on stage.

## Toast

One line that says what just happened, with Undo where it can be undone, gone after five seconds.

**Use it** after every action. `Keystone.toast('RFI sent. The case waits for one document.', { undo: fn })`. Options: `mark: 'ok' | 'ask' | 'bad' | false`, `ms`.

**Write** past tense, specific: "Closed. INV-7291 matches the payment." Not "Success!".

## Trace

The chain behind a claim: the claim, each step that produced it (which bot, which tool, what it kept and dropped), and the sources.

**Markup.** `.k-trace > .k-trace__line` + `.k-trace__step.is-claim` + `.k-trace__step` rows (a `.k-row` with a small avatar, a bold action and a `.k-tool`, then a `small` detail). Add `.is-on` to play.

**Write** what was dropped as well as what was kept. Tag plain code as "Rules, not AI" and anything faked as "(simulated)". In Track 2 the Trace is the path through the systems, written the way the practice labels write it: the link followed, the customer record, the latest approved check, then the decision.

## Routine

Work that starts without a prompt: a name, a schedule in mono, an on/off switch, and the last run's result.

**Use it** for work that runs without a prompt: "Work the overnight queue · Daily 06:00", "Run again when the SOP changes". Two or three are enough, and only ones the system really does.

**Markup.** `.k-card.k-routine.is-on` with `.k-routine__clock`, name and `.k-routine__when`, a `button.k-switch[role=switch][aria-checked]`, and `.k-routine__last`. In the app's sidebar use the compact `.k-rrow`. Listen for `k:toggle`.

## Handoff

The team as a relay: each bot does one job and passes a named result to the next, and the last node is always the person who decides.

**Use it** once, on the landing page. Three to five nodes (`style="--n:4"`).

**Markup.** `.k-relay > .k-relay__track` + one `.k-relay__node` per step with `data-idle`, `data-doing`, `data-done` and `data-pass` (the chip that travels on: "3 cited records"). Inside: an avatar, a bold name, a `.k-tool` tag and a `small` line.

**Script.** `Keystone.relay(el, { every: 1800 })` plays while on screen. Under it, a beats line: "Case Lead routes. Bots read and check. You decide."

## Takeover

When a bot is blocked, a person steps into the bot's own computer, fixes the one thing, and hands it back.

**Markup.** `section.k-takeover` with a head (avatar + reason), `.k-takeover__screen` (bar + page lines + `.k-cursor`) and actions. Toggle `.is-yours` while the person has control. On Hand back, set the bot to `done` and toast what it finished.

**Write** the reason as the bot would say it: "The file for INV-7291 would not open." A recovered block is a stronger demo than a perfect run.

## Metrics

Big light numbers in a slab of tiles, each counting up, each with its source and how it was measured.

**Use it** for the two to four figures that matter: runs that agree out of 5, wrong closes on a hand-checked sample, time for 200 cases; in Track 2, practice labels right out of 50.

**Markup.** `.k-metrics > .k-metric` with `.k-metric__label`, `.k-metric__val` (`.is-ok` / `.is-bad` when the colour means something), and a row with a `.k-cite` and `.k-metric__how`. Count up with `Keystone.count(el, 800)`.

**Rules.** Our own result says how we measured it ("40 cases checked by hand, 21 Nov"). A figure from the brief cites the brief. An unmeasured number stays a `[n]` placeholder.

## ActionFeed

A short, live list of the steps a bot is taking, each with a mono detail, for the person who wants reassurance.

**Use it** behind a hover or a "Show steps" toggle next to a working bot, never as the main view.

**Markup and script.** `<div class="k-feed"><div class="k-feed__list"></div></div>`, then `Keystone.feed(el, [['Read the invoice', 'INV-7291'], …], { every: 1200 })`.

**Write steps** as past-tense verbs with a concrete result: "Normalised the name · \"SMITH, John\" → John Smith". Real results from the run, never filler.

## Loader

The splash: bars that fill with the spectrum, one per step, a percentage riding up, and the steps ticking into a list before the screen slides away.

**Use it** as the splash for the demo. It waits for real data: `const l = Keystone.loader({ steps, wait: fetchPromise, max: 8000 })` or call `l.done()`. It eases to 86% by itself and only reaches 100% when the data is in.

**Steps.** Two to four, each under 32 characters, written as what the product does: `['Reading 200 cases', 'bank']`, `['Citing every reason']`.

**Here.** Hide the original's roof cap: `.k-loader__cap{display:none}`.

## TitleCard

The first and last frame of the video: a bot's colour field with its eyes cropped large, beside the deep twin of that colour carrying the title.

**Use it** for the video's title and end cards, and on the stage screen while setting up. Choose the colour of the bot that does the most visible job.

**Markup.** `section.k-titlecard[data-color="blue"]` with `.k-titlecard__face` (an avatar) and `.k-titlecard__words` holding `.k-tc-meta`, `.k-tc-title` (two beats on two lines), `.k-tc-sub`, and for the end card a `.k-tc-cta` row with `.k-tc-qr` and `.k-tc-url`. Size the root by its container (`width: 100%; height: 100vh`).

**End card** swaps the title for the repo URL and the team.

## Chip

Small labels: status chips and marks that pair colour with a glyph, mono tool tags, honesty labels, and the LIVE marker.

**Status.** `.k-chip--ok` ✓ closed or cleared, `.k-chip--ask` ? needs a person, `.k-chip--bad` ↑ escalated or = confirmed match, `.k-chip--info` a source. Verdict chips use the brief's exact words: ✓ CLOSE, ? RFI, ↑ ESCALATE; ✓ DIFFERENT_ENTITY, ? REVIEW, = SAME_ENTITY. Always include the glyph or a word. `.k-mk--*` is the 18px round form for tables.

**Tools.** `.k-tool` in mono caps names what is really behind each step: Grok Bot, Supabase, Tavily, or "Rules, not AI" for plain code.

**Honesty.** `.k-honest--synthetic` on every screen of made-up data, worded "Invented data · Diligent dev set" for the kit's records; `.k-honest--simulated` for anything faked. `.k-live` only on data that is really updating.

## Button

Fully round pills with a verb: one ink primary per view, quiet surfaces for everything else, and a round voice button.

**Variants.** `.k-btn--primary` (the one thing this view is for: Send the request, Take the case, Try the demo), default, `.k-btn--ghost`, `.k-btn--text`. Sizes `--sm` 32px, default 40px, `--lg` 52px. `.k-iconbtn` for icons with an `aria-label`. `.k-voice` is the round level-meter button; `.is-live` animates it.

**Rules.** Verb first, sentence case: "Send the request", "Take the case". An arrow `<span class="k-arr">→</span>` only when the button goes somewhere.

## Walkthrough

One alert or case, told in five steps that play themselves. Use it for the middle of the video, and on the landing page in place of a paragraph on how it works.

**Markup.** `.kw[data-kw]` holding `.kw-tabs > .kw-tab` (one per step, with `style="--dur: 7s"`, a number in `small`, a name in `b` and a `.kw-tab__bar > i`), a `.kw-ctl` row (`.kw-count`, `[data-kw-prev]`, `[data-kw-play]`, `[data-kw-next]`), and `.kw-stage > .kw-panel` (one per step). Each panel has one sentence in `.kw-say` and `.kw-panes` with a `.kw-src` (the source) and a `.kw-con` (what the system concludes).

**Pieces.** `.kw-files` (what it was given), `.kw-path` (records followed one to the next), a `.k-doc` with `.kw-hl` phrases, `.kw-row` with a `.kw-swap` mark that resolves, `.kw-cmp` rows (two sides and a word between; `.is-key` on the row that decides), `.kw-out` (the record it writes, field by field), `.kw-verdict` and `.kw-runs`.

**Script.** `keystone-walk.js` mounts every `[data-kw]`, or call `Keystone.walk(el)`. Give each piece `class="kw-r"` and a `--d` delay in reading order; give each resolving row a `--m` for when its mark lands.

**Rules.**
- One plain sentence per step. The console's title is the question the step answers ("The same party?"), with the record's ID in mono at the right.
- The source pane shows the record as it is written. The console shows only what was taken from it, each line with its ID.
- A phrase lights up just before the row that cites it. The verdict is always last.
- The head of the console is the bot doing the step. Its motion is the status; no spinner beside it.
- Replace the example with a case from your own output before recording, and check every code on screen belongs to its verdict.

## Queue that works itself

The alert queue, worked one case after another, for the analyst's home screen and the opening of the video.

**Markup.** `.kq-list > .kq-row.kw-r` with `--d` (when the row arrives), `--w` (when work on it starts) and `--m` (when its verdict lands). Inside: a `.kw-swap` mark, the case name in `b` with its ID and rules in `.kq-id`, a `.kq-line` holding three stacked lines (`.q` Queued, `.a` what is being checked, `.b` the result), and a `.kq-end` with the verdict chip and the reason code in `code`. End with a `.kq-tally` of the three verdicts.

**Rules.** Work the cases in order, about 1.6 s each, so only one row is busy at a time. The result line names the fact that decided it. An escalation's line says nothing was asked of the customer. Drive the real queue from the system's output file: a row resolves when its line is written.

## Not used here

PropertyCard, EPC and Map belong to the real estate version. They are still in the CSS; leave them off the screen.
