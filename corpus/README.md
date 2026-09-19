# Corpus provenance and conventions

## Provenance statement

**Every document, ticket, record and image in this corpus is
synthetic.** All of it was generated for this training program using
large language models and programmatic renderers, following the rules
in `BUILD_SPEC.md` section 9.

- No OQ material of any kind was used: no documents, data, site names,
  asset tags, employee names, or incident records.
- No third-party operator's published material was used. Procedure
  text, manual text and maintenance records were generated, not lifted.
- All sites (`MRB`, `SHZ`, ...), people, equipment tags and incidents
  are invented. Any resemblance to real facilities or events is
  coincidental.
- Generation deliberately injects realistic messiness (typos, run-ons,
  missing fields, mixed-language phrasing) so the labs teach against
  realistic inputs. See BUILD_SPEC.md section 9 for the full list.

## Layout

```
corpus/
  manuals/       equipment manuals (Markdown + YAML frontmatter)
  hse/           HSE procedures (Markdown + YAML frontmatter)
  maintenance/   maintenance / work-order history (structured records)
  tickets/       service-desk tickets (JSONL) — see below
  images/        rendered image set + the spec files that are its ground truth
```

Document frontmatter format and naming conventions are defined in
`docs/contracts.md` (Contract 1). That file is the authority; this one
summarises.

## Tickets (`corpus/tickets/`)

- `tickets_raw.jsonl` — one JSON object per line:
  `ticket_id, created, site, channel, subject, body`.
- `ticket_id`: `INC-` + 6 digits, unique.
  `channel`: `portal | email | phone | walk_in`.
  `created`: ISO 8601. `subject` may be `""`; `body` never is.
- Raw inputs only. Structured labels (category, urgency, routing...)
  live in `data/finetune/` and `data/eval/`, so retrieval labs can
  ingest tickets without ever seeing answers.
- Class distribution is deliberately imbalanced (access/password
  dominates, telecom/ERP rare) and the text is deliberately messy.
  Do not "clean it up" — the mess is the curriculum.

## Planted problems (deliberate — do not fix)

The corpus contains planted retrieval traps and data-quality problems
that the labs are built to surface: duplicate tags with different
revision dates, a superseding procedure with no cross-reference, an
ambiguous term across families, a scanned-image page, near-duplicate
tickets, train/validation leakage, and schema violations. If you find
one, that is the corpus working as designed.
