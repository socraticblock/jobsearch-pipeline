# Disclaimer

## 1. Nature of the project

jobsearch is a local, open-source tool — not a hosted service. It runs
entirely on your own machine. The maintainers have no visibility into,
control over, or responsibility for how the tool is used after download.

## 2. Third-party platforms

jobsearch interacts with one third-party service: Gmail, through Google's
official OAuth flow with the `gmail.readonly` scope. The tool respects
Google's terms of service, robots.txt on any URL it follows, and the
rate limits the Gmail API enforces.

- You are responsible for compliance with the terms of service of every
  platform you use this tool with.
- The tool never bypasses CAPTCHA, paywall, login, rate-limit, or
  bot-control on any third-party service. A future contribution that
  adds any of these will be rejected.
- Consequences of any third-party terms-of-service violation, including
  account suspension or legal action, are solely the responsibility of
  the user.

## 3. Data privacy

- All personal data (profile, decisions, log, output) is stored locally.
- The only outbound call that may carry private data is the Gmail
  read API call, made under the `gmail.readonly` scope. The OAuth
  refresh token is stored locally; it is never sent to anyone but
  Google.
- The export gate at `scripts/export_bundle.py` refuses to copy a
  `token.json` or `client_secret.json` into the public artifact. A
  planted token is detected by mutation testing.
- The maintainers are not a Data Controller or Data Processor under
  GDPR or any other privacy regulation. You are.

## 4. Verdict honesty

The deterministic gate in this project is not a recommendation. A
non-`NOT_SUITABLE` verdict means the gate found nothing
disqualifying; it is not advice to apply, and it is not a
prediction of interview or hire probability. A `NOT_SUITABLE`
verdict means the gate found a quoted piece of evidence that
the posting fails one of your rules; it is not a judgement of
your worth.

The gate produces four verdict bands, defined in
`jobsearch/rules.py`:

  - `STRONG_MATCH` — every rule satisfied, a clean fit
  - `POTENTIAL_MATCH` — every hard rule satisfied, soft signals differ
  - `NEEDS_RESEARCH` — a hard rule is uncertain; not enough data
  - `NOT_SUITABLE` — a hard rule fails; the gate rejects

A reader of a `STRONG_MATCH` or `POTENTIAL_MATCH` verdict must
still look at the posting. A reader of a `NEEDS_RESEARCH`
verdict must still fill in the missing fact. A reader of a
`NOT_SUITABLE` verdict must still check the quoted evidence
before ruling the posting out.

- The system makes no false-negative guarantee. Some postings will be
  misclassified. The goal is auditable uncertainty, not perfect recall.
- The system makes no false-positive guarantee. A `STRONG_MATCH` or
  `POTENTIAL_MATCH` posting may still be a poor fit. The gate is a
  sieve, not a recommender.
- The system never substitutes a verdict for a missing fact. An
  unset profile field produces `NEEDS_RESEARCH`, not a rejection.
  An unreadable posting produces `UNCONFIRMED`, not a pass.

## 5. Acceptable use

**Acceptable:**
- Personal job-search automation
- Evaluating job-alert emails against a documented rule set
- Generating a deterministic shortlist with quoted evidence
- Tracking your application pipeline

**Not acceptable:**
- Auto-submitting applications on the user's behalf (the tool does
  not have this capability; do not add it)
- Bypassing third-party access controls
- Scraping third-party services beyond the documented Gmail read API
- Mass-applying to postings the gate marked as `STRONG_MATCH` or
  `POTENTIAL_MATCH` without human review
- Re-publishing the project's claimed results as if they were
  measured on real users (the synthetic-evidence standard in
  `CLAIMS.md` is the binding rule)

## 6. Indemnification

By using this software, you agree to indemnify, defend, and hold
harmless the authors, contributors, and any affiliated parties from
and against any and against any and all claims, damages, losses,
liabilities, costs, and expenses (including reasonable attorneys'
fees) arising from your use of this software, your violation of these
terms, or your violation of any third-party terms of service.

## 7. Warranty disclaimer

This software is provided under the licence chosen by the maintainer
"as is", without warranty of any kind, express or implied, including
but not limited to the warranties of merchantability, fitness for a
particular purpose, and noninfringement. In no event shall the
authors or copyright holders be liable for any claim, damages, or
other liability arising from the use of this software.

## 8. Changes

This disclaimer may be updated. The current version is recorded in
`CHANGELOG.md`. Continued use of the software after a change
constitutes acceptance of the updated terms.
