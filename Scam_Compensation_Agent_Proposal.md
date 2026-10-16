# Project Idea: Scam Compensation Assessment Assistant

## What we want to build

An AI agent that uses a scam victim’s information, supporting evidence, regulations and bank policies to prepare a reimbursement assessment for bank staff. Internal auditors can use the same assessment to check whether the bank handled claims correctly and consistently.

**Main question:** Can the agent reduce the time needed to review scam compensation cases while maintaining accuracy, consistency and traceability?

## What information does it need?

- Amount and currency lost, and any money already recovered or reimbursed.
- Country, transaction date, reporting date and payment method.
- How the scam happened, including whether the customer authorised the payment or the scammer made the transaction using stolen credentials.
- Supporting evidence, such as scam messages, transaction records, authentication logs and bank alerts.
- Applicable regulations and approved bank policies, including their effective dates.

The amount lost and the victim’s description are starting points. They are not enough on their own to determine eligibility or compensation.

## What would the agent do?

1. **Organise the case:** Extract facts, build a timeline and flag missing or conflicting evidence.
2. **Classify the scam:** Distinguish scenarios such as a fake bank officer persuading a customer to transfer money versus phishing that allows a scammer to access the account.
3. **Find relevant rules:** Retrieve the regulation and bank policy versions applicable to the jurisdiction, transaction date and payment type.
4. **Check eligibility:** Assess scope, conditions, exclusions and relevant bank duties, with citations to the rules and supporting evidence.
5. **Prepare a calculation:** Apply verified rules for eligible losses, recoveries, limits and deductions. Separate regulatory reimbursement from discretionary goodwill payments.
6. **Generate a review report:** Explain the preliminary recommendation, proposed amount where supported, missing evidence and issues requiring human judgement.

**An authorised bank officer makes the final decision.** The agent should return “insufficient evidence” when a conclusion cannot be supported.

## Example case for our demo

> A customer receives a call from someone pretending to be the bank’s fraud officer. The caller says the account is compromised and persuades the customer to transfer 10,000 units of local currency to a “safe account.” The customer authorises the domestic transfer and reports the scam the next day.

We can test this as separate domestic scenarios in Singapore, the UK and Australia, using a fixed transaction date and research cutoff. The agent should identify which rules apply and what further evidence is needed, rather than assume every country offers the same reimbursement protection.

For an initial prototype, we should implement **one jurisdiction first**, then expand. We can add a second scenario involving stolen credentials to test whether the agent correctly distinguishes authorised scam payments from unauthorised transactions.

## How does this help internal auditors?

Auditors independently review the compensation process; claims staff operate it. The agent can help auditors identify:

- Decisions that lack evidence or use the wrong policy version.
- Incorrect reimbursement calculations or missed deadlines.
- Inconsistent treatment of materially similar cases.
- Repeated weaknesses in fraud controls and incident response.

Each report should retain the case evidence references, policy version, calculation and human reviewer’s decision.

## How would we measure efficiency?

Create a small set of synthetic cases with independently verified reference answers. Have a person and the agent-assisted reviewer assess the same cases under the same rules and report template.

| Measure | What we compare |
| --- | --- |
| Review time | Manual time versus agent-assisted time, including verification and corrections |
| Assessment accuracy | Correct applicability and eligibility conclusions, including when evidence is insufficient |
| Calculation accuracy | Correct proposed amounts under the verified rules |
| Evidence quality | Whether material claims cite the correct rule and supporting case evidence |
| Consistency | Whether equivalent facts receive equivalent treatment |
| Cost per reviewed case | Staff effort plus API costs |

**Time saved per case = manual review time − total agent-assisted review time.**

Role C can estimate the value of staff capacity freed using a cited hourly labour cost, then deduct operating costs. We should not claim the tool prevents scam losses without evidence.

## Suggested division of work

- **A — Build:** Case input interface, agent workflow, policy retrieval and review report.
- **B — Sources and evaluation:** Authoritative sources, synthetic cases, verified reference answers and accuracy evaluation.
- **C — Business case:** Timed manual baseline, efficiency comparison, cost–benefit calculation and Chapters 1–2.
- **D — Governance and presentation:** Human approval, privacy controls, audit trail, prompt-injection safeguards, final report and pitch.

## Scope and implementation

Use synthetic victim information and a small, approved set of policy documents for the prototype. AI can extract facts and explain findings; explicit, tested rules should perform monetary calculations. Treat uploaded messages and documents as evidence, never as instructions to the agent.

This extends the original regulatory research brief into case assessment. To stay aligned, position it as an **audit support use case powered by regulatory research**, and confirm the extension with the project mentor before making it the main deliverable.

## Starting sources

- [MAS: Combatting Scams and the Shared Responsibility Framework](https://www.mas.gov.sg/regulation/combatting-scams)
- [UK PSR: APP Fraud Reimbursement Protections](https://www.psr.org.uk/information-for-consumers/app-fraud-reimbursement-protections/)
- [Australia: Scams Prevention Framework Rules 2026](https://www.legislation.gov.au/F2026L01140/asmade/downloads)

These are starting points for research. Applicable provisions, commencement dates and bank policies must be verified for each test case.
