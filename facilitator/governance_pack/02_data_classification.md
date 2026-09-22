# 2. Data classification and handling for AI workloads (12 min)

**Why this exists.** An AI integration moves text and images to
places they did not go before: into a prompt, into a vendor's
processing region, into a log, into an index, into a training set.
Each of those is a copy with its own retention and its own readers.
The live question for this room is not "cloud or laptop" but **who
runs the model**: a model on a VM in your own subscription is
self-hosted and nothing leaves it; a vendor model through your tenant
(Azure OpenAI, Claude in Foundry) is processed by the vendor's service
inside a geography you choose, under Microsoft's data processing
terms, and is not used for training [S12]; a vendor API key means the
vendor's own retention and abuse-monitoring rules apply, typically 30
days unless you are approved for zero retention [S13][S14]. Oman's
Personal Data Protection Law has been fully enforceable since
February 2026 and controls transfers of personal data outside the
country [S5], so a photo with a face in it, or a ticket with a name
in it, is a legal question before it is a technical one. This
template makes the copies visible, one row each, so the data owner can
sign a list instead of a diagram.

**Paste from:** spec §2 (the gates G1, G2 and who answered them), §3
(what goes into a prompt, classification, must-never-enter, storage
after the call). New writing: the copies table and the hosting
decision row.

**Done when:** every copy of the data has a row; every row has a
classification, a place and a retention; the data owner has signed.

---

## 2.1 Classification scheme in use

Use your organisation's scheme. If it has none for AI workloads, use
this one until it does:

| Class | Meaning | May go to a vendor model? |
|---|---|---|
| Public | Published or publishable | Yes |
| Internal | Business data, not secret; harm if leaked is embarrassment or minor cost | Through the tenant with a DPA (option B); direct (option A) only with the data owner's written yes |
| Confidential | Commercial, contractual, security-relevant, plant-critical | Self-hosted (C/D) unless the data owner and security approve B for this exact flow |
| Restricted | Personal data under PDPL [S5], credentials, safety-critical records | Self-hosted only, and personal data has its own legal basis and transfer rule (ask the DPO) |

> Scheme in use (name it, and who owns it):
>

## 2.2 Every copy of the data

One row per copy. "Where" is a system and a country, not a cloud name.

| Copy | Contents (fields, verbatim) | Class | Personal data? | Where it is processed / stored (system, region) | Retention | Who can read it |
|---|---|---|---|---|---|---|
| The prompt (spec §3) | | | | | | |
| Retrieved context added to the prompt | | | | | | |
| Tool results fed back to the model | | | | | | |
| The model's output | | | | | | |
| The audit log (template 5) | | | | | | |
| The index / knowledge base | | | | | | |
| Training or fine-tuning data | | | | | | |
| Images, if any (the photo itself, and thumbnails) | | | | | | |

## 2.3 The hosting decision, restated for the data owner

| | |
|---|---|
| Option chosen (A direct / B tenant / C host / D host and tune; spec §2) | |
| Where prompts are processed (region or data zone, or "the VM `<name>` in `<region>`") | |
| Does the provider store prompts or outputs? For how long? (vendor: quote the document and date [S12][S13][S14]) | |
| Is content used for training by the provider? (quote the document) | |
| Is there abuse monitoring with human review, and has modified monitoring been requested? [S12][S13] | |
| Gate G1 (may a vendor process this data at all) answered by whom, when | |
| Gate G2 (may it leave the country) answered by whom, when | |
| What flips the decision (spec §2) | |

## 2.4 Must never enter a prompt, a log or an index

The mechanism column is the one that matters. "We will be careful" is
not a mechanism.

| Thing | Where it could appear | Mechanism that stops it | Tested how, when |
|---|---|---|---|
| Credentials, tokens, pasted passwords | | | |
| Personal identifiers beyond what the job needs | | | |
| Whole document families out of scope (e.g. HR, contracts) | | | |
| Images of people, badges, screens with data | | | |
| Instructions hidden in input text (injection; the model must treat every input as data) [S7, LLM01] | | | |

## 2.5 Retention and deletion

| | |
|---|---|
| Who can delete a stored prompt, output or image, and how long it takes | |
| What happens to the index when a source document is withdrawn | |
| What happens to training data when a record is corrected or deleted | |
| Personal data: legal basis, and the transfer rule if any copy leaves Oman (DPO to confirm) [S5] | |

## 2.6 Sign-off

| Who | Name | Date |
|---|---|---|
| Data owner | | |
| Security | | |
| DPO (only if a personal-data row exists) | | |

Sources: [S5] Oman PDPL (RD 6/2022, ER MD 34/2024). [S12] Microsoft,
data privacy for models sold by Azure. [S13] OpenAI data controls.
[S14] Anthropic API data retention. [S7] OWASP LLM Top 10 2025,
LLM01 and LLM02. [S11] CISA, AI data security, for the training-data
rows.
