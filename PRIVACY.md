# Privacy in the UK and the EU

This note explains how Keystone's Track 1 triage system would handle personal data at a real UK or EU firm.

The hackathon cases are synthetic. Every person and company in them is invented, so the system processes no real personal data here. The design below is for a firm's data protection officer and lawyers to confirm. It is not legal advice.

## 1. The system runs inside each firm

The decision engine in `system/` is plain Python. It calls no model and uses no network. That is the strongest privacy property we have. `system/run` can run on each institution's own machines, in its own UK or EU region. Customer data never has to leave the firm. At most the output file's hash and the verdict counts leave.

Each institution is a separate controller of its data. We act as its processor, under the contract that Article 28 requires in both regimes. Four firms means four sealed tenants. We never pool cases across firms, and we never tune rules on a firm's live cases. Either step would make us a controller. It would also break the rule that AML data serves AML alone. In the UK that rule is regulation 41 of the Money Laundering Regulations 2017.

## 2. Whose data is involved

The customer is only one of the people in a case. Payers and payees appear in the transactions. Evidence documents name directors and relatives. The internal list records unproven allegations about people who may never have been charged.

In both regimes we treat escalations and internal list entries as criminal offence data. That is the safe reading. Transaction descriptions can also reveal health or religion. That is special category data. It brings in stricter rules under Article 9 and under the UK's new Article 22A.

## 3. UK and EU rules, side by side

| Duty | UK | EU | How the system meets it |
|---|---|---|---|
| Lawful basis | Legal obligation under the MLRs 2017. Regulation 41 limits the data to anti-money-laundering use and requires a privacy notice at onboarding. | Legal obligation under national laws based on the AML directives. The AML Regulation replaces them from 10 July 2027. | The system reads only the folder it is given. It uses the data for triage and nothing else. |
| Criminal offence data | Article 10 UK GDPR plus a DPA 2018 Schedule 1 condition, such as preventing unlawful acts. The firm also keeps a written policy on how it handles this data. | Article 10 GDPR needs EU or national law to authorise the processing. The AML Regulation does so, with safeguards. | Only the MLRO (the firm's money laundering reporting officer) can read ESCALATE rows and internal list matches. |
| Automated decisions | Articles 22A to 22D apply. The Data (Use and Access) Act 2025 added them, and they have been in force since 5 February 2026. Fully automated significant decisions are allowed unless they rest on special category data. The person must be told, and can make their case, ask for a human and contest the result. | Article 22 GDPR still bans them unless a narrow exception applies. For AML that exception is authorisation by law. The EU court's SCHUFA ruling says a score a human relies on heavily can count as the decision itself. The AML Regulation adds meaningful human intervention for decisions about the customer relationship and its transactions. | A named analyst confirms every RFI and ESCALATE. A CLOSE that releases a held payment also needs a human, because releasing it carries out a transaction. The firm tracks how often analysts override the system, to show the review is real. |
| Explanation | The person can ask how a significant automated decision was made. | The Dun & Bradstreet Austria ruling (2025) requires an explanation of the logic actually applied, in plain terms. The AML Regulation adds a right to an explanation and to challenge, except for suspicious activity reports. | Every verdict carries a reason code and cites the documents it rests on. The rules are readable code, and together they are the explanation. |
| Tipping off | Section 333A of the Proceeds of Crime Act 2002 makes it an offence to reveal a suspicious activity report or an investigation. The DPA 2018 crime exemption lets the firm leave escalation data out of a subject access request. | National law limits GDPR rights under Article 23. The AML Regulation keeps the ban on tipping off. | RFI wording asks for one document and never hints at suspicion. Escalations carry a "disclosure restricted" flag, so the team answering access requests cannot reveal them by mistake. |
| Retention | Regulation 40 of the MLRs says to keep records for five years after the relationship ends, then delete them. | Five years under the AML directives and the AML Regulation. | Stored decisions carry a purge date tied to the firm's relationship end date. Run hashes hold no personal data and can stay. |
| Impact assessment (DPIA) | Required. Large-scale criminal offence data triggers it, and so do decisions about access to a service. | Required under Article 35 for the same reasons. The firm consults its lead data protection authority if high risk remains. | We write one per firm before launch. The five-run check and the mutation tests count as evidence for it. |
| Transfers | UK rules already allow transfers to the EU and EEA. | The EU renewed its UK adequacy decision on 19 December 2025, valid until 27 December 2031. An EU firm can therefore use a UK processor. | Any hosted store sits in a London or Frankfurt region under the vendor's data processing agreement. Support access from the US needs the EU-US Data Privacy Framework and its UK extension, or standard contracts with a risk assessment. |
| Outsourcing | The FCA's outsourcing rules (SYSC 8) and operational resilience rules cover the firm's use of us. | DORA governs contracts with IT providers and requires a register of them. | Every contract includes audit rights and an exit plan. |
| Security | Article 32. Breaches go to the ICO within 72 hours. | The same rule, reported to the lead authority. | Everything is encrypted, and access is limited by firm and role. Every view of a case is logged. |
| Fairness | The accuracy principle in Article 5 applies. The Equality Act 2010 counts nationality as race. Consumer Duty forbids foreseeable harm such as needless account freezes. | The AML Regulation bans biased outcomes from automated processes. | The high-risk-country rule (TM06) can stand in for nationality. The firm reports outcome rates by country and customer type every month. |
| AI Act | No UK equivalent. The ICO's guidance on AI applies. | Fixed rules written by people likely fall outside the Act's definition of an AI system. AML monitoring is not on the high-risk list, and the credit-scoring entry excludes fraud detection. | If a model is added, the AI literacy duties apply and the classification is checked again. |

## 4. What changes before real data

1. **Database access.** The demo schema in [`supabase/schema.sql`](supabase/schema.sql) lets any holder of the public key read every stored decision. That is acceptable only for synthetic data. With real data, reads are limited to the user's firm and role, and the public key gets no access. Otherwise customer names would sit beside ESCALATE verdicts. That would be both a breach and a tipping-off risk.
2. **A named analyst on every action.** The demo `analyst_actions` log records what was done but not who did it. Anyone with the public key can also add to it. With real data, only signed-in staff can add an action, and each one carries that analyst's identity. That record is the proof of human review. The log already never rewrites history, which suits an audit trail. Its rows still follow the retention purge.
3. **Reasons stay inside the firm.** Each `reason` names people and dates of birth, as the brief asks, and analysts need that detail. Anything that leaves the firm carries only case IDs and reason codes.
4. **Retention and restriction.** Stored decisions gain the purge date and the "disclosure restricted" flag from the table above.
5. **This repository.** `output/*.jsonl` holds names because the brief asks for specific reasons. That is fine here only because every name is invented. Real output never goes in a repository, and a pre-commit check would block it.
6. **Public-source search.** The Tavily context tool in [`tools/mlro_context.py`](tools/mlro_context.py) sends a country name and a fixed phrase. It never sends a customer, a case or an amount. A list of allowed country names will enforce that. A search on a person's name belongs after escalation, at the MLRO's request. It should go through a vendor that has a data processing agreement and keeps no search logs.
7. **Model calls.** The scored system calls no model. If one is added through OpenRouter, names are swapped for tokens first. Requests go only to UK or EU providers that keep no data.
8. **What runs today.** The UI names Document, Payments, Web and Screening bots. Today fixed rules decide every verdict. Any model or search bot is future work and follows the rules in this note.

## Sources

- [Data (Use and Access) Act 2025 commencement plans (GOV.UK)](https://www.gov.uk/guidance/data-use-and-access-act-2025-plans-for-commencement)
- [Data (Use and Access) Act 2025 data protection changes (GOV.UK)](https://www.gov.uk/guidance/data-use-and-access-act-2025-data-protection-and-privacy-changes)
- [Commission renews UK adequacy until 27 December 2031 (Freeths)](https://www.freeths.co.uk/insights-events/legal-articles/2026/european-commission-renews-uk-adequacy-decisions-until-27-december-2031/)
- [EU renews UK adequacy decisions (Hunton)](https://hunton.com/privacy-and-information-security-law/european-commission-renews-uk-data-adequacy-decisions)
- [AML Regulation Article 76 text (SpringLex)](https://www.springlex.eu/en/packages/aml/amlr-regulation/article-76/)
- [AI in AML and human intervention under the AML Regulation (HLC)](https://www.hlc.com/en/publications/ai-in-aml-compliance-navigating-human-intervention-under-the-aml-regulation)
- [AI Act Annex III (EU AI Act Service Desk)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)
- [High-risk AI in financial services (William Fry)](https://www.williamfry.com/knowledge/high-risk-ai-in-financial-services/)
