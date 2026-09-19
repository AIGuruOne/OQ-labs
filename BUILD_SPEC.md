# OQ Advanced AI for IT | Lab Build Spec
 
**Version:** 1.0, 17 Sept 2026
**For:** Preety, Utkarsh, and the Claude sessions they work in
**Build window:** Fri 18 Sept to Wed 23 Sept. Freeze Thu 24 Sept. Program starts Sun 27 Sept
**Owner of decisions:** Ritesh Vajariya
 
---
 
## How to use this document
 
This is the single source of truth for what gets built. It is written to be handed to a Claude session or Claude Code along with the repo, so it carries the context the build needs without anyone having seen the conversations behind it.
 
If something needed is not in here, ask Ritesh. Do not invent curriculum. The program schedule in section 2 is fixed and has been time-budgeted; a lab that does not fit its slot gets cut, not extended.
 
Contents:
 
1. The engagement
2. Program schedule and what each session needs
3. Decisions locked
4. Team and slices
5. Interface contracts
6. Compute policy
7. Repo layout
8. Build items
9. Synthetic data rules
10. Working with Claude Code on this repo
11. Timing protocol
12. Definition of done
13. Day by day
14. Not in scope
15. Risks
16. Decision rights
17. Appendix: starter CLAUDE.md
---
 
## 1. The engagement
 
**Client:** OQ, an integrated energy company in Oman. Engaged through Tracez Global.
**Program:** Advanced AI for IT. Five days onsite in Muscat, Sunday 27 Sept to Thursday 1 Oct.
**Facilitator:** Ritesh Vajariya, all five days.
**Cohort:** 10 to 15 OQ IT practitioners in capstone groups of 2 to 3. Developers, integration architects, automation engineers, data engineers. They write Python and call REST APIs. They are not data scientists and will not own GPU clusters.
**What the week builds toward:** each group leaves with a deployment-ready AI integration for an OQ IT use case, plus eight take-away artifacts.
 
**What this means for the labs.** Everything must be ownable by an enterprise IT team after we leave. No research code, no training infrastructure, no dependency on a vendor being in the room. Where something is genuinely out of their reach, it gets shown and scoped honestly rather than faked as a lab.
 
**Confidentiality.** No real OQ data enters any lab. Everything in the corpus is synthetic. See section 9, which is a hard rule, not a preference.
 
---
 
## 2. Program schedule and what each session needs
 
Times are fixed. Session time per day is 320 minutes, running 08:30 to 15:15 with a mid-morning break, a Dhuhr and lunch break, and a mid-afternoon break. Every day ends at 15:15.
 
A session marked **talk** needs no notebook. Build nothing for it beyond slides support, which Ritesh owns.
 
### Day 1, Sun 27 Sept: ARCHITECT
 
| Time | Min | Session | Type | Needs | Owner |
|---|---|---|---|---|---|
| 08:30 | 15 | Welcome and program arc | Talk | | |
| 08:45 | 90 | S1. Fundamentals block, compressible to 45 | Lab | `01_fundamentals`, `setup_check.py` | Utkarsh |
| 10:30 | 45 | S2. September 2026 model landscape | Talk | | |
| 11:15 | 35 | S3. Build, buy or host | Talk | Decision matrix template | Utkarsh |
| 12:45 | 90 | S4. Architecture spec and cost model lab | Lab | Spec template, cost model sheet | Utkarsh |
| 14:30 | 25 | S5. Spec peer review | Discussion | Review checklist | Utkarsh |
| 14:55 | 20 | Close: capstone groups form | Facilitated | Five use case briefs | Utkarsh |
 
S1 runs long or short based on a live diagnostic in its first 10 minutes. Build both paths: the full 90-minute sequence and a 45-minute compressed path that skips to structured outputs and the agent loop. If compressed, the reclaimed 45 minutes runs a Claude Code configuration session, which also needs a short guide.
 
### Day 2, Mon 28 Sept: OWN THE MODEL
 
| Time | Min | Session | Type | Needs | Owner |
|---|---|---|---|---|---|
| 08:30 | 15 | S6. Why own the model | Talk | | |
| 08:45 | 50 | S7. Lab: run a model yourself | Lab | `02_local_inference`, Ollama setup guide | Utkarsh |
| 09:35 | 40 | S8. What breaks at scale | Lab then talk | `03_concurrency`, sizing worksheet | Utkarsh |
| 10:30 | 30 | S9. When to fine-tune | Talk | | |
| 11:00 | 50 | S10. Lab: build the dataset | Lab | `04_dataset_builder`, quality checks, seeded ticket set | Utkarsh |
| 12:45 | 90 | S11. Lab: fine-tune it | Lab | `05_finetune`, rubric template | Utkarsh |
| 14:30 | 45 | S12. Did it work | Lab | `06_compare_base_tuned`, eval harness | Utkarsh |
 
### Day 3, Tue 29 Sept: GROUND IT
 
| Time | Min | Session | Type | Needs | Owner |
|---|---|---|---|---|---|
| 08:30 | 10 | S13. Warm-up | Discussion | | |
| 08:40 | 65 | S14. Retrieval pipeline design | Talk | | |
| 09:45 | 110 | S15. Lab: full text pipeline, spans the break | Lab | `07_rag_pipeline`, text corpus, adversarial set, RAGAS config | Preety |
| 12:45 | 120 | S16. Vision and multimodal, spans the break | Talk and 3 labs | `08`, `09`, `10`, image set, `score_extraction.py` | Preety |
| 15:00 | 15 | Close | Discussion | | |
 
S16 internal shape: 20 min talk on vision failure modes, 25 min diagram extraction lab, 25 min scanned page lab, 30 min multimodal retrieval lab, 20 min industrial CV scoping talk.
 
### Day 4, Wed 30 Sept: AGENTS
 
| Time | Min | Session | Type | Needs | Owner |
|---|---|---|---|---|---|
| 08:30 | 40 | S19. Tune versus retrieve, settled | Lab | `11_three_way` | Preety |
| 09:10 | 25 | S20. The agent stack as a decision table | Talk | Decision table | Preety |
| 09:35 | 25 | S21. MCP | Talk | | |
| 10:00 | 25 | S22. MCP live, spans the break | Demo and setup | Two pre-built server configs, inspector guide | Preety |
| 10:40 | 70 | S23. Lab: the agent graph | Lab | `12_agent_graph` | Preety |
| 12:45 | 90 | S24. Lab: control | Lab | `13_agent_control` | Preety |
| 14:30 | 30 | S25. Agent safety and emerging patterns | Talk and demo | Injection demo, harness and loop handout | Preety |
| 15:00 | 15 | Close: integration mapping | Worksheet | Mapping worksheet | Preety |
 
### Day 5, Thu 1 Oct: INTEGRATE, DEPLOY, SHOWCASE
 
Day 5 uses a custom afternoon schedule so the showcase keeps a full hour.
 
| Time | Min | Session | Type | Needs | Owner |
|---|---|---|---|---|---|
| 08:30 | 80 | S26. Custom MCP server, guided class build | Type-along | Mock ERP API, reference MCP server, inspector tests | Utkarsh |
| 09:50 | 25 | S27. Capstone assembly begins | Build | Capstone scaffold, production engineering handout | Utkarsh |
| 10:30 | 80 | S28. Capstone assembly | Build | Same | Utkarsh |
| 12:45 | 30 | S29. Governance and deployment pack | Talk and template | Governance pack templates | Utkarsh |
| 13:15 | 30 | Final polish | Build | Deployment checklist | Utkarsh |
| 14:00 | 65 | S30. Showcase and peer review | Presentations | Peer scoring sheet | Utkarsh |
| 15:05 | 10 | Synthesis and close | Talk | | |
 
### Notebook to session map
 
| Notebook | Session | Declared runtime budget |
|---|---|---|
| `01_fundamentals` | D1 S1 | 60 min of the 90 min block |
| `02_local_inference` | D2 S7 | 40 min of 50 |
| `03_concurrency` | D2 S8 | 15 min of 40 |
| `04_dataset_builder` | D2 S10 | 40 min of 50 |
| `05_finetune` | D2 S11 | Training completes in 25 min; block is 90 |
| `05b_finetune_mlx` | Learner variant | Same output, Apple Silicon |
| `06_compare_base_tuned` | D2 S12 | 25 min of 45 |
| `07_rag_pipeline` | D3 S15 | 95 min of 110, three passes |
| `08_vision_diagram` | D3 S16 lab 1 | 20 min of 25 |
| `09_vision_scanned` | D3 S16 lab 2 | 20 min of 25 |
| `10_multimodal_retrieval` | D3 S16 lab 3 | 25 min of 30 |
| `11_three_way` | D4 S19 | 25 min of 40 |
| `12_agent_graph` | D4 S23 | 60 min of 70 |
| `13_agent_control` | D4 S24 | 75 min of 90 |
 
The gap between the notebook budget and the session length is deliberate: it absorbs setup, questions and the one laptop that goes wrong. Do not fill it.
 
---
 
## 3. Decisions locked
 
| # | Decision | Locked |
|---|---|---|
| 1 | Fine-tune task | **IT service desk ticket to structured record.** Free-text ticket in, strict JSON out. Schema in section 8B |
| 2 | Build and demo platform | **Colab.** Everything is built, tested and demonstrated in Colab. Local is the fallback if OQ's network blocks it |
| 3 | Corpus size | **60 to 80 documents**, roughly 200 pages equivalent, 50 as the floor |
| 4 | Learner platform | **Open.** Notebooks are dual-runtime so this can be decided as late as Day 1 |
 
**Why the ticket task.** It is a format task, so tuning genuinely helps. It is the cohort's daily reality, so nobody needs the domain explained. It lands on one of the five capstone use cases. And the three-way comparison stays honest: the tuned model wins on schema adherence, retrieval wins on factual lookup, the base model is verbose and inconsistent. Each earns its place, which is the lesson. A knowledge task would make retrieval win everything and make Day 2 look wasted.
 
### Three audiences, not one
 
| Audience | Runs on |
|---|---|
| Preety and Utkarsh, building | Colab. Nobody is asked to own a particular laptop spec, and there is one environment to debug |
| Ritesh, demonstrating | Colab, with a tested local path on his machine if OQ blocks Google services |
| Participants | Open, decided when the laptop inventory arrives |
 
**What Colab-first costs: one line in the Day 3 vision lab.** The original framing was that the image never leaves the laptop, answering the data classification objection. In Colab it plainly does leave. Reframe the lesson as self-hosted versus vendor API rather than laptop versus cloud: a model on a VM you control is self-hosted, and the Colab runtime stands in for OQ's own Azure VM. That is also what OQ will actually deploy. Notebook 08 should carry this framing in its opening markdown cell.
 
---
 
## 4. Team and slices
 
Split by vertical slice, not by layer. Each person owns whole program days end to end: the data that day consumes, the notebooks, the eval, the solutions, and the pre-baked outputs.
 
| | Owns | Program days |
|---|---|---|
| **Preety** | The retrieval and reasoning chain | Day 3 and Day 4 |
| **Utkarsh** | The model and infrastructure chain | Day 1, Day 2 and Day 5, plus the repo foundation |
| **Ritesh** | Rubric, plausibility review, dry runs, slides, cuts | All |
 
**A slice includes everything it needs.** If your day needs data, you build the data. If it needs an eval, you build the eval. If it needs a service running, you build the service. No handoffs mid-slice.
 
**New to you is not a reason to hand it over.** The vision renderers, the MCP server, the concurrency script and the agent graph are new work for whoever gets them. That is the job. Ask each other, ask Ritesh, read the docs, use Claude. The only thing that travels between the two slices is a question, not a task.
 
Corpus splits by consumer: Preety builds the documents her retrieval labs read, Utkarsh builds the tickets his fine-tuning consumes.
 
| Owner | Slice contents |
|---|---|
| Utkarsh | **Foundation:** repo scaffold, pinned requirements, `setup_check.py`, `CLAUDE.md`, notebook conventions, endpoint config |
| Utkarsh | **Day 1:** fundamentals notebook, spec and cost model templates, five use case briefs, review checklist |
| Utkarsh | **Day 2 morning:** Ollama setup guide, concurrency script, sizing worksheet, notebooks 02 and 03 |
| Utkarsh | **Day 2 afternoon:** 600 service tickets, schema, dataset builder, quality checks with planted problems, fine-tune notebook, MLX variant, eval harness, pre-baked adapter |
| Utkarsh | **Day 5:** mock ERP API, reference MCP server, inspector tests, capstone scaffold, governance templates, production handout, peer scoring sheet |
| Preety | **Day 3 morning:** text corpus with planted traps, ingestion and chunking, hybrid and rerank, adversarial set, golden answers, RAGAS config, notebook 07 |
| Preety | **Day 3 afternoon:** image renderers, image set across three tiers, known-bad case, `score_extraction.py`, notebooks 08 to 10, multimodal indexing pattern |
| Preety | **Day 4:** three-way comparison notebook, agent stack decision table, two pre-built MCP server configs, agent graph and control notebooks, injection demo, harness and loop handout, mapping worksheet |
 
---
 
## 5. Interface contracts
 
Agreed Friday 09:00, in thirty minutes. These are the only places the two slices touch.
 
| # | Contract | Owner |
|---|---|---|
| 1 | Corpus directory layout and document frontmatter format | Preety proposes, both agree |
| 2 | Notebook conventions: header cell, runtime declaration, pinned install cell, TODO marker style, environment detection | Utkarsh proposes, both agree |
| 3 | Endpoint config: one module that switches local Ollama, hosted API, or tuned adapter | Utkarsh owns, Preety consumes |
| 4 | Eval output format, so every scored table composes into the three-way comparison | Both, Ritesh on the rubric |
| 5 | Index interface, so the retrieval pipeline is callable from the agent notebook and the Day 5 capstone scaffold | Preety owns, Utkarsh consumes |
 
Write each contract down in `docs/contracts.md` on Friday. A contract that only exists in a conversation is not a contract.
 
**Daily 15-minute sync at 09:00.** Three things only: what shipped, what is blocked, whether a contract needs to change.
 
---
 
## 6. Compute policy
 
100 Colab compute units cover the build, the testing, three dry runs and one demo rehearsal. The failure mode is not heavy computation. It is a GPU runtime left connected while somebody writes code.
 
**The rule that decides whether the budget holds: write on CPU, execute on GPU, disconnect immediately.** A CPU runtime costs nothing, and most of the work needs no accelerator: notebook structure, data generation, prompts, scoring logic, chunking, API calls.
 
| Rule | Why |
|---|---|
| **T4 unless a model genuinely will not fit** | Higher accelerator tiers cost several times more per hour, and these labs target small models. This single choice decides the budget |
| **Develop on CPU runtimes** | Units burn while a GPU runtime is connected, not only while it computes |
| **50 units each, burn reported at the Monday sync** | Half gone by Monday means something is being brute-forced that should be debugged |
| **Hold about 30 units in reserve for Tue to Thu** | Dry runs and rehearsal are the runs that matter most and cannot hit an empty balance |
 
GPU work is roughly: fine-tune test runs at 20 minutes each, vision extraction across the image set against two models, three timed dry runs, one rehearsal. Everything else is CPU.
 
**Nothing shipped may require Pro.** The cold free-tier test in section 12 catches violations.
 
---
 
## 7. Repo layout
 
```
oq-advanced-ai/
  README.md                     entry point, 20-minute setup promise
  CLAUDE.md                     see appendix
  requirements.txt              fully pinned, no ranges
  docs/
    contracts.md                the five interface contracts
    timing_log.md               measured lab durations
    failure_playbook.md
  setup/
    setup_check.py              environment diagnostic, pass/fail table
    ollama_setup.md             Colab and local
    .env.example
  config/
    endpoints.py                local / API / tuned adapter switch
  corpus/
    manuals/  hse/  maintenance/  tickets/  images/
    README.md                   provenance statement
  data/
    finetune/{train,val}.jsonl
    eval/heldout_20.jsonl
    eval/rubric.md
    eval/rag_adversarial.jsonl
    eval/golden_answers.jsonl
    eval/image_ground_truth/
  notebooks/                    participant versions, TODO gaps
  solutions/                    completed, with outputs retained
  scripts/
    run_eval.py
    score_extraction.py
    quality_checks.py
    render_images.py
    generate_tickets.py
  services/
    mock_erp/                   FastAPI, runs locally and in Colab
    mcp_server_reference/
  checkpoints/
    adapter_prebaked/
  facilitator/
    prebaked_outputs/
    slides/
```
 
Two versions per notebook is the rule: `notebooks/` has gaps to fill, `solutions/` runs clean. Never one file with commented-out answers.
 
---
 
## 8. Build items
 
Ownership is in section 4. This is what exists, not who builds it.
 
### A. Synthetic corpus
 
| Family | Detail |
|---|---|
| Equipment manuals | Pumps, compressors, heat exchangers, valves. Every asset carries a tag in a consistent format. Tags are what make the hybrid search lesson land |
| HSE procedures | Permit to work, confined space entry, lockout, gas testing. Markdown with a real header hierarchy, because header-aware chunking is taught against these |
| Maintenance and work order history | Structured records: date, tag, failure mode, action taken, parts |
| Service desk tickets | ~600, generated. Primary family, since the fine-tune task is built on it |
| Images | Section B2 |
 
**Planted retrieval traps, deliberate:**
- The same equipment tag in two documents with different revision dates
- A procedure that supersedes another with no explicit cross-reference
- A term with two meanings across document families
- One scanned-looking page, an image of text, that breaks normal ingestion
### B. Fine-tuning dataset: ticket to structured record
 
```json
{
  "category": "access | hardware | software | network | erp | telecom | other",
  "affected_system": "string or null",
  "asset_tag": "string or null",
  "urgency": "low | medium | high | critical",
  "impact": "single_user | team | site | enterprise",
  "requested_action": "one short imperative clause",
  "routing_queue": "string"
}
```
 
Five of seven fields are enums or nullable strings, so scoring is exact match and needs no human judgement. `requested_action` is the one generative field. `urgency` is where defensible disagreement lives, which makes the Day 2 rubric conversation worth having.
 
| Item | Detail |
|---|---|
| Train | ~400 pairs |
| Validation | ~80 pairs |
| Held-out eval | 20 pairs, never in train or val, used by Day 2 S12 and Day 4 S19 |
| Dataset builder | Turns raw corpus tickets into pairs. Participants extend it, they do not start blank |
| Quality checks | Duplicates, validation leakage, schema violations, coverage gaps, class imbalance |
 
**Class distribution must be realistically imbalanced.** Access and password tickets dominate, telecom and ERP are rare. Do not balance it. An even distribution flatters the tuned model and hides a real problem the quality check should surface.
 
**Plant the problems the checks find:** ~20 near-duplicates, 5 rows leaking train into validation, 10 schema violations such as a missing enum value, stray prose inside a field, or a malformed asset tag. Participants find real problems in 90 seconds.
 
### B2. Image set with ground truth
 
**Generate images from structured data, so ground truth costs nothing.** Every image renders from a spec file, and the spec is the ground truth. Write the component list, render the diagram from it, and scoring becomes a dictionary comparison. Hand-labelling would eat a day of the week.
 
| Asset | Count | Made from | Ground truth |
|---|---|---|---|
| P&ID-style diagrams | 10 to 12 | SVG rendered from JSON: components, tags, connections, line types | The spec |
| Equipment nameplates | 8 to 10 | Rendered from an equipment record, then aged with noise, skew, glare | The record |
| Scanned procedure pages | 5 to 6 | HSE procedure Markdown rendered to page images with scan artefacts: skew, speckle, a signature scrawl, one at poor contrast | The source Markdown |
| Inspection photos with handwriting | 4 to 5 | Rendered scene plus a handwritten-style overlay from a known string | The string |
| Known-bad case | 1 | A diagram rendered so a plausible misreading is likely, for example two tags at low separation | The spec plus the expected wrong answer |
 
**Difficulty tiers matter.** Three clean, three moderate, two genuinely hard per family. If everything is clean the models look perfect and the block teaches nothing.
 
**Diagrams must use real ISA symbol conventions and tag formats, not boxes with labels.** This is the credibility risk of the whole block: the room reads P&IDs daily. Ritesh reviews Tuesday.
 
**The known-bad case feeds lab 3.** Its wrong extraction goes into the index and gets retrieved and cited as fact, which is the governance argument for Day 5. It must reproduce reliably across at least three runs, not happen by luck.
 
### C. Eval harness
 
Machine-scored, not a room arguing about quality.
 
| Item | Detail |
|---|---|
| `run_eval.py` | Takes a model endpoint and a dataset, returns a scored table. Works against Ollama, a hosted API, or a tuned adapter with no code change |
| Rubric | Mostly machine-checkable for the ticket task. At most two human-judged dimensions |
| Base versus tuned | Day 2 S12. One command, one table |
| Three-way | Day 4 S19. Base, tuned, base plus retrieval, same 20 questions, one table |
| `score_extraction.py` | Compares an image extraction against ground truth. Reports fields correct, fields missed, and **components invented as a separate number**, never folded into an accuracy score |
| RAG adversarial set | Exact tags, multi-hop, ambiguous phrasing, plus golden answers |
| RAGAS config | Faithfulness, answer relevancy, context precision, pinned version |
 
Design the rubric so Day 2 scoring takes 15 minutes of reading results, not 40 minutes of debate.
 
### D. Notebooks
 
Every notebook declares at the top: expected runtime, what it needs, and what a correct result looks like.
 
Three requirements from building Colab-first. These are the difference between a notebook that demos and one that dies mid-session.
 
| Requirement | What it means |
|---|---|
| **Environment detection cell** | First code cell detects Colab versus local and branches: install path, file paths, whether to mount Drive. One notebook, two environments, no forked copies |
| **Drive persistence at every milestone** | Runtimes disconnect. Vector store, trained adapter, extraction results and eval tables all save as produced. A disconnect costs the current cell, never the session. The Day 3 morning lab runs 110 minutes and will not survive otherwise |
| **Resumable from any checkpoint** | Reconnect, remount, reload, continue. Nobody restarts a 40-minute ingestion because a tab went idle |
 
**Ollama inside Colab works.** Install it in the runtime, serve it, hit localhost. The Day 2 concurrency lesson still lands, because a sequential backend degrades the same way under load. Absolute numbers differ from a laptop, and the notebook says so rather than pretending otherwise.
 
**Distribution is a GitHub repo with Open in Colab links**, not shared Drive files. Version controlled, one source of truth.
 
### E. Services
 
| Item | Detail |
|---|---|
| Mock ERP API | FastAPI. Work orders, maintenance history, equipment master. Read endpoints plus one write endpoint, because the write is what the approval interrupt gates. Runs locally and inside a Colab runtime |
| Reference MCP server | Against the mock ERP, built to the 2026-07-28 spec. Typed tools, read-only by default, secrets from environment, an audit log line per tool call |
| Inspector test script | Proves the server works before anything connects to it |
 
### F. Facilitator kit
 
| Item | Detail |
|---|---|
| `timing_log.md` | Measured wall-clock duration of every lab from dry runs. If a lab overruns, it gets cut before travel, not in the room |
| `failure_playbook.md` | The 15 likeliest breakages with fixes: Colab blocked, runtime disconnect, GPU unavailable, Ollama will not start, model pull too slow, no API key, pip blocked, OOM, port in use, Drive not mounting |
| Pre-baked outputs | A saved result for every lab. If a lab dies, show the output and keep moving. **The highest-value insurance item in the build** |
| Pre-baked adapter | A trained adapter in the repo, so Day 2 S12 and Day 4 S19 work even if nobody's training completes |
| Slides | Ritesh owns content. Engineers supply every number and screenshot from actual runs, never invented |
 
### G. Environment check
 
`setup/setup_check.py` prints a pass or fail table: Python version, pip install works, API key present and a call succeeds, Ollama reachable, Drive mountable, disk space, GPU present or absent. This is what the Day 1 diagnostic runs, and what goes out in the pre-program email so failures surface before Sunday.
 
---
 
## 9. Synthetic data rules
 
These are hard rules. A breach here is a client problem, not a bug.
 
| Rule | Detail |
|---|---|
| **Nothing real** | No scraped OQ material, no real OQ site names, no real asset tags, no real employee names, no real incident records. Invent sites, people and tags |
| **Provenance recorded** | `corpus/README.md` states that every document is synthetic, how it was generated, and that no OQ or third-party source material was used |
| **No real third-party content either** | Do not lift procedure text from another operator's public documents. Generate it |
 
**Consistency conventions, agreed Friday and used by both slices:**
 
| Thing | Format | Example shape |
|---|---|---|
| Equipment tag | Letter prefix, dash, four digits, optional letter suffix | `P-1201A`, `HX-3040` |
| Site code | Three letters, invented, not OQ's real facilities | `MRB`, `SHZ` |
| Ticket ID | Prefix plus six digits | `INC-004412` |
| Work order ID | Prefix plus six digits | `WO-118305` |
| Asset tag for IT kit | Prefix plus five digits | `LAP-04412` |
| Dates | ISO 8601 throughout | `2026-08-14` |
 
**Make generated text genuinely messy.** A model asked for 600 tickets will produce 600 clean, similar, well-formed paragraphs, and the labs will teach nothing because extraction becomes trivial. Force variation deliberately:
 
- Run-on sentences and missing punctuation
- Typos and inconsistent capitalisation
- Missing information the schema wants, so `null` handling gets exercised
- Two unrelated problems in one ticket
- Non-native English phrasing, since OQ's workforce is mixed. Respectful and realistic, never caricature
- Pasted error strings and stack fragments
- References to screenshots that are not attached
- Users guessing at causes and being wrong
- Wildly varying length, from one line to a wall of text
Same principle for maintenance records and manuals: inconsistent heading depth, a table that spans a page break, an appendix referenced but missing.
 
---
 
## 10. Working with Claude Code on this repo
 
Both engineers will use Claude and Claude Code. These conventions keep an agent productive and stop it from quietly breaking the build.
 
### Notebooks are teaching material, not production code
 
An agent writes dense, elegant, clever code. Lab notebooks need the opposite: obvious, linear, readable code that a mid-level Python developer can follow while under time pressure in a room in Muscat.
 
| Do | Do not |
|---|---|
| One idea per cell | Chain six operations into a comprehension |
| Explicit intermediate variables with plain names | Clever one-liners |
| Print the shape of what just happened | Silent success |
| Markdown cell before every code cell explaining why | Code that assumes the reader infers intent |
| Small helper functions in a `utils.py` the notebook imports | 80-line functions inline in a cell |
 
The test: could a participant read the cell, understand what it does, and modify it, without help, in under a minute?
 
### Forbidden without asking Ritesh
 
| Never | Why |
|---|---|
| `pip install -U` or unpinned installs | The stack freezes on 24 Sept. An agent upgrading a package on 23 Sept invalidates every dry run |
| Change the ticket schema | Every eval, dataset and comparison depends on it |
| Change session timings or lab durations | The schedule is time-budgeted and fixed |
| Move to a bigger model or accelerator tier to make something work | Fix the approach instead, or raise it. The tier is a hard constraint |
| Commit API keys, or notebook outputs containing keys | Obvious, and easy for an agent to do accidentally |
| Add a dependency that needs compilation or a system package | It will fail on somebody's machine on Day 1 |
 
### Repo hygiene
 
- Pin everything in `requirements.txt`. Exact versions, no ranges
- Clear outputs before committing anything in `notebooks/`. Keep outputs in `solutions/`, since those are the reference
- Secrets via `.env` only, `.env.example` committed, `.env` git-ignored
- A branch per slice, merged to main daily. Main must always be runnable
- Every script takes arguments rather than hardcoding paths, so it works in Colab and locally
### Good ways to use Claude on this build
 
- Generating the synthetic corpus and tickets, with the messiness rules in section 9 in the prompt
- Writing the renderers, then reviewing their output against real P&ID conventions
- Drafting the failure playbook from actual errors encountered, not imagined ones
- Reviewing the other person's notebook for legibility against the table above
- Writing the markdown explanation cells, which is where notebooks usually get thin
### Check work with a fresh session
 
When something is done, open a new Claude session with no history, hand it the notebook and this spec, and ask whether the notebook meets its declared runtime budget and legibility bar. A session that watched the code get written is the worst reviewer of it.
 
---
 
## 11. Timing protocol
 
The schedule lives or dies on this. "It took about twenty minutes" is not a measurement.
 
For every lab:
 
1. Fresh runtime, cold. No cached packages, no warm session
2. Start a wall clock at the first cell
3. Run top to bottom with no manual intervention
4. Stop the clock when the declared output exists
5. Record in `docs/timing_log.md`: notebook, date, runtime type (Colab CPU, Colab T4, local), accelerator, measured minutes, and anything that needed a retry
6. Run it twice. If the two differ by more than 20 percent, find out why before recording
A lab that exceeds its declared budget in section 2 gets simplified or cut. Report it at the daily sync the day you measure it, not the day before travel.
 
---
 
## 12. Definition of done
 
Nothing ships until it passes these.
 
| Test | Standard |
|---|---|
| **Cold Colab, free tier** | Every notebook runs on a fresh free-tier runtime in an account that has never opened it, within its declared budget. Not a warm Pro session with packages cached. **The single most important test here** |
| **Survives a disconnect** | Kill the runtime mid-lab, reconnect, remount, continue from the last checkpoint without redoing completed work |
| **Runs locally too** | The environment detection path works on a local machine, verified once per slice before freeze |
| **No Pro dependency** | If it needs Colab Pro, it is not finished |
| **Restart and run all** | Top to bottom, no manual intervention, no hidden state |
| **Cross-check, not self-check** | Each person runs the other's slice before it counts as done |
| **Timed and recorded** | Two measured runs in `timing_log.md`, inside the section 2 budget |
| **Solution parity** | Every participant notebook has a solution producing the documented result |
| **Legibility** | Passes the section 10 table. A participant can read any cell and modify it in under a minute |
| **Pre-baked output exists** | Every lab has a saved result the facilitator can show if the live run dies |
| **Clean data** | Section 9 rules hold. Provenance documented |
| **No secrets** | No keys in code, config, or committed notebook outputs |
 
---
 
## 13. Day by day
 
| Day | Preety | Utkarsh | Ritesh |
|---|---|---|---|
| **Fri 18** | Contracts, 09:00, written to `docs/contracts.md`. Text corpus: manuals, HSE procedures, tags, planted traps | Contracts, 09:00. Repo scaffold, pinned requirements, `setup_check.py`, notebook conventions, endpoint config | Sign off section 3. Ticket schema review |
| **Sat 19** | Corpus: maintenance records, provenance README. Ingestion and chunking working | 600 tickets with realistic imbalance and the messiness rules applied. Dataset builder and quality checks | Rubric design with Utkarsh |
| **Sun 20** | Notebook 07 end to end: pipeline, hybrid, rerank, with Drive checkpointing. Adversarial set started | Fine-tune notebook. **First cold free-tier run, timed and logged** | Review corpus and tickets for oil and gas plausibility |
| **Mon 21** | Image renderers, all four types, spec-to-image | Notebooks 01, 02, 03 including Ollama inside Colab. Pre-bake the adapter. MLX variant if time allows | Slides from real outputs. Compute burn check |
| **Tue 22** | Image set across three tiers, known-bad case, `score_extraction.py`, notebook 08 | Mock ERP API, reference MCP server, inspector tests | **Dry-run Day 2 end to end, timed.** Review diagrams against real P&ID conventions |
| **Wed 23** | Notebooks 09, 10, 11. Pre-baked vision outputs. Agent notebooks 12, 13 | Capstone scaffold, governance templates, production handout, failure playbook | **Dry-run Day 3 and Day 4, timed.** Cut anything that overruns |
| **Thu 24** | Freeze. Cold free-tier test of every notebook in her slices. Pre-baked outputs verified | Same. Local path verified per slice. Lab pack to OQ | Sign off. **Demo fallback ladder tested: Colab, hotspot, fully local** |
 
**Critical paths.** Utkarsh: tickets to dataset to fine-tune notebook to dry run. Preety: corpus to pipeline to renderers to vision notebooks. The renderers must work by Monday evening or the vision notebooks have nothing to run against.
 
**If the week tightens,** the Day 5 slice narrows first: mock API plus a single-tool MCP server, thinner capstone scaffold. It has the most slack because groups build on top of it rather than following it step by step. Then the industrial CV segment becomes a handout. Then Day 4 depth.
 
---
 
## 14. Not in scope
 
Say no to these now, so nobody builds them on Tuesday night.
 
- Object detection training. No YOLO, no bounding boxes, no PPE detector. Industrial CV is a 20-minute scoping talk, not a build
- Vision model fine-tuning. Text fine-tuning only
- Full fine-tunes, multi-GPU training, anything needing a reserved GPU
- Serving a large model at production concurrency. Discussed with published numbers and shown, not run
- Production authentication on the mock ERP. Environment secrets in lab, OIDC discussed in the talk
- Any custom UI or dashboard
- CI, containerisation, packaging for redistribution
- Five separate capstone starter kits. One scaffold plus five use case briefs
---
 
## 15. Risks
 
| Risk | Mitigation |
|---|---|
| **OQ blocks Colab outright.** An energy company's DLP may block Google services by policy, not just proxy. This ends the demo | Three-step ladder, all tested before travel: Colab over OQ network, Colab over phone hotspot, fully local on the facilitator machine. Step one tested from an actual OQ network port on Sat 26, not from the hotel |
| **Runtime disconnects mid-lab.** Day 3 morning runs 110 minutes | Drive checkpointing at every milestone plus resumability. A notebook requirement, not a hope |
| **Compute gone before the dry runs** | CPU for development, T4 only, 30 units reserved, burn checked Monday. Topping up is cheap next to a dry run that cannot happen |
| **Synthetic diagrams look nothing like a real P&ID** | The credibility risk of the vision block. Real ISA conventions and tag formats. Ritesh reviews Tuesday, Wednesday has room for one rework pass |
| **Generated corpus is too clean**, so extraction is trivial and the labs teach nothing | Section 9 messiness rules, applied at generation time and spot-checked by the other engineer |
| **The known-bad extraction does not reproduce** | Verified across three runs. If it is luck rather than reliable, the pre-baked version is what gets shown |
| **A lab overruns and eats the next session** | The timing log exists for this. Cut on Wednesday, not in the room |
| **One slice slips and the other cannot cover it** | The cost of vertical ownership. Daily sync catches it on day one rather than day four. Cut order is fixed in advance |
| **Model pull over venue Wi-Fi is slow** | Pull during Day 1 tech check, not Day 2. Carry model files offline as backup |
 
---
 
## 16. Decision rights
 
| Decide yourself | Raise with Ritesh |
|---|---|
| Library choice within the pinned stack | Adding or upgrading a dependency |
| Notebook structure, cell ordering, helper design | Lab duration or session order |
| Corpus content and volume within section 8 ranges | The ticket schema, the eval rubric, the difficulty tiers |
| How to generate or render something | Dropping a lab, or converting a lab to a demo |
| Naming inside your own slice | Anything touching an interface contract |
| Your own working order within the week | Model tier, accelerator tier, anything needing Pro |
 
When blocked more than an hour, raise it. The week is too short to lose half a day being stuck politely.
 
---
 
## 17. Appendix: starter CLAUDE.md
 
Drop this in the repo root on Friday. Utkarsh owns it thereafter.
 
```markdown
# OQ Advanced AI for IT: lab repo
 
Teaching material for a 5-day onsite program with OQ (Oman energy company) IT
practitioners, 27 Sept to 1 Oct 2026. Read BUILD_SPEC.md before doing anything.
 
## What this repo is
Notebooks, synthetic data, eval scripts and services for hands-on labs.
This is teaching material, not production code. Legibility beats elegance
every time.
 
## Hard rules
- NEVER run `pip install -U` or add unpinned dependencies. The stack freezes
  24 Sept. Ask before adding any dependency.
- NEVER change the ticket schema in data/finetune. Every eval depends on it.
- NEVER change lab durations or session order. The schedule is time-budgeted.
- NEVER move to a bigger model or accelerator to make something work. Fix the
  approach or raise it.
- NEVER commit secrets, or notebook outputs containing them.
- All synthetic data only. No real OQ material, names, sites or asset tags.
 
## Notebook style
- One idea per cell. Explicit intermediate variables. Plain names.
- A markdown cell before every code cell explaining why, not what.
- Print the shape or a sample of what just happened. No silent success.
- Helpers go in utils.py and get imported, not inlined at 80 lines.
- Test: can a participant read a cell and modify it in under a minute?
 
## Two versions of every notebook
- notebooks/ has TODO gaps for participants. Outputs cleared before commit.
- solutions/ runs clean end to end. Outputs retained as the reference.
 
## Every notebook must
- Detect Colab versus local in the first code cell and branch accordingly.
- Save to Drive at every milestone. Runtimes disconnect.
- Resume from the last checkpoint after a reconnect.
- Declare at the top: expected runtime, requirements, what correct looks like.
- Run on a cold free-tier Colab runtime within its declared budget.
 
## Conventions
- Equipment tags: P-1201A. Site codes: three invented letters. Tickets:
  INC-004412. Work orders: WO-118305. IT assets: LAP-04412. Dates: ISO 8601.
- Scripts take arguments. No hardcoded paths.
- Pinned versions only, exact, no ranges.
 
## Commands
- Environment check: `python setup/setup_check.py`
- Eval: `python scripts/run_eval.py --dataset <path> --endpoint <name>`
- Image scoring: `python scripts/score_extraction.py --pred <path> --truth <path>`
- Data quality: `python scripts/quality_checks.py --dataset <path>`
- Mock ERP: `uvicorn services.mock_erp.main:app --reload`
```