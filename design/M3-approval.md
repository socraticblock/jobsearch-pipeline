# M3 — Notification & Approval (design)

Goal: the owner sees a short, honest shortlist and makes one decision per job —
and that decision is bound to that job only.

## 1. Channel

**Telegram first** (already works; `hermes send` needs no LLM). Discord is a later
addition, not a prerequisite.

## 2. Message shape (per job)

```
#<job_id>  <Title> — <Company>
Location: <loc> · <remote>       Salary: <salary or "not published">
Fit: <shortlist|review>          Source: <alert name / date>
Why: <2–4 cited bullets>
Gaps: <checked-but-missing items>
Red flags: <e.g. "no salary", "agency repost", "vague scope">
Description: <complete|incomplete — reason>
Link: <original URL>
Status: new | approved-to-prepare | rejected | saved | applied
```

## 3. Actions — bound to a unique job id

- `approve` — **approve to investigate / prepare** (NOT authorisation to submit)
- `reject`
- `research` — queue a deeper look (company, people, salary)
- `save` — park for later

Capture mechanism: the Hermes `clarify` tool (native pickable options in the
user's UI), plus a plain-text fallback protocol `job <id> <action>` for scripted
or mobile use. Both resolve to the same DB write. **An approval is a row keyed by
(`job_id`, `action`) — never inferred from free text.**

## 4. Persistence & delivery rules

- `decisions` table: `UNIQUE(job_id, action)` → a decision is recorded once.
- A job already decided is **never re-notified**.
- Digest batching: one daily shortlist message (top N by fit), with per-job
  detail on request — avoids notification fatigue.
- Cron writes the digest to `digests/`; a **separate agent step** delivers it
  (same discipline as `twitter-jobs`, so cron itself never sends).

## 5. What approval does NOT do

Approving job #42 authorises preparation for #42 only. Submission (M5) needs a
separate, explicit gate with recipient validation, idempotency and read-back
verification. No approval is ever generalised to "and similar jobs".

## 6. Acceptance tests

- A decision mutates exactly one row.
- Re-running the digest never re-notifies a decided job.
- An approval for job A cannot be replayed against job B (id mismatch rejected).
- With no decisions, the digest contains only `new` jobs.

## 7. Owner involvement

Approve the channel, the message format, the action vocabulary, and the daily
cadence before M3 is switched on.
