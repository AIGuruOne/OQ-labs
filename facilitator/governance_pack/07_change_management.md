# 7. Model and prompt change management (8 min)

**Why this exists.** In an ordinary integration a change is a code
diff, reviewed and rolled back by version control. In this one, six
things change behaviour and only one of them is code: the base model,
the adapter, the system prompt, the schema, the index build and the
thresholds (confidence floor, k, the invented-count rule). Notebook 06
already treats the adapter as a versioned artefact: its run id
carries the sha256 fingerprint of the weights, so two evals can never
be confused. This template extends that habit to the other five. The
rule is the one Day 2 S12 taught: nothing is promoted without a
before-and-after comparison on the same eval set, and a change that
lowers format or raises the invented count is not promoted, whatever
it improves elsewhere. The CISA data-security guidance asks for
provenance and integrity checks (hashes, signatures) on models and
data throughout the lifecycle [S11]; the NCSC/CISA guidelines put
update management under secure operation [S10]; ISO/IEC 42001 expects
the AI lifecycle, including change, to be managed as a process [S3].
Engineers know this already as "no untagged deploys". Here it is for
prompts.

**Paste from:** spec §4 (model, where it runs, version, who upgrades),
§8 (rollback). New writing: the version table, the promotion rule,
the rollback drill.

**Done when:** every versioned thing has a place where its version is
recorded and a rollback that was tried once; the promotion rule has a
name against it.

---

## 7.1 What is versioned, where, and how to go back

| Thing | Version identifier (what you write down) | Where it is recorded | Re-evaluation required before promotion | Rollback (command / action, and how long it takes) |
|---|---|---|---|---|
| Base model | name + digest (e.g. the Ollama model digest, or the vendor model version string) | | full eval set (template 3.1) | |
| Adapter / fine-tuned weights | sha256 of `adapter_model.safetensors` (first 8 hex digits as the short id, as notebook 06 prints) | | full eval set + compare against the model in use | `register_adapter.py --adapter <previous>` + restart, or the vendor deployment slot |
| System prompt | version number + sha256 of the text (`dataset_utils.SYSTEM_PROMPT` is the one copy in the lab) | | full eval set; **for a tuned model a prompt change means retraining** | |
| Output schema | schema version; frozen in the lab (`data/finetune/ticket_schema.json`) | | rebuild dataset, retrain, full eval | |
| Index build | `index_build_id` = build date + hash of the corpus manifest | | retrieval eval (golden answers, adversarial set) | keep the previous build; switch the pointer |
| Thresholds and rules | confidence floor, k, context cap, invented-count rule, approval classes; a version number on the config file | | the behaviour tests (template 3.3) | config rollback |
| Tool list / MCP server | `server_version`; the tool table in template 4 | | inspector test script; the injection test | previous server version |
| The code | git tag | | existing CI / tests | git |

## 7.2 The promotion rule

| | |
|---|---|
| Eval set used for every comparison (must be the same `dataset_sha256`; `--compare` refuses otherwise) | |
| Must not fall: format (schema-valid / citation present), invented count | |
| Must improve or hold: the field or answer accuracy the change was for | |
| Who runs the comparison, who signs the promotion (two people) | |
| Where the comparison file is kept (`comparison.json` beside the version table) | |
| Shadow or canary period for a promoted change, and the sample scored at its end | |

## 7.3 Change record (one row per change, kept with the pack)

| Date | Thing changed | From → to (identifiers) | Why | Comparison file | Result (promoted / rolled back) | Signed by |
|---|---|---|---|---|---|---|
| | | | | | | |

## 7.4 The rollback drill

Do it once before go-live, on the real deployment, and write the time.

| Rollback of | Tried on (date) | Took (minutes) | Anything that surprised you |
|---|---|---|---|
| Adapter / model | | | |
| Prompt or thresholds | | | |
| Index build | | | |

## 7.5 Retraining runbook (only if a tuned model is in use)

| Step | Do | Owner |
|---|---|---|
| 1 | Rebuild the dataset from confirmed records; run the quality checks (near-duplicates, leakage, schema, coverage, imbalance) | |
| 2 | Retrain; record the new fingerprint | |
| 3 | `run_eval.py` on the held-out set; `--compare` against the model in use | |
| 4 | Promotion rule (7.2); change record (7.3) | |
| 5 | Never retrain on the eval set, and never lift a number by moving items into training (the Day 2 warning) | |

## 7.6 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Deputy | | |

Sources: [S11] CISA and partners, AI data security best practices
(provenance, integrity). [S10] NCSC/CISA secure AI system development,
"secure operation and maintenance: update management". [S3] ISO/IEC
42001:2023 (AI lifecycle). Contract 4 in `docs/contracts.md` for the
comparison rule.
