# Pre-baked outputs: the capstone (Day 5, S27-S30)

The brief 5 build (`capstone/examples/brief5_similar_tickets.py`) and the
starter (`capstone/my_usecase.py`), run on 2026-09-23 as a group would.
A **LOCAL run**: Windows build laptop, Python 3.11, `hosted` =
gpt-4o-mini, `tuned` = the pre-baked adapter (`b1c0e3d4`) on Ollama
0.12.10. Absolute paths are replaced by `<repo>`, `<python>`, `<temp>`.
If a group's live run dies in S30, show these.

| File | What it is | Checklist item |
|---|---|---|
| `logs/A1_status.txt` | `status` on an empty output folder: every FALLBACK row | A1, A2 |
| `logs/A3_hosted.txt`, `logs/A4_tuned.txt` | a pasted GateKey VPN ticket, hosted then tuned | A3, A4 |
| `logs/A5_no_services.txt` | ERP and MCP off: the lookup says so, the pipeline answers (and the per-record fallback gap) | A5 |
| `logs/B1_*.txt`, `eval/` | the held-out 20 through each pipeline, scored by `run_eval.py`; `eval/comparison.txt` is the four-column table | B1-B4 |
| `logs/C4_injection.txt` | a ticket that tells the model to re-route itself | C4 |
| `logs/D3_tagged_ticket.txt`, `audit/tool_call.jsonl` | a ticket naming `HX-2629`: the MCP `get_equipment` call and its audit line | D3 |
| `audit/llm_call.jsonl` | all 85 model calls of the run (template 5.1.1) | D1, D2 |
| `audit/index_write_first3.jsonl` | the first 3 of the 580 lines written when the reference index was built (template 5.1.3) | - |

The filled checklist that cites these files:
`facilitator/examples/deployment_checklist_brief5_filled.md`.
