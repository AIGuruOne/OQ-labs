# Corpus provenance and conventions

## Provenance statement

**Every document, ticket, record and image in this corpus is
synthetic.** All of it was generated for this training program,
following the rules in `BUILD_SPEC.md` section 9.

- No OQ material of any kind was used: no documents, data, site names,
  asset tags, employee names, or incident records.
- No third-party operator's published material was used. Procedure
  text, manual text and maintenance records were generated, not lifted.
- All sites (`MRB`, `SHZ`, ...), people, equipment tags and incidents
  are invented. Any resemblance to real facilities or events is
  coincidental.
- Generation deliberately injects realistic messiness (typos, run-ons,
  missing fields, non-native phrasing) so the labs teach against
  realistic inputs. See BUILD_SPEC.md section 9 for the full list.

### How the tickets were generated

`corpus/tickets/tickets_raw.jsonl` is the output of

```
python scripts/generate_tickets.py --count 600 --seed 42
```

- **No LLM, no API call, no network, no GPU.** The generator is plain
  Python (standard library only). It combines hand-written scenario
  templates (`scripts/ticket_scenarios.py`) with writer personas and
  phrase banks (`scripts/ticket_phrases.py`) under a seeded random
  number generator, then applies typos, lowercasing, dropped
  punctuation and run-on sentences. Every template sentence was
  written for this repo; none was copied from a real ticket, a real
  service desk, OQ, or any third party.
- **Deterministic.** Same `--seed` and `--count` give byte-identical
  files on any OS and any Python 3.11+ (verified on 3.11, 3.12, 3.13,
  3.14). For seed 42, count 600:

  | File | SHA-256 |
  |---|---|
  | `corpus/tickets/tickets_raw.jsonl` | `bbc72f5bbcf8478177081d9dbcfa7b309f1f74df6c66f1404ce58edb8af66143` |
  | `data/finetune/ticket_labels.jsonl` | `82e02badaba65a03f3bafe0108b83940bfc227a7ebab928d962fcad25dfcd706` |

  `tests/test_generate_tickets.py` fails if the committed files and the
  generator ever disagree. Every downstream artifact (dataset, adapter,
  eval tables) is built from these files - if you change a phrase
  bank, regenerate and rebuild everything downstream.
- **Invented names.** Enterprise systems (`Tavrona ERP`, `StaffGate`,
  `DocHarbor`, `AssetHive`, `ProcessLens`, `GateKey VPN`, `KeyNest`,
  `ClaimPoint`, `MyPortal`, `VoxLine`, `PrintFlow`, `SupplierLink`)
  do not exist. Commodity desktop products (Windows, Outlook, Excel,
  Teams, Chrome, AutoCAD, Power BI, Acrobat) are named because every
  service desk sees them and they identify no company. People are
  **first names only**, so no ticket can match a real employee.
- **Checked.** `python scripts/check_tickets.py ...` greps the output
  against a denylist of real OQ group companies, facilities, Omani
  place names, the products OQ is publicly known to run, other
  operators, and any `Al <Name>` / `bin <Name>` family-name pattern.
  It must report clean before a regenerated corpus is committed.

## Layout

```
corpus/
  manuals/       equipment manuals (Markdown + YAML frontmatter)
  hse/           HSE procedures (Markdown + YAML frontmatter)
  maintenance/   maintenance / work-order history (structured records)
  tickets/       service-desk tickets (JSONL) - see below
  images/        rendered image set + the spec files that are its ground truth
```

Document frontmatter format and naming conventions are defined in
`docs/contracts.md` (Contract 1). That file is the authority; this one
summarises.

## Tickets (`corpus/tickets/`)

- `tickets_raw.jsonl` - one JSON object per line:
  `ticket_id, created, site, channel, subject, body`.
- `ticket_id`: `INC-` + 6 digits, unique, rising with `created`.
  `channel`: `portal | email | phone | walk_in`.
  `created`: ISO 8601, 2026-03-01 to 2026-08-31, Sunday-Thursday work
  week. `subject` may be `""`; `body` never is.
- `site`: one of seven invented codes - `MRB SHZ KTF WQR ZFL HBT TMQ`
  (`MRB` is the head office and raises the most tickets).
- IT asset tags are a three-letter prefix + 5 digits:
  `LAP` laptop, `DSK` desktop, `MON` monitor, `PRN` printer,
  `PHN` desk phone, `MOB` mobile.
- **Raw inputs only.** The ground-truth records live in
  `data/finetune/ticket_labels.jsonl`, never under `corpus/`, so
  retrieval labs can ingest tickets without ever seeing answers.
- Class distribution is deliberately imbalanced (access/password
  dominates, telecom/ERP rare) and the text is deliberately messy.
  Do not "clean it up" - the mess is the curriculum.

### Ground truth (`data/finetune/ticket_labels.jsonl`)

One line per ticket, same order as `tickets_raw.jsonl`:

```json
{"ticket_id": "INC-004412",
 "record": {"category": "...", "affected_system": null, "asset_tag": null,
            "urgency": "...", "impact": "...", "requested_action": "...",
            "routing_queue": "..."},
 "meta": {"scenario": "access.password_reset", "persona": "terse",
          "features": ["system_unnamed", "very_short"], "word_count": 6}}
```

`record` is exactly the BUILD_SPEC.md section 8B schema
(`data/finetune/ticket_schema.json`). `meta` is generator bookkeeping
for error analysis ("the tuned model fails mostly on `two_problems`
tickets") - it is never a training target.

### Labelling rules

The labels are derivable from the ticket text by these rules. They are
the starting point for `data/eval/rubric.md`.

| Field | Rule |
|---|---|
| `category` | The nature of the problem, not the user's diagnosis. A user who blames "a virus" for an expired password still has an `access` ticket. Login/password/MFA/permission = `access`; ERP transactions, roles and workflow = `erp`; facilities, phishing reports, ticket chasers = `other`. |
| `affected_system` | The canonical name of the application or service **if the user names it** (any spelling: `tavrona`, `Staff Gate`, `outlok`), else `null`. "The system", "the HR portal" = `null`. Physical devices are not systems - they go in `asset_tag`. |
| `asset_tag` | The IT asset tag of the first problem's device, normalised to `LAP-04412` form (users write `lap 04412`, `LAP04412`), else `null`. Plant equipment tags (`P-1201A`), work orders (`WO-118305`) and old ticket ids are context, never the asset. |
| `urgency` | Follows the **stated business effect, never the tone**. `critical`: work blocked across a site or the enterprise. `high`: a user or team cannot work at all; or a stated same-day deadline; or degraded service across a site/enterprise. `medium`: degraded but workable; a request with a needed-by date. `low`: a request with no time pressure; anything the user says can wait. `URGENT!!!` with no reason changes nothing. |
| `impact` | Who is affected according to the text. No statement = `single_user`. |
| `requested_action` | One short imperative clause, canonical per problem type. Names the system only when `affected_system` is not null. |
| `routing_queue` | One of `identity_access, end_user_computing, network_ops, erp_support, apps_support, telecom_voice, security_ops, service_desk_l1`. Mostly, but not purely, a function of `category`. |
| Two problems in one ticket | The record describes the **first** problem raised. The second would be split into its own ticket by the desk. Its system and asset are distractors. |

### Messiness, by design

Each is forced at generation time and flagged in `meta.features`:
run-ons and missing punctuation, typos, inconsistent capitalisation,
absent information (`system_unnamed`, no asset tag), two unrelated
problems (`two_problems`), non-native phrasing (`non_native`), pasted
error strings and stack fragments (`error_string`, `multiline_paste`),
screenshots that are not attached (`screenshot_ref`), wrong guesses at
the cause, desk-agent phone notes (`agent_note`), forwarded email
trails (`forwarded`), shouting with no reason (`tone_urgent`), plant
tags and work orders as distractors (`plant_tag_distractor`), and
length from 2 words to a 200+ word wall of text.

The non-native phrasing uses ordinary features of Gulf and South Asian
business English ("kindly", "the same", "do the needful", present
continuous). It is written to be respectful and realistic. Names are
paired with writing styles at random - no name implies any style.

## Planted problems (deliberate - do not fix)

The corpus contains planted retrieval traps and data-quality problems
that the labs are built to surface: duplicate tags with different
revision dates, a superseding procedure with no cross-reference, an
ambiguous term across families, a scanned-image page, near-duplicate
tickets, train/validation leakage, and schema violations. If you find
one, that is the corpus working as designed.

Note: the near-duplicates, leakage and schema violations are planted
by the Day 2 dataset builder (`scripts/build_dataset.py`) into
`data/finetune/{train,val}.jsonl`. `ticket_labels.jsonl` itself is
clean: all 600 records validate, and so do the 20 rows of
`data/eval/heldout_20.jsonl`.

What was planted, and exactly where, is recorded in
`data/finetune/planted_problems.json`. **That file is the facilitator
answer key - it is for us, not for participants.** Details, and how the
held-out 20 are chosen, are in `data/README.md`.

One consequence for `corpus/tickets/`: the 20 planted near-duplicates
carry ticket ids that do **not** exist in `tickets_raw.jsonl` (a
resubmitted ticket gets a new id - each one is the first free number
after its source, e.g. `INC-004107` after `INC-004106`). They exist
only in `train.jsonl`. The corpus file itself is never modified by the
dataset builder.
