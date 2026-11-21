# How this system decides

This system reads a transaction-monitoring case and gives one verdict. It closes the case, asks the customer one question, or escalates to the MLRO.

It is plain Python with fixed rules. It calls no language model and uses no network. The same input produces the same output file every time, byte for byte.

## The method in one minute

A careful analyst asks three questions in a fixed order. The system asks the same three.

| Order | Question | Verdict if yes |
|---|---|---|
| 1 | Does anything on file point to crime? | ESCALATE |
| 2 | Does a document on file explain every alert in the case? | CLOSE |
| 3 | Nothing is suspicious, but something has no document behind it. | RFI, naming the one document to ask for |

The order is deliberate. Suspicion is checked first because the SOP forbids questioning a customer once there is suspicion. Closing has the strictest test because a wrongful close is the most costly mistake.

## What "explains" means

A document does not explain a payment by being on file. It explains a payment only when its own facts match that payment.

| Fact | Test |
|---|---|
| Amount | The document states the payment amount to the penny |
| Party | The document names the payer or payee on the transaction |
| Account | Where the document gives an account, it is the account on the transaction |
| Date | A letter or invoice is dated on or before the payment it explains |

Here is an example with invented names. Sam Field is a nurse who declared an income of £2,800 a month. In March the account receives £41,500 from "Hale & Co Solicitors client account" with the reference "ESTATE OF R FIELD". Total receipts for the month are £44,300, and the rule for activity above the declared profile raises an alert.

| What is on file | Verdict | Why |
|---|---|---|
| A letter from Hale & Co, dated before the payment, confirming a distribution of £41,500.00 from that estate | CLOSE, `DOCUMENTED_EVENT` | The payer and the amount match, and the letter predates the payment |
| No letter | RFI, `RFI_SOURCE_OF_FUNDS` | Nothing looks criminal and the solicitor's letter would settle it |
| A letter confirming £35,000.00 | RFI, `RFI_SOURCE_OF_FUNDS` | The letter does not account for a payment of £41,500 |
| A fraud report from another bank about a payment into this account | ESCALATE | A sign of crime outranks any explanation |

After a document explains a payment, the system re-tests the alert without that money. Receipts of £44,300 less the £41,500 inheritance leave £2,800. That is inside the limit of three times declared income, so the alert has nothing left to explain.

## Each monitoring rule has its own test

A case closes only when every alert in it passes.

| Rule | The alert is explained when |
|---|---|
| TM01 activity above profile | The money left after removing documented receipts is within the rule's limit |
| TM02 rapid movement | The money in with no document is under £2,000, or less than 80% of it moved on |
| TM03 just under a threshold | Every alerted transaction matches a line in the customer's takings records or contract schedule |
| TM04 many payers or payees | The counterparties with no document number no more than the rule's limit |
| TM05 large cash | The cash matches a documented sale or an earlier withdrawal of the same amount |
| TM06 higher-risk country | Every alerted payment is documented. An invoice from the payee alone is not enough |
| TM07 dormant account | Every alerted movement of money is documented |
| TM08 third party | Every third-party payment is documented, for example by a gift letter or a group structure chart |
| TM10 early redemption | A dated document gives the reason and nothing was paid to anyone else |
| TM22 internal list | Identity facts on file show the counterparty is a different party |

## When in doubt, it does not close

A wrong decision costs more than no decision. In the brief's scoring a wrongful close costs 10 and an unnecessary question costs 3. So passing the tests above is not enough. Three further checks run before any close.

The first check looks for leftovers. It searches the alerted transactions for a payment of £1,000 or more that no document covers and whose other party has never appeared on the account before. One such payment turns the close into an RFI. For a personal customer the same applies to money from an own-name account that has never appeared before.

The second check applies at the payments firm. A held payment of £10,000 or more to anyone but the client is not released without a matching invoice or contract on file. The system reads that threshold from `POLICY.md`.

The third check asks whose document it is. A letter that opens "Dear" followed by another person's name is set aside. So is a sale receipt that puts the customer on the buying side. The same holds for an invoice or credit note made out to another party. A generic opening such as "Dear Tenant" proves nothing either way, so it is not held against the document.

Two rules for own accounts follow from the same idea. A personal customer who moves money between two of their own accounts needs a statement for each one. And when own money arrives in a dormant account, a statement is not enough. The statement shows whose account the money came from. Only a re-verification record shows that the person now using the dormant account is the customer.

## Signs of crime

Each escalation rests on evidence in the file. The system never escalates on a hunch or on the size of a payment.

| Evidence on file | Reason code |
|---|---|
| A sending bank's fraud report about a payment into the account | `ESC_MULE_ACTIVITY` |
| One device used to log in to several customers' accounts | `ESC_ACCOUNT_MISUSE` |
| A staff note that the customer asked how to stay under a limit, with transactions just under it | `ESC_STRUCTURING` |
| The company register shows the payer was dissolved before it paid | `ESC_UNEXPLAINED_FUNDS` |
| Undocumented cash that was sent on to someone else within days | `ESC_UNEXPLAINED_FUNDS` |
| Money from new payers leaves to companies the customer's own director controls | `ESC_PASS_THROUGH` |
| Invoices for goods unrelated to the declared business, from an undeclared country | `ESC_INVOICE_MISMATCH` |
| A payment to or from a higher-risk country with no document behind it | `ESC_HIGH_RISK_CORRIDOR` |
| A third party funds payouts to many people who share a few addresses | `ESC_THIRD_PARTY_FUNDING` |
| An investment account pays out to someone other than the customer | `ESC_THIRD_PARTY_FUNDING` |
| Fund units sold within days, with the proceeds paid to someone else | `ESC_EARLY_REDEMPTION` |
| The listed party is the counterparty, or still controlled it on the payment date | `ESC_LISTED_PARTY` |

## Two policy settings that decide many cases

**Own accounts.** A transfer from an account in the customer's own name counts as the customer's money only when a statement on file shows the customer holds that account. The statement must show the same account number and the same amount. If such transfers take receipts to 5 times the declared figure or more, the system sends an RFI for an updated profile. Below 5 times it closes. The system reads the number 5 from `POLICY.md`.

**The internal list.** A match on a name or an address proves nothing. The system compares every identity fact on file with the list entry. For a person that means the date of birth. For a company it means the registered address and the dates each person held office or control.

| What the file shows | Verdict |
|---|---|
| Same name and same date of birth, or the listed person still controlled the company when it was paid | ESCALATE, `ESC_LISTED_PARTY` |
| Same name but a different date of birth, or the listed person is not among the company's officers | CLOSE, `LIST_MATCH_DIFFERENT_PARTY` |
| No identity fact to compare | RFI, `RFI_COUNTERPARTY_DETAILS` |

One trap deserves a mention. A listed director can resign the day before a payment while still owning the company. The system checks the register of people with significant control as well as the officer list. It escalates when control had not yet passed.

## How the reason is written

Every check records the facts it used. These are the document ID, the transaction ID, the amount, the names and the dates. The reason is assembled from those recorded facts. Where a staff note or a chat matters, the reason quotes the sentence instead of restating it, because a paraphrase can claim more than the note says. The `evidence` list holds the deciding documents first, then any list entry, then the one or two transactions the reason names. For an RFI, the last sentence states the exact document to request.

## Why there is no language model

The documents vary in wording, so reading them is the hard part. We handled that without a model. The system extracts typed facts instead of matching phrases. It reads every pound amount, date, account reference, labelled field and table row. A date of birth is recognised by being a date at least 16 years older than the letter, however the writer phrased it.

This choice makes the five scored runs identical, and a run costs nothing. Every decision can also be traced to a line of code and a fact in the file.

## How we tested it without answers

The development cases carry no labels, so we cannot report an accuracy figure. We tested the reasoning instead.

**Mutation tests.** A system can reach the right verdict for the wrong reason. It might close whenever a document of the right type is present. `tools/mutation_test.py` guards against that. It takes real cases, changes one fact in memory and checks that the verdict moves as the SOP requires. A letter stating a different amount no longer closes a case. A statement in another person's name no longer proves an own account. A gift letter whose date of birth matches the list entry escalates, and the same letter with a different date of birth closes. A fully documented case with one extra £5,000 payment from a stranger no longer closes. A sale receipt with the seller and buyer swapped no longer closes. A dormant account with a statement but no re-verification no longer closes. All 33 tests pass.

**Repeat runs.** `tools/verify.py` runs each institution five times under five different hash seeds from inside `system/`. The five output files are identical.

**Linux run.** The grader calls `system/run` directly on Linux. We cloned the repository fresh inside Ubuntu and ran it that way with Python 3.14. All four output files matched the ones produced on Windows with Python 3.12, byte for byte.

**Output checks.** The same script confirms one line per case, a reason code that belongs to its verdict, and cited IDs that exist in that case's own files. It also confirms that no customer name or ID from the development cases appears in the code.

On the 4,000 development cases the system closes 2,000, sends 1,000 RFIs and escalates 1,000.

## What we are less sure of

Some cases fit two reason codes. Cash paid back in after an earlier withdrawal could be `WITHIN_PROFILE` or `OWN_ACCOUNT`. A transfer from a joint account could be `OWN_ACCOUNT` or `THIRD_PARTY_DOCUMENTED`. We chose the code whose description fits most literally, and the reason text states the facts either way.

Staff notes and chats are free text. The system reads them for supporting detail and for a small set of signals, such as a question about staying under a limit. A note worded in a way we did not anticipate could be missed. In that event the case goes to an RFI or an escalation. A case is never closed on the strength of free text alone.

A case that fits no explanation and shows no sign of crime gets an RFI. If the system cannot read a case at all, it escalates that case with a note saying so. No case is ever dropped.

## Running it

```
system/run <institution folder> <output file>
```

It needs Python 3 and the standard library only. It reads the folder it is given and writes the output file. A run of 1,000 cases takes about 4 seconds on a laptop, so 200 cases take about one second. There are no model calls, so a run costs nothing.

## Code map

| File | What it holds |
|---|---|
| `run` | The entry point |
| `triage/loader.py` | Reads the institution folder and the numbers set in `POLICY.md` |
| `triage/textfacts.py` | Extracts amounts, dates, accounts, fields and tables from documents |
| `triage/case.py` | Assembles one case with its alerts, transactions, documents and reviews |
| `triage/explain.py` | The explanations. Each matches a document's facts to transactions |
| `triage/flags.py` | The signs of crime |
| `triage/listmatch.py` | Internal-list matches |
| `triage/decide.py` | The three questions, the per-rule tests and the wording of reasons |
