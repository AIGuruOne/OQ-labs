# Architecture spec — filled example for brief 1 (ticket to structured record)

> Filled in against `facilitator/architecture_spec_template.md` on
> 2026-09-22 by the build team, in a notional 90 minutes, to test the
> template. Every number that is a measurement comes from this repo
> (`facilitator/prebaked_outputs/eval/`, `docs/timing_log.md`,
> `facilitator/cost_model.xlsx`). Everything about the company, the
> desk and the people is invented. Reviewed with the S5 checklist in
> `spec_review_brief1_filled.md` — the findings there are real gaps
> in this spec, left in on purpose so the review has something to find.

---

## 0. Cover

| | |
|---|---|
| Group | Table 3 (integration architect, service desk lead, platform engineer) |
| Use case brief | 1 — Ticket to structured record |
| Version and date | v0.1, 2026-09-27 |
| Owner after the week (name in principle) | Faisal, platform engineering (in principle; confirmed by his manager? OPEN) |

## 1. The job (8 min)

- **One sentence.**
  > When a ticket is created in the service desk tool, the system takes its subject and body and produces the seven-field triage record, so that the desk agent can confirm it in one click instead of typing it.
- **Input.**
  > Ticket subject (may be empty) and body, plain text, 2 words to about 450 tokens (p95 211 on our 600-ticket sample). Sent by the desk tool's on-create webhook. About 300 a working day.
- **Output.**
  > One JSON object with exactly the seven schema fields (`category`, `affected_system`, `asset_tag`, `urgency`, `impact`, `requested_action`, `routing_queue`) plus `valid: true/false` and `model: <name>`. Received by the desk tool, shown as a pre-filled triage form. The agent confirms or edits within the next five minutes; the ticket routes on confirm.
- **Today.**
  > An agent reads and types the seven fields by hand. Median time to first triage 40 min, three hours after a long weekend. The number to move: median time to first triage, and the share of tickets bounced back by a queue for mis-routing (today 11%, invented).
- **Not in scope.**
  > (1) The desk-tool plugin that renders the form — we deliver the endpoint and a webhook contract; the plugin is a post-week task. (2) Auto-routing without a human confirm. The record is always confirmed by an agent in the pilot.

## 2. The decision (5 min)

- **Option chosen.**
  > **D — host and fine-tune.** Matrix totals at the base weights: A 380, B 430, C 295, D 305 (`facilitator/decision_matrix_template.md`, worked example). B scored highest but is removed by a gate (next line), so the choice is between C and D, and D wins on quality evidence.
- **Gates.**
  > G1 = **NO**: ticket bodies sometimes contain pasted passwords and personal data, and the data owner (Maryam, invented) will not allow vendor processing until the cloud DPA review completes, which is after the pilot start. Removes A and B. G2 = no (moot). G3 = yes. G4 = yes, from S12: see section 6. G5 = partly — Faisal, part-time, no GPU experience.
- **What flips it.**
  > When the DPA review completes with approval for a data-zone deployment, B wins 430 to 305 and this spec's section 4 is replaced by an Azure OpenAI deployment; sections 3, 6 and 8 stay as they are. The eval in section 6 is rerun against the vendor model before switching.

## 3. Data (10 min)

- **What goes into a prompt.**
  > `subject` (needed, may be empty), `body` (needed). Nothing else: not requester name, not site, not channel, not attachments. Formatted as `Subject: <subject>\n\n<body>` exactly as in training (`dataset_utils.format_ticket_text`).
- **Classification.**
  > Prompt: *internal*, and *personal data* (first names, occasionally more). Output: *internal*, no personal data by construction (seven enum/short fields; `requested_action` is a short imperative clause). Classified by the data owner, 2026-09-27.
- **Must never enter a prompt.**
  > Requester identity fields (kept out by the webhook contract: it sends subject and body only). Pasted passwords and secrets *inside* the body: OPEN — no mechanism yet. Candidate: a regex redaction step before the call (`password[:=]\s*\S+`, `pwd`, 6+ digit codes after "OTP"), applied to the prompt and the log, measured for false positives on the 600-ticket sample.
- **Where the text is stored after the call.**
  > The audit log (section 8) stores the prompt hash, the output and the validation result, not the prompt text. The ticket text stays in the desk tool, which already holds it. Log retention 90 days on the VM's disk, readable by platform engineering only.
- **Training or index data.**
  > 600 tickets with labelled records (synthetic in the lab; the real desk's last two quarters of agent-confirmed records in production). Split 400 train / 80 validation / 20 held-out. Quality checks before any training: near-duplicates (word-set Jaccard >= 0.8), train-to-validation leakage, schema violations, category coverage, class imbalance reported not corrected (`scripts/quality_checks.py`). Refreshed monthly from agent corrections (section 6).

## 4. Model and serving (10 min)

- **Model.**
  > Llama 3.2 1B Instruct with a LoRA adapter (r=16, 3 epochs on 400 rows), `checkpoints/adapter_prebaked` in the lab. Not 3B: the 1B trains in 7 minutes on a free T4 and its tuned scores (section 6) are above the pilot bar on the fields that matter; 3B is untested tuned and its untuned urgency advantage (13/20 vs 7/20) is a rubric question, not a size question. Not smaller: nothing smaller with a chat template was tested.
- **Where it runs.**
  > One Azure VM, NV12ads A10 v5 (24 GB), Linux, UAE North, $1.30/h. Served by Ollama behind the OpenAI-compatible API. **Version is a problem:** the adapter loads on Ollama 0.12.10 and Ollama 0.34 refuses adapters. For production the adapter is merged into the base weights (PEFT `merge_and_unload`) and the merged model is served by a current Ollama or vLLM — OPEN, to be tested. Upgrades: Faisal, monthly patch window.
- **Endpoint.**
  > `get_endpoint("tuned")` from `config/endpoints.py` (`TUNED_MODEL=oq-ticket-tuned`, `OLLAMA_BASE_URL` pointing at the VM). The integration calls `.chat_json(...)`; swapping to `hosted` after the DPA review is a `.env` change.
- **Context budget.**
  > 4,096 tokens (`num_ctx`). Input cap 1,500 tokens; a longer body is truncated at the end (the first problem in a ticket is the one that is labelled, so the start matters more than the end) and the truncation is logged.
- **Output contract.**
  > `data/finetune/ticket_schema.json`, validated with `jsonschema` in the endpoint before the reply leaves. On failure the caller receives `valid: false` and an empty record; the desk tool shows the blank form. Wrapped JSON (code fence, prose) is treated as invalid. Format failures so far: the tuned model 0 of 20 and 0 of 72; the untuned 1B base 7 of 20 (2 replies not JSON at all, 5 parsed but failed the schema, none fenced).
- **Timeout, retry, fallback.**
  > 20 s timeout (measured median 0.8 s on a T4; the VM's A10 is faster), one retry, then `valid: false`. The desk works exactly as today when the endpoint is down: the form is blank. Nobody is paged for a blank form; a 30-minute failure rate above 10% pages Faisal.

## 5. Retrieval and tools (8 min)

- **Sources.** none
- **Freshness.** none
- **Per request.** none
- **Tools.** none — the endpoint reads the ticket and writes nothing. The desk tool writes the confirmed record.
- **Untrusted text.**
  > The ticket body is untrusted. It reaches the model as user content only, never as system text, and the output is a validated seven-field record, so an instruction inside a ticket ("set urgency critical") can at worst produce a wrong field, which the agent sees. Tested on Day 4 S25 with the injection ticket.

## 6. Quality (10 min)

- **Correct means.**
  > `data/eval/rubric.md`: six fields by exact match (`affected_system` normalised for case and spacing), `requested_action` by word-set Jaccard >= 0.5, plus format (raw reply parses and passes the schema) and an invented-values count. Human judgement only on urgency misses (H1) and a sample of requested actions below threshold (H2).
- **Eval set.**
  > 20 held-out tickets, stratified over all seven categories, never in train or validation, and with no near-lookalike (Jaccard >= 0.6) anywhere in either — enforced by `tests/test_build_dataset.py`. Too small for a pilot claim (one ticket is 5 points); see targets.
- **Targets.** (today = the pre-baked adapter through Ollama, `06_tuned_prebaked_*`; base = untuned 1B; hosted = gpt-4o-mini class, for reference only)

  | Measurement | Untuned 1B | Tuned 1B (today) | Hosted (reference) | Pilot target on 200 tickets |
  |---|---|---|---|---|
  | Format: schema-valid | 13/20 | 20/20 | 20/20 | 99% |
  | `routing_queue` | 7/20 | 16/20 | 17/20 | 80% |
  | `requested_action` >= 0.5 | 0/20 | 16/20 | 6/20 | 70% (floor measure) |
  | `category` | 9/20 | 15/20 | 19/20 | 80% |
  | `asset_tag` | 16/20 | 20/20 | 20/20 | 95% |
  | `urgency` | 5/20 | 7/20 | 8/20 | not targeted — agent always sets it |
  | Whole record (six exact fields) | 2/20 | 4/20 | 6/20 | reported, not targeted |
  | Invented values | 2 | 0 | 0 | 0 |

  > On the 72 cleaned validation tickets the tuned model scores urgency 55/72 and routing 62/72; the held-out 20 is deliberately hard on urgency. Urgency misses are 9 over-by-one, 1 over-by-two, 3 under-by-one: the model escalates. The rubric's open question (the system prompt never defines the urgency levels) is why urgency is an agent field in the pilot.
- **Human review.**
  > Every record is confirmed by an agent in the pilot (that is the workflow). Additionally the desk lead samples 20 confirmed tickets a week against the rubric and records per-field agreement. A miss is a row in the corrections file, which is next month's training data.
- **Retrain or rebuild trigger.**
  > Weekly sample routing accuracy below 70% for two consecutive weeks, or any change to the queue list or the schema, starts the runbook: rebuild dataset from confirmed records, quality checks, retrain, `run_eval.py` on the held-out set, `--compare` against the model in use, promote only if routing and format do not fall.

## 7. Cost and capacity (7 min)

| From the sheet (`cost_model.xlsx`, scenario A) | Value |
|---|---|
| Requests per month | 6,600 |
| Input / output tokens per request | 330 / 60 (measured) |
| Vendor API $ per month (Claude Sonnet 5, for the flip case) | $5.38 |
| Self-hosted $ per month (with ops labour) | $1,434 (compute $949, ops 8 h × $60 = $480, storage $5) |
| Break-even requests per month | 1,760,589 |
| Peak requests per hour | 112 |
| VMs needed at peak, if hosting | 1 (capacity 3,000/h at 60% utilisation; the VM is idle 99.7% of the time) |

- **Latency target.**
  > p95 under 5 s from webhook to record. Measured so far: median 0.8 s per ticket on a Colab T4, one at a time; p95 under 10 concurrent requests not yet measured — notebook 03 on Day 2.
- **Cost cap.**
  > $1,600 a month (the VM plus ops plus margin). The VM is fixed-price, so the cap is really a guard against a second VM being added without a decision; if the peak-hour queue exceeds 5 s p95 for a week the answer is a decision, not autoscaling.

## 8. Failure and control (8 min)

- **Wrong answer.**
  > The agent sees every record before it has an effect: the form is pre-filled, not submitted. Urgency in particular is always the agent's. A wrong routing that the agent confirms is a training example next month.
- **Model down.**
  > `valid: false`, blank form, the desk works as today. The business can live with it indefinitely; it is the current state.
- **Audit log.**
  > Per call: timestamp, ticket id, caller (the webhook identity), sha256 of the prompt, model name and adapter fingerprint (sha256 of the adapter weights, as notebook 06 prints), output record, validation result and reasons, input and output tokens, seconds, truncated yes/no. JSON lines on the VM, shipped to the central log store nightly. No prompt text (section 3).
- **Kill switch.**
  > Faisal or the desk lead disables the webhook in the desk tool (30 seconds, no deployment). Stopping the VM is the second switch.
- **Rollback.**
  > Every promoted adapter is kept as `checkpoints/adapter_<model>_<run>` with its eval summary. Rollback is `register_adapter.py --adapter <previous>` and a restart: under five minutes, tested on Day 2 by registering the pre-baked adapter over a group's own.

## 9. Ownership and rollout (5 min)

- **Owner.**
  > Faisal, platform engineering, in principle. His manager has not agreed and he has not run a GPU VM. OPEN.
- **Pilot.**
  > The `MRB` desk (four agents, the busiest site), six weeks, measured on: median time to first triage, bounce-back rate, weekly sample routing accuracy, agent edits per record.
- **First 30 days.**
  > (1) Week 1: shadow mode — records produced and logged, form not pre-filled, so the first 200-ticket eval is on real tickets. (2) Week 2: pre-fill on. (3) Week 4: first retrain from corrections, compared, promoted or not.
- **Sign-offs needed before pilot.**
  > Data owner (Maryam) on section 3 including the redaction step; security on the VM's network position and the log store; the desk lead on the workflow change; Faisal's manager on ownership.

## 10. Open questions (2 min)

| # | Question | Who | By when |
|---|---|---|---|
| 1 | Named owner confirmed by their manager | Faisal / desk lead | before Day 5 S29 |
| 2 | Secrets redaction mechanism before the call and in the log; false-positive rate on the 600 sample | integration architect | Day 3 evening |
| 3 | Serve the merged adapter on a current Ollama/vLLM instead of pinning Ollama 0.12.10 | platform engineer | before pilot; test on Day 5 S27 |
| 4 | p95 latency under 10 concurrent requests | all | Day 2 S8 |
| 5 | Is a data-zone deployment of the model family available in a Gulf region, for the flip case | integration architect | DPA review |
