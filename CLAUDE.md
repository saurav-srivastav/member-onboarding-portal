# CLAUDE.md

Project-specific instructions for the exchange member onboarding portal. General
engineering principles live in `~/.claude/CLAUDE.md` and are not repeated here.

Read `README.md` before changing the flow.

## Operations is the single channel — do not route around it

The KYC vendor interfaces only with Operations; Compliance reaches the member
only through Operations. In code this is the `TO_ROUTE → OPEN` transition in
`models.route_to_member`: a vendor or compliance clarification is invisible to
the member until Ops routes it. Never surface a `TO_ROUTE` item on a member
screen, and never let Compliance or the vendor create an `OPEN` clarification
directly. `test_app.py` asserts this; if that check fails, the fix is the code,
not the test.

## The metric is derived from stage_history, never stored

Time to onboard, time in stage, first-time-right and round-trips are all
computed in `models.metrics` and `models.timeline` from the timestamps in
`stage_history`. Do not add a cached `duration` or `onboarded_days` column — a
stored copy drifts, and the whole point of the portal is that the numbers fall
out of normal use.

Every stage change must go through `models.set_stage`, which writes the history
row. A bare `UPDATE applications SET stage=…` silently breaks the metrics.

## The application form is filled in the portal, not uploaded

`FORM_SECTIONS` in `documents.py` defines the in-portal form; `DOCUMENTS`
defines the 9 file uploads. Do not add the application form back as a tenth
checklist item — catching bad answers at entry, rather than inside a returned
PDF, is the change this build exists to demonstrate.

## The per-document loop must stay per-document

A return moves one document to `RETURNED` and the application back to
`DOCUMENTS`; everything else keeps its status. When the member re-uploads,
`maybe_return_to_ops` sends it back to Ops without a fresh submission. Never
reset the whole pack on a single return — that is the email behaviour the
portal replaces.

## Demo data is seeded, and reseeding is destructive

`seed.py` deletes `portal.db` and rebuilds it. Dates are relative to today so
the demo always reads the same way. `portal.db` and `uploads/` are git-ignored;
never commit either.

Verify any change with:

```bash
./.venv/bin/python test_app.py
```
