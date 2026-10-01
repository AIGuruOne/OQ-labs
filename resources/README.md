# Resources: the slides, and the files you fill in

Everything here opens in a PDF reader, Excel or Word. **Nothing here needs
Python**, so this folder is the place to start if you are coming back to the
material and do not want to set up an environment first.

All of it is synthetic program material: no real OQ data.

## Slide decks

All five days, plus the Azure follow-on.

| File | Covers |
|---|---|
| `OQ_Day1_Architect.pdf` | Fundamentals, build/buy/host, the architecture spec, peer review |
| `OQ_Day2_Own_the_Model.pdf` | Running a model yourself, scale, the dataset, fine-tuning, did it work |
| `OQ_Day3_Ground_It.pdf` | Retrieval, the golden set, vision on real documents |
| `OQ_Day4_Agents.pdf` | Tune versus retrieve, MCP, the agent graph, control and safety |
| `OQ_Day5_Integrate_and_Ship.pdf` | Build an MCP server, the capstone, governance, the showcase |
| `OQ_Colab_to_Azure.pdf` | Moving what you built in Colab onto an Azure VM in the OQ tenant |

`day5/OQ_Day5_Integrate_and_Ship_v2.pptx` is the editable source for the Day 5
deck, if you need to adapt it.

## Day 1 (Architect)

| File | Session | What you do with it |
|---|---|---|
| `day1/OQ_D1_S3_Decision_Matrix.xlsx` | S3, 11:15 | Answer the five gates, score the four hosting options, write the five sentences. The workbook does the arithmetic |
| `day1/OQ_D1_S4_Architecture_Spec_Template.docx` | S4, 12:45 | Your architecture spec, one per person. Type into the shaded boxes. Save as `Spec_<your name>_v0.1.docx` |
| `day1/OQ_D1_S4_Cost_Model.xlsx` | S4 | Volume and tokens in, monthly cost out, vendor API against self-hosted. Yellow cells are inputs. Feeds spec section 7 |
| `day1/OQ_D1_S5_Spec_Review_Checklist.docx` | S5, 14:15 | Review the next person's spec: 43 YES / NO / CAN'T TELL questions and three findings |
| `day1/OQ_D1_Use_Case_Briefs.pdf` | S4 and the close | The five capstone briefs. Read before you pick |

### Examples: what a good answer looks like

All three are filled for use case brief 1 (ticket triage). Use them to see
the level of detail, then write your own for your system.

| Example | Shows |
|---|---|
| Decision matrix workbook, sheet `Worked example` | Gates, scores and the five sentences for brief 1 |
| `day1/examples/OQ_D1_S4_Example_Spec_Brief1.pdf` | The spec template filled in: a v0.1 with real gaps left in |
| `day1/examples/OQ_D1_S5_Example_Review_Brief1.pdf` | The checklist applied to that spec: answers, three findings, two of them BLOCKS |
| `day1/OQ_D1_S4_Cost_Model.xlsx` as shipped | Its default inputs are the brief 1 service desk (scenario A) |

## Day 2 (Own the model)

| File | Session | What you do with it |
|---|---|---|
| `day2/OQ_D2_S8_Sizing_Worksheet.xlsx` | S8 | Your volumes and latency target in, how many servers out. Fill it from your own load test (`notebooks/03_concurrency.ipynb`) |
| `day2/OQ_D2_S12_Base_vs_Tuned_Scorecard.xlsx` | S12 | Record base against tuned on the four measurements, so the verdict is a number and not an impression |

## Day 3 (Ground it)

| File | Session | What you do with it |
|---|---|---|
| `day3/OQ_D3_S14_RAG_Blueprint.docx` | S14 | The retrieval design for your own system: sources, chunking, what happens when nothing matches |
| `day3/OQ_D3_S15_Golden_Set_Starter.xlsx` | S15 | The questions you will score against, with their expected answers. Start it here, grow it at your desk |
| `day3/OQ_D3_S16_Document_Vision_Pack.docx` | S16 | Which documents you would send to a vision model, what you do with the ones it cannot read |

### Examples

| Example | Shows |
|---|---|
| `day3/examples/OQ_D3_S14_Example_RAG_Blueprint_Brief2.pdf` | The blueprint filled in for use case brief 2 |
| `day3/examples/OQ_D3_S16_Example_Vision_Pack_Brief3.pdf` | The vision pack filled in for use case brief 3 |

## Day 4 (Agents)

| File | Session | What you do with it |
|---|---|---|
| `day4/OQ_D4_S19_Three_Way_Scorecard.xlsx` | S19 | Base, tuned and retrieval side by side on the same tickets, so "which approach" is answered with numbers |
| `day4/OQ_D4_S23_Rung_and_Cost_Sheet.xlsx` | S23 | Which rung of the ladder your use case actually needs, and what each rung costs |
| `day4/OQ_D4_S24_Agent_Design_Sheet.xlsx` | S24 | Your agent's steps, tools and gates written down before any code |
| `day4/OQ_D4_S25_Harness_Handout_Section4.docx` | S25 | The harness and loop hand-out, section 4 |
| `day4/OQ_D4_S25_Tool_and_MCP_Risk_Register.xlsx` | S25 | Every tool you expose, what it can break, and what gates it |
| `day4/OQ_D4_Close_Integration_Map.xlsx` | Close | Which OQ systems this touches, in which direction, through what |
| `day4/OQ_D4_Close_Spec_v05_Insert.docx` | Close | The pages that take your Day 1 spec from v0.1 to v0.5 |

### Examples

All three are filled for use case brief 4.

| Example | Shows |
|---|---|
| `day4/examples/OQ_D4_S24_Example_Agent_Design_Brief4.pdf` | The agent design sheet filled in |
| `day4/examples/OQ_D4_S25_Example_Risk_Register_Brief4.pdf` | The risk register filled in |
| `day4/examples/OQ_D4_Close_Example_Integration_Map_Brief4.pdf` | The integration map filled in |

## Day 5 (Integrate and ship)

| File | Session | What you do with it |
|---|---|---|
| `day5/Day5_Step_Card.pdf` | S26 | The MCP build sequence as a card you can keep beside the keyboard |
| `day5/Day5_Capstone_Quick_Card.pdf` | S27–S28 | The capstone at a glance: what to build, in what order |
| `day5/OQ_Day5_Deployment_Checklist.xlsx` | S28 | What has to be true before this runs against anything real |
| `day5/Day5_Governance_Stories_and_Template_Map.pdf` | S29 | Which governance template answers which question |
| `day5/OQ_Day5_Template1_System_Register.docx` | S29 | Governance template 1: the system register, with its named owner |
| `day5/OQ_Day5_Template4_Approval_Gating.docx` | S29 | Governance template 4: which tools need a person, and who |
| `day5/OQ_Day5_Peer_Scoring.xlsx` | S30 | The peer scoring sheet for the showcase |
| `day5/OQ_Day5_Runbook.pdf` | all day | The day's runbook |

### Open this one in a browser

`day5/OQ_Day5_Graph_Walkthrough.html` — the picnic agent, step by step, as a
single file. **Double-click it; there is nothing to install and no key to set.**
It is the fastest way back into "who actually runs a tool" if the agent sessions
have gone fuzzy. The live version, which really calls a model, is
`apps/oq_agent/` in this repo.

## Where these came from

Some of these are generated from Markdown sources in `facilitator/` — the
decision matrix, architecture spec, cost model, review checklist, sizing
worksheet, the harness hand-out, the governance templates, the deployment
checklist and the peer scoring sheet. For those, `facilitator/` is the original
and this folder is the Office version.

The rest — the Day 3 and Day 4 sheets, the Day 5 cards, the slide decks — have no
Markdown source. The file here is the original.

If a Markdown file and its Office version disagree, trust `facilitator/` and tell
the facilitator.
